"""
core/black_scholes.py
Mô hình định giá Chứng quyền (Call Warrant) theo Black-Scholes:
- Tính Giá hợp lý (Fair Value), Delta, Theta/ngày, Effective Gearing, Điểm hòa vốn (Breakeven)
- Giải Implied Volatility (IV) bằng scipy.optimize.brentq trên khoảng [1e-4, 5.0]
- Kiểm tra điều kiện giá trị nội tại để chống phân kỳ với CW Deep OTM hoặc CW chiết khấu
- Ma trận mô phỏng lợi nhuận (Payoff Matrix) 21 kịch bản (+/-20%, bước 2%)
- Khóa quy chuẩn toàn bộ giá trị về đơn vị VNĐ trước khi tính toán
"""

import math
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

def calculate_historical_volatility(close_series: pd.Series, lookback: int = 60) -> float:
    """Tính độ biến động lịch sử (Historical Volatility) 60 phiên chuẩn hóa năm (x sqrt(252))."""
    if len(close_series) < 15:
        return 0.30  # Giá trị mặc định 30% nếu chuỗi dữ liệu quá ngắn
    log_ret = np.log(close_series / close_series.shift(1)).dropna()
    recent_ret = log_ret.tail(lookback)
    daily_std = recent_ret.std()
    annualized_vol = daily_std * np.sqrt(252.0)
    return float(np.clip(annualized_vol, 0.05, 2.0))

def black_scholes_call_price(S: float, K: float, T: float, r: float, sigma: float, CR: float = 1.0) -> float:
    """
    Tính giá lý thuyết Call Warrant (đơn vị VNĐ):
    C = (S * N(d1) - K * exp(-r*T) * N(d2)) / CR
    """
    if T <= 0 or S <= 0 or K <= 0 or sigma <= 0 or CR <= 0:
        return max(0.0, (S - K) / CR)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    c_raw = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return max(0.0, c_raw / CR)

def calculate_cw_greeks(S: float, K: float, T: float, r: float, sigma: float, CR: float = 1.0, market_price: float = None):
    """Tính toán các chỉ số Greeks cho Chứng quyền."""
    if T <= 0 or S <= 0 or K <= 0 or sigma <= 0 or CR <= 0:
        return {"delta": 0.0, "theta_daily": 0.0, "effective_gearing": 0.0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    # Delta
    delta = norm.cdf(d1) / CR

    # Theta (tính theo ngày)
    term1 = -(S * norm.pdf(d1) * sigma) / (2.0 * sqrt_T)
    term2 = -r * K * math.exp(-r * T) * norm.cdf(d2)
    theta_annual = (term1 + term2) / CR
    theta_daily = theta_annual / 365.0

    # Effective Gearing = Delta * (S / Market_Price_CW)
    eff_gearing = 0.0
    if market_price and market_price > 0:
        eff_gearing = delta * (S / market_price)

    return {
        "delta": round(float(delta), 4),
        "theta_daily": round(float(theta_daily), 2),
        "effective_gearing": round(float(eff_gearing), 2)
    }

def solve_implied_volatility(market_price: float, S: float, K: float, T: float, r: float, CR: float = 1.0) -> float:
    """
    Giải Implied Volatility (IV) bằng thuật toán brentq trên khoảng [1e-4, 5.0]:
    - Kiểm tra điều kiện giá trị nội tại (Intrinsic Value): nếu market_price <= Intrinsic, trả về None.
    """
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0 or CR <= 0:
        return None

    intrinsic = max(0.0, (S - K) / CR)
    if market_price <= intrinsic + 1.0:
        # Giá thị trường thấp hơn hoặc bằng giá trị nội tại (CW chiết khấu)
        return None

    def obj_func(sig):
        return black_scholes_call_price(S, K, T, r, sig, CR) - market_price

    try:
        # Kiểm tra hai đầu mút
        f_low = obj_func(1e-4)
        f_high = obj_func(5.0)
        if f_low * f_high > 0:
            return None
        iv = brentq(obj_func, 1e-4, 5.0, xtol=1e-5)
        return round(float(iv * 100.0), 2)  # %
    except Exception:
        return None

def generate_payoff_matrix(S: float, K: float, CR: float, market_price: float, range_pct: float = 0.20, step_pct: float = 0.02) -> pd.DataFrame:
    """
    Tạo ma trận mô phỏng lợi nhuận (Payoff Matrix) 21 kịch bản khi giá cổ phiếu cơ sở
    biến động từ -range_pct đến +range_pct (mặc định -20% -> +20%, bước 2%).
    """
    steps = int(round((2 * range_pct) / step_pct)) + 1
    pct_changes = np.linspace(-range_pct, range_pct, steps)

    rows = []
    for pct in pct_changes:
        s_sim = S * (1.0 + pct)
        intrinsic_sim = max(0.0, (s_sim - K) / CR)
        pnl = intrinsic_sim - market_price
        pnl_pct = (pnl / market_price) * 100.0 if market_price > 0 else 0.0
        rows.append({
            "pct_change_stock": round(pct * 100.0, 1),
            "stock_sim_price": round(s_sim, 0),
            "cw_intrinsic_sim": round(intrinsic_sim, 0),
            "pnl_vnd": round(pnl, 0),
            "pnl_pct": round(pnl_pct, 1)
        })

    return pd.DataFrame(rows)

def analyze_warrant(cw_info: dict, stock_close_vnd: float, hv_60d: float = 0.30, r: float = 0.05) -> dict:
    """
    Tổng hợp phân tích toàn diện 1 mã Chứng quyền:
    - cw_info: {'strike_price_vnd', 'conversion_ratio', 'maturity_date', 'last_price_vnd'}
    """
    k = float(cw_info.get("strike_price_vnd", 0))
    cr = float(cw_info.get("conversion_ratio", 1.0))
    m_price = float(cw_info.get("last_price_vnd", 0))
    mat_date = cw_info.get("maturity_date")

    if isinstance(mat_date, str):
        mat_dt = pd.to_datetime(mat_date).date()
    else:
        mat_dt = mat_date

    today = pd.Timestamp.now().date()
    days_to_mat = (mat_dt - today).days
    if days_to_mat <= 0:
        return {"status": "EXPIRED"}

    t_years = days_to_mat / 365.0

    fair_price = black_scholes_call_price(stock_close_vnd, k, t_years, r, hv_60d, cr)
    greeks = calculate_cw_greeks(stock_close_vnd, k, t_years, r, hv_60d, cr, market_price=m_price)
    iv = solve_implied_volatility(m_price, stock_close_vnd, k, t_years, r, cr)

    breakeven = k + m_price * cr
    breakeven_pct = ((breakeven - stock_close_vnd) / stock_close_vnd) * 100.0 if stock_close_vnd > 0 else 0.0

    diff_val_pct = ((m_price - fair_price) / fair_price) * 100.0 if fair_price > 0 else 0.0
    valuation_status = "Đắt (Overvalued)" if diff_val_pct > 5.0 else ("Rẻ (Undervalued)" if diff_val_pct < -5.0 else "Hợp lý (Fair)")

    return {
        "status": "ACTIVE",
        "days_to_maturity": days_to_mat,
        "stock_price_vnd": stock_close_vnd,
        "strike_price_vnd": k,
        "conversion_ratio": cr,
        "market_price_vnd": m_price,
        "fair_price_vnd": round(fair_price, 0),
        "diff_val_pct": round(diff_val_pct, 1),
        "valuation_status": valuation_status,
        "iv_pct": iv,
        "delta": greeks["delta"],
        "theta_daily": greeks["theta_daily"],
        "effective_gearing": greeks["effective_gearing"],
        "breakeven_price": round(breakeven, 0),
        "breakeven_pct": round(breakeven_pct, 1)
    }
