"""
pages/4_Derivatives_Breadth.py
Tầng 4 — Phái sinh & Độ Rộng Thị Trường (Trọng số 10%)
- Biểu đồ VN30F1M, Độ lệch Basis (VN30F1M - VN30) và Open Interest (OI)
- Độ rộng thị trường (Market Breadth) tính hoàn toàn từ Local DB:
  + % Cổ phiếu nằm trên đường trung bình MA50
  + % Cổ phiếu nằm trên đường trung bình MA200
  + Đường Advance/Decline (A/D Line) tích lũy
- Tính toán điểm tự động Tầng 4 kèm cơ chế tái phân bổ trọng số khi OI là NULL
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config.tickers import TIER_1_UNIVERSE
from core.db_manager import load_ohlcv, get_connection
from core.indicators import calculate_mas
from core.scoring_engine import score_tier4_derivatives_breadth

st.set_page_config(page_title="Tầng 4: Phái sinh & Độ rộng", page_icon="⚡", layout="wide")

st.title("⚡ TẦNG 4: PHÁI SINH & ĐỘ RỘNG THỊ TRƯỜNG")
st.caption("Khung phân tích vị thế phái sinh, độ lệch Basis, biến động OI và sức khỏe nội tại độ rộng thị trường (Market Breadth)")

# --- TÍNH TOÁN ĐỘ RỘNG TỪ LOCAL DB ---
stocks_above_ma50 = 0
stocks_above_ma200 = 0
total_stocks_evaluated = 0
advances = 0
declines = 0

for t in TIER_1_UNIVERSE[:60]: # Quét 60 mã thanh khoản lớn
    df = load_ohlcv(t)
    if df is not None and len(df) >= 50:
        df_mas = calculate_mas(df)
        last_row = df_mas.iloc[-1]
        c = last_row['close']
        ma50 = last_row.get('ma50', c)
        ma200 = last_row.get('ma200', c)
        if c > ma50:
            stocks_above_ma50 += 1
        if pd.notna(ma200) and c > ma200:
            stocks_above_ma200 += 1
        if len(df_mas) >= 2:
            if c > df_mas.iloc[-2]['close']:
                advances += 1
            elif c < df_mas.iloc[-2]['close']:
                declines += 1
        total_stocks_evaluated += 1

pct_ma50 = (stocks_above_ma50 / total_stocks_evaluated * 100.0) if total_stocks_evaluated > 0 else None
pct_ma200 = (stocks_above_ma200 / total_stocks_evaluated * 100.0) if total_stocks_evaluated > 0 else None
ad_slope = ((advances - declines) / total_stocks_evaluated) if total_stocks_evaluated > 0 else None

# --- TẢI PHÁI SINH VÀ SPOT TỪ LOCAL DB (KHÔNG DÙNG DỮ LIỆU MÔ PHỎNG) ---
conn = get_connection()
try:
    df_future = pd.read_sql_query("""
        SELECT date, COALESCE(settlement_price, close) AS future_close, oi
        FROM derivatives_daily
        WHERE ticker = 'VN30F1M'
        ORDER BY date ASC;
    """, conn)
finally:
    conn.close()
df_vn30 = load_ohlcv('VN30')
if not df_future.empty:
    df_future['date'] = pd.to_datetime(df_future['date'])
if df_vn30 is not None and not df_vn30.empty:
    df_spot = df_vn30[['date', 'close']].rename(columns={'close': 'spot_close'}).copy()
    df_spot['date'] = pd.to_datetime(df_spot['date'])
    df_deriv = df_future.merge(df_spot, on='date', how='inner')
else:
    df_deriv = pd.DataFrame(columns=['date', 'future_close', 'oi', 'spot_close'])

real_basis = None
real_oi_trend = None
if not df_deriv.empty:
    df_deriv['basis'] = df_deriv['future_close'] - df_deriv['spot_close']
    real_basis = float(df_deriv.iloc[-1]['basis'])
if len(df_future) >= 2:
    last = df_future.iloc[-1]
    prev = df_future.iloc[-2]
    if pd.notna(last['future_close']) and pd.notna(prev['future_close']) and pd.notna(last['oi']) and pd.notna(prev['oi']):
        oi_direction = 'UP' if last['oi'] >= prev['oi'] else 'DOWN'
        price_direction = 'UP' if last['future_close'] >= prev['future_close'] else 'DOWN'
        real_oi_trend = f'OI_{oi_direction}_PRICE_{price_direction}'

# --- TÍNH ĐIỂM TẦNG 4 ---
t4_data = {
    "basis": real_basis,
    "pct_above_ma50": pct_ma50,
    "ad_slope": ad_slope,
    "oi_trend": real_oi_trend
}
t4_res = score_tier4_derivatives_breadth(t4_data)

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
col_s1.metric("Điểm Tầng 4 (Phái sinh & Độ rộng)", f"{t4_res['score']:.1f}/100" if t4_res['score'] is not None else "Chưa đủ dữ liệu")
col_s2.metric("Độ lệch Basis (VN30F - VN30)", f"{real_basis:+.1f} điểm" if real_basis is not None else "Chưa có", f"{t4_res['details'].get('basis', 0):.0f} điểm" if 'basis' in t4_res['details'] else None)
col_s3.metric("% Cổ phiếu > MA50", f"{pct_ma50:.1f}%" if pct_ma50 is not None else "Chưa có", f"{t4_res['details'].get('breadth50', 0):.0f} điểm" if 'breadth50' in t4_res['details'] else None)
col_s4.metric("Độ dốc Đường A/D", f"{ad_slope:+.2f}" if ad_slope is not None else "Chưa có", f"{t4_res['details'].get('ad_slope', 0):.0f} điểm" if 'ad_slope' in t4_res['details'] else None)

st.markdown("---")

# --- PHẦN 1: ĐỘ RỘNG THỊ TRƯỜNG ---
st.header("1. Sức Khỏe Nội Tại & Độ Rộng Thị Trường (Market Breadth)")

col_b1, col_b2 = st.columns(2)
with col_b1:
    if pct_ma50 is None:
        st.info("Chưa đủ dữ liệu OHLCV để tính độ rộng MA50.")
    else:
        fig_gauge_ma50 = go.Figure(go.Indicator(
            mode="gauge+number", value=pct_ma50,
            title={'text': "<b>% Cổ Phiếu Nằm Trên MA50</b>"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00C853" if pct_ma50 >= 50 else "#FF5252"}}
        ))
        fig_gauge_ma50.update_layout(template="plotly_dark", height=280)
        st.plotly_chart(fig_gauge_ma50, width='stretch')

with col_b2:
    if pct_ma200 is None:
        st.info("Chưa đủ dữ liệu OHLCV để tính độ rộng MA200.")
    else:
        fig_gauge_ma200 = go.Figure(go.Indicator(
            mode="gauge+number", value=pct_ma200,
            title={'text': "<b>% Cổ Phiếu Nằm Trên MA200</b>"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#2979FF" if pct_ma200 >= 50 else "#FF5252"}}
        ))
        fig_gauge_ma200.update_layout(template="plotly_dark", height=280)
        st.plotly_chart(fig_gauge_ma200, width='stretch')

st.markdown("---")

# --- PHẦN 2: PHÁI SINH VN30F & BASIS ---
st.header("2. Hợp Đồng Tương Lai VN30F1M & Basis")

if df_deriv.empty:
    st.info("Chưa có đủ dữ liệu VN30F1M và VN30 cùng ngày trong Local DB để tính basis/OI. Đồng bộ dữ liệu trước khi xem biểu đồ.")
else:
    fig_deriv = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        specs=[[{}], [{'secondary_y': True}]],
        subplot_titles=("Giá HĐTL VN30F1M vs Chỉ Số Cơ Sở VN30", "Độ Lệch Basis (VN30F - VN30) & Khối Lượng Mở (OI)")
    )
    fig_deriv.add_trace(go.Scatter(x=df_deriv['date'], y=df_deriv['future_close'], mode='lines', name='VN30F1M'), row=1, col=1)
    fig_deriv.add_trace(go.Scatter(x=df_deriv['date'], y=df_deriv['spot_close'], mode='lines', name='VN30 Index'), row=1, col=1)
    fig_deriv.add_trace(go.Bar(x=df_deriv['date'], y=df_deriv['basis'], name='Basis'), row=2, col=1, secondary_y=False)
    fig_deriv.add_trace(go.Scatter(x=df_deriv['date'], y=df_deriv['oi'], mode='lines', name='Open Interest (OI)'), row=2, col=1, secondary_y=True)
    fig_deriv.update_layout(template="plotly_dark", height=600, showlegend=True)
    st.plotly_chart(fig_deriv, width='stretch')
