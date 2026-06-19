# VOX System Update — June 19, 2026

## Summary
Deployed full-market scanning infrastructure. No more narrow watchlist recommendations.

## New Components

### 1. vox-top-opportunities-scanner
- **Schedule:** 6 AM + 2 PM weekdays
- **Purpose:** Scan ALL 19,356 vox_grades for grade ≥ 65 + BUY/STRONG_BUY/ACCUMULATE
- **Output:** Stores top 100 in `top_opportunities` table, alerts on new grade 80+
- **Script:** `vox_cron/vox_top_opportunities_scanner.py`

### 2. vox-liquid-universe-builder
- **Schedule:** Sunday 6 PM weekly
- **Purpose:** Build top 5,000 liquid tickers from 19,356 by composite score
- **Output:** `liquid_universe` table with 340 unique tickers (after dedup)
- **Script:** `vox_cron/build_universe.py`

### 3. vox-weekly-stock-adder
- **Schedule:** Sunday 7 PM weekly
- **Purpose:** Add new tickers discovered in liquid_universe but not in vox_grades
- **Output:** Expands vox_grades universe weekly
- **Script:** `vox_cron/vox_weekly_stock_adder.py`

## Key Findings

| Metric | Value |
|--------|-------|
| Total vox_grades | 19,356 |
| Grade ≥ 65 | 100 stocks (0.5%) |
| Grade ≥ 70 | 30 stocks |
| Grade 80+ | 13 stocks |
| Top grade | IONQ 90 |

## System Bugs Identified

1. **IONQ missing from unified_grades** — VOX 90 never unified, table only has stale 50-69
2. **Watchlist stocks downgraded** — SE (86→59), MCO (84→61), VEEV (84→61)
3. **1,616 inflation bug tickers** — VOX SELL but unified BUY ≥60
4. **Duplicate tickers in vox_grades** — 4,660 duplicates found, 340 unique after dedup

## Cron Jobs Active (25 total)

| Job | Schedule | Status |
|-----|----------|--------|
| vox-top-opportunities-scanner | 6 AM, 2 PM | ✅ Active |
| vox-liquid-universe-builder | Sunday 6 PM | ✅ Active |
| vox-weekly-stock-adder | Sunday 7 PM | ✅ Active |
| vox-macro-snapshot | 6 AM daily | ✅ Active |
| vox-morning-digest | 7:30 AM | ✅ Active |
| vox-evening-digest | 4:30 PM | ✅ Active |
| vox-massive-opportunity | 10 AM, 4 PM | ✅ Active |
| vox-pattern-scanner | 7 AM, 1 PM | ✅ Active |
| vox-watchlist-grader | 6 AM | ✅ Active |
| vox-daily-health-check | 5 AM | ✅ Active |

## Next Steps
- [ ] Fix unified grading pipeline for watchlist stocks
- [ ] Deduplicate vox_grades table (4,660 duplicates)
- [ ] Add real volume data for liquidity scoring
- [ ] Integrate Finnhub/Twitter for weekly new ticker discovery

## Deployment
- Committed to: https://github.com/joseamijares/vox-grader
- Branch: main
- Commit: d76f9ff
