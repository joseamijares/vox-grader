#!/usr/bin/env python3
"""
eToro Sync for Railway — Direct PostgreSQL, no Supabase wrapper
"""

import os
import sys
import json
import uuid
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import (
    get_positions, upsert_position, delete_position,
    get_watchlist, _get_cursor
)

def etoro_request(endpoint: str) -> dict:
    """Make authenticated request to eToro public API."""
    api_key = os.environ.get("ETORO_API_KEY")
    user_key = os.environ.get("ETORO_USER_KEY")

    if not api_key or not user_key:
        raise ValueError("ETORO_API_KEY or ETORO_USER_KEY not set")

    url = f"https://public-api.etoro.com/api/v1{endpoint}"
    request_id = str(uuid.uuid4())

    req = urllib.request.Request(url)
    req.add_header("x-api-key", api_key)
    req.add_header("x-user-key", user_key)
    req.add_header("x-request-id", request_id)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Origin", "https://etoro.com")
    req.add_header("Referer", "https://etoro.com/")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP Error {e.code}: {e.reason}")

def fetch_instruments(instrument_ids: list) -> dict:
    """Fetch instrument metadata to map IDs to names."""
    if not instrument_ids:
        return {}

    ids_str = ",".join(map(str, instrument_ids))
    data = etoro_request(f"/market-data/instruments?instrumentIds={ids_str}")

    mapping = {}
    for inst in data.get("instrumentDisplayDatas", []):
        iid = inst.get("instrumentID")
        mapping[iid] = {
            "name": inst.get("instrumentDisplayName", "Unknown"),
            "symbol": inst.get("symbolFull", "?"),
            "type": inst.get("instrumentTypeID", 0)
        }
    return mapping

def sync_etoro():
    """Fetch eToro portfolio and update Railway Postgres."""
    print("🔑 Loading eToro credentials...")
    print("📊 Fetching portfolio from eToro API...")

    portfolio = etoro_request("/trading/info/real/pnl")
    cp = portfolio.get("clientPortfolio", {})
    positions = cp.get("positions", [])
    mirrors = cp.get("mirrors", [])
    cash = cp.get("credit", 0)

    # Fetch instrument names
    instrument_ids = sorted(set(p.get("instrumentID") for p in positions if p.get("instrumentID")))
    inst_map = fetch_instruments(instrument_ids)

    # Calculate totals
    direct_exposure = sum(p.get("unrealizedPnL", {}).get("exposureInAccountCurrency", 0) for p in positions)
    direct_pnl = sum(p.get("unrealizedPnL", {}).get("pnL", 0) for p in positions)

    mirror_exposure = 0
    mirror_pnl = 0
    for m in mirrors:
        for p in m.get("positions", []):
            mirror_exposure += p.get("unrealizedPnL", {}).get("exposureInAccountCurrency", 0)
            mirror_pnl += p.get("unrealizedPnL", {}).get("pnL", 0)

    mirror_available = sum(m.get("availableAmount", 0) for m in mirrors)
    total_value = direct_exposure + mirror_exposure + mirror_available + cash

    print(f"\n💰 REAL eToro Value: ${total_value:,.2f}")
    print(f"📈 Direct Positions: {len(positions)} | ${direct_exposure:,.2f}")
    print(f"🪞 Mirrors: {len(mirrors)} | ${mirror_exposure:,.2f}")
    print(f"💵 Cash: ${cash:,.2f}")

    # Aggregate positions by symbol
    from collections import defaultdict
    aggregated = defaultdict(lambda: {"shares": 0, "value": 0, "pnl": 0, "initial": 0})

    for pos in positions:
        iid = pos.get("instrumentID", 0)
        info = inst_map.get(iid, {"symbol": f"ID:{iid}", "name": "Unknown"})
        symbol = info.get("symbol", "?")

        exposure = pos.get("unrealizedPnL", {}).get("exposureInAccountCurrency", 0)
        initial = pos.get("initialAmountInDollars", 0)
        is_buy = pos.get("isBuy", True)
        units = pos.get("units", 0)
        open_rate = pos.get("openRate", 0)

        if units and units > 0:
            shares = abs(units)
        elif open_rate > 0:
            shares = exposure / open_rate
        else:
            shares = 0

        if initial > 0 and shares > 0:
            avg_cost = initial / shares
        elif open_rate > 0:
            avg_cost = open_rate
        else:
            avg_cost = 0

        aggregated[symbol]["shares"] += shares if is_buy else -shares
        aggregated[symbol]["value"] += exposure
        aggregated[symbol]["pnl"] += pos.get("unrealizedPnL", {}).get("pnL", 0)
        aggregated[symbol]["initial"] += initial
        aggregated[symbol]["avg_cost"] = avg_cost

    # Get watchlist for grades
    watchlist = {w['ticker']: w for w in get_watchlist()}

    # Get existing positions to find eToro-only ones to delete
    existing = get_positions()
    etoro_tickers = set()

    # Insert/update positions
    inserted = 0
    updated = 0
    for symbol, data in sorted(aggregated.items(), key=lambda x: x[1]["value"], reverse=True):
        if data["value"] < 1:
            continue

        wl = watchlist.get(symbol, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")

        shares = abs(data["shares"])
        live_price = data["value"] / shares if shares > 0 else 0
        etoro_tickers.add(symbol)

        position = {
            "ticker": symbol,
            "shares": shares,
            "avg_cost": data.get("avg_cost", 0),
            "live_price": live_price,
            "live_value": data["value"],
            "grade": grade,
            "council": council,
            "brokers": ["eToro"],
            "sector": wl.get("sector", ""),
            "updated_at": datetime.now().isoformat()
        }

        # Check if position exists
        existing_pos = next((p for p in existing if p['ticker'] == symbol), None)
        if existing_pos:
            # Merge brokers
            old_brokers = existing_pos.get('brokers', []) or []
            new_brokers = list(set(old_brokers + ["eToro"]))
            position["brokers"] = new_brokers
            position["shares"] = existing_pos.get("shares", 0) + shares  # Add shares
            position["live_value"] = existing_pos.get("live_value", 0) + data["value"]
            upsert_position(position)
            updated += 1
        else:
            upsert_position(position)
            inserted += 1

    # Delete eToro positions that are no longer in portfolio
    for pos in existing:
        if 'eToro' in (pos.get('brokers') or []) and pos['ticker'] not in etoro_tickers:
            # Only delete if eToro is the ONLY broker
            brokers = pos.get('brokers', []) or []
            if len(brokers) == 1 and brokers[0] == 'eToro':
                delete_position(pos['ticker'])
                print(f"  🗑️ Deleted {pos['ticker']} (no longer in eToro)")

    print(f"\n✅ eToro sync: {inserted} inserted, {updated} updated")
    return True

if __name__ == "__main__":
    sync_etoro()
