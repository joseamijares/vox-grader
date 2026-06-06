#!/usr/bin/env python3
"""
VOX Grader Service — Runs inside Railway, connects to Railway Postgres
Integrated 6-Layer Grading Pipeline v2
"""
import os
import sys
import time
import schedule
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sync.vox_postgres_sync import get_positions, get_watchlist, update_position, save_vox_grade, upsert_watchlist
from grading.vox_engine import calculate_vox_grade, batch_vox_grade

# Import 6-layer system
from layers.macro_trends import get_macro_data, compute_macro_signals
from layers.weather_patterns import get_noaa_active_alerts, classify_weather_impact
from collections import defaultdict


def compute_sector_momentum(positions, watchlist):
    """Compute sector momentum from current grades and councils."""
    all_items = positions + watchlist
    sector_tickers = defaultdict(list)
    sector_grades = defaultdict(list)
    sector_buys = defaultdict(int)
    sector_sells = defaultdict(int)

    for item in all_items:
        sector = item.get("sector") or "Uncategorized"
        ticker = item["ticker"]
        sector_tickers[sector].append(ticker)
        if item.get("grade"):
            sector_grades[sector].append(int(item["grade"]))
        council = (item.get("council") or "").upper()
        if council.startswith("BUY"):
            sector_buys[sector] += 1
        elif council.startswith("SELL"):
            sector_sells[sector] += 1

    results = []
    for sector, tickers in sector_tickers.items():
        unique = list(set(tickers))
        grades = sector_grades.get(sector, [])
        avg = sum(grades) / len(grades) if grades else 50
        mom = min(100, max(0, int(avg + (sector_buys[sector] - sector_sells[sector]) * 5)))
        if mom >= 70:
            trend = "STRONG"
        elif mom >= 55:
            trend = "POSITIVE"
        elif mom >= 45:
            trend = "NEUTRAL"
        elif mom >= 30:
            trend = "NEGATIVE"
        else:
            trend = "WEAK"
        results.append({
            "sector": sector,
            "momentum_score": mom,
            "trend": trend,
            "ticker_count": len(unique),
            "avg_grade": round(avg, 1),
        })
    return results


def run_macro_layer() -> list:
    """Run macro trends layer."""
    print(f"[{datetime.now(timezone.utc)}] 📊 Running Macro Trends...")
    try:
        macro_data = get_macro_data()
        signals = compute_macro_signals(macro_data)
        print(f"[{datetime.now(timezone.utc)}]   ✅ {len(signals)} macro signals")
        for s in signals:
            print(f"      {s['signal_direction']:10s} {s['signal_name']}")
        return signals
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}]   ❌ Macro error: {e}")
        return []


def run_sector_layer() -> list:
    """Run sector momentum layer."""
    print(f"[{datetime.now(timezone.utc)}] 🏭 Running Sector Momentum...")
    try:
        positions = get_positions()
        watchlist = get_watchlist()
        results = compute_sector_momentum(positions, watchlist)
        print(f"[{datetime.now(timezone.utc)}]   ✅ {len(results)} sectors analyzed")
        for s in results[:5]:
            print(f"      {s['sector']:25s} score={s['momentum_score']:3d} trend={s['trend']}")
        return results
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}]   ❌ Sector error: {e}")
        return []


def run_weather_layer() -> list:
    """Run weather patterns layer."""
    print(f"[{datetime.now(timezone.utc)}] 🌪️  Running Weather Patterns...")
    try:
        alerts = get_noaa_active_alerts()
        patterns = classify_weather_impact(alerts)
        print(f"[{datetime.now(timezone.utc)}]   ✅ {len(patterns)} weather patterns from {len(alerts)} alerts")
        return patterns
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}]   ❌ Weather error: {e}")
        return []


def integrated_grade_all():
    """Run full integrated 6-layer grading on all positions and watchlist."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now(timezone.utc)}] 🧠 INTEGRATED 6-LAYER GRADING v2")
    print(f"{'='*60}")

    # Step 1: Run all layers
    macro_signals = run_macro_layer()
    sector_momentum = run_sector_layer()
    weather_patterns = run_weather_layer()

    # Step 2: Get all items to grade
    positions = get_positions()
    watchlist = get_watchlist()

    all_tickers = {}
    for p in positions:
        all_tickers[p["ticker"]] = {"type": "position", "data": p}
    for w in watchlist:
        if w["ticker"] not in all_tickers:
            all_tickers[w["ticker"]] = {"type": "watchlist", "data": w}

    print(f"[{datetime.now(timezone.utc)}] 🎯 Grading {len(all_tickers)} tickers...")

    tickers = list(all_tickers.keys())
    results = batch_vox_grade(tickers, macro_signals, sector_momentum, weather_patterns)

    # Step 3: Push to DB
    print(f"[{datetime.now(timezone.utc)}] 💾 Saving {len(results)} grades to PostgreSQL...")
    updated_positions = 0
    updated_watchlist = 0
    saved_grades = 0

    for r in results:
        info = all_tickers[r.ticker]
        update_data = {
            "grade": r.overall_grade,
            "council": r.council,
            "sector": r.sector or info["data"].get("sector", ""),
        }

        if info["type"] == "position":
            update_position(r.ticker, update_data)
            updated_positions += 1
        else:
            existing = info["data"]
            upsert_data = {
                "ticker": r.ticker,
                "name": r.name or existing.get("name", r.ticker),
                "sector": r.sector or existing.get("sector", ""),
                "thesis": existing.get("thesis", ""),
                "entry_price": existing.get("entry_price", 0),
                "target_price": existing.get("target_price", 0),
                "stop_loss": existing.get("stop_loss", 0),
                "grade": r.overall_grade,
                "council": r.council,
                "status": existing.get("status", "active"),
                "notes": existing.get("notes", ""),
            }
            upsert_watchlist(upsert_data)
            updated_watchlist += 1

        save_vox_grade({
            "ticker": r.ticker,
            "name": r.name or r.ticker,
            "vox_grade": r.overall_grade,
            "previous_grade": info["data"].get("grade", 0) or 0,
            "action": r.council,
            "current_price": float(info["data"].get("live_price", 0) or 0),
            "stop_loss": float(info["data"].get("live_price", 0) or 0) * 0.85 if info["data"].get("live_price") else 0,
            "entry_point": float(info["data"].get("live_price", 0) or 0) * 0.95 if info["data"].get("live_price") else 0,
            "position_value": float(info["data"].get("live_value", 0) or 0),
            "shares": float(info["data"].get("shares", 0) or 0),
            "technical_score": r.technical_score,
            "fundamental_score": r.fundamental_score,
            "macro_score": r.macro_score,
            "sector_score": r.sector_score,
            "weather_score": r.weather_score,
            "sentiment_score": r.sentiment_score,
            "catalysts": "; ".join(r.factors.get("technical", {}).get("mean_reversion_signals", [])[:3]) or "None",
            "weather_factors": f"Macro: {len(macro_signals)} signals; Weather: {len(weather_patterns)} patterns",
        })
        saved_grades += 1

    print(f"[{datetime.now(timezone.utc)}] ✅ Updated {updated_positions} positions, {updated_watchlist} watchlist, {saved_grades} grades")

    # Print top/bottom
    results.sort(key=lambda x: -x.overall_grade)
    print(f"\n[{datetime.now(timezone.utc)}] 🏆 TOP 10:")
    for r in results[:10]:
        print(f"   {r.ticker:8s} {r.overall_grade:3d} {r.council:12s} T={r.technical_score} F={r.fundamental_score} M={r.macro_score} S={r.sector_score} W={r.weather_score} Se={r.sentiment_score}")
    print(f"[{datetime.now(timezone.utc)}] ⚠️ BOTTOM 10:")
    for r in results[-10:]:
        print(f"   {r.ticker:8s} {r.overall_grade:3d} {r.council:12s} T={r.technical_score} F={r.fundamental_score} M={r.macro_score} S={r.sector_score} W={r.weather_score} Se={r.sentiment_score}")

    return {"graded": len(results), "positions": updated_positions, "watchlist": updated_watchlist}


def sync_etoro():
    """Sync eToro positions to Railway DB."""
    try:
        from brokers.etoro_sync_railway import sync_etoro as do_sync
        print(f"[{datetime.now(timezone.utc)}] 📡 Starting eToro sync...")
        count = do_sync()
        print(f"[{datetime.now(timezone.utc)}] ✅ eToro sync: {count} positions")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] ❌ eToro sync failed: {e}")
        import traceback
        traceback.print_exc()


def sync_all_brokers():
    """Sync all broker JSON portfolios."""
    try:
        from brokers.unified_sync import sync_all_brokers as do_sync
        print(f"[{datetime.now(timezone.utc)}] 📡 Starting unified broker sync...")
        count = do_sync()
        print(f"[{datetime.now(timezone.utc)}] ✅ Unified sync: {count} positions")
    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] ❌ Unified sync failed: {e}")
        import traceback
        traceback.print_exc()


def daily_job():
    """Daily 7:30 AM CT job: sync + integrated grade."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now(timezone.utc)}] 🌅 DAILY VOX RUN")
    print(f"{'='*60}")
    sync_etoro()
    sync_all_brokers()
    integrated_grade_all()
    print(f"[{datetime.now(timezone.utc)}] ✅ Daily run complete\n")


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc)}] 🚀 VOX 6-Layer Grader v2 starting...")
    print(f"[{datetime.now(timezone.utc)}] Data: {os.listdir('/app/data') if os.path.exists('/app/data') else 'NO DATA'}")

    # Schedule daily at 7:30 AM CT (13:30 UTC)
    schedule.every().day.at("13:30").do(daily_job)

    # Also run immediately on startup
    daily_job()

    print(f"[{datetime.now(timezone.utc)}] ⏰ Scheduled for 13:30 UTC daily")

    while True:
        schedule.run_pending()
        time.sleep(60)
