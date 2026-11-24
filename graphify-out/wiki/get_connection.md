# get_connection()

> God node · 30 connections · `core/db_manager.py`

**Community:** [Community 0](Community_0.md)

## Connections by Relation

### calls
- [load_ohlcv()](load_ohlcv.md) `EXTRACTED`
- [sync_database()](sync_database.md) `EXTRACTED`
- [scan_stock()](scan_stock.md) `EXTRACTED`
- [get_trade_journal()](get_trade_journal.md) `EXTRACTED`
- get_setting() `EXTRACTED`
- init_db() `EXTRACTED`
- load_ohlcv_global() `EXTRACTED`
- save_ohlcv_daily() `EXTRACTED`
- save_ohlcv_global() `EXTRACTED`
- set_setting() `EXTRACTED`
- run_system_audit() `EXTRACTED`
- get_margin_series() `EXTRACTED`
- get_db_max_date() `EXTRACTED`
- get_user_drawings() `EXTRACTED`
- save_user_drawing() `EXTRACTED`
- import_margin_excel() `EXTRACTED`
- delete_user_drawing() `EXTRACTED`
- update_trade_exit() `EXTRACTED`
- sqlite3 `EXTRACTED`

### contains
- db_manager.py `EXTRACTED`

### imports
- test_suite.py `EXTRACTED`
- backtest_engine.py `EXTRACTED`
- data_fetcher.py `EXTRACTED`
- 7_Journal_Backtest.py `EXTRACTED`
- screener.py `EXTRACTED`
- 2_Macro_Margin.py `EXTRACTED`
- 4_Derivatives_Breadth.py `EXTRACTED`
- 6_Warrants_CW.py `EXTRACTED`
- margin_aggregator.py `EXTRACTED`

### rationale_for
- Khởi tạo kết nối SQLite với cấu hình WAL mode và tối ưu hiệu năng. `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*