# KẾ HOẠCH CHỐT XÂY DỰNG HỆ THỐNG PHÂN TÍCH ĐẦU TƯ TOP-DOWN 6 TẦNG & LOCAL QUANT DATABASE (STREAMLIT)

> **Phiên bản tài liệu:** v3.0 — **FINAL PRODUCTION SPEC** (Đã khóa toàn bộ 100% yêu cầu, không còn điểm mở, sẵn sàng bàn giao code)
> **Phiên bản tài liệu:** v4.0 — **FINAL UNIFIED SPEC** (Đã tích hợp 100% phản hồi ngày 22/11/2026, không còn điểm mở)
>
> **Đối tượng triển khai code:** Antigravity / Gemini 3.8 Flash
>
> **Nền tảng mục tiêu:** Python 3.11+, SQLite + Parquet Local Database, Streamlit Multi-page Web App (Dark Mode Pro, Plotly 100% Log Interactive Charts, Auto-Report Generator)
> **Nền tảng mục tiêu:** Python 3.11+, SQLite Local Database, Streamlit Multi-page Web App (Dark Mode Pro, Plotly 100% Log Interactive Charts, Auto-Report Generator)
>
> **Nguồn phương pháp luận:** Thực chiến cá nhân (Case Study KDH, NLG, FPT tháng 11/2026), khung PTCB + QTRR tham khảo **vfin.vn**, và chuẩn hóa học thuật từ bộ sách **Wiley Trading** (John Murphy, Martin Pring, John Ehlers, Alan Andrews / Timothy Morge, W.D. Gann, Jeremy du Plessis — Point & Figure).
> **Nguồn phương pháp luận:** Thực chiến cá nhân (Case Study KDH, NLG, FPT tháng 11/2026), khung PTCB + QTRR tham khảo **vfin.vn**, và chuẩn hóa học thuật từ bộ sách **Wiley Trading** (John Murphy, Martin Pring, John Ehlers, Alan Andrews / Timothy Morge, W.D. Gann).

---

## TÓM TẮT TOÀN BỘ QUYẾT ĐỊNH ĐÃ KHÓA (LOCKED ARCHITECTURE)
## TÓM TẮT TOÀN BỘ QUYẾT ĐỊNH ĐÃ KHÓA (LOCKED ARCHITECTURE v4.0)

| Hạng mục | Phương án đã khóa | Yêu cầu bắt buộc khi Antigravity viết code |
| :--- | :--- | :--- |
| **1. Nguồn dữ liệu (KHÔNG dùng `vnstock`)** | **`yfinance` + MSN Finance + FRED + CSV/Excel Local** *(kèm cổng mở SSI API)* | **Tuyệt đối không dùng `vnstock`** (do từ 10/11/2026 các bản cũ đã ngừng hoạt động, bản v6 yêu cầu API key CTCK riêng & bản mở rộng thu phí). Dùng `yfinance` (`.VN` & quốc tế) + MSN Finance fallback + FRED CSV + Import file Excel/CSV cục bộ (`vnindex_margin_2000_2026.xlsx`, Phái sinh, Chứng quyền, BCTC). |
| **2. Kiến trúc Local Database & Đồng bộ** | **Local-First DB (`SQLite` + `Parquet`) + VN-Index Trading Calendar Guard** | Người dùng **tạo & cập nhật Database cục bộ trước**, sau đó mọi thao tác Quét mã/RRG/Backtest chỉ đọc từ DB trên máy (tốc độ < 1 giây, không bị chặn IP). Tự động so sánh ngày mới nhất trong DB với **ngày giao dịch gần nhất của VN-Index (bỏ T7, CN, tính mốc sau 15:00 giờ VN)** $\to$ hiện cảnh báo nhắc cập nhật trước khi quét. |
| **3. Chuẩn hóa Giá** | **100% Giá đã điều chỉnh (`Adjusted Price`)** | Toàn bộ OHLCV từ `yfinance` bắt buộc tải với `auto_adjust=True` (tự động điều chỉnh cổ tức/chia tách như case FPT) trước khi lưu DB, resample sang `1W`/`1M` và tính chỉ báo. |
| **4. Thang đo Đồ thị** | **100% Log Scale** | Khóa cứng `yaxis_type="log"` trên cả 3 khung `1M` $\to$ `1W` $\to$ `1D` cho toàn bộ đồ thị giá. |
| **5. Auto-Pitchfork 3 điểm** | **2 chiều Đối xứng (Bearish & Bullish) + Swing Window (`N=5`)** | Dùng `scipy.signal.argrelextrema` với cửa sổ mặc định `N=5` nến mỗi bên (có thanh trượt chỉnh `N` từ `2` đến `20` trên UI). Bắt buộc tính trung điểm bằng trung bình nhân trên trục $\log_{10}$. |
| **6. Vẽ Trendline & Công cụ Nâng cao** | **Hybrid Auto + Manual + Gann + Point & Figure (P&F) ngay v1.0** | Tích hợp sẵn **Auto-Trendline + vẽ tay Plotly**, **W.D. Gann (Gann Fan, Gann Box, Square of 9, Time Cycles)** và **Biểu đồ Point & Figure (X/O + Horizontal/Vertical Target Count)** ngay trong bản v1.0. |
| **7. Trọng số Top-Down (0–100)** | **10% – 20% – 20% – 10% – 40%** *(tùy chỉnh bằng Slider)* | Thiên văn/Gann (10%) + Vĩ mô/Margin/Yield Curve (20%) + Hàng hóa/RRG Ngành (20%) + Phái sinh/Độ rộng (10%) + Cổ phiếu 1M-1W-1D (40%). |
| **8. Quản trị Vị thế & Cảnh báo** | **Scaling-Out 50/50 + Auto Alert Danh mục** | Tab Nhật ký lệnh tự động đối chiếu giá đóng cửa mới nhất trong Local DB với các mốc **Stop-Loss / Trailing Stop / Target 1 (50%) / Target 2 (50%)** để bật cờ cảnh báo trực quan cho các mã đang giữ (như NLG). |
| **1. Nguồn dữ liệu** | **`vnstock` (Community Edition, free) + `yfinance` (quốc tế) + FRED** | **Dùng `vnstock`** cho toàn bộ dữ liệu chứng khoán VN (OHLCV, Listing, Phân ngành ICB, BCTC, Phái sinh VN30F, Chứng quyền CW). Dùng `yfinance` cho dữ liệu quốc tế (DXY, Vàng, Dầu, VIX, US10Y). Dùng FRED CSV cho Yield Curve. Dữ liệu Margin VN tự tổng hợp từ BCTC các CTCK lớn qua vnstock. |
| **2. Kiến trúc Local Database & Đồng bộ** | **Local-First DB (`SQLite`) + VN-Index Trading Calendar Guard** | Người dùng **tạo & cập nhật Database cục bộ trước**, sau đó mọi thao tác Quét mã/RRG/Backtest chỉ đọc từ DB trên máy (tốc độ < 1 giây). Tự động so sánh ngày mới nhất trong DB với **ngày giao dịch gần nhất của VN-Index (bỏ T7, CN, Lễ, tính mốc sau 15:00 giờ VN)** → hiện cảnh báo nhắc cập nhật trước khi quét. Ngày lễ VN tự động cập nhật theo năm. |
| **3. Chuẩn hóa Giá** | **100% Giá đã điều chỉnh (`Adjusted Price`)** | `vnstock` trả về giá đã điều chỉnh cổ tức/chia tách. Toàn bộ OHLCV được lưu dạng adjusted trước khi resample sang `1W`/`1M` và tính chỉ báo. |
| **4. Thang đo Đồ thị** | **100% Log Scale** | Khóa cứng `yaxis_type="log"` trên cả 3 khung `1M` → `1W` → `1D` cho toàn bộ đồ thị giá. |
| **5. Auto-Pitchfork 3 điểm** | **2 chiều Đối xứng (Bearish & Bullish) + Swing Window (`N=5`)** | Dùng `scipy.signal.argrelextrema` với cửa sổ mặc định `N=5` nến mỗi bên (có thanh trượt chỉnh `N` từ `2` đến `20` trên UI). Chọn P1 gần nhất hiện tại. Vẽ 1 Bearish + 1 Bullish (checkbox bật/tắt). Warning Lines mặc định TẮT (checkbox bật). Bắt buộc tính trung điểm bằng trung bình nhân trên trục $\log_{10}$. |
| **6. Vẽ Trendline & Công cụ Nâng cao** | **Hybrid Auto + Manual + Gann (KHÔNG có P&F)** | Tích hợp sẵn **Auto-Trendline + vẽ tay Plotly** (persist vào SQLite) và **W.D. Gann (Gann Fan, Gann Box, Square of 9, Time Cycles)** ngay trong bản v1.0. **Đã loại bỏ Point & Figure (P&F)**. |
| **7. Trọng số Top-Down (0–100)** | **10% – 20% – 20% – 10% – 40%** *(tùy chỉnh bằng Slider)* | Thiên văn/Gann (10%) + Vĩ mô/Margin/Yield Curve (20%) + Hàng hóa/RRG Ngành (20%) + Phái sinh/Độ rộng (10%) + VN-Index 1M-1W-1D (40%, có tùy chọn loại bỏ nhóm Vingroup). |
| **8. Quản trị Vị thế & Cảnh báo** | **Scaling-Out 50/50 + Auto Alert Danh mục (Chỉ BUY)** | Tab Nhật ký lệnh chỉ hỗ trợ BUY. Tự động đối chiếu giá đóng cửa mới nhất trong Local DB với các mốc **Stop-Loss / Trailing Stop / Target 1 (50%) / Target 2 (50%)** để bật cờ cảnh báo trực quan cho các mã đang giữ. |

---

## PHẦN 1: GIẢI PHẪU CASE STUDY THỰC CHIẾN & MODULE LỊCH SỬ LUÂN CHUYỂN NGÀNH

### 1.1. Ma trận Giải phẫu Đa khung ($1M \to 1W \to 1D$) trên Thang Logarit (Case Study KDH & NLG)

| Khung thời gian | Vai trò trong Hệ thống | Cấu trúc thực chiến (KDH mua 14.0 — 05/11/2026; NLG mua 21.2 — 03/11/2026) | Quy tắc định lượng hóa cho Bộ lọc |
| :--- | :--- | :--- | :--- |
| **Khung Tháng (`1M` - Log)** | Định vị chu kỳ lớn & vùng hỗ trợ lịch sử | Giá rút chân tại hợp lưu: `MA200` + `EMA200` + hỗ trợ lịch sử + biên dưới Bullish Pitchfork. `Fisher(9) 1M` ở cực trị âm sâu ($< -2.5$). | **Vùng Đáy Chu Kỳ (Stage 1 $\to$ 2):** Giá nằm trong biên độ $\pm 8\%$ quanh `MA200/EMA200 (1M)` hoặc biên dưới Pitchfork `1M`; `Fisher(9) 1M < -2.0` và bắt đầu bẻ ngang/cắt lên. |
| **Khung Tháng (`1M` - Log)** | Định vị chu kỳ lớn & vùng hỗ trợ lịch sử | Giá rút chân tại hợp lưu: `MA200` + `EMA200` + hỗ trợ lịch sử + biên dưới Bullish Pitchfork. `Fisher(9) 1M` ở cực trị âm sâu ($< -2.5$). | **Vùng Đáy Chu Kỳ (Stage 1 → 2):** Giá nằm trong biên độ $\pm 8\%$ quanh `MA200/EMA200 (1M)` hoặc biên dưới Pitchfork `1M`; `Fisher(9) 1M < -2.0` và bắt đầu bẻ ngang/cắt lên. |
| **Khung Tuần (`1W` - Log)** | Xác nhận dòng tiền lớn & đảo chiều xu hướng trung hạn | Khối lượng tuần bùng nổ ($> 2.5\times \text{SMA}_9(\text{Vol})$ ở KDH). `MACD(12, 26, 9)` Histogram thu hẹp đà giảm hoặc mở rộng dương; `RSI(14)` thoát quá bán. | **Xác nhận Dòng tiền:** `Volume 1W` $\ge 1.8 \times \text{SMA}_9(\text{Vol})$, `MFI(14) 1W` hướng lên trên mốc 45, giá giữ vững biên dưới hoặc phá vỡ cạnh trên Bearish Pitchfork `1W`. |
| **Khung Ngày (`1D` - Log)** | Căn điểm vào lệnh (Entry), quản trị vị thế & chốt lời | `Fisher(9) 1D` cắt lên đường tín hiệu từ vùng âm sâu (Entry). Khi giá tiến sát cản `MA120/EMA120 1D` và `Fisher(9) 1D > +1.9` $\to$ quá mua ngắn hạn (chốt 50%). | **Quy tắc Scaling-Out 50/50:** Mua khi `Fisher(9) 1D` cắt lên + vượt `EMA21`. Chốt 50% khi `Fisher(9) 1D > +2.0` chạm cản `EMA120/MA120 1D`; giữ 50% với Trailing Stop dưới `EMA21/MA50 1D` để ăn sóng khung Tuần. |
| **Khung Ngày (`1D` - Log)** | Căn điểm vào lệnh (Entry), quản trị vị thế & chốt lời | `Fisher(9) 1D` cắt lên đường tín hiệu từ vùng âm sâu (Entry). Khi giá tiến sát cản `MA120/EMA120 1D` và `Fisher(9) 1D > +1.9` → quá mua ngắn hạn (chốt 50%). | **Quy tắc Scaling-Out 50/50:** Mua khi `Fisher(9) 1D` cắt lên + vượt `EMA21`. Chốt 50% khi `Fisher(9) 1D > +2.0` chạm cản `EMA120/MA120 1D`; giữ 50% với Trailing Stop dưới `EMA21/MA50 1D` để ăn sóng khung Tuần. |

### 1.2. Lớp lọc "An toàn Bảng cân đối" (Balance Sheet Gatekeeper — Tham khảo `vfin.vn`)
Mọi mã vượt qua bộ lọc kỹ thuật phải đi qua lớp kiểm tra cơ bản (nạp từ MSN Finance + bảng `fundamentals_manual.csv` lưu trong SQLite):
Mọi mã vượt qua bộ lọc kỹ thuật phải đi qua lớp kiểm tra cơ bản (nạp từ `vnstock` Finance module + bảng `fundamentals_manual` trong SQLite):
1. **Đòn bẩy an toàn:** $\text{Nợ vay} / \text{Vốn chủ sở hữu} < 1.2$ (nhóm phi tài chính).
2. **Định giá chiết khấu:** $P/B \le 1.3$ khi bắt đáy chu kỳ (ưu tiên $P/B < 1.0$ như NLG tại vùng 21.2).
3. **Thanh khoản thực:** Giá trị giao dịch trung bình 20 phiên $\ge 15$ tỷ VNĐ/phiên (loại mã bo cung / kẹt thanh khoản giải chấp như KOS).

### 1.3. Module Lịch sử Luân chuyển Ngành (Sector Rotation Backtest — Chuẩn Martin Pring / John Murphy)
* Phân nhóm rổ cổ phiếu đại diện cho 9 ngành chính Việt Nam (Ngân hàng, Chứng khoán, Bất động sản, Thép/VLXD, Dầu khí, Bán lẻ, Công nghệ, Điện/Nước, Đầu tư công).
* Phân nhóm rổ cổ phiếu đại diện cho 9 ngành chính Việt Nam (Ngân hàng, Chứng khoán, Bất động sản, Thép/VLXD, Dầu khí, Bán lẻ, Công nghệ, Điện/Nước, Đầu tư công). Phân nhóm tự động theo chuẩn **ICB** từ `vnstock` → `Reference("dnse").industry.sectors()`.
* Đối chiếu hiệu suất từng nhóm ngành sau các mốc lịch sử (*Đáy 03/2020*, *Đỉnh 04/2022*, *Đáy 11/2022*, *Nhịp chỉnh 2026*) sau +1M, +3M, +6M, +12M để rút bài học luân chuyển dòng tiền theo 4 pha kinh tế của Martin Pring.

---

## PHẦN 2: ĐẶC TẢ TOÁN HỌC & THUẬT TOÁN LÕI (CORE QUANT ENGINE)

Toàn bộ dữ liệu giá đầu vào là **Giá đã điều chỉnh (`Adj Close` / `auto_adjust=True`)**. Mọi tính toán hình học thực hiện trên trục Logarit cơ số 10:
Toàn bộ dữ liệu giá đầu vào là **Giá đã điều chỉnh** (vnstock trả về adjusted price). Mọi tính toán hình học thực hiện trên trục Logarit cơ số 10:
$$y_i = \log_{10}(P_i), \quad t_i = \text{chỉ số nến nguyên liên tục (bar index)}$$

### 2.1. Auto-Pitchfork 3 Điểm trên Trục Logarit (Swing Window `N=5`)
* **Phát hiện Pivot:** Dùng `scipy.signal.argrelextrema(high_log, np.greater_equal, order=N)` và `argrelextrema(low_log, np.less_equal, order=N)` với `N = 5` mặc định (có thanh trượt `N` từ `2` đến `20` trên giao diện).
* **Chế độ 1 — Bearish / Corrective Pitchfork (Quy tắc gốc của người dùng):**
  * $P_1$: Đỉnh Swing High gốc; $P_2$: Đáy Swing Low thấp nhất & gần nhất bên phải $P_1$ ($t_2 > t_1$); $P_3$: Đỉnh Swing High cao nhất & gần nhất bên phải $P_2$ ($t_3 > t_2, P_3 < P_1$).
* **Quy tắc chọn bộ 3 điểm (đã khóa):**
  * **P1 gần nhất hiện tại** (không phải đỉnh/đáy cao/thấp nhất toàn bộ lịch sử).
  * Vẽ **1 Bearish + 1 Bullish** cùng lúc (có checkbox bật/tắt từng loại).
  * Warning Lines ±50%, ±100% — mặc định **TẮT** (có checkbox bật).
  * Khi thay đổi slider `N`, Pitchfork cập nhật ngay real-time.
* **Chế độ 1 — Bearish / Corrective Pitchfork:**
  * $P_1$: Đỉnh Swing High gần nhất; $P_2$: Đáy Swing Low thấp nhất & gần nhất bên phải $P_1$ ($t_2 > t_1$); $P_3$: Đỉnh Swing High cao nhất & gần nhất bên phải $P_2$ ($t_3 > t_2, P_3 < P_1$).
* **Chế độ 2 — Bullish Pitchfork (Đối xứng):**
  * $P_1$: Đáy Swing Low gốc; $P_2$: Đỉnh Swing High cao nhất & gần nhất bên phải $P_1$ ($t_2 > t_1$); $P_3$: Đáy Swing Low thấp nhất & gần nhất bên phải $P_2$ ($t_3 > t_2, P_3 > P_1$).
  * $P_1$: Đáy Swing Low gần nhất; $P_2$: Đỉnh Swing High cao nhất & gần nhất bên phải $P_1$ ($t_2 > t_1$); $P_3$: Đáy Swing Low thấp nhất & gần nhất bên phải $P_2$ ($t_3 > t_2, P_3 > P_1$).
* **Phương trình 3 đường (Trung bình nhân trên trục Log):**
  $$t_M = \frac{t_2 + t_3}{2}, \qquad y_M = \frac{\log_{10}(P_2) + \log_{10}(P_3)}{2}, \qquad m = \frac{y_M - y_1}{t_M - t_1}$$
  $$P_{\text{ML}}(t) = 10^{\, y_1 + m(t - t_1)}, \qquad P_{\text{L2}}(t) = 10^{\, y_2 + m(t - t_2)}, \qquad P_{\text{L3}}(t) = 10^{\, y_3 + m(t - t_3)}$$
  *(Kèm tùy chọn bật Warning Lines $\pm 50\%, \pm 100\%$ khoảng cách $\Delta y = |y_2 - y_M|$).*

### 2.2. Bộ Chỉ báo Kỹ thuật Chuẩn hóa
1. **Đường Trung bình Động:** Mặc định vẽ `EMA(120)`, `EMA(200)`, `MA(120)`, `MA(200)` + bổ sung `EMA(21)` và `MA(50)` (checkbox bật/tắt).
2. **RSI(14):** Wilder's Smoothing ($\alpha = 1/14$), tự động đánh dấu phân kỳ dương/âm.
2. **RSI(14):** Wilder's Smoothing ($\alpha = 1/14$), tự động đánh dấu phân kỳ dương/âm (dùng cùng Swing Window `N` như Pitchfork để detect pivot, vẽ đường nối 2 đáy/đỉnh + annotation text trên cả 3 khung 1M/1W/1D).
3. **MACD(12, 26, 9):** $\text{EMA}_{12} - \text{EMA}_{26}$, Signal $\text{EMA}_9$, Histogram.
4. **Ehlers Fisher Transform(9):**
   $$x_t = \frac{\text{High}_t + \text{Low}_t}{2}, \quad v_t = \text{clip}\left(0.66 \left(\frac{x_t - \min_9(x)}{\max_9(x) - \min_9(x)} - 0.5\right) + 0.67 v_{t-1},\; -0.999,\; 0.999\right)$$
   $$F_t = 0.5 \ln\left(\frac{1 + v_t}{1 - v_t}\right) + 0.5 F_{t-1}, \qquad \text{Trigger}_t = F_{t-1}$$
   Giá trị khởi tạo: $v_0 = 0$, $F_0 = 0$. Chuỗi < 9 nến dùng expanding window.
5. **Dòng tiền & Khối lượng:** `MFI(14)` và `VolRatio` $= \text{Volume}_t / \text{SMA}_9(\text{Volume})$ (tô nổi khi $\ge 1.8$).

### 2.3. Auto-Trendline Hybrid (Phương án C)
* **Tự động:** Nối các cặp Pivot cùng Swing Window `N` trong không gian $\log_{10}(P)$ tạo 2 đường kháng cự giảm gần nhất và 2 đường hỗ trợ tăng gần nhất (loại đường bị thân nến xuyên thủng quá 2 lần).
* **Vẽ tay tương tác:** Bật thanh công cụ Plotly `modeBarButtonsToAdd=['drawline', 'drawopenpath', 'eraseshape']` để người dùng kẻ/xóa thêm đường trực tiếp trên đồ thị Log.
* **Tự động:** Nối các cặp Pivot cùng Swing Window `N` trong không gian $\log_{10}(P)$ tạo 2 đường kháng cự giảm gần nhất (theo thời gian) và 2 đường hỗ trợ tăng gần nhất (loại đường bị thân nến close xuyên thủng quá 2 lần). Trendline kéo dài đến cuối chart.
* **Vẽ tay tương tác:** Bật thanh công cụ Plotly `modeBarButtonsToAdd=['drawline', 'drawopenpath', 'eraseshape']` để người dùng kẻ/xóa thêm đường trực tiếp trên đồ thị Log. **Persist vào SQLite** (lưu lâu dài qua các phiên sử dụng).

### 2.4. Bộ công cụ W.D. Gann (Đưa vào ngay bản v1.0)
1. **Gann Time Cycles & Fibonacci Time:** Từ một ngày Đỉnh/Đáy gốc chọn trên UI $\to$ chiếu tự động các mốc đảo chiều (+30, +45, +60, +90, +144, +180, +360 ngày lịch và 21, 34, 55, 89, 144 phiên).
1. **Gann Time Cycles & Fibonacci Time:** Từ một ngày Đỉnh/Đáy gốc chọn trên UI → chiếu tự động các mốc đảo chiều (+30, +45, +60, +90, +144, +180, +360 **ngày lịch** và 21, 34, 55, 89, 144 **phiên giao dịch**).
2. **Gann Square of 9 (Tính mức hỗ trợ/kháng cự theo góc độ):** Từ giá Đỉnh hoặc Đáy gốc $P_0$:
   $$P_{\text{target}}(\theta, k) = \left(\sqrt{P_0} \pm \frac{\theta}{180^\circ} \cdot k\right)^2$$
   Tính tự động các mốc góc $45^\circ, 90^\circ, 180^\circ, 270^\circ, 360^\circ$ (cả chiều giảm từ đỉnh như case FPT và chiều tăng từ đáy như KDH/NLG).
3. **Gann Fan & Gann Box trên trục Log:** Cho phép chọn 2 điểm neo (Đỉnh/Đáy) $\to$ tự động vẽ các tia tỷ lệ Gann ($1\times 1, 1\times 2, 2\times 1, 1\times 4, 4\times 1$) và lưới hộp thời gian–giá (25%, 50%, 75%) phủ trực tiếp lên đồ thị.
   $$P_{\text{target}}(\theta, k) = \left(\sqrt{P_0} \pm \frac{\theta}{180°} \cdot k\right)^2$$
   Hệ số `k = 1` mặc định (có slider chỉnh 0.5 → 2.0). Tính tự động các mốc góc $45°, 90°, 180°, 270°, 360°$ (cả chiều giảm từ đỉnh như case FPT và chiều tăng từ đáy như KDH/NLG).
3. **Gann Fan & Gann Box trên trục Log:** Cho phép chọn 2 điểm neo (Đỉnh/Đáy) → tự động vẽ các tia tỷ lệ Gann ($1\times 1, 1\times 2, 2\times 1, 1\times 4, 4\times 1$) trên trục Log (1×1 = 45° trên chart log). Lưới hộp Gann Box: chia $\log_{10}(P_{high}) - \log_{10}(P_{low})$ theo 25%, 50%, 75% phủ trực tiếp lên đồ thị.

### 2.5. Biểu đồ Point & Figure (P&F — Đưa vào ngay bản v1.0)
Theo chuẩn sách *The Definitive Guide to Point and Figure* (Jeremy du Plessis — Wiley):
* **Cấu trúc cột X/O trên thang Log (% Box Size):** Mặc định **Box Size = 2% (khung 1D)** hoặc **3% (khung 1W)**, **Reversal = 3-Box** (có bộ chọn chỉnh Box Size & Reversal trên UI).
* **Công thức Đo Mục tiêu Giá từ Đỉnh / Đáy (Price Objective Count):**
  * **Vertical Count (Đo theo cột bứt phá/rơi đầu tiên):**
    $$\text{Target}_{\text{down}} = P_{\text{top}} \times (1 - b)^{(\text{Số ô cột O đầu} \times \text{Reversal})}, \qquad \text{Target}_{\text{up}} = P_{\text{bottom}} \times (1 + b)^{(\text{Số ô cột X đầu} \times \text{Reversal})}$$
  * **Horizontal Count (Đo theo bề rộng vùng tích lũy/phân phối):** Nhân số cột đi ngang trong nền tích lũy/phân phối với hệ số Reversal và Box Size ($b$) để phóng chiếu vùng mục tiêu (ví dụ kiểm chứng mục tiêu giảm từ đỉnh FPT hoặc mục tiêu tăng từ đáy KDH/NLG).
### 2.5. Mô hình Định giá Chứng quyền (Black-Scholes cho Tầng 6)

### 2.6. Mô hình Định giá Chứng quyền (Black-Scholes cho Tầng 6)
Tính tự động cho Call Warrant: Giá hợp lý $C_{\text{fair}} = \frac{S \cdot N(d_1) - K e^{-rT} N(d_2)}{CR}$, **Implied Volatility (IV)** (Newton-Raphson), **Delta**, **Theta/ngày**, **Effective Gearing**, **Độ lệch định giá (%)**, **Điểm hòa vốn (Breakeven)** và ma trận mô phỏng lợi nhuận (Payoff Matrix).
> **Giải thích Black-Scholes đơn giản:**
> Black-Scholes là công thức toán học để tính **giá hợp lý** (fair value) của Chứng quyền (CW). Nó giúp bạn biết CW đang được bán **đắt hơn hay rẻ hơn** so với giá trị thực, dựa trên: giá cổ phiếu cơ sở ($S$), giá thực hiện ($K$), thời gian còn lại đến đáo hạn ($T$), lãi suất ($r$), và mức độ biến động giá ($\sigma$). Từ đó tính ra các chỉ số giúp quyết định mua/bán CW:
> - **Giá hợp lý (Fair Value):** CW đáng giá bao nhiêu → so với giá thị trường để biết đắt/rẻ
> - **IV (Implied Volatility):** Mức biến động thị trường đang kỳ vọng → IV cao = CW đắt
> - **Delta:** Giá CW thay đổi bao nhiêu khi cổ phiếu cơ sở tăng/giảm 1 đơn vị
> - **Theta:** CW mất giá bao nhiêu mỗi ngày do thời gian trôi (time decay)
> - **Effective Gearing:** Đòn bẩy hiệu quả thực tế của CW
> - **Breakeven:** Giá cổ phiếu cơ sở cần đạt để CW hòa vốn
> - **Payoff Matrix:** Bảng mô phỏng lãi/lỗ theo nhiều kịch bản giá khác nhau

**Công thức:** Tính tự động cho Call Warrant: $C_{\text{fair}} = \frac{S \cdot N(d_1) - K e^{-rT} N(d_2)}{CR}$

**Tham số đã khóa:**
| Tham số | Giá trị | Ghi chú |
|:---|:---|:---|
| Lãi suất phi rủi ro $r$ | 5% mặc định | Có input box cho người dùng tự chỉnh |
| Volatility $\sigma$ | Historical Volatility 60 ngày (close-to-close) | Tính tự động từ Local DB |
| IV Seed (Newton-Raphson) | 30% | Tolerance = 1e-6 |
| Payoff Matrix | ±20% với bước 2% | 21 kịch bản giá |
| Conversion Ratio (CR) | Lấy từ `vnstock` → `Reference().warrant.list()` | Tự động |

---

## PHẦN 3: KIẾN TRÚC LOCAL-FIRST DATABASE & CƠ CHẾ CẢNH BÁO LỊCH VN-INDEX

### 3.1. Quy trình Vận hành 2 Bước (Sync First $\to$ Scan Fast)
Để loại bỏ hoàn toàn tình trạng chậm, lag hoặc bị Yahoo Finance chặn IP khi quét hàng trăm mã:
### 3.1. Quy trình Vận hành 2 Bước (Sync First → Scan Fast)
Để loại bỏ hoàn toàn tình trạng chậm, lag khi quét hàng trăm mã:
1. **Bước 1 — Khởi tạo & Cập nhật Database cục bộ (`core/db_manager.py`):**
   * Lưu trữ tại thư mục `data/quant_local.db` (SQLite chứa metadata, lịch sử cập nhật, danh sách mã, BCTC, Margin, Phái sinh, Chứng quyền, Nhật ký lệnh) và `data/ohlcv/*.parquet` (lưu chuỗi OHLCV khung `1D` đã điều chỉnh cực nhẹ và đọc siêu tốc).
   * Lưu trữ tại file `data/quant_local.db` (SQLite chứa **toàn bộ dữ liệu**: OHLCV, metadata, lịch sử cập nhật, danh sách mã, BCTC, Margin tổng hợp, Phái sinh, Chứng quyền, Nhật ký lệnh, Đường vẽ tay).
   * Hỗ trợ **Incremental Update** (chỉ tải các phiên còn thiếu từ `last_date + 1` đến hiện tại thay vì tải lại toàn bộ lịch sử từ đầu), kèm thanh tiến trình (`st.progress`) và cơ chế `sleep(0.3s)` chống rate-limit.
   * Lịch sử ban đầu: Tải **max available** từ vnstock (cổ phiếu VN thường từ ~2007-2012 tùy mã). Vĩ mô quốc tế (yfinance) cũng tải **max available**.
   * Nếu vnstock lỗi cho 1 mã cụ thể (mã ngừng giao dịch, hủy niêm yết) → retry 3 lần, đánh dấu lỗi bằng `st.warning()` trên UI, bỏ qua mã đó.

> **Giải thích SQLite:**
> SQLite là database chạy ngay trên máy bạn dưới dạng 1 file duy nhất (`quant_local.db`), không cần cài server. Dữ liệu OHLCV của tất cả các mã sẽ được lưu trực tiếp trong các bảng SQLite (thay vì file Parquet riêng lẻ). Ưu điểm: đơn giản, 1 file chứa tất cả, dễ backup/di chuyển.

2. **Bước 2 — Bộ Kiểm tra Lịch giao dịch VN-Index (`VNIndexCalendarGuard`):**
   * Xác định ngày giao dịch gần nhất kỳ vọng (`expected_last_trading_day`) theo múi giờ Việt Nam (`Asia/Ho_Chi_Minh`):
     * Nếu hôm nay là **Thứ 7** $\to$ lùi về **Thứ 6**.
     * Nếu hôm nay là **Chủ Nhật** $\to$ lùi về **Thứ 6**.
     * Nếu hôm nay là **Thứ 2 – Thứ 6** nhưng **trước 15:05 chiều** (thị trường chưa đóng cửa xong phiên ATC) $\to$ lùi về ngày làm việc liền trước (nếu là Thứ 2 thì lùi về Thứ 6 tuần trước).
     * Hỗ trợ danh sách ngày lễ Tết Việt Nam (`VN_HOLIDAYS` trong `config/settings.py`) để không báo lệch giả vào ngày lễ.
     * Nếu hôm nay là **Thứ 7** → lùi về **Thứ 6**.
     * Nếu hôm nay là **Chủ Nhật** → lùi về **Thứ 6**.
     * Nếu hôm nay là **Thứ 2 – Thứ 6** nhưng **trước 15:05 chiều** (thị trường chưa đóng cửa xong phiên ATC) → lùi về ngày làm việc liền trước (nếu là Thứ 2 thì lùi về Thứ 6 tuần trước).
     * **Ngày lễ VN tự động cập nhật theo năm:** Hệ thống tự tính ngày lễ cố định hàng năm (Tết Dương lịch 1/1, Giỗ Tổ 10/3 ÂL, 30/4-1/5, Quốc khánh 2/9) + Tết Nguyên Đán (tra bảng lịch âm-dương), kèm ngày nghỉ bù nếu trùng Chủ Nhật. Có file `config/vn_holidays.py` tự sinh danh sách cho năm hiện tại.
   * **Hành vi trên Giao diện:** Trước khi người dùng chạy Bộ lọc (`Screener`) hoặc mở Dashboard:
     * Nếu Database chưa được khởi tạo $\to$ Khóa nút Quét, hiện hướng dẫn bấm **"Khởi tạo Database lần đầu"**.
     * Nếu `db_last_date < expected_last_trading_day` $\to$ Hiện **Banner cảnh báo màu vàng nổi bật**: *"⚠️ Dữ liệu Database đang dừng ở ngày `DD/MM/YYYY`, chậm hơn phiên giao dịch gần nhất của VN-Index (`DD/MM/YYYY`). Vui lòng bấm [Cập nhật Database] trước khi quét mã!"* (vẫn có nút phụ *"Bỏ qua & Quét trên dữ liệu cũ"* nếu người dùng muốn kiểm tra offline).
     * Nếu Database chưa được khởi tạo → Khóa nút Quét, hiện hướng dẫn bấm **"Khởi tạo Database lần đầu"**.
     * Nếu `db_last_date < expected_last_trading_day` → Hiện **Banner cảnh báo màu vàng nổi bật**: *"⚠️ Dữ liệu Database đang dừng ở ngày `DD/MM/YYYY`, chậm hơn phiên giao dịch gần nhất của VN-Index (`DD/MM/YYYY`). Vui lòng bấm [Cập nhật Database] trước khi quét mã!"* (vẫn có nút phụ *"Bỏ qua & Quét trên dữ liệu cũ"* nếu người dùng muốn kiểm tra offline).

### 3.2. Chiến lược Nguồn dữ liệu (Không `vnstock`)
* **Dữ liệu Giá OHLCV Cổ phiếu VN & Vĩ mô/Hàng hóa quốc tế:** `yfinance` (`auto_adjust=True`, hậu tố `.VN` cho rổ VN100 + Watchlist tự thêm; ticker quốc tế `DX-Y.NYB`, `VND=X`, `^TNX`, `^TYX`, `^VIX`, `GC=F`, `BZ=F`, `CL=F`, `HG=F`, `SLX`).
* **Nguồn dự phòng & Chỉ số VN:** **MSN Finance API** (`assets.msn.com/service/Finance/...`) làm fallback tự động lấy `VN-Index`, `VN30`, giá mã `.VN` khi Yahoo thiếu, và bổ sung `P/E`, `P/B`, `BVPS`, `Market Cap`.
* **Đường cong Lợi suất Mỹ:** Đọc trực tiếp CSV công khai từ **FRED** (`T10Y2Y`, `T10Y3M`).
* **Dữ liệu Đặc thù Việt Nam (CSV/Excel Import & Edit trên UI):**
  * `vn_margin_history.xlsx / .csv` (hỗ trợ nạp thẳng file `vnindex_margin_2000_2026.xlsx` của bạn).
  * `vn30f_history.csv` (Phái sinh VN30F1M, Basis, OI).
  * `cw_watchlist.csv` (Danh sách Chứng quyền đang giao dịch).
  * `fundamentals_manual.csv` (Bổ sung nhanh Nợ/VCSH, Tiền mặt, BVPS nếu MSN thiếu).
* **Cổng Mở rộng Tương lai (Plugin Interface):** Thiết kế sẵn class trừu tượng `BaseDataProvider` trong `core/data_fetcher.py` để sau này nếu bạn muốn cắm trực tiếp **SSI FastConnect / Open API** chỉ cần viết thêm 1 file adapter mà không phải sửa code ứng dụng.
### 3.2. Chiến lược Nguồn dữ liệu (Đã cập nhật v4.0)

| Loại dữ liệu | Nguồn (Free) | Code mẫu |
|:---|:---|:---|
| **OHLCV cổ phiếu VN** | `vnstock` Community | `Market("dnse").equity("FPT").ohlcv(start=..., interval="1D")` |
| **VN-Index, VN30, HNX-Index** | `vnstock` Community | `Market("dnse").index("VNINDEX").ohlcv(...)` |
| **Danh sách mã niêm yết** | `vnstock` Community | `Reference("dnse").equity.list(exchange="HOSE")` |
| **Phân ngành ICB** | `vnstock` Community | `Reference("dnse").industry.sectors()` |
| **P/E, P/B, BCTC** | `vnstock` Finance module | Báo cáo tài chính cơ bản (giới hạn số kỳ ở bản free) |
| **VN30F1M Phái sinh** | `vnstock` Community | `Market().futures("VN30F1M").ohlcv(start=..., interval="1D")` |
| **Chứng quyền CW** | `vnstock` Community | `Reference().warrant.list()` + `Market().warrant("CFPT2501").ohlcv(...)` |
| **Dư nợ Margin VN** | Tự tổng hợp từ BCTC CTCK qua `vnstock` | Lấy BCTC quý của top 15 CTCK (SSI, HCM, VCI, VND, TCBS, VPS, HSC...) → cộng khoản mục "Cho vay giao dịch ký quỹ" + hỗ trợ Import file Excel bổ sung |
| **OHLCV quốc tế** | `yfinance` | `DX-Y.NYB` (DXY), `VND=X`, `^TNX`, `^TYX`, `^VIX`, `GC=F`, `BZ=F`, `CL=F`, `HG=F`, `SLX` |
| **Yield Curve Mỹ** | FRED CSV công khai | Download tự động từ URL FRED khi cập nhật DB (`T10Y2Y`, `T10Y3M`) |

* **Cổng Mở rộng Tương lai (Plugin Interface):** Thiết kế sẵn class trừu tượng `BaseDataProvider` trong `core/data_fetcher.py` để sau này nếu muốn cắm trực tiếp **SSI FastConnect / Open API** chỉ cần viết thêm 1 file adapter.

### 3.3. SQLite Schema chi tiết

```sql
-- Bảng metadata quản lý danh sách mã & ngày cập nhật
CREATE TABLE stock_metadata (
    ticker TEXT PRIMARY KEY,
    exchange TEXT,           -- HOSE, HNX, UPCOM
    icb_sector TEXT,         -- Phân ngành ICB từ vnstock
    icb_industry TEXT,
    market_cap REAL,
    last_updated DATE,
    is_vingroup INTEGER DEFAULT 0,  -- Flag nhóm Vingroup (VIC, VHM, VRE, VGI...)
    status TEXT DEFAULT 'ACTIVE'    -- ACTIVE, DELISTED, ERROR
);

-- Bảng OHLCV chính (tất cả mã, khung 1D)
CREATE TABLE ohlcv_daily (
    ticker TEXT,
    date DATE,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (ticker, date)
);

-- Bảng OHLCV quốc tế (DXY, Vàng, Dầu, VIX...)
CREATE TABLE ohlcv_global (
    ticker TEXT,
    date DATE,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    PRIMARY KEY (ticker, date)
);

-- Bảng Phái sinh VN30F
CREATE TABLE derivatives_daily (
    ticker TEXT,            -- VN30F1M, VN30F2M
    date DATE,
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    oi INTEGER,             -- Open Interest (nếu vnstock cung cấp)
    PRIMARY KEY (ticker, date)
);

-- Bảng chỉ số tài chính cơ bản
CREATE TABLE fundamentals (
    ticker TEXT,
    quarter TEXT,           -- '2026Q3'
    pe REAL, pb REAL, bvps REAL,
    total_debt REAL,
    equity REAL,
    debt_to_equity REAL,
    revenue REAL,
    net_income REAL,
    source TEXT DEFAULT 'vnstock',  -- vnstock hoặc manual
    PRIMARY KEY (ticker, quarter)
);

-- Bảng Dư nợ Margin tổng hợp
CREATE TABLE margin_history (
    quarter TEXT PRIMARY KEY,   -- '2026Q3'
    total_margin_bn REAL,       -- Tổng dư nợ margin (tỷ VNĐ)
    vnindex_close REAL,         -- VN-Index đóng cửa cuối quý
    source TEXT,                -- 'auto_bctc' hoặc 'manual_import'
    notes TEXT
);

-- Bảng Chứng quyền metadata
CREATE TABLE warrants (
    cw_ticker TEXT PRIMARY KEY,
    underlying TEXT,
    strike_price REAL,
    maturity_date DATE,
    conversion_ratio REAL,
    issuer TEXT,
    last_updated DATE
);

-- Nhật ký lệnh (Chỉ BUY)
CREATE TABLE trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    entry_date DATE NOT NULL,
    entry_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    stop_loss REAL,
    trailing_stop REAL,
    target_1 REAL,
    target_2 REAL,
    status TEXT DEFAULT 'OPEN',       -- OPEN, PARTIAL, CLOSED
    exit_date_1 DATE,                 -- Ngày chốt 50% (Target 1)
    exit_price_1 REAL,
    exit_qty_1 INTEGER,
    exit_date_2 DATE,                 -- Ngày chốt phần còn lại
    exit_price_2 REAL,
    exit_qty_2 INTEGER,
    pnl_pct REAL,                     -- % Lãi/Lỗ tổng
    notes TEXT
);

-- Đường vẽ tay Plotly (persist lâu dài)
CREATE TABLE user_drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timeframe TEXT NOT NULL,          -- '1D', '1W', '1M'
    drawing_type TEXT,                -- 'line', 'path'
    drawing_json TEXT,                -- JSON data từ Plotly shapes
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Yield Curve data
CREATE TABLE yield_curve (
    date DATE PRIMARY KEY,
    t10y2y REAL,
    t10y3m REAL
);

-- Sự kiện Chính trị/Chính sách
CREATE TABLE macro_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date DATE,
    event_type TEXT,                   -- FOMC, NHNN, QUOC_HOI, OTHER
    description TEXT,
    impact TEXT                        -- BULLISH, BEARISH, NEUTRAL
);
```

---

## PHẦN 4: KIẾN TRÚC 6 TẦNG TOP-DOWN & HỆ THỐNG CHẤM ĐIỂM (0–100)

### 4.1. Công thức Tổng hợp Top-Down Composite Score (0–100)
$$\text{Total Score} = 0.10 S_{\text{T1}} + 0.20 S_{\text{T2}} + 0.20 S_{\text{T3}} + 0.10 S_{\text{T4}} + 0.40 S_{\text{T5}}$$
$$\text{Total Score} = w_1 S_{\text{T1}} + w_2 S_{\text{T2}} + w_3 S_{\text{T3}} + w_4 S_{\text{T4}} + w_5 S_{\text{T5}}$$

Trọng số mặc định: $w_1 = 0.10, w_2 = 0.20, w_3 = 0.20, w_4 = 0.10, w_5 = 0.40$

*(Kèm thanh trượt trên Sidebar cho phép người dùng tự điều chỉnh trọng số 5 thành phần, hệ thống tự chuẩn hóa tổng về 100%).*

### 4.2. Chi tiết 7 Trang Chức năng (Streamlit Multi-Page)
### 4.2. SCORING RUBRIC CHI TIẾT TỪNG TẦNG (0–100) — Best Practice Design

#### Tầng 1 — Thiên văn & Gann ($S_{T1}$, Trọng số 10%) — **NGƯỜI DÙNG TỰ CHẤM**

Do tính chất chủ quan của phân tích thiên văn/Gann, tầng này **để người dùng tự đánh giá bằng slider 0–100** trên UI, kèm bảng tham khảo gợi ý:

| Điều kiện tham khảo | Điểm gợi ý |
|:---|:---:|
| Gann Time Cycle trùng vùng đảo chiều + New Moon + Thủy Tinh thuận hành | 80–100 |
| Gann Time Cycle gần vùng đảo chiều, không có tín hiệu thiên văn rõ | 50–70 |
| Không có tín hiệu Gann đáng chú ý | 40–50 |
| Thủy Tinh nghịch hành + Full Moon + vùng Gann trung tính | 20–40 |
| Nhiều tín hiệu cảnh báo cùng lúc | 0–20 |

#### Tầng 2 — Vĩ mô & Margin ($S_{T2}$, Trọng số 20%) — **TỰ ĐỘNG**

$$S_{T2} = 0.25 \cdot S_{\text{yield}} + 0.15 \cdot S_{\text{DXY}} + 0.15 \cdot S_{\text{VIX}} + 0.15 \cdot S_{\text{VND}} + 0.30 \cdot S_{\text{margin}}$$

| Chỉ số | Điều kiện | Điểm |
|:---|:---|:---:|
| **Yield Curve (T10Y2Y)** | > +0.5% (dương rõ, kinh tế mở rộng) | 90 |
| | 0% → +0.5% (dương nhẹ) | 70 |
| | -0.2% → 0% (gần đảo ngược) | 40 |
| | < -0.2% (đảo ngược, cảnh báo suy thoái) | 15 |
| **DXY** | < 100 (USD yếu, dòng tiền chảy vào EM) | 85 |
| | 100–104 | 60 |
| | 104–108 | 35 |
| | > 108 (USD quá mạnh, rủi ro EM) | 15 |
| **VIX** | < 15 (thị trường bình lặng) | 90 |
| | 15–20 | 70 |
| | 20–30 | 40 |
| | > 30 (hoảng loạn) | 10 |
| **VND/USD** | Ổn định hoặc VND tăng giá (Rate giảm) | 80 |
| | VND mất giá nhẹ (< 2% / quý) | 55 |
| | VND mất giá mạnh (> 2% / quý) | 20 |
| **Margin Growth** | Margin tăng < 5% QoQ (tích lũy sớm) | 85 |
| | Margin tăng 5–15% QoQ (đang tăng tốc) | 65 |
| | Margin tăng > 15% QoQ (quá nóng, cảnh báo đỉnh) | 30 |
| | Margin giảm mạnh > 10% QoQ (giải chấp / đáy) | 50 |

#### Tầng 3 — Hàng hóa & RRG Ngành ($S_{T3}$, Trọng số 20%) — **TỰ ĐỘNG**

$$S_{T3} = 0.40 \cdot S_{\text{RRG}} + 0.30 \cdot S_{\text{commodity}} + 0.30 \cdot S_{\text{correlation}}$$

| Chỉ số | Điều kiện | Điểm |
|:---|:---|:---:|
| **RRG Quadrant (ngành đang xét)** | Leading (RS-Ratio > 100, RS-Mom > 100) | 90 |
| | Improving (RS-Ratio < 100, RS-Mom > 100) | 70 |
| | Weakening (RS-Ratio > 100, RS-Mom < 100) | 35 |
| | Lagging (RS-Ratio < 100, RS-Mom < 100) | 10 |
| **Hàng hóa liên quan** | Xu hướng thuận lợi cho ngành (vd: Dầu tăng → tốt cho Dầu khí VN) | 80 |
| | Trung tính | 50 |
| | Bất lợi (vd: Thép giảm mạnh → xấu cho HPG, HSG) | 20 |
| **Tương quan 20W** | Pearson correlation > +0.5 (cùng chiều mạnh) | Tính theo hướng thuận/bất lợi |

RRG dùng công thức JdK gốc, window **12 tuần** cho RS-Ratio, benchmark **VN-Index**. Trail/tail dài **8 kỳ**. Backtest hiệu suất bằng Simple Return (không tính cổ tức).

#### Tầng 4 — Phái sinh & Độ rộng ($S_{T4}$, Trọng số 10%) — **TỰ ĐỘNG**

$$S_{T4} = 0.25 \cdot S_{\text{basis}} + 0.25 \cdot S_{\text{OI}} + 0.30 \cdot S_{\text{breadth50}} + 0.20 \cdot S_{\text{AD}}$$

| Chỉ số | Điều kiện | Điểm |
|:---|:---|:---:|
| **Basis VN30F1M** | Basis > +5 điểm (Premium cao, kỳ vọng tăng) | 85 |
| | Basis 0 → +5 | 65 |
| | Basis -5 → 0 (Discount nhẹ) | 40 |
| | Basis < -5 (Discount sâu, bi quan) | 20 |
| **OI Trend (5 phiên)** | OI tăng + Giá tăng (Long mới vào) | 85 |
| | OI tăng + Giá giảm (Short mới vào) | 25 |
| | OI giảm + Giá tăng (Short cover) | 60 |
| | OI giảm + Giá giảm (Long bỏ cuộc) | 30 |
| **% Cổ phiếu > MA50** | > 70% | 90 |
| | 50–70% | 65 |
| | 30–50% | 40 |
| | < 30% | 15 |
| **AD Line slope (20 phiên)** | Slope dương mạnh (thị trường rộng tăng) | 85 |
| | Slope dương nhẹ | 60 |
| | Slope âm nhẹ | 35 |
| | Slope âm mạnh (phân kỳ âm vs VN-Index) | 15 |

#### Tầng 5 — VN-Index Đa khung ($S_{T5}$, Trọng số 40%) — **TỰ ĐỘNG**

**Tính cho VN-Index** (đánh giá thị trường chung), có **checkbox loại bỏ nhóm Vingroup** (VIC, VHM, VRE, VGI...) khỏi phép tính.

$$S_{T5} = 0.30 \cdot S_{\text{1M}} + 0.35 \cdot S_{\text{1W}} + 0.35 \cdot S_{\text{1D}}$$

Mỗi sub-score khung ($S_{\text{1M}}, S_{\text{1W}}, S_{\text{1D}}$) tính từ:

$$S_{\text{frame}} = 0.30 \cdot S_{\text{Fisher}} + 0.20 \cdot S_{\text{RSI}} + 0.20 \cdot S_{\text{MACD}} + 0.15 \cdot S_{\text{Vol}} + 0.15 \cdot S_{\text{Trend}}$$

| Chỉ báo | Điều kiện | Điểm |
|:---|:---|:---:|
| **Fisher(9)** | < -2.5 bắt đầu cắt lên (đáy sâu, cơ hội) | 95 |
| | -2.5 → -1.0, cắt lên | 75 |
| | -1.0 → +1.0 (trung tính) | 50 |
| | +1.0 → +2.0 (nóng) | 35 |
| | > +2.0 (quá mua, cảnh báo) | 15 |
| **RSI(14)** | < 30 (quá bán) | 85 |
| | 30–45 | 65 |
| | 45–55 (trung tính) | 50 |
| | 55–70 | 40 |
| | > 70 (quá mua) | 20 |
| **MACD Histogram** | Histogram âm → đang thu hẹp (bearish yếu dần) | 70 |
| | Histogram chuyển dương | 80 |
| | Histogram dương → đang mở rộng | 65 |
| | Histogram dương → đang thu hẹp | 40 |
| | Histogram chuyển âm | 20 |
| **VolRatio** | ≥ 2.5 kèm giá tăng (bùng nổ dòng tiền) | 90 |
| | 1.8–2.5 kèm giá tăng | 75 |
| | 0.8–1.8 | 50 |
| | ≥ 1.8 kèm giá giảm (xả hàng) | 25 |
| **Trend (giá vs EMA)** | Giá > EMA21 > EMA50 > EMA120 (uptrend mạnh) | 90 |
| | Giá > EMA21, EMA21 > EMA50 | 70 |
| | Giá < EMA21 nhưng > EMA50 (pullback) | 45 |
| | Giá < EMA50 < EMA120 (downtrend) | 15 |

**Tùy chọn loại bỏ nhóm Vingroup:** Khi bật, tính lại VN-Index bằng cách loại trọng số các mã VIC, VHM, VRE, VGI ra khỏi tính toán các chỉ báo kỹ thuật (tính lại OHLCV VN-Index adjusted = VN-Index gốc − đóng góp điểm Vingroup).

### 4.3. Chi tiết 7 Trang Chức năng (Streamlit Multi-Page)
1. **`app.py` (Master Dashboard & DB Control Center):**
   * Thanh trạng thái Local Database + Nút đồng bộ Incremental Update + Cảnh báo lịch VN-Index (T7/CN).
   * Đồng hồ điểm **Top-Down Score (0–100)** tổng hợp từ Tầng 1 $\to$ Tầng 5.
   * Thanh trạng thái Local Database + Nút đồng bộ Incremental Update + Cảnh báo lịch VN-Index (T7/CN/Lễ).
   * Đồng hồ điểm **Top-Down Score (0–100)** dạng Plotly gauge indicator, phân vùng màu: 0–30 = Đỏ (Bearish), 30–50 = Vàng (Neutral), 50–70 = Xanh lá (Bullish), 70–100 = Xanh đậm (Strong Bull). Hiện điểm từng tầng bên cạnh đồng hồ tổng.
   * Bảng tóm tắt **Cảnh báo Danh mục đang giữ** (hiển thị ngay nếu mã nào chạm Stop-Loss/Target).

2. **`pages/1_Astro_Gann.py` (Tầng 1 — Thiên văn & W.D. Gann — Trọng số 10%):**
   * Lịch pha Mặt Trăng (New/Full Moon) & Thủy Tinh nghịch hành (`ephem`) phủ lên đồ thị VN-Index Log.
   * Bộ tính **Gann Time Cycles**, **Gann Square of 9**, **Gann Fan & Gann Box** cho cả VN-Index và từng mã cổ phiếu.
   * **Slider chấm điểm Tầng 1 (0–100)** cho người dùng tự đánh giá.

3. **`pages/2_Macro_Margin.py` (Tầng 2 — Chính trị, Vĩ mô & Margin — Trọng số 20%):**
   * Đường cong lợi suất FRED (`T10Y2Y`, `T10Y3M`), `DXY`, `US10Y`, `VND=X`, `VIX`.
   * Biểu đồ tương quan **Dư nợ Margin vs. Đỉnh/Đáy VN-Index (2000–nay)** tách riêng mốc thời gian đỉnh/đáy thực tế; hỗ trợ Import file `vnindex_margin_2000_2026.xlsx` và cập nhật quý mới.
   * Bảng theo dõi sự kiện Chính trị/Chính sách (FOMC, NHNN, Quốc hội).
   * Biểu đồ tương quan **Dư nợ Margin vs. Đỉnh/Đáy VN-Index** — tự động tổng hợp từ BCTC các CTCK lớn qua vnstock + hỗ trợ Import file Excel bổ sung.
   * Bảng theo dõi sự kiện Chính trị/Chính sách (FOMC, NHNN, Quốc hội) — nhập từ UI editor.

4. **`pages/3_Commodities_RRG.py` (Tầng 3 — Hàng hóa, RRG & Lịch sử Ngành — Trọng số 20%):**
   * Biểu đồ **RRG 4 góc phần tư** cho Hàng hóa quốc tế và 9 nhóm Ngành Việt Nam (tính từ Local DB).
   * Ma trận tương quan Hàng hóa $\leftrightarrow$ Cổ phiếu VN và tab **Backtest Lịch sử Luân chuyển Ngành** (2020, 2022, 2026).
   * Biểu đồ **RRG 4 góc phần tư** cho Hàng hóa quốc tế và 9 nhóm Ngành Việt Nam (phân nhóm ICB tự động từ vnstock, tính từ Local DB).
   * Ma trận tương quan Hàng hóa ↔ Cổ phiếu VN và tab **Backtest Lịch sử Luân chuyển Ngành** (2020, 2022, 2026).

5. **`pages/4_Derivatives_Breadth.py` (Tầng 4 — Phái sinh & Độ rộng Thị trường — Trọng số 10%):**
   * Biểu đồ `VN30F1M`, **Basis (VN30F1M - VN30)** và **Open Interest (OI)** từ CSV/UI editor.
   * Biểu đồ `VN30F1M` (từ vnstock), **Basis (VN30F1M - VN30)** và **Open Interest (OI)**.
   * **Market Breadth** (tính hoàn toàn từ Local DB): % cổ phiếu trên `MA50`, % trên `MA200`, đường Advance/Decline Line.
6. **`pages/5_Stock_Screener_MTF.py` (Tầng 5 — Bộ lọc 1M-1W-1D Log, Auto-Pitchfork & P&F — Trọng số 40%):**
   * **Quét siêu tốc trên Local DB** với 3 Preset (*Bắt đáy Chu kỳ mẫu KDH/NLG*, *Breakout Bearish Pitchfork*, *Uptrend Pullback*) + lớp lọc *Balance Sheet Gatekeeper*.

6. **`pages/5_Stock_Screener_MTF.py` (Tầng 5 — Bộ lọc 1M-1W-1D Log, Auto-Pitchfork — Trọng số 40%):**
   * **Quét siêu tốc trên Local DB** với 3 Preset + lớp lọc *Balance Sheet Gatekeeper*:
     * **Preset 1 — Bắt đáy Chu kỳ (mẫu KDH/NLG):** Giá ±8% MA200(1M) ∧ Fisher(9,1M) < -2.0 bẻ ngang ∧ P/B ≤ 1.3 ∧ Nợ/VCSH < 1.2 ∧ GTGD 20p ≥ 15 tỷ
     * **Preset 2 — Breakout Bearish Pitchfork:** Close(1W) > Upper Bearish Pitchfork ∧ Vol(1W) ≥ 1.8× SMA9(Vol) ∧ MFI(14) > 45
     * **Preset 3 — Uptrend Pullback:** Giá pullback chạm EMA21(1D) ∧ EMA21 > EMA50 > EMA120 ∧ RSI(14) 40–55 ∧ Fisher(9) > -0.5
   * **Checkbox loại bỏ nhóm Vingroup** khỏi Tầng 5 scoring.
   * **Trạm Đồ thị Deep-Dive 100% Log Scale (`1M` / `1W` / `1D`):**
     * Tab 1: Biểu đồ Nến Log 4-panel (MA/EMA + Auto-Pitchfork Swing `N` + Auto-Trendline + Vẽ tay Plotly + Gann Fan/Box).
     * Tab 2: **Biểu đồ Point & Figure (P&F X/O)** tự động tính mục tiêu giá Horizontal/Vertical Count.
     * Tab 3: **Xuất Báo cáo Phân tích Tự động (1-Click)** ra Markdown / HTML (in PDF).
     * Tab 1: Biểu đồ Nến Log 4-panel (MA/EMA + Auto-Pitchfork Swing `N` + Auto-Trendline + Vẽ tay Plotly persist SQLite + Gann Fan/Box). Mặc định: 1D=500 nến, 1W=260 nến, 1M=120 nến (cho phép zoom/pan). 4-panel: P1=Giá+MA+Pitchfork+Gann, P2=RSI+Fisher, P3=MACD, P4=Volume+MFI.
     * Tab 2: **Xuất Báo cáo Phân tích Tự động (1-Click)** ra Markdown / HTML (Jinja2 template), lưu `data/reports/`.

7. **`pages/6_Warrants_CW.py` (Tầng 6 — Định giá & Lọc Chứng quyền Black-Scholes):**
   * Nạp danh sách CW từ CSV/UI, tự lấy giá cơ sở $S$ & độ biến động $\sigma_{60d}$ từ Local DB $\to$ tính Giá hợp lý, IV, Effective Gearing, Theta, Breakeven và Payoff Matrix.
   * Nạp danh sách CW tự động từ `vnstock` → `Reference().warrant.list()`, tự lấy giá cơ sở $S$ & độ biến động $\sigma_{60d}$ từ Local DB → tính Giá hợp lý, IV, Effective Gearing, Theta, Breakeven và Payoff Matrix (±20%, bước 2%, 21 kịch bản).

8. **`pages/7_Journal_Backtest.py` (Nhật ký Lệnh, Scaling-Out 50/50 & Hệ thống Cảnh báo Tự động):**
   * Chỉ hỗ trợ **BUY** (không có SELL SHORT).
   * Nạp sẵn 2 lệnh mẫu thực chiến: **KDH** (Mua 14.0 ngày 05/11/2026, chốt 15.7 ngày 13/11/2026) và **NLG** (Mua 21.2 ngày 03/11/2026, Trailing Stop 23.8–24.1, Target 1: 26.2–26.8, Target 2: 29.5–31.3).
   * **Auto-Alert Engine:** Tự động quét giá đóng cửa mới nhất trong Local DB của tất cả vị thế `OPEN` và gắn cờ màu:
     * 🔴 **CHẠM STOP / TRAILING STOP** (Giá $\le$ Stop)
     * 🟡 **CHẠM TARGET 1 — CHỐT 50%** (Giá $\ge$ Target 1)
     * 🟢 **CHẠM TARGET 2 — CHỐT PHẦN CÒN LẠI** (Giá $\ge$ Target 2)
     * 🔵 **ĐANG GỒNG LÃI AN TOÀN** (kèm tính % lãi/lỗ thực tế & gợi ý dời Trailing Stop theo `EMA21/MA50 1D`).
   * **Partial Exit (chốt 50%):** Lưu trên cùng 1 dòng gốc — cập nhật `exit_date_1`, `exit_price_1`, `exit_qty_1` khi chốt 50%, rồi `exit_date_2`, `exit_price_2`, `exit_qty_2` khi chốt phần còn lại. Status chuyển: OPEN → PARTIAL → CLOSED.
   * **Auto-Alert Engine:** Tự động quét giá đóng cửa mới nhất trong Local DB của tất cả vị thế `OPEN` / `PARTIAL` và gắn cờ màu:
     * 🔴 **CHẠM STOP / TRAILING STOP** (Giá ≤ Stop)
     * 🟡 **CHẠM TARGET 1 — CHỐT 50%** (Giá ≥ Target 1)
     * 🟢 **CHẠM TARGET 2 — CHỐT PHẦN CÒN LẠI** (Giá ≥ Target 2)
     * 🔵 **ĐANG GỒNG LÃI AN TOÀN** (kèm tính % lãi/lỗ thực tế & gợi ý dời Trailing Stop theo `EMA21/MA50 1D` — chỉ hiện gợi ý, không tự động cập nhật).
   * Cờ cảnh báo hiện trên cả Dashboard (`app.py`) và trang Journal.

---

## PHẦN 5: CẤU TRÚC THƯ MỤC & LỘ TRÌNH TRIỂN KHAI 4 PHA CHO ANTIGRAVITY

### 5.1. Thư viện (`requirements.txt` — Không cài `vnstock`)
### 5.1. Thư viện (`requirements.txt`)
```text
streamlit>=1.38.0
vnstock
vnstock-oapi
yfinance>=0.2.44
pandas>=2.2.0
numpy>=1.26.0
scipy>=1.13.0
plotly>=5.24.0
requests>=2.32.0
ephem>=4.1.5
jinja2>=3.1.4
openpyxl>=3.1.5
pyarrow>=17.0.0
```

### 5.2. Cấu trúc Thư mục Dự án
```text
topdown_quant_app/
├── app.py                          # Trang chủ: DB Sync Control, VN-Index Calendar Guard, Top-Down Score & Portfolio Alerts
├── requirements.txt
├── .streamlit/
│   └── config.toml                 # Dark theme: theme.base = "dark", layout = "wide"
├── config/
│   ├── tickers.py                  # Rổ VN100 (.VN), phân nhóm 9 Ngành, ticker Vĩ mô & Hàng hóa
│   └── settings.py                 # Cấu hình mặc định (100% Log, auto_adjust=True, Swing N=5, VN_HOLIDAYS, Trọng số 6 tầng)
│   ├── tickers.py                  # Danh sách mã từ vnstock, phân nhóm 9 Ngành ICB, ticker Vĩ mô & Hàng hóa, Flag Vingroup
│   ├── settings.py                 # Cấu hình mặc định (100% Log, Swing N=5, Trọng số 5 tầng, Scoring thresholds)
│   └── vn_holidays.py              # Tự động sinh ngày lễ VN theo năm (Tết Dương, Giỗ Tổ, 30/4-1/5, 2/9, Tết Nguyên Đán)
├── core/
│   ├── db_manager.py               # Quản lý SQLite + Parquet Local DB, Incremental Update & VNIndexCalendarGuard (nghỉ T7/CN)
│   ├── data_fetcher.py             # BaseDataProvider + YFinanceProvider + MSNFinanceProvider + FREDProvider (sẵn cổng SSI)
│   ├── db_manager.py               # Quản lý SQLite Local DB, Incremental Update & VNIndexCalendarGuard
│   ├── data_fetcher.py             # BaseDataProvider + VnstockProvider + YFinanceProvider + FREDProvider
│   ├── indicators.py               # RSI(14), EMA/MA(21,50,120,200), MACD(12,26,9), Fisher(9), MFI(14), VolRatio
│   ├── geometry_log.py             # Auto-Pitchfork 3 điểm (Bearish/Bullish, Swing N) & Auto-Trendline trên trục Log
│   ├── gann_engine.py              # Gann Time Cycles, Square of 9, Gann Fan & Gann Box trên trục Log
│   ├── pnf_engine.py               # Point & Figure (X/O Log % Box Size) + Horizontal & Vertical Target Count
│   ├── gann_engine.py              # Gann Time Cycles, Square of 9 (k slider), Gann Fan & Gann Box trên trục Log
│   ├── astro_engine.py             # Pha Mặt Trăng & Thủy Tinh nghịch hành (ephem)
│   ├── rrg_engine.py               # JdK RS-Ratio, RS-Momentum & Backtest Lịch sử Luân chuyển Ngành
│   ├── screener.py                 # Bộ lọc siêu tốc trên Local DB + Balance Sheet Gatekeeper + Top-Down Score
│   ├── black_scholes.py            # Định giá Chứng quyền (Fair Value, IV, Greeks, Gearing, Payoff)
│   ├── rrg_engine.py               # JdK RS-Ratio, RS-Momentum (12W window) & Backtest Lịch sử Luân chuyển Ngành
│   ├── scoring_engine.py           # Hệ thống chấm điểm 0-100 cho 5 Tầng + Top-Down Composite Score
│   ├── screener.py                 # Bộ lọc siêu tốc trên Local DB + Balance Sheet Gatekeeper + 3 Preset
│   ├── black_scholes.py            # Định giá Chứng quyền (Fair Value, IV Newton-Raphson, Greeks, Gearing, Payoff)
│   ├── margin_aggregator.py        # Tổng hợp Dư nợ Margin từ BCTC CTCK qua vnstock
│   ├── portfolio_alerts.py         # Động cơ đối chiếu Nhật ký lệnh với Local DB & sinh cờ cảnh báo Stop/Target
│   └── report_generator.py         # Xuất báo cáo phân tích tự động Markdown / HTML
│   └── report_generator.py         # Xuất báo cáo phân tích tự động Markdown / HTML (Jinja2)
├── components/
│   ├── charts_plotly.py            # Biểu đồ 100% Log 4-panel + Hybrid Drawline + Gann Overlay + P&F Chart
│   └── ui_cards.py                 # Banner cảnh báo DB, thẻ KPI, đồng hồ Top-Down Score, cờ cảnh báo danh mục
│   ├── charts_plotly.py            # Biểu đồ 100% Log 4-panel + Hybrid Drawline persist SQLite + Gann Overlay
│   └── ui_cards.py                 # Banner cảnh báo DB, thẻ KPI, đồng hồ Top-Down Score gauge, cờ cảnh báo danh mục
├── pages/
│   ├── 1_Astro_Gann.py
│   ├── 2_Macro_Margin.py
│   ├── 3_Commodities_RRG.py
│   ├── 4_Derivatives_Breadth.py
│   ├── 5_Stock_Screener_MTF.py
│   ├── 6_Warrants_CW.py
│   └── 7_Journal_Backtest.py
├── templates/
│   └── report_template.html        # Jinja2 template cho Auto-Report
└── data/
    ├── quant_local.db              # SQLite Database cục bộ
    ├── ohlcv/                      # File .parquet lưu OHLCV đã điều chỉnh từng mã
    └── manual/                     # File mẫu: vn_margin_history.csv, vn30f_history.csv, cw_watchlist.csv, trade_journal.csv
    ├── quant_local.db              # SQLite Database cục bộ (chứa TẤT CẢ dữ liệu)
    ├── reports/                    # Báo cáo phân tích xuất ra
    ├── logs/                       # Log file (app.log, INFO level)
    └── manual/                     # File import thủ công: vn_margin_history.xlsx, fundamentals_manual.csv
```

### 5.3. Lộ trình Triển khai 4 Pha (Nghiệm thu từng Pha)
* **Pha 1 — Lõi Local Database, Lịch VN-Index & Trạm Đồ thị Log + P&F + Gann:**
  * Xây dựng `db_manager.py`, `data_fetcher.py` (`yfinance auto_adjust=True` + MSN fallback), `indicators.py`, `geometry_log.py`, `gann_engine.py`, `pnf_engine.py`, `charts_plotly.py` và `pages/5_Stock_Screener_MTF.py`.
  * *Nghiệm thu:* Khởi tạo được Local DB cho rổ cổ phiếu mẫu (có `KDH.VN`, `NLG.VN`, `FPT.VN`, `VCG.VN`); hiện đúng cảnh báo nếu ngày DB lệch lịch giao dịch VN-Index (T7/CN); quét siêu tốc từ DB; vẽ chuẩn đồ thị **100% Log Scale** kèm Auto-Pitchfork (`N=5`), Gann Fan/Square of 9 và Point & Figure (X/O).
### 5.3. Logging & Error Handling
* Logging `INFO` level ra file `data/logs/app.log`.
* vnstock/yfinance lỗi → retry 3 lần, đánh dấu lỗi trên UI bằng `st.warning()`.

### 5.4. Lộ trình Triển khai 4 Pha (Nghiệm thu từng Pha)
* **Pha 1 — Lõi Local Database, Lịch VN-Index & Trạm Đồ thị Log + Gann:**
  * Xây dựng `db_manager.py`, `data_fetcher.py` (vnstock + yfinance), `indicators.py`, `geometry_log.py`, `gann_engine.py`, `charts_plotly.py` và `pages/5_Stock_Screener_MTF.py`.
  * *Nghiệm thu:* Khởi tạo được Local DB cho rổ cổ phiếu mẫu (có `KDH`, `NLG`, `FPT`, `VCG`); hiện đúng cảnh báo nếu ngày DB lệch lịch giao dịch VN-Index (T7/CN/Lễ); quét siêu tốc từ DB; vẽ chuẩn đồ thị **100% Log Scale** kèm Auto-Pitchfork (`N=5`), Gann Fan/Square of 9; vẽ tay persist vào SQLite.
* **Pha 2 — Tầng Vĩ mô, Margin, Hàng hóa, RRG & Lịch sử Luân chuyển Ngành:**
  * Xây dựng `pages/2_Macro_Margin.py`, `pages/3_Commodities_RRG.py`, `core/rrg_engine.py`.
  * *Nghiệm thu:* Import được file Excel/CSV Margin VN-Index (2000–2026), vẽ đường cong lợi suất FRED, biểu đồ RRG 4 góc phần tư và bảng thống kê lịch sử luân chuyển 9 nhóm ngành.
  * Xây dựng `pages/2_Macro_Margin.py`, `pages/3_Commodities_RRG.py`, `core/rrg_engine.py`, `core/margin_aggregator.py`.
  * *Nghiệm thu:* Tổng hợp được dư nợ Margin từ BCTC CTCK + Import file Excel bổ sung; vẽ đường cong lợi suất FRED; biểu đồ RRG 4 góc phần tư; bảng thống kê lịch sử luân chuyển 9 nhóm ngành ICB.
* **Pha 3 — Tầng Thiên văn, Phái sinh & Định giá Chứng quyền Black-Scholes:**
  * Xây dựng `pages/1_Astro_Gann.py`, `pages/4_Derivatives_Breadth.py`, `pages/6_Warrants_CW.py`.
  * *Nghiệm thu:* Chiếu pha Trăng & Gann Time Cycles lên VN-Index; tính Market Breadth từ Local DB; định giá chuẩn Black-Scholes & Payoff Matrix cho danh sách Chứng quyền.
* **Pha 4 — Master Dashboard, Nhật ký Lệnh Auto-Alert & Auto-Report:**
  * Hoàn thiện `app.py`, `pages/7_Journal_Backtest.py`, `core/portfolio_alerts.py` và `core/report_generator.py`.
  * *Nghiệm thu:* Tổng hợp đúng Top-Down Score (10-20-20-10-40, chỉnh được bằng slider); tự động bật cờ cảnh báo cho lệnh mẫu NLG khi đối chiếu giá mới nhất từ Local DB; xuất báo cáo phân tích 1-click `.md`/`.html` hoàn chỉnh.
  * *Nghiệm thu:* Chiếu pha Trăng & Gann Time Cycles lên VN-Index; lấy VN30F1M từ vnstock + tính Basis/OI; tính Market Breadth từ Local DB; nạp danh sách CW từ vnstock + định giá chuẩn Black-Scholes & Payoff Matrix.
* **Pha 4 — Master Dashboard, Scoring Engine, Nhật ký Lệnh Auto-Alert & Auto-Report:**
  * Hoàn thiện `app.py`, `core/scoring_engine.py`, `pages/7_Journal_Backtest.py`, `core/portfolio_alerts.py` và `core/report_generator.py`.
  * *Nghiệm thu:* Tổng hợp đúng Top-Down Score (10-20-20-10-40, chỉnh được bằng slider); tùy chọn loại bỏ Vingroup; tự động bật cờ cảnh báo cho lệnh mẫu NLG khi đối chiếu giá mới nhất từ Local DB; xuất báo cáo phân tích 1-click `.md`/`.html` hoàn chỉnh.
