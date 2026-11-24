"""
core/screener.py
Bộ lọc định lượng cổ phiếu siêu tốc độc quyền trên SQLite Local Database:
- Lớp lọc An toàn Bảng cân đối (Balance Sheet Gatekeeper): P/B <= 1.3, Nợ/VCSH < 1.2 (miễn trừ Tài chính), Thanh khoản >= 15 tỷ
- Preset 1: Bắt đáy Chu kỳ (mẫu thực chiến KDH & NLG)
- Preset 2: Breakout Bearish Pitchfork (Bứt phá kênh giảm nến Tuần 1W)
- Preset 3: Uptrend Pullback (Điều chỉnh lành mạnh kiểm định EMA21 nến Ngày 1D)
"""

import logging
import numpy as np
import pandas as pd
from core.db_manager import load_ohlcv, get_connection
from core.indicators import resample_ohlcv, calculate_all_indicators, detect_rsi_divergence
from core.geometry_log import compute_bearish_pitchfork, compute_bullish_pitchfork
from config.settings import PRESET_2_PARAMS, PRESET_3_PARAMS
from config.tickers import FINANCIAL_TICKERS

logger = logging.getLogger(__name__)

_MARKET_REGIME_CACHE = {}


def get_market_regime(force_reload: bool = False) -> dict:
    """
    Chế độ thị trường chung (Top-Down Layer 1) từ VN-Index nến ngày:
    - ok          : (VNI Close >= VNI EMA50 * 0.98) OR (VNI RSI14 >= 46)   [Baseline]
    - ok_enhanced : (VNI Close >= VNI EMA50 * 0.995) OR (VNI RSI14 >= 48)  [Bộ lọc tối ưu]
    Nếu chưa có dữ liệu VN-Index, trả về ok=True kèm cờ thiếu dữ liệu để không
    chặn oan tín hiệu (hệ thống không bịa xu hướng).
    """
    if not force_reload and 'data' in _MARKET_REGIME_CACHE:
        return _MARKET_REGIME_CACHE['data']

    res = {"ok": True, "close": None, "ema50": None, "rsi": None, "available": False}
    try:
        df_vni = load_ohlcv("VNINDEX")
        if df_vni is not None and len(df_vni) >= 60:
            ind = calculate_all_indicators(df_vni, is_monthly=False)
            last = ind.iloc[-1]
            c = float(last['close'])
            e50 = float(last.get('ema50', c))
            rsi = float(last.get('rsi', 50.0))
            ok_std = bool((c >= e50 * 0.98) or (rsi >= 46.0))
            ok_enh = bool((c >= e50 * 0.995) or (rsi >= 48.0))
            res.update({
                "ok": ok_std,
                "ok_enhanced": ok_enh,
                "close": round(c, 2),
                "ema50": round(e50, 2),
                "rsi": round(rsi, 1),
                "available": True,
            })
    except Exception:
        logger.exception("Không tính được chế độ thị trường VN-Index")

    _MARKET_REGIME_CACHE['data'] = res
    return res

def check_balance_sheet_gatekeeper(ticker: str, fundamentals_df: pd.DataFrame, avg_val_20p: float, is_financial: bool = False) -> tuple[bool, dict]:
    """
    Kiểm tra 3 tiêu chí an toàn bảng cân đối:
    1. Thanh khoản thực: GTGD 20 phiên >= 15 tỷ VNĐ/phiên
    2. Đòn bẩy an toàn: Nợ/VCSH < 1.2 (Miễn trừ hoàn toàn cho nhóm Tài chính)
    3. Định giá P/B <= 1.3 (Ưu tiên P/B < 1.0)
    """
    # 1. Thanh khoản
    pass_liquidity = (avg_val_20p >= 15.0)

    # Nếu thiếu dữ liệu BCTC trong DB -> trả về trạng thái thiếu để UI hiển thị cờ FUNDAMENTAL_MISSING
    if fundamentals_df is None or fundamentals_df.empty:
        return pass_liquidity, {
            "pass_all": pass_liquidity,
            "status": "FUNDAMENTAL_MISSING",
            "pb": None,
            "debt_to_equity": None,
            "avg_liquidity": avg_val_20p
        }

    latest_f = fundamentals_df.iloc[-1]
    pb = latest_f.get("pb", np.nan)
    de = latest_f.get("debt_to_equity", np.nan)

    pass_pb = True
    if pd.notna(pb):
        pass_pb = (pb <= 1.3)

    pass_de = True
    if not is_financial and pd.notna(de):
        pass_de = (de < 1.2)

    pass_all = pass_liquidity and pass_pb and pass_de
    return pass_all, {
        "pass_all": pass_all,
        "status": "OK" if pass_all else "FAILED",
        "pb": round(float(pb), 2) if pd.notna(pb) else None,
        "debt_to_equity": round(float(de), 2) if pd.notna(de) else None,
        "avg_liquidity": round(float(avg_val_20p), 2)
    }

def scan_stock(ticker: str, preset: str = "preset_1", swing_order: int = 5, use_enhancements: bool = False) -> dict:
    """Quét 1 mã cổ phiếu từ Local DB theo Preset định sẵn (hỗ trợ chế độ Tối Ưu Hóa Dữ Liệu Lịch Sử)."""
    df_1d = load_ohlcv(ticker)
    if df_1d is None or len(df_1d) < 30:
        return None

    df_1d_ind = calculate_all_indicators(df_1d, is_monthly=False)
    last_1d = df_1d_ind.iloc[-1]
    c_1d = float(last_1d['close'])
    o_1d = float(last_1d['open'])

    # Tính thanh khoản 20 phiên (tỷ VNĐ): close_kVND * volume / 1e6
    recent_20 = df_1d_ind.tail(20)
    avg_liquidity = float((recent_20['close'] * recent_20['volume'] / 1e6).mean())

    is_fin = (ticker in FINANCIAL_TICKERS)

    # Tải fundamentals nếu có
    conn = get_connection()
    fund_df = pd.read_sql_query(
        "SELECT * FROM fundamentals WHERE ticker = ? ORDER BY quarter ASC;",
        conn, params=[ticker]
    )
    conn.close()

    gate_pass, gate_info = check_balance_sheet_gatekeeper(ticker, fund_df, avg_liquidity, is_financial=is_fin)

    # --- Preset 1: Bắt đáy Chu kỳ (mẫu KDH / NLG) ---
    if preset == "preset_1":
        # Yêu cầu khung 1M
        df_1m = resample_ohlcv(df_1d, "1M")
        if len(df_1m) < 6:
            return None

        df_1m_ind = calculate_all_indicators(df_1m, is_monthly=True)
        last_1m = df_1m_ind.iloc[-1]
        prev_1m = df_1m_ind.iloc[-2]

        ma_long = last_1m.get('ma_long_1m', c_1d)
        if pd.isna(ma_long) or ma_long <= 0:
            ma_long = c_1d

        # Điều kiện 1: Giá nằm trong biên độ +/- 10% quanh MA_long_1M
        dist_pct = abs(c_1d - ma_long) / ma_long * 100.0
        cond_ma = (dist_pct <= 10.0)

        # Điều kiện 2: Fisher(9, 1M) < -1.8 và đang bẻ ngang hoặc cắt lên
        fisher_1m = last_1m.get('fisher', 0.0)
        fisher_1m_prev = prev_1m.get('fisher', 0.0)
        cond_fisher = (fisher_1m < -1.8) and (fisher_1m >= fisher_1m_prev - 0.05)

        # Điều kiện BẮT BUỘC (Baseline MTF - AGENTS.md §4.6): Xác nhận nến ngày
        # Nến ngày xanh (Close >= Open), RSI >= 30, và có Vol_Ratio >= 1.25 hoặc Fisher cắt lên
        rsi_1d = float(last_1d.get('rsi', 50.0))
        vol_r_1d = float(last_1d.get('vol_ratio', 1.0))
        f_1d = float(last_1d.get('fisher', 0.0))
        f_sig_1d = float(last_1d.get('fisher_signal', 0.0))
        prev_1d = df_1d_ind.iloc[-2] if len(df_1d_ind) >= 2 else last_1d
        f_1d_prev = float(prev_1d.get('fisher', 0.0))
        ema9_1d = float(last_1d.get('ema9', c_1d))
        is_green = (c_1d >= o_1d)
        has_momentum = (f_1d > f_sig_1d) or (vol_r_1d >= 1.25)
        cond_daily_confirm = (rsi_1d >= 30.0) and is_green and has_momentum

        pass_trigger = False
        if not use_enhancements:
            pass_trigger = cond_daily_confirm
        else:
            # Tối ưu hóa Preset 1: RSI >= 35, Close >= EMA9, Fisher turnaround hoặc phân kỳ dương RSI
            divs = detect_rsi_divergence(df_1d_ind, order=5)
            recent_bullish_div = False
            if divs.get("bullish"):
                last_div = divs["bullish"][-1]
                if len(df_1d) - 1 - last_div["t2"] <= 15:
                    recent_bullish_div = True

            fisher_turnaround = (f_1d > f_sig_1d) and (f_1d > f_1d_prev)
            has_momentum_reversal = fisher_turnaround or recent_bullish_div or (f_1d > f_sig_1d and vol_r_1d >= 1.25)
            pass_trigger = is_green and (rsi_1d >= 35.0) and (c_1d >= ema9_1d) and has_momentum_reversal

        # Kiểm tra Gatekeeper và điều kiện bắt buộc
        if cond_ma and cond_fisher and gate_pass and pass_trigger:
            return {
                "ticker": ticker,
                "preset": "Preset 1: Bắt đáy Chu kỳ",
                "price": round(float(c_1d), 2),
                "dist_ma_pct": round(float(dist_pct), 2),
                "ma_ref": round(float(ma_long), 2),
                "fisher_1m": round(float(fisher_1m), 2),
                "enhanced": "Đã xác nhận đảo chiều" if use_enhancements else "Tiêu chuẩn",
                "pb": gate_info["pb"],
                "debt_to_equity": gate_info["debt_to_equity"],
                "avg_liquidity": gate_info["avg_liquidity"]
            }

    # --- Preset 2: Breakout Bearish Pitchfork (Khung 1W) ---
    elif preset == "preset_2":
        df_1w = resample_ohlcv(df_1d, "1W")
        if len(df_1w) < 15:
            return None

        df_1w_ind = calculate_all_indicators(df_1w, is_monthly=False)
        last_1w = df_1w_ind.iloc[-1]
        c_1w = float(last_1w['close'])

        # Tính Pitchfork 1W
        pf = compute_bearish_pitchfork(df_1w, order=swing_order)
        cond_pf = False
        upper_line_val = None
        if pf:
            idx_last = len(df_1w) - 1
            if idx_last in pf['t_eval']:
                pos = np.where(pf['t_eval'] == idx_last)[0][0]
                upper_line_val = pf['p_l3'][pos]
                if c_1w > upper_line_val:
                    cond_pf = True

        vol_ratio_1w = float(last_1w.get('vol_ratio', 1.0))
        cond_vol = (vol_ratio_1w >= PRESET_2_PARAMS["vol_ratio_min_1w"])

        mfi_1w = float(last_1w.get('mfi', 50.0))
        cond_mfi = (mfi_1w >= 45.0)

        # Điều kiện BẮT BUỘC: Lọc râu nến & khoảng cách EMA21
        h_w = float(last_1w['high'])
        l_w = float(last_1w['low'])
        ema21_w = float(last_1w.get('ema21', c_1w))
        rng = h_w - l_w
        candle_str = (c_1w - l_w) / rng if rng > 0 else 0.0
        dist_ema_w = abs(c_1w - ema21_w) / ema21_w if ema21_w > 0 else 0.0
        cond_candle_tail = (candle_str >= 0.50) and (dist_ema_w <= 0.15)
        rsi_1d = float(last_1d.get('rsi', 50.0))

        pass_trigger = False
        if not use_enhancements:
            pass_trigger = cond_candle_tail
        else:
            # Tối ưu hóa Preset 2 (nguồn ngưỡng: settings.PRESET_2_PARAMS)
            breakout_margin_ok = (upper_line_val is not None) and (
                c_1w >= upper_line_val * PRESET_2_PARAMS["breakout_margin"])
            pass_trigger = (breakout_margin_ok
                            and (candle_str >= PRESET_2_PARAMS["candle_strength_min"])
                            and (dist_ema_w <= PRESET_2_PARAMS["max_dist_ema21w"])
                            and (rsi_1d <= PRESET_2_PARAMS["rsi_max"])
                            and (mfi_1w >= PRESET_2_PARAMS["mfi_min_1w"]))

        # Top-Down Layer 1: không mua bứt phá khi VN-Index gãy sâu.
        # Dùng đúng ngưỡng baseline (0.98 / RSI 46) như backtest_engine P2 để
        # quét live và kiểm định lịch sử cho ra cùng một tập tín hiệu.
        regime2 = get_market_regime()
        cond_market2 = regime2["ok"]

        if cond_pf and cond_vol and cond_mfi and pass_trigger and cond_market2 and (avg_liquidity >= 15.0):
            return {
                "ticker": ticker,
                "preset": "Preset 2: Breakout Bearish Pitchfork",
                "price": round(float(c_1w), 2),
                "upper_pitchfork": round(float(upper_line_val), 2) if upper_line_val else None,
                "vol_ratio_1w": round(float(vol_ratio_1w), 2),
                "mfi_1w": round(float(mfi_1w), 1),
                "enhanced": "Lọc Bull Trap & Thân Nến" if use_enhancements else "Tiêu chuẩn",
                "avg_liquidity": round(avg_liquidity, 2)
            }

    # --- Preset 3: Uptrend Pullback (Khung 1D) ---
    elif preset == "preset_3":
        ema21 = float(last_1d.get('ema21', c_1d))
        ema50 = float(last_1d.get('ema50', c_1d))
        ema120 = float(last_1d.get('ema120', c_1d))

        # Xu hướng tăng vững: EMA21 > EMA50 > EMA120
        cond_trend = (ema21 > ema50 > ema120)

        # Pullback chạm sát EMA21 (+/- 3%)
        dist_ema21 = abs(c_1d - ema21) / ema21 * 100.0
        cond_pullback = (dist_ema21 <= 3.0)

        rsi = float(last_1d.get('rsi', 50.0))
        cond_rsi = (PRESET_3_PARAMS["rsi_low"] <= rsi <= PRESET_3_PARAMS["rsi_high"])

        fisher = float(last_1d.get('fisher', 0.0))
        cond_fisher = (fisher > PRESET_3_PARAMS["fisher_min"])

        # Điều kiện BẮT BUỘC (Baseline MTF - AGENTS.md §4.6): Lọc nến xả hàng & giữ hỗ trợ EMA21
        vol_r = float(last_1d.get('vol_ratio', 1.0))
        is_distrib = (c_1d < o_1d) and (vol_r > 1.25)
        holds_support = (c_1d >= ema21 * PRESET_3_PARAMS["ema21_buffer"])
        cond_distrib_filter = (not is_distrib) and holds_support

        regime = get_market_regime()

        pass_trigger = False
        if not use_enhancements:
            pass_trigger = cond_distrib_filter and regime["ok"]
        else:
            # Tối ưu hóa Preset 3 (nguồn ngưỡng: settings.PRESET_3_PARAMS)
            # 1. Nến bật nảy xác nhận: Nến xanh (Close >= Open) & đóng ở nửa trên thân nến
            # 2. Cạn kiệt cung trên nến pullback (vol_ratio nến trước thấp) và không xả hàng
            # 3. EMA21 dốc lên: EMA21_t >= EMA21_{t-2}
            # 4. Giữ vững EMA21 * buffer
            # 5. RSI ngày lành mạnh
            # 6. Market regime guard: VNI Close >= EMA50 * buffer hoặc RSI >= ngưỡng
            day_rng = float(last_1d['high']) - float(last_1d['low'])
            candle_str_1d = (c_1d - float(last_1d['low'])) / day_rng if day_rng > 0 else 0.0
            bounce_confirmed = (c_1d >= o_1d) and (candle_str_1d >= PRESET_3_PARAMS["candle_strength_min"])

            prev_1d = df_1d_ind.iloc[-2] if len(df_1d_ind) >= 2 else last_1d
            vol_r_prev = float(prev_1d.get('vol_ratio', 1.0))
            vol_dryup = (vol_r_prev <= PRESET_3_PARAMS["vol_dryup_max"]) and (not is_distrib)

            ema21_prev2 = float(df_1d_ind.iloc[-3].get('ema21', ema21)) if len(df_1d_ind) >= 3 else ema21
            ema21_sloping_up = (ema21 >= ema21_prev2)

            rsi_healthy = (rsi >= PRESET_3_PARAMS["rsi_healthy"])
            market_ok = regime.get("ok_enhanced", regime["ok"])

            pass_trigger = (bounce_confirmed and vol_dryup and ema21_sloping_up and
                            holds_support and rsi_healthy and market_ok)

        if cond_trend and cond_pullback and cond_rsi and cond_fisher and pass_trigger and (avg_liquidity >= 15.0):
            return {
                "ticker": ticker,
                "preset": "Preset 3: Uptrend Pullback",
                "price": round(float(c_1d), 2),
                "ema21": round(float(ema21), 2),
                "dist_ema21_pct": round(float(dist_ema21), 2),
                "rsi_1d": round(float(rsi), 1),
                "fisher_1d": round(float(fisher), 2),
                "enhanced": "Lọc Cạn Cung & Giữ EMA21" if use_enhancements else "Tiêu chuẩn",
                "avg_liquidity": round(avg_liquidity, 2)
            }

    return None

def run_screener(tickers: list, preset: str = "preset_1", swing_order: int = 5, use_enhancements: bool = False) -> pd.DataFrame:
    """Quét toàn bộ danh sách mã trong Local DB và trả về kết quả lọc."""
    matched = []
    errors = 0
    for t in tickers:
        try:
            res = scan_stock(t, preset=preset, swing_order=swing_order, use_enhancements=use_enhancements)
            if res:
                matched.append(res)
        except Exception:
            errors += 1
            logger.exception("Lỗi khi quét mã %s (preset=%s) - bỏ qua mã này", t, preset)
    if errors:
        logger.warning("run_screener: %d/%d mã bị lỗi và đã bỏ qua", errors, len(tickers))
    return pd.DataFrame(matched)
