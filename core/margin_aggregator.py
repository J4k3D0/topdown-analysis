"""
core/margin_aggregator.py
Module quản lý và tổng hợp chuỗi số liệu Dư nợ Margin thị trường chứng khoán Việt Nam:
- Phân tách rõ ràng giữa chuỗi Toàn thị trường 78 CTCK (scope = 'market_total') từ file Excel
  và chuỗi Proxy nhóm CTCK lớn (scope = 'top15_proxy')
- Tính toán tốc độ tăng trưởng Margin theo quý (QoQ %)
- Tương quan Dư nợ Margin vs các mốc đỉnh/đáy lịch sử VN-Index (2000 - 2026)
"""

import os
import logging
import pandas as pd
import numpy as np
from core.db_manager import get_connection

logger = logging.getLogger(__name__)


def _read_margin_table(path: str) -> pd.DataFrame:
    """Đọc bảng Margin từ .xlsx/.xls/.csv (tự dò encoding tiếng Việt)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        last_err = None
        for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError as e:  # thử encoding kế tiếp
                last_err = e
        raise ValueError(f"Không đọc được file CSV: {last_err}")
    return pd.read_excel(path)


def import_margin_excel(excel_path: str = None) -> int:
    """
    Import chuỗi dữ liệu Margin từ file Excel/CSV (vnindex_margin_2000_2026.xlsx|csv).
    Trả về số quý đã ghi. Ném lỗi rõ ràng thay vì âm thầm trả 0.
    """
    if not excel_path or not os.path.exists(excel_path):
        raise FileNotFoundError(f"Không tìm thấy file Margin: {excel_path}")

    df = _read_margin_table(excel_path)
    if df is None or df.empty:
        raise ValueError("File Margin rỗng.")

    df.columns = [str(c).lower().strip() for c in df.columns]

    # Tìm các cột quý, dư nợ margin, vnindex
    q_col = next((c for c in df.columns if 'quý' in c or 'quarter' in c or 'time' in c), None)
    m_col = next((c for c in df.columns if 'margin' in c or 'dư nợ' in c or 'vay' in c), None)
    v_col = next((c for c in df.columns if 'vnindex' in c or 'vni' in c or 'index' in c), None)

    if not q_col or not m_col:
        raise ValueError(
            f"Không nhận diện được cột Quý/Margin. Cột hiện có: {list(df.columns)}. "
            "Cần tối thiểu 1 cột chứa 'quý'/'quarter'/'time' và 1 cột chứa 'margin'/'dư nợ'."
        )

    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    try:
        for _, row in df.iterrows():
            q_val = str(row[q_col]).strip()
            if not q_val or q_val.lower() == 'nan':
                continue
            m_val = float(row[m_col]) if pd.notna(row[m_col]) and str(row[m_col]).strip() != '' else 0.0
            v_val = None
            if v_col and pd.notna(row[v_col]):
                try:
                    v_val = float(row[v_col])
                except (TypeError, ValueError):
                    v_val = None

            cursor.execute("""
            INSERT OR REPLACE INTO margin_history
            (quarter, scope, total_margin_bn, vnindex_close, source, notes)
            VALUES (?, 'market_total', ?, ?, 'excel_import', 'Dữ liệu toàn thị trường 78 CTCK');
            """, (q_val, m_val, v_val))
            count += 1

        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Import Margin thất bại khi ghi SQLite")
        raise
    finally:
        conn.close()

    return count

def get_margin_series(scope: str = "market_total") -> pd.DataFrame:
    """Lấy chuỗi lịch sử Dư nợ Margin và tính % tăng trưởng QoQ."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT quarter, total_margin_bn, vnindex_close FROM margin_history WHERE scope = ? ORDER BY quarter ASC;",
        conn, params=[scope]
    )
    conn.close()

    if df.empty:
        # KHÔNG bịa chuỗi mẫu: trả về rỗng để UI cảnh báo người dùng import dữ liệu thật.
        df = pd.DataFrame(columns=["quarter", "total_margin_bn", "vnindex_close"])

    df['margin_growth_qoq'] = df['total_margin_bn'].pct_change() * 100.0 if not df.empty else pd.Series(dtype=float)
    return df
