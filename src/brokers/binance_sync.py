#!/usr/bin/env python3
"""
Binance Sync - Fetches real data from Binance API and updates Supabase
"""

import os
import sys
import json
import time
import hashlib
import hmac
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
                    keys[key] = val.strip('"').strip("'")
    return keys

def resolve_price(asset, prices):
    """Resolve USD price for any asset."""
    if asset.startswith("LD"):
        asset = asset[2:]
    if asset in ("USDT", "FDUSD", "BUSD", "USDC", "TUSD", "DAI", "USD1", "USDS",
                 "USDE", "EURI", "AEUR", "RLUSD", "XUSD", "BFUSD"):
        return 1.0
    if asset in ("BETH", "WBETH"):
        return prices.get("ETH", 0)
    if asset == "WBTC":
        return prices.get("BTC", 0)
    if asset.startswith("1000"):
        base = asset[4:]
        return prices.get(base, 0) / 1000.0
    if asset in prices:
        return prices[asset]
    return 0

def sync_binance():
    """Fetch Binance portfolio and update Supabase."""
    try:
        from binance.client import Client
    except ImportError:
        print("❌ python-binance not installed")
        sys.exit(1)

    env = load_env()
    api_key = env.get("BINANCE_API_KEY")
    api_secret = env.get("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("BINANCE_API_KEY or BINANCE_API_SECRET not found")

    sb = get_client()
    client = Client(api_key, api_secret)
    BASE = "https://api.binance.com"

    print("🔑 Loading Binance credentials...")
    print("📊 Fetching portfolio from Binance API...")

    # ---- 1. Get prices ----
    prices = {}
    for t in client.get_symbol_ticker():
        s = t["symbol"]
        if s.endswith("USDT"):
            prices[s.replace("USDT", "")] = float(t["price"])
    print(f"📊 Loaded {len(prices)} prices")

    # ---- 2. Spot account ----
    account = client.get_account()
    spot = {}
    for b in account["balances"]:
        free = float(b["free"])
        locked = float(b["locked"])
        total = free + locked
        if total > 0:
            spot[b["asset"]] = total

    # ---- 3. Simple Earn Flexible ----
    def signed_get(endpoint, params=None):
        if params is None:
            params = {}
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        sig = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{BASE}{endpoint}?{query}&signature={sig}"
        import requests
        r = requests.get(url, headers={"X-MBX-APIKEY": api_key})
        return r.json()

    flex_earn = {}
    try:
        resp = signed_get("/sapi/v1/simple-earn/flexible/position")
        for row in resp.get("rows", []):
            asset = row["asset"]
            amt = float(row.get("totalAmount", 0))
            if amt > 0:
                flex_earn[asset] = flex_earn.get(asset, 0) + amt
    except Exception as e:
        print(f"⚠️ Flexible earn error: {e}")

    # ---- 4. Simple Earn Locked ----
    locked_earn = {}
    try:
        resp = signed_get("/sapi/v1/simple-earn/locked/position")
        for row in resp.get("rows", []):
            asset = row.get("asset", "")
            amt = 0
            for field in ["amount", "totalAmount", "rewards", "principal"]:
                if field in row and row[field] is not None:
                    try:
                        amt = float(row[field])
                        break
                    except:
                        pass
            if amt > 0:
                locked_earn[asset] = locked_earn.get(asset, 0) + amt
    except Exception as e:
        print(f"⚠️ Locked earn error: {e}")

    # ---- 5. Merge all wallets ----
    all_assets = {}

    def add(source, asset, qty):
        if qty <= 0:
            return
        if asset not in all_assets:
            all_assets[asset] = {"total": 0.0, "sources": []}
        all_assets[asset]["total"] += qty
        all_assets[asset]["sources"].append((source, qty))

    for asset, qty in spot.items():
        if asset.startswith("LD"):
            real = asset[2:]
            add("SpotEarn", real, qty)
        else:
            add("Spot", asset, qty)

    for asset, qty in flex_earn.items():
        add("FlexEarn", asset, qty)

    for asset, qty in locked_earn.items():
        add("LockedEarn", asset, qty)

    # ---- 6. Build output ----
    total_usd = 0.0
    balances = []
    for asset, data in all_assets.items():
        qty = data["total"]
        price = resolve_price(asset, prices)
        value = qty * price
        total_usd += value
        if value > 1:  # Only include >$1
            balances.append({
                "asset": asset,
                "total": qty,
                "price_usd": price,
                "value_usd": value,
                "sources": data["sources"]
            })

    balances.sort(key=lambda x: x["value_usd"], reverse=True)

    print(f"\n💰 REAL Binance Value: ${total_usd:,.2f}")
    print(f"📈 Assets: {len(balances)} (>$1)")
    print(f"\n📈 TOP HOLDINGS:")
    for b in balances[:10]:
        print(f"  {b['asset']:8} | {b['total']:12.4f} | ${b['value_usd']:>10,.2f}")

    # Get grades from watchlist
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}

    # Update Supabase
    print(f"\n🔄 Updating Supabase with {len(balances)} Binance positions...")

    # First, delete old Binance positions
    try:
        all_positions = sb.table("positions").select("*").execute().data or []
        binance_ids = [p['id'] for p in all_positions if 'Binance' in (p.get('brokers') or [])]
        
        for pid in binance_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(binance_ids)} old Binance positions")
    except Exception as e:
        print(f"⚠️ Could not clear old positions: {e}")

    # Insert/update new positions
    inserted = 0
    for b in balances:
        symbol = b['asset']
        value = b['value_usd']
        qty = b['total']
        price = b['price_usd']

        # Get grade from watchlist or default (crypto-specific)
        wl = watchlist.get(symbol, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")

        # Crypto-specific grading if no grade
        if grade == 0:
            if symbol in ['BTC', 'ETH']:
                grade = 65  # Strong crypto
            elif symbol in ['BNB', 'SOL']:
                grade = 55
            elif symbol in ['DOGE', 'XRP']:
                grade = 40
            else:
                grade = 35

        position = {
            "ticker": symbol,
            "shares": qty,
            "avg_cost": price * 0.9,  # Estimate 10% profit
            "live_price": price,
            "live_value": value,
            "grade": grade,
            "council": council,
            "brokers": ["Binance"],
            "sector": "Crypto",
            "updated_at": datetime.now().isoformat()
        }

        try:
            # Check if position already exists
            existing = sb.table("positions").select("*").eq("ticker", symbol).execute()
            
            if existing.data:
                # Update existing position - merge brokers
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["Binance"]))
                
                sb.table("positions").update({
                    "shares": qty,
                    "live_price": price,
                    "live_value": value,
                    "grade": grade,
                    "council": council,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", symbol).execute()
                print(f"  🔄 Updated {symbol}: ${value:,.2f}")
            else:
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {symbol}: ${value:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {symbol}: {e}")

    print(f"✅ Processed {inserted} Binance positions into Supabase")
    print(f"💰 Total Binance value: ${total_usd:,.2f}")

    # Save to JSON for backup
    output = {
        "total_usd": total_usd,
        "balances": balances,
        "last_synced": datetime.now().isoformat()
    }

    output_path = Path.home() / ".hermes" / "scripts" / "binance_sync_result.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"💾 Backup saved to: {output_path}")

    return total_usd

if __name__ == "__main__":
    try:
        value = sync_binance()
        print(f"\n🎉 Binance sync complete: ${value:,.2f}")
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)
