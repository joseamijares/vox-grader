# VOX Compounding System v1.0

## Overview
Tracks portfolio growth, sets goals, measures progress, creates feedback loops for aggressive compounding.

## Tables
- **portfolio_goals**: weekly/monthly/quarterly/yearly targets
- **portfolio_history**: daily AUM/grade/return snapshots
- **trade_journal**: every trade with thesis, outcome, lessons
- **performance_metrics**: win rate, avg return, sharpe, max drawdown
- **compounding_projections**: forward-looking scenarios (2%-12% monthly)

## Crons
| Cron | Schedule | Purpose |
|------|----------|---------|
| vox-compounding-snapshot | 7 AM daily | Record portfolio state |
| vox-weekly-progress | Mon 8 AM | Dashboard + metrics briefing |

## Goals (Current)
- Weekly: +0.5% → $138,875
- Monthly: +2.0% → $140,948
- Quarterly: +8.0% → $149,239
- Yearly: +35.0% → $186,549

## Projections (from $138,184)
| Scenario | Monthly | 12-Mo AUM | Return |
|----------|---------|-----------|--------|
| Conservative | 2% | $187,251 | 35% |
| Moderate | 4% | $245,237 | 77% |
| Aggressive | 6% | $314,054 | 127% |
| VOX Target | 8% | $407,971 | 195% |
| High Risk | 12% | $598,362 | 333% |
