"""
core/sources.py
Lớp adapter nguồn dữ liệu MIỄN PHÍ (0 credential) + registry + rate limiter + fallback.

Chuỗi ưu tiên (tự động chuyển nguồn, không bao giờ chặn pipeline):
    Cổ phiếu : vndirect  ->  vps  ->  yfinance  ->  RAW cache (L1)
    Chỉ số   : vps       ->  yfinance
    Vĩ mô    : yfinance  ->  RAW cache
    Lợi suất : FRED      ->  yfinance

Đặc điểm quan trọng:
- VNDirect trả về giá ĐÃ ĐIỀU CHỈNH (adClose) kèm trần/sàn công bố từng phiên và
  sàn niêm yết từng phiên (`floor`) => kiểm tra biên độ chính xác, không cần suy đoán.
- VPS (feed TradingView công khai) là nguồn thay thế cho VNINDEX vì yfinance đã
  ngừng trả dữ liệu cho ^VNINDEX.
- Mọi kết quả đều kèm `source` để ghi vào L1 RAW và truy vết.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import requests

from config.settings import (
    VNSTOCK_GUEST_RPM, VNSTOCK_KEY_RPM, YFINANCE_SLEEP_SEC,
)
from config.tickers import get_exchange

logger = logging.getLogger(__name__)

INDEX_TICKERS = {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX", "VN30F1M"}

# Cột chuẩn của lớp dữ liệu giá
OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


# ---------------------------------------------------------------------------
# Hạ tầng chung
# ---------------------------------------------------------------------------
class RateLimiter:
    """Giới hạn số request/phút cho từng nguồn (bảo vệ free tier)."""

    def __init__(self, rpm: float):
        self.min_interval = 60.0 / max(rpm, 1e-6)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            delta = time.monotonic() - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept": "application/json,text/plain,*/*",
    })
    return s


def _to_date_str(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


def is_index_ticker(ticker: str) -> bool:
    return (ticker or "").upper().replace("^", "") in INDEX_TICKERS


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa khung dữ liệu: đúng cột, đúng thứ tự, đúng kiểu, sắp xếp theo ngày."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        out[c] = pd.to_numeric(out.get(c), errors="coerce")
    out = out[out["date"].notna()]
    out = out.dropna(subset=["close"])
    out = out[out["close"] > 0]

    # Bảo đảm high/low bao trùm open/close (sửa sai lệch nhỏ sau khi điều chỉnh)
    out["high"] = out[["high", "open", "close"]].max(axis=1)
    out["low"] = out[["low", "open", "close"]].min(axis=1)

    out = out.drop_duplicates(subset=["date"], keep="last")
    return out.sort_values("date").reset_index(drop=True)


@dataclass
class SourceResult:
    ticker: str
    source: str
    df: Optional[pd.DataFrame]
    ok: bool
    message: str = ""
    attempted: list = field(default_factory=list)

    @property
    def rows(self) -> int:
        return 0 if self.df is None else len(self.df)


# ---------------------------------------------------------------------------
# Adapter: VNDirect (nguồn chính cho cổ phiếu)
# ---------------------------------------------------------------------------
class VndirectSource:
    """
    API công khai của VNDirect:
        /v4/stock_prices?q=code:HPG~date:gte:2012-01-01&sort=date:asc&size=2000&page=1

    Trả về: giá đã điều chỉnh (adOpen/adHigh/adLow/adClose), giá gốc (close),
    trần/sàn công bố (ceilingPrice/floorPrice), giá tham chiếu (basicPrice),
    sàn niêm yết từng phiên (floor), khối lượng khớp lệnh + thỏa thuận.
    """

    name = "vndirect"
    kind = "stock"
    priority = 1
    BASE = "https://api-finfo.vndirect.com.vn/v4/stock_prices"
    PAGE_SIZE = 2000
    MAX_PAGES = 12

    def __init__(self, rpm: float = 240):
        self._limiter = RateLimiter(rpm)
        self._session = _session()

    def available(self) -> bool:
        return True

    def _get(self, url: str, retries: int = 3) -> Optional[dict]:
        for attempt in range(retries):
            try:
                self._limiter.wait()
                r = self._session.get(url, timeout=40)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None
            except Exception as e:
                logger.debug(f"vndirect request lỗi ({attempt + 1}/{retries}): {e}")
                time.sleep(1.0 * (attempt + 1))
        return None

    def fetch_ohlcv(self, ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        if is_index_ticker(ticker):
            return None
        start = _to_date_str(start_date) or "2012-01-01"
        end = _to_date_str(end_date)

        q = f"code:{ticker.upper()}~date:gte:{start}"
        if end:
            q += f"~date:lte:{end}"

        frames = []
        for page in range(1, self.MAX_PAGES + 1):
            url = f"{self.BASE}?sort=date:asc&q={q}&size={self.PAGE_SIZE}&page={page}"
            payload = self._get(url)
            if not payload:
                break
            data = payload.get("data") or []
            if not data:
                break
            frames.append(pd.DataFrame(data))
            total_pages = int(payload.get("totalPages") or 1)
            if page >= total_pages:
                break

        if not frames:
            return None

        df = pd.concat(frames, ignore_index=True)
        if "type" in df.columns:
            df = df[df["type"].astype(str).str.upper() == "STOCK"]
        if len(df) == 0:
            return None

        for c in ("basicPrice", "ceilingPrice", "floorPrice", "open", "high", "low", "close",
                  "adOpen", "adHigh", "adLow", "adClose", "nmVolume", "ptVolume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        raw_close = df["close"]
        adj_close = df["adClose"].where(df["adClose"] > 0)
        factor = (adj_close / raw_close.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        factor = factor.where(factor > 0, 1.0).fillna(1.0)

        def adjusted(adj_col: str, raw_col: str) -> pd.Series:
            adj = pd.to_numeric(df.get(adj_col), errors="coerce")
            raw = pd.to_numeric(df.get(raw_col), errors="coerce")
            return adj.where(adj > 0, raw * factor)

        out = pd.DataFrame({
            "date": df["date"],
            "open": adjusted("adOpen", "open"),
            "high": adjusted("adHigh", "high"),
            "low": adjusted("adLow", "low"),
            "close": adj_close.where(adj_close.notna(), raw_close),
            "volume": df.get("nmVolume", pd.Series(0, index=df.index)).fillna(0)
                      + df.get("ptVolume", pd.Series(0, index=df.index)).fillna(0),
            "raw_close": raw_close,
            "reference_price": df.get("basicPrice"),
            "ceiling_price": df.get("ceilingPrice"),
            "floor_price": df.get("floorPrice"),
            "exchange": df.get("floor"),
        })
        return _finalize(out)

    def fetch_exchange(self, ticker: str) -> str:
        """Sàn niêm yết hiện tại theo nguồn (fallback: bản đồ tĩnh)."""
        df = self.fetch_ohlcv(ticker, start_date=_to_date_str(pd.Timestamp.now() - pd.Timedelta(days=30)))
        if df is not None and len(df) and "exchange" in df.columns:
            val = str(df["exchange"].iloc[-1]).upper()
            if val in ("HOSE", "HNX", "UPCOM"):
                return val
        return get_exchange(ticker)


# ---------------------------------------------------------------------------
# Adapter: VPS / TradingView public feed (nguồn chính cho VNINDEX)
# ---------------------------------------------------------------------------
class VpsSource:
    """Feed lịch sử công khai của VPS theo định dạng TradingView UDF."""

    name = "vps"
    kind = "stock+index"
    priority = 2
    BASE = "https://histdatafeed.vps.com.vn/tradingview/history"

    def __init__(self, rpm: float = 300):
        self._limiter = RateLimiter(rpm)
        self._session = _session()

    def available(self) -> bool:
        return True

    def fetch_ohlcv(self, ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        symbol = (ticker or "").upper().replace("^", "")
        start = _to_date_str(start_date) or "2012-01-01"
        end = _to_date_str(end_date) or pd.Timestamp.now().strftime("%Y-%m-%d")
        frm = int(pd.Timestamp(start).timestamp())
        to = int((pd.Timestamp(end) + pd.Timedelta(days=1)).timestamp())

        url = f"{self.BASE}?symbol={symbol}&resolution=1D&from={frm}&to={to}"
        for attempt in range(3):
            try:
                self._limiter.wait()
                r = self._session.get(url, timeout=40)
                if r.status_code != 200:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                payload = r.json()
                if payload.get("s") != "ok" or not payload.get("t"):
                    return None
                out = pd.DataFrame({
                    "date": pd.to_datetime(payload["t"], unit="s").normalize(),
                    "open": payload["o"],
                    "high": payload["h"],
                    "low": payload["l"],
                    "close": payload["c"],
                    "volume": payload["v"],
                })
                return _finalize(out)
            except Exception as e:
                logger.debug(f"vps request lỗi ({attempt + 1}/3): {e}")
                time.sleep(1.0 * (attempt + 1))
        return None


# ---------------------------------------------------------------------------
# Adapter: yfinance (dự phòng cổ phiếu, nguồn chính cho vĩ mô)
# ---------------------------------------------------------------------------
class YFinanceSource:
    name = "yfinance"
    kind = "stock+macro"
    priority = 3

    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
        except ImportError:
            self.yf = None

    def available(self) -> bool:
        return self.yf is not None

    def _yf_symbol(self, ticker: str) -> str:
        t = (ticker or "").upper()
        if is_index_ticker(t):
            return "^" + t.replace("^", "")
        if t.endswith(".VN") or "=" in t or t.startswith("^"):
            return t
        return f"{t}.VN"

    def fetch_ohlcv(self, ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        if not self.yf:
            return None
        symbol = self._yf_symbol(ticker)
        for attempt in range(2):
            try:
                tk = self.yf.Ticker(symbol)
                if start_date:
                    hist = tk.history(start=_to_date_str(start_date),
                                      end=_to_date_str(end_date), auto_adjust=True)
                else:
                    hist = tk.history(period="max", auto_adjust=True)
                if hist is None or hist.empty:
                    return None
                hist = hist.reset_index()
                hist.columns = [str(c).lower() for c in hist.columns]
                date_col = "date" if "date" in hist.columns else "datetime"
                out = pd.DataFrame({
                    "date": pd.to_datetime(hist[date_col]).dt.tz_localize(None).dt.normalize(),
                    "open": hist["open"], "high": hist["high"],
                    "low": hist["low"], "close": hist["close"],
                    "volume": hist.get("volume", 0),
                })
                # yfinance trả VND cho cổ phiếu VN -> quy đổi sang kVND
                if not is_index_ticker(ticker) and out["close"].median() > 500:
                    for c in ("open", "high", "low", "close"):
                        out[c] = out[c] / 1000.0
                return _finalize(out)
            except Exception as e:
                logger.debug(f"yfinance {symbol} lỗi ({attempt + 1}/2): {e}")
                time.sleep(1.0)
        return None

    def fetch_macro(self, ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        return self.fetch_ohlcv(ticker, start_date, end_date)


# ---------------------------------------------------------------------------
# Adapter: FRED (đường cong lợi suất)
# ---------------------------------------------------------------------------
class FredSource:
    name = "fred"
    kind = "macro"
    priority = 1
    URL_T10Y2Y = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y"
    URL_T10Y3M = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y3M"

    def available(self) -> bool:
        return True

    def fetch_yield_curve(self) -> Optional[pd.DataFrame]:
        try:
            d2 = pd.read_csv(self.URL_T10Y2Y)
            d3 = pd.read_csv(self.URL_T10Y3M)
            d2.columns = ["date", "t10y2y"]
            d3.columns = ["date", "t10y3m"]
            for d, col in ((d2, "t10y2y"), (d3, "t10y3m")):
                d[col] = pd.to_numeric(d[col], errors="coerce")
                d.dropna(subset=[col], inplace=True)
            merged = pd.merge(d2, d3, on="date", how="outer").sort_values("date")
            return merged
        except Exception as e:
            logger.warning(f"FRED lỗi: {e}")
            return None


# ---------------------------------------------------------------------------
# Adapter: vnstock (free tier, guest mode) - tuỳ chọn, tự bỏ qua nếu không có
# ---------------------------------------------------------------------------
class VnstockSource:
    """
    vnstock free (guest ~20 request/phút). Nếu chưa cài hoặc bị chặn,
    adapter tự báo không khả dụng và registry chuyển sang nguồn kế tiếp.
    """

    name = "vnstock"
    kind = "stock+fundamentals"
    priority = 0  # ưu tiên cao nhất khi hoạt động được

    def __init__(self):
        self._limiter = RateLimiter(VNSTOCK_GUEST_RPM)
        self._api = None
        self._checked = False

    def _load(self):
        if self._checked:
            return self._api
        self._checked = True
        try:
            from vnstock import Quote  # vnstock >= 3.x
            self._api = Quote
        except Exception:
            self._api = None
        return self._api

    def available(self) -> bool:
        return self._load() is not None

    def fetch_ohlcv(self, ticker: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        Quote = self._load()
        if Quote is None:
            return None
        try:
            self._limiter.wait()
            q = Quote(symbol=ticker.upper(), source="VCI")
            df = q.history(start=_to_date_str(start_date) or "2012-01-01",
                           end=_to_date_str(end_date) or pd.Timestamp.now().strftime("%Y-%m-%d"))
            if df is None or len(df) == 0:
                return None
            df = df.rename(columns={
                "time": "date", "open": "open", "high": "high",
                "low": "low", "close": "close", "volume": "volume",
            })
            return _finalize(df)
        except Exception as e:
            logger.debug(f"vnstock {ticker} lỗi: {e}")
            return None


# ---------------------------------------------------------------------------
# Registry + fallback
# ---------------------------------------------------------------------------
_SOURCES = {}


def _get(name: str):
    if name not in _SOURCES:
        _SOURCES[name] = {
            "vndirect": VndirectSource,
            "vps": VpsSource,
            "yfinance": YFinanceSource,
            "vnstock": VnstockSource,
        }[name]()
    return _SOURCES[name]


def stock_chain():
    """Chuỗi nguồn cho cổ phiếu, đã lọc theo khả năng thực tế."""
    chain = []
    for name in ("vnstock", "vndirect", "vps", "yfinance"):
        src = _get(name)
        try:
            if src.available():
                chain.append(src)
        except Exception:
            continue
    return chain


def index_chain():
    """Chuỗi nguồn cho chỉ số (yfinance đã ngừng trả ^VNINDEX)."""
    chain = []
    for name in ("vps", "yfinance"):
        src = _get(name)
        try:
            if src.available():
                chain.append(src)
        except Exception:
            continue
    return chain


def macro_chain():
    return [s for s in (_get("yfinance"),) if s.available()]


def _log(run_id, source, dataset, ticker, started, rows_in, status, message):
    try:
        from core.db_manager import log_ingest
        log_ingest(run_id or "adhoc", source, dataset, ticker, started,
                   rows_in=rows_in, rows_written=rows_in,
                   status=status, message=message)
    except Exception:
        pass


def fetch_ohlcv(ticker: str, start_date: str = None, end_date: str = None,
                run_id: str = None, log: bool = True,
                allow_cache: bool = True) -> SourceResult:
    """
    Tải OHLCV qua chuỗi nguồn ưu tiên. Luôn trả về SourceResult (không raise).
    Nếu mọi nguồn trực tuyến thất bại -> thử RAW cache trong L1.
    """
    ticker = (ticker or "").upper().replace("^", "")
    chain = index_chain() if is_index_ticker(ticker) else stock_chain()
    attempted = []

    for src in chain:
        started = pd.Timestamp.now()
        try:
            df = src.fetch_ohlcv(ticker, start_date, end_date)
        except Exception as e:
            attempted.append(f"{src.name}:ERR:{e}")
            _log(run_id, src.name, "ohlcv", ticker, started, 0, "FAILED", str(e))
            continue

        if df is not None and len(df) > 0:
            status = "OK" if not attempted else "FALLBACK"
            if log:
                _log(run_id, src.name, "ohlcv", ticker, started, len(df), status,
                     "nguồn chính" if status == "OK" else f"sau {len(attempted)} nguồn lỗi")
            return SourceResult(ticker, src.name, df, True, status, attempted)

        attempted.append(f"{src.name}:EMPTY")
        if log:
            _log(run_id, src.name, "ohlcv", ticker, started, 0, "EMPTY", "không có dữ liệu")

    # Cuối cùng: RAW cache
    if allow_cache:
        try:
            from core.db_manager import load_raw_ohlcv
            raw = load_raw_ohlcv(ticker)
            if raw is not None and len(raw) > 0:
                if start_date:
                    raw = raw[raw["date"] >= pd.to_datetime(start_date)]
                if end_date:
                    raw = raw[raw["date"] <= pd.to_datetime(end_date)]
                if len(raw) > 0:
                    return SourceResult(ticker, f"raw_cache:{raw['source'].iloc[-1]}", raw, True,
                                        "CACHE", attempted)
        except Exception:
            pass

    return SourceResult(ticker, "none", None, False, "tất cả nguồn đều thất bại", attempted)


def fetch_macro(ticker: str, start_date: str = None, end_date: str = None,
                run_id: str = None) -> SourceResult:
    """Tải dữ liệu vĩ mô/hàng hóa quốc tế (yfinance)."""
    attempted = []
    for src in macro_chain():
        started = pd.Timestamp.now()
        try:
            df = src.fetch_macro(ticker, start_date, end_date)
        except Exception as e:
            attempted.append(f"{src.name}:ERR:{e}")
            continue
        if df is not None and len(df) > 0:
            _log(run_id, src.name, "macro", ticker, started, len(df), "OK", "macro")
            return SourceResult(ticker, src.name, df, True, "OK", attempted)
        attempted.append(f"{src.name}:EMPTY")
    return SourceResult(ticker, "none", None, False, "không có nguồn macro", attempted)


def fetch_yield_curve(run_id: str = None) -> Optional[pd.DataFrame]:
    started = pd.Timestamp.now()
    df = FredSource().fetch_yield_curve()
    if df is not None and len(df) > 0:
        _log(run_id, "fred", "yield_curve", "T10Y2Y", started, len(df), "OK", "FRED")
        return df
    return None


def resolve_exchange(ticker: str) -> str:
    """Xác định sàn niêm yết: ưu tiên nguồn dữ liệu, sau đó bản đồ tĩnh."""
    try:
        src = _get("vndirect")
        if src.available():
            return src.fetch_exchange(ticker)
    except Exception:
        pass
    return get_exchange(ticker)
