#!/usr/bin/env python3
"""
S&P 500 Weekly Grader Service — Runs inside Railway
Grades all 500 S&P 500 tickers using VOX 6-layer engine
"""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sync.vox_postgres_sync import _get_cursor
from grading.vox_engine import calculate_vox_grade
from psycopg2.extras import execute_values


def get_sp500_tickers():
    """Fetch active tickers from sp500_universe."""
    with _get_cursor() as cur:
        cur.execute("SELECT ticker FROM sp500_universe WHERE is_active = TRUE ORDER BY ticker")
        return [r["ticker"] for r in cur.fetchall()]


def create_sp500_grades_table():
    """Create the sp500_grades table if it doesn't exist."""
    with _get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sp500_grades (
                ticker TEXT PRIMARY KEY REFERENCES sp500_universe(ticker),
                vox_grade INTEGER,
                technical_score INTEGER,
                fundamental_score INTEGER,
                macro_score INTEGER,
                sector_score INTEGER,
                weather_score INTEGER,
                sentiment_score INTEGER,
                computed_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    print("[S&P500] Created/verified sp500_grades table")


def grade_all_sp500(batch_size=25):
    """Grade all S&P 500 tickers using VOX engine."""
    print(f"[{datetime.now(timezone.utc)}] [S&P500] Starting weekly grading...")

    tickers = get_sp500_tickers()
    print(f"[S&P500] Loaded {len(tickers)} tickers from sp500_universe")

    results = []
    errors = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"[S&P500] Batch {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1}: {batch[0]}...{batch[-1]}")

        for ticker in batch:
            try:
                grade_data = calculate_vox_grade(ticker)
                if grade_data:
                    results.append({
                        "ticker": ticker,
                        "vox_grade": grade_data.overall_grade,
                        "technical_score": grade_data.technical_score,
                        "fundamental_score": grade_data.fundamental_score,
                        "macro_score": grade_data.macro_score,
                        "sector_score": grade_data.sector_score,
                        "weather_score": grade_data.weather_score,
                        "sentiment_score": grade_data.sentiment_score,
                    })
            except Exception as e:
                errors.append((ticker, str(e)[:100]))

        # Save batch incrementally to avoid memory issues
        if results:
            save_grades(results)
            print(f"[S&P500] Saved {len(results)} grades so far")

    print(f"[{datetime.now(timezone.utc)}] [S&P500] Graded {len(results)} tickers, {len(errors)} errors")
    return results, errors


def save_grades(results):
    """Save grades to Postgres."""
    with _get_cursor() as cur:
        rows = [
            (
                r["ticker"],
                r["vox_grade"],
                r["technical_score"],
                r["fundamental_score"],
                r["macro_score"],
                r["sector_score"],
                r["weather_score"],
                r["sentiment_score"],
                datetime.now(timezone.utc),
            )
            for r in results
        ]

        execute_values(cur, """
            INSERT INTO sp500_grades 
            (ticker, vox_grade, technical_score, fundamental_score, macro_score, sector_score,
             weather_score, sentiment_score, computed_at)
            VALUES %s
            ON CONFLICT (ticker) DO UPDATE SET
                vox_grade = EXCLUDED.vox_grade,
                technical_score = EXCLUDED.technical_score,
                fundamental_score = EXCLUDED.fundamental_score,
                macro_score = EXCLUDED.macro_score,
                sector_score = EXCLUDED.sector_score,
                weather_score = EXCLUDED.weather_score,
                sentiment_score = EXCLUDED.sentiment_score,
                computed_at = NOW()
        """, rows)


def print_grade_stats(results):
    """Print grade distribution statistics."""
    if not results:
        print("[S&P500] No results to display")
        return

    grades = [r["vox_grade"] for r in results if r["vox_grade"]]

    print("\n" + "=" * 60)
    print("S&P 500 GRADE DISTRIBUTION")
    print("=" * 60)

    bins = [
        (0, 30, "<30 SELL"),
        (30, 40, "30-40"),
        (40, 50, "40-50"),
        (50, 55, "50-55"),
        (55, 60, "55-60"),
        (60, 65, "60-65"),
        (65, 70, "65-70"),
        (70, 80, "70-80 BUY"),
        (80, 100, "80+ STRONG"),
    ]

    for low, high, label in bins:
        count = sum(1 for g in grades if low <= g < high)
        bar = "█" * (count // 3)
        print(f"  {label:15} {count:3d} {bar}")

    print(f"\n  Mean: {sum(grades)/len(grades):.1f}")
    print(f"  Median: {sorted(grades)[len(grades)//2]:.1f}")
    print(f"  Range: {min(grades)} - {max(grades)}")

    # Top 10
    print("\n  TOP 10:")
    top = sorted(results, key=lambda x: x.get("vox_grade", 0), reverse=True)[:10]
    for r in top:
        print(f"    {r['ticker']:<6} Grade: {r['vox_grade']:2d}")

    # Bottom 10
    print("\n  BOTTOM 10:")
    bottom = sorted(results, key=lambda x: x.get("vox_grade", 0))[:10]
    for r in bottom:
        print(f"    {r['ticker']:<6} Grade: {r['vox_grade']:2d}")


def weekly_job():
    """Weekly S&P 500 grading job."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now(timezone.utc)}] [S&P500] WEEKLY GRADING RUN")
    print(f"{'='*60}")

    create_sp500_grades_table()
    results, errors = grade_all_sp500()
    print_grade_stats(results)

    if errors:
        print(f"\n[S&P500] Errors ({len(errors)}):")
        for ticker, error in errors[:10]:
            print(f"  {ticker}: {error}")

    print(f"\n[{datetime.now(timezone.utc)}] [S&P500] Weekly grading complete!")
    return {"graded": len(results), "errors": len(errors)}


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc)}] [S&P500] Weekly grader starting...")
    weekly_job()
