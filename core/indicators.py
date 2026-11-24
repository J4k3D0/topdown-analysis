"""
core/indicators.py
Bộ tính toán chỉ báo kỹ thuật chuẩn hóa cho hệ thống Top-Down Quant:
- Resampling chuỗi thời gian W-FRI và ME (tương thích pandas >= 2.2) kèm cờ last_bar_partial
- Đường trung bình động MA/EMA (21, 50, 120, 200) kèm cơ chế Fallback cho khung Tháng (1M)
- RSI(14) Wilder's smoothing và thuật toán phát hiện phân kỳ đỉnh/đáy tự động
- MACD(12, 26, 9)
- Ehlers Fisher Transform(9) và Trigger line
- Dòng tiền & Khối lượng: MFI(14), VolRatio (Volume / SMA9(Vol))
- Chỉ số VNINDEX_EX_VIN (Loại bỏ tác động của 4 mã Vingroup: VIC, VHM, VRE, VPL)
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

def resample_ohlcv(df: pd.DataFrame, timeframe: str = "1W") -> pd.DataFrame:
    """
    Chuyển đổi khung thời gian OHLCV từ 1D sang 1W hoặc 1M:
    - 1W: 'W-FRI' (đóng nến vào Thứ Sáu)
    - 1M: 'ME' (Month End, tương thích pandas >= 2.2)
    Gắn cờ last_bar_partial nếu phiên cuối chưa hoàn tất kỳ.
    """
    if df is None or df.empty:
        return df

    df_work = df.copy()
    if 'date' in df_work.columns:
        df_work['date'] = pd.to_datetime(df_work['date'])
        df_work.set_index('date', inplace=True)
    elif not isinstance(df_work.index, pd.DatetimeIndex):
        df_work.index = pd.to_datetime(df_work.index)

    df_work.sort_index(inplace=True)

    # Chỉ tổng hợp các cột THỰC SỰ tồn tại. Chuỗi chỉ có 'close' (ví dụ RRG ngành)
    # vẫn resample được thay vì ném KeyError. Cột lạ được giữ bằng 'last'.
    full_rules = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    agg_rules = {c: how for c, how in full_rules.items() if c in df_work.columns}
    for c in df_work.columns:
        if c not in agg_rules:
            agg_rules[c] = 'last'

    if timeframe.upper() in ("1W", "W", "WEEK"):
        resampled = df_work.resample("W-FRI", label="right", closed="right").agg(agg_rules)
    elif timeframe.upper() in ("1M", "M", "MONTH"):
        resampled = df_work.resample("ME", label="right", closed="right").agg(agg_rules)
    else:
        return df_work.reset_index()

    required = [c for c in ('open', 'close') if c in resampled.columns]
    if required:
        resampled.dropna(subset=required, inplace=True)

    # Đánh giá cờ partial bar
    if not resampled.empty and not df_work.empty:
        last_daily_date = df_work.index[-1].date()
        last_resampled_date = resampled.index[-1].date()
        is_partial = False
        if timeframe.upper() in ("1W", "W", "WEEK"):
            # Nếu ngày cuối của dữ liệu ngày chưa phải thứ Sáu
            if last_daily_date.weekday() != 4:
                is_partial = True
        elif timeframe.upper() in ("1M", "M", "MONTH"):
            # Nếu chưa hết tháng
            next_day = last_daily_date + pd.Timedelta(days=1)
            if next_day.month == last_daily_date.month:
                is_partial = True
        resampled.attrs["last_bar_partial"] = is_partial

    return resampled.reset_index()

def calculate_mas(df: pd.DataFrame, is_monthly: bool = False) -> pd.DataFrame:
    """
    Tính các đường MA/EMA: 21, 50, 120, 200.
    Nếu is_monthly = True (khung 1M), áp dụng quy tắc Fallback:
    MA_long_1M = MA200 nếu >= 200 nến; MA120 nếu 120-199 nến; EMA200 nếu < 120 nến.
    """
    df_out = df.copy()
    close = df_out['close']

    # EMA
    df_out['ema9'] = close.ewm(span=9, adjust=False).mean()
    df_out['ema21'] = close.ewm(span=21, adjust=False).mean()
    df_out['ema50'] = close.ewm(span=50, adjust=False).mean()
    df_out['ema120'] = close.ewm(span=120, adjust=False).mean()
    df_out['ema200'] = close.ewm(span=200, adjust=False).mean()

    # SMA
    df_out['ma21'] = close.rolling(window=21).mean()
    df_out['ma50'] = close.rolling(window=50).mean()
    df_out['ma120'] = close.rolling(window=120).mean()
    df_out['ma200'] = close.rolling(window=200).mean()

    if is_monthly:
        # Cascade fallback: MA200 -> MA120 -> MA50 -> EMA200
        # Đảm bảo mọi thanh nến tháng đều có ngưỡng tham chiếu dài hạn hợp lệ (0 NaNs)
        cascade = df_out['ma200'].combine_first(df_out['ma120']).combine_first(df_out['ma50']).combine_first(df_out['ema200'])
        df_out['ma_long_1m'] = cascade
        n_bars = len(df_out)
        if n_bars >= 200:
            df_out['ma_long_1m_type'] = 'MA200'
        elif n_bars >= 120:
            df_out['ma_long_1m_type'] = 'MA120'
        elif n_bars >= 50:
            df_out['ma_long_1m_type'] = 'MA50'
        else:
            df_out['ma_long_1m_type'] = 'EMA200'

    return df_out

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Smoothing RSI(14) (alpha = 1/14)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def detect_rsi_divergence(df: pd.DataFrame, order: int = 5) -> dict:
    """
    Phát hiện phân kỳ RSI so với giá:
    - Phân kỳ dương (Bullish Divergence): Đáy giá sau thấp hơn đáy giá trước, nhưng đáy RSI sau cao hơn.
    - Phân kỳ âm (Bearish Divergence): Đỉnh giá sau cao hơn đỉnh giá trước, nhưng đỉnh RSI sau thấp hơn.
    """
    if len(df) < order * 2 + 5 or 'rsi' not in df.columns:
        return {"bullish": [], "bearish": []}

    close = df['close'].values
    rsi = df['rsi'].values
    dates = df['date'].values if 'date' in df.columns else df.index.values

    low_pivots = argrelextrema(close, np.less_equal, order=order)[0]
    high_pivots = argrelextrema(close, np.greater_equal, order=order)[0]

    bullish_divs = []
    if len(low_pivots) >= 2:
        for i in range(len(low_pivots) - 1):
            p1, p2 = low_pivots[i], low_pivots[i + 1]
            if p2 - p1 < 60:  # Khoảng cách tối đa 60 bars
                if close[p2] < close[p1] and rsi[p2] > rsi[p1]:
                    bullish_divs.append({
                        "t1": p1, "t2": p2,
                        "date_1": str(dates[p1])[:10], "date_2": str(dates[p2])[:10],
                        "p1": close[p1], "p2": close[p2],
                        "rsi1": rsi[p1], "rsi2": rsi[p2]
                    })

    bearish_divs = []
    if len(high_pivots) >= 2:
        for i in range(len(high_pivots) - 1):
            p1, p2 = high_pivots[i], high_pivots[i + 1]
            if p2 - p1 < 60:
                if close[p2] > close[p1] and rsi[p2] < rsi[p1]:
                    bearish_divs.append({
                        "t1": p1, "t2": p2,
                        "date_1": str(dates[p1])[:10], "date_2": str(dates[p2])[:10],
                        "p1": close[p1], "p2": close[p2],
                        "rsi1": rsi[p1], "rsi2": rsi[p2]
                    })

    return {"bullish": bullish_divs, "bearish": bearish_divs}

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD(12, 26, 9) và Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        'macd': macd_line,
        'macd_signal': signal_line,
        'macd_hist': histogram
    })

def calculate_fisher_transform(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    """
    Ehlers Fisher Transform(9):
    x_t = (High + Low) / 2
    v_t = clip(0.66 * ((x - min9)/(max9 - min9) - 0.5) + 0.67*v_{t-1}, -0.999, 0.999)
    F_t = 0.5 * ln((1 + v_t)/(1 - v_t)) + 0.5 * F_{t-1}
    Trigger_t = F_{t-1}
    """
    df_out = df.copy()
    high = df_out['high']
    low = df_out['low']
    x = (high + low) / 2.0

    min_x = x.rolling(window=period, min_periods=1).min()
    max_x = x.rolling(window=period, min_periods=1).max()
    denom = (max_x - min_x).replace(0, 0.0001)

    n = len(df_out)
    v = np.zeros(n, dtype=np.float64)
    f = np.zeros(n, dtype=np.float64)

    x_vals = x.values
    min_x_vals = min_x.values
    denom_vals = denom.values

    for i in range(1, n):
        scaled = 0.66 * ((x_vals[i] - min_x_vals[i]) / denom_vals[i] - 0.5) + 0.67 * v[i - 1]
        v[i] = np.clip(scaled, -0.999, 0.999)
        val = 0.5 * np.log((1.0 + v[i]) / (1.0 - v[i])) + 0.5 * f[i - 1]
        f[i] = val

    df_out['fisher'] = f
    df_out['fisher_signal'] = pd.Series(f).shift(1).fillna(0).values
    return df_out

def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index (MFI 14)."""
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    money_flow = typical_price * df['volume']

    delta = typical_price.diff()
    pos_flow = np.where(delta > 0, money_flow, 0.0)
    neg_flow = np.where(delta < 0, money_flow, 0.0)

    pos_mf = pd.Series(pos_flow, index=df.index).rolling(window=period).sum()
    neg_mf = pd.Series(neg_flow, index=df.index).rolling(window=period).sum()

    mfr = pos_mf / neg_mf.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    return mfi.fillna(50)

def calculate_all_indicators(df: pd.DataFrame, is_monthly: bool = False) -> pd.DataFrame:
    """Tính toán toàn bộ bộ chỉ báo kỹ thuật cho chuỗi OHLCV."""
    if df is None or df.empty or len(df) < 5:
        return df

    res = calculate_mas(df, is_monthly=is_monthly)
    res['rsi'] = calculate_rsi(res['close'])

    macd_df = calculate_macd(res['close'])
    res['macd'] = macd_df['macd']
    res['macd_signal'] = macd_df['macd_signal']
    res['macd_hist'] = macd_df['macd_hist']

    res = calculate_fisher_transform(res, period=9)
    res['mfi'] = calculate_mfi(res, period=14)

    vol_sma9 = res['volume'].rolling(window=9).mean()
    res['vol_ratio'] = res['volume'] / vol_sma9.replace(0, np.nan)
    res['vol_ratio'] = res['vol_ratio'].fillna(1.0)

    return res

def compute_ex_vingroup_index(vnindex_df: pd.DataFrame, vin_dfs: dict, weights_dict: dict = None) -> pd.DataFrame:
    """
    Tái tạo chỉ số VNINDEX_EX_VIN loại trừ 4 mã Vingroup (VIC, VHM, VRE, VPL):
    R_{ex-vin, t} = (R_{VN, t} - sum(w_i * R_{i, t})) / (1 - sum(w_i))
    P_{ex-vin, t} = P_0 * prod(1 + R_{ex-vin, tau})
    """
    if vnindex_df is None or vnindex_df.empty:
        return vnindex_df

    df_vn = vnindex_df.copy().sort_values('date').reset_index(drop=True)
    df_vn['return_vn'] = df_vn['close'].pct_change().fillna(0)

    # Trọng số mặc định tham chiếu nếu không truyền weights_dict: VIC (~4.5%), VHM (~4.2%), VRE (~1.5%), VPL (~1.8%)
    default_w = {'VIC': 0.045, 'VHM': 0.042, 'VRE': 0.015, 'VPL': 0.018}
    w_map = weights_dict if weights_dict else default_w

    sum_vin_weighted_ret = np.zeros(len(df_vn))
    sum_w = 0.0

    for ticker, df_vin in vin_dfs.items():
        if df_vin is not None and not df_vin.empty and ticker in w_map:
            w_i = w_map[ticker]
            sum_w += w_i
            merged = pd.merge(df_vn[['date']], df_vin[['date', 'close']], on='date', how='left')
            ret_vin = merged['close'].pct_change().fillna(0).values
            sum_vin_weighted_ret += w_i * ret_vin

    w_denom = max(1.0 - sum_w, 0.01)
    ret_ex_vin = (df_vn['return_vn'].values - sum_vin_weighted_ret) / w_denom

    # Khởi tạo chuỗi giá tích lũy giữ nguyên giá khởi đầu của VNINDEX
    p0 = df_vn['close'].iloc[0]
    cum_ret = np.cumprod(1.0 + ret_ex_vin)
    df_vn['close_ex_vin'] = p0 * cum_ret

    # Điều chỉnh tương ứng open, high, low
    ratio = df_vn['close_ex_vin'] / df_vn['close'].replace(0, 1)
    df_vn['open_ex_vin'] = df_vn['open'] * ratio
    df_vn['high_ex_vin'] = df_vn['high'] * ratio
    df_vn['low_ex_vin'] = df_vn['low'] * ratio

    return df_vn


def compute_market_breadth(tickers: list, sample_size: int = 60) -> dict:
    """
    Độ rộng thị trường (Market Breadth) từ Local DB:
    - % cổ phiếu đóng cửa trên MA50 / MA200
    - Độ dốc Advance/Decline: (số mã tăng - số mã giảm) / số mã đánh giá
    Dùng chung cho Dashboard (Tầng 4) và trang Phái sinh để tránh lệch số liệu.
    """
    from core.db_manager import load_ohlcv

    above50 = above200 = advances = declines = evaluated = 0
    for t in list(tickers)[:sample_size]:
        try:
            df = load_ohlcv(t)
            if df is None or len(df) < 50:
                continue
            df_mas = calculate_mas(df)
            last = df_mas.iloc[-1]
            c = float(last['close'])
            ma50 = last.get('ma50', c)
            ma200 = last.get('ma200', c)
            if pd.notna(ma50) and c > float(ma50):
                above50 += 1
            if pd.notna(ma200) and c > float(ma200):
                above200 += 1
            if len(df_mas) >= 2:
                prev_c = float(df_mas.iloc[-2]['close'])
                if c > prev_c:
                    advances += 1
                elif c < prev_c:
                    declines += 1
            evaluated += 1
        except Exception:
            continue

    if evaluated == 0:
        return {"pct_above_ma50": None, "pct_above_ma200": None, "ad_slope": None, "evaluated": 0}

    return {
        "pct_above_ma50": (above50 / evaluated) * 100.0,
        "pct_above_ma200": (above200 / evaluated) * 100.0,
        "ad_slope": (advances - declines) / evaluated,
        "evaluated": evaluated,
    }
