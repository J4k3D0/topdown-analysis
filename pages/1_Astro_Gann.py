"""
pages/1_Astro_Gann.py
Tầng 1 — Thiên văn Tài chính & W.D. Gann (Trọng số 10%)
- Lịch pha Mặt Trăng (New Moon / Full Moon) và dải Thủy Tinh nghịch hành (Mercury Retrograde)
- Bộ tính Gann Time Cycles (+30, +45, +60, +90, +144, +180, +360 ngày lịch và 21, 34, 55, 89, 144 nến)
- Gann Square of 9 (chuẩn hóa đơn vị kVND, hệ số k = 0.5 - 2.0)
- Gann Fan & Gann Box trên không gian Logarit
- Slider chấm điểm Tầng 1 (0 - 100) cho người dùng tự đánh giá (lưu bền vững SQLite)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date

from core.db_manager import get_setting, set_setting, load_ohlcv
from core.astro_engine import get_moon_phase_info, is_mercury_retrograde, get_astro_events_for_range
from core.gann_engine import calculate_gann_time_cycles, calculate_gann_square_of_9, calculate_gann_fan_log, calculate_gann_box_log
from components.charts_plotly import create_deep_dive_chart

st.set_page_config(page_title="Tầng 1: Thiên văn & Gann", page_icon="🪐", layout="wide")

st.title("🪐 TẦNG 1: THIÊN VĂN TÀI CHÍNH & W.D. GANN")
st.caption("Khung phân tích chu kỳ tự nhiên kết hợp góc độ hình học W.D. Gann (Square of 9, Time Cycles, Fan/Box)")

# --- SLIDER CHẤM ĐIỂM TẦNG 1 ---
st.subheader("📝 Đánh Giá & Chấm Điểm Tầng 1 (0 - 100)")
current_t1_score = float(get_setting("t1_user_score", 65.0))
col_s1, col_s2 = st.columns([2, 1])

with col_s1:
    new_t1_score = st.slider(
        "Kéo thanh trượt để chấm điểm Tầng 1 (hệ thống tự động lưu vào Database)",
        min_value=0.0, max_value=100.0, value=current_t1_score, step=5.0
    )
    if new_t1_score != current_t1_score:
        set_setting("t1_user_score", new_t1_score)
        st.success(f"Đã lưu điểm Tầng 1: **{new_t1_score} / 100**")

with col_s2:
    st.markdown("""
    **Bảng gợi ý điểm tham khảo:**
    - `80 - 100`: Gann Time Cycle trùng vùng đảo chiều + New Moon + Thủy Tinh thuận hành
    - `50 - 70`: Gann Time Cycle gần vùng đảo chiều, không có cảnh báo
    - `40 - 50`: Vùng trung tính, không có tín hiệu Gann nổi bật
    - `0 - 40`: Thủy Tinh nghịch hành + Full Moon + nhiều tín hiệu cảnh báo đỉnh
    """)

st.markdown("---")

# --- PHẦN 1: THIÊN VĂN TÀI CHÍNH ---
st.header("1. Chu Kỳ Pha Mặt Trăng & Thủy Tinh Nghịch Hành")

today = date.today()
moon_info = get_moon_phase_info(today)
is_retro = is_mercury_retrograde(today)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Pha Mặt Trăng Hôm Nay", moon_info["phase_name"], f"Tuổi trăng: {moon_info['moon_age']} ngày")
col_m2.metric("Độ Chiếu Sáng", f"{moon_info['illumination_pct']}%")
col_m3.metric(
    "Thủy Tinh (Mercury)",
    "🔴 NGHỊCH HÀNH (Retrograde)" if is_retro else "🟢 THUẬN HÀNH (Direct)",
    "Cảnh báo rung lắc/nhiễu" if is_retro else "Xu hướng thông suốt"
)

if is_retro:
    st.warning("⚠️ **CẢNH BÁO THỦY TINH NGHỊCH HÀNH:** Thị trường thường phát sinh các nhịp đảo chiều giả hoặc biến động bất thường. Khuyến nghị hạn chế mua đuổi giá cao!")

st.markdown("---")

# --- PHẦN 2: W.D. GANN SQUARE OF 9 ---
st.header("2. W.D. Gann Square of 9 (Khóa Chuẩn Đơn Vị kVND)")
st.caption("Công thức toán học: $P_{target}(\\theta, k) = (\\sqrt{P_0} \\pm \\frac{\\theta}{180^\\circ} \\cdot k)^2$")

col_g1, col_g2, col_g3 = st.columns(3)
p0_input = col_g1.number_input("Giá Neo Đỉnh/Đáy Gốc (P0 theo kVND)", min_value=0.1, max_value=5000.0, value=21.2, step=0.1)
k_slider = col_g2.slider("Hệ số bước nhảy k", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
is_idx = col_g3.checkbox("Đây là Chỉ số (VN-Index > 500 điểm)", value=False)

gann_sq9 = calculate_gann_square_of_9(p0_input, k=k_slider, is_index=is_idx)

if gann_sq9:
    col_res, col_sup = st.columns(2)
    with col_res:
        st.subheader("🔺 Các Mốc Kháng Cự (Chiều Tăng)")
        df_res = pd.DataFrame(gann_sq9["resistances"])
        st.dataframe(df_res.rename(columns={"label": "Góc", "price": "Giá Mục Tiêu (kVND)", "pct_change": "% Tăng"}), width='stretch')

    with col_sup:
        st.subheader("🔻 Các Mốc Hỗ Trợ (Chiều Giảm)")
        df_sup = pd.DataFrame(gann_sq9["supports"])
        st.dataframe(df_sup.rename(columns={"label": "Góc", "price": "Giá Hỗ Trợ (kVND)", "pct_change": "% Giảm"}), width='stretch')

st.markdown("---")

# --- PHẦN 3: GANN TIME CYCLES ---
st.header("3. Gann Time Cycles & Fibonacci Time Projection")

base_date_input = st.date_input("Chọn Ngày Đỉnh / Đáy Gốc Neo Chu Kỳ Thời Gian", value=date(2026, 11, 3))
cycles_data = calculate_gann_time_cycles(base_date_input)

col_t1, col_t2 = st.columns(2)
with col_t1:
    st.subheader("📅 Mốc Ngày Lịch (+30, +45, +60, +90, +144, +180, +360 ngày)")
    st.dataframe(pd.DataFrame(cycles_data["calendar_cycles"]), width='stretch')

with col_t2:
    st.subheader("📊 Mốc Phiên Giao Dịch (Fibonacci Time: 21, 34, 55, 89, 144 nến)")
    st.write(f"Tính từ ngày neo `{cycles_data['base_date']}`:")
    for b in cycles_data["trading_bars"]:
        st.markdown(f"- **+{b} phiên:** Vùng kiểm tra quán tính đảo chiều xu hướng")
