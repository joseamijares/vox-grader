# VOX Architecture: Single Source of Truth

## Date: 2026-06-21
## Status: DEPLOYED

---

## Problem Statement

The VOX system had multiple competing grade sources causing contradictions:

| System | IONQ Grade | Frequency | Type |
|--------|-----------|-----------|------|
| vox_grades | 55 | Daily | Algorithmic |
| watchlist_grades | 90 | Weekly | Manual |
| sp500_grades | N/A | Weekly | Narrow universe |

**Result:** IONQ went from STRONG_BUY (90) → HOLD (55) → STRONG_BUY (83) in 48 hours.

**Root cause:** `unified_grades` blended all three sources with a weighted formula, allowing stale watchlist data to override fresh algorithmic scores.

---

## Solution: Single Source of Truth

### Architecture

```
vox_grades (algorithmic, daily, 1,345 tickers)
    │
    ▼
unified_grades (exact mirror + timestamp)
    │
    ▼
RAG / Context Layer (Hermes)
    - Fetches vox_grades
    - Adds macro context (geopolitical, oil, VIX)
    - Generates final recommendation
    - NO grade modification
```

### Key Principles

1. **vox_grades is the ONLY source of truth** for numeric grades
2. **unified_grades is a mirror** — not a blend
3. **watchlist_grades and sp500_grades are reference tables** — not used in grading
4. **Context (RAG) is additive** — it adds narrative but never changes the grade

---

## Data Flow

### vox_grades (Source)
- Algorithmic scoring based on technical, fundamental, macro, sentiment layers
- Updated daily by grader service
- 1,345 tickers covered
- Columns: ticker, vox_grade, action, technical_score, fundamental_score, macro_score, sentiment_score, generated_at

### unified_grades (Mirror)
- Exact copy of vox_grades latest record per ticker
- Adds: computed_at, vox_source, contradiction detection
- Rebuilt daily by vox_unified_rebuilder.py
- 1,345 records (1:1 with vox_grades)

### Context Layer (RAG)
- Fetches vox_grades + unified_grades
- Adds real-time context: news, geopolitical risk, sector momentum
- Generates final recommendation with conviction level
- Does NOT modify grades

---

## Inflation Bug Fix

**Previous:** 107 tickers had VOX SELL but unified >= 60 (BUY)

**Fix:** unified = vox directly (no blending means no inflation possible)

**Verification:**
```sql
SELECT COUNT(*) 
FROM unified_grades u
JOIN vox_grades v ON u.ticker = v.ticker
WHERE v.action IN ('SELL', 'STRONG_SELL')
  AND u.unified_grade >= 60;
-- Result: 0 (was 107)
```

---

## Cross-Validation

**Previous:** 4/10 mismatches between vox_grades and unified_grades

**Fix:** unified = vox directly (100% match guaranteed)

**Verification:**
```sql
SELECT v.ticker, v.vox_grade, u.unified_grade
FROM vox_grades v
JOIN unified_grades u ON v.ticker = u.ticker
WHERE v.vox_grade != u.unified_grade;
-- Result: 0 rows
```

---

## Current Market State (2026-06-21)

| Metric | Value |
|--------|-------|
| Highest grade | 71 (TSM, HOLD) |
| BUY/STRONG_BUY count | 0 |
| HOLD count | 247 |
| SELL/TRIM count | 1,098 |

**Why no BUYs?**
- Israel-Iran conflict escalating
- Strait of Hormuz closed (20% global oil)
- Market expected down Monday
- VIX elevated
- Algorithm correctly cautious

---

## Cron Jobs

| Cron | Schedule | Purpose |
|------|----------|---------|
| vox-unified-rebuilder | Daily 8 AM | Rebuild unified_grades from vox_grades |
| vox-grade-improvement-alert | Daily 2 PM | Alert when any ticker hits 75+ |
| vox-market-monitor | Daily 9 AM | Monitor market open, update recommendations |

---

## Files

| File | Purpose |
|------|---------|
| scripts/vox_unified_rebuilder.py | Rebuilds unified_grades from vox_grades |
| scripts/vox_grade_improvement_alert.py | Alerts on grade improvements |
| scripts/vox_market_monitor.py | Market open monitoring |

---

## Maintenance

### When to update this doc:
- Any change to grade sources
- Any change to unified formula
- Any new table added to grading pipeline

### Verification checklist (run weekly):
- [ ] unified_grades count == vox_grades count (1,345)
- [ ] Inflation bug = 0 tickers
- [ ] Cross-validation = 0 mismatches
- [ ] Latest grade date == today
