"""
components/charts_plotly.py
Mô-đun dựng biểu đồ Plotly tương tác 100% Log Scale theo chuẩn chuyên nghiệp:
- Biểu đồ nến 4-Panel Subplots (Giá + MA/EMA/Pitchfork/Gann, RSI + Phân kỳ, MACD, Volume + MFI)
- Khóa cứng yaxis_type="log" trên cả 3 khung thời gian 1M -> 1W -> 1D
- Tích hợp Auto-Pitchfork 3 điểm (Bearish & Bullish) và Warning Lines
- Auto-Trendline và hiển thị các đường vẽ tay lưu trong SQLite
- Biểu đồ RRG 4 góc phần tư kèm đuôi xoay 8 kỳ
- Biểu đồ Tương quan Margin vs VN-Index và Đường cong Lợi suất FRED
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Bảng màu Dark Mode chuẩn Bloomberg/TradingView
COLORS = {
    "bg": "#0E1117",
    "paper": "#1E222D",
    "grid": "#2A2E39",
    "candle_up": "#00C853",
    "candle_down": "#FF5252",
    "ema21": "#29B6F6",
    "ema50": "#FFA726",
    "ema120": "#AB47BC",
    "ema200": "#EF5350",
    "ma200": "#FFD54F",
    "pitchfork_ml": "#FCC934",
    "pitchfork_l2": "#4CAF50",
    "pitchfork_l3": "#FF5252",
    "rsi": "#9C27B0",
    "macd": "#2196F3",
    "macd_signal": "#FF9800",
    "mfi": "#00E676"
}

def create_deep_dive_chart(df: pd.DataFrame, ticker: str, timeframe: str = "1D",
                           pitchfork_data: dict = None, trendlines: list = None,
                           user_drawings: list = None, rsi_divs: dict = None,
                           gann_fan: dict = None, gann_box: dict = None,
                           index_offset: int = 0) -> go.Figure:
    """
    Tạo biểu đồ Deep-Dive 4-panel chuyên sâu trên thang Logarit 100%:
    - Panel 1: Nến + MA/EMA + Pitchfork + Trendline + User Drawing + Gann
    - Panel 2: RSI(14) + Đánh dấu phân kỳ đỉnh/đáy
    - Panel 3: MACD(12, 26, 9) Line, Signal Line, Histogram
    - Panel 4: Khối lượng giao dịch + MFI(14)

    index_offset: số nến bị cắt ở đầu khi df là tail() của chuỗi đã dùng để
    tính Pitchfork/Trendline. Nhờ đó hình học tính trên toàn bộ lịch sử vẫn
    vẽ đúng trên cửa sổ hiển thị.
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", title=f"Chưa có dữ liệu cho {ticker}")
        return fig

    # 4 panels: Giá (55%), RSI (15%), MACD (15%), Volume/MFI (15%)
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        # Panel 4 dùng trục phụ (secondary y) cho MFI để không bị ép vào thang Volume
        specs=[[{"secondary_y": False}], [{"secondary_y": False}],
               [{"secondary_y": False}], [{"secondary_y": True}]],
        subplot_titles=(
            f"{ticker} ({timeframe}) - 100% Log Scale & MA/EMA/Pitchfork/Gann",
            "RSI(14) & Phân kỳ Đỉnh/Đáy",
            "MACD(12, 26, 9) & Histogram",
            "Khối lượng & MFI(14)"
        )
    )

    x_vals = df['date'] if 'date' in df.columns else df.index

    # --- PANEL 1: NẾN VÀ HÌNH HỌC ---
    fig.add_trace(
        go.Candlestick(
            x=x_vals,
            open=df['open'], high=df['high'], low=df['low'], close=df['close'],
            increasing_line_color=COLORS["candle_up"],
            decreasing_line_color=COLORS["candle_down"],
            name="OHLCV"
        ),
        row=1, col=1
    )

    # MA/EMA
    for ma_col, color, name in [
        ('ema21', COLORS['ema21'], 'EMA 21'),
        ('ema50', COLORS['ema50'], 'EMA 50'),
        ('ema120', COLORS['ema120'], 'EMA 120'),
        ('ema200', COLORS['ema200'], 'EMA 200'),
        ('ma200', COLORS['ma200'], 'MA 200')
    ]:
        if ma_col in df.columns:
            fig.add_trace(
                go.Scatter(x=x_vals, y=df[ma_col], mode='lines', line=dict(color=color, width=1.2), name=name),
                row=1, col=1
            )

    if 'ma_long_1m' in df.columns:
        lbl = df['ma_long_1m_type'].iloc[-1] if 'ma_long_1m_type' in df.columns else 'MA Long'
        fig.add_trace(
            go.Scatter(x=x_vals, y=df['ma_long_1m'], mode='lines', line=dict(color='#E040FB', width=2, dash='dot'), name=f"Hỗ trợ chu kỳ ({lbl})"),
            row=1, col=1
        )

    # Pitchfork lines (hỗ trợ 1 hoặc nhiều pitchfork: Bearish + Bullish)
    if pitchfork_data:
        pf_list = [pitchfork_data] if isinstance(pitchfork_data, dict) else list(pitchfork_data)
    else:
        pf_list = []
    for _pf in pf_list:
        t_eval = np.asarray(_pf.get('t_eval', []), dtype=int) - int(index_offset)
        if t_eval.size > 0:
            # Map index t_eval sang x_vals (giữ đúng căn chỉnh mảng, không cắt mù quáng)
            mask = (t_eval >= 0) & (t_eval < len(x_vals))
            if mask.any():
                x_pf = [x_vals.iloc[i] for i in t_eval[mask]]
                p_ml = np.asarray(_pf['p_ml'])[mask]
                p_l2 = np.asarray(_pf['p_l2'])[mask]
                p_l3 = np.asarray(_pf['p_l3'])[mask]

                mode_lbl = "Bearish" if _pf.get('mode') == 'bearish' else "Bullish"
                fig.add_trace(
                    go.Scatter(x=x_pf, y=p_ml, mode='lines', line=dict(color=COLORS['pitchfork_ml'], width=1.5, dash='dash'), name=f"Median Line ({mode_lbl})"),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=x_pf, y=p_l2, mode='lines', line=dict(color=COLORS['pitchfork_l2'], width=1.2), name=f"Biên dưới ({mode_lbl})"),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(x=x_pf, y=p_l3, mode='lines', line=dict(color=COLORS['pitchfork_l3'], width=1.2), name=f"Biên trên ({mode_lbl})"),
                    row=1, col=1
                )

    # Auto-Trendlines
    if trendlines:
        for tl in trendlines:
            t_eval = np.asarray(tl['t_eval'], dtype=int) - int(index_offset)
            mask = (t_eval >= 0) & (t_eval < len(x_vals))
            if mask.any():
                x_tl = [x_vals.iloc[i] for i in t_eval[mask]]
                p_tl = np.asarray(tl['price_eval'])[mask]
                fig.add_trace(
                    go.Scatter(x=x_tl, y=p_tl, mode='lines', line=dict(color=tl['color'], width=1.2, dash='dot'), name=f"Trendline {tl['type']}"),
                    row=1, col=1
                )

    # User drawings from SQLite
    if user_drawings:
        for ud in user_drawings:
            fig.add_trace(
                go.Scatter(
                    x=[ud['date_1'], ud['date_2']],
                    y=[ud['price_1'], ud['price_2']],
                    mode='lines+text',
                    text=[ud.get('label', ''), ''],
                    line=dict(color=ud.get('color', '#FCC934'), width=2),
                    name=f"Vẽ tay: {ud.get('label', 'Line')}"
                ),
                row=1, col=1
            )

    # Gann Fan
    if gann_fan and 'lines' in gann_fan:
        t_eval = np.asarray(gann_fan.get('t_eval', []), dtype=int)
        mask = (t_eval >= 0) & (t_eval < len(x_vals))
        if mask.any():
            x_gann = [x_vals.iloc[i] for i in t_eval[mask]]
            for r_name, p_line in gann_fan['lines'].items():
                p_sub = np.asarray(p_line)[mask]
                fig.add_trace(
                    go.Scatter(x=x_gann, y=p_sub, mode='lines', line=dict(color="#B388FF", width=1, dash='dashdot'), name=f"Gann Fan {r_name}"),
                    row=1, col=1
                )

    # --- PANEL 2: RSI(14) ---
    if 'rsi' in df.columns:
        fig.add_trace(
            go.Scatter(x=x_vals, y=df['rsi'], mode='lines', line=dict(color=COLORS['rsi'], width=1.5), name="RSI(14)"),
            row=2, col=1
        )
        # Đường ngưỡng 30 và 70
        fig.add_hline(y=70, line=dict(color="red", width=1, dash="dot"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="green", width=1, dash="dot"), row=2, col=1)

        # Chú thích phân kỳ
        if rsi_divs:
            for b_div in rsi_divs.get('bullish', []):
                fig.add_annotation(
                    x=b_div['date_2'], y=b_div['rsi2'],
                    text="Phân kỳ Dương", showarrow=True, arrowhead=1, arrowcolor="#00C853",
                    font=dict(color="#00C853", size=10), row=2, col=1
                )
            for b_div in rsi_divs.get('bearish', []):
                fig.add_annotation(
                    x=b_div['date_2'], y=b_div['rsi2'],
                    text="Phân kỳ Âm", showarrow=True, arrowhead=1, arrowcolor="#FF5252",
                    font=dict(color="#FF5252", size=10), row=2, col=1
                )

    # --- PANEL 3: MACD ---
    if 'macd' in df.columns:
        fig.add_trace(
            go.Scatter(x=x_vals, y=df['macd'], mode='lines', line=dict(color=COLORS['macd'], width=1.5), name="MACD"),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(x=x_vals, y=df['macd_signal'], mode='lines', line=dict(color=COLORS['macd_signal'], width=1.2), name="Signal"),
            row=3, col=1
        )
        # Histogram
        hist_colors = [COLORS['candle_up'] if v >= 0 else COLORS['candle_down'] for v in df['macd_hist']]
        fig.add_trace(
            go.Bar(x=x_vals, y=df['macd_hist'], marker_color=hist_colors, name="Histogram"),
            row=3, col=1
        )

    # --- PANEL 4: VOLUME & MFI ---
    if 'volume' in df.columns:
        vol_colors = []
        vol_ratio = df.get('vol_ratio', pd.Series(1.0, index=df.index))
        for vr, c_val, o_val in zip(vol_ratio, df['close'], df['open']):
            if vr >= 1.8:
                vol_colors.append("#FFD600")  # Bùng nổ khối lượng
            elif c_val >= o_val:
                vol_colors.append("rgba(0, 200, 83, 0.5)")
            else:
                vol_colors.append("rgba(255, 82, 82, 0.5)")

        fig.add_trace(
            go.Bar(x=x_vals, y=df['volume'], marker_color=vol_colors, name="Volume"),
            row=4, col=1
        )

    if 'mfi' in df.columns:
        fig.add_trace(
            go.Scatter(x=x_vals, y=df['mfi'], mode='lines', line=dict(color=COLORS['mfi'], width=1.5), name="MFI(14)"),
            row=4, col=1, secondary_y=True
        )

    # Khóa cứng 100% LOG SCALE cho Panel 1
    fig.update_yaxes(type="log", row=1, col=1, title_text="Giá (Log kVND)")
    fig.update_yaxes(range=[0, 100], row=2, col=1, title_text="RSI")
    fig.update_yaxes(row=3, col=1, title_text="MACD")
    fig.update_yaxes(row=4, col=1, title_text="Volume")
    fig.update_yaxes(range=[0, 100], row=4, col=1, secondary_y=True,
                     title_text="MFI", showgrid=False)

    fig.update_layout(
        template="plotly_dark",
        height=850,
        margin=dict(l=50, r=30, t=50, b=30),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    fig._config = {'modeBarButtonsToAdd': ['drawline', 'eraseshape'], 'scrollZoom': True}
    return fig

def create_rrg_plot(rrg_results: dict) -> go.Figure:
    """Biểu đồ Relative Rotation Graph (RRG) 4 góc phần tư."""
    fig = go.Figure()

    # Thêm 4 góc phần tư nền
    fig.add_shape(type="rect", x0=100, y0=100, x1=125, y1=125, fillcolor="rgba(0, 200, 83, 0.08)", line_width=0)
    fig.add_shape(type="rect", x0=100, y0=75, x1=125, y1=100, fillcolor="rgba(255, 214, 0, 0.08)", line_width=0)
    fig.add_shape(type="rect", x0=75, y0=75, x1=100, y1=100, fillcolor="rgba(213, 0, 0, 0.08)", line_width=0)
    fig.add_shape(type="rect", x0=75, y0=100, x1=100, y1=125, fillcolor="rgba(41, 121, 255, 0.08)", line_width=0)

    # Trục trung tâm 100
    fig.add_hline(y=100, line=dict(color="#424242", width=1.5, dash="dash"))
    fig.add_vline(x=100, line=dict(color="#424242", width=1.5, dash="dash"))

    for name, item in rrg_results.items():
        tail = item.get("tail", [])
        if not tail:
            continue
        xs = [p["rs_ratio"] for p in tail]
        ys = [p["rs_momentum"] for p in tail]

        # Đuôi RRG
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='lines',
            line=dict(color=item['color'], width=1.2),
            showlegend=False
        ))

        # Điểm đầu mới nhất
        fig.add_trace(go.Scatter(
            x=[xs[-1]], y=[ys[-1]],
            mode='markers+text',
            marker=dict(size=10, color=item['color']),
            text=[name],
            textposition="top right",
            name=f"{name} ({item['quadrant']})"
        ))

    fig.update_layout(
        template="plotly_dark",
        title="Biểu đồ Luân chuyển Tương đối RRG (12W Window, Đuôi 8 Kỳ vs VN-Index)",
        xaxis=dict(title="RS-Ratio (Xu hướng tương đối)", range=[85, 115]),
        yaxis=dict(title="RS-Momentum (Đà tương đối)", range=[85, 115]),
        height=650,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2)
    )

    return fig

def create_margin_correlation_chart(margin_df: pd.DataFrame) -> go.Figure:
    """Biểu đồ tương quan Dư nợ Margin toàn thị trường vs VN-Index (2000 - 2026)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=margin_df['quarter'], y=margin_df['total_margin_bn'],
            name="Dư nợ Margin (Tỷ VNĐ)",
            marker_color="rgba(41, 98, 255, 0.6)"
        ),
        secondary_y=False
    )

    if 'vnindex_close' in margin_df.columns:
        fig.add_trace(
            go.Scatter(
                x=margin_df['quarter'], y=margin_df['vnindex_close'],
                name="VN-Index Đóng cửa Quý",
                mode='lines+markers',
                line=dict(color="#FFD600", width=2)
            ),
            secondary_y=True
        )

    fig.update_layout(
        template="plotly_dark",
        title="Tương quan Dư Nợ Margin Toàn Thị Trường vs Đỉnh/Đáy VN-Index",
        height=500
    )
    fig.update_yaxes(title_text="Dư nợ Margin (Tỷ VNĐ)", secondary_y=False)
    fig.update_yaxes(title_text="Điểm số VN-Index", secondary_y=True)

    return fig

def create_yield_curve_chart(yield_df: pd.DataFrame) -> go.Figure:
    """Biểu đồ Đường cong Lợi suất Trái phiếu Mỹ FRED (T10Y2Y)."""
    fig = go.Figure()

    if yield_df is not None and not yield_df.empty:
        fig.add_trace(go.Scatter(
            x=yield_df['date'], y=yield_df['t10y2y'],
            mode='lines',
            line=dict(color="#29B6F6", width=1.5),
            name="T10Y2Y (10Y - 2Y Spread %)"
        ))

        fig.add_hline(y=0.0, line=dict(color="red", width=1.5, dash="dash"))

    fig.update_layout(
        template="plotly_dark",
        title="Đường cong Lợi suất Trái phiếu Chính phủ Mỹ FRED (T10Y2Y Spread)",
        yaxis_title="Lợi suất Chênh lệch (%)",
        height=450
    )
    return fig
