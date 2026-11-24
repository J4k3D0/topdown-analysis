"""
core/db_manager.py
Quản lý kết nối và thao tác với SQLite Local Database (WAL mode, Foreign Keys, Indexing).

Kiến trúc phân lớp dữ liệu (bổ sung, không phá vỡ tên bảng cũ):
- L0 META      : schema_version, data_sources, ingest_log, data_quality_log, ohlcv_rejected
- L1 RAW       : raw_ohlcv, raw_macro, raw_corporate_actions, raw_fundamentals,
                 raw_derivatives, raw_warrants  (append-only, giữ nguyên gốc từ nguồn)
- L2 CLEAN     : các bảng nghiệp vụ theo 6 tầng (ohlcv_daily, fundamentals, margin_history,
                 derivatives_daily, warrants, trade_journal, ...) - chỉ ghi sau khi kiểm định
- L3 FEATURE   : feature_cache (chỉ báo tính sẵn theo mã/khung, chống tính lặp)
- L4 ANALYTICS : signal_log, backtest_runs, backtest_trades (đo hiệu quả thực tế)
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, date
import pandas as pd

from config.settings import DB_PATH, LOGS_DIR
from config.tickers import (
    TIER_1_UNIVERSE, SECTOR_MAPPING, FINANCIAL_TICKERS, VINGROUP_TICKERS, get_exchange
)
from config.vn_holidays import trading_day_mask

SCHEMA_VERSION = "6.0.0"

# Cấu hình logging
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def get_connection():
    """Khởi tạo kết nối SQLite với cấu hình WAL mode và tối ưu hiệu năng."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Tạo mới 12 bảng và các chỉ mục nếu chưa tồn tại, kèm nạp dữ liệu mẫu ban đầu."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Bảng metadata cổ phiếu
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_metadata (
        ticker TEXT PRIMARY KEY,
        exchange TEXT,
        icb_sector TEXT,
        icb_industry TEXT,
        is_financial INTEGER DEFAULT 0,
        is_vingroup INTEGER DEFAULT 0,
        universe_tier INTEGER DEFAULT 1,
        listed_shares REAL,
        market_cap_bn REAL,
        last_updated DATE,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    # 2. Bảng OHLCV cổ phiếu & chỉ số VN (đơn vị kVND cho cổ phiếu, điểm cho chỉ số)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ohlcv_daily (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        is_adjusted INTEGER DEFAULT 1,
        PRIMARY KEY (ticker, date)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_date ON ohlcv_daily(date);")

    # 3. Bảng OHLCV Vĩ mô & Hàng hóa quốc tế
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ohlcv_global (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (ticker, date)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_global_date ON ohlcv_global(date);")

    # 4. Bảng Phái sinh VN30F
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS derivatives_daily (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        settlement_price REAL,
        volume INTEGER,
        oi INTEGER,
        PRIMARY KEY (ticker, date)
    );
    """)

    # 5. Bảng Chỉ số Tài chính Cơ bản theo Quý
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fundamentals (
        ticker TEXT NOT NULL,
        quarter TEXT NOT NULL,
        pe REAL,
        pb REAL,
        bvps REAL,
        total_debt REAL,
        equity REAL,
        debt_to_equity REAL,
        revenue REAL,
        net_income REAL,
        source TEXT DEFAULT 'manual_csv',
        PRIMARY KEY (ticker, quarter)
    );
    """)

    # 6. Bảng Dư nợ Margin Tổng hợp
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS margin_history (
        quarter TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT 'market_total',
        total_margin_bn REAL,
        free_float_ratio REAL,
        avg_liquidity_bn REAL,
        vnindex_close REAL,
        source TEXT,
        notes TEXT,
        PRIMARY KEY (quarter, scope)
    );
    """)

    # 7. Bảng Chứng quyền metadata & giá
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warrants (
        cw_ticker TEXT PRIMARY KEY,
        underlying TEXT NOT NULL,
        exercise_type TEXT DEFAULT 'CALL',
        strike_price_vnd REAL NOT NULL,
        maturity_date DATE NOT NULL,
        conversion_ratio REAL NOT NULL,
        issuer TEXT,
        last_price_vnd REAL,
        last_updated DATE,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    # 8. Bảng Nhật ký Lệnh (Chỉ BUY, hỗ trợ Scaling-out 50/50 trên 1 dòng gốc)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        entry_date DATE NOT NULL,
        entry_price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        stop_loss REAL,
        trailing_stop REAL,
        target_1 REAL,
        target_2 REAL,
        status TEXT DEFAULT 'OPEN',
        exit_date_1 DATE,
        exit_price_1 REAL,
        exit_qty_1 INTEGER DEFAULT 0,
        exit_date_2 DATE,
        exit_price_2 REAL,
        exit_qty_2 INTEGER DEFAULT 0,
        pnl_pct REAL,
        notes TEXT
    );
    """)

    # 9. Bảng Đường Trendline Vẽ tay Persist SQLite
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_drawings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        label TEXT,
        date_1 DATE NOT NULL,
        price_1 REAL NOT NULL,
        date_2 DATE NOT NULL,
        price_2 REAL NOT NULL,
        extend_right INTEGER DEFAULT 1,
        color TEXT DEFAULT '#FCC934',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drawings_ticker_tf ON user_drawings(ticker, timeframe);")

    # 10. Bảng Đường cong Lợi suất FRED
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS yield_curve (
        date DATE PRIMARY KEY,
        t10y2y REAL,
        t10y3m REAL
    );
    """)

    # 11. Bảng Sự kiện Chính trị / Chính sách Vĩ mô
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS macro_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date DATE,
        event_type TEXT,
        description TEXT,
        impact TEXT
    );
    """)

    # 12. Bảng Lưu Cấu hình Người dùng Bền vững
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 13. Các lớp dữ liệu L0 / L1 / L3 / L4
    _create_layer_tables(cursor)

    conn.commit()

    # Khởi tạo danh sách metadata mặc định cho Tier 1
    _seed_metadata(cursor)
    # Đăng ký danh mục nguồn dữ liệu miễn phí
    _seed_data_sources(cursor)
    # Ghi nhận phiên bản schema
    cursor.execute(
        "INSERT OR REPLACE INTO schema_version (key, value, applied_at) VALUES (?, ?, CURRENT_TIMESTAMP);",
        ("schema_version", SCHEMA_VERSION)
    )
    # Nạp 2 lệnh mẫu thực chiến KDH & NLG
    _seed_trade_journal(cursor)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully with 12 business tables + layered data tables.")


def _create_layer_tables(cursor):
    """Tạo các bảng L0 META, L1 RAW, L3 FEATURE, L4 ANALYTICS (idempotent)."""

    # ---------------- L0 META ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_sources (
        name TEXT PRIMARY KEY,
        kind TEXT,                -- stock | index | macro | fundamentals | derivatives
        layer TEXT,               -- nguồn cấp dữ liệu (L1)
        priority INTEGER,         -- 1 = ưu tiên cao nhất
        base_url TEXT,
        is_free INTEGER DEFAULT 1,
        requires_key INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE',
        last_ok_at DATETIME,
        last_error TEXT,
        notes TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ingest_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        source TEXT,
        dataset TEXT,             -- ohlcv | macro | yield_curve | fundamentals | derivatives
        ticker TEXT,
        started_at DATETIME,
        finished_at DATETIME,
        rows_in INTEGER DEFAULT 0,
        rows_written INTEGER DEFAULT 0,
        rows_rejected INTEGER DEFAULT 0,
        status TEXT,              -- OK | FALLBACK | FAILED | EMPTY
        message TEXT
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingest_log_ticker ON ingest_log(ticker, dataset);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ingest_log_time ON ingest_log(started_at);")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_quality_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT,
        ticker TEXT,
        date DATE,
        issue TEXT,               -- HOLIDAY | ZERO_VOLUME | OHLC_INVALID | LIMIT_BREACH_UP | ...
        severity TEXT,            -- INFO | WARN | ERROR
        action TEXT,              -- DELETED | QUARANTINED | BACK_ADJUSTED | KEPT
        detail TEXT,
        detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dq_log_ticker ON data_quality_log(ticker, issue);")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ohlcv_rejected (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        source TEXT,
        issue TEXT NOT NULL,
        detail TEXT,
        rejected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, date, issue)
    );
    """)

    # Lịch giao dịch thực tế suy ra từ chỉ số (chuẩn nhất, không phụ thuộc thư viện lễ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cal_trading_days (
        date DATE PRIMARY KEY,
        is_trading INTEGER NOT NULL,
        source TEXT DEFAULT 'VNINDEX',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ---------------- L1 RAW (append-only, giữ nguyên gốc) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_ohlcv (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        source TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL,
        volume REAL,
        raw_close REAL,
        ceiling_price REAL,
        floor_price REAL,
        exchange TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, date, source)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_ohlcv_ticker ON raw_ohlcv(ticker, date);")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_macro (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        source TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, date, source)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_corporate_actions (
        ticker TEXT NOT NULL,
        ex_date DATE NOT NULL,
        source TEXT NOT NULL,
        action_type TEXT NOT NULL,   -- SPLIT | BONUS | DIVIDEND_CASH | CONSOLIDATION
        ratio REAL,
        cash_amount REAL,
        note TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, ex_date, source, action_type)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_fundamentals (
        ticker TEXT NOT NULL,
        quarter TEXT NOT NULL,
        source TEXT NOT NULL,
        metric TEXT NOT NULL,
        value REAL,
        unit TEXT,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, quarter, source, metric)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_derivatives (
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        source TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL,
        volume REAL, oi REAL,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, date, source)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_warrants (
        cw_ticker TEXT NOT NULL,
        date DATE NOT NULL,
        source TEXT NOT NULL,
        price REAL, volume REAL,
        fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (cw_ticker, date, source)
    );
    """)

    # ---------------- L3 FEATURE (cache chỉ báo) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feature_cache (
        ticker TEXT NOT NULL,
        timeframe TEXT NOT NULL,     -- 1D | 1W | 1M
        params_key TEXT NOT NULL,    -- băm cấu hình chỉ báo
        as_of_date DATE,
        payload BLOB,                -- DataFrame pickle
        rows INTEGER,
        built_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (ticker, timeframe, params_key)
    );
    """)

    # ---------------- L4 ANALYTICS ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        date DATE NOT NULL,
        preset TEXT NOT NULL,
        enhanced INTEGER DEFAULT 0,
        close REAL,
        score REAL,
        features TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (ticker, date, preset, enhanced)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id TEXT PRIMARY KEY,
        preset TEXT,
        start_date DATE,
        end_date DATE,
        universe TEXT,
        params TEXT,
        metrics TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backtest_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        preset TEXT,
        enhanced INTEGER DEFAULT 0,
        entry_date DATE,
        entry_price REAL,
        exit_date DATE,
        exit_price REAL,
        exit_reason TEXT,
        pnl_pct REAL,
        pnl_net_pct REAL,
        bars_held INTEGER,
        result TEXT,
        FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON backtest_trades(run_id);")

def _seed_metadata(cursor):
    """Điền danh mục các mã vào stock_metadata và chuẩn hóa sàn niêm yết (HOSE, HNX, UPCOM)."""
    from config.tickers import (
        TIER_1_UNIVERSE, HNX_TICKERS, UPCOM_TICKERS,
        FINANCIAL_TICKERS, VINGROUP_TICKERS, SECTOR_MAPPING, get_exchange
    )
    sector_lookup = {}
    for sec, t_list in SECTOR_MAPPING.items():
        for t in t_list:
            sector_lookup[t] = sec

    all_seed_tickers = sorted(list(set(TIER_1_UNIVERSE + HNX_TICKERS + UPCOM_TICKERS)))
    for ticker in all_seed_tickers:
        is_fin = 1 if ticker in FINANCIAL_TICKERS else 0
        is_vin = 1 if ticker in VINGROUP_TICKERS else 0
        sec = sector_lookup.get(ticker, "Khác")
        exch = get_exchange(ticker)
        cursor.execute("""
        INSERT INTO stock_metadata
        (ticker, exchange, icb_sector, is_financial, is_vingroup, universe_tier, status)
        VALUES (?, ?, ?, ?, ?, 1, 'ACTIVE')
        ON CONFLICT(ticker) DO UPDATE SET exchange = excluded.exchange, icb_sector = excluded.icb_sector;
        """, (ticker, exch, sec, is_fin, is_vin))


def sync_stock_metadata_exchanges(conn=None):
    """
    Đồng bộ và chuẩn hóa trường exchange ('HOSE', 'HNX', 'UPCOM') cho toàn bộ mã trong stock_metadata.
    Đồng thời nạp thêm các mã HNX và UPCOM mới nếu chưa có.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    cursor = conn.cursor()
    _seed_metadata(cursor)
    conn.commit()
    if should_close:
        conn.close()


def _seed_data_sources(cursor):
    """Đăng ký danh mục nguồn dữ liệu miễn phí (0 credential) và thứ tự ưu tiên."""
    sources = [
        # name, kind, layer, priority, base_url, is_free, requires_key, notes
        ("vndirect", "stock", "L1", 1, "https://api-finfo.vndirect.com.vn/v4", 1, 0,
         "Giá đã điều chỉnh + trần/sàn thực tế + sàn niêm yết từng phiên. Nguồn chính cho cổ phiếu."),
        ("vps", "stock+index", "L1", 2, "https://histdatafeed.vps.com.vn", 1, 0,
         "Feed TradingView công khai. Nguồn chính cho VNINDEX (yfinance đã ngừng trả ^VNINDEX)."),
        ("yfinance", "stock+macro", "L1", 3, "https://query1.finance.yahoo.com", 1, 0,
         "Dự phòng cho cổ phiếu (.VN) và nguồn chính cho vĩ mô/hàng hóa quốc tế."),
        ("fred", "macro", "L1", 1, "https://fred.stlouisfed.org", 1, 0,
         "Đường cong lợi suất T10Y2Y / T10Y3M."),
        ("vnstock", "stock+fundamentals", "L1", 1, "https://vnstocks.com", 1, 0,
         "vnstock free (guest ~20 req/phút). Tự động bỏ qua nếu chưa cài hoặc bị chặn."),
        ("ssi_iboard", "derivatives", "L1", 2, "https://iboard-query.ssi.com.vn", 1, 0,
         "Bảng giá phái sinh / chứng quyền EOD."),
        ("local_manual", "manual", "L1", 9, None, 1, 0,
         "File Excel/CSV thủ công trong data/manual (margin, BCTC, CW)."),
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO data_sources
    (name, kind, layer, priority, base_url, is_free, requires_key, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, sources)

def _seed_trade_journal(cursor):
    """Nạp sẵn 2 lệnh mẫu thực chiến theo đúng hồ sơ ca nghiên cứu (KDH & NLG)."""
    cursor.execute("SELECT COUNT(*) FROM trade_journal;")
    if cursor.fetchone()[0] == 0:
        # Lệnh KDH: Mua 14.0 ngày 05/11/2026, chốt 15.7 ngày 13/11/2026 (CLOSED, lãi +12.14%)
        cursor.execute("""
        INSERT INTO trade_journal (
            ticker, entry_date, entry_price, quantity,
            stop_loss, trailing_stop, target_1, target_2,
            status, exit_date_1, exit_price_1, exit_qty_1,
            exit_date_2, exit_price_2, exit_qty_2, pnl_pct, notes
        ) VALUES (
            'KDH', '2026-11-05', 14.0, 10000,
            13.2, 14.8, 15.5, 16.5,
            'CLOSED', '2026-11-13', 15.7, 10000,
            NULL, NULL, 0, 12.14, 'Case study bắt đáy chu kỳ MA200(1M) + Fisher âm sâu. Đã chốt toàn bộ tại cản MA120(1D).'
        );
        """)

        # Lệnh NLG: Mua 21.2 ngày 03/11/2026, Trailing stop 23.8-24.1, Target 1: 26.2-26.8, Target 2: 29.5-31.3 (OPEN)
        cursor.execute("""
        INSERT INTO trade_journal (
            ticker, entry_date, entry_price, quantity,
            stop_loss, trailing_stop, target_1, target_2,
            status, exit_date_1, exit_price_1, exit_qty_1,
            exit_date_2, exit_price_2, exit_qty_2, pnl_pct, notes
        ) VALUES (
            'NLG', '2026-11-03', 21.2, 10000,
            19.8, 24.1, 26.5, 30.5,
            'OPEN', NULL, NULL, 0,
            NULL, NULL, 0, 0.0, 'Vị thế đang gồng lãi theo sóng tuần, quản trị Trailing Stop theo EMA21/MA50(1D).'
        );
        """)

# --- Các hàm truy vấn & cập nhật bảng dữ liệu ---

def get_db_max_date(ticker: str = None) -> str:
    """Trả về ngày giao dịch gần nhất có trong cơ sở dữ liệu (của 1 mã hoặc toàn bộ)."""
    conn = get_connection()
    cursor = conn.cursor()
    if ticker:
        cursor.execute("SELECT MAX(date) FROM ohlcv_daily WHERE ticker = ?;", (ticker,))
    else:
        cursor.execute("SELECT MAX(date) FROM ohlcv_daily;")
    res = cursor.fetchone()[0]
    conn.close()
    return res

def save_ohlcv_daily(df: pd.DataFrame, ticker: str, source: str = "clean", strict: bool = True) -> dict:
    """
    Ghi chuỗi OHLCV ĐÃ KIỂM ĐỊNH vào lớp CLEAN (ohlcv_daily).

    Chặn ngay từ đầu vào (mọi nến bị chặn đều được lưu vết vào ohlcv_rejected):
    - Nến rơi vào ngày không giao dịch (Thứ 7, Chủ Nhật, ngày lễ) -> không giao dịch thì không có nến.
    - Nến có volume <= 0 -> không có giao dịch thật.
    - Nến OHLC không nhất quán (high < low, close ngoài [low, high]).
    - Giá <= 0 hoặc thiếu trường bắt buộc.

    Trả về dict thống kê: {"written", "rejected", "issues"}.
    """
    stats = {"written": 0, "rejected": 0, "issues": {}}
    if df is None or len(df) == 0:
        return stats

    work = df.copy()
    for col in ("date", "open", "high", "low", "close", "volume"):
        if col not in work.columns:
            logger.warning(f"{ticker}: thiếu cột {col}, bỏ qua ghi dữ liệu.")
            return stats

    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        work[col] = pd.to_numeric(work[col], errors="coerce")

    is_adj = work["is_adjusted"].fillna(1).astype(int) if "is_adjusted" in work.columns else 1

    # --- Phân loại lỗi ---
    valid_date = work["date"].notna()
    trading = pd.Series(False, index=work.index)
    if valid_date.any():
        trading.loc[valid_date] = trading_day_mask(work.loc[valid_date, "date"])

    has_price = work[["open", "high", "low", "close"]].notna().all(axis=1) & (work["close"] > 0)
    vol_ok = work["volume"].fillna(0) > 0
    hl_ok = (work["high"] >= work["low"] * 0.999) & \
            (work["close"] <= work["high"] * 1.001) & (work["close"] >= work["low"] * 0.999) & \
            (work["open"] <= work["high"] * 1.001) & (work["open"] >= work["low"] * 0.999)

    issue_map = {
        "INVALID_DATE": ~valid_date,
        "NON_TRADING_DAY": valid_date & ~trading,
        "ZERO_VOLUME": valid_date & trading & ~vol_ok,
        "OHLC_INVALID": valid_date & trading & vol_ok & ~(has_price & hl_ok),
    }

    keep = valid_date & trading & vol_ok & has_price & hl_ok
    if strict is False:
        keep = valid_date & has_price

    rejected_rows = []
    for issue, mask in issue_map.items():
        if mask.any():
            stats["issues"][issue] = int(mask.sum())
            sub = work.loc[mask]
            for _, r in sub.iterrows():
                rejected_rows.append((
                    ticker,
                    r["date"].strftime("%Y-%m-%d") if pd.notna(r["date"]) else "1900-01-01",
                    _f(r.get("open")), _f(r.get("high")), _f(r.get("low")), _f(r.get("close")),
                    _f(r.get("volume")), source, issue, None
                ))
    if rejected_rows:
        _write_rejected(rejected_rows)
        stats["rejected"] = len(rejected_rows)

    # --- Ghi phần hợp lệ ---
    valid = work.loc[keep]
    if len(valid) == 0:
        return stats

    records = []
    for idx, row in valid.iterrows():
        adj = int(is_adj.loc[idx]) if hasattr(is_adj, "loc") else 1
        records.append((
            ticker,
            row["date"].strftime("%Y-%m-%d"),
            float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]),
            int(row["volume"]), adj
        ))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany("""
    INSERT OR REPLACE INTO ohlcv_daily
    (ticker, date, open, high, low, close, volume, is_adjusted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, records)
    last_dt = max(r[1] for r in records)
    cursor.execute("UPDATE stock_metadata SET last_updated = ? WHERE ticker = ?;", (last_dt, ticker))
    conn.commit()
    conn.close()

    stats["written"] = len(records)
    return stats


def _f(v):
    try:
        return float(v) if pd.notna(v) else None
    except (TypeError, ValueError):
        return None


def _write_rejected(rows, conn=None):
    """Lưu các nến bị loại vào bảng kiểm toán ohlcv_rejected."""
    own = conn is None
    if own:
        conn = get_connection()
    conn.executemany("""
    INSERT OR REPLACE INTO ohlcv_rejected
    (ticker, date, open, high, low, close, volume, source, issue, detail)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)
    if own:
        conn.commit()
        conn.close()


def replace_ohlcv(ticker: str, df: pd.DataFrame, source: str = "repair") -> dict:
    """Xóa toàn bộ chuỗi cũ của 1 mã rồi ghi lại chuỗi đã kiểm định (dùng cho repair)."""
    conn = get_connection()
    conn.execute("DELETE FROM ohlcv_daily WHERE ticker = ?;", (ticker,))
    conn.commit()
    conn.close()
    return save_ohlcv_daily(df, ticker, source=source)


def delete_ohlcv(ticker: str, start_date: str = None, end_date: str = None) -> int:
    """Xóa các nến của 1 mã (toàn bộ hoặc theo khoảng ngày)."""
    conn = get_connection()
    query = "DELETE FROM ohlcv_daily WHERE ticker = ?"
    params = [ticker]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    cur = conn.execute(query, params)
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


# --- L1 RAW: lưu nguyên bản dữ liệu từ nguồn (append-only, có provenance) ---

def save_raw_ohlcv(df: pd.DataFrame, ticker: str, source: str) -> int:
    """Ghi dữ liệu gốc vào L1 RAW, giữ cả giá gốc và trần/sàn công bố nếu có."""
    if df is None or len(df) == 0:
        return 0
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work[work["date"].notna()]
    if len(work) == 0:
        return 0

    def col(name):
        return work[name] if name in work.columns else pd.Series([None] * len(work), index=work.index)

    rows = []
    for i, (_, r) in enumerate(work.iterrows()):
        rows.append((
            ticker, r["date"].strftime("%Y-%m-%d"), source,
            _f(r.get("open")), _f(r.get("high")), _f(r.get("low")), _f(r.get("close")),
            _f(r.get("volume")), _f(r.get("raw_close")),
            _f(r.get("ceiling_price")), _f(r.get("floor_price")),
            r.get("exchange"),
        ))
    conn = get_connection()
    conn.executemany("""
    INSERT OR REPLACE INTO raw_ohlcv
    (ticker, date, source, open, high, low, close, volume, raw_close,
     ceiling_price, floor_price, exchange, fetched_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """, rows)
    conn.commit()
    conn.close()
    return len(rows)


def load_raw_ohlcv(ticker: str, source: str = None) -> pd.DataFrame:
    """Đọc dữ liệu gốc từ L1 RAW (dùng khi mất mạng)."""
    conn = get_connection()
    query = "SELECT * FROM raw_ohlcv WHERE ticker = ?"
    params = [ticker]
    if source:
        query += " AND source = ?"
        params.append(source)
    query += " ORDER BY date ASC;"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


# --- L0 META: log thu thập & kiểm định ---

def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def log_ingest(run_id: str, source: str, dataset: str, ticker: str,
               started_at, rows_in: int = 0, rows_written: int = 0,
               rows_rejected: int = 0, status: str = "OK", message: str = ""):
    """Ghi 1 dòng log thu thập dữ liệu vào L0 META."""
    try:
        conn = get_connection()
        conn.execute("""
        INSERT INTO ingest_log
        (run_id, source, dataset, ticker, started_at, finished_at,
         rows_in, rows_written, rows_rejected, status, message)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?);
        """, (run_id, source, dataset, ticker, str(started_at), rows_in,
              rows_written, rows_rejected, status, message))
        if status == "OK":
            conn.execute("UPDATE data_sources SET last_ok_at = CURRENT_TIMESTAMP, status = 'ACTIVE' WHERE name = ?;", (source,))
        elif status in ("FAILED", "FALLBACK"):
            conn.execute("UPDATE data_sources SET last_error = ? WHERE name = ?;", (message[:300], source))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"log_ingest thất bại: {e}")


def log_quality(run_id: str, ticker: str, dt, issue: str, severity: str,
                action: str, detail: str = ""):
    """Ghi 1 dòng log kiểm định chất lượng dữ liệu."""
    try:
        conn = get_connection()
        conn.execute("""
        INSERT INTO data_quality_log (run_id, ticker, date, issue, severity, action, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (run_id, ticker, str(dt)[:10] if dt is not None else None,
              issue, severity, action, detail))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"log_quality thất bại: {e}")


def get_schema_version() -> str:
    try:
        conn = get_connection()
        row = conn.execute("SELECT value FROM schema_version WHERE key = 'schema_version';").fetchone()
        conn.close()
        return row[0] if row else "unknown"
    except Exception:
        return "unknown"


def quality_summary() -> dict:
    """
    Tổng hợp nhanh trạng thái chất lượng dữ liệu của lớp CLEAN
    (dùng cho badge cảnh báo trên giao diện).
    """
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM ohlcv_daily;").fetchone()[0]
        tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_daily;").fetchone()[0]
        zerovol = conn.execute("SELECT COUNT(*) FROM ohlcv_daily WHERE volume IS NULL OR volume <= 0;").fetchone()[0]
        try:
            rejected = conn.execute("SELECT COUNT(*) FROM ohlcv_rejected;").fetchone()[0]
        except Exception:
            rejected = 0
        last = conn.execute("SELECT MAX(date) FROM ohlcv_daily;").fetchone()[0]
    finally:
        conn.close()
    return {
        "rows": total,
        "tickers": tickers,
        "zero_volume": zerovol,
        "rejected": rejected,
        "last_date": last,
        "schema_version": get_schema_version(),
        "ok": zerovol == 0 and total > 0,
    }

def load_ohlcv(ticker: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """Tải chuỗi dữ liệu OHLCV 1D từ SQLite cho 1 mã cổ phiếu."""
    conn = get_connection()
    query = "SELECT date, open, high, low, close, volume FROM ohlcv_daily WHERE ticker = ?"
    params = [ticker]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " ORDER BY date ASC;"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=False)
    return df

def save_ohlcv_global(df: pd.DataFrame, ticker: str):
    """Lưu chuỗi dữ liệu vĩ mô / hàng hóa quốc tế vào ohlcv_global."""
    if df is None or df.empty:
        return
    conn = get_connection()
    cursor = conn.cursor()
    records = []
    for _, row in df.iterrows():
        dt = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
        records.append((
            ticker,
            dt,
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            int(row['volume']) if 'volume' in row and pd.notna(row['volume']) else 0
        ))
    cursor.executemany("""
    INSERT OR REPLACE INTO ohlcv_global
    (ticker, date, open, high, low, close, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """, records)
    conn.commit()
    conn.close()

def load_ohlcv_global(ticker: str) -> pd.DataFrame:
    """Tải chuỗi dữ liệu vĩ mô / hàng hóa quốc tế."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM ohlcv_global WHERE ticker = ? ORDER BY date ASC;",
        conn, params=[ticker]
    )
    conn.close()
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

# --- Quản lý Cấu hình Người dùng (user_settings) ---

def get_setting(key: str, default_val=None):
    """Đọc cấu hình người dùng từ bảng user_settings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM user_settings WHERE key = ?;", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row[0])
        except:
            return row[0]
    return default_val

def set_setting(key: str, val):
    """Lưu cấu hình người dùng vào bảng user_settings."""
    conn = get_connection()
    cursor = conn.cursor()
    val_str = json.dumps(val) if not isinstance(val, str) else val
    cursor.execute("""
    INSERT OR REPLACE INTO user_settings (key, value, updated_at)
    VALUES (?, ?, CURRENT_TIMESTAMP);
    """, (key, val_str))
    conn.commit()
    conn.close()

# --- Quản lý Đường vẽ Trendline (user_drawings) ---

def get_user_drawings(ticker: str, timeframe: str) -> list:
    """Lấy danh sách các đường trendline đã persist của 1 mã trên khung thời gian cụ thể."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, label, date_1, price_1, date_2, price_2, extend_right, color
    FROM user_drawings
    WHERE ticker = ? AND timeframe = ?
    ORDER BY created_at ASC;
    """, (ticker, timeframe))
    rows = cursor.fetchall()
    conn.close()
    drawings = []
    for r in rows:
        drawings.append({
            "id": r[0], "label": r[1],
            "date_1": r[2], "price_1": r[3],
            "date_2": r[4], "price_2": r[5],
            "extend_right": bool(r[6]), "color": r[7]
        })
    return drawings

def save_user_drawing(ticker: str, timeframe: str, label: str,
                      date_1: str, price_1: float, date_2: str, price_2: float,
                      extend_right: bool = True, color: str = "#FCC934"):
    """Lưu 1 đường trendline mới vào database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO user_drawings
    (ticker, timeframe, label, date_1, price_1, date_2, price_2, extend_right, color)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (ticker, timeframe, label, date_1, price_1, date_2, price_2, 1 if extend_right else 0, color))
    conn.commit()
    conn.close()

def delete_user_drawing(drawing_id: int):
    """Xóa 1 đường trendline khỏi database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_drawings WHERE id = ?;", (drawing_id,))
    conn.commit()
    conn.close()

def update_user_drawing(drawing_id: int, label: str, date_1: str, price_1: float, date_2: str, price_2: float, extend_right: bool = True, color: str = "#FCC934"):
    """Cập nhật tọa độ hoặc thông tin đường trendline đã lưu."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE user_drawings
    SET label = ?, date_1 = ?, price_1 = ?, date_2 = ?, price_2 = ?, extend_right = ?, color = ?
    WHERE id = ?;
    """, (label, str(date_1), float(price_1), str(date_2), float(price_2), 1 if extend_right else 0, color, drawing_id))
    conn.commit()
    conn.close()

# --- Quản lý Nhật ký Lệnh (trade_journal) ---

def get_trade_journal(status_filter: str = None) -> pd.DataFrame:
    """Tải toàn bộ hoặc lọc theo trạng thái nhật ký lệnh."""
    conn = get_connection()
    query = "SELECT * FROM trade_journal"
    params = []
    if status_filter:
        query += " WHERE status = ?"
        params.append(status_filter)
    query += " ORDER BY id DESC;"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def update_trade_exit(trade_id: int, exit_step: int, exit_date: str, exit_price: float, exit_qty: int, notes: str = ""):
    """
    Cập nhật chốt lời từng phần (Scaling-Out 50/50):
    - exit_step = 1: chốt Target 1 (50%), status chuyển sang 'PARTIAL',
      dời stop_loss = entry_price (breakeven) và trailing_stop = entry_price theo AGENTS.md §4.5
    - exit_step = 2: chốt phần còn lại, status chuyển sang 'CLOSED' và tính pnl_pct tổng
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT entry_price, quantity, exit_price_1, exit_qty_1 FROM trade_journal WHERE id = ?;", (trade_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    entry_price, total_qty, ep1, eq1 = row

    if exit_step == 1:
        cursor.execute("""
        UPDATE trade_journal
        SET exit_date_1 = ?, exit_price_1 = ?, exit_qty_1 = ?, status = 'PARTIAL',
            stop_loss = ?, trailing_stop = ?,
            notes = notes || ' | ' || ?
        WHERE id = ?;
        """, (exit_date, exit_price, exit_qty, entry_price, entry_price, notes, trade_id))
    elif exit_step == 2:
        # Tính PnL bình quân gia quyền
        ep1 = ep1 if ep1 is not None else exit_price
        eq1 = eq1 if eq1 is not None else 0
        eq2 = exit_qty
        ep2 = exit_price

        total_proceeds = (eq1 * ep1) + (eq2 * ep2)
        total_cost = total_qty * entry_price
        pnl_pct = ((total_proceeds - total_cost) / total_cost) * 100.0 if total_cost > 0 else 0.0

        cursor.execute("""
        UPDATE trade_journal
        SET exit_date_2 = ?, exit_price_2 = ?, exit_qty_2 = ?, status = 'CLOSED', pnl_pct = ?, notes = notes || ' | ' || ?
        WHERE id = ?;
        """, (exit_date, exit_price, exit_qty, round(pnl_pct, 2), notes, trade_id))

    conn.commit()
    conn.close()
