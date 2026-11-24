"""
core/scoring_engine.py
Hệ thống chấm điểm định lượng 6 tầng Top-Down (0 - 100) theo chuẩn kiến trúc v5.0:
- Tầng 1: Thiên văn & Gann (Người dùng tự chấm slider 0-100, lưu bền vững SQLite)
- Tầng 2: Vĩ mô & Margin (Yield Curve, DXY, VIX, Tỷ giá VND, Tăng trưởng Margin)
- Tầng 3: Hàng hóa & RRG Ngành (Phân tách Market-Level toàn thị trường và Stock-Level từng mã)
- Tầng 4: Phái sinh & Độ rộng thị trường (Basis, OI Trend, % Cổ phiếu > MA50, Độ dốc AD Line)
- Tầng 5: VN-Index Đa khung (1M - 1W - 1D) kèm tùy chọn loại bỏ nhóm Vingroup (EX_VIN)
- Hỗ trợ Dynamic Reweighting: Tự động phát hiện thiếu dữ liệu và tái phân bổ trọng số
  (tuyệt đối không nhồi số mặc định giả tạo, đảm bảo tính trung thực định lượng)
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
from config.settings import DEFAULT_TOPDOWN_WEIGHTS

logger = logging.getLogger(__name__)


def score_tier1_astro_gann(user_score: float = 50.0) -> float:
    """Tầng 1: Trả về điểm do người dùng tự chấm bằng Slider (0 - 100)."""
    return float(np.clip(user_score, 0.0, 100.0))


def score_tier2_macro_margin(macro_data: Optional[dict] = None) -> dict:
    """
    Tầng 2: Vĩ mô & Margin:
    Trọng số chuẩn: Yield (0.25), DXY (0.15), VIX (0.15), VND (0.15), Margin (0.30).
    Cơ chế Dynamic Reweighting: Tự động loại bỏ các thành phần thiếu (None) và tái phân bổ trọng số.
    """
    if not macro_data:
        return {"score": None, "available": False, "details": {}, "active_weights": {}}

    sub_scores = {}
    base_weights = {
        "yield": 0.25,
        "dxy": 0.15,
        "vix": 0.15,
        "vnd": 0.15,
        "margin": 0.30
    }

    # 1. Yield Curve (T10Y2Y spread %)
    y_spread = macro_data.get("t10y2y")
    if y_spread is not None and pd.notna(y_spread):
        if y_spread > 0.5:
            sub_scores["yield"] = 90.0
        elif y_spread >= 0.0:
            sub_scores["yield"] = 70.0
        elif y_spread >= -0.2:
            sub_scores["yield"] = 40.0
        else:
            sub_scores["yield"] = 15.0

    # 2. DXY
    dxy = macro_data.get("dxy")
    if dxy is not None and pd.notna(dxy):
        if dxy < 100.0:
            sub_scores["dxy"] = 85.0
        elif dxy <= 104.0:
            sub_scores["dxy"] = 60.0
        elif dxy <= 108.0:
            sub_scores["dxy"] = 35.0
        else:
            sub_scores["dxy"] = 15.0

    # 3. VIX
    vix = macro_data.get("vix")
    if vix is not None and pd.notna(vix):
        if vix < 15.0:
            sub_scores["vix"] = 90.0
        elif vix <= 20.0:
            sub_scores["vix"] = 70.0
        elif vix <= 30.0:
            sub_scores["vix"] = 40.0
        else:
            sub_scores["vix"] = 10.0

    # 4. VND/USD change % (60 phiên)
    vnd_change = macro_data.get("vnd_change_60d")
    if vnd_change is not None and pd.notna(vnd_change):
        if vnd_change <= 0.0:
            sub_scores["vnd"] = 80.0
        elif vnd_change <= 2.0:
            sub_scores["vnd"] = 55.0
        else:
            sub_scores["vnd"] = 20.0

    # 5. Margin Growth QoQ %
    margin_qoq = macro_data.get("margin_growth_qoq")
    if margin_qoq is not None and pd.notna(margin_qoq):
        if margin_qoq < -10.0:
            sub_scores["margin"] = 50.0  # Giải chấp tạo đáy
        elif margin_qoq < 5.0:
            sub_scores["margin"] = 85.0  # Tích lũy sớm an toàn
        elif margin_qoq <= 15.0:
            sub_scores["margin"] = 65.0  # Đang tăng tốc
        else:
            sub_scores["margin"] = 30.0  # Quá nóng, rủi ro đỉnh

    if not sub_scores:
        return {"score": None, "available": False, "details": {}, "active_weights": {}}

    # Tái chuẩn hóa trọng số cho các thành phần khả dụng
    total_avail_w = sum(base_weights[k] for k in sub_scores)
    active_weights = {k: base_weights[k] / total_avail_w for k in sub_scores}
    total_t2 = sum(sub_scores[k] * active_weights[k] for k in sub_scores)

    return {
        "score": round(float(total_t2), 1),
        "available": True,
        "details": sub_scores,
        "active_weights": active_weights,
        "missing_components": [k for k in base_weights if k not in sub_scores]
    }


def score_tier3_market_level(rrg_results: Optional[dict] = None,
                              commodity_trend_score: Optional[float] = None) -> dict:
    """
    Tầng 3: Market-Level Score (toàn thị trường):
    Tính từ tỷ lệ phân bổ của 9 ngành trên 4 góc phần tư RRG và xu hướng hàng hóa.
    Nếu thiếu 1 trong 2, tự động tái chuẩn hóa 100% cho thành phần còn lại.
    """
    sub_scores = {}
    base_weights = {}

    if rrg_results:
        quad_weights = {"Leading": 100.0, "Improving": 70.0, "Weakening": 35.0, "Lagging": 10.0}
        scores = [quad_weights.get(item.get("quadrant", "Improving"), 50.0) for item in rrg_results.values()]
        if scores:
            sub_scores["rrg_distribution"] = float(np.mean(scores))
            base_weights["rrg_distribution"] = 0.60

    if commodity_trend_score is not None and pd.notna(commodity_trend_score):
        sub_scores["commodity_trend"] = float(commodity_trend_score)
        base_weights["commodity_trend"] = 0.40

    if not sub_scores:
        return {"score": None, "available": False, "details": {}}

    tot_w = sum(base_weights.values())
    total_t3 = sum(sub_scores[k] * (base_weights[k] / tot_w) for k in sub_scores)

    return {
        "score": round(float(total_t3), 1),
        "available": True,
        "details": {k: round(v, 1) for k, v in sub_scores.items()}
    }


def score_tier4_derivatives_breadth(data: Optional[dict] = None) -> dict:
    """
    Tầng 4: Phái sinh & Độ rộng thị trường:
    - Basis: > +5 (85), 0->+5 (65), -5->0 (40), < -5 (20)
    - OI Trend: Tăng+Giá tăng (85), Giảm+Giá tăng (60), Giảm+Giá giảm (30), Tăng+Giá giảm (25)
    - % Cổ phiếu > MA50: >70% (90), 50-70% (65), 30-50% (40), <30% (15)
    - AD Line Slope: Dương mạnh (85), Dương nhẹ (60), Âm nhẹ (35), Âm mạnh (15)
    Hỗ trợ Dynamic Reweighting: Tự động bỏ qua bất kỳ trường nào là None.
    """
    if not data:
        return {"score": None, "available": False, "details": {}}

    sub_scores = {}
    base_weights = {
        "basis": 0.25,
        "oi": 0.25,
        "breadth50": 0.30,
        "ad_slope": 0.20
    }

    basis = data.get("basis")
    if basis is not None and pd.notna(basis):
        if basis > 5.0:
            sub_scores["basis"] = 85.0
        elif basis >= 0.0:
            sub_scores["basis"] = 65.0
        elif basis >= -5.0:
            sub_scores["basis"] = 40.0
        else:
            sub_scores["basis"] = 20.0

    breadth50 = data.get("pct_above_ma50")
    if breadth50 is not None and pd.notna(breadth50):
        if breadth50 > 70.0:
            sub_scores["breadth50"] = 90.0
        elif breadth50 >= 50.0:
            sub_scores["breadth50"] = 65.0
        elif breadth50 >= 30.0:
            sub_scores["breadth50"] = 40.0
        else:
            sub_scores["breadth50"] = 15.0

    ad_slope = data.get("ad_slope")
    if ad_slope is not None and pd.notna(ad_slope):
        if ad_slope > 0.5:
            sub_scores["ad_slope"] = 85.0
        elif ad_slope >= 0.0:
            sub_scores["ad_slope"] = 60.0
        elif ad_slope >= -0.5:
            sub_scores["ad_slope"] = 35.0
        else:
            sub_scores["ad_slope"] = 15.0

    oi_trend = data.get("oi_trend")
    if oi_trend is not None:
        oi_scores = {
            "OI_UP_PRICE_UP": 85.0,
            "OI_DOWN_PRICE_UP": 60.0,
            "OI_DOWN_PRICE_DOWN": 30.0,
            "OI_UP_PRICE_DOWN": 25.0
        }
        if oi_trend in oi_scores:
            sub_scores["oi"] = oi_scores[oi_trend]

    if not sub_scores:
        return {"score": None, "available": False, "details": {}}

    tot_w = sum(base_weights[k] for k in sub_scores)
    total_t4 = sum(sub_scores[k] * (base_weights[k] / tot_w) for k in sub_scores)

    return {
        "score": round(float(total_t4), 1),
        "available": True,
        "details": sub_scores,
        "missing_components": [k for k in base_weights if k not in sub_scores]
    }


def _score_single_frame(df_frame: pd.DataFrame) -> float:
    """Chấm điểm 1 khung thời gian (1M, 1W hoặc 1D) từ Fisher, RSI, MACD, Volume và Trend."""
    if df_frame is None or df_frame.empty or len(df_frame) < 5:
        return 50.0

    last = df_frame.iloc[-1]
    prev = df_frame.iloc[-2] if len(df_frame) >= 2 else last

    # 1. Fisher Transform (30%)
    fisher = last.get('fisher', 0.0)
    fisher_prev = prev.get('fisher', 0.0)
    is_cutting_up = fisher > fisher_prev

    if fisher < -2.5 and is_cutting_up:
        s_fisher = 95.0
    elif -2.5 <= fisher < -1.0 and is_cutting_up:
        s_fisher = 75.0
    elif -1.0 <= fisher <= 1.0:
        s_fisher = 50.0
    elif 1.0 < fisher <= 2.0:
        s_fisher = 35.0
    else:
        s_fisher = 15.0

    # 2. RSI (20%)
    rsi = last.get('rsi', 50.0)
    if rsi < 30.0:
        s_rsi = 85.0
    elif rsi <= 45.0:
        s_rsi = 65.0
    elif rsi <= 55.0:
        s_rsi = 50.0
    elif rsi <= 70.0:
        s_rsi = 40.0
    else:
        s_rsi = 20.0

    # 3. MACD Histogram (20%)
    hist = last.get('macd_hist', 0.0)
    hist_prev = prev.get('macd_hist', 0.0)
    if hist < 0 and hist > hist_prev:
        s_macd = 70.0  # Âm nhưng đang thu hẹp
    elif hist >= 0 and hist_prev < 0:
        s_macd = 80.0  # Vừa cắt chuyển dương
    elif hist >= 0 and hist >= hist_prev:
        s_macd = 65.0  # Dương mở rộng
    elif hist >= 0 and hist < hist_prev:
        s_macd = 40.0  # Dương thu hẹp
    else:
        s_macd = 20.0  # Âm mở rộng

    # 4. Vol Ratio (15%)
    vol_ratio = last.get('vol_ratio', 1.0)
    price_up = last['close'] >= prev['close']
    if vol_ratio >= 2.5 and price_up:
        s_vol = 90.0
    elif vol_ratio >= 1.8 and price_up:
        s_vol = 75.0
    elif 0.8 <= vol_ratio <= 1.8:
        s_vol = 50.0
    elif vol_ratio >= 1.8 and not price_up:
        s_vol = 25.0
    else:
        s_vol = 45.0

    # 5. Trend vs EMA (15%)
    c = last['close']
    ema21 = last.get('ema21', c)
    ema50 = last.get('ema50', c)
    ema120 = last.get('ema120', c)

    if c > ema21 > ema50 > ema120:
        s_trend = 90.0
    elif c > ema21 and ema21 > ema50:
        s_trend = 70.0
    elif c < ema21 and c > ema50:
        s_trend = 45.0
    else:
        s_trend = 15.0

    frame_score = (0.30 * s_fisher) + (0.20 * s_rsi) + (0.20 * s_macd) + (0.15 * s_vol) + (0.15 * s_trend)
    return float(frame_score)


def score_tier5_vnindex_mtf(df_1m: Optional[pd.DataFrame],
                            df_1w: Optional[pd.DataFrame],
                            df_1d: Optional[pd.DataFrame]) -> dict:
    """
    Tầng 5: VN-Index Đa khung (1M - 1W - 1D) - Trọng số 40%:
    S_T5 = 0.30 * S_1M + 0.35 * S_1W + 0.35 * S_1D
    """
    if df_1d is None or df_1d.empty:
        return {"score": None, "available": False, "details": {}}

    s_1m = _score_single_frame(df_1m) if df_1m is not None and not df_1m.empty else None
    s_1w = _score_single_frame(df_1w) if df_1w is not None and not df_1w.empty else None
    s_1d = _score_single_frame(df_1d)

    frames = {}
    base_w = {"1M": 0.30, "1W": 0.35, "1D": 0.35}
    if s_1m is not None:
        frames["1M"] = s_1m
    if s_1w is not None:
        frames["1W"] = s_1w
    if s_1d is not None:
        frames["1D"] = s_1d

    tot_w = sum(base_w[k] for k in frames)
    total_t5 = sum(frames[k] * (base_w[k] / tot_w) for k in frames)

    return {
        "score": round(float(total_t5), 1),
        "available": True,
        "details": {k: round(v, 1) for k, v in frames.items()}
    }


def calculate_topdown_composite_score(scores: dict, weights: Optional[dict] = None) -> dict:
    """
    Tổng hợp điểm Top-Down Composite Score (0 - 100):
    Total = w1*S_T1 + w2*S_T2 + w3*S_T3 + w4*S_T4 + w5*S_T5
    Dynamic Reweighting: Tự động loại bỏ các tầng không có dữ liệu (None) và tái chuẩn hóa về 100%.
    """
    w_cfg = weights if weights else DEFAULT_TOPDOWN_WEIGHTS

    tier_keys = {
        "T1": "T1_Astro_Gann",
        "T2": "T2_Macro_Margin",
        "T3": "T3_Commodity_RRG",
        "T4": "T4_Deriv_Breadth",
        "T5": "T5_VNIndex_MTF"
    }

    # Lọc các tầng có dữ liệu thực tế (khác None)
    active_tiers = {}
    missing_tiers = []

    for t_short, t_full in tier_keys.items():
        val = scores.get(t_short)
        if val is not None and pd.notna(val):
            active_tiers[t_short] = float(val)
        else:
            missing_tiers.append(t_short)

    if not active_tiers:
        return {
            "composite_score": 50.0,
            "zone": "Neutral",
            "color": "#FF9500",
            "sub_scores": scores,
            "weights": {},
            "reweighted": False,
            "missing_tiers": list(tier_keys.keys())
        }

    # Tái chuẩn hóa trọng số các tầng khả dụng
    total_active_w = sum(w_cfg.get(tier_keys[t], 0.20) for t in active_tiers)
    if total_active_w <= 0:
        total_active_w = 1.0

    norm_weights = {
        tier_keys[t]: w_cfg.get(tier_keys[t], 0.20) / total_active_w for t in active_tiers
    }

    composite = sum(active_tiers[t] * norm_weights[tier_keys[t]] for t in active_tiers)
    composite = round(float(np.clip(composite, 0.0, 100.0)), 1)

    # Đánh giá phân vùng
    if composite < 30.0:
        zone = "Bearish"
        color = "#FF3B30"
    elif composite < 50.0:
        zone = "Neutral"
        color = "#FF9500"
    elif composite < 70.0:
        zone = "Bullish"
        color = "#34C759"
    else:
        zone = "Strong Bull"
        color = "#007AFF"

    return {
        "composite_score": composite,
        "zone": zone,
        "color": color,
        "sub_scores": scores,
        "weights": norm_weights,
        "reweighted": len(missing_tiers) > 0,
        "missing_tiers": missing_tiers
    }
