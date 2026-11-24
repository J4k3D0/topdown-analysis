"""
config/vn_holidays.py
Xác định lịch nghỉ lễ giao dịch của thị trường chứng khoán Việt Nam (HOSE/HNX)
và tính toán ngày giao dịch kỳ vọng gần nhất (VNIndexCalendarGuard).
"""

import os
import json
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
import pytz

try:
    import holidays
except ImportError:
    holidays = None

OVERRIDE_FILE = os.path.join(os.path.dirname(__file__), "vn_holidays_override.json")

# Cache theo năm: tránh khởi tạo lại đối tượng holidays cho từng nến khi quét 350.000 dòng.
_HOLIDAY_CACHE = {}
_OVERRIDE_CACHE = {"mtime": None, "dates": set()}


def _load_override_dates() -> set:
    """Đọc file override nghỉ bù của HOSE (cache theo mtime)."""
    if not os.path.exists(OVERRIDE_FILE):
        return set()
    try:
        mtime = os.path.getmtime(OVERRIDE_FILE)
    except OSError:
        return set()
    if _OVERRIDE_CACHE["mtime"] == mtime:
        return _OVERRIDE_CACHE["dates"]

    dates = set()
    try:
        with open(OVERRIDE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for _yr, h_list in data.items():
            for item in h_list:
                dates.add(datetime.strptime(item["date"], "%Y-%m-%d").date())
    except Exception:
        dates = set()
    _OVERRIDE_CACHE["mtime"] = mtime
    _OVERRIDE_CACHE["dates"] = dates
    return dates


def _year_holidays(year: int) -> set:
    """Tập ngày lễ của 1 năm (cache)."""
    if year in _HOLIDAY_CACHE:
        return _HOLIDAY_CACHE[year]
    result = set()
    if holidays:
        try:
            result.update(holidays.country_holidays("VN", years=[year]).keys())
        except Exception:
            pass
    _HOLIDAY_CACHE[year] = result
    return result


def get_vietnam_holidays(years=None) -> set:
    """
    Trả về tập hợp các đối tượng date là ngày nghỉ lễ tại Việt Nam,
    kết hợp giữa thư viện holidays và file override riêng của HOSE.
    """
    if years is None:
        current_year = datetime.now().year
        years = [current_year - 1, current_year, current_year + 1]
    elif isinstance(years, int):
        years = [years]

    holiday_dates = set()
    for y in years:
        holiday_dates |= _year_holidays(int(y))
    holiday_dates |= _load_override_dates()
    return holiday_dates


def is_trading_day(check_date: date) -> bool:
    """Kiểm tra một ngày có phải ngày giao dịch (không phải T7, CN và không phải ngày lễ)."""
    if check_date.weekday() in (5, 6):  # 5 = Thứ 7, 6 = Chủ Nhật
        return False
    return check_date not in _year_holidays(check_date.year) and check_date not in _load_override_dates()


def trading_day_mask(dates) -> np.ndarray:
    """
    Vector hóa: trả về mảng bool cho biết từng ngày có phải ngày giao dịch hay không.
    Nhanh hơn is_trading_day() hàng trăm lần khi quét toàn bộ chuỗi lịch sử.
    """
    idx = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    mask = np.asarray(idx.dayofweek < 5)
    if len(idx) == 0:
        return mask

    years = sorted(set(idx.year.tolist()))
    hols = get_vietnam_holidays(years)
    if hols:
        hol_arr = np.array(sorted(np.datetime64(h, "D") for h in hols), dtype="datetime64[D]")
        mask &= ~np.isin(idx.values.astype("datetime64[D]"), hol_arr)
    return mask

def get_expected_last_trading_day(now_dt: datetime = None) -> date:
    """
    Xác định ngày giao dịch gần nhất kỳ vọng của VN-Index theo giờ Việt Nam (UTC+7):
    - Nếu hôm nay là Thứ 7 hoặc Chủ Nhật -> lùi về ngày giao dịch trước đó.
    - Nếu hôm nay là ngày trong tuần:
      + Nếu trước 15:05 chiều (chưa đóng phiên ATC) -> lùi về ngày giao dịch liền trước.
      + Nếu sau 15:05 chiều -> chính là hôm nay (nếu hôm nay là ngày giao dịch hợp lệ).
    """
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    if now_dt is None:
        now_dt = datetime.now(vn_tz)
    elif now_dt.tzinfo is None:
        now_dt = vn_tz.localize(now_dt)

    current_date = now_dt.date()
    current_time = now_dt.time()

    # Mốc đóng cửa thị trường hoàn tất ATC
    market_close_time = datetime.strptime("15:05", "%H:%M").time()

    candidate = current_date
    if current_time < market_close_time:
        # Nếu chưa qua 15:05, phiên hôm nay chưa chốt -> lùi 1 ngày
        candidate = candidate - timedelta(days=1)

    # Lùi tiếp nếu candidate rơi vào T7, CN hoặc ngày lễ
    while not is_trading_day(candidate):
        candidate = candidate - timedelta(days=1)

    return candidate
