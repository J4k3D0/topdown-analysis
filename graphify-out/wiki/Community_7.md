# Community 7

> 15 nodes · cohesion 0.15

## Key Concepts

- **scoring_engine.py** (15 connections) — `core/scoring_engine.py`
- **score_tier5_vnindex_mtf()** (6 connections) — `core/scoring_engine.py`
- **calculate_topdown_composite_score()** (5 connections) — `core/scoring_engine.py`
- **score_tier1_astro_gann()** (5 connections) — `core/scoring_engine.py`
- **score_tier2_macro_margin()** (5 connections) — `core/scoring_engine.py`
- **_score_single_frame()** (4 connections) — `core/scoring_engine.py`
- **score_tier3_market_level()** (4 connections) — `core/scoring_engine.py`
- **DataFrame** (2 connections)
- **core/scoring_engine.py Hệ thống chấm điểm định lượng 6 tầng Top-Down (0 - 100)…** (1 connections) — `core/scoring_engine.py`
- **Tầng 1: Trả về điểm do người dùng tự chấm bằng Slider (0 - 100).** (1 connections) — `core/scoring_engine.py`
- **Chấm điểm 1 khung thời gian (1M, 1W hoặc 1D) từ Fisher, RSI, MACD, Volume và…** (1 connections) — `core/scoring_engine.py`
- **Tầng 2: Vĩ mô & Margin (Trọng số 20%): S_T2 = 0.25*S_yield + 0.15*S_DXY +…** (1 connections) — `core/scoring_engine.py`
- **Tầng 5: VN-Index Đa khung (1M - 1W - 1D) - Trọng số 40%: S_T5 = 0.30 * S_1M +…** (1 connections) — `core/scoring_engine.py`
- **Tổng hợp điểm Top-Down Composite Score (0 - 100): Total = w1*S_T1 + w2*S_T2 +…** (1 connections) — `core/scoring_engine.py`
- **Tầng 3: Market-Level Score (toàn thị trường): Tính từ tỷ lệ phân bổ của 9 ngành…** (1 connections) — `core/scoring_engine.py`

## Relationships

- [Community 1](Community_1.md) (8 shared connections)
- [Community 3](Community_3.md) (6 shared connections)
- [Community 2](Community_2.md) (4 shared connections)
- [Community 9](Community_9.md) (3 shared connections)

## Source Files

- `core/scoring_engine.py`

## Audit Trail

- EXTRACTED: 37 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*