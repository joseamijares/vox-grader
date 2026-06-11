#!/usr/bin/env python3
"""
S&P 500 Weekly Grading Job
Grades all 500 S&P 500 tickers using the VOX 6-layer engine
and saves results to Railway Postgres.
"""
import sys
import os
import time
from datetime import datetime, timezone

# -- Ensure env vars are set (Railway) ----------------------------------------
# These can also be passed in via cron env; we set defaults here too.
# Use external proxy host for local runs, internal host for Railway
DEFAULT_HOST = (
    "acela.proxy.rlwy.net"
    if os.path.exists(os.path.expanduser("~/.hermes/.env"))
    else "postgres-flpd.railway.internal"
)
os.environ.setdefault("PGPASSWORD", "")
os.environ.setdefault("PGHOST", DEFAULT_HOST)
os.environ.setdefault("PGPORT", "35577")
os.environ.setdefault("PGUSER", "postgres")
os.environ.setdefault("PGDATABASE", "railway")

# -- Add src to path ----------------------------------------------------------
SRC_DIR = os.path.expanduser("~/dev/vox-grader/src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from sync.vox_postgres_sync import _get_cursor
from grading.vox_engine import calculate_vox_grade

# -- Config -------------------------------------------------------------------
BATCH_SIZE = 25
PROGRESS_INTERVAL = 50


def get_sector_momentum():
    """Fetch latest sector momentum data from DB."""
    with _get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (sector)
                sector, momentum_score, avg_grade, buy_count, hold_count, sell_count
            FROM sector_momentum
            ORDER BY sector, computed_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def get_active_tickers():
    """Fetch all active S&P 500 tickers from sp500_universe."""
    with _get_cursor() as cur:
        cur.execute("""
            SELECT ticker, security, sector
            FROM sp500_universe
            WHERE is_active = TRUE
            ORDER BY ticker
        """)
        return cur.fetchall()


def save_grade(result):
    """Insert a single grade result into sp500_grades."""
    sql = """
    INSERT INTO sp500_grades (
        ticker, vox_grade, technical_score, fundamental_score,
        macro_score, sector_score, weather_score, sentiment_score, computed_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (ticker) DO UPDATE SET
        vox_grade = EXCLUDED.vox_grade,
        technical_score = EXCLUDED.technical_score,
        fundamental_score = EXCLUDED.fundamental_score,
        macro_score = EXCLUDED.macro_score,
        sector_score = EXCLUDED.sector_score,
        weather_score = EXCLUDED.weather_score,
        sentiment_score = EXCLUDED.sentiment_score,
        computed_at = EXCLUDED.computed_at
    """
    now = datetime.now(timezone.utc)
    with _get_cursor() as cur:
        cur.execute(sql, (
            result.ticker,
            result.overall_grade,
            result.technical_score,
            result.fundamental_score,
            result.macro_score,
            result.sector_score,
            result.weather_score,
            result.sentiment_score,
            now,
        ))


def grade_ticker(ticker_info, sector_momentum=None):
    """Grade a single ticker and return the result or None on failure."""
    ticker = ticker_info["ticker"]
    try:
        result = calculate_vox_grade(ticker, sector_momentum=sector_momentum or [])
        return result
    except Exception as e:
        print(f"  X {ticker}: {e}")
        return None


def run():
    print("=" * 60)
    print("S&P 500 Weekly VOX Grading Job")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Pre-fetch sector momentum once for all tickers
    print("Fetching sector momentum...")
    sector_momentum = get_sector_momentum()
    print(f"  Loaded {len(sector_momentum)} sector momentum records")
    print()

    tickers = get_active_tickers()
    total = len(tickers)
    print(f"Active tickers to grade: {total}")

    results = []
    errors = []
    start_time = time.time()

    for i, ticker_info in enumerate(tickers):
        result = grade_ticker(ticker_info, sector_momentum=sector_momentum)
        if result:
            results.append(result)
            try:
                save_grade(result)
            except Exception as e:
                print(f"  DB save failed for {ticker_info['ticker']}: {e}")
                errors.append((ticker_info["ticker"], f"DB save: {e}"))
        else:
            errors.append((ticker_info["ticker"], "Grading failed"))

        # Progress every 50 tickers
        if (i + 1) % PROGRESS_INTERVAL == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  Progress: {i + 1}/{total}  ({rate:.1f} tickers/sec)  errors: {len(errors)}")

        # Small sleep to avoid hammering yfinance
        if (i + 1) % BATCH_SIZE == 0:
            time.sleep(0.5)

    # -- Final stats ----------------------------------------------------------
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("FINAL STATS")
    print("=" * 60)
    print(f"Total tickers:       {total}")
    print(f"Successfully graded: {len(results)}")
    print(f"Errors:              {len(errors)}")
    print(f"Elapsed time:        {elapsed:.1f}s ({elapsed/60:.1f} min)")

    if results:
        grades = [r.overall_grade for r in results]
        avg_grade = sum(grades) / len(grades)
        print(f"\nAverage VOX grade:   {avg_grade:.1f}")

        # Grade distribution
        buckets = {
            "STRONG_BUY (90-100)": 0,
            "BUY (75-89)": 0,
            "HOLD (55-74)": 0,
            "SELL (35-54)": 0,
            "STRONG_SELL (0-34)": 0,
        }
        for g in grades:
            if g >= 90:
                buckets["STRONG_BUY (90-100)"] += 1
            elif g >= 75:
                buckets["BUY (75-89)"] += 1
            elif g >= 55:
                buckets["HOLD (55-74)"] += 1
            elif g >= 35:
                buckets["SELL (35-54)"] += 1
            else:
                buckets["STRONG_SELL (0-34)"] += 1

        print("\nGrade Distribution:")
        for label, count in buckets.items():
            pct = count / len(grades) * 100
            bar = "#" * int(pct / 2)
            print(f"  {label:22s} {count:3d} ({pct:5.1f}%) {bar}")

        # Top 10
        sorted_results = sorted(results, key=lambda r: r.overall_grade, reverse=True)
        print("\nTop 10:")
        for r in sorted_results[:10]:
            print(f"  {r.ticker:6s}  {r.overall_grade:3d}  {r.council:12s}  {r.sector or '':20s}  {r.name or ''}")

        # Bottom 10
        print("\nBottom 10:")
        for r in sorted_results[-10:]:
            print(f"  {r.ticker:6s}  {r.overall_grade:3d}  {r.council:12s}  {r.sector or '':20s}  {r.name or ''}")

    if errors:
        print(f"\nFailed tickers ({len(errors)}):")
        for t, reason in errors[:20]:
            print(f"  {t}: {reason}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    print("\n" + "=" * 60)
    print(f"Done: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)


if __name__ == "__main__":
    run()
