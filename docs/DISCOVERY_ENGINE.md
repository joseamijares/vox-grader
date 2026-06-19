# VOX Discovery Engine v1.0

## Overview
Discovers new stocks from multiple sources, grades them, tracks discovery history.

## Sources
1. **Momentum Scan**: Grade 75+ from vox_grades not in portfolio
2. **Sector Momentum**: Top tickers from high-momentum sectors
3. **Trade Signals**: High composite score signals
4. **Weekly Additions**: Manual new tickers via vox_weekly_stock_adder

## Tables
- **discovery_queue**: pending stocks to research
- **discovery_history**: all discoveries with outcomes
- **sector_opportunities**: sector-ranked plays
- **theme_alignment**: macro theme -> stock mapping

## Cron
| Cron | Schedule | Purpose |
|------|----------|---------|
| vox-discovery-weekly | Sunday 6 PM | Full discovery scan |

## Current Queue (Top 10)
| Ticker | Grade | Source | Priority |
|--------|-------|--------|----------|
| IONQ | 90 | momentum | 10 |
| SE | 86 | momentum | 8 |
| GE | 85 | momentum | 8 |
| MU | 85 | momentum | 8 |
| MCO | 84 | momentum | 8 |
| VEEV | 84 | momentum | 8 |
| CPAY | 84 | momentum | 8 |
| LLY | 84 | momentum | 8 |
| C | 83 | momentum | 7 |
| BAC | 83 | momentum | 7 |

## Themes Tracked
- Artificial Intelligence
- Nuclear Energy
- Cryptocurrency
- Emerging Markets Fintech
- Biotechnology
- Quantum Computing
