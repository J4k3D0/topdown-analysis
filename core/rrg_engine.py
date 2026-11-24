"""
core/rrg_engine.py
Mô hình Đồ thị Luân chuyển Tương đối (Relative Rotation Graph - RRG) chuẩn Julius de Kempenaer (JdK):
- Khung thời gian tuần (W-FRI), cửa sổ 12 tuần (12W), độ dài đuôi 8 kỳ (8 weeks tail)
- Điểm chuẩn (Benchmark): VN-Index
- Tính toán 4 góc phần tư: Leading (Dẫn dắt), Weakening (Suy yếu), Lagging (Tụt hậu), Improving (Cải thiện)
- Backtest lịch sử luân chuyển 9 nhóm ngành qua các mốc chu kỳ lớn (2020, 2022, 2026)
"""

import numpy as np
import pandas as pd
from datetime import datetime
from config.settings import RRG_BENCHMARK, RRG_WINDOW_WEEKS, RRG_TAIL_PERIODS
from core.indicators import resample_ohlcv

def compute_rrg_metrics(price_df: pd.DataFrame, benchmark_df: pd.DataFrame, window: int = 12, tail_len: int = 8) -> dict:
    """
    Tính chuỗi RS-Ratio và RS-Momentum cho 1 chuỗi giá cổ phiếu/ngành so với Benchmark:
    - price_df và benchmark_df đã ở khung tuần W-FRI
    """
    if price_df is None or benchmark_df is None or len(price_df) < window + tail_len:
        return None

    # Hợp nhất theo ngày đóng nến tuần
    merged = pd.merge(
        price_df[['date', 'close']].rename(columns={'close': 'close_target'}),
        benchmark_df[['date', 'close']].rename(columns={'close': 'close_bm'}),
        on='date', how='inner'
    ).sort_values('date').reset_index(drop=True)

    if len(merged) < window + tail_len:
        return None

    # 1. Relative Strength (RS)
    merged['rs'] = (merged['close_target'] / merged['close_bm']) * 100.0

    # 2. RS-Ratio (chuẩn hóa Z-score 12 tuần)
    rs_mean = merged['rs'].rolling(window=window).mean()
    rs_std = merged['rs'].rolling(window=window).std().replace(0, np.nan)
    z_rs = (merged['rs'] - rs_mean) / rs_std
    merged['rs_ratio'] = 100.0 + 10.0 * z_rs
    # Làm mượt nhẹ bằng EMA 3 tuần
    merged['rs_ratio'] = merged['rs_ratio'].ewm(span=3, adjust=False).mean()

    # 3. RS-Momentum
    ratio_change = merged['rs_ratio'].diff(1)
    change_mean = ratio_change.rolling(window=window).mean()
    change_std = ratio_change.rolling(window=window).std().replace(0, np.nan)
    z_mom = (ratio_change - change_mean) / change_std
    merged['rs_momentum'] = 100.0 + 10.0 * z_mom
    merged['rs_momentum'] = merged['rs_momentum'].ewm(span=3, adjust=False).mean()

    valid_df = merged.dropna(subset=['rs_ratio', 'rs_momentum']).reset_index(drop=True)
    if len(valid_df) < tail_len:
        return None

    # Lấy tail_len điểm gần nhất cho đuôi RRG
    tail_df = valid_df.tail(tail_len).copy()

    last_row = tail_df.iloc[-1]
    last_ratio = float(last_row['rs_ratio'])
    last_mom = float(last_row['rs_momentum'])

    # Xác định góc phần tư hiện tại
    if last_ratio >= 100.0 and last_mom >= 100.0:
        quadrant = "Leading"
        color = "#00C853"
    elif last_ratio >= 100.0 and last_mom < 100.0:
        quadrant = "Weakening"
        color = "#FFD600"
    elif last_ratio < 100.0 and last_mom < 100.0:
        quadrant = "Lagging"
        color = "#D50000"
    else:
        quadrant = "Improving"
        color = "#2979FF"

    tail_points = []
    for _, r in tail_df.iterrows():
        dt_str = r['date'].strftime('%Y-%m-%d') if hasattr(r['date'], 'strftime') else str(r['date'])[:10]
        tail_points.append({
            "date": dt_str,
            "rs_ratio": round(float(r['rs_ratio']), 2),
            "rs_momentum": round(float(r['rs_momentum']), 2)
        })

    return {
        "rs_ratio": round(last_ratio, 2),
        "rs_momentum": round(last_mom, 2),
        "quadrant": quadrant,
        "color": color,
        "tail": tail_points
    }

def calculate_multi_asset_rrg(asset_dfs: dict, benchmark_df: pd.DataFrame, window: int = 12, tail_len: int = 8) -> dict:
    """Tính toán RRG cho toàn bộ danh mục tài sản hoặc danh mục 9 ngành."""
    # Resample benchmark sang 1W nếu đang ở 1D
    bm_weekly = resample_ohlcv(benchmark_df, "1W") if len(benchmark_df) > 50 else benchmark_df

    rrg_results = {}
    for name, df_asset in asset_dfs.items():
        if df_asset is not None and len(df_asset) > 30:
            asset_weekly = resample_ohlcv(df_asset, "1W") if len(df_asset) > 50 else df_asset
            metrics = compute_rrg_metrics(asset_weekly, bm_weekly, window=window, tail_len=tail_len)
            if metrics:
                rrg_results[name] = metrics

    return rrg_results

# Các mốc sự kiện chu kỳ lớn của VN-Index để backtest luân chuyển ngành
HISTORICAL_CYCLE_DATES = {
    "Đáy COVID (Tháng 03/2020)": "2020-03-31",
    "Đỉnh Lịch Sử (Tháng 04/2022)": "2022-04-08",
    "Đáy Hoảng Loạn (Tháng 11/2022)": "2022-11-16",
    "Đỉnh Sóng 2026 (Tháng 02/2026)": "2026-02-27"
}

def backtest_sector_rotation(sector_daily_dfs: dict, base_date: str) -> pd.DataFrame:
    """
    Backtest hiệu suất Simple Return của 9 ngành sau mốc sự kiện tại các khung:
    +1 Tháng (+21 phiên), +3 Tháng (+63 phiên), +6 Tháng (+126 phiên), +12 Tháng (+252 phiên).
    """
    periods = {
        "+1M": 21,
        "+3M": 63,
        "+6M": 126,
        "+12M": 252
    }

    results = []
    for sector_name, df in sector_daily_dfs.items():
        if df is None or df.empty:
            continue

        df_sorted = df.sort_values('date').reset_index(drop=True)
        # Tìm bar gần nhất với base_date
        df_sorted['dt_str'] = df_sorted['date'].astype(str).str[:10]
        base_match = df_sorted[df_sorted['dt_str'] >= base_date]

        if base_match.empty:
            continue

        base_idx = base_match.index[0]
        p_base = df_sorted.loc[base_idx, 'close']

        row_res = {"Ngành": sector_name}
        for p_label, bars in periods.items():
            tgt_idx = base_idx + bars
            if tgt_idx < len(df_sorted):
                p_tgt = df_sorted.loc[tgt_idx, 'close']
                ret = ((p_tgt - p_base) / p_base) * 100.0
                row_res[p_label] = round(float(ret), 2)
            else:
                row_res[p_label] = np.nan

        results.append(row_res)

    res_df = pd.DataFrame(results)
    return res_df
