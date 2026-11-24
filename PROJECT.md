# Project: vnstock Top-Down Quant System (v5.0)

## Architecture
- 6-Layer Top-Down Quantitative Architecture (Astro & Macro -> Market Regime -> Sectors & Commodities -> Derivatives & Breadth -> Multi-timeframe Log Geometry & Screeners -> Risk Management & Warrants)
- Central SQLite WAL database manager (`core/db_manager.py`)
- Standard indicators with W-FRI / ME resampling (`core/indicators.py`)
- Multi-timeframe UI in Streamlit (`app.py`, `pages/1_Astro_Gann.py` - `pages/7_Journal_Backtest.py`)
- Single unified test suite in `test_suite.py` without fragmented test files

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Session Extraction & Analysis | Parse 263 messages from OpenCode session `ses_df7237322ffe3XWKb3v8AnGvRv` | M1 | survey |
| 2 | Comprehensive PLAN.md | Complete plan file detailing all 16 fixes, architecture, and execution steps | M1 | survey |
| 3 | Core Bug Fixes Validation | Resampling KeyError, geometry windowing, MFI subplot, NaN handling, Macro real data, Margin CSV | M1 | survey |
| 4 | Quantitative Presets Optimization | Unified settings, negative slope Bearish Pitchfork, dry-up Preset 3 bounce, Monthly MA cascade | M1 | survey |
| 5 | Streamlit Modernization & Dark Theme | Dark theme config, sans-serif font, width='stretch', 0 unhandled exceptions across 8 pages | M1 | survey |
| 6 | Database Connection Hygiene | Safe `try...finally: conn.close()` across UI pages and core engines | M1 | survey |
| 7 | Fundamentals Template Data | Provide `data/manual/fundamentals_template.csv` for Balance Sheet Gatekeeper | M1 | survey |
| 8 | Automated UI Smoke Test (TEST 17) | Direct integration of Streamlit AppTest / smoke test into `test_suite.py` (17/17 PASS) | M1 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Implementation & Plan Finalization | Finalize PLAN.md, integrate TEST 17 into test_suite.py, verify fundamentals template and DB hygiene | none | COMPLETE |

## Interface Contracts
- `test_suite.py`: executes all tests standalone, exit code 0 on success, 0 external temp leaks.
- `PLAN.md`: located at `d:\AI\vnstock\PLAN.md`, provides complete roadmap and audit breakdown.
- `AGENTS.md`: mathematical invariants (kVND, log10 scale, geometric mean Pitchfork, pandas ME/W-FRI, Streamlit stretch).

## Code Layout
- `app.py`: Streamlit Master Dashboard
- `pages/*.py`: 7 Feature Pages
- `core/*.py`: Quantitative Engines
- `config/*.py`: Global configurations & parameters
- `components/*.py`: Reusable Plotly charts and UI cards
- `test_suite.py`: Unified test suite
- `PLAN.md`: System plan and audit specification
