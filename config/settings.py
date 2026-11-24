"""
config/settings.py
Cấu hình tham số mặc định của hệ thống Top-Down Quant:
- Thang đo 100% Log Scale
- Đơn vị giá cổ phiếu: kVND (nghìn đồng)
- Ngưỡng tính toán chỉ báo kỹ thuật & Auto-Pitchfork
- Trọng số mặc định 5 tầng Top-Down (10% - 20% - 20% - 10% - 40%)
- Tham số Black-Scholes cho Chứng quyền
- Luật biên độ giá theo sàn (HOSE ±7%, HNX ±10%, UPCoM ±15%) phục vụ kiểm tra toàn vẹn dữ liệu
- Cửa sổ dữ liệu chuẩn (canonical) và giới hạn tốc độ gọi nguồn dữ liệu miễn phí
"""

import os

# Đường dẫn thư mục gốc
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Đường dẫn lưu trữ dữ liệu
DATA_DIR = os.path.join(ROOT_DIR, "data")
# Cho phép bộ kiểm thử trỏ toàn bộ artefact ghi ra ngoài dữ liệu sản xuất.
# Nếu chỉ đổi DB mà vẫn dùng reports/logs mặc định, test vẫn để lại rác trong
# thư mục data của người dùng.
DB_PATH = os.environ.get("QUANT_DB_PATH") or os.path.join(DATA_DIR, "quant_local.db")
REPORTS_DIR = os.environ.get("QUANT_REPORTS_DIR") or os.path.join(DATA_DIR, "reports")
LOGS_DIR = os.environ.get("QUANT_LOGS_DIR") or os.path.join(DATA_DIR, "logs")
MANUAL_DATA_DIR = os.path.join(DATA_DIR, "manual")

# Đảm bảo các thư mục luôn tồn tại
for _dir in [DATA_DIR, REPORTS_DIR, LOGS_DIR, MANUAL_DATA_DIR]:
    os.makedirs(_dir, exist_ok=True)

# Quy chuẩn đơn vị giá và thang đo
UNIT_STOCK_PRICE = "kVND"       # Cổ phiếu lưu ở đơn vị nghìn đồng
UNIT_INDEX = "POINT"           # Chỉ số lưu ở điểm nguyên
LOG_CHART_DEFAULT = True       # 100% Log Scale

# Tham số hình học & Pitchfork
DEFAULT_SWING_ORDER = 5        # N=5 nến mỗi bên cho argrelextrema
MIN_SWING_ORDER = 2
MAX_SWING_ORDER = 20

# Trọng số Top-Down mặc định (0-100)
DEFAULT_TOPDOWN_WEIGHTS = {
    "T1_Astro_Gann": 0.10,
    "T2_Macro_Margin": 0.20,
    "T3_Commodity_RRG": 0.20,
    "T4_Deriv_Breadth": 0.10,
    "T5_VNIndex_MTF": 0.40
}

# Tham số RRG (Relative Rotation Graph)
RRG_BENCHMARK = "VNINDEX"
RRG_WINDOW_WEEKS = 12
RRG_TAIL_PERIODS = 8

# Tham số Black-Scholes Định giá CW
CW_DEFAULT_RISK_FREE_RATE = 0.05  # 5%/năm
CW_VOLATILITY_LOOKBACK = 60       # 60 phiên giao dịch
CW_IV_MIN = 1e-4
CW_IV_MAX = 5.0                   # 500%
CW_PAYOFF_RANGE_PCT = 0.20        # +/- 20%
CW_PAYOFF_STEP_PCT = 0.02         # bước 2% (21 kịch bản)

# Ngưỡng màu Top-Down Composite Score Gauge
SCORE_ZONES = [
    {"range": [0, 30], "color": "#FF3B30", "label": "Bearish (Rủi ro cao)"},
    {"range": [30, 50], "color": "#FF9500", "label": "Neutral (Thận trọng)"},
    {"range": [50, 70], "color": "#34C759", "label": "Bullish (Tích cực)"},
    {"range": [70, 100], "color": "#007AFF", "label": "Strong Bull (Cơ hội lớn)"}
]

# Tùy chọn lọc mặc định
DEFAULT_UNIVERSE_TIER = 1  # 1 = Fast Core (~150 mã)
EXCLUDE_VINGROUP_DEFAULT = False

# =====================================================================
# LUẬT BIÊN ĐỘ GIÁ THEO SÀN (dùng cho kiểm tra toàn vẹn dữ liệu)
# =====================================================================
# Biên độ dao động giá chuẩn của từng sàn trong một phiên.
PRICE_LIMIT = {
    "HOSE": 0.07,     # ±7%
    "HNX": 0.10,      # ±10%
    "UPCOM": 0.15,    # ±15%
}
DEFAULT_EXCHANGE = "HOSE"

# Sai số cho phép: làm tròn bước giá, giá tham chiếu, đơn vị kVND (2 chữ số thập phân).
# 0.5pp là đủ rộng cho sai số làm tròn nhưng vẫn bắt được mọi cú nhảy bất khả thi.
LIMIT_TOLERANCE = 0.005

# Vượt biên độ trong khoảng (limit, limit + WARN] chỉ ghi cảnh báo, KHÔNG xóa:
# đây là dư âm của điều chỉnh cổ tức trên chuỗi giá đã điều chỉnh.
LIMIT_WARN_TOLERANCE = 0.02

# Ngày giao dịch đầu tiên của một mã được phép vượt biên độ (biên độ riêng khi niêm yết).
LISTING_DAY_LIMIT = {
    "HOSE": 0.20,
    "HNX": 0.30,
    "UPCOM": 0.40,
}

# Sau thời gian tạm ngừng giao dịch dài, phiên đầu tiên được nới biên độ.
POST_SUSPENSION_DAYS = 25
POST_SUSPENSION_LIMIT = 0.20

# Ngưỡng phân loại một cú nhảy giá bất khả thi:
# - STEP  : đổi mức giá vĩnh viễn  -> nghi chia tách / cổ tức chưa điều chỉnh
# - SPIKE : giật 1 phiên rồi quay lại -> dữ liệu hỏng, phải loại bỏ
SPIKE_WINDOW = 3            # số phiên để kiểm tra giá có quay về mức cũ
SPIKE_REVERSAL_RATIO = 0.5  # |r_next| >= 50% |r| được coi là đảo chiều

# =====================================================================
# CỬA SỔ DỮ LIỆU CHUẨN
# =====================================================================
# 2010-2011: dữ liệu cũ, chỉ hiển thị (legacy). 2012 -> nay: canonical, dùng để ra quyết định.
DATA_WINDOW_START = "2012-01-01"
LEGACY_WINDOW_END = "2011-12-31"
BACKTEST_START = "2015-01-01"

# =====================================================================
# GIỚI HẠN TỐC ĐỘ NGUỒN DỮ LIỆU MIỄN PHÍ (0 credential)
# =====================================================================
# vnstock guest ~20 request/phút -> giữ 18 để an toàn.
VNSTOCK_GUEST_RPM = 18
VNSTOCK_KEY_RPM = 55
YFINANCE_SLEEP_SEC = 0.05
FULL_REFRESH_DAYS = 7          # chu kỳ tải lại toàn bộ để bắt điều chỉnh hồi tố cổ tức

# =====================================================================
# CHI PHÍ GIAO DỊCH (dùng cho backtest thực chiến)
# =====================================================================
FEE_BUY = 0.0015       # 0,15% phí môi giới chiều mua
FEE_SELL = 0.0015      # 0,15% phí môi giới chiều bán
TAX_SELL = 0.0010      # 0,10% thuế bán
SLIPPAGE = 0.0015      # 0,15% trượt giá mỗi chiều
SETTLEMENT_DAYS = 2.5  # T+2.5 (bán được sau 2,5 phiên)

# =====================================================================
# THAM SỐ BỘ LỌC 3 PRESET (hiệu chỉnh bằng kiểm định lịch sử 2015-2026)
# ---------------------------------------------------------------------
# NGUỒN DUY NHẤT: cả `core/screener.py` (quét live) và
# `core/backtest_engine.py` (kiểm định) đều đọc từ đây, nhờ đó tín hiệu
# live và tín hiệu lịch sử luôn cùng một tập. Muốn thực nghiệm ngưỡng mới
# thì sửa đúng một chỗ này (hoặc override động trong script nghiên cứu).
# =====================================================================
PRESET_2_PARAMS = {
    "breakout_margin": 1.005,      # Close >= UpperLine * 1.005 (bứt phá >= 0,5%)
    "candle_strength_min": 0.50,   # (Close - Low) / (High - Low) nến tuần
    "max_dist_ema21w": 0.12,       # |Close - EMA21(1W)| / EMA21(1W) <= 12%
    "rsi_max": 70.0,               # chống mua đuổi quá mua trên nến ngày
    "mfi_min_1w": 48.0,            # xung lực dòng tiền nến tuần
    "vol_ratio_min_1w": 1.5,       # Volume tuần >= 1.5x SMA9(Vol)
    "market_ema50_buffer": 0.98,   # VN-Index Close >= EMA50 * 0.98
    "market_rsi_min": 46.0,        # HOẶC VN-Index RSI14 >= 46
}

PRESET_3_PARAMS = {
    "max_dist_ema21_pct": 2.0,     # |Close - EMA21(1D)| / EMA21(1D) <= 2%
    "rsi_low": 40.0,
    "rsi_high": 58.0,
    "rsi_healthy": 45.0,           # RSI ngày xác nhận lành mạnh
    "fisher_min": -0.6,
    "vol_dryup_max": 1.10,         # cạn cung: vol_ratio nến trước <= 1.10
    "ema21_buffer": 0.99,          # giữ vững EMA21 * 0.99
    "candle_strength_min": 0.50,
    "market_ema50_buffer": 0.995,  # VN-Index Close >= EMA50 * 0.995
    "market_rsi_min": 48.0,        # HOẶC VN-Index RSI14 >= 48
}

PRESET_1_PARAMS = {
    "fisher_1m_max": -1.8,         # Fisher(9, 1M) < -1.8 (đáy chu kỳ)
    "ma200_1m_band_pct": 10.0,     # giá quanh MA200(1M) ± 10%
    "rsi_1d_min": 30.0,            # xác nhận nến ngày
    "vol_ratio_1d_min": 1.25,      # khối lượng hấp thụ
}
