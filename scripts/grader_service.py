#!/usr/bin/env python3
"""
VOX Grader Service — Runs inside Railway, connects to Railway Postgres
Single source of truth for all VOX grading operations.
"""
import os
import sys
import time
import schedule
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sync.vox_postgres_sync import get_positions, update_position, save_vox_grade
from grading.engine import calculate_grade


def auto_grade_all():
    """Grade all positions with grade=0 or grade IS NULL."""
    positions = get_positions()
    ungraded = [p for p in positions if p.get('grade') in (0, None, '')]
    
    if not ungraded:
        print(f"[{datetime.now(timezone.utc)}] No ungraded positions")
        return 0
    
    print(f"[{datetime.now(timezone.utc)}] Grading {len(ungraded)} positions...")
    graded = 0
    
    for pos in ungraded:
        ticker = pos['ticker']
        try:
            result = calculate_grade(ticker)
            
            update_position(ticker, {
                'grade': result.overall_grade,
                'council': result.council,
                'sector': result.sector or pos.get('sector', 'Technology')
            })
            
            save_vox_grade({
                'ticker': ticker,
                'name': result.name or ticker,
                'vox_grade': result.overall_grade,
                'previous_grade': pos.get('grade', 0) or 0,
                'action': result.council,
                'current_price': pos.get('live_price', 0),
                'stop_loss': pos.get('live_price', 0) * 0.85 if pos.get('live_price') else 0,
                'entry_point': pos.get('live_price', 0) * 0.95 if pos.get('live_price') else 0,
                'position_value': pos.get('live_value', 0),
                'shares': pos.get('shares', 0),
                'technical_score': result.technical_score,
                'fundamental_score': result.fundamental_score,
                'macro_score': 50,
                'sector_score': 50,
                'weather_score': 50,
                'sentiment_score': result.sentiment_score,
                'catalysts': '; '.join(result.factors.get('technical', {}).get('mean_reversion_signals', [])[:3]),
                'weather_factors': 'Pending macro analysis'
            })
            
            print(f"  ✅ {ticker}: Grade {result.overall_grade} ({result.council})")
            graded += 1
        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
    
    print(f"[{datetime.now(timezone.utc)}] Graded {graded}/{len(ungraded)}")
    return graded


def sync_etoro():
    """Sync eToro positions to Railway DB."""
    from brokers.etoro_sync_railway import sync_etoro as do_sync
    print(f"[{datetime.now(timezone.utc)}] Starting eToro sync...")
    try:
        do_sync()
        print(f"[{datetime.now(timezone.utc)}] eToro sync complete")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] eToro sync failed: {e}")
        # Don't crash the whole service if eToro fails


def daily_job():
    """Daily 7:30 AM job: sync + grade + alerts."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now(timezone.utc)}] DAILY VOX RUN")
    print(f"{'='*60}")
    sync_etoro()
    auto_grade_all()
    print(f"[{datetime.now(timezone.utc)}] Daily run complete\n")


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc)}] VOX Grader Service starting...")
    
    # Schedule daily at 7:30 AM CT (13:30 UTC)
    schedule.every().day.at("13:30").do(daily_job)
    
    # Also run immediately on startup
    daily_job()
    
    print(f"[{datetime.now(timezone.utc)}] Scheduled for 13:30 UTC daily")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
