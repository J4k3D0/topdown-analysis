"""
core/portfolio_alerts.py
Động cơ cảnh báo tự động cho danh mục lệnh đang nắm giữ (Auto-Alert Engine):
- Quét đối chiếu giá đóng cửa mới nhất trong Local DB với các mốc Stop Loss, Trailing Stop, Target 1, Target 2
- Máy trạng thái ưu tiên phân biệt rõ ràng giữa OPEN và PARTIAL (chống phát lặp cờ Target 1 khi đã chốt 50%)
- Gợi ý nâng Trailing Stop theo EMA21/MA50(1D) khi vị thế đang gồng lãi an toàn
"""

import pandas as pd
from core.db_manager import get_trade_journal, load_ohlcv
from core.indicators import calculate_mas

def evaluate_portfolio_alerts() -> list:
    """
    Quét toàn bộ các lệnh có trạng thái 'OPEN' và 'PARTIAL' trong bảng trade_journal
    và sinh cờ cảnh báo trực quan tương ứng.
    """
    # Lấy các lệnh chưa đóng
    df_journal = get_trade_journal()
    if df_journal is None or df_journal.empty:
        return []

    active_trades = df_journal[df_journal['status'].isin(['OPEN', 'PARTIAL'])].copy()
    if active_trades.empty:
        return []

    alerts = []
    for _, trade in active_trades.iterrows():
        ticker = trade['ticker']
        entry_p = float(trade['entry_price'])
        stop_p = float(trade['stop_loss']) if pd.notna(trade['stop_loss']) else 0.0
        trail_p = float(trade['trailing_stop']) if pd.notna(trade['trailing_stop']) else 0.0
        tgt1_p = float(trade['target_1']) if pd.notna(trade['target_1']) else 999999.0
        tgt2_p = float(trade['target_2']) if pd.notna(trade['target_2']) else 999999.0
        status = trade['status']

        # Tải giá đóng cửa mới nhất từ Local DB
        df_stock = load_ohlcv(ticker)
        if df_stock is None or df_stock.empty:
            continue

        df_mas = calculate_mas(df_stock)
        last_row = df_mas.iloc[-1]
        p_last = float(last_row['close'])
        ema21 = float(last_row.get('ema21', p_last))
        ma50 = float(last_row.get('ma50', p_last))

        if status == 'PARTIAL':
            ep1 = float(trade['exit_price_1']) if pd.notna(trade.get('exit_price_1')) else entry_p
            pnl_pct = (0.5 * ((ep1 - entry_p) / entry_p) + 0.5 * ((p_last - entry_p) / entry_p)) * 100.0
        else:
            pnl_pct = ((p_last - entry_p) / entry_p) * 100.0

        effective_stop = max(stop_p, trail_p)

        # 1. Ưu tiên 1 (Cả OPEN và PARTIAL): Chạm Stop Loss / Trailing Stop
        if p_last <= effective_stop:
            alerts.append({
                "trade_id": trade['id'],
                "ticker": ticker,
                "status": status,
                "alert_level": "STOP",
                "badge_color": "red",
                "badge_text": "🔴 CHẠM STOP / TRAILING STOP",
                "p_last": p_last,
                "entry_price": entry_p,
                "trigger_price": effective_stop,
                "pnl_pct": round(pnl_pct, 2),
                "action_msg": f"Giá hiện tại {p_last:.2f} đã chạm ngưỡng cắt/bảo vệ vốn {effective_stop:.2f}. Khuyến nghị đóng vị thế!"
            })

        # 2. Ưu tiên 2 (Cả OPEN và PARTIAL): Chạm Target 2
        elif p_last >= tgt2_p:
            alerts.append({
                "trade_id": trade['id'],
                "ticker": ticker,
                "status": status,
                "alert_level": "TARGET_2",
                "badge_color": "green",
                "badge_text": "🟢 CHẠM TARGET 2 — CHỐT PHẦN CÒN LẠI",
                "p_last": p_last,
                "entry_price": entry_p,
                "trigger_price": tgt2_p,
                "pnl_pct": round(pnl_pct, 2),
                "action_msg": f"Giá hiện tại {p_last:.2f} đã đạt mục tiêu Target 2 ({tgt2_p:.2f}). Khuyến nghị chốt lời toàn bộ!"
            })

        # 3. Ưu tiên 3 (CHỈ ÁP DỤNG KHI status == 'OPEN'): Chạm Target 1
        elif status == 'OPEN' and p_last >= tgt1_p:
            alerts.append({
                "trade_id": trade['id'],
                "ticker": ticker,
                "status": status,
                "alert_level": "TARGET_1",
                "badge_color": "yellow",
                "badge_text": "🟡 CHẠM TARGET 1 — CHỐT 50%",
                "p_last": p_last,
                "entry_price": entry_p,
                "trigger_price": tgt1_p,
                "pnl_pct": round(pnl_pct, 2),
                "action_msg": f"Giá hiện tại {p_last:.2f} đã chạm Target 1 ({tgt1_p:.2f}). Thực hiện quy tắc Scaling-Out chốt 50%!"
            })

        # 4. Trạng thái bình thường: Đang gồng lãi an toàn
        else:
            suggest_trail = max(trail_p, ema21, ma50) if p_last > entry_p else trail_p
            alerts.append({
                "trade_id": trade['id'],
                "ticker": ticker,
                "status": status,
                "alert_level": "SAFE",
                "badge_color": "blue",
                "badge_text": "🔵 ĐANG GỒNG LÃI AN TOÀN" if pnl_pct >= 0 else "⚪ VỊ THẾ BÌNH THƯỜNG",
                "p_last": p_last,
                "entry_price": entry_p,
                "trigger_price": effective_stop,
                "pnl_pct": round(pnl_pct, 2),
                "action_msg": f"Lãi/lỗ hiện tại: {pnl_pct:+.2f}%. Gợi ý dời Trailing Stop lên vùng {suggest_trail:.2f} (dưới EMA21/MA50)."
            })

    return alerts
