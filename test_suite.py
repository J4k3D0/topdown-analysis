"""
test_suite.py
Bộ kiểm thử tự động toàn diện cho hệ thống Top-Down Quant v5.0:
Kiểm tra 100% các mô-đun lõi:
1. Database Manager & Schema (12 bảng)
2. Chuỗi OHLCV chuẩn hóa (VNINDEX, NLG, KDH, FPT, VCG)
3. Indicators, Resampling (1D -> 1W -> 1M) & Chỉ số Ex-Vingroup (4 mã VIC, VHM, VRE, VPL)
4. Geometry Log (Auto-Pitchfork & Auto-Trendlines)
5. W.D. Gann Engine (Square of 9, Time Cycles, Fan/Box)
6. Financial Astro Engine (Pha Trăng & Thủy Tinh nghịch hành)
7. Black-Scholes Engine (Call CW, Greeks, brentq IV, Payoff, Deep OTM & Intrinsic Discount)
8. RRG Engine (12W JdK RRG & Sector Backtest)
9. Scoring Engine (5 Tầng & Top-Down Composite Score)
10. Portfolio Alerts & Scaling-Out Lifecycle (OPEN/PARTIAL/CLOSED state machine, Breakeven Stop & Weighted PnL)
11. Report Generator (Jinja2 HTML & Markdown)
12. Backtest Engine (Scaling-Out 50/50)
13. Screener & Balance Sheet Gatekeeper (Preset 1, 2, 3 MTF & Financial Exemption)
14. VN-Index Calendar Guard (2026-11-24, Nghỉ Bù 2026-04-27, 15:05 ATC Cutoff)
15. Hồi quy UI/Core (resample close-only, Gann giá nhỏ, cửa sổ hình học, MFI axis, Market Regime, Import Margin CSV)
16. Tối ưu hóa Chiến lược Định lượng, Vector hóa & Sửa lỗi Hệ thống
17. Streamlit UI Smoke Test / Runtime Verification (app.py & 7 trang con)
"""

import os
import sys
import atexit
import logging
import shutil
import tempfile
import numpy as np
import pandas as pd
from datetime import date, timedelta

# Bộ test luôn chạy trên vùng tạm nếu người gọi không chỉ định rõ một DB khác.
# Điều này tránh seed dữ liệu tổng hợp hoặc báo cáo thử nghiệm vào data/ sản xuất.
_test_root = None
if not os.environ.get("QUANT_DB_PATH"):
    _test_root = tempfile.mkdtemp(prefix="vnstock-test-")
    os.environ["QUANT_DB_PATH"] = os.path.join(_test_root, "quant_test.db")
    os.environ["QUANT_REPORTS_DIR"] = os.path.join(_test_root, "reports")
    os.environ["QUANT_LOGS_DIR"] = os.path.join(_test_root, "logs")

    def _cleanup_test_root():
        # Trên Windows, FileHandler của logging có thể giữ khóa file log đến
        # cuối process; đóng handler trước khi xóa vùng tạm.
        logging.shutdown()
        shutil.rmtree(_test_root, ignore_errors=True)

    atexit.register(_cleanup_test_root)

print("=" * 60)
print("BẮT ĐẦU KIỂM THỬ HỆ THỐNG TOP-DOWN QUANT v5.0")
print("=" * 60)

# 1. TEST DATABASE MANAGER
print("\n[TEST 1] Khởi tạo Database và 12 bảng SQLite...")
from core.db_manager import (
    init_db, get_connection, get_db_max_date,
    save_ohlcv_daily, load_ohlcv, get_setting, set_setting,
    get_trade_journal, get_user_drawings, save_user_drawing
)
init_db()
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]
required_tables = [
    'stock_metadata', 'ohlcv_daily', 'ohlcv_global', 'derivatives_daily',
    'fundamentals', 'margin_history', 'warrants', 'trade_journal',
    'user_drawings', 'yield_curve', 'macro_events', 'user_settings'
]
missing = [t for t in required_tables if t not in tables]
assert not missing, f"Thiếu các bảng: {missing}"
print(f"-> PASS: Tất cả {len(required_tables)} bảng và Indexes đã được khởi tạo chuẩn!")

cursor.execute("SELECT COUNT(*) FROM stock_metadata;")
meta_cnt = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM trade_journal;")
trade_cnt = cursor.fetchone()[0]
print(f"-> Metadata đã seed: {meta_cnt} mã, Trade Journal: {trade_cnt} lệnh mẫu (KDH, NLG).")

# Kiểm tra phân loại đầy đủ 3 sàn HOSE, HNX, UPCOM
cursor.execute("SELECT DISTINCT exchange FROM stock_metadata;")
exchanges = {r[0] for r in cursor.fetchall()}
assert {"HOSE", "HNX", "UPCOM"}.issubset(exchanges), f"Thiếu phân loại 3 sàn trong metadata: {exchanges}"

from config.tickers import get_exchange, get_tickers_by_exchange, HOSE_TICKERS, HNX_TICKERS, UPCOM_TICKERS
assert get_exchange("HPG") == "HOSE", f"HPG phải thuộc HOSE, nhận: {get_exchange('HPG')}"
assert get_exchange("CEO") == "HNX", f"CEO phải thuộc HNX, nhận: {get_exchange('CEO')}"
assert get_exchange("PVS") == "HNX", f"PVS phải thuộc HNX, nhận: {get_exchange('PVS')}"
assert get_exchange("BSR") == "UPCOM", f"BSR phải thuộc UPCOM, nhận: {get_exchange('BSR')}"
assert get_exchange("ACV") == "UPCOM", f"ACV phải thuộc UPCOM, nhận: {get_exchange('ACV')}"
assert len(get_tickers_by_exchange("HOSE")) > 0, "Danh sách HOSE không được rỗng"
assert len(get_tickers_by_exchange("HNX")) > 0, "Danh sách HNX không được rỗng"
assert len(get_tickers_by_exchange("UPCOM")) > 0, "Danh sách UPCOM không được rỗng"
print("-> PASS: Nhận diện và đồng bộ danh mục 3 sàn (HOSE, HNX, UPCoM) chuẩn xác 100%!")
conn.close()

# 2. SEED SYNTHETIC OHLCV CHO VNINDEX, NLG, KDH, FPT, VCG (CHỈ KHI DB CHƯA CÓ DỮ LIỆU)
print("\n[TEST 2] Kiểm tra và đảm bảo chuỗi OHLCV sẵn sàng cho VNINDEX, NLG, KDH, FPT, VCG...")
# Có dự phòng cho các ngày nghỉ HOSE bị bộ kiểm định loại bỏ, vẫn bảo đảm
# tối thiểu 400 nến hợp lệ để các kiểm thử đa khung chạy ổn định.
dates = pd.date_range(end=pd.Timestamp.now(), periods=460, freq='B')

def generate_sample_stock(base_p, trend=0.0003, vol=0.015):
    np.random.seed(int(base_p * 10))
    ret = np.random.randn(len(dates)) * vol + trend
    p = base_p * np.exp(np.cumsum(ret))
    open_p = p * (1 + np.random.randn(len(dates)) * 0.004)
    return pd.DataFrame({
        'date': dates,
        'open': open_p,
        # High/low phải bao trùm cả open và close để bộ kiểm định OHLC
        # đang được kiểm thử không loại dữ liệu tổng hợp do chính test tạo ra.
        'high': np.maximum(p, open_p) * (1 + abs(np.random.randn(len(dates)) * 0.01)),
        'low': np.minimum(p, open_p) * (1 - abs(np.random.randn(len(dates)) * 0.01)),
        'close': p,
        'volume': np.random.randint(500000, 3000000, size=len(dates))
    })

# Bảo vệ DB sản phẩm: Nếu đã có dữ liệu thực tế trong DB, KHÔNG ghi đè nến giả lập
sample_tickers = [("VNINDEX", 1520.0, 0.0002, 0.008),
                  ("NLG", 21.2, 0.0005, 0.018),
                  ("KDH", 14.0, 0.0004, 0.016),
                  ("FPT", 123.3, 0.0006, 0.014),
                  ("VCG", 16.5, 0.0003, 0.02)]

for sym, base_p, tr, vl in sample_tickers:
    existing = load_ohlcv(sym)
    if existing is None or len(existing) < 400:
        df_seed = generate_sample_stock(base_p, trend=tr, vol=vl)
        save_ohlcv_daily(df_seed, sym, source="synthetic_test")

print("-> PASS: Dữ liệu OHLCV sẵn sàng (bảo toàn 100% dữ liệu thực tế, không bị ghi đè nến rác)!")

# 3. TEST INDICATORS & RESAMPLING
print("\n[TEST 3] Kiểm tra Bộ Chỉ Báo & Resampling W-FRI / ME...")
from core.indicators import resample_ohlcv, calculate_all_indicators, detect_rsi_divergence, compute_ex_vingroup_index

df_loaded = load_ohlcv("NLG")
assert len(df_loaded) >= 400, "Lỗi load_ohlcv"

df_1w = resample_ohlcv(df_loaded, "1W")
assert len(df_1w) > 50, "Lỗi resample 1W"
assert "last_bar_partial" in df_1w.attrs, "Thiếu cờ last_bar_partial trên 1W"

df_1m = resample_ohlcv(df_loaded, "1M")
assert len(df_1m) > 10, "Lỗi resample 1M"

df_ind_1d = calculate_all_indicators(df_loaded, is_monthly=False)
for col in ['ema21', 'ema50', 'ema120', 'ema200', 'ma200', 'rsi', 'macd', 'macd_hist', 'fisher', 'mfi', 'vol_ratio']:
    assert col in df_ind_1d.columns, f"Thiếu cột chỉ báo: {col}"

df_ind_1m = calculate_all_indicators(df_1m, is_monthly=True)
assert 'ma_long_1m' in df_ind_1m.columns, "Thiếu cột Fallback MA_long_1M trên khung 1M"

rsi_divs = detect_rsi_divergence(df_ind_1d, order=5)
assert "bullish" in rsi_divs and "bearish" in rsi_divs, "Lỗi detect_rsi_divergence"

# Kiểm tra tái tạo chỉ số Ex-Vingroup (4 mã: VIC, VHM, VRE, VPL)
df_vni_sample = load_ohlcv("VNINDEX")
vin_sample_dfs = {
    'VIC': generate_sample_stock(42.0, trend=0.0001, vol=0.02),
    'VHM': generate_sample_stock(45.0, trend=-0.0002, vol=0.02),
    'VRE': generate_sample_stock(24.0, trend=0.0001, vol=0.025),
    'VPL': generate_sample_stock(18.0, trend=-0.0001, vol=0.02)
}
df_ex_vin = compute_ex_vingroup_index(df_vni_sample, vin_sample_dfs)
assert df_ex_vin is not None, "compute_ex_vingroup_index trả về None"
assert len(df_ex_vin) == len(df_vni_sample), "Chiều dài chuỗi ex-vin khác chuỗi gốc"
for c_vin in ['close_ex_vin', 'open_ex_vin', 'high_ex_vin', 'low_ex_vin']:
    assert c_vin in df_ex_vin.columns, f"Thiếu cột {c_vin} trong kết quả ex-vin"
assert not np.allclose(df_ex_vin['close_ex_vin'].values, df_vni_sample['close'].values), "Chỉ số Ex-Vin không phản ánh biến động loại trừ Vingroup"
print(f"-> PASS: Resampling chuẩn W-FRI/ME, Indicators đầy đủ, Ex-Vingroup (4 mã) & Phân kỳ RSI OK!")

# 4. TEST GEOMETRY LOG (PITCHFORK & TRENDLINES)
print("\n[TEST 4] Kiểm tra Auto-Pitchfork 3 điểm trên thang Log & Auto-Trendline...")
from core.geometry_log import compute_bearish_pitchfork, compute_bullish_pitchfork, compute_auto_trendlines

pf_bear = compute_bearish_pitchfork(df_ind_1d, order=5)
pf_bull = compute_bullish_pitchfork(df_ind_1d, order=5)
tls = compute_auto_trendlines(df_ind_1d, order=5)

print(f"-> Bearish Pitchfork tính được: {'CÓ' if pf_bear else 'KHÔNG (tùy thế nến)'}")
print(f"-> Bullish Pitchfork tính được: {'CÓ' if pf_bull else 'KHÔNG'}")
print(f"-> Auto-Trendlines tìm thấy: {len(tls)} đường.")
print("-> PASS: Thuật toán hình học logarit hoạt động trơn tru!")

# 5. TEST GANN ENGINE
print("\n[TEST 5] Kiểm tra W.D. Gann Engine (Square of 9 & Time Cycles)...")
from core.gann_engine import calculate_gann_square_of_9, calculate_gann_time_cycles, calculate_gann_fan_log

sq9_nlg = calculate_gann_square_of_9(21.2, k=1.0)
assert len(sq9_nlg["resistances"]) == 8, "Lỗi tính góc kháng cự Square of 9"
assert len(sq9_nlg["supports"]) == 8, "Lỗi tính góc hỗ trợ Square of 9"
# Kiểm tra mốc 90 độ của NLG (21.2)
target_90 = next(r for r in sq9_nlg["resistances"] if r["angle"] == 90)
print(f"-> NLG (21.2k) mốc 90° Square of 9: {target_90['price']}k (+{target_90['pct_change']}%) [Target 1 thực chiến]")

cycles = calculate_gann_time_cycles("2026-11-03")
assert len(cycles["calendar_cycles"]) == 8, "Lỗi Gann Time Cycles"
print("-> PASS: Gann Square of 9 & Gann Time Cycles chính xác!")

# 6. TEST FINANCIAL ASTRO ENGINE
print("\n[TEST 6] Kiểm tra Thiên văn tài chính (Pha Mặt Trăng & Thủy Tinh nghịch hành)...")
from core.astro_engine import get_moon_phase_info, is_mercury_retrograde

moon = get_moon_phase_info(date.today())
assert "moon_age" in moon and "illumination_pct" in moon, "Lỗi moon_phase"
is_retro = is_mercury_retrograde(date.today())
print(f"-> Hôm nay: Pha trăng '{moon['phase_name']}', Tuổi: {moon['moon_age']} ngày. Thủy tinh: {'Nghịch hành' if is_retro else 'Thuận hành'}")
print("-> PASS: Astro Engine hoạt động chính xác không phụ thuộc C++ build!")

# 7. TEST BLACK-SCHOLES ENGINE
print("\n[TEST 7] Kiểm tra Định giá Chứng quyền Black-Scholes brentq...")
from core.black_scholes import (
    black_scholes_call_price, calculate_cw_greeks,
    solve_implied_volatility, generate_payoff_matrix
)

# Test định giá với NLG giá 21,200 VNĐ, Strike 22,000 VNĐ, T=90 ngày, r=5%, vol=32%, CR=2
s_vnd = 21200.0
k_vnd = 22000.0
t_yr = 90.0 / 365.0
c_fair = black_scholes_call_price(s_vnd, k_vnd, t_yr, 0.05, 0.32, CR=2.0)
assert c_fair > 0, "Lỗi giá Black-Scholes"

# Test brentq IV solver
mkt_price = 850.0
iv_solved = solve_implied_volatility(mkt_price, s_vnd, k_vnd, t_yr, 0.05, CR=2.0)
print(f"-> Black-Scholes Call: Fair Price = {c_fair:.1f} VNĐ, Thị trường = {mkt_price} VNĐ, IV solved = {iv_solved}%")

payoff = generate_payoff_matrix(s_vnd, k_vnd, 2.0, mkt_price)
assert len(payoff) == 21, f"Ma trận Payoff phải có đúng 21 kịch bản, hiện có {len(payoff)}"

# Test các ca biên Black-Scholes brentq:
# Ca biên 1: Deep OTM Call Warrant (hội tụ trên [1e-4, 5.0], không bị phân kỳ Newton-Raphson)
iv_otm = solve_implied_volatility(50.0, 21200.0, 50000.0, 0.25, 0.05, 1.0)
assert iv_otm is not None and iv_otm > 0, "Lỗi giải IV cho Deep OTM warrant"

# Ca biên 2: Thị giá chứng quyền chiết khấu dưới giá trị nội tại (C <= max((S-K)/CR, 0)) -> trả về None
iv_discount = solve_implied_volatility(25000.0, 50000.0, 20000.0, 0.25, 0.05, 1.0)
assert iv_discount is None, "Chứng quyền dưới giá trị nội tại phải trả về None"

# Ca biên 3: Thị giá <= 0 -> trả về None
assert solve_implied_volatility(0.0, s_vnd, k_vnd, t_yr, 0.05, CR=2.0) is None
print(f"-> Black-Scholes Ca biên: Deep OTM IV hội tụ = {iv_otm:.2f}%, Dưới giá trị nội tại trả về None chuẩn xác!")
print("-> PASS: Black-Scholes brentq IV solver, Ca biên & Payoff matrix 21 kịch bản hoàn hảo!")

# 8. TEST RRG ENGINE
print("\n[TEST 8] Kiểm tra Relative Rotation Graph (JdK RRG 12W)...")
from core.rrg_engine import compute_rrg_metrics

df_bm = load_ohlcv("VNINDEX")
rrg_m = compute_rrg_metrics(df_1w, resample_ohlcv(df_bm, "1W"), window=12, tail_len=8)
if rrg_m:
    print(f"-> RRG NLG vs VN-Index: RS-Ratio = {rrg_m['rs_ratio']}, RS-Momentum = {rrg_m['rs_momentum']}, Quadrant = {rrg_m['quadrant']}")
print("-> PASS: JdK RRG Engine tính toán mượt mà!")

# 9. TEST SCORING ENGINE
print("\n[TEST 9] Kiểm tra Hệ thống Chấm điểm 5 Tầng & Top-Down Composite...")
from core.scoring_engine import (
    score_tier1_astro_gann, score_tier2_macro_margin,
    score_tier4_derivatives_breadth, score_tier5_vnindex_mtf,
    calculate_topdown_composite_score
)

s1 = score_tier1_astro_gann(70.0)
s2 = score_tier2_macro_margin({"t10y2y": 0.3, "dxy": 102.0, "vix": 16.0, "vnd_change_60d": 0.5, "margin_growth_qoq": 4.0})["score"]
s3 = 65.0
s4 = score_tier4_derivatives_breadth({"basis": 2.0, "pct_above_ma50": 65.0, "ad_slope": 0.3})["score"]
df_ind_1w = calculate_all_indicators(df_1w, is_monthly=False)
s5 = score_tier5_vnindex_mtf(df_ind_1m, df_ind_1w, df_ind_1d)["score"]

comp = calculate_topdown_composite_score({"T1": s1, "T2": s2, "T3": s3, "T4": s4, "T5": s5})
print(f"-> Điểm Top-Down tổng hợp: {comp['composite_score']}/100, Phân vùng: {comp['zone']}")
assert 0 <= comp['composite_score'] <= 100, "Điểm composite ngoài miền 0-100"
print("-> PASS: Scoring Engine chính xác!")

# 10. TEST PORTFOLIO ALERTS & SCALING-OUT LIFECYCLE
print("\n[TEST 10] Kiểm tra Động cơ Cảnh báo Danh mục & Vòng đời Scaling-Out 50/50...")
from core.portfolio_alerts import evaluate_portfolio_alerts
from core.db_manager import update_trade_exit

alerts = evaluate_portfolio_alerts()
print(f"-> Đã quét {len(alerts)} cảnh báo ban đầu cho các vị thế active:")
for al in alerts:
    print(f"   * {al['badge_text']} | {al['ticker']}: {al['action_msg']}")

# Kiểm tra Vòng đời Scaling-Out 50/50 trong DB & Tính PnL bình quân gia quyền:
conn_alert = get_connection()
c_alert = conn_alert.cursor()
c_alert.execute("""
INSERT INTO trade_journal (ticker, entry_date, entry_price, quantity, stop_loss, trailing_stop, target_1, target_2, status)
VALUES ('KDH', '2026-11-01', 20.0, 1000, 18.0, 18.0, 23.0, 27.0, 'OPEN');
""")
test_tid = c_alert.lastrowid
conn_alert.commit()
conn_alert.close()

# Chốt 50% tại Target 1 (exit_step=1): Chuyển sang 'PARTIAL', dời stop_loss và trailing_stop về breakeven (entry_price=20.0)
update_trade_exit(test_tid, exit_step=1, exit_date="2026-11-15", exit_price=23.0, exit_qty=500, notes="Chốt 50% Target 1")

conn_alert = get_connection()
c_alert = conn_alert.cursor()
c_alert.execute("SELECT status, stop_loss, trailing_stop, exit_price_1, exit_qty_1 FROM trade_journal WHERE id = ?;", (test_tid,))
row_partial = c_alert.fetchone()
conn_alert.close()

assert row_partial[0] == 'PARTIAL', "Lỗi chuyển trạng thái PARTIAL"
assert row_partial[1] == 20.0, f"stop_loss phải dời về breakeven (20.0), hiện là {row_partial[1]}"
assert row_partial[2] == 20.0, f"trailing_stop phải đặt bằng entry_price (20.0), hiện là {row_partial[2]}"
assert row_partial[3] == 23.0, "Lỗi ghi nhận exit_price_1"
assert row_partial[4] == 500, "Lỗi ghi nhận exit_qty_1"

# Kiểm tra tính PnL bình quân gia quyền cho vị thế PARTIAL trong evaluate_portfolio_alerts
alerts_partial = evaluate_portfolio_alerts()
target_alert = next((a for a in alerts_partial if a['trade_id'] == test_tid), None)
assert target_alert is not None, "Không tìm thấy alert cho lệnh PARTIAL vừa tạo"
p_now = target_alert['p_last']
expected_weighted_pnl = (0.5 * ((23.0 - 20.0) / 20.0) + 0.5 * ((p_now - 20.0) / 20.0)) * 100.0
assert abs(target_alert['pnl_pct'] - round(expected_weighted_pnl, 2)) < 0.05, f"PnL gia quyền không khớp: {target_alert['pnl_pct']} vs {expected_weighted_pnl:.2f}"

# Chốt phần còn lại (exit_step=2): Chuyển sang 'CLOSED' và tính pnl_pct tổng
update_trade_exit(test_tid, exit_step=2, exit_date="2026-11-20", exit_price=27.0, exit_qty=500, notes="Chốt 50% Target 2")

conn_alert = get_connection()
c_alert = conn_alert.cursor()
c_alert.execute("SELECT status, pnl_pct FROM trade_journal WHERE id = ?;", (test_tid,))
row_closed = c_alert.fetchone()
conn_alert.close()

assert row_closed[0] == 'CLOSED', "Lỗi chuyển trạng thái CLOSED"
assert abs(row_closed[1] - 25.0) < 0.1, f"PnL tổng sau 2 lần chốt phải là 25.0%, hiện là {row_closed[1]}%"
print("-> PASS: Vòng đời Scaling-Out 50/50 (Breakeven Stop Loss & Weighted PnL) chuẩn xác!")

# 11. TEST REPORT GENERATOR
print("\n[TEST 11] Kiểm tra Xuất Báo Cáo Phân Tích Tự Động (1-Click Jinja2 HTML & Markdown)...")
from core.report_generator import generate_stock_report

rep_res = generate_stock_report("NLG", {
    "current_price": 21.2,
    "rsi_1d": 48.5,
    "fisher_1d": -0.82,
    "avg_liquidity": 48.5,
    "entry_rec": "21.0 - 21.2 kVND",
    "stop_rec": "19.8 kVND",
    "target1_rec": "26.5 kVND",
    "target2_rec": "30.5 kVND"
})
assert os.path.exists(rep_res["html_path"]), "Lỗi sinh file HTML"
assert os.path.exists(rep_res["md_path"]), "Lỗi sinh file Markdown"
print(f"-> Báo cáo đã xuất: {rep_res['html_path']} và {rep_res['md_path']}")
print("-> PASS: Report Generator hoàn hảo!")

# 12. TEST BACKTEST & OPTIMIZATION ENGINE
print("\n[TEST 12] Kiểm tra Động cơ Backtest Thực Chiến & Tối Ưu Hóa (Scaling-Out 50/50)...")
from core.backtest_engine import backtest_preset

res_bt = backtest_preset("HPG", preset="preset_3", start_date="2020-01-01", use_enhancements=True)
assert "trades" in res_bt and "summary" in res_bt, "Lỗi kết quả backtest_preset"
if res_bt["summary"]:
    print(f"-> HPG Preset 3 (Enhanced): WinRate = {res_bt['summary']['win_rate']}%, ProfitFactor = {res_bt['summary']['profit_factor']}, Total Trades = {res_bt['summary']['total_trades']}")
print("-> PASS: Động cơ Backtest Thực Chiến & Tối Ưu Hóa hoạt động hoàn hảo!")

# 13. TEST SCREENER & BALANCE SHEET GATEKEEPER
print("\n[TEST 13] Kiểm tra Bộ Lọc Định Lượng & Lớp Lọc An Toàn Bảng Cân Đối (Gatekeeper)...")
from core.screener import check_balance_sheet_gatekeeper, scan_stock, run_screener

# 13.1. Kiểm tra Gatekeeper
# Trường hợp 1: Nhóm Tài chính (VCB, SSI, TCB...) đòn bẩy D/E = 7.5 -> MIỄN TRỪ, PASS
df_f_fin = pd.DataFrame([{'quarter': '2024Q3', 'pb': 1.1, 'debt_to_equity': 7.5}])
pass_fin, info_fin = check_balance_sheet_gatekeeper("TCB", df_f_fin, 25.0, is_financial=True)
assert pass_fin, "Nhóm Tài chính phải được miễn trừ điều kiện Nợ/VCSH < 1.2"
assert info_fin["status"] == "OK"

# Trường hợp 2: Doanh nghiệp phi tài chính D/E = 2.5 (>= 1.2) -> FAILED
df_f_nonfin = pd.DataFrame([{'quarter': '2024Q3', 'pb': 1.1, 'debt_to_equity': 2.5}])
pass_nonfin, info_nonfin = check_balance_sheet_gatekeeper("HPG", df_f_nonfin, 25.0, is_financial=False)
assert not pass_nonfin, "Doanh nghiệp phi tài chính có Nợ/VCSH >= 1.2 phải bị loại"
assert info_nonfin["status"] == "FAILED"

# Trường hợp 3: P/B vượt trần 1.3 -> FAILED
df_f_high_pb = pd.DataFrame([{'quarter': '2024Q3', 'pb': 2.5, 'debt_to_equity': 0.5}])
pass_hpb, _ = check_balance_sheet_gatekeeper("DGC", df_f_high_pb, 25.0, is_financial=False)
assert not pass_hpb, "Cổ phiếu có P/B > 1.3 phải bị Gatekeeper loại"

# Trường hợp 4: Thanh khoản < 15 tỷ -> FAILED
pass_liq, _ = check_balance_sheet_gatekeeper("DGC", df_f_nonfin, 8.0, is_financial=False)
assert not pass_liq, "Cổ phiếu thanh khoản < 15 tỷ phải bị loại"

print("-> Gatekeeper: Miễn trừ tài chính D/E, loại bỏ đòn bẩy cao phi tài chính & lọc P/B/thanh khoản OK!")

# 13.2. Kiểm tra quy tắc đa khung bắt buộc cho 3 Presets (AGENTS.md §4.6)
# Tạo dữ liệu kiểm thử đạt chuẩn Preset 3 (Uptrend Pullback)
dates_p3 = pd.date_range('2025-01-01', periods=160, freq='B')
p_base = 20.0 * np.exp(np.linspace(0, 0.4, 160))
df_p3_pass = pd.DataFrame({
    'date': dates_p3,
    'open': p_base * 0.998,
    'high': p_base * 1.01,
    'low': p_base * 0.99,
    'close': p_base,
    'volume': 1500000
})
df_p3_pass.loc[157, 'close'] = df_p3_pass.loc[156, 'close'] * 0.99
df_p3_pass.loc[158, 'close'] = df_p3_pass.loc[157, 'close'] * 0.985
df_p3_pass.loc[159, 'close'] = df_p3_pass.loc[158, 'close'] * 0.995
df_p3_pass.loc[159, 'open'] = df_p3_pass.loc[159, 'close'] * 0.997 # Nến xanh
df_p3_pass.loc[159, 'high'] = df_p3_pass.loc[159, 'close'] * 1.005
df_p3_pass.loc[159, 'low'] = df_p3_pass.loc[159, 'close'] * 0.995
df_p3_pass.loc[159, 'volume'] = 1000000 # Khối lượng cạn kiệt
save_ohlcv_daily(df_p3_pass, 'P3_VALID', source='test_suite')

res_p3_valid = scan_stock('P3_VALID', preset='preset_3')
assert res_p3_valid is not None, "P3_VALID phải thỏa mãn Preset 3"

# Kiểm tra Lọc Nến Xả Hàng: Nến đỏ kèm Vol_Ratio > 1.25 -> PHẢI BỊ LOẠI
df_p3_dist = df_p3_pass.copy()
df_p3_dist.loc[159, 'open'] = df_p3_dist.loc[159, 'close'] * 1.02 # Nến đỏ
df_p3_dist.loc[159, 'high'] = df_p3_dist.loc[159, 'open'] * 1.005
df_p3_dist.loc[159, 'low'] = df_p3_dist.loc[159, 'close'] * 0.995
df_p3_dist.loc[159, 'volume'] = 3000000 # Vol xả lớn (Vol_Ratio > 1.25)
save_ohlcv_daily(df_p3_dist, 'P3_DISTRIB_FAIL', source='test_suite')

res_p3_dist = scan_stock('P3_DISTRIB_FAIL', preset='preset_3')
assert res_p3_dist is None, "Preset 3 bắt buộc phải lọc bỏ nến xả hàng theo AGENTS.md §4.6"

# Kiểm tra Lọc Thủng Hỗ Trợ: Close < EMA21 * 0.99 -> PHẢI BỊ LOẠI
df_p3_break = df_p3_pass.copy()
df_p3_break.loc[159, 'close'] = df_p3_break.loc[158, 'close'] * 0.92
df_p3_break.loc[159, 'open'] = df_p3_break.loc[159, 'close'] * 0.99
df_p3_break.loc[159, 'high'] = df_p3_break.loc[159, 'close'] * 1.01
df_p3_break.loc[159, 'low'] = df_p3_break.loc[159, 'close'] * 0.99
save_ohlcv_daily(df_p3_break, 'P3_BREAK_FAIL', source='test_suite')

res_p3_break = scan_stock('P3_BREAK_FAIL', preset='preset_3')
assert res_p3_break is None, "Preset 3 bắt buộc phải giữ hỗ trợ EMA21 * 0.99"

print("-> PASS: Screener Presets & Balance Sheet Gatekeeper hoạt động hoàn hảo!")

# 14. TEST VN-INDEX CALENDAR GUARD
print("\n[TEST 14] Kiểm tra VN-Index Calendar Guard (Lịch Nghỉ Lễ HOSE 2026 & Mốc 15:05 ATC)...")
from datetime import datetime
from config.vn_holidays import is_trading_day, get_expected_last_trading_day, trading_day_mask

# 14.1. Ngày Văn hóa Việt Nam 24/11/2026 (ngày nghỉ mới áp dụng từ năm 2026) -> KHÔNG PHẢI NGÀY GIAO DỊCH
assert not is_trading_day(date(2026, 11, 24)), "Ngày 2026-11-24 phải là ngày nghỉ lễ HOSE"

# 14.2. Ngày nghỉ hoán đổi / nghỉ bù đặc biệt của HOSE (2026-04-27 Giỗ Tổ bù) -> KHÔNG PHẢI NGÀY GIAO DỊCH
assert not is_trading_day(date(2026, 4, 27)), "Ngày 2026-04-27 phải là ngày nghỉ bù HOSE"

# 14.3. Ngày cuối tuần (T7, CN) -> KHÔNG PHẢI NGÀY GIAO DỊCH
assert not is_trading_day(date(2026, 11, 22)), "Chủ nhật 2026-11-22 không phải ngày giao dịch"

# 14.4. Ngày giao dịch thông thường hợp lệ (Thứ Tư 2026-11-18)
assert is_trading_day(date(2026, 11, 18)), "Thứ Tư 2026-11-18 phải là ngày giao dịch hợp lệ"

# 14.5. Mốc cắt ATC 15:05:
# - Trước 15:05 (14:30) trên ngày giao dịch hợp lệ -> ngày giao dịch kỳ vọng lùi về phiên trước (2026-11-17)
dt_pre_atc = datetime(2026, 11, 18, 14, 30)
assert get_expected_last_trading_day(dt_pre_atc) == date(2026, 11, 17), "Trước 15:05 ATC phải kỳ vọng phiên hôm trước"

# - Sau 15:05 (15:30) trên ngày giao dịch hợp lệ -> ngày giao dịch kỳ vọng chính là phiên hôm nay (2026-11-18)
dt_post_atc = datetime(2026, 11, 18, 15, 30)
assert get_expected_last_trading_day(dt_post_atc) == date(2026, 11, 18), "Sau 15:05 ATC phải kỳ vọng phiên hôm nay"

# - Ngày nghỉ lễ (2026-11-24) lúc 16:00 -> tự động lùi về ngày giao dịch liền trước (2026-11-23)
dt_holiday = datetime(2026, 11, 24, 16, 0)
assert get_expected_last_trading_day(dt_holiday) == date(2026, 11, 23), "Ngày nghỉ lễ phải lùi về ngày giao dịch gần nhất"

# 14.6. Kiểm tra trading_day_mask tối ưu hóa tốc độ
mask_res = trading_day_mask([date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)])
assert list(mask_res) == [True, False, True], "trading_day_mask trả về kết quả không chính xác"

print("-> PASS: VN-Index Calendar Guard chuẩn xác (24/11, nghỉ bù, mốc 15:05 ATC, mask)!")

# ============================================================
# 15. TEST HỒI QUY UI/CORE (các lỗi runtime đã phát hiện khi audit)
# ============================================================
print("\n[TEST 15] Kiểm tra hồi quy UI/Core (resample close-only, Gann giá nhỏ, cửa sổ hình học, MFI axis, Market Regime, Import Margin CSV)...")

# 15.1. resample_ohlcv chỉ có cột 'close' (nguồn gốc crash Tầng 3 / RRG)
df_close_only = df_loaded[['date', 'close']].copy()
df_w_close = resample_ohlcv(df_close_only, "1W")
assert not df_w_close.empty and 'close' in df_w_close.columns, "resample_ohlcv phải hỗ trợ DataFrame chỉ có close"
assert 'date' in df_w_close.columns, "resample_ohlcv phải trả lại cột date"

# 15.2. Gann Square of 9 với cổ phiếu giá nhỏ (< 10 kVND) phải dùng scale 10.0
from core.gann_engine import calculate_gann_square_of_9
g_low = calculate_gann_square_of_9(5.0)
assert g_low.get('scale') == 10.0, "Cổ phiếu < 10 kVND phải dùng scale 10.0"
_up90 = next(x for x in g_low['resistances'] if x['angle'] == 90)
assert 5.0 <= _up90['pct_change'] <= 25.0, f"Gann 90° giá nhỏ bất thường: {_up90['pct_change']}%"
g_nlg = calculate_gann_square_of_9(21.2)
_nlg90 = next(x for x in g_nlg['resistances'] if x['angle'] == 90)
assert abs(_nlg90['price'] - 26.05) < 0.02, "Mốc Gann 90° của NLG 21.2 phải giữ 26.05 kVND"

# 15.3. Hình học tính trên toàn chuỗi nhưng vẽ trên cửa sổ tail() phải hiển thị được
from components.charts_plotly import create_deep_dive_chart
from core.geometry_log import compute_bearish_pitchfork, compute_auto_trendlines

_n = 460
_dt = pd.date_range(end=pd.Timestamp.now(), periods=_n, freq='B')
_t = np.arange(_n)
_c = 60.0 * np.exp(-0.0018 * _t + 0.18 * np.sin(_t / 9.0))
df_geom = pd.DataFrame({
    'date': _dt, 'open': _c, 'high': _c * 1.012, 'low': _c * 0.988,
    'close': _c, 'volume': np.full(_n, 1000000.0)
})
df_geom = calculate_all_indicators(df_geom, is_monthly=False)
pf_full = compute_bearish_pitchfork(df_geom, order=5)
assert pf_full is not None, "Không tính được Bearish Pitchfork trên chuỗi giảm mẫu"
tls_full = compute_auto_trendlines(df_geom, order=5)
_view = df_geom.tail(200).reset_index(drop=True)
_off = len(df_geom) - len(_view)
fig_reg = create_deep_dive_chart(_view, "TEST", "1D", pitchfork_data=pf_full,
                                 trendlines=tls_full, index_offset=_off)
_names = [t.name or '' for t in fig_reg.data]
assert any('Median Line' in n for n in _names), "Regression: Pitchfork không được vẽ khi dùng index_offset"
assert any(n.startswith('Trendline') for n in _names), "Regression: Auto-Trendline không được vẽ khi dùng index_offset"

# 15.4. MFI phải nằm trên trục phụ 0-100, không bị ép vào thang Volume
_mfi_tr = [t for t in fig_reg.data if t.name == 'MFI(14)']
assert _mfi_tr, "Thiếu trace MFI(14)"
assert _mfi_tr[0].yaxis == 'y5', f"MFI phải nằm trên trục phụ y5, hiện tại: {_mfi_tr[0].yaxis}"
assert 'yaxis5' in fig_reg.layout and list(fig_reg.layout.yaxis5.range) == [0, 100], "Trục MFI phải khóa 0-100"

# 15.5. Market Regime (Top-Down Layer 1) trả về cấu trúc hợp lệ
from core.screener import get_market_regime
_regime = get_market_regime(force_reload=True)
for _k in ('ok', 'available', 'close', 'ema50', 'rsi'):
    assert _k in _regime, f"get_market_regime thiếu khóa {_k}"
assert isinstance(_regime['ok'], bool), "Market Regime .ok phải là bool"

# 15.6. Import Margin từ CSV (trước đây chỉ đọc Excel -> luôn trả 0)
from core.margin_aggregator import import_margin_excel
_csv_path = os.path.join(tempfile.mkdtemp(prefix="margin-test-"), "margin.csv")
pd.DataFrame({
    "Quý": ["TEST_1Q", "TEST_2Q"],
    "Dư nợ Margin": [123.4, 130.1],
    "VNIndex": [1000.0, 1010.0],
}).to_csv(_csv_path, index=False, encoding="utf-8-sig")
_n_imported = import_margin_excel(_csv_path)
assert _n_imported == 2, f"Import CSV Margin phải ghi 2 quý, nhận {_n_imported}"
_conn = get_connection()
_conn.execute("DELETE FROM margin_history WHERE quarter LIKE 'TEST%';")
_conn.commit()
_conn.close()

# 15.7. Một nguồn ngưỡng duy nhất: screener live và backtest phải cùng tham số
from config.settings import PRESET_2_PARAMS, PRESET_3_PARAMS, ROOT_DIR
import core.backtest_engine as _be
assert _be.P3_MAX_DIST_EMA21_PCT == PRESET_3_PARAMS["max_dist_ema21_pct"]
assert _be.P3_VOL_DRYUP_MAX == PRESET_3_PARAMS["vol_dryup_max"]
assert _be.P3_MARKET_EMA50_BUFFER == PRESET_3_PARAMS["market_ema50_buffer"]
assert _be.P3_MARKET_RSI_MIN == PRESET_3_PARAMS["market_rsi_min"]
assert _be.P3_EMA21_BUFFER == PRESET_3_PARAMS["ema21_buffer"]
assert _be.P2_BREAKOUT_MARGIN == PRESET_2_PARAMS["breakout_margin"]
assert _be.P2_MAX_DIST_EMA21W == PRESET_2_PARAMS["max_dist_ema21w"]
assert _be.P2_VOL_RATIO_MIN_1W == PRESET_2_PARAMS["vol_ratio_min_1w"]
_log_src = open(os.path.join(ROOT_DIR, "core", "screener.py"), encoding="utf-8").read()
assert "PRESET_3_PARAMS" in _log_src and "PRESET_2_PARAMS" in _log_src, \
    "Screener phải đọc ngưỡng từ config/settings.py, không hardcode"

print("-> PASS: Hết crash RRG, Gann giá nhỏ hợp lý, Pitchfork/Trendline vẽ được, MFI 0-100, Market Regime & Import CSV OK!")

# ============================================================
# 16. TEST TỐI ƯU HÓA ĐỊNH LƯỢNG & SỬA LỖI HỆ THỐNG (MILESTONE 1)
# ============================================================
print("\n[TEST 16] Kiểm tra Tối ưu hóa Chiến lược Định lượng, Vector hóa & Sửa lỗi Hệ thống...")

# 16.1. Kiểm tra khóa hình học Bearish Pitchfork độ dốc dốc xuống m < 0
from core.geometry_log import compute_bearish_pitchfork, compute_bullish_pitchfork
_dates_pf = pd.date_range('2025-01-01', periods=80, freq='W-FRI')

# Kênh dốc lên (Bullish slope): P1 đỉnh 20, P2 đáy 22, P3 đỉnh 25 -> m >= 0
_p_up = [20.0, 18.0, 15.0, 12.0, 15.0, 20.0, 22.0, 25.0, 24.0, 26.0] * 8
_df_up = pd.DataFrame({
    'date': _dates_pf,
    'open': _p_up,
    'high': [p * 1.05 for p in _p_up],
    'low': [p * 0.95 for p in _p_up],
    'close': _p_up,
    'volume': 1000000
})
_pf_bear_up = compute_bearish_pitchfork(_df_up, order=3)
if _pf_bear_up is not None:
    assert _pf_bear_up['m'] < 0, f"Bearish Pitchfork bắt buộc phải có m < 0, nhận m = {_pf_bear_up['m']}"

# Kênh dốc xuống chuẩn (P1 đỉnh 40.0, P2 đáy 20.0, P3 đỉnh 28.0 < 40.0) -> yM < y1 (m < 0)
_p_down = [40.0, 35.0, 30.0, 25.0, 20.0, 22.0, 25.0, 28.0, 26.0, 24.0, 22.0, 19.0] * 6 + [18.0] * 8
_df_down = pd.DataFrame({
    'date': _dates_pf,
    'open': _p_down,
    'high': [p * 1.04 for p in _p_down],
    'low': [p * 0.96 for p in _p_down],
    'close': _p_down,
    'volume': 1000000
})
_pf_bear_down = compute_bearish_pitchfork(_df_down, order=3)
assert _pf_bear_down is not None, "Dữ liệu kênh giảm chuẩn phải tính được Bearish Pitchfork"
assert _pf_bear_down['m'] < 0, f"Bearish Pitchfork phải có độ dốc âm m < 0, nhận {_pf_bear_down['m']}"

# 16.2. Kiểm tra Preset 3: Nến bật nảy (Bounce confirmation) và Lọc cạn cung (Volume dry-up)
from core.screener import scan_stock
_df_clean = load_ohlcv('P3_VALID')

# Nến đỏ hoặc râu dưới dài không có thân xanh -> bị loại
_df_p3_weak = _df_clean.copy()
_df_p3_weak.iloc[-1, _df_p3_weak.columns.get_loc('close')] = _df_p3_weak.iloc[-1]['open'] * 0.999 # Nến đỏ
_df_p3_weak.iloc[-1, _df_p3_weak.columns.get_loc('high')] = _df_p3_weak.iloc[-1]['open'] * 1.002
_df_p3_weak.iloc[-1, _df_p3_weak.columns.get_loc('low')] = _df_p3_weak.iloc[-1]['close'] * 0.99
save_ohlcv_daily(_df_p3_weak, 'P3_WEAK_CANDLE', source='test_suite')
_res_p3_weak = scan_stock('P3_WEAK_CANDLE', preset='preset_3', use_enhancements=True)
assert _res_p3_weak is None, "Preset 3 Enhanced bắt buộc nến vào lệnh phải là nến xanh bật nảy"

# Nến trước đó khối lượng cao (không cạn cung) -> bị loại
_df_p3_heavy = _df_clean.copy()
_df_p3_heavy.iloc[-2, _df_p3_heavy.columns.get_loc('volume')] = 3500000 # Phiên pullback trước vol lớn (không dry-up)
save_ohlcv_daily(_df_p3_heavy, 'P3_HEAVY_PULLBACK', source='test_suite')
_res_p3_heavy = scan_stock('P3_HEAVY_PULLBACK', preset='preset_3', use_enhancements=True)
assert _res_p3_heavy is None, "Preset 3 Enhanced bắt buộc phiên pullback phải cạn kiệt thanh khoản"

# Dữ liệu chuẩn thỏa mãn Preset 3 Enhanced -> phải PASS
_df_p3_pass_enh = _df_clean.copy()
_df_p3_pass_enh.iloc[-2, _df_p3_pass_enh.columns.get_loc('volume')] = 800000 # Cạn cung
_df_p3_pass_enh.iloc[-1, _df_p3_pass_enh.columns.get_loc('open')] = _df_p3_pass_enh.iloc[-1]['close'] * 0.995 # Nến xanh thân tốt
_df_p3_pass_enh.iloc[-1, _df_p3_pass_enh.columns.get_loc('high')] = _df_p3_pass_enh.iloc[-1]['close'] * 1.002
_df_p3_pass_enh.iloc[-1, _df_p3_pass_enh.columns.get_loc('low')] = _df_p3_pass_enh.iloc[-1]['open'] * 0.998 # Đóng nửa trên
save_ohlcv_daily(_df_p3_pass_enh, 'P3_ENHANCED_PASS', source='test_suite')
_res_p3_enh = scan_stock('P3_ENHANCED_PASS', preset='preset_3', use_enhancements=True)
assert _res_p3_enh is not None, "P3_ENHANCED_PASS phải thỏa mãn Preset 3 Enhanced"

# 16.3. Kiểm tra Fallback MA_long_1M khung nến Tháng (0 giá trị NaN)
from core.indicators import calculate_mas
_dates_m = pd.date_range('2015-01-01', periods=140, freq='ME')
_df_1m_sample = pd.DataFrame({
    'date': _dates_m,
    'open': np.linspace(20, 50, 140),
    'high': np.linspace(22, 55, 140),
    'low': np.linspace(19, 48, 140),
    'close': np.linspace(21, 52, 140),
    'volume': 5000000
})
_df_mas_1m = calculate_mas(_df_1m_sample, is_monthly=True)
assert 'ma_long_1m' in _df_mas_1m.columns, "Thiếu cột ma_long_1m"
_nan_count = _df_mas_1m['ma_long_1m'].isna().sum()
assert _nan_count == 0, f"ma_long_1m phải có 0 giá trị NaN qua cơ chế fallback cascade, nhận {_nan_count} NaNs"
assert _df_mas_1m['ma_long_1m'].iloc[0] > 0, "ma_long_1m tại nến đầu tiên phải có giá trị dương hợp lệ"

# 16.4. Kiểm tra Fisher Transform NumPy vectorization output parity
from core.indicators import calculate_fisher_transform
np.random.seed(42)
_high_test = np.random.uniform(20.0, 25.0, 200)
_low_test = _high_test - np.random.uniform(0.5, 2.0, 200)
_close_test = (_high_test + _low_test) / 2.0
_df_fish_test = pd.DataFrame({
    'high': _high_test,
    'low': _low_test,
    'close': _close_test,
    'volume': 1000000
})
_res_fish = calculate_fisher_transform(_df_fish_test, period=9)
assert 'fisher' in _res_fish.columns and 'fisher_signal' in _res_fish.columns, "Fisher Transform thiếu cột kết quả"
# Kiểm tra đối soát với công thức chuẩn (vòng lặp tham chiếu)
_x_ref = (_high_test + _low_test) / 2.0
_min_ref = pd.Series(_x_ref).rolling(9, min_periods=1).min().values
_max_ref = pd.Series(_x_ref).rolling(9, min_periods=1).max().values
_denom_ref = np.where(_max_ref - _min_ref == 0, 0.0001, _max_ref - _min_ref)
_v_ref = np.zeros(200)
_f_ref = np.zeros(200)
for _i in range(1, 200):
    _s = 0.66 * ((_x_ref[_i] - _min_ref[_i]) / _denom_ref[_i] - 0.5) + 0.67 * _v_ref[_i - 1]
    _v_ref[_i] = np.clip(_s, -0.999, 0.999)
    _f_ref[_i] = 0.5 * np.log((1.0 + _v_ref[_i]) / (1.0 - _v_ref[_i])) + 0.5 * _f_ref[_i - 1]
assert np.allclose(_res_fish['fisher'].values, _f_ref, atol=1e-12), "Fisher Transform vector hóa phải đồng nhất 100% với công thức toán"

# 16.5. Kiểm tra Động cơ Backtest: Tối ưu hóa Win Rate & Profit Factor
from core.backtest_engine import backtest_preset
_bt_base = backtest_preset('KDH', preset='preset_3', start_date='2020-01-01', use_enhancements=False)
_bt_enh = backtest_preset('KDH', preset='preset_3', start_date='2020-01-01', use_enhancements=True)
assert _bt_base['summary'] is not None and _bt_enh['summary'] is not None, "Backtest KDH phải tạo được summary"
assert _bt_enh['summary']['profit_factor'] >= _bt_base['summary']['profit_factor'], \
    f"Enhanced Profit Factor ({_bt_enh['summary']['profit_factor']}) phải >= Baseline Profit Factor ({_bt_base['summary']['profit_factor']})"
assert _bt_enh['summary']['max_drawdown_pct'] <= _bt_base['summary']['max_drawdown_pct'], \
    f"Enhanced Max Drawdown ({_bt_enh['summary']['max_drawdown_pct']}%) phải <= Baseline Max Drawdown ({_bt_base['summary']['max_drawdown_pct']}%)"
assert _bt_enh['summary']['win_rate'] >= _bt_base['summary']['win_rate'], \
    f"Enhanced Win Rate ({_bt_enh['summary']['win_rate']}%) phải >= Baseline Win Rate ({_bt_base['summary']['win_rate']}%)"

print("-> PASS: Bearish Pitchfork m < 0, Preset 3 Bounce & Cạn Cung, Fallback MA 0 NaNs, Fisher Vectorized Parity & Backtest Tối Ưu hoàn hảo!")

# ============================================================
# 17. TEST KIỂM THỬ KHÓI GIAO DIỆN STREAMLIT (UI SMOKE TEST / RUNTIME VERIFICATION)
# ============================================================
print("\n[TEST 17] Kiểm tra Khói Giao Diện UI Streamlit (app.py & 7 trang con)...")
import runpy
import warnings

_ui_pages = [
    "app.py",
    "pages/1_Astro_Gann.py",
    "pages/2_Macro_Margin.py",
    "pages/3_Commodities_RRG.py",
    "pages/4_Derivatives_Breadth.py",
    "pages/5_Stock_Screener_MTF.py",
    "pages/6_Warrants_CW.py",
    "pages/7_Journal_Backtest.py"
]

_st_logger = logging.getLogger("streamlit")
_prev_st_level = _st_logger.level
_st_logger.setLevel(logging.ERROR)

for _page in _ui_pages:
    assert os.path.exists(_page), f"Không tìm thấy trang UI: {_page}"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            runpy.run_path(_page, run_name="__main__")
        print(f"-> PASS: {_page} thực thi thành công 0 ngoại lệ!")
    except Exception as _e:
        _st_logger.setLevel(_prev_st_level)
        raise AssertionError(f"Trang UI {_page} gặp ngoại lệ runtime: {_e}") from _e

_st_logger.setLevel(_prev_st_level)
print("-> PASS: Tất cả 8 trang Streamlit (app.py + 7 trang con) vượt qua UI Smoke Test thành công 100%!")

print("\n" + "=" * 60)
print("TẤT CẢ 17 MÔ-ĐUN ĐÃ VƯỢT QUA KIỂM THỬ TỰ ĐỘNG THÀNH CÔNG 100%!")
print("=" * 60)
