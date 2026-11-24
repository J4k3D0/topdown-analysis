"""
core/geometry_log.py
Thuật toán hình học kỹ thuật thuần toán học trên không gian Logarit cơ số 10:
- Auto-Pitchfork 3 điểm (Bearish & Bullish) với bộ lọc Swing Window (order = N)
- Tính trung điểm bằng trung bình nhân trên trục Log
- Tùy chọn Warning Lines (+/-50%, +/-100%)
- Auto-Trendline tự động nhận diện hỗ trợ / kháng cự chính không bị nến xuyên thủng quá 2 lần
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

def get_pivots_log(df: pd.DataFrame, order: int = 5):
    """
    Xác định các đỉnh (Swing High) và đáy (Swing Low) trên không gian log10(Price).
    Khử trùng lặp các nến đỉnh/đáy phẳng liên tiếp (giữ nến có giá trị cực trị lớn nhất).
    """
    if len(df) < order * 2 + 3:
        return np.array([]), np.array([])

    high_log = np.log10(df['high'].values)
    low_log = np.log10(df['low'].values)

    raw_highs = argrelextrema(high_log, np.greater_equal, order=order)[0]
    raw_lows = argrelextrema(low_log, np.less_equal, order=order)[0]

    # Khử trùng lặp đỉnh liên tiếp không có đáy xen giữa
    cleaned_highs = []
    for h in raw_highs:
        if not cleaned_highs:
            cleaned_highs.append(h)
        else:
            prev = cleaned_highs[-1]
            if h - prev <= 1:
                if high_log[h] > high_log[prev]:
                    cleaned_highs[-1] = h
            else:
                cleaned_highs.append(h)

    cleaned_lows = []
    for l in raw_lows:
        if not cleaned_lows:
            cleaned_lows.append(l)
        else:
            prev = cleaned_lows[-1]
            if l - prev <= 1:
                if low_log[l] < low_log[prev]:
                    cleaned_lows[-1] = l
            else:
                cleaned_lows.append(l)

    return np.array(cleaned_highs), np.array(cleaned_lows)

def compute_bearish_pitchfork(df: pd.DataFrame, order: int = 5, extend_bars: int = 30):
    """
    Tính Bearish (Corrective) Pitchfork:
    - Duyệt ngược tìm P1 là đỉnh gần hiện tại nhất có bộ ba hợp lệ (P1 đỉnh, P2 đáy sau P1, P3 đỉnh sau P2 với P3 < P1).
    - P2: đáy thấp nhất bên phải P1.
    - P3: đỉnh cao nhất bên phải P2 (P3 < P1).
    """
    n = len(df)
    highs, lows = get_pivots_log(df, order=order)
    if len(highs) < 2 or len(lows) < 1:
        return None

    high_prices = df['high'].values
    low_prices = df['low'].values

    # Duyệt ngược từ đỉnh gần nhất
    selected = None
    for h_idx in reversed(highs):
        t1 = h_idx
        p1 = high_prices[t1]

        # Tìm các đáy sau t1
        lows_after = lows[lows > t1]
        if len(lows_after) == 0:
            continue

        # P2 là đáy thấp nhất sau t1
        t2 = lows_after[np.argmin(low_prices[lows_after])]
        p2 = low_prices[t2]

        # Tìm các đỉnh sau t2 có P3 < P1
        highs_after = highs[(highs > t2) & (high_prices[highs] < p1)]
        if len(highs_after) == 0:
            continue

        # P3 là đỉnh cao nhất sau t2
        t3 = highs_after[np.argmax(high_prices[highs_after])]
        p3 = high_prices[t3]

        # Kiểm tra độ dốc giảm bắt buộc: m < 0 tương đương yM < y1 (vì tM = (t2 + t3)/2 > t1)
        y1 = np.log10(p1)
        y2 = np.log10(p2)
        y3 = np.log10(p3)
        yM = (y2 + y3) / 2.0
        if yM >= y1:
            continue

        selected = (t1, p1, t2, p2, t3, p3)
        break

    if not selected:
        return None

    t1, p1, t2, p2, t3, p3 = selected
    return _build_pitchfork_lines(t1, p1, t2, p2, t3, p3, n + extend_bars, mode="bearish")

def compute_bullish_pitchfork(df: pd.DataFrame, order: int = 5, extend_bars: int = 30):
    """
    Tính Bullish Pitchfork (Đối xứng):
    - Duyệt ngược tìm P1 là đáy gần hiện tại nhất có bộ ba hợp lệ (P1 đáy, P2 đỉnh sau P1, P3 đáy sau P2 với P3 > P1).
    - P2: đỉnh cao nhất bên phải P1.
    - P3: đáy thấp nhất bên phải P2 (P3 > P1).
    """
    n = len(df)
    highs, lows = get_pivots_log(df, order=order)
    if len(lows) < 2 or len(highs) < 1:
        return None

    high_prices = df['high'].values
    low_prices = df['low'].values

    selected = None
    for l_idx in reversed(lows):
        t1 = l_idx
        p1 = low_prices[t1]

        highs_after = highs[highs > t1]
        if len(highs_after) == 0:
            continue

        t2 = highs_after[np.argmax(high_prices[highs_after])]
        p2 = high_prices[t2]

        lows_after = lows[(lows > t2) & (low_prices[lows] > p1)]
        if len(lows_after) == 0:
            continue

        t3 = lows_after[np.argmin(low_prices[lows_after])]
        p3 = low_prices[t3]

        # Kiểm tra độ dốc tăng bắt buộc: m > 0 tương đương yM > y1 (vì tM = (t2 + t3)/2 > t1)
        y1 = np.log10(p1)
        y2 = np.log10(p2)
        y3 = np.log10(p3)
        yM = (y2 + y3) / 2.0
        if yM <= y1:
            continue

        selected = (t1, p1, t2, p2, t3, p3)
        break

    if not selected:
        return None

    t1, p1, t2, p2, t3, p3 = selected
    return _build_pitchfork_lines(t1, p1, t2, p2, t3, p3, n + extend_bars, mode="bullish")

def _build_pitchfork_lines(t1, p1, t2, p2, t3, p3, max_t, mode="bearish"):
    """Phương trình đường trung tâm và 2 đường song song trên trục log10."""
    y1 = np.log10(p1)
    y2 = np.log10(p2)
    y3 = np.log10(p3)

    tM = (t2 + t3) / 2.0
    yM = (y2 + y3) / 2.0

    denom = tM - t1
    if denom <= 0:
        return None
    m = (yM - y1) / denom

    # Khóa hình học độ dốc: Bearish Pitchfork phải có m < 0, Bullish Pitchfork phải có m > 0
    if mode == "bearish" and m >= 0:
        return None
    if mode == "bullish" and m <= 0:
        return None

    delta_y = abs(y2 - yM)

    t_eval = np.arange(t1, max_t)

    # Median Line
    y_ml = y1 + m * (t_eval - t1)
    p_ml = 10.0 ** y_ml

    # Line 2 (qua P2)
    y_l2 = y2 + m * (t_eval - t2)
    p_l2 = 10.0 ** y_l2

    # Line 3 (qua P3)
    y_l3 = y3 + m * (t_eval - t3)
    p_l3 = 10.0 ** y_l3

    # Warning lines (+100%, -100%)
    p_wl_upper = 10.0 ** (np.maximum(y_l2, y_l3) + delta_y)
    p_wl_lower = 10.0 ** (np.minimum(y_l2, y_l3) - delta_y)

    return {
        "mode": mode,
        "m": float(m),
        "t_eval": t_eval,
        "p_ml": p_ml,
        "p_l2": p_l2,
        "p_l3": p_l3,
        "p_wl_upper": p_wl_upper,
        "p_wl_lower": p_wl_lower,
        "pivots": {
            "P1": (int(t1), float(p1)),
            "P2": (int(t2), float(p2)),
            "P3": (int(t3), float(p3))
        }
    }

def compute_auto_trendlines(df: pd.DataFrame, order: int = 5):
    """
    Tự động xác định các đường trendline kháng cự giảm và hỗ trợ tăng trên thang log:
    - Nối các cặp pivot liên tiếp.
    - Loại bỏ đường bị thân nến (close) xuyên thủng quá 2 lần.
    - Kéo dài đến bar cuối cùng.
    """
    n = len(df)
    if n < order * 2 + 3:
        return []

    highs, lows = get_pivots_log(df, order=order)
    close_log = np.log10(df['close'].values)
    high_log = np.log10(df['high'].values)
    low_log = np.log10(df['low'].values)

    trendlines = []

    # Kháng cự giảm (nối các đỉnh)
    if len(highs) >= 2:
        for i in range(len(highs) - 1, 0, -1):
            t2 = highs[i]
            t1 = highs[i - 1]
            if high_log[t2] < high_log[t1] and (t2 - t1) >= 5:
                # Tính đường thẳng
                slope = (high_log[t2] - high_log[t1]) / (t2 - t1)
                t_eval = np.arange(t1, n)
                line_log = high_log[t1] + slope * (t_eval - t1)

                # Kiểm tra số lần bị thân nến xuyên thủng
                penetrations = np.sum(close_log[t1:n] > line_log)
                if penetrations <= 2:
                    trendlines.append({
                        "type": "resistance",
                        "t1": int(t1), "price1": float(10 ** high_log[t1]),
                        "t2": int(t2), "price2": float(10 ** high_log[t2]),
                        "t_eval": t_eval,
                        "price_eval": 10.0 ** line_log,
                        "color": "#FF5252"
                    })
                    if len([tl for tl in trendlines if tl['type'] == 'resistance']) >= 2:
                        break

    # Hỗ trợ tăng (nối các đáy)
    if len(lows) >= 2:
        for i in range(len(lows) - 1, 0, -1):
            t2 = lows[i]
            t1 = lows[i - 1]
            if low_log[t2] > low_log[t1] and (t2 - t1) >= 5:
                slope = (low_log[t2] - low_log[t1]) / (t2 - t1)
                t_eval = np.arange(t1, n)
                line_log = low_log[t1] + slope * (t_eval - t1)

                penetrations = np.sum(close_log[t1:n] < line_log)
                if penetrations <= 2:
                    trendlines.append({
                        "type": "support",
                        "t1": int(t1), "price1": float(10 ** low_log[t1]),
                        "t2": int(t2), "price2": float(10 ** low_log[t2]),
                        "t_eval": t_eval,
                        "price_eval": 10.0 ** line_log,
                        "color": "#4CAF50"
                    })
                    if len([tl for tl in trendlines if tl['type'] == 'support']) >= 2:
                        break

    return trendlines
