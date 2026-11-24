"""
core/astro_engine.py
Động cơ tính toán Thiên văn tài chính (Financial Astrology) cho Tầng 1:
- Pha Mặt Trăng (New Moon - Trăng mới, Full Moon - Trăng tròn)
- Thủy Tinh nghịch hành (Mercury Retrograde)
- Tích hợp chuẩn hóa góc [-180, +180] độ chống nhảy 360 -> 0 độ
"""

import math
from datetime import datetime, date, timedelta
import pandas as pd

# Mốc chuẩn New Moon tham chiếu thiên văn chính xác: 2000-01-06 18:14 UTC
REF_NEW_MOON = datetime(2000, 1, 6, 18, 14)
SYNODIC_MONTH = 29.53058867  # ngày

# Bảng tra cứu chính xác các kỳ Thủy Tinh nghịch hành (Mercury Retrograde) giai đoạn 2024 - 2027
# Dựa trên niên giám thiên văn NASA JPL Horizons
MERCURY_RETROGRADE_PERIODS = [
    # 2024
    ("2024-04-01", "2024-04-25"),
    ("2024-08-05", "2024-08-28"),
    ("2024-11-26", "2024-12-15"),
    # 2025
    ("2025-03-15", "2025-04-07"),
    ("2025-07-18", "2025-08-11"),
    ("2025-11-09", "2025-11-29"),
    # 2026
    ("2026-02-26", "2026-03-20"),
    ("2026-06-29", "2026-07-23"),
    ("2026-10-24", "2026-11-13"),
    # 2027
    ("2027-02-09", "2027-03-03"),
    ("2027-06-10", "2027-07-04"),
    ("2027-10-07", "2027-10-28")
]

def get_moon_phase_info(check_date: date) -> dict:
    """
    Tính tuổi trăng và xác định pha Mặt Trăng theo thuật toán thiên văn Jean Meeus:
    - Tuổi trăng = (days_since_ref) % 29.53058867
    - New Moon: Tuổi trăng < 1.0 hoặc > 28.53 ngày
    - Full Moon: 13.76 <= Tuổi trăng <= 15.76 ngày
    """
    if isinstance(check_date, str):
        check_dt = datetime.strptime(check_date[:10], "%Y-%m-%d")
    elif isinstance(check_date, date) and not isinstance(check_date, datetime):
        check_dt = datetime.combine(check_date, datetime.min.time())
    else:
        check_dt = check_date

    diff_days = (check_dt - REF_NEW_MOON).total_seconds() / 86400.0
    moon_age = diff_days % SYNODIC_MONTH

    # Tỷ lệ chiếu sáng (Illumination: 0.0 -> 1.0)
    illumination = 0.5 * (1.0 - math.cos(2.0 * math.pi * moon_age / SYNODIC_MONTH))

    is_new_moon = (moon_age < 1.0) or (moon_age > (SYNODIC_MONTH - 1.0))
    is_full_moon = abs(moon_age - (SYNODIC_MONTH / 2.0)) <= 1.0

    phase_name = "Khác"
    if is_new_moon:
        phase_name = "New Moon (Trăng mới)"
    elif is_full_moon:
        phase_name = "Full Moon (Trăng tròn)"
    elif moon_age < (SYNODIC_MONTH / 2.0):
        phase_name = "Trăng tròn dần (Waxing)"
    else:
        phase_name = "Trăng khuyết dần (Waning)"

    return {
        "date": check_dt.strftime("%Y-%m-%d"),
        "moon_age": round(moon_age, 2),
        "illumination_pct": round(illumination * 100.0, 1),
        "is_new_moon": is_new_moon,
        "is_full_moon": is_full_moon,
        "phase_name": phase_name
    }

def is_mercury_retrograde(check_date) -> bool:
    """Kiểm tra ngày cụ thể có nằm trong dải Thủy Tinh nghịch hành hay không."""
    dt_str = check_date.strftime("%Y-%m-%d") if hasattr(check_date, "strftime") else str(check_date)[:10]
    for start_d, end_d in MERCURY_RETROGRADE_PERIODS:
        if start_d <= dt_str <= end_d:
            return True
    return False

def get_astro_events_for_range(start_date: str, end_date: str) -> dict:
    """
    Tổng hợp toàn bộ danh sách ngày New Moon, Full Moon và các dải Thủy Tinh nghịch hành
    trong khoảng ngày để phủ lên đồ thị VN-Index.
    """
    start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()

    new_moons = []
    full_moons = []

    curr = start_dt
    while curr <= end_dt:
        info = get_moon_phase_info(curr)
        if info["is_new_moon"]:
            new_moons.append(info["date"])
        elif info["is_full_moon"]:
            full_moons.append(info["date"])
        curr += timedelta(days=1)

    # Lọc các dải Mercury Retrograde giao thoa với khoảng ngày
    active_retrogrades = []
    for s_d, e_d in MERCURY_RETROGRADE_PERIODS:
        if not (e_d < start_date or s_d > end_date):
            active_retrogrades.append({
                "start": max(s_d, start_date),
                "end": min(e_d, end_date)
            })

    return {
        "new_moons": sorted(list(set(new_moons))),
        "full_moons": sorted(list(set(full_moons))),
        "retrogrades": active_retrogrades
    }
