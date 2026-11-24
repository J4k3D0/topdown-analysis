"""
components/ui_cards.py
Các thành phần giao diện trực quan cho Streamlit:
- Đồng hồ đo Top-Down Composite Score (Plotly Gauge Indicator với 4 vùng màu)
- Banner cảnh báo lịch giao dịch VN-Index (VNIndexCalendarGuard)
- Thẻ cảnh báo danh mục nắm giữ (Portfolio Alert Badges)
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import date
from config.vn_holidays import get_expected_last_trading_day

def render_topdown_gauge(score_data: dict) -> go.Figure:
    """Tạo đồng hồ đo Top-Down Composite Score (0 - 100) dạng Plotly Gauge."""
    score = score_data.get("composite_score", 50.0)
    zone = score_data.get("zone", "Neutral")
    color = score_data.get("color", "#FF9500")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>TOP-DOWN COMPOSITE SCORE</b><br><span style='font-size:14px;color:{color}'>{zone.upper()}</span>", 'font': {'size': 18}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#FFFFFF"},
            'bar': {'color': color, 'thickness': 0.3},
            'bgcolor': "#1E222D",
            'borderwidth': 2,
            'bordercolor': "#2A2E39",
            'steps': [
                {'range': [0, 30], 'color': "rgba(255, 59, 48, 0.3)"},
                {'range': [30, 50], 'color': "rgba(255, 149, 0, 0.3)"},
                {'range': [50, 70], 'color': "rgba(52, 199, 89, 0.3)"},
                {'range': [70, 100], 'color': "rgba(0, 122, 255, 0.3)"}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 3},
                'thickness': 0.8,
                'value': score
            }
        }
    ))

    fig.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=30, r=30, t=60, b=20)
    )
    return fig

def render_db_calendar_guard(db_max_date_str: str = None) -> bool:
    """
    Kiểm tra tính kịp thời của dữ liệu trong Local DB so với phiên VN-Index gần nhất:
    - Nếu DB rỗng -> báo lỗi đỏ, yêu cầu khởi tạo.
    - Nếu DB chậm hơn ngày giao dịch kỳ vọng -> hiện banner vàng cảnh báo.
    - Trả về True nếu dữ liệu hoàn toàn cập nhật.
    """
    expected_dt = get_expected_last_trading_day()
    expected_str = expected_dt.strftime("%Y-%m-%d")

    if not db_max_date_str:
        st.error("⚠️ **CẢNH BÁO:** Cơ sở dữ liệu cục bộ (`quant_local.db`) chưa có dữ liệu. Vui lòng bấm nút **'Cập nhật Database'** bên dưới trước khi phân tích hoặc quét mã!")
        return False

    db_dt = None
    try:
        db_dt = date.fromisoformat(str(db_max_date_str)[:10])
    except Exception:
        pass

    if db_dt and db_dt < expected_dt:
        st.warning(
            f"⚠️ **CẢNH BÁO LỆCH LỊCH VN-INDEX:** Dữ liệu trong Database đang dừng ở ngày **{db_max_date_str}**, "
            f"chậm hơn phiên giao dịch gần nhất của VN-Index (**{expected_str}**). "
            f"Vui lòng bấm **[Đồng Bộ / Cập Nhật Database]** để đảm bảo tín hiệu chính xác nhất!"
        )
        return False
    else:
        st.success(f"✅ Dữ liệu Database đang cập nhật phiên mới nhất: **{db_max_date_str}**")
        return True

def render_alert_card(alert: dict):
    """Hiển thị thẻ cảnh báo cho từng vị thế trong danh mục."""
    level = alert.get("alert_level")
    ticker = alert.get("ticker")
    pnl = alert.get("pnl_pct", 0.0)
    msg = alert.get("action_msg", "")
    badge = alert.get("badge_text", "")

    pnl_str = f"+{pnl:.2f}%" if pnl > 0 else f"{pnl:.2f}%"

    if level == "STOP":
        st.error(f"**{badge}** | **{ticker}** (Lãi/Lỗ: `{pnl_str}`) — {msg}")
    elif level == "TARGET_2":
        st.success(f"**{badge}** | **{ticker}** (Lãi/Lỗ: `{pnl_str}`) — {msg}")
    elif level == "TARGET_1":
        st.warning(f"**{badge}** | **{ticker}** (Lãi/Lỗ: `{pnl_str}`) — {msg}")
    else:
        st.info(f"**{badge}** | **{ticker}** (Lãi/Lỗ: `{pnl_str}`) — {msg}")
