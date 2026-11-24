"""
core/report_generator.py
Tạo báo cáo phân tích đầu tư tự động (1-Click Auto-Report) dạng HTML (Jinja2) và Markdown.
Lưu file vào thư mục data/reports/.
"""

import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from config.settings import REPORTS_DIR, ROOT_DIR

TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")

def generate_stock_report(ticker: str, analysis_data: dict) -> dict:
    """
    Sinh báo cáo phân tích cho mã cổ phiếu:
    - analysis_data: chứa giá hiện tại, RSI, Fisher, MTF status, Gann targets, khuyến nghị.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")

    context = {
        "ticker": ticker,
        "date_str": today_str,
        "current_price": analysis_data.get("current_price", 0.0),
        "rsi_1d": analysis_data.get("rsi_1d", 50.0),
        "fisher_1d": analysis_data.get("fisher_1d", 0.0),
        "avg_liquidity": analysis_data.get("avg_liquidity", 0.0),
        "mtf_status": analysis_data.get("mtf_status", {
            "1M": {"position": "Vùng hỗ trợ dài hạn", "fisher": "-2.5", "ma_ref": "MA200", "assessment": "Đáy chu kỳ tích lũy"},
            "1W": {"position": "Tích lũy khối lượng lớn", "vol_ratio": "2.1", "mfi": "52", "assessment": "Dòng tiền lớn xác nhận"},
            "1D": {"position": "Sóng hồi phục", "assessment": "Căn điểm vào lệnh"}
        }),
        "gann_targets": analysis_data.get("gann_targets", []),
        "entry_rec": analysis_data.get("entry_rec", "Vùng hỗ trợ MA/EMA"),
        "stop_rec": analysis_data.get("stop_rec", "-7% từ giá vốn"),
        "target1_rec": analysis_data.get("target1_rec", "Kháng cự ngắn hạn"),
        "target2_rec": analysis_data.get("target2_rec", "Mục tiêu chu kỳ dài hạn")
    }

    # 1. Render HTML bằng Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("report_template.html")
    html_out = template.render(context)

    html_path = os.path.join(REPORTS_DIR, f"REPORT_{ticker}_{timestamp_slug}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    # 2. Render Markdown
    md_lines = [
        f"# BÁO CÁO PHÂN TÍCH ĐẦU TƯ TOP-DOWN: {ticker}",
        f"*Ngày xuất: {today_str} | Đơn vị: kVND*",
        "",
        f"- **Giá Đóng Cửa:** {context['current_price']} kVND",
        f"- **RSI(14) 1D:** {context['rsi_1d']} | **Fisher(9) 1D:** {context['fisher_1d']}",
        f"- **Thanh khoản 20p:** {context['avg_liquidity']} tỷ VNĐ/phiên",
        "",
        "## 1. Đánh Giá Đa Khung Thời Gian (1M -> 1W -> 1D)",
        f"- **Khung Tháng (1M):** {context['mtf_status']['1M']['assessment']}",
        f"- **Khung Tuần (1W):** {context['mtf_status']['1W']['assessment']}",
        f"- **Khung Ngày (1D):** {context['mtf_status']['1D']['assessment']}",
        "",
        "## 2. Kế Hoạch Vào Lệnh & Quản Trị Vị Thế",
        f"- **Entry:** {context['entry_rec']}",
        f"- **Stop Loss:** {context['stop_rec']}",
        f"- **Target 1 (50%):** {context['target1_rec']}",
        f"- **Target 2 (50%):** {context['target2_rec']}",
        "",
        "---",
        "*Hệ thống Phân Tích Top-Down 6 Tầng v5.0*"
    ]
    md_out = "\n".join(md_lines)
    md_path = os.path.join(REPORTS_DIR, f"REPORT_{ticker}_{timestamp_slug}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_out)

    return {
        "html_path": html_path,
        "md_path": md_path,
        "timestamp": timestamp_slug
    }
