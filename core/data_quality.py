"""
core/data_quality.py
Lớp kiểm định & sửa chữa chất lượng dữ liệu (chạy trước khi ghi vào lớp CLEAN).

Bốn nhóm lỗi được xử lý theo đúng luật thị trường Việt Nam:
1. NON_TRADING_DAY : nến rơi vào Thứ 7 / Chủ Nhật / ngày lễ  -> XÓA (ngày nghỉ thì không giao dịch).
2. ZERO_VOLUME     : volume <= 0                              -> XÓA (không có giao dịch thật).
3. OHLC_INVALID    : high < low, close ngoài [low, high]       -> XÓA.
4. LIMIT_BREACH_*  : |return| vượt biên độ sàn
     - HOSE ±7%, HNX ±10%, UPCoM ±15% (theo sàn của TỪNG phiên)
     - Nến đầu niêm yết và nến sau tạm ngừng > 25 phiên được nới biên độ.
     - Giá GIẢM vượt biên độ (STEP) -> coi là chia tách/cổ tức chưa điều chỉnh
       -> back-adjust toàn bộ chuỗi phía trước theo tỷ lệ.
     - Giá TĂNG vượt biên độ -> bất khả thi -> quarantine (loại nến) + ghi log.

Cung cấp CLI duy nhất (không tạo script rời rạc):
    python -m core.data_quality --validate [--ticker HPG]
    python -m core.data_quality --purge [--dry-run]
    python -m core.data_quality --repair --all
    python -m core.data_quality --calendar
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

from config.settings import (
    PRICE_LIMIT, LIMIT_TOLERANCE, LIMIT_WARN_TOLERANCE, DEFAULT_EXCHANGE,
    LISTING_DAY_LIMIT, POST_SUSPENSION_DAYS, POST_SUSPENSION_LIMIT,
    DATA_WINDOW_START,
)
from config.tickers import get_exchange
from config.vn_holidays import trading_day_mask

logger = logging.getLogger(__name__)

ISSUE_NON_TRADING = "NON_TRADING_DAY"
ISSUE_ZERO_VOLUME = "ZERO_VOLUME"
ISSUE_OHLC_INVALID = "OHLC_INVALID"
ISSUE_LIMIT_DOWN = "LIMIT_BREACH_DOWN"     # nghi chia tách / cổ tức
ISSUE_LIMIT_UP = "LIMIT_BREACH_UP"         # bất khả thi
ISSUE_LIMIT_WARN = "LIMIT_WARN"
ISSUE_INVALID_PRICE = "INVALID_PRICE"

SEVERITY = {
    ISSUE_NON_TRADING: "ERROR",
    ISSUE_ZERO_VOLUME: "ERROR",
    ISSUE_OHLC_INVALID: "ERROR",
    ISSUE_LIMIT_DOWN: "ERROR",
    ISSUE_LIMIT_UP: "ERROR",
    ISSUE_LIMIT_WARN: "WARN",
    ISSUE_INVALID_PRICE: "ERROR",
}

OHLCV = ["date", "open", "high", "low", "close", "volume"]


@dataclass
class QualityReport:
    ticker: str
    rows_in: int = 0
    rows_kept: int = 0
    non_trading: int = 0
    zero_volume: int = 0
    ohlc_invalid: int = 0
    limit_up: int = 0
    limit_down: int = 0
    limit_warn: int = 0
    adjusted_events: int = 0
    first_date: str = None
    last_date: str = None
    exchange: str = None
    issues: dict = field(default_factory=dict)

    @property
    def errors(self) -> int:
        return self.non_trading + self.zero_volume + self.ohlc_invalid + self.limit_up + self.limit_down

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["errors"] = self.errors
        d["ok"] = self.ok
        return d


# ---------------------------------------------------------------------------
# Chuẩn hóa & luật biên độ
# ---------------------------------------------------------------------------
def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in OHLCV:
        if c not in out.columns:
            out[c] = np.nan
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.sort_values("date").reset_index(drop=True)


def price_limit(exchange: str) -> float:
    return PRICE_LIMIT.get((exchange or DEFAULT_EXCHANGE).upper(), PRICE_LIMIT[DEFAULT_EXCHANGE])


def listing_limit(exchange: str) -> float:
    return LISTING_DAY_LIMIT.get((exchange or DEFAULT_EXCHANGE).upper(), 0.20)


def exchange_series(df: pd.DataFrame, ticker: str) -> pd.Series:
    """Sàn của từng phiên: ưu tiên cột `exchange` do nguồn trả về, sau đó bản đồ tĩnh."""
    if "exchange" in df.columns:
        s = df["exchange"].astype("string").str.upper()
        return s.fillna(get_exchange(ticker))
    return pd.Series(get_exchange(ticker), index=df.index)


def _is_genuine_bar(df: pd.DataFrame, idx) -> bool:
    """
    Nếu nguồn có công bố trần/sàn thực tế và giá gốc nằm trong biên độ đó
    => nến là thật, sai lệch chỉ do điều chỉnh cổ tức -> chỉ cảnh báo, không xóa.
    """
    if "raw_close" not in df.columns:
        return False
    row = df.loc[idx]
    raw = row.get("raw_close")
    ceil = row.get("ceiling_price")
    floor = row.get("floor_price")
    if pd.isna(raw) or pd.isna(ceil) or pd.isna(floor):
        return False
    tol = max(0.02, abs(float(raw)) * 0.005)
    return (float(floor) - tol) <= float(raw) <= (float(ceil) + tol)


# ---------------------------------------------------------------------------
# Back-adjust cổ tức / chia tách
# ---------------------------------------------------------------------------
def detect_corporate_actions(df: pd.DataFrame, ticker: str,
                             exchange: str = None) -> list:
    """
    Phát hiện các cú giảm giá vượt biên độ (nghi chia tách / cổ tức chưa điều chỉnh).
    Trả về list các dict: {index, date, ratio, limit}.
    """
    if len(df) < 2:
        return []
    exch = exchange_series(df, ticker) if exchange is None else pd.Series(exchange, index=df.index)
    close = df["close"].to_numpy(dtype=float)
    dates = df["date"].to_numpy()
    gaps = df["date"].diff().dt.days.fillna(999).to_numpy()

    events = []
    for i in range(1, len(df)):
        prev, cur = close[i - 1], close[i]
        if not np.isfinite(prev) or not np.isfinite(cur) or prev <= 0:
            continue
        r = cur / prev - 1.0
        ex = str(exch.iloc[i]).upper()
        lim = listing_limit(ex) if i == 0 else price_limit(ex)
        if gaps[i] > POST_SUSPENSION_DAYS:
            lim = max(lim, POST_SUSPENSION_LIMIT)
        if r < -(lim + LIMIT_TOLERANCE):
            events.append({
                "index": i,
                "date": pd.Timestamp(dates[i]).strftime("%Y-%m-%d"),
                "ratio": cur / prev,
                "return": r,
                "exchange": ex,
            })
    return events


def back_adjust(df: pd.DataFrame, ticker: str, exchange: str = None,
                max_events: int = 60) -> tuple[pd.DataFrame, list]:
    """
    Back-adjust chuỗi giá: mỗi sự kiện chia tách/cổ tức ở nến i sẽ nhân toàn bộ
    nến TRƯỚC i với tỷ lệ ratio, đồng thời chia khối lượng cho ratio.
    Trả về (df đã điều chỉnh, danh sách sự kiện đã xử lý).
    """
    work = _normalize(df)
    applied = []
    for _ in range(max_events):
        events = detect_corporate_actions(work, ticker, exchange)
        if not events:
            break
        ev = events[0]
        i, ratio = ev["index"], ev["ratio"]
        if not (0.05 < ratio < 1.0):
            # tỷ lệ bất thường -> không thể là chia tách, dừng lại để quarantine
            break
        for c in ("open", "high", "low", "close"):
            work.loc[: i - 1, c] = work.loc[: i - 1, c] * ratio
        work.loc[: i - 1, "volume"] = work.loc[: i - 1, "volume"] / ratio
        work["is_adjusted"] = 1
        applied.append(ev)
    return work, applied


# ---------------------------------------------------------------------------
# Kiểm định một chuỗi
# ---------------------------------------------------------------------------
def validate_frame(df: pd.DataFrame, ticker: str, exchange: str = None,
                   auto_adjust: bool = True, run_id: str = None) -> tuple[pd.DataFrame, pd.DataFrame, QualityReport]:
    """
    Kiểm định một khung OHLCV. Trả về (df_hợp_lệ, df_bị_loại, QualityReport).
    """
    ticker = (ticker or "").upper()
    rep = QualityReport(ticker=ticker, rows_in=0 if df is None else len(df))
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=OHLCV), pd.DataFrame(columns=OHLCV), rep

    work = _normalize(df)
    work["_issue"] = ""

    # 1. Ngày không giao dịch
    bad_date = work["date"].isna()
    trading = pd.Series(False, index=work.index)
    good_date = ~bad_date
    if good_date.any():
        trading.loc[good_date] = trading_day_mask(work.loc[good_date, "date"])
    work.loc[bad_date, "_issue"] = ISSUE_NON_TRADING
    work.loc[good_date & ~trading, "_issue"] = ISSUE_NON_TRADING
    rep.non_trading = int((bad_date | (good_date & ~trading)).sum())

    # 2. Giá / khối lượng không hợp lệ
    price_ok = (work["close"] > 0) & work[["open", "high", "low", "close"]].notna().all(axis=1)
    vol_ok = work["volume"].fillna(0) > 0
    mask = (work["_issue"] == "") & ~price_ok
    work.loc[mask, "_issue"] = ISSUE_INVALID_PRICE
    rep.issues[ISSUE_INVALID_PRICE] = int(mask.sum())

    mask = (work["_issue"] == "") & ~vol_ok
    work.loc[mask, "_issue"] = ISSUE_ZERO_VOLUME
    rep.zero_volume = int(mask.sum())

    # 3. OHLC không nhất quán
    hl_ok = (
        (work["high"] >= work["low"] * 0.999)
        & (work["close"] <= work["high"] * 1.001)
        & (work["close"] >= work["low"] * 0.999)
        & (work["open"] <= work["high"] * 1.001)
        & (work["open"] >= work["low"] * 0.999)
    )
    mask = (work["_issue"] == "") & ~hl_ok
    work.loc[mask, "_issue"] = ISSUE_OHLC_INVALID
    rep.ohlc_invalid = int(mask.sum())

    # 4. Biên độ giá (chỉ xét các nến còn hợp lệ)
    clean = work[work["_issue"] == ""].copy()
    if len(clean) > 1 and auto_adjust:
        clean, applied = back_adjust(clean, ticker, exchange)
        rep.adjusted_events = len(applied)
        for ev in applied:
            _log_quality(run_id, ticker, ev["date"], ISSUE_LIMIT_DOWN, "ERROR",
                         "BACK_ADJUSTED", f"ratio={ev['ratio']:.4f} ({ev['exchange']})")
        rep.limit_down = len(applied)

    if len(clean) > 0:
        exch = exchange_series(clean, ticker) if exchange is None else pd.Series(exchange, index=clean.index)
        ret = clean["close"].pct_change()
        gaps = clean["date"].diff().dt.days
        first_bar = clean.index == clean.index[0]
        post_suspend = gaps > POST_SUSPENSION_DAYS
        lim = exch.map(lambda x: price_limit(x))
        lim = lim.where(~first_bar, exch.map(lambda x: listing_limit(x)))
        lim = lim.where(~post_suspend, np.maximum(lim, POST_SUSPENSION_LIMIT))

        over_hard = ret.abs() > (lim + LIMIT_TOLERANCE)
        over_warn = (ret.abs() > lim) & ~over_hard
        # miễn trừ nến đầu và nến sau tạm ngừng
        over_hard = over_hard & ~first_bar & ~post_suspend
        over_warn = over_warn & ~first_bar & ~post_suspend

        up = over_hard & (ret > 0)
        down = over_hard & (ret < 0)

        # Nến có trần/sàn công bố và giá gốc nằm trong biên độ => nến thật
        warn_idx = []
        for idx in clean.index[over_hard]:
            if _is_genuine_bar(clean, idx):
                warn_idx.append(idx)
        if warn_idx:
            up.loc[warn_idx] = False
            down.loc[warn_idx] = False
            over_warn.loc[warn_idx] = True

        rep.limit_up = int(up.sum())
        rep.limit_down = max(rep.limit_down, int(down.sum()))
        rep.limit_warn = int(over_warn.sum())

        clean.loc[up, "_issue"] = ISSUE_LIMIT_UP
        clean.loc[down, "_issue"] = ISSUE_LIMIT_DOWN
        clean.loc[over_warn, "_issue"] = ISSUE_LIMIT_WARN

        for idx in clean.index[up | down]:
            issue = clean.loc[idx, "_issue"]
            _log_quality(run_id, ticker, clean.loc[idx, "date"], issue, "ERROR",
                         "QUARANTINED",
                         f"ret={ret.loc[idx]:.2%} limit={lim.loc[idx]:.2%} exch={exch.loc[idx]}")

    # 5. Tổng hợp
    all_rows = pd.concat([work[work["_issue"] != ""], clean], ignore_index=True)
    rejected = all_rows[all_rows["_issue"].isin(
        [ISSUE_NON_TRADING, ISSUE_ZERO_VOLUME, ISSUE_OHLC_INVALID,
         ISSUE_INVALID_PRICE, ISSUE_LIMIT_UP, ISSUE_LIMIT_DOWN]
    )].copy()
    kept = all_rows[~all_rows["_issue"].isin(
        [ISSUE_NON_TRADING, ISSUE_ZERO_VOLUME, ISSUE_OHLC_INVALID,
         ISSUE_INVALID_PRICE, ISSUE_LIMIT_UP, ISSUE_LIMIT_DOWN]
    )].copy()
    kept = kept.drop(columns=["_issue"], errors="ignore").sort_values("date").reset_index(drop=True)

    rep.rows_kept = len(kept)
    if len(kept):
        rep.first_date = kept["date"].iloc[0].strftime("%Y-%m-%d")
        rep.last_date = kept["date"].iloc[-1].strftime("%Y-%m-%d")
    rep.exchange = exchange or get_exchange(ticker)
    rep.issues.update({
        ISSUE_NON_TRADING: rep.non_trading,
        ISSUE_ZERO_VOLUME: rep.zero_volume,
        ISSUE_OHLC_INVALID: rep.ohlc_invalid,
        ISSUE_LIMIT_UP: rep.limit_up,
        ISSUE_LIMIT_DOWN: rep.limit_down,
        ISSUE_LIMIT_WARN: rep.limit_warn,
    })
    return kept, rejected, rep


def _log_quality(run_id, ticker, dt, issue, severity, action, detail):
    try:
        from core.db_manager import log_quality
        log_quality(run_id or "adhoc", ticker, dt, issue, severity, action, detail)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sửa chữa & purge trên database
# ---------------------------------------------------------------------------
def purge_invalid(dry_run: bool = False, run_id: str = None) -> dict:
    """
    Quét toàn bộ lớp CLEAN, xóa các nến bất khả thi:
    ngày nghỉ, volume <= 0, OHLC không nhất quán. (Không sửa biên độ.)
    """
    from core.db_manager import get_connection
    conn = get_connection()
    df = pd.read_sql_query("SELECT ticker, date, open, high, low, close, volume FROM ohlcv_daily;", conn)

    stats = {"rows_before": len(df), "holiday": 0, "zero_volume": 0, "ohlc_invalid": 0,
             "rows_after": len(df), "deleted": 0, "tickers": 0}
    if len(df) == 0:
        conn.close()
        return stats

    trading = pd.Series(False, index=df.index)
    dates = pd.to_datetime(df["date"], errors="coerce")
    good = dates.notna()
    trading.loc[good] = trading_day_mask(dates[good])

    hol = ~trading
    zv = (df["volume"].fillna(0) <= 0) & trading
    ohlc_bad = trading & (df["volume"].fillna(0) > 0) & (
        (df["high"] < df["low"] * 0.999)
        | (df["close"] > df["high"] * 1.001) | (df["close"] < df["low"] * 0.999)
        | (df["open"] > df["high"] * 1.001) | (df["open"] < df["low"] * 0.999)
    )
    drop = hol | zv | ohlc_bad
    stats["holiday"] = int(hol.sum())
    stats["zero_volume"] = int(zv.sum())
    stats["ohlc_invalid"] = int(ohlc_bad.sum())
    stats["deleted"] = int(drop.sum())
    stats["tickers"] = int(df.loc[drop, "ticker"].nunique())
    stats["rows_after"] = stats["rows_before"] - stats["deleted"]

    if dry_run or stats["deleted"] == 0:
        conn.close()
        return stats

    # Lưu vết trước khi xóa
    rejected = df.loc[drop].copy()
    rejected["source"] = "clean_purge"
    rejected["issue"] = np.select(
        [hol[drop], zv[drop]], [ISSUE_NON_TRADING, ISSUE_ZERO_VOLUME], default=ISSUE_OHLC_INVALID
    )
    rows = []
    for _, r in rejected.iterrows():
        rows.append((r["ticker"], str(r["date"])[:10], r["open"], r["high"], r["low"],
                     r["close"], r["volume"], "clean_purge", r["issue"], None))
    conn.executemany("""
    INSERT OR REPLACE INTO ohlcv_rejected
    (ticker, date, open, high, low, close, volume, source, issue, detail)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)

    keys = list(zip(df.loc[drop, "ticker"], df.loc[drop, "date"]))
    conn.executemany("DELETE FROM ohlcv_daily WHERE ticker = ? AND date = ?;", keys)
    conn.commit()
    conn.close()

    for issue, mask in ((ISSUE_NON_TRADING, hol), (ISSUE_ZERO_VOLUME, zv), (ISSUE_OHLC_INVALID, ohlc_bad)):
        if mask.any():
            sub = df.loc[mask]
            for t, n in sub.groupby("ticker").size().items():
                _log_quality(run_id, t, None, issue, "ERROR", "DELETED", f"{int(n)} nến")
    return stats


def repair_ticker(ticker: str, start_date: str = None, run_id: str = None,
                  save: bool = True, source_df: pd.DataFrame = None) -> dict:
    """
    Tải lại TOÀN BỘ chuỗi của 1 mã từ nguồn ưu tiên (không incremental),
    kiểm định, back-adjust rồi ghi đè lớp CLEAN. Dữ liệu gốc lưu vào L1 RAW.
    """
    from core.db_manager import save_raw_ohlcv, replace_ohlcv, save_ohlcv_daily

    start = start_date or DATA_WINDOW_START
    source_name = "provided"
    if source_df is None:
        from core.sources import fetch_ohlcv
        res = fetch_ohlcv(ticker, start_date=start, run_id=run_id)
        if not res.ok:
            return {"ticker": ticker, "ok": False, "source": res.source,
                    "message": res.message, "attempted": res.attempted}
        source_df = res.df
        source_name = res.source

    try:
        save_raw_ohlcv(source_df, ticker, source_name.split(":")[-1])
    except Exception as e:
        logger.warning(f"Không ghi được RAW cho {ticker}: {e}")

    exchange = None
    if "exchange" in source_df.columns:
        vals = source_df["exchange"].dropna().astype(str).str.upper().unique()
        if len(vals):
            exchange = "HOSE" if "HOSE" in vals else vals[-1]

    kept, rejected, rep = validate_frame(source_df, ticker, exchange=exchange, run_id=run_id)

    if save:
        if len(rejected):
            from core.db_manager import _write_rejected
            rows = []
            for _, r in rejected.iterrows():
                rows.append((ticker, str(r["date"])[:10], r.get("open"), r.get("high"),
                             r.get("low"), r.get("close"), r.get("volume"), source_name,
                             r["_issue"], None))
            _write_rejected(rows)
        replace_ohlcv(ticker, kept, source=source_name)

    out = rep.as_dict()
    out.update({"source": source_name, "ok": rep.ok or rep.rows_kept > 0,
                "message": "OK" if rep.ok else f"{rep.errors} nến bị loại"})
    return out


def repair_all(tickers: list = None, start_date: str = None, run_id: str = None,
               progress=None) -> pd.DataFrame:
    """Tải lại & sửa chữa toàn bộ danh mục (mặc định: mọi mã đang có trong DB)."""
    from core.db_manager import get_connection
    if tickers is None:
        conn = get_connection()
        rows = conn.execute("SELECT DISTINCT ticker FROM ohlcv_daily ORDER BY ticker;").fetchall()
        conn.close()
        tickers = [r[0] for r in rows]

    results = []
    for i, t in enumerate(tickers, 1):
        try:
            r = repair_ticker(t, start_date=start_date, run_id=run_id)
        except Exception as e:
            r = {"ticker": t, "ok": False, "message": f"EXC: {e}"}
        results.append(r)
        if progress:
            progress(i / len(tickers), t)
    return pd.DataFrame(results)


def build_calendar(run_id: str = None) -> int:
    """
    Xây dựng lịch giao dịch thực tế từ dữ liệu chỉ số (nguồn chuẩn nhất):
    ngày có nến VNINDEX chính là ngày thị trường giao dịch.
    """
    from core.db_manager import get_connection
    conn = get_connection()
    dates = conn.execute(
        "SELECT DISTINCT date FROM ohlcv_daily WHERE ticker = 'VNINDEX' AND volume > 0 ORDER BY date;"
    ).fetchall()
    if not dates:
        dates = conn.execute(
            "SELECT DISTINCT date FROM ohlcv_daily WHERE volume > 0 ORDER BY date;"
        ).fetchall()
    rows = [(r[0], 1, "VNINDEX") for r in dates]
    if rows:
        conn.executemany("""
        INSERT OR REPLACE INTO cal_trading_days (date, is_trading, source, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP);
        """, rows)
        conn.commit()
    conn.close()
    return len(rows)


def validate_all(tickers: list = None) -> pd.DataFrame:
    """Kiểm định toàn bộ lớp CLEAN hiện tại, trả về bảng tổng hợp theo mã."""
    from core.db_manager import get_connection, load_ohlcv
    conn = get_connection()
    if tickers is None:
        tickers = [r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM ohlcv_daily ORDER BY ticker;").fetchall()]
    conn.close()

    out = []
    for t in tickers:
        df = load_ohlcv(t)
        _, _, rep = validate_frame(df, t, auto_adjust=False)
        out.append(rep.as_dict())
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_reports(reports: pd.DataFrame):
    if reports.empty:
        print("Không có dữ liệu.")
        return
    cols = ["ticker", "rows_in", "rows_kept", "non_trading", "zero_volume",
            "ohlc_invalid", "limit_up", "limit_down", "limit_warn", "exchange"]
    cols = [c for c in cols if c in reports.columns]
    print(reports[cols].to_string(index=False))
    total_err = int(reports.get("errors", pd.Series(dtype=int)).sum()) if "errors" in reports else 0
    print(f"\nTổng lỗi: {total_err} | Mã đạt chuẩn: "
          f"{int(reports['ok'].sum()) if 'ok' in reports else 0}/{len(reports)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kiểm định & sửa chữa chất lượng dữ liệu")
    parser.add_argument("--validate", action="store_true", help="Kiểm định lớp CLEAN")
    parser.add_argument("--purge", action="store_true", help="Xóa nến ngày nghỉ / volume<=0 / OHLC sai")
    parser.add_argument("--repair", action="store_true", help="Tải lại toàn bộ chuỗi từ nguồn")
    parser.add_argument("--all", action="store_true", help="Áp dụng cho toàn bộ mã")
    parser.add_argument("--ticker", type=str, default=None, help="Chỉ xử lý 1 mã")
    parser.add_argument("--start", type=str, default=None, help="Ngày bắt đầu (mặc định 2012-01-01)")
    parser.add_argument("--calendar", action="store_true", help="Xây dựng lịch giao dịch thực tế")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ báo cáo, không ghi")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.calendar:
        n = build_calendar()
        print(f"Đã cập nhật lịch giao dịch: {n} ngày.")
        return 0

    if args.purge:
        stats = purge_invalid(dry_run=args.dry_run)
        print(f"Trước: {stats['rows_before']:,} nến | ngày nghỉ: {stats['holiday']:,} | "
              f"volume<=0: {stats['zero_volume']:,} | OHLC sai: {stats['ohlc_invalid']:,} | "
              f"xóa: {stats['deleted']:,} | còn lại: {stats['rows_after']:,} "
              f"({stats['tickers']} mã bị ảnh hưởng)")
        if args.dry_run:
            print("(dry-run: chưa ghi thay đổi)")
        return 0

    if args.repair:
        tickers = [args.ticker] if args.ticker else None
        if not args.all and not args.ticker:
            print("Cần --all hoặc --ticker.")
            return 2

        def prog(p, t):
            print(f"  [{p * 100:5.1f}%] {t}", flush=True)

        df = repair_all(tickers=tickers, start_date=args.start, run_id=None, progress=prog)
        _print_reports(df)
        return 0

    # mặc định: validate
    tickers = [args.ticker] if args.ticker else None
    reports = validate_all(tickers)
    _print_reports(reports)
    return 0 if (reports.empty or bool(reports["ok"].all())) else 1


if __name__ == "__main__":
    sys.exit(main())
