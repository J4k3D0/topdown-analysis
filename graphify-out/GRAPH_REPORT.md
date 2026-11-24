# Graph Report - vnstock  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 258 nodes · 664 edges · 10 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 30 edges
2. `load_ohlcv()` - 19 edges
3. `calculate_all_indicators()` - 15 edges
4. `resample_ohlcv()` - 14 edges
5. `sync_database()` - 12 edges
6. `scan_stock()` - 11 edges
7. `backtest_preset()` - 11 edges
8. `compute_bearish_pitchfork()` - 10 edges
9. `get_trade_journal()` - 9 edges
10. `create_deep_dive_chart()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `render_db_calendar_guard()` --calls--> `get_expected_last_trading_day()`  [EXTRACTED]
  components/ui_cards.py → config/vn_holidays.py
- `evaluate_portfolio_alerts()` --calls--> `get_trade_journal()`  [EXTRACTED]
  core/portfolio_alerts.py → core/db_manager.py
- `backtest_preset()` --calls--> `load_ohlcv()`  [EXTRACTED]
  core/backtest_engine.py → core/db_manager.py
- `evaluate_portfolio_alerts()` --calls--> `load_ohlcv()`  [EXTRACTED]
  core/portfolio_alerts.py → core/db_manager.py
- `scan_stock()` --calls--> `load_ohlcv()`  [EXTRACTED]
  core/screener.py → core/db_manager.py

## Import Cycles
- None detected.

## Communities (10 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (16): delete_user_drawing(), get_connection(), get_db_max_date(), get_setting(), get_trade_journal(), get_user_drawings(), init_db(), load_ohlcv() (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (9): create_deep_dive_chart(), create_margin_correlation_chart(), create_rrg_plot(), create_yield_curve_chart(), render_alert_card(), render_db_calendar_guard(), render_topdown_gauge(), evaluate_portfolio_alerts() (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (12): _compute_weekly_pitchfork_vector(), calculate_gann_box_log(), calculate_gann_fan_log(), calculate_gann_square_of_9(), _build_pitchfork_lines(), compute_auto_trendlines(), compute_bearish_pitchfork(), compute_bullish_pitchfork() (+4 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (8): backtest_preset(), run_system_audit(), calculate_gann_time_cycles(), resample_ohlcv(), generate_stock_report(), backtest_sector_rotation(), calculate_multi_asset_rrg(), compute_rrg_metrics()

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (10): get_astro_events_for_range(), get_moon_phase_info(), is_mercury_retrograde(), analyze_warrant(), black_scholes_call_price(), calculate_cw_greeks(), calculate_historical_volatility(), generate_payoff_matrix() (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (4): BaseDataProvider, FREDProvider, sync_database(), YFinanceProvider

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (8): calculate_all_indicators(), calculate_fisher_transform(), calculate_macd(), calculate_mas(), calculate_mfi(), calculate_rsi(), compute_ex_vingroup_index(), detect_rsi_divergence()

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (6): calculate_topdown_composite_score(), _score_single_frame(), score_tier1_astro_gann(), score_tier2_macro_margin(), score_tier3_market_level(), score_tier5_vnindex_mtf()

### Community 8 - "Community 8"
Cohesion: 0.25
Nodes (3): get_expected_last_trading_day(), get_vietnam_holidays(), is_trading_day()

### Community 9 - "Community 9"
Cohesion: 0.27
Nodes (3): get_margin_series(), import_margin_excel(), generate_sample_stock()

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 9`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08170731707317073 - nodes in this community are weakly interconnected._
- **Why does `sync_database()` connect `Community 5` to `Community 0`, `Community 1`, `Community 9`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.09041835357624832 - nodes in this community are weakly interconnected._
- **Why does `get_expected_last_trading_day()` connect `Community 8` to `Community 1`, `Community 3`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.10510510510510511 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.10606060606060606 - nodes in this community are weakly interconnected._