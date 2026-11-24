# AGENTS.md — Hướng Dẫn Vận Hành & Bản Đồ Kiến Trúc Hệ Thống (Top-Down Quant System)

Tài liệu này được thiết kế dành riêng cho các Trợ lý Trí tuệ Nhân tạo (AI Coding Agents: Antigravity, Claude, Codex, Cursor, Gemini, v.v.) để thấu hiểu toàn diện cấu trúc mã nguồn, triết lý định lượng, bản đồ phụ thuộc Graphify và các bất biến toán học bất khả xâm phạm của dự án **Hệ Thống Phân Tích Định Lượng Top-Down Chứng Khoán Việt Nam (v5.0)**.

---

## 1. Hướng Dẫn Điều Hướng Đồ Thị Tri Thức (Graphify Knowledge Graph)

Dự án này đã được tích hợp đồ thị tri thức mã nguồn tự động thông qua công cụ **Graphify** tại thư mục `graphify-out/`:
- **Đồ thị tổng thể:** `graphify-out/graph.json` (258 nodes, 664 edges, 10 communities).
- **Báo cáo cấu trúc:** `graphify-out/GRAPH_REPORT.md` (Điểm neo chịu tải - God Nodes, liên kết ngầm giữa các tầng).
- **Bản đồ trực quan:** `graphify-out/graph.html` (Biểu đồ lực tương tác không gian call-graph).
- **Hệ thống Wiki Agent:** `graphify-out/wiki/index.md` (20 bài viết tra cứu chi tiết từng community và module).

### Quy Tắc Điều Hướng Dành Cho AI Agent:
1. **Tra cứu trước khi đọc code thô:** Khi cần tìm hiểu kiến trúc hoặc liên kết giữa các module, hãy sử dụng đồ thị tri thức hoặc tra cứu các bài viết trong `graphify-out/wiki/` thay vì đọc quét toàn bộ file làm tiêu tốn ngữ cảnh.
2. **Các lệnh truy vấn Graphify qua CLI:**
   - Tra cứu quan hệ ngắn nhất giữa 2 hàm/lớp: `uvx --from graphifyy graphify path "get_connection" "backtest_preset"`
   - Giải thích một khái niệm/hàm trung tâm: `uvx --from graphifyy graphify explain "calculate_all_indicators"`
   - Cập nhật đồ thị sau khi sửa code: `uvx --from graphifyy graphify . --code-only` (chế độ AST thuần Python, 0 chi phí token API).
3. **Các Điểm Neo Chịu Tải Trọng Yếu (God Nodes) cần đặc biệt lưu ý:**
   - `get_connection()`: Điểm nối 30 liên kết — Quản lý SQLite WAL mode tập trung cho toàn bộ hệ thống.
   - `load_ohlcv()`: Điểm nối 19 liên kết — Nạp chuỗi giá lịch sử chuẩn hóa theo kVND từ database.
   - `calculate_all_indicators()`: Điểm nối 15 liên kết — Tính toán bộ chỉ báo đồng nhất đa khung thời gian.
   - `resample_ohlcv()`: Điểm nối 14 liên kết — Chuẩn hóa nến tuần W-FRI và nến tháng ME kèm cờ `last_bar_partial`.
   - `scan_stock()` & `backtest_preset()`: Cốt lõi của bộ lọc định lượng và động cơ kiểm định lịch sử.

---

## 2. Triết Lý Định Lượng & Kiến Trúc 6 Tầng Top-Down

Hệ thống được xây dựng dựa trên nguyên lý định lượng đa tầng, đi từ vĩ mô đến cấu trúc vi mô, kết hợp hài hòa giữa chiêm tinh tài chính, chu kỳ thời gian và kỷ luật quản trị vốn:

```
[ TẦNG 1: VĨ MÔ & THIÊN VĂN TÀI CHÍNH ]
   ├── Lịch HOSE (Holiday Calendar Guard)
   └── Chu kỳ Mặt Trăng (Moon Phases) & Thủy Tinh nghịch hành (Mercury Retrograde)
             ↓
[ TẦNG 2: THỊ TRƯỜNG CHUNG & DÒNG TIỀN VĨ MÔ ]
   ├── VN-Index Top-Down Gauge (0 - 100)
   ├── Dư nợ Margin toàn thị trường 2000 - 2026
   └── Lãi suất FRED, DXY, T10Y2Y & Tỷ giá USD/VND
             ↓
[ TẦNG 3: LUÂN CHUYỂN NGÀNH & HÀNG HÓA ]
   ├── JdK Relative Rotation Graph (RRG 12W, 8-bar tails) trên 9 ngành ICB
   └── Tương quan giá hàng hóa toàn cầu (Dầu Brent, Thép, Cao su, Phân bón)
             ↓
[ TẦNG 4: PHÁI SINH & ĐỘ RỘNG THỊ TRƯỜNG ]
   ├── VN30F1M Basis & Phân kỳ Open Interest (OI)
   └── Độ rộng Advance/Decline & Tỷ lệ cổ phiếu trên MA50
             ↓
[ TẦNG 5: BỘ LỌC ĐA KHUNG (1M-1W-1D) & CẤU TRÚC LOGARIT ]
   ├── 100% Biểu đồ trên trục Logarit cơ số 10 (log10)
   ├── Auto-Pitchfork 3 điểm (Bearish/Bullish) với trung điểm trung bình nhân
   ├── W.D. Gann Square of 9 (khóa kVND) & Gann Time Cycles
   ├── 3 Presets chiến lược (Bắt đáy 1M, Breakout Pitchfork 1W, Uptrend Pullback 1D)
   └── Lớp lọc An toàn Bảng cân đối (Balance Sheet Gatekeeper: P/B <= 1.3, Nợ/VCSH < 1.2)
             ↓
[ TẦNG 6: QUẢN TRỊ VỊ THẾ & CHỨNG QUYỀN ]
   ├── Kỷ luật Chốt lời từng phần Scaling-Out 50/50 (Target 1: +15%, Target 2: +35%)
   ├── Dời Stop Loss về hòa vốn (Breakeven) & Trailing Stop theo EMA21 nến ngày
   └── Định giá Chứng quyền (CW) Black-Scholes brentq IV solver & Ma trận Payoff 21 kịch bản
```

---

## 3. Cấu Trúc Thư Mục & Phân Trách Mã Nguồn

```
vnstock/
├── app.py                      # Master Dashboard & Trạm kiểm soát Database (Top-Down Gauge, Calendar Guard)
├── test_suite.py               # Bộ kiểm thử tự động toàn diện 12 mô-đun (chạy độc lập, không tạo rác)
├── PLAN.md                     # Bản kiểm toán đặc tả kỹ thuật v5.0
├── AGENTS.md                   # Tài liệu hướng dẫn AI & quy tắc vận hành (File này)
│
├── config/                     # Cấu hình danh mục và hệ thống
│   ├── settings.py             # Cấu hình tham số, giao diện Streamlit, chuẩn logarit, đơn vị kVND
│   ├── tickers.py              # Danh mục Tier 1 (~150 mã), 9 ngành ICB, Vingroup 4 mã, CTCK niêm yết
│   ├── vn_holidays.py          # Lịch nghỉ giao dịch HOSE (chuẩn ngày nghỉ 2026, ngày 24/11)
│   └── vn_holidays_override.json # Lịch nghỉ bù đặc biệt của HOSE
│
├── core/                       # 14 Động cơ tính toán định lượng chuyên sâu
│   ├── db_manager.py           # SQLite WAL mode, khởi tạo 12 bảng, indexes, nạp/lưu OHLCV
│   ├── indicators.py           # Resampling W-FRI/ME, EMA/MA, RSI, Fisher Transform, MFI, Ex-Vingroup
│   ├── geometry_log.py         # Auto-Pitchfork 3 điểm log, Warning Lines, Auto-Trendline
│   ├── gann_engine.py          # Gann Square of 9 (kVND), Gann Time Cycles, Gann Fan/Box Log
│   ├── astro_engine.py         # Pha Mặt Trăng Jean Meeus, Thủy Tinh nghịch hành (bảng tra 2024-2027)
│   ├── black_scholes.py        # Định giá CW Black-Scholes, scipy brentq IV solver, 21-scenario payoff
│   ├── rrg_engine.py           # JdK RRG 12W, Sector Rotation Backtest
│   ├── scoring_engine.py       # Hệ thống chấm điểm 5 tầng & Top-Down Composite Score (0-100)
│   ├── screener.py             # Bộ lọc định lượng 3 Preset + Lớp lọc An toàn Bảng cân đối
│   ├── backtest_engine.py      # Động cơ kiểm định lịch sử thực chiến, tối ưu hóa xác suất dự đoán
│   ├── portfolio_alerts.py     # Máy trạng thái cảnh báo danh mục (phân định OPEN / PARTIAL)
│   ├── report_generator.py     # Xuất báo cáo 1-click (Jinja2 HTML & Markdown)
│   ├── data_fetcher.py         # Kết nối YFinance, FRED, đồng bộ hóa SQLite
│   └── margin_aggregator.py    # Dữ liệu Margin 2000-2026 so sánh tương quan VN-Index
│
├── components/                 # Thành phần giao diện Streamlit tái sử dụng
│   ├── charts_plotly.py        # Đồ thị nến Deep-Dive 100% Log 4-panel, biểu đồ RRG, Yield Curve
│   └── ui_cards.py             # Đồng hồ Top-Down Gauge, Calendar Guard card, Alert card
│
├── pages/                      # 7 Trang chức năng chuyên sâu của Web App
│   ├── 1_Astro_Gann.py         # Thiên văn tài chính, Pha Trăng, Thủy Tinh, Gann Square of 9
│   ├── 2_Macro_Margin.py       # Vĩ mô quốc tế, Lợi suất T10Y2Y, Dư nợ Margin 2000-2026
│   ├── 3_Commodities_RRG.py    # JdK RRG 12W 9 nhóm ngành ICB & Hàng hóa thế giới
│   ├── 4_Derivatives_Breadth.py# Phái sinh VN30F1M Basis, OI, Độ rộng thị trường A/D
│   ├── 5_Stock_Screener_MTF.py # Bộ lọc đa khung 1M-1W-1D, Trạm đồ thị Log, Lưu trendline vẽ tay
│   ├── 6_Warrants_CW.py        # Bảng tính định giá Chứng quyền CW, brentq IV, Ma trận Payoff
│   └── 7_Journal_Backtest.py   # Nhật ký lệnh Scaling-Out 50/50 & Trạm Kiểm định Thực tiễn Lịch sử
│
├── data/                       # Dữ liệu cục bộ
│   ├── quant_local.db          # SQLite Database chuẩn WAL (30+ cổ phiếu, 2010 - 2026)
│   └── reports/                # Thư mục lưu trữ báo cáo tự động xuất ra
│
└── graphify-out/               # Đồ thị tri thức kiến trúc sinh bởi Graphify
    ├── graph.json              # Dữ liệu đồ thị nút và cạnh
    ├── GRAPH_REPORT.md         # Báo cáo God Nodes và phân cụm
    ├── graph.html              # Biểu đồ quan hệ tương tác trực quan
    └── wiki/                   # Thư viện 20 bài viết tra cứu mã nguồn
```

---

## 4. Các Bất Biến Toán Học & Quy Tắc Code Bất Khả Xâm Phạm

Mọi AI khi bảo trì hoặc phát triển tính năng mới bắt buộc phải tuân thủ nghiêm ngặt các quy tắc sau:

### 4.1. Quy Tắc Đơn Vị Giá (kVND vs VND)
- **Chuẩn lưu trữ và tính toán kỹ thuật:** MỌI giá đóng cửa, mở cửa, cao nhất, thấp nhất trong database và các chỉ báo kỹ thuật ĐỀU LÀ **nghìn đồng (kVND)** (ví dụ: NLG giá 21.2, FPT giá 123.3, KDH giá 14.0).
- **Gann Square of 9:** TUYỆT ĐỐI giữ nguyên đơn vị kVND. Do công thức $(\sqrt{P} \pm \frac{\theta}{180})^2$ phụ thuộc vào độ lớn số học, việc đổi sang VND sẽ làm sai lệch hoàn toàn góc dự báo (sai lệch >130%).
- **Định giá Chứng quyền (Black-Scholes):** Module `core/black_scholes.py` là nơi DUY NHẤT tự động quy đổi giá sang **đồng (VND)** (nhân với 1.000) để đảm bảo đồng nhất đơn vị giữa cổ phiếu cơ sở, giá thực hiện và giá thị trường của chứng quyền khi giải IV bằng `scipy.optimize.brentq`.

### 4.2. Quy Tắc Hình Học Trên Thang Logarit 100%
- Mọi phép phân tích đường xu hướng (Auto-Trendline) và kênh Pitchfork ĐỀU PHẢI tính toán trên không gian $\log_{10}(Price)$.
- **Pitchfork Trung điểm:** Tọa độ $y$ của trung điểm giữa $P_2$ và $P_3$ phải là trung bình nhân trên thang thường, tức trung bình cộng trên trục logarit:
  $$y_M = \frac{\log_{10}(P_2) + \log_{10}(P_3)}{2}$$
- **Hệ số góc Gann Fan Log:** Bất biến trên thang logarit với bước đơn vị $s = \frac{\log_{10}(P_{end}) - \log_{10}(P_{start})}{\Delta t}$.

### 4.3. Quy Tắc Resampling Khung Thời Gian
- Chuẩn pandas $\ge 2.2$: Nến tháng sử dụng mã `"ME"` (Month End), nến tuần sử dụng `"W-FRI"` (Week ending Friday).
- Khi bar cuối cùng chưa kết thúc (phiên giữa tuần/tháng), phải gắn cờ `attrs['last_bar_partial'] = True` để cảnh báo nến chưa hoàn thiện, tránh thiên kiến nhìn trước tương lai.

### 4.4. Quy Tắc Streamlit Hiện Đại (Không Dùng `use_container_width`)
- Cấm sử dụng tham số lỗi thời `use_container_width=True` (sẽ bị gỡ bỏ sau năm 2025).
- Thay thế hoàn toàn bằng `width='stretch'` (khi muốn kéo dãn vừa vặn container) hoặc `width='content'` (vừa theo nội dung).

### 4.5. Quy Tắc Quản Trị Vị Thế Scaling-Out 50/50
- Quản trị một lệnh mua chỉ trên **đúng 1 dòng dữ liệu** trong bảng `trade_journal`.
- Máy trạng thái:
  - `OPEN`: Vị thế đang mở đủ 100% khối lượng.
  - `PARTIAL`: Đã chốt 50% khối lượng đầu tiên tại Target 1 (+15%). Đồng thời dời Stop Loss về Breakeven (giá vào lệnh), kích hoạt Trailing Stop bám sát EMA21 nến ngày.
  - `CLOSED`: Đã thoát nốt 50% khối lượng còn lại tại Target 2 (+35%) hoặc chạm Trailing Stop / Stop Loss.

### 4.6. Quy Tắc Lọc Đa Khung Thời Gian Cho 3 Presets (Đã Tối Ưu Qua Backtest)
- **Preset 1 (Bắt đáy Chu kỳ 1M):** Khung Tháng thỏa mãn Fisher(9, 1M) < -1.8 và giá quanh MA200(1M) $\pm 10\%$. **Bắt buộc có xác nhận nến Ngày:** Nến ngày xanh ($Close \ge Open$), $RSI \ge 30$, và có khối lượng hấp thụ ($Vol \ Ratio \ge 1.25\times$) hoặc Fisher ngày cắt lên.
- **Preset 2 (Breakout Bearish Pitchfork 1W):** Giá tuần vượt cạnh trên Line 3 kèm $Vol \ Ratio \ge 1.5\times$, $MFI \ge 45$. **Bắt buộc lọc râu nến:** Nến tuần đóng ở nửa trên thân nến ($\frac{Close - Low}{High - Low} \ge 0.50$) và khoảng cách giá tới EMA21 tuần $\le 15\%$. **Bộ lọc Enhanced (kiểm định 2015–2026):** biên bứt phá $\ge 0.5\%$, khoảng cách EMA21 tuần $\le 12\%$, $RSI(1D) \le 70$, $MFI(1W) \ge 48$, và **Market Regime Gate** ($VNIndex \ge EMA50 \times 0.98$ hoặc $RSI(1D) \ge 46$) — giảm mạnh Bull Trap, nâng PF từ 1.33 lên ~1.46.
- **Preset 3 (Uptrend Pullback 1D):** Sóng tăng EMA21 > EMA50 > EMA120, giá kéo về sát EMA21 $\le 2\%$ (tối ưu từ 3% qua thực nghiệm). **Bắt buộc lọc nến xả hàng:** Không vào lệnh nếu nến kéo lùi là nến đỏ kèm vol lớn ($Close < Open$ và $Vol \ Ratio > 1.25$), giá đóng cửa phải giữ trên $EMA21 \times 0.99$, nến trước đó phải cạn cung ($Vol \ Ratio \le 1.10$) và **Market Regime Gate** ($VNIndex \ge EMA50 \times 0.995$ hoặc $RSI(1D) \ge 48$).
- **Nguồn ngưỡng duy nhất:** Toàn bộ ngưỡng 3 Preset nằm tại `config/settings.py` (`PRESET_1_PARAMS`, `PRESET_2_PARAMS`, `PRESET_3_PARAMS`). `core/screener.py` (quét live) và `core/backtest_engine.py` (kiểm định) đọc chung một nguồn — cấm hardcode lại ngưỡng ở nơi khác (đã có TEST 15.7 canh giữ).

---

## 5. Danh Mục Lệnh Thường Dùng Cho AI

| Nhiệm Vụ | Lệnh Thực Thi | Ghi Chú |
| :--- | :--- | :--- |
| **Kiểm thử tự động toàn diện** | `python test_suite.py` | Kiểm tra toàn bộ 12 mô-đun, bắt buộc PASS 100% |
| **Khởi chạy ứng dụng Web** | `streamlit run app.py` | Chạy ứng dụng Streamlit trên cổng mặc định (8501) |
| **Chạy kiểm định lịch sử (Backtest)** | `python core/backtest_engine.py` | Quét dữ liệu 11 năm trên 30 mã trong Local DB |
| **Cập nhật Knowledge Graph** | `uvx --from graphifyy graphify . --code-only` | Quét lại AST code và cập nhật `graphify-out/` |
| **Biên dịch kiểm tra cú pháp** | `Get-ChildItem -Recurse -Filter *.py \| ForEach-Object { python -m py_compile $_.FullName }` | Đảm bảo không phát sinh lỗi cú pháp hay cảnh báo |
| **Truy vấn quan hệ mã nguồn** | `uvx --from graphifyy graphify path "nodeA" "nodeB"` | Tìm đường đi ngắn nhất giữa 2 thành phần hệ thống |

---
*Tài liệu được cập nhật và đồng bộ tự động theo bản kiểm định thực tiễn v5.0 (22/11/2026).*
