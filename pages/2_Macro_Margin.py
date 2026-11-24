"""
pages/2_Macro_Margin.py
Tầng 2 — Vĩ mô, Lợi suất & Dư nợ Margin (Trọng số 20%)
- Đường cong lợi suất Trái phiếu Mỹ FRED (T10Y2Y, T10Y3M)
- Các tài sản vĩ mô quốc tế: DXY, US10Y, USD/VND, VIX
- Biểu đồ tương quan Dư nợ Margin toàn thị trường vs Đỉnh/Đáy VN-Index (2000 - 2026)
- Tính toán tự động điểm Tầng 2 theo Rubric khóa trong v5.0
- Quản lý sự kiện Chính trị / Chính sách Vĩ mô (FOMC, NHNN, Quốc hội)
"""

import streamlit as st
import pandas as pd
import os

from core.db_manager import get_connection, load_ohlcv_global
from core.scoring_engine import score_tier2_macro_margin
from core.margin_aggregator import get_margin_series, import_margin_excel
from components.charts_plotly import create_yield_curve_chart, create_margin_correlation_chart

st.set_page_config(page_title="Tầng 2: Vĩ mô & Margin", page_icon="🌐", layout="wide")

st.title("🌐 TẦNG 2: VĨ MÔ, LỢI SUẤT & DƯ NỢ MARGIN")
st.caption("Khung phân tích chu kỳ tiền tệ vĩ mô, độ dốc Yield Curve, áp lực tỷ giá và đòn bẩy Margin thị trường")

# --- ĐIỂM SỐ TỰ ĐỘNG TẦNG 2 ---
conn = get_connection()
try:
    df_yield = pd.read_sql_query("SELECT date, t10y2y, t10y3m FROM yield_curve ORDER BY date ASC;", conn)
    # Tăng trưởng Margin QoQ từ 2 quý gần nhất trong DB
    cursor = conn.cursor()
    cursor.execute("""
        SELECT total_margin_bn FROM margin_history
        WHERE scope = 'market_total' AND total_margin_bn IS NOT NULL
        ORDER BY quarter DESC LIMIT 2;
    """)
    _m_rows = cursor.fetchall()
finally:
    conn.close()

last_yield = float(df_yield['t10y2y'].iloc[-1]) if not df_yield.empty else 0.25

# Đọc dữ liệu vĩ mô THẬT từ ohlcv_global (không dùng số hardcoded)
def _last_global(ticker: str):
    try:
        s = load_ohlcv_global(ticker)
        if s is not None and not s.empty and 'close' in s.columns:
            return float(s['close'].iloc[-1])
    except Exception:
        pass
    return None

real_dxy = _last_global('DX-Y.NYB')
real_vix = _last_global('^VIX')

# Tỷ giá USD/VND: đọc chuỗi VND=X (nếu có), tính % thay đổi 60 phiên
vnd_series = load_ohlcv_global('VND=X')
real_vnd_change = None
if vnd_series is not None and not vnd_series.empty and 'close' in vnd_series.columns and len(vnd_series) > 60:
    _c_now = float(vnd_series['close'].iloc[-1])
    _c_60 = float(vnd_series['close'].iloc[-61])
    if _c_60 > 0:
        real_vnd_change = (_c_now / _c_60 - 1.0) * 100.0

last_margin_qoq = None
if len(_m_rows) == 2 and _m_rows[1][0] not in (None, 0):
    last_margin_qoq = (float(_m_rows[0][0]) / float(_m_rows[1][0]) - 1.0) * 100.0

margin_df = get_margin_series(scope="market_total")

t2_result = score_tier2_macro_margin({
    "t10y2y": last_yield,
    "dxy": real_dxy,
    "vix": real_vix,
    "vnd_change_60d": real_vnd_change,
    "margin_growth_qoq": last_margin_qoq
})

col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
col_s1.metric("Điểm Tầng 2 (Vĩ mô & Margin)", f"{t2_result['score']}/100")
col_s2.metric("Yield Curve (T10Y2Y)", f"{last_yield:+.2f}%", f"{t2_result['details'].get('yield', 'N/A')} điểm")
col_s3.metric("Chỉ số DXY", f"{real_dxy:.2f}" if real_dxy is not None else "N/A", f"{t2_result['details'].get('dxy', 'N/A')} điểm")
col_s4.metric("Chỉ số VIX", f"{real_vix:.2f}" if real_vix is not None else "N/A", f"{t2_result['details'].get('vix', 'N/A')} điểm")
_margin_lbl = f"{last_margin_qoq:+.1f}%" if last_margin_qoq is not None else "N/A"
col_s5.metric("Tăng trưởng Margin QoQ", _margin_lbl, f"{t2_result['details'].get('margin', 'N/A')} điểm")

st.markdown("---")

# --- PHẦN 1: ĐƯỜNG CONG LỢI SUẤT FRED ---
st.header("1. Đường Cong Lợi Suất Trái Phiếu Chính Phủ Mỹ (FRED Yield Curve)")
fig_yield = create_yield_curve_chart(df_yield)
st.plotly_chart(fig_yield, width='stretch')

st.markdown("---")

# --- PHẦN 2: DƯ NỢ MARGIN VS VN-INDEX ---
st.header("2. Tương Quan Dư Nợ Margin vs Đỉnh/Đáy VN-Index (2000 - 2026)")
if margin_df.empty:
    st.info("ℹ️ Chưa có dữ liệu Dư nợ Margin thật trong Local DB. Hệ thống không hiển thị số liệu giả lập — "
            "vui lòng import file Excel/CSV bên dưới để kích hoạt phần phân tích này.")
else:
    st.caption(f"Dữ liệu toàn thị trường 78 CTCK ({margin_df['quarter'].iloc[-1]}: "
               f"{margin_df['total_margin_bn'].iloc[-1]:,.0f} tỷ đồng)")

uploaded_file = st.file_uploader("Import bổ sung file Excel/CSV Dư nợ Margin (vnindex_margin_2000_2026.xlsx)", type=["xlsx", "xls", "csv"])
if uploaded_file is not None:
    _ext = os.path.splitext(uploaded_file.name)[1].lower() or ".xlsx"
    _dest = os.path.join("data", "manual", f"uploaded_margin{_ext}")
    os.makedirs(os.path.dirname(_dest), exist_ok=True)
    with open(_dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    try:
        c = import_margin_excel(_dest)
        st.success(f"Đã import thành công {c} quý dữ liệu Margin!")
        st.rerun()
    except Exception as e:
        st.error(f"Import thất bại: {e}")

if not margin_df.empty:
    fig_margin = create_margin_correlation_chart(margin_df)
    st.plotly_chart(fig_margin, width='stretch')

    st.subheader("📋 Bảng Thống Kê Dư Nợ Margin Qua Các Quý")
    st.dataframe(margin_df.tail(12).rename(columns={
        "quarter": "Quý",
        "total_margin_bn": "Dư nợ Margin (Tỷ VNĐ)",
        "vnindex_close": "VN-Index",
        "margin_growth_qoq": "Tăng trưởng QoQ (%)"
    }), width='stretch')

st.markdown("---")

# --- PHẦN 3: SỰ KIỆN CHÍNH SÁCH VĨ MÔ ---
st.header("3. Nhật Ký Sự Kiện Chính Sách Vĩ Mô & Tiền Tệ")

conn = get_connection()
try:
    cursor = conn.cursor()
    cursor.execute("SELECT event_date, event_type, description, impact FROM macro_events ORDER BY event_date DESC;")
    events = cursor.fetchall()

    if not events:
        # Nạp sự kiện mẫu
        sample_events = [
            ("2026-11-01", "NHNN", "Duy trì lãi suất điều hành thấp hỗ trợ tăng trưởng tín dụng cuối năm", "BULLISH"),
            ("2026-10-15", "QUOC_HOI", "Kỳ họp thông qua các gói thúc đẩy đầu tư công hạ tầng giao thông", "BULLISH"),
            ("2026-09-18", "FOMC", "Fed hạ lãi suất 25 bps, giảm bớt áp lực tỷ giá USD/VND", "BULLISH")
        ]
        cursor.executemany("INSERT INTO macro_events (event_date, event_type, description, impact) VALUES (?, ?, ?, ?);", sample_events)
        conn.commit()
        cursor.execute("SELECT event_date, event_type, description, impact FROM macro_events ORDER BY event_date DESC;")
        events = cursor.fetchall()
finally:
    conn.close()

st.dataframe(pd.DataFrame(events, columns=["Ngày", "Tổ Chức", "Nội Dung Sự Kiện", "Tác Động"]), width='stretch')
