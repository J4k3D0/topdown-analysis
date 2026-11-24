"""
app.py
Trang chủ: Master Dashboard & DB Control Center
Hệ Thống Phân Tích Đầu Tư Top-Down 6 Tầng & Local Quant Database (v5.0)
Tích hợp Dynamic Reweighting & Data Quality Pipeline Guard (0 hardcoded data)
"""

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Top-Down Quant System v5.0",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

from config.settings import DEFAULT_TOPDOWN_WEIGHTS
from config.tickers import TIER_1_UNIVERSE, VINGROUP_TICKERS
from core.db_manager import (
    init_db, get_db_max_date, get_setting, set_setting, load_ohlcv, get_connection
)
from core.data_fetcher import sync_database
from core.indicators import (
    calculate_all_indicators, resample_ohlcv, compute_ex_vingroup_index,
    compute_market_breadth
)
from core.scoring_engine import (
    score_tier1_astro_gann, score_tier2_macro_margin,
    score_tier3_market_level, score_tier4_derivatives_breadth,
    score_tier5_vnindex_mtf, calculate_topdown_composite_score
)
from core.portfolio_alerts import evaluate_portfolio_alerts
from components.ui_cards import render_topdown_gauge, render_db_calendar_guard, render_alert_card
from components.charts_plotly import create_deep_dive_chart

# Khởi tạo DB nếu chưa có
init_db()

# --- SIDEBAR CONTROL CENTER ---
st.sidebar.title("🎛️ DB Control Center")

db_last_date = get_db_max_date()
st.sidebar.markdown(f"**Ngày dữ liệu gần nhất:** `{db_last_date if db_last_date else 'Chưa có'}`")

# Thống kê mã theo sàn trong DB
conn_sidebar = get_connection()
try:
    cur_sidebar = conn_sidebar.cursor()
    cur_sidebar.execute("SELECT exchange, count(*) FROM stock_metadata GROUP BY exchange;")
    ex_counts = dict(cur_sidebar.fetchall())
finally:
    conn_sidebar.close()

c_hose = ex_counts.get("HOSE", 0)
c_hnx = ex_counts.get("HNX", 0)
c_upcom = ex_counts.get("UPCOM", 0)
st.sidebar.caption(f"📊 **Trong DB:** HOSE ({c_hose}) • HNX ({c_hnx}) • UPCoM ({c_upcom})")

from config.tickers import get_tickers_by_exchange

scope_choice = st.sidebar.selectbox(
    "Phạm vi Cập nhật / Đồng bộ",
    options=["TIER_1", "ALL", "HOSE", "HNX", "UPCOM"],
    format_func=lambda x: {
        "TIER_1": "Tier 1: Fast Core (~150 mã liên sàn)",
        "ALL": "Tất Cả 3 Sàn (HOSE + HNX + UPCOM)",
        "HOSE": "Sàn HOSE / HSX (~120 mã)",
        "HNX": "Sàn HNX (HNX30 & Thanh khoản)",
        "UPCOM": "Sàn UPCoM (Vốn hóa lớn)",
    }.get(x, x),
    index=0
)

target_sync_tickers = get_tickers_by_exchange(scope_choice)
st.sidebar.caption(f"🎯 Số mã chọn cập nhật: **{len(target_sync_tickers)} mã**")

# Nút đồng bộ dữ liệu
if st.sidebar.button("🔄 Đồng Bộ / Cập Nhật Database", type="primary", width='stretch'):
    prog_bar = st.sidebar.progress(0.0)
    status_text = st.sidebar.empty()

    def update_prog(pct, msg):
        prog_bar.progress(pct)
        status_text.caption(msg)

    with st.spinner(f"Đang đồng bộ dữ liệu ({scope_choice}) vào SQLite qua Multi-Source Pipeline..."):
        res = sync_database(tickers=target_sync_tickers, progress_callback=update_prog)
        st.sidebar.success(f"Đã cập nhật {res['synced_count']} mã ({scope_choice}) thành công!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Trọng Số 5 Tầng Top-Down")

# Đọc cấu hình trọng số đã lưu hoặc dùng mặc định
saved_weights = get_setting("topdown_weights", DEFAULT_TOPDOWN_WEIGHTS)

w_t1 = st.sidebar.slider("Tầng 1: Thiên văn & Gann (%)", 0, 50, int(saved_weights.get("T1_Astro_Gann", 0.10) * 100), step=5)
w_t2 = st.sidebar.slider("Tầng 2: Vĩ mô & Margin (%)", 0, 50, int(saved_weights.get("T2_Macro_Margin", 0.20) * 100), step=5)
w_t3 = st.sidebar.slider("Tầng 3: Hàng hóa & RRG (%)", 0, 50, int(saved_weights.get("T3_Commodity_RRG", 0.20) * 100), step=5)
w_t4 = st.sidebar.slider("Tầng 4: Phái sinh & Độ rộng (%)", 0, 50, int(saved_weights.get("T4_Deriv_Breadth", 0.10) * 100), step=5)
w_t5 = st.sidebar.slider("Tầng 5: VN-Index Đa khung (%)", 0, 80, int(saved_weights.get("T5_VNIndex_MTF", 0.40) * 100), step=5)

new_weights = {
    "T1_Astro_Gann": w_t1 / 100.0,
    "T2_Macro_Margin": w_t2 / 100.0,
    "T3_Commodity_RRG": w_t3 / 100.0,
    "T4_Deriv_Breadth": w_t4 / 100.0,
    "T5_VNIndex_MTF": w_t5 / 100.0
}
set_setting("topdown_weights", new_weights)

st.sidebar.markdown("---")
ex_vin_opt = st.sidebar.checkbox("Loại trừ Vingroup (VIC, VHM, VRE, VPL)", value=get_setting("exclude_vingroup", False))
set_setting("exclude_vingroup", ex_vin_opt)

# --- NỘI DUNG CHÍNH MASTER DASHBOARD ---
st.title("📈 HỆ THỐNG PHÂN TÍCH ĐẦU TƯ TOP-DOWN 6 TẦNG")
st.caption("Phương pháp luận: Thực chiến cá nhân (KDH, NLG, FPT) • Khung PTCB vfin.vn • Wiley Trading (John Murphy, Martin Pring, John Ehlers, W.D. Gann)")

# 1. Kiểm tra Lịch giao dịch VN-Index & Data Quality Guard
render_db_calendar_guard(db_last_date)

# 2. Truy vấn dữ liệu thực tế từ Local Database (Không nhồi số giả)
conn = get_connection()
try:
    cursor = conn.cursor()

    # Lấy T10Y2Y từ bảng yield_curve
    cursor.execute("SELECT t10y2y FROM yield_curve ORDER BY date DESC LIMIT 1;")
    y_row = cursor.fetchone()
    real_t10y2y = float(y_row[0]) if y_row and y_row[0] is not None else None

    # Lấy DXY từ ohlcv_global
    cursor.execute("SELECT close FROM ohlcv_global WHERE ticker = 'DX-Y.NYB' ORDER BY date DESC LIMIT 1;")
    dxy_row = cursor.fetchone()
    real_dxy = float(dxy_row[0]) if dxy_row and dxy_row[0] is not None else None

    # Lấy VIX từ ohlcv_global
    cursor.execute("SELECT close FROM ohlcv_global WHERE ticker = '^VIX' ORDER BY date DESC LIMIT 1;")
    vix_row = cursor.fetchone()
    real_vix = float(vix_row[0]) if vix_row and vix_row[0] is not None else None

    # Suy ra tăng trưởng margin QoQ từ hai quý gần nhất. Schema chỉ lưu giá trị
    # dư nợ gốc, không lưu một cột tăng trưởng dẫn xuất.
    cursor.execute("""
        SELECT total_margin_bn
        FROM margin_history
        WHERE scope = 'market_total' AND total_margin_bn IS NOT NULL
        ORDER BY quarter DESC
        LIMIT 2;
    """)
    margin_rows = cursor.fetchall()
    real_margin_qoq = None
    if len(margin_rows) == 2 and margin_rows[1][0] not in (None, 0):
        real_margin_qoq = (float(margin_rows[0][0]) / float(margin_rows[1][0]) - 1.0) * 100.0

    # Schema phái sinh lưu giá/OI nguyên gốc. Basis cần giá spot VN30 nên được
    # tính sau khi kiểm tra hai chuỗi có cùng ngày; xu hướng OI dùng hai phiên gần nhất.
    cursor.execute("""
        SELECT date, COALESCE(settlement_price, close), oi
        FROM derivatives_daily
        WHERE ticker = 'VN30F1M'
        ORDER BY date DESC
        LIMIT 2;
    """)
    deriv_rows = cursor.fetchall()
finally:
    conn.close()

# 3. Tính toán điểm từng tầng theo dữ liệu thực
# T1: Thiên văn & Gann (người dùng tự chấm)
t1_user_score = float(get_setting("t1_user_score", 65.0))
s1 = score_tier1_astro_gann(t1_user_score)

# T2: Vĩ mô & Margin (Dynamic Reweighting trên dữ liệu thực tế)
t2_input = {
    "t10y2y": real_t10y2y,
    "dxy": real_dxy,
    "vix": real_vix,
    "vnd_change_60d": None,
    "margin_growth_qoq": real_margin_qoq
}
t2_res = score_tier2_macro_margin(t2_input)
s2 = t2_res["score"]

# T3: Hàng hóa & RRG — tính điểm xu hướng hàng hóa THẬT từ ohlcv_global
_comm_tickers = ['GC=F', 'BZ=F', 'CL=F', 'HG=F', 'SLX']
_moms = []
_conn_c = get_connection()
try:
    for _tk in _comm_tickers:
        _g = pd.read_sql_query(
            "SELECT close FROM ohlcv_global WHERE ticker = ? ORDER BY date ASC;",
            _conn_c, params=[_tk])
        if len(_g) > 60:
            _moms.append((float(_g['close'].iloc[-1]) / float(_g['close'].iloc[-61]) - 1.0) * 100.0)
finally:
    _conn_c.close()

commodity_trend_score = None
if _moms:
    _avg_mom = float(np.mean(_moms))
    if _avg_mom > 5.0:
        commodity_trend_score = 80.0
    elif _avg_mom >= 0.0:
        commodity_trend_score = 65.0
    elif _avg_mom >= -5.0:
        commodity_trend_score = 45.0
    else:
        commodity_trend_score = 25.0

t3_res = score_tier3_market_level(rrg_results=None, commodity_trend_score=commodity_trend_score)
s3 = t3_res["score"]

# T5: VN-Index Đa khung
df_vni = load_ohlcv("VNINDEX")
df_vn30 = load_ohlcv("VN30")

# Xử lý tùy chọn loại trừ 4 mã Vingroup (EX_VIN)
df_vni_target = df_vni
vni_chart_title = "VNINDEX"
if df_vni is not None and not df_vni.empty and ex_vin_opt:
    vin_dfs = {}
    for vt in VINGROUP_TICKERS:
        df_vin_item = load_ohlcv(vt)
        if df_vin_item is not None and not df_vin_item.empty:
            vin_dfs[vt] = df_vin_item
    df_vni_ex = compute_ex_vingroup_index(df_vni, vin_dfs)
    if df_vni_ex is not None and 'close_ex_vin' in df_vni_ex.columns:
        df_vni_target = df_vni.copy()
        df_vni_target['open'] = df_vni_ex['open_ex_vin']
        df_vni_target['high'] = df_vni_ex['high_ex_vin']
        df_vni_target['low'] = df_vni_ex['low_ex_vin']
        df_vni_target['close'] = df_vni_ex['close_ex_vin']
        vni_chart_title = "VNINDEX (EX-VIN)"

real_basis = None
real_oi_trend = None
if deriv_rows and df_vn30 is not None and not df_vn30.empty:
    deriv_date, deriv_price, _ = deriv_rows[0]
    spot_rows = df_vn30[df_vn30["date"] == pd.to_datetime(deriv_date)]
    if deriv_price is not None and not spot_rows.empty:
        real_basis = float(deriv_price) - float(spot_rows.iloc[-1]["close"])
if len(deriv_rows) == 2:
    _, last_price, last_oi = deriv_rows[0]
    _, prev_price, prev_oi = deriv_rows[1]
    if None not in (last_price, prev_price, last_oi, prev_oi):
        oi_direction = "UP" if float(last_oi) >= float(prev_oi) else "DOWN"
        price_direction = "UP" if float(last_price) >= float(prev_price) else "DOWN"
        real_oi_trend = f"OI_{oi_direction}_PRICE_{price_direction}"
df_1d_ind = None
df_1w_ind = None
df_1m_ind = None
if df_vni_target is not None and len(df_vni_target) > 50:
    df_1d_ind = calculate_all_indicators(df_vni_target, is_monthly=False)
    df_1w_ind = calculate_all_indicators(resample_ohlcv(df_vni_target, "1W"), is_monthly=False)
    df_1m_ind = calculate_all_indicators(resample_ohlcv(df_vni_target, "1M"), is_monthly=True)
    t5_res = score_tier5_vnindex_mtf(df_1m_ind, df_1w_ind, df_1d_ind)
    s5 = t5_res["score"]
elif df_vni_target is not None and len(df_vni_target) > 0:
    # Có dữ liệu nhưng chưa đủ 50 phiên: vẫn có thể vẽ biểu đồ, điểm T5 = N/A
    df_1d_ind = calculate_all_indicators(df_vni_target, is_monthly=False)
    s5 = None
else:
    s5 = None

# T4: Phái sinh & Độ rộng (sau khi đã suy ra basis/OI từ dữ liệu thô)
_breadth = compute_market_breadth(TIER_1_UNIVERSE, sample_size=60)
t4_input = {
    "basis": real_basis,
    "pct_above_ma50": _breadth["pct_above_ma50"],
    "ad_slope": _breadth["ad_slope"],
    "oi_trend": real_oi_trend
}
t4_res = score_tier4_derivatives_breadth(t4_input)
s4 = t4_res["score"]

# Tổng hợp Top-Down Composite Score với Dynamic Reweighting
scores_dict = {"T1": s1, "T2": s2, "T3": s3, "T4": s4, "T5": s5}
composite_data = calculate_topdown_composite_score(scores_dict, weights=new_weights)

# 4. Hiển thị Gauge và KPI thẻ điểm
col_gauge, col_kpi = st.columns([1.2, 1.8])

with col_gauge:
    fig_gauge = render_topdown_gauge(composite_data)
    st.plotly_chart(fig_gauge, width='stretch')

with col_kpi:
    st.subheader("📊 Điểm Thành Phần 5 Tầng (Dynamic Reweighting)")
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    kpi_col1.metric("T1: Thiên văn / Gann", f"{s1:.1f}/100", f"Trọng số {composite_data['weights'].get('T1_Astro_Gann', 0)*100:.0f}%")
    
    t2_label = f"{s2:.1f}/100" if s2 is not None else "N/A"
    t2_delta = f"Trọng số {composite_data['weights'].get('T2_Macro_Margin', 0)*100:.0f}%" if s2 is not None else "Tự động phân bổ lại"
    kpi_col2.metric("T2: Vĩ mô / Margin", t2_label, t2_delta)

    t3_label = f"{s3:.1f}/100" if s3 is not None else "N/A"
    t3_delta = f"Trọng số {composite_data['weights'].get('T3_Commodity_RRG', 0)*100:.0f}%" if s3 is not None else "Tự động phân bổ lại"
    kpi_col3.metric("T3: Hàng hóa / RRG", t3_label, t3_delta)

    kpi_col4, kpi_col5 = st.columns(2)
    t4_label = f"{s4:.1f}/100" if s4 is not None else "N/A"
    t4_delta = f"Trọng số {composite_data['weights'].get('T4_Deriv_Breadth', 0)*100:.0f}%" if s4 is not None else "Tự động phân bổ lại"
    kpi_col4.metric("T4: Phái sinh / Độ rộng", t4_label, t4_delta)

    t5_label = f"{s5:.1f}/100" if s5 is not None else "N/A"
    t5_delta = f"Trọng số {composite_data['weights'].get('T5_VNIndex_MTF', 0)*100:.0f}%" if s5 is not None else "Thiếu dữ liệu VNI"
    kpi_col5.metric(f"T5: VN-Index MTF {'(EX_VIN)' if ex_vin_opt else ''}", t5_label, t5_delta)

    if composite_data.get("reweighted"):
        missing_names = ", ".join(composite_data.get("missing_tiers", []))
        st.info(f"ℹ️ **Cơ chế minh bạch dữ liệu:** Các tầng `{missing_names}` chưa có dữ liệu thực tế trong DB nên hệ thống đã **tự động tái phân bổ 100% trọng số** cho các tầng còn lại, loại trừ hoàn toàn số giả lập hardcoded.")

    st.success(f"💡 **Trạng thái thị trường chung:** `{composite_data['zone']}`. Điểm số phản ánh trung thực từ các nguồn dữ liệu đã kiểm định sạch.")

# 5. Cảnh báo Danh mục Lệnh Đang Nắm Giữ
st.markdown("---")
st.subheader("🚨 Cảnh Báo Danh Mục Lệnh Đang Nắm Giữ")

alerts = evaluate_portfolio_alerts()
if alerts:
    for al in alerts:
        render_alert_card(al)
else:
    st.success("Tất cả các vị thế trong danh mục đang nằm trong vùng an toàn, chưa chạm ngưỡng Stop Loss hoặc Target.")

# 6. Đồ thị Tổng Quan VN-Index (100% Log Scale)
st.markdown("---")
st.subheader(f"📉 Biểu Đồ Tổng Quan {vni_chart_title} (100% Log Scale)")
if df_1d_ind is not None and not df_1d_ind.empty:
    fig_vni = create_deep_dive_chart(df_1d_ind.tail(300), vni_chart_title, "1D")
    cfg_chart = getattr(fig_vni, '_config', {'modeBarButtonsToAdd': ['drawline', 'eraseshape'], 'scrollZoom': True})
    st.plotly_chart(fig_vni, width='stretch', config=cfg_chart)
else:
    st.info("Bấm [Đồng Bộ / Cập Nhật Database] ở thanh bên để tải dữ liệu lịch sử VN-Index.")
