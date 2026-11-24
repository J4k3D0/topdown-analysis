# sync_database()

> God node · 12 connections · `core/data_fetcher.py`

**Community:** [Community 5](Community_5.md)

## Connections by Relation

### calls
- pandas `EXTRACTED`
- [get_connection()](get_connection.md) `EXTRACTED`
- YFinanceProvider `EXTRACTED`
- save_ohlcv_daily() `EXTRACTED`
- save_ohlcv_global() `EXTRACTED`
- time `EXTRACTED`
- .fetch_yield_curve() `EXTRACTED`
- .fetch_stock_ohlcv() `INFERRED`
- .fetch_macro_ohlcv() `INFERRED`

### contains
- data_fetcher.py `EXTRACTED`

### imports
- app.py `EXTRACTED`

### rationale_for
- Thực hiện đồng bộ dữ liệu vào Local SQLite Database (Incremental Update): - Chỉ… `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*