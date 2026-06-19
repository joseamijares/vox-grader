# VOX Housekeeping — June 19, 2026 (Holiday)

## Deployed Today

### New Crons (3)
| Job | Schedule | Purpose |
|-----|----------|---------|
| vox-top-opportunities-scanner | 6 AM, 2 PM daily | Full 19,356 market scan |
| vox-liquid-universe-builder | Sunday 6 PM | Top 5,000 liquid tickers |
| vox-weekly-stock-adder | Sunday 7 PM | Auto-expand universe |

### Fixed Bugs (1)
- **portfolio-dashboard-update** — `pwd` → `password` in psycopg2 connect (was causing exit code 1 every 6 hours)

### Commits
- `d76f9ff` — docs: add VOX audit report 2026-06-16
- `4897c33` — feat: deploy full-market scanning infrastructure

## Current Cron Status (25 jobs)

| Status | Count | Jobs |
|--------|-------|------|
| ✅ Active + OK | 24 | All except one |
| ✅ Active + Fixed | 1 | portfolio-dashboard-update (just fixed) |
| 🔴 Paused | 0 | None |

## Known Issues Remaining

| Issue | Severity | Action |
|-------|----------|--------|
| IONQ missing from unified_grades | 🔴 High | Fix unified pipeline for watchlist stocks |
| 1,616 inflation bug tickers | 🔴 High | Re-run unified grading with bug fix |
| 4,660 duplicate tickers in vox_grades | 🟡 Medium | Deduplicate table |
| 10 grade contradictions | 🟡 Medium | Cross-validate DE, MNST, IREN, CIFR, SHOP |
| Web search layer disabled | 🟡 Medium | Integrate Finnhub/NewsAPI |
| Social layer disabled | 🟡 Medium | Integrate Reddit/X APIs |
| sp500-daily-sector-screen workdir wrong | 🟢 Low | Points to /Users/jos/dev/vox-grader instead of scripts dir |

## Next Holiday Tasks
- [ ] Fix unified grading pipeline for watchlist stocks (IONQ, SE, MCO, VEEV)
- [ ] Deduplicate vox_grades table
- [ ] Add real volume data for liquidity scoring
- [ ] Refactor vox_top_opportunities_scanner to read from liquid_universe
- [ ] Audit all DB connection strings for hardcoded passwords
- [ ] Review paused crons and re-enable useful ones
- [ ] Add error handling to all cron scripts

## DB Health
- Total tables: 31
- Total vox_grades: 19,356 (340 unique after dedup)
- Total positions: 72
- Total trade_signals: 946
- liquid_universe: 340 tickers
- top_opportunities: 100 tickers

## AUM
- Grand Total: $196,978.47
- Total Positions: 72
- Average Grade: 47.7
