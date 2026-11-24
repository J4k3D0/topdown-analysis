"""
core/backtest_engine.py
Động cơ Backtest Thực chiến & Tối ưu hóa Xác suất Dự đoán Tương lai (2010 - 2026):
- Kiểm tra tính thực tiễn của 3 Preset trên chuỗi dữ liệu lịch sử thực tế của thị trường Việt Nam
- Áp dụng nguyên bản quy tắc quản trị Scaling-Out 50/50 theo đúng hệ thống của người dùng
- Chẩn đoán các nguyên nhân gây tín hiệu sai (Bắt dao rơi nến Tháng, Phá vỡ giả nến Tuần, Xả hàng nến Ngày)
- Phát triển các lớp lọc bổ sung (Dòng tiền hấp thụ, Phân kỳ RSI, Điểm khô thanh khoản, Khung thị trường chung)
- Tối ưu hóa hiệu năng vector/pre-indexing giúp quét hàng chục nghìn phiên chỉ trong vài giây
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime
from config.settings import PRESET_2_PARAMS, PRESET_3_PARAMS
from core.db_manager import load_ohlcv, get_connection
from core.indicators import resample_ohlcv, calculate_all_indicators
from core.geometry_log import get_pivots_log

# ---------------------------------------------------------------------------
# Tham số hiệu chỉnh của Preset 3 (đọc từ config/settings.py, đọc động ở
# runtime để phục vụ nghiên cứu thực nghiệm/tối ưu xác suất dự đoán mà không
# phải sửa thuật toán).
# ---------------------------------------------------------------------------
P3_MAX_DIST_EMA21_PCT = PRESET_3_PARAMS["max_dist_ema21_pct"]
P3_RSI_LOW = PRESET_3_PARAMS["rsi_low"]
P3_RSI_HIGH = PRESET_3_PARAMS["rsi_high"]
P3_RSI_HEALTHY = PRESET_3_PARAMS["rsi_healthy"]
P3_FISHER_MIN = PRESET_3_PARAMS["fisher_min"]
P3_VOL_DRYUP_MAX = PRESET_3_PARAMS["vol_dryup_max"]
P3_EMA21_BUFFER = PRESET_3_PARAMS["ema21_buffer"]
P3_CANDLE_STRENGTH_MIN = PRESET_3_PARAMS["candle_strength_min"]
P3_MARKET_EMA50_BUFFER = PRESET_3_PARAMS["market_ema50_buffer"]
P3_MARKET_RSI_MIN = PRESET_3_PARAMS["market_rsi_min"]

# Preset 2
P2_BREAKOUT_MARGIN = PRESET_2_PARAMS["breakout_margin"]
P2_CANDLE_STRENGTH_MIN = PRESET_2_PARAMS["candle_strength_min"]
P2_MAX_DIST_EMA21W = PRESET_2_PARAMS["max_dist_ema21w"]
P2_RSI_MAX = PRESET_2_PARAMS["rsi_max"]
P2_MFI_MIN_1W = PRESET_2_PARAMS["mfi_min_1w"]
P2_VOL_RATIO_MIN_1W = PRESET_2_PARAMS["vol_ratio_min_1w"]
P2_MARKET_EMA50_BUFFER = PRESET_2_PARAMS["market_ema50_buffer"]
P2_MARKET_RSI_MIN = PRESET_2_PARAMS["market_rsi_min"]

# Cache chứa chỉ báo VNINDEX dùng chung cho toàn bộ các lượt backtest
_VNI_INDICATORS_CACHE = {}

def _get_vni_cached_sub():
    """Lấy dữ liệu chỉ báo VNINDEX từ cache tránh việc tính lại hàng ngàn lần."""
    cache_key = os.environ.get('QUANT_DB_PATH', 'default')
    if cache_key in _VNI_INDICATORS_CACHE:
        return _VNI_INDICATORS_CACHE[cache_key].copy()

    df_vni = load_ohlcv('VNINDEX')
    if df_vni is not None and len(df_vni) > 60:
        df_vni_ind = calculate_all_indicators(df_vni, is_monthly=False)
        cols_vni = ['date', 'close', 'ema50', 'rsi']
        df_vni_sub = df_vni_ind[[c for c in cols_vni if c in df_vni_ind.columns]].rename(columns={
            'close': 'vni_close', 'ema50': 'vni_ema50', 'rsi': 'vni_rsi'
        })
        df_vni_sub['date'] = pd.to_datetime(df_vni_sub['date'])
        df_vni_sub = df_vni_sub.sort_values('date')
        _VNI_INDICATORS_CACHE[cache_key] = df_vni_sub
        return df_vni_sub.copy()
    return None

def _compute_weekly_pitchfork_vector(df_1w: pd.DataFrame, order: int = 5) -> np.ndarray:
    """Tính đường biên trên (Line 3) của Bearish Pitchfork cho toàn bộ các tuần trong df_1w với tốc độ vector."""
    n = len(df_1w)
    upper_lines = np.full(n, np.nan)
    if n < 15:
        return upper_lines

    highs, lows = get_pivots_log(df_1w, order=order)
    if len(highs) < 2 or len(lows) < 1:
        return upper_lines

    hp = df_1w['high'].values
    lp = df_1w['low'].values

    for w in range(15, n):
        # Chỉ xét các đỉnh đáy đã hoàn toàn xác nhận trước tuần w (tối thiểu cách order nến)
        h_sub = highs[highs <= w - order]
        l_sub = lows[lows <= w - order]
        if len(h_sub) < 2 or len(l_sub) < 1:
            continue

        for t1 in reversed(h_sub):
            p1 = hp[t1]
            l_after = l_sub[l_sub > t1]
            if len(l_after) == 0:
                continue

            t2 = l_after[np.argmin(lp[l_after])]
            p2 = lp[t2]

            h_after = h_sub[(h_sub > t2) & (hp[h_sub] < p1)]
            if len(h_after) == 0:
                continue

            t3 = h_after[np.argmax(hp[h_after])]
            p3 = hp[t3]

            y1, y2, y3 = np.log10(p1), np.log10(p2), np.log10(p3)
            tM = (t2 + t3) / 2.0
            yM = (y2 + y3) / 2.0

            # Bắt buộc độ dốc Bearish Pitchfork phải dốc xuống: m < 0 tương đương yM < y1 (vì tM > t1)
            if tM <= t1 or yM >= y1:
                continue

            m = (yM - y1) / (tM - t1)
            upper_lines[w] = 10.0 ** (y3 + m * (w - t3))
            break

    return upper_lines

def backtest_preset(ticker: str, preset: str = "preset_1", start_date: str = "2015-01-01",
                    stop_loss_pct: float = 0.07, target1_pct: float = 0.15, target2_pct: float = 0.35,
                    use_enhancements: bool = False) -> dict:
    """
    Backtest 1 mã cổ phiếu qua toàn bộ lịch sử nến ngày từ start_date đến hiện tại:
    - preset: 'preset_1' (Bắt đáy chu kỳ), 'preset_2' (Breakout Pitchfork), 'preset_3' (Uptrend Pullback)
    - use_enhancements: Kích hoạt các bộ lọc tối ưu hóa nhằm tăng độ chính xác dự đoán.
    """
    df_raw = load_ohlcv(ticker, start_date=None)
    if df_raw is None or len(df_raw) < 150:
        return {"trades": [], "summary": None}

    df_raw = df_raw.sort_values('date').reset_index(drop=True)
    df_raw['date'] = pd.to_datetime(df_raw['date'])

    # 1. Tính toán chỉ báo cho nến Ngày
    df_1d = calculate_all_indicators(df_raw, is_monthly=False)

    # 2. Resample và tính chỉ báo nến Tuần
    df_1w_raw = resample_ohlcv(df_raw, "1W")
    df_1w = calculate_all_indicators(df_1w_raw, is_monthly=False)
    df_1w['date'] = pd.to_datetime(df_1w['date'])

    # Tính Pitchfork nhanh cho nến tuần
    df_1w['upper_pitchfork_1w'] = _compute_weekly_pitchfork_vector(df_1w, order=5)
    cols_1w = ['date', 'upper_pitchfork_1w', 'vol_ratio', 'mfi', 'high', 'low', 'ema21']
    df_1w_sub = df_1w[[c for c in cols_1w if c in df_1w.columns]].rename(columns={
        'vol_ratio': 'vol_ratio_1w',
        'mfi': 'mfi_1w',
        'high': 'high_1w',
        'low': 'low_1w',
        'ema21': 'ema21_1w'
    })

    # 3. Resample và tính chỉ báo nến Tháng
    df_1m_raw = resample_ohlcv(df_raw, "1M")
    df_1m = calculate_all_indicators(df_1m_raw, is_monthly=True)
    df_1m['date'] = pd.to_datetime(df_1m['date'])
    cols_1m = ['date', 'ma_long_1m', 'fisher', 'fisher_signal']
    df_1m_sub = df_1m[[c for c in cols_1m if c in df_1m.columns]].rename(columns={
        'ma_long_1m': 'ma_long_1m',
        'fisher': 'fisher_1m',
        'fisher_signal': 'fisher_sig_1m'
    })

    # 4. Hợp nhất (merge_asof) các khung thời gian vào df_1d trong 1 phép toán duy nhất
    df_merged = pd.merge_asof(df_1d.sort_values('date'), df_1w_sub.sort_values('date'), on='date', direction='backward')
    df_merged = pd.merge_asof(df_merged, df_1m_sub.sort_values('date'), on='date', direction='backward')

    # Nạp VNINDEX để lọc Regime thị trường chung (Top-Down Layer 1) qua cache
    df_vni_sub = _get_vni_cached_sub()
    if df_vni_sub is not None:
        df_merged = pd.merge_asof(df_merged, df_vni_sub, on='date', direction='backward')
    else:
        df_merged['vni_close'] = 1000.0
        df_merged['vni_ema50'] = 1000.0
        df_merged['vni_rsi'] = 50.0

    df_merged['date_str'] = df_merged['date'].dt.strftime('%Y-%m-%d')

    trades = []
    in_trade = False
    current_trade = None

    start_indices = df_merged[df_merged['date_str'] >= start_date].index
    if len(start_indices) == 0:
        return {"trades": [], "summary": None}

    start_idx = max(start_indices[0], 60)
    n_bars = len(df_merged)

    # Chuyển đổi các cột cần dùng sang numpy array để đạt tốc độ vòng lặp tối đa
    c_arr = df_merged['close'].values
    o_arr = df_merged['open'].values
    h_arr = df_merged['high'].values
    l_arr = df_merged['low'].values
    dt_arr = df_merged['date_str'].values

    ema9_arr = df_merged['ema9'].values if 'ema9' in df_merged else c_arr
    ema21_arr = df_merged['ema21'].values if 'ema21' in df_merged else c_arr
    ema50_arr = df_merged['ema50'].values if 'ema50' in df_merged else c_arr
    ema120_arr = df_merged['ema120'].values if 'ema120' in df_merged else c_arr
    rsi_arr = df_merged['rsi'].values if 'rsi' in df_merged else np.full(n_bars, 50.0)
    vol_r_arr = df_merged['vol_ratio'].values if 'vol_ratio' in df_merged else np.ones(n_bars)
    fisher_arr = df_merged['fisher'].values if 'fisher' in df_merged else np.zeros(n_bars)
    fisher_sig_arr = df_merged['fisher_signal'].values if 'fisher_signal' in df_merged else np.zeros(n_bars)

    ma_long_1m_arr = df_merged['ma_long_1m'].values if 'ma_long_1m' in df_merged else c_arr
    fisher_1m_arr = df_merged['fisher_1m'].values if 'fisher_1m' in df_merged else np.zeros(n_bars)

    up_pf_1w_arr = df_merged['upper_pitchfork_1w'].values if 'upper_pitchfork_1w' in df_merged else np.full(n_bars, np.nan)
    vol_r_1w_arr = df_merged['vol_ratio_1w'].values if 'vol_ratio_1w' in df_merged else np.ones(n_bars)
    mfi_1w_arr = df_merged['mfi_1w'].values if 'mfi_1w' in df_merged else np.full(n_bars, 50.0)
    h_1w_arr = df_merged['high_1w'].values if 'high_1w' in df_merged else c_arr
    l_1w_arr = df_merged['low_1w'].values if 'low_1w' in df_merged else c_arr
    ema21_1w_arr = df_merged['ema21_1w'].values if 'ema21_1w' in df_merged else c_arr

    vni_c_arr = df_merged['vni_close'].values if 'vni_close' in df_merged else c_arr
    vni_ema50_arr = df_merged['vni_ema50'].values if 'vni_ema50' in df_merged else c_arr
    vni_rsi_arr = df_merged['vni_rsi'].values if 'vni_rsi' in df_merged else np.full(n_bars, 50.0)

    i = start_idx
    while i < n_bars:
        c_now = float(c_arr[i])
        o_now = float(o_arr[i])
        h_now = float(h_arr[i])
        l_now = float(l_arr[i])
        dt_now = str(dt_arr[i])

        if in_trade:
            # QUẢN TRỊ VỊ THẾ SCALING-OUT 50/50
            entry_p = current_trade['entry_price']
            sl_p = current_trade['stop_loss']
            trail_p = current_trade['trailing_stop']
            t1_p = current_trade['target_1']
            t2_p = current_trade['target_2']
            effective_stop = max(sl_p, trail_p)

            # Cập nhật Trailing Stop theo EMA21/EMA50 nến ngày khi đã chốt 50%
            # Đặt trailing stop tại max(EMA21 * 0.96, EMA50 * 0.99) để vị thế 50% có không gian dao động vươn tới Target 2 (+35%)
            ema21_now = float(ema21_arr[i])
            ema50_now = float(ema50_arr[i])
            if current_trade['status'] == 'PARTIAL':
                trailing_ref = max(ema21_now * 0.96, ema50_now * 0.99)
                current_trade['trailing_stop'] = max(current_trade['trailing_stop'], entry_p, trailing_ref)
                effective_stop = current_trade['trailing_stop']

            # 1. Chạm Stop Loss hoặc Trailing Stop
            if l_now <= effective_stop:
                exit_p = min(effective_stop, o_now)
                current_trade['exit_date'] = dt_now
                current_trade['exit_price_final'] = exit_p
                current_trade['bars_held'] = i - current_trade['entry_bar']

                if current_trade['status'] == 'OPEN':
                    current_trade['pnl_pct'] = ((exit_p - entry_p) / entry_p) * 100.0
                    current_trade['result'] = 'LOSS' if current_trade['pnl_pct'] < 0 else 'WIN'
                else:
                    pnl_1 = ((current_trade['exit_price_1'] - entry_p) / entry_p) * 100.0
                    pnl_2 = ((exit_p - entry_p) / entry_p) * 100.0
                    current_trade['pnl_pct'] = (pnl_1 + pnl_2) / 2.0
                    current_trade['result'] = 'WIN' if current_trade['pnl_pct'] > 0 else 'LOSS'

                current_trade['status'] = 'CLOSED'
                trades.append(current_trade)
                in_trade = False
                current_trade = None
                i += 1
                continue

            # 2. Chạm Target 2 (Chốt phần còn lại)
            elif h_now >= t2_p:
                exit_p = t2_p
                current_trade['exit_date'] = dt_now
                current_trade['exit_price_final'] = exit_p
                current_trade['bars_held'] = i - current_trade['entry_bar']

                if current_trade['status'] == 'PARTIAL':
                    pnl_1 = ((current_trade['exit_price_1'] - entry_p) / entry_p) * 100.0
                    pnl_2 = ((exit_p - entry_p) / entry_p) * 100.0
                    current_trade['pnl_pct'] = (pnl_1 + pnl_2) / 2.0
                else:
                    current_trade['pnl_pct'] = ((exit_p - entry_p) / entry_p) * 100.0

                current_trade['result'] = 'WIN'
                current_trade['status'] = 'CLOSED'
                trades.append(current_trade)
                in_trade = False
                current_trade = None
                i += 1
                continue

            # 3. Chạm Target 1 (Chốt 50% đầu tiên, nâng Stop lên Breakeven)
            elif current_trade['status'] == 'OPEN' and h_now >= t1_p:
                current_trade['status'] = 'PARTIAL'
                current_trade['exit_date_1'] = dt_now
                current_trade['exit_price_1'] = t1_p
                current_trade['trailing_stop'] = max(current_trade['trailing_stop'], entry_p)

            # 4. Time-stop: 120 phiên (~6 tháng)
            elif (i - current_trade['entry_bar']) >= 120:
                exit_p = c_now
                current_trade['exit_date'] = dt_now
                current_trade['exit_price_final'] = exit_p
                current_trade['bars_held'] = i - current_trade['entry_bar']
                if current_trade['status'] == 'PARTIAL':
                    pnl_1 = ((current_trade['exit_price_1'] - entry_p) / entry_p) * 100.0
                    pnl_2 = ((exit_p - entry_p) / entry_p) * 100.0
                    current_trade['pnl_pct'] = (pnl_1 + pnl_2) / 2.0
                else:
                    current_trade['pnl_pct'] = ((exit_p - entry_p) / entry_p) * 100.0
                current_trade['result'] = 'WIN' if current_trade['pnl_pct'] > 0 else 'LOSS'
                current_trade['status'] = 'CLOSED'
                trades.append(current_trade)
                in_trade = False
                current_trade = None

            i += 1
            continue

        # --- KIỂM TRA TÍN HIỆU VÀO LỆNH ---
        signal_triggered = False

        # === PRESET 1: BẮT ĐÁY CHU KỲ NẾN THÁNG ===
        if preset == "preset_1":
            ma_long = float(ma_long_1m_arr[i])
            fisher_m = float(fisher_1m_arr[i])

            if pd.notna(ma_long) and ma_long > 0:
                dist_pct = abs(c_now - ma_long) / ma_long * 100.0
                cond_ma = (dist_pct <= 10.0)
                cond_fisher = (fisher_m < -1.8)

                if cond_ma and cond_fisher:
                    if not use_enhancements:
                        signal_triggered = True
                    else:
                        # TỐI ƯU HÓA PRESET 1: XÁC NHẬN ĐIỂM ĐẢO CHIỀU ĐA KHUNG (MULTI-TIMEFRAME CONFIRMATION)
                        # 1. Nến ngày xanh (Close >= Open)
                        # 2. RSI nến ngày an toàn (RSI >= 35)
                        # 3. Giá đóng cửa nằm trên EMA9 nến ngày (Close >= EMA9)
                        # 4. Xác nhận đảo chiều động lượng: Fisher turnaround hoặc phân kỳ dương RSI nến ngày
                        rsi_now = float(rsi_arr[i])
                        vol_r_now = float(vol_r_arr[i])
                        fisher_1d = float(fisher_arr[i])
                        fisher_sig_1d = float(fisher_sig_arr[i])
                        fisher_prev_1d = float(fisher_arr[i - 1]) if i > 0 else fisher_1d
                        ema9_now = float(ema9_arr[i])

                        is_green_candle = (c_now >= o_now)
                        cond_rsi_safe = (rsi_now >= 35.0)
                        cond_ema9 = (c_now >= ema9_now)

                        # Fisher turnaround (cắt signal và dốc lên) hoặc dòng tiền hấp thụ mạnh
                        fisher_turnaround = (fisher_1d > fisher_sig_1d) and (fisher_1d > fisher_prev_1d)
                        has_momentum = fisher_turnaround or (fisher_1d > fisher_sig_1d and vol_r_now >= 1.25)

                        # Phân kỳ dương RSI trong 15 phiên gần nhất
                        is_rsi_div = False
                        if i >= 15:
                            sub_c = c_arr[i - 15:i]
                            sub_rsi = rsi_arr[i - 15:i]
                            min_c_idx = np.argmin(sub_c)
                            if c_now <= sub_c[min_c_idx] * 1.03 and rsi_now > sub_rsi[min_c_idx] + 2.0:
                                is_rsi_div = True

                        if is_green_candle and cond_rsi_safe and cond_ema9 and (has_momentum or is_rsi_div):
                            signal_triggered = True

        # === PRESET 2: BREAKOUT BEARISH PITCHFORK NẾN TUẦN ===
        elif preset == "preset_2":
            up_line = float(up_pf_1w_arr[i])
            if pd.notna(up_line):
                vol_r_w = float(vol_r_1w_arr[i])
                mfi_w = float(mfi_1w_arr[i])

                if c_now > up_line and vol_r_w >= 1.5 and mfi_w >= 45.0:
                    if not use_enhancements:
                        signal_triggered = True
                    else:
                        # TỐI ƯU HÓA PRESET 2: LỌC BULL TRAP & BẢO TOÀN VỊ THẾ TUẦN
                        # 1. Breakout margin >= 0.5% (Close >= UpperLine * 1.005)
                        # 2. Lọc râu nến: Candle strength >= 0.50 (zero-range guard -> 0.0)
                        # 3. Khoảng cách tới EMA21 tuần <= 12%
                        # 4. Chống mua đuổi quá mua: RSI ngày <= 70.0
                        # 5. Xung lực dòng tiền MFI tuần >= 48.0
                        # 6. Top-Down Layer 1: VN-Index không gãy sâu (đồng bộ với Preset 3)
                        h_w = float(h_1w_arr[i])
                        l_w = float(l_1w_arr[i])
                        ema21_w = float(ema21_1w_arr[i])
                        rsi_1d = float(rsi_arr[i])

                        range_w = h_w - l_w
                        candle_strength = (c_now - l_w) / range_w if range_w > 0 else 0.0
                        dist_ema_w = abs(c_now - ema21_w) / ema21_w if ema21_w > 0 else 0.0
                        breakout_margin_ok = (c_now >= up_line * P2_BREAKOUT_MARGIN)

                        vni_c2 = float(vni_c_arr[i])
                        vni_e50_2 = float(vni_ema50_arr[i])
                        vni_rsi2 = float(vni_rsi_arr[i])
                        market_ok_2 = (vni_c2 >= vni_e50_2 * P2_MARKET_EMA50_BUFFER) or (vni_rsi2 >= P2_MARKET_RSI_MIN)

                        if (breakout_margin_ok and candle_strength >= P2_CANDLE_STRENGTH_MIN and
                            dist_ema_w <= P2_MAX_DIST_EMA21W and rsi_1d <= P2_RSI_MAX and
                            mfi_w >= P2_MFI_MIN_1W and vol_r_w >= P2_VOL_RATIO_MIN_1W and market_ok_2):
                            signal_triggered = True

        # === PRESET 3: UPTREND PULLBACK NẾN NGÀY ===
        elif preset == "preset_3":
            ema21_1d = float(ema21_arr[i])
            ema50_1d = float(ema50_arr[i])
            ema120_1d = float(ema120_arr[i])

            cond_trend = (ema21_1d > ema50_1d > ema120_1d)
            dist_ema21 = abs(c_now - ema21_1d) / ema21_1d * 100.0
            cond_pullback = (dist_ema21 <= P3_MAX_DIST_EMA21_PCT)

            rsi_1d = float(rsi_arr[i])
            cond_rsi = (P3_RSI_LOW <= rsi_1d <= P3_RSI_HIGH)

            fisher_1d = float(fisher_arr[i])
            cond_fisher = (fisher_1d > P3_FISHER_MIN)

            if cond_trend and cond_pullback and cond_rsi and cond_fisher:
                if not use_enhancements:
                    signal_triggered = True
                else:
                    # TỐI ƯU HÓA PRESET 3: LỌC NẾN XẢ HÀNG & XÁC NHẬN BẬT TỪ HỖ TRỢ ĐỘNG
                    # 1. Nến bật nảy xác nhận: Nến xanh (Close >= Open) & đóng ở nửa trên thân nến ((Close - Low)/(High - Low) >= 0.50)
                    # 2. Cạn kiệt cung (Volume Dry-Up): Nến trước đó cạn cung (vol_ratio <= 1.20) và nến hiện tại không xả hàng
                    # 3. EMA21 đang dốc lên hoặc bẻ ngang: EMA21_t >= EMA21_{t-2}
                    # 4. Giá giữ vững hỗ trợ EMA21 (Close >= EMA21 * 0.99)
                    # 5. RSI ngày lành mạnh (RSI >= 45.0)
                    # 6. Top-Down Market Regime Guard: VN-Index Close >= EMA50 * 0.995 hoặc RSI >= 48.0
                    day_range = h_now - l_now
                    candle_str_1d = (c_now - l_now) / day_range if day_range > 0 else 0.0
                    bounce_confirmed = (c_now >= o_now) and (candle_str_1d >= P3_CANDLE_STRENGTH_MIN)

                    vol_r = float(vol_r_arr[i])
                    vol_r_prev = float(vol_r_arr[i - 1]) if i > 0 else 1.0
                    is_distribution_bar = (c_now < o_now) and (vol_r > 1.25)
                    vol_dryup = (vol_r_prev <= P3_VOL_DRYUP_MAX) and (not is_distribution_bar)

                    ema21_prev2 = float(ema21_arr[i - 2]) if i >= 2 else ema21_1d
                    ema21_sloping_up = (ema21_1d >= ema21_prev2)

                    holds_ema21 = (c_now >= ema21_1d * P3_EMA21_BUFFER)
                    rsi_healthy = (rsi_1d >= P3_RSI_HEALTHY)

                    vni_c = float(vni_c_arr[i])
                    vni_e50 = float(vni_ema50_arr[i])
                    vni_rsi = float(vni_rsi_arr[i])
                    market_ok = (vni_c >= vni_e50 * P3_MARKET_EMA50_BUFFER) or (vni_rsi >= P3_MARKET_RSI_MIN)

                    if (bounce_confirmed and vol_dryup and ema21_sloping_up and
                        holds_ema21 and rsi_healthy and market_ok):
                        signal_triggered = True

        if signal_triggered:
            in_trade = True
            current_trade = {
                "ticker": ticker,
                "preset": preset,
                "entry_bar": i,
                "entry_date": dt_now,
                "entry_price": c_now,
                "stop_loss": c_now * (1.0 - stop_loss_pct),
                "trailing_stop": c_now * (1.0 - stop_loss_pct),
                "target_1": c_now * (1.0 + target1_pct),
                "target_2": c_now * (1.0 + target2_pct),
                "status": "OPEN",
                "exit_date_1": None,
                "exit_price_1": None,
                "exit_date": None,
                "exit_price_final": None,
                "bars_held": 0,
                "pnl_pct": 0.0,
                "result": "OPEN"
            }

        i += 1

    if not trades:
        return {"trades": [], "summary": None}

    df_tr = pd.DataFrame(trades)
    total_trades = len(df_tr)
    wins = df_tr[df_tr['result'] == 'WIN']
    losses = df_tr[df_tr['result'] == 'LOSS']

    win_rate = (len(wins) / total_trades) * 100.0 if total_trades > 0 else 0.0
    avg_win = float(wins['pnl_pct'].mean()) if not wins.empty else 0.0
    avg_loss = float(losses['pnl_pct'].mean()) if not losses.empty else 0.0

    total_gain = float(wins['pnl_pct'].sum()) if not wins.empty else 0.0
    total_loss = abs(float(losses['pnl_pct'].sum())) if not losses.empty else 0.0
    profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 1.0)

    loss_rate = 100.0 - win_rate
    expectancy = (win_rate / 100.0 * avg_win) + (loss_rate / 100.0 * avg_loss)

    cum_returns = (1.0 + df_tr['pnl_pct'] / 100.0).cumprod()
    peak = cum_returns.cummax()
    drawdown = (cum_returns - peak) / peak * 100.0
    max_dd = abs(float(drawdown.min())) if not drawdown.empty else 0.0

    summary = {
        "ticker": ticker,
        "preset": preset,
        "enhanced": use_enhancements,
        "total_trades": total_trades,
        "win_trades": len(wins),
        "loss_trades": len(losses),
        "win_rate": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_pct": round(expectancy, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "total_cum_pnl_pct": round(float((cum_returns.iloc[-1] - 1.0) * 100.0), 2) if not cum_returns.empty else 0.0
    }

    return {"trades": trades, "summary": summary}

def run_system_audit(start_date: str = "2015-01-01", tickers: list = None) -> dict:
    """Chạy đối đầu toàn diện Baseline vs Enhanced trên các cổ phiếu thực tế trong DB."""
    if tickers is None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ticker FROM ohlcv_daily WHERE ticker != 'VNINDEX';")
        tickers = [r[0] for r in cursor.fetchall()]
        conn.close()

    audit_summary = []
    trade_samples = {}

    presets_to_test = [
        ("preset_1", "Preset 1: Bắt đáy chu kỳ 1M"),
        ("preset_2", "Preset 2: Breakout Pitchfork 1W"),
        ("preset_3", "Preset 3: Uptrend Pullback 1D")
    ]

    for preset_key, p_name in presets_to_test:
        base_sums = []
        base_trades = []
        for t in tickers:
            res_b = backtest_preset(t, preset=preset_key, start_date=start_date, use_enhancements=False)
            if res_b["summary"]:
                base_sums.append(res_b["summary"])
            if res_b["trades"]:
                base_trades.extend(res_b["trades"])

        enh_sums = []
        enh_trades = []
        for t in tickers:
            res_e = backtest_preset(t, preset=preset_key, start_date=start_date, use_enhancements=True)
            if res_e["summary"]:
                enh_sums.append(res_e["summary"])
            if res_e["trades"]:
                enh_trades.extend(res_e["trades"])

        df_b = pd.DataFrame(base_sums)
        df_e = pd.DataFrame(enh_sums)

        tot_b = int(df_b['total_trades'].sum()) if not df_b.empty else 0
        win_b = int(df_b['win_trades'].sum()) if not df_b.empty else 0
        wr_b = (win_b / tot_b * 100.0) if tot_b > 0 else 0.0
        pf_b = float(df_b['profit_factor'].median()) if not df_b.empty else 0.0
        dd_b = float(df_b['max_drawdown_pct'].mean()) if not df_b.empty else 0.0

        tot_e = int(df_e['total_trades'].sum()) if not df_e.empty else 0
        win_e = int(df_e['win_trades'].sum()) if not df_e.empty else 0
        wr_e = (win_e / tot_e * 100.0) if tot_e > 0 else 0.0
        pf_e = float(df_e['profit_factor'].median()) if not df_e.empty else 0.0
        dd_e = float(df_e['max_drawdown_pct'].mean()) if not df_e.empty else 0.0

        diff_wr = wr_e - wr_b
        diff_str = f"+{diff_wr:.1f}%" if diff_wr >= 0 else f"{diff_wr:.1f}%"

        audit_summary.append({
            "Chiến Lược": p_name,
            "Gốc - Lệnh": tot_b,
            "Gốc - WinRate (%)": round(wr_b, 1),
            "Gốc - ProfitFactor": round(pf_b, 2),
            "Gốc - MaxDD (%)": round(dd_b, 1),
            "Tối Ưu - Lệnh": tot_e,
            "Tối Ưu - WinRate (%)": round(wr_e, 1),
            "Tối Ưu - ProfitFactor": round(pf_e, 2),
            "Tối Ưu - MaxDD (%)": round(dd_e, 1),
            "Cải Thiện WinRate": diff_str
        })

        trade_samples[preset_key] = {
            "baseline_trades": base_trades[:10],
            "enhanced_trades": enh_trades[:10]
        }

    return {
        "summary_df": pd.DataFrame(audit_summary),
        "trade_samples": trade_samples,
        "tickers_count": len(tickers)
    }

if __name__ == "__main__":
    import time
    t0 = time.time()
    print("=" * 70)
    print("KIỂM ĐỊNH THỰC TIỄN HỆ THỐNG TRÊN DỮ LIỆU LỊCH SỬ THẬT (2015 - 2026)")
    print("=" * 70)
    res = run_system_audit(start_date="2015-01-01")
    elapsed = time.time() - t0
    print(f"\nThời gian chạy: {elapsed:.2f} giây trên {res['tickers_count']} mã cổ phiếu niêm yết.")
    print("\nBẢNG ĐỐI ĐẦU HIỆU SUẤT GỐC (BASELINE) VS TỐI ƯU (ENHANCED):")
    print(res["summary_df"].to_string(index=False))
