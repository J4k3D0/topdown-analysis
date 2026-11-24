"""
core/gann_engine.py
Bộ công cụ W.D. Gann chuyên sâu trên không gian Logarit cơ số 10:
- Gann Time Cycles (+30, +45, +60, +90, +144, +180, +360 ngày lịch và 21, 34, 55, 89, 144, 233 nến)
- Gann Square of 9: Khóa chuẩn đơn vị kVND, công thức P_target = (sqrt(P0) +/- (theta/180) * k)^2
- Gann Fan & Gann Box trên thang Log
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def calculate_gann_time_cycles(base_date, n_bars_ahead: int = 250):
    """
    Tính các mốc thời gian Gann Time Cycles và Fibonacci Time từ ngày neo (base_date):
    - Ngày lịch: +30, +45, +60, +90, +144, +180, +270, +360 ngày
    - Phiên giao dịch (trading bars): 21, 34, 55, 89, 144, 233 bars
    """
    if isinstance(base_date, str):
        base_dt = datetime.strptime(base_date[:10], "%Y-%m-%d").date()
    elif isinstance(base_date, pd.Timestamp):
        base_dt = base_date.date()
    else:
        base_dt = base_date

    calendar_days = [30, 45, 60, 90, 144, 180, 270, 360]
    trading_bars = [21, 34, 55, 89, 144, 233]

    cycle_dates = []
    for cd in calendar_days:
        tgt_dt = base_dt + timedelta(days=cd)
        cycle_dates.append({
            "type": "calendar_day",
            "cycle_val": cd,
            "target_date": tgt_dt.strftime("%Y-%m-%d"),
            "label": f"+{cd}d"
        })

    return {
        "base_date": base_dt.strftime("%Y-%m-%d"),
        "calendar_cycles": cycle_dates,
        "trading_bars": trading_bars
    }

def calculate_gann_square_of_9(p0: float, k: float = 1.0, is_index: bool = False):
    """
    Gann Square of 9:
    P_target(theta, k) = (sqrt(P0) +/- (theta / 180) * k)^2
    Khóa 100% đơn vị kVND cho cổ phiếu (vd: KDH = 14.0, NLG = 21.2, FPT = 123.3).
    Hệ số scale theo độ lớn giá để bước sóng góc không bị triệt tiêu (giá nhỏ)
    hoặc phình quá mức (chỉ số):
      - Chỉ số / giá > 500  -> scale = 0.1
      - Cổ phiếu < 10 kVND  -> scale = 10.0  (tăng độ phân giải góc)
      - Còn lại             -> scale = 1.0
    """
    if p0 <= 0:
        return {}

    if is_index or p0 > 500:
        scale = 0.1
    elif p0 < 10:
        scale = 10.0
    else:
        scale = 1.0
    p_scaled = p0 * scale
    sqrt_p = np.sqrt(p_scaled)

    angles = [45, 90, 135, 180, 225, 270, 315, 360]
    results_up = []
    results_down = []

    for deg in angles:
        step = (deg / 180.0) * k

        # Hướng tăng (Resistance Targets)
        p_up = (sqrt_p + step) ** 2 / scale
        pct_up = ((p_up - p0) / p0) * 100.0
        results_up.append({
            "angle": deg,
            "price": round(float(p_up), 2),
            "pct_change": round(float(pct_up), 2),
            "label": f"+{deg}°"
        })

        # Hướng giảm (Support Targets)
        val_down = sqrt_p - step
        if val_down > 0:
            p_down = (val_down ** 2) / scale
            pct_down = ((p_down - p0) / p0) * 100.0
            results_down.append({
                "angle": deg,
                "price": round(float(p_down), 2),
                "pct_change": round(float(pct_down), 2),
                "label": f"-{deg}°"
            })
        else:
            results_down.append({
                "angle": deg,
                "price": 0.0,
                "pct_change": -100.0,
                "label": f"-{deg}°"
            })

    return {
        "p0": p0,
        "k": k,
        "scale": scale,
        "resistances": results_up,
        "supports": results_down
    }

def calculate_gann_fan_log(t0: int, p0: float, t1: int, p1: float, max_t: int):
    """
    Vẽ các tia Gann Fan trên không gian Logarit cơ số 10:
    Hệ số góc cơ sở (tia 1x1): m_base = (log10(p1) - log10(p0)) / (t1 - t0)
    Các tia tỷ lệ:
    1x8, 1x4, 1x3, 1x2, 1x1, 2x1, 3x1, 4x1, 8x1
    """
    y0 = np.log10(p0)
    y1 = np.log10(p1)
    denom = t1 - t0
    if denom == 0:
        return {}

    m_1x1 = (y1 - y0) / denom

    ratios = {
        "1x8": m_1x1 / 8.0,
        "1x4": m_1x1 / 4.0,
        "1x3": m_1x1 / 3.0,
        "1x2": m_1x1 / 2.0,
        "1x1": m_1x1,
        "2x1": m_1x1 * 2.0,
        "3x1": m_1x1 * 3.0,
        "4x1": m_1x1 * 4.0,
        "8x1": m_1x1 * 8.0
    }

    t_eval = np.arange(t0, max_t)
    fan_lines = {}
    for r_name, slope in ratios.items():
        y_line = y0 + slope * (t_eval - t0)
        p_line = 10.0 ** y_line
        fan_lines[r_name] = p_line

    return {
        "t_eval": t_eval,
        "t0": t0, "p0": p0,
        "t1": t1, "p1": p1,
        "lines": fan_lines
    }

def calculate_gann_box_log(t0: int, p0: float, t1: int, p1: float):
    """
    Lưới Gann Box chia 25%, 50%, 75% trên không gian log10(Price) và thời gian:
    y = log10(P)
    """
    y_min = min(np.log10(p0), np.log10(p1))
    y_max = max(np.log10(p0), np.log10(p1))
    dy = y_max - y_min

    levels_y = [
        ("0%", y_min, 10.0 ** y_min),
        ("25%", y_min + 0.25 * dy, 10.0 ** (y_min + 0.25 * dy)),
        ("50%", y_min + 0.50 * dy, 10.0 ** (y_min + 0.50 * dy)),
        ("75%", y_min + 0.75 * dy, 10.0 ** (y_min + 0.75 * dy)),
        ("100%", y_max, 10.0 ** y_max)
    ]

    t_min = min(t0, t1)
    t_max = max(t0, t1)
    dt = t_max - t_min

    time_levels = [
        ("0%", t_min),
        ("25%", int(t_min + 0.25 * dt)),
        ("50%", int(t_min + 0.50 * dt)),
        ("75%", int(t_min + 0.75 * dt)),
        ("100%", t_max)
    ]

    return {
        "price_levels": levels_y,
        "time_levels": time_levels
    }
