"""
pages/6_Warrants_CW.py
Tầng 6 — Định Giá & Lọc Chứng Quyền (Black-Scholes & Greeks Engine)
- Tính toán Giá hợp lý (Fair Value), Implied Volatility (IV) bằng scipy.optimize.brentq
- Greeks chuyên sâu: Delta, Theta/ngày, Effective Gearing, Điểm hòa vốn (Breakeven)
- Ma trận mô phỏng lợi nhuận (Payoff Matrix) 21 kịch bản (+/-20%, bước 2%)
- Quy đổi đồng bộ toàn bộ đơn vị về VNĐ để loại trừ lỗi toán học
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from core.db_manager import get_connection, load_ohlcv
from core.black_scholes import (
    calculate_historical_volatility, analyze_warrant,
    generate_payoff_matrix
)

st.set_page_config(page_title="Tầng 6: Chứng Quyền Black-Scholes", page_icon="🎫", layout="wide")

st.title("🎫 TẦNG 6: ĐỊNH GIÁ & LỌC CHỨNG QUYỀN (BLACK-SCHOLES)")
st.caption("Khung định giá lý thuyết Call Warrant, bóc tách Implied Volatility, Greeks và mô phỏng Payoff Matrix")

# Quản lý danh sách Chứng quyền theo dõi
conn = get_connection()
try:
    cursor = conn.cursor()
    cursor.execute("SELECT cw_ticker, underlying, strike_price_vnd, maturity_date, conversion_ratio, last_price_vnd, issuer FROM warrants WHERE status = 'ACTIVE';")
    cw_rows = cursor.fetchall()
    seeded_demo = False

    if not cw_rows:
        # Nạp mẫu chứng quyền thực chiến
        seeded_demo = True
        today = date.today()
        sample_cws = [
            ("CFPT2501", "FPT", 115000.0, (today + timedelta(days=95)).strftime("%Y-%m-%d"), 2.0, 5200.0, "SSI"),
            ("CNLG2502", "NLG", 22000.0, (today + timedelta(days=120)).strftime("%Y-%m-%d"), 2.0, 1850.0, "HSC"),
            ("CKDH2501", "KDH", 14500.0, (today + timedelta(days=110)).strftime("%Y-%m-%d"), 2.0, 1100.0, "VND"),
            ("CHPG2503", "HPG", 26000.0, (today + timedelta(days=80)).strftime("%Y-%m-%d"), 3.0, 1250.0, "VPS")
        ]
        cursor.executemany("""
        INSERT OR REPLACE INTO warrants
        (cw_ticker, underlying, strike_price_vnd, maturity_date, conversion_ratio, last_price_vnd, issuer, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
        """, sample_cws)
        conn.commit()
        cursor.execute("SELECT cw_ticker, underlying, strike_price_vnd, maturity_date, conversion_ratio, last_price_vnd, issuer FROM warrants WHERE status = 'ACTIVE';")
        cw_rows = cursor.fetchall()
finally:
    conn.close()

cw_df = pd.DataFrame(cw_rows, columns=["cw_ticker", "underlying", "strike_price_vnd", "maturity_date", "conversion_ratio", "last_price_vnd", "issuer"])

if seeded_demo:
    st.warning("⚠️ Chưa có chứng quyền thật trong Local DB — bảng bên dưới là 4 CW MẪU để minh họa phương pháp định giá. "
               "Cần cập nhật giá thị trường và điều khoản thật trước khi ra quyết định đầu tư.")

st.subheader("📋 Bảng Tổng Hợp Chứng Quyền Đang Theo Dõi")

# Tính toán định giá cho tất cả CW
analyzed_list = []
for _, row in cw_df.iterrows():
    und = row["underlying"]
    # Tải giá cơ sở từ Local DB
    df_und = load_ohlcv(und)
    if df_und is not None and not df_und.empty:
        # Giá lưu ở kVND -> nhân 1000 để sang VNĐ
        s_vnd = float(df_und['close'].iloc[-1]) * 1000.0
        hv_60d = calculate_historical_volatility(df_und['close'])
    else:
        # Giá fallback
        defaults = {"FPT": 123300.0, "NLG": 21200.0, "KDH": 14000.0, "HPG": 25500.0}
        s_vnd = defaults.get(und, 25000.0)
        hv_60d = 0.32

    res = analyze_warrant(dict(row), stock_close_vnd=s_vnd, hv_60d=hv_60d, r=0.05)
    if res.get("status") == "ACTIVE":
        analyzed_list.append({
            "Mã CW": row["cw_ticker"],
            "Cơ Sở": und,
            "Giá Cơ Sở (VNĐ)": f"{s_vnd:,.0f}",
            "Giá Thực Hiện (K)": f"{row['strike_price_vnd']:,.0f}",
            "Tỷ Lệ Chuyển Đổi": f"{row['conversion_ratio']}:1",
            "Ngày Đáo Hạn": row["maturity_date"],
            "Còn lại (ngày)": res["days_to_maturity"],
            "Giá Thị Trường": f"{row['last_price_vnd']:,.0f}",
            "Giá Hợp Lý (BS)": f"{res['fair_price_vnd']:,.0f}",
            "Lệch Định Giá (%)": f"{res['diff_val_pct']:+.1f}%",
            "Định Giá": res["valuation_status"],
            "IV (%)": f"{res['iv_pct']}%" if res['iv_pct'] else "N/A",
            "Delta": res["delta"],
            "Effective Gearing": f"{res['effective_gearing']}x",
            "Hòa Vốn (Breakeven)": f"{res['breakeven_price']:,.0f}"
        })

if analyzed_list:
    st.dataframe(pd.DataFrame(analyzed_list), width='stretch')

st.markdown("---")

# --- PHẦN 2: DEEP DIVE & MA TRẬN PAYOFF ---
st.header("2. Phân Tích Chuyên Sâu & Ma Trận Mô Phỏng Lợi Nhuận (Payoff Matrix)")

selected_cw = st.selectbox("Chọn mã Chứng quyền để mô phỏng ma trận Payoff:", options=cw_df["cw_ticker"].tolist())
row_selected = cw_df[cw_df["cw_ticker"] == selected_cw].iloc[0]

# Tải thông số
und = row_selected["underlying"]
df_und = load_ohlcv(und)
s_vnd = float(df_und['close'].iloc[-1]) * 1000.0 if df_und is not None and not df_und.empty else 21200.0
k_vnd = float(row_selected["strike_price_vnd"])
cr_val = float(row_selected["conversion_ratio"])
m_val = float(row_selected["last_price_vnd"])

col_p1, col_p2, col_p3 = st.columns(3)
col_p1.metric("Giá Cổ Phiếu Cơ Sở (S)", f"{s_vnd:,.0f} VNĐ")
col_p2.metric("Giá Thực Hiện (K)", f"{k_vnd:,.0f} VNĐ")
col_p3.metric("Giá Thị Trường CW", f"{m_val:,.0f} VNĐ")

payoff_df = generate_payoff_matrix(s_vnd, k_vnd, cr_val, m_val, range_pct=0.20, step_pct=0.02)

st.subheader("📊 Ma Trận 21 Kịch Bản Biến Động Giá Cơ Sở (±20%, bước 2%)")
st.dataframe(payoff_df.rename(columns={
    "pct_change_stock": "% Biến Động Giá Cơ Sở",
    "stock_sim_price": "Giá Cơ Sở Mô Phỏng (VNĐ)",
    "cw_intrinsic_sim": "Giá Trị CW Lúc Đáo Hạn",
    "pnl_vnd": "Lãi/Lỗ Tuyệt Đối (VNĐ)",
    "pnl_pct": "Tỷ Suất Lợi Nhuận CW (%)"
}), width='stretch')
