"""
core/data_fetcher.py
Kiến trúc thu thập và chuẩn hóa dữ liệu tài chính đa nguồn (Multi-Source Ingestion):
- Tích hợp chuỗi nguồn miễn phí (core.sources): VNDirect (Cổ phiếu) -> VPS (Chỉ số) -> yfinance -> FRED
- Kiểm định chất lượng nghiêm ngặt (core.data_quality) trước khi ghi vào tầng CLEAN (ohlcv_daily)
- Cơ chế Rolling Refresh (7 ngày gần nhất) tránh lỗi mù lòa chia tách/cổ tức của Incremental Update
- Đồng bộ tự động Vĩ mô, Hàng hóa toàn cầu và Lợi suất Trái phiếu Mỹ FRED
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, date, timedelta
from typing import Optional, Callable

import numpy as np
import pandas as pd
import requests

from config.settings import DB_PATH, LOGS_DIR, MANUAL_DATA_DIR, DATA_WINDOW_START
from config.tickers import (
    TIER_1_UNIVERSE, MACRO_COMMODITY_TICKERS, VINGROUP_TICKERS, get_exchange
)
from core.db_manager import (
    get_connection, save_ohlcv_daily, save_ohlcv_global, save_raw_ohlcv,
    _write_rejected
)
from core.sources import (
    fetch_ohlcv, fetch_macro, fetch_yield_curve
)
from core.data_quality import validate_frame

logger = logging.getLogger(__name__)


class FREDProvider:
    """Tải chuỗi dữ liệu Đường cong Lợi suất Trái phiếu Mỹ từ URL CSV công khai của FRED."""
    URL_T10Y2Y = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
    URL_T10Y3M = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y3M"

    @classmethod
    def fetch_yield_curve(cls) -> Optional[pd.DataFrame]:
        return fetch_yield_curve()


def fetch_stock_ohlcv(ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
    """
    Tải OHLCV cho 1 mã qua chuỗi nguồn tự động (VNDirect -> VPS -> yfinance).
    Trả về DataFrame đã kiểm định sạch, kèm các thuộc tính nguồn.
    """
    result = fetch_ohlcv(ticker, start_date=start_date, end_date=end_date)
    if result.ok and result.df is not None and not result.df.empty:
        return result.df
    return None


def sync_database(tickers: list = None, exchange: str = None, progress_callback: Optional[Callable] = None,
                  lookback_refresh_days: int = 7) -> dict:
    """
    Thực hiện đồng bộ dữ liệu vào Local SQLite Database:
    - Hỗ trợ đồng bộ theo danh sách tickers hoặc theo sàn (exchange = 'HOSE' | 'HNX' | 'UPCOM' | 'ALL' | 'TIER_1')
    - Cơ chế Rolling Refresh (mặc định 7 ngày): Tải từ `max_date - 7 days` để cập nhật các điều chỉnh sau giao dịch
    - Kiểm tra và phân loại sàn giao dịch tự động
    - Ghi nhận đầy đủ nguồn gốc (source) và kiểm tra tính toàn vẹn
    """
    conn = get_connection()
    cursor = conn.cursor()

    if tickers is not None:
        target_tickers = tickers
    elif exchange:
        from config.tickers import get_tickers_by_exchange
        target_tickers = get_tickers_by_exchange(exchange)
    else:
        target_tickers = TIER_1_UNIVERSE
    # Đưa VNINDEX lên đầu danh sách để làm mốc tham chiếu
    all_symbols = ['VNINDEX'] + [t for t in target_tickers if t != 'VNINDEX']

    total = len(all_symbols) + len(MACRO_COMMODITY_TICKERS) + 1
    current_step = 0
    synced_stocks = 0
    failed_stocks = []
    run_id = f"sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 1. Đồng bộ cổ phiếu & VN-Index
    for sym in all_symbols:
        cursor.execute("SELECT MAX(date) FROM ohlcv_daily WHERE ticker = ?;", (sym,))
        row = cursor.fetchone()
        max_d = row[0] if row else None

        start_d = DATA_WINDOW_START
        if max_d:
            # Lùi lại lookback_refresh_days để cập nhật các điều chỉnh giá đóng cửa/cổ tức
            refresh_d = pd.to_datetime(max_d) - timedelta(days=lookback_refresh_days)
            start_d = max(refresh_d.strftime("%Y-%m-%d"), DATA_WINDOW_START)

        try:
            result = fetch_ohlcv(sym, start_date=start_d, run_id=run_id)
            if result.ok and result.df is not None and not result.df.empty:
                raw_df = result.df
                save_raw_ohlcv(raw_df, sym, result.source)
                clean_df, rejected_df, report = validate_frame(
                    raw_df, sym, exchange=get_exchange(sym), run_id=run_id
                )
                if not rejected_df.empty:
                    _write_rejected([
                        (sym, str(row["date"])[:10], row.get("open"), row.get("high"),
                         row.get("low"), row.get("close"), row.get("volume"), result.source,
                         row.get("_issue", "QUALITY_REJECTED"), None)
                        for _, row in rejected_df.iterrows()
                    ])
                save_stats = save_ohlcv_daily(clean_df, sym, source=result.source)
                if save_stats.get("written", 0) > 0:
                    synced_stocks += 1
            elif not max_d:
                failed_stocks.append(sym)
        except Exception as e:
            logger.warning(f"Lỗi khi đồng bộ {sym}: {e}")
            if not max_d:
                failed_stocks.append(sym)

        current_step += 1
        if progress_callback:
            progress_callback(current_step / total, f"Đang đồng bộ {sym} ({current_step}/{total})...")
        time.sleep(0.05)

    # 2. Đồng bộ Vĩ mô & Hàng hóa quốc tế
    for macro_sym, label in MACRO_COMMODITY_TICKERS.items():
        cursor.execute("SELECT MAX(date) FROM ohlcv_global WHERE ticker = ?;", (macro_sym,))
        row = cursor.fetchone()
        max_d = row[0] if row else None

        start_d = None
        if max_d:
            refresh_d = pd.to_datetime(max_d) - timedelta(days=lookback_refresh_days)
            start_d = refresh_d.strftime("%Y-%m-%d")

        try:
            result = fetch_macro(macro_sym, start_date=start_d, run_id=run_id)
            if result.ok and result.df is not None and not result.df.empty:
                save_ohlcv_global(result.df, macro_sym)
        except Exception as e:
            logger.warning(f"Lỗi đồng bộ vĩ mô {label} ({macro_sym}): {e}")

        current_step += 1
        if progress_callback:
            progress_callback(current_step / total, f"Đang đồng bộ vĩ mô {label}...")
        time.sleep(0.05)

    # 3. Đồng bộ FRED Yield Curve
    try:
        df_yield = fetch_yield_curve(run_id=run_id)
        if df_yield is not None and not df_yield.empty:
            records = []
            for _, r in df_yield.iterrows():
                d_str = str(r['date'])[:10]
                t2y = float(r['t10y2y']) if pd.notna(r['t10y2y']) else None
                t3m = float(r['t10y3m']) if pd.notna(r['t10y3m']) else None
                if t2y is not None:
                    records.append((d_str, t2y, t3m))
            if records:
                cursor.executemany("INSERT OR REPLACE INTO yield_curve (date, t10y2y, t10y3m) VALUES (?, ?, ?);", records)
                conn.commit()
    except Exception as e:
        logger.error(f"Lỗi đồng bộ FRED Yield Curve: {e}")

    conn.close()

    if progress_callback:
        progress_callback(1.0, "Đồng bộ hoàn tất!")

    return {
        "synced_count": synced_stocks,
        "failed_tickers": failed_stocks,
        "total_attempted": len(all_symbols)
    }
