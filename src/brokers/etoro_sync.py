#!/usr/bin/env python3
"""
eToro Sync - Fetches real data from eToro API and updates Supabase
"""

import os
import sys
import json
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Add scripts path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import get_client

def load_env():
    """Load API keys from ~/.hermes/.env"""
    env_path = Path.home() / ".hermes" / ".env"
    keys = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    keys[key] = val
    return keys

def etoro_request(endpoint: str, env: dict) -> dict:
    """Make authenticated request to eToro public API."""
    api_key = env.get("ETORO_API_KEY")
    user_key = env.get("ETORO_USER_KEY")

    if not api_key or not user_key:
        raise ValueError("ETORO_API_KEY or ETORO_USER_KEY not found")

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

def fetch_instruments(env: dict, instrument_ids: list) -> dict:
    """Fetch instrument metadata to map IDs to names."""
    if not instrument_ids:
        return {}

    ids_str = ",".join(map(str, instrument_ids))
    data = etoro_request(f"/market-data/instruments?instrumentIds={ids_str}", env)

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
    """Fetch eToro portfolio and update Supabase."""
    env = load_env()
    sb = get_client()

    print("🔑 Loading eToro credentials...")
    print("📊 Fetching portfolio from eToro API...")

    portfolio = etoro_request("/trading/info/real/pnl", env)
    cp = portfolio.get("clientPortfolio", {})
    positions = cp.get("positions", [])
    mirrors = cp.get("mirrors", [])
    cash = cp.get("credit", 0)

    # Fetch instrument names
    instrument_ids = sorted(set(p.get("instrumentID") for p in positions if p.get("instrumentID")))
    inst_map = fetch_instruments(env, instrument_ids)

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
        pnl = pos.get("unrealizedPnL", {}).get("pnL", 0)
        initial = pos.get("initialAmountInDollars", 0)
        is_buy = pos.get("isBuy", True)
        units = pos.get("units", 0)  # Actual share count
        open_rate = pos.get("openRate", 0)  # Entry price per share

        # Use actual units if available, otherwise derive from exposure/openRate
        if units and units > 0:
            shares = abs(units)
        elif open_rate > 0:
            shares = exposure / open_rate
        else:
            shares = 0

        # Calculate avg_cost: if we know initial investment and shares
        if initial > 0 and shares > 0:
            avg_cost = initial / shares
        elif open_rate > 0:
            avg_cost = open_rate
        else:
            avg_cost = 0

        aggregated[symbol]["shares"] += shares if is_buy else -shares
        aggregated[symbol]["value"] += exposure
        aggregated[symbol]["pnl"] += pnl
        aggregated[symbol]["initial"] += initial
        aggregated[symbol]["avg_cost"] = avg_cost  # Store for later use

    # Get grades from watchlist
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}

    # Update Supabase
    print(f"\n🔄 Updating Supabase with {len(aggregated)} eToro positions...")

    # First, delete old eToro positions
    try:
        # Get all positions and filter for eToro
        all_positions = sb.table("positions").select("*").execute().data or []
        etoro_ids = [p['id'] for p in all_positions if 'eToro' in (p.get('brokers') or [])]
        
        for pid in etoro_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(etoro_ids)} old eToro positions")
    except Exception as e:
        print(f"⚠️ Could not clear old positions: {e}")

    # Insert new positions
    inserted = 0
    for symbol, data in sorted(aggregated.items(), key=lambda x: x[1]["value"], reverse=True):
        if data["value"] < 1:  # Skip tiny positions
            continue

        # Get grade from watchlist or default
        wl = watchlist.get(symbol, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")

        # Calculate live price
        shares = abs(data["shares"])
        live_price = data["value"] / shares if shares > 0 else 0

        position = {
            "ticker": symbol,
            "shares": shares,
            "avg_cost": data.get("avg_cost", 0),
            "live_price": live_price,
            "live_value": data["value"],
            "grade": grade,
            "council": council,
            "brokers": ["eToro"],
            "sector": "",
            "updated_at": datetime.now().isoformat()
        }

        try:
            # Check if position already exists
            existing = sb.table("positions").select("*").eq("ticker", symbol).execute()
            
            if existing.data:
                # Update existing position - merge brokers
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["eToro"]))
                
                # Update with new values
                sb.table("positions").update({
                    "shares": shares,
                    "avg_cost": data.get("avg_cost", 0),
                    "live_price": live_price,
                    "live_value": data["value"],
                    "grade": grade,
                    "council": council,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", symbol).execute()
                print(f"  🔄 Updated {symbol}: ${data['value']:,.2f}")
            else:
                # Insert new position
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {symbol}: ${data['value']:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {symbol}: {e}")

    print(f"✅ Inserted {inserted} eToro positions into Supabase")
    print(f"💰 Total eToro value: ${direct_exposure:,.2f}")

    # Save to JSON for backup
    output = {
        "total_value": total_value,
        "cash": cash,
        "direct_positions": len(positions),
        "mirrors": len(mirrors),
        "aggregated": dict(aggregated),
        "last_synced": datetime.now().isoformat()
    }

    output_path = Path.home() / ".hermes" / "scripts" / "etoro_sync_result.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"💾 Backup saved to: {output_path}")

    return total_value

if __name__ == "__main__":
    try:
        value = sync_etoro()
        print(f"\n🎉 eToro sync complete: ${value:,.2f}")
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)
