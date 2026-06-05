#!/usr/bin/env python3
"""
eToro Sync for Railway — Tries API first, falls back to local JSON
"""

import os
import sys
import json
import uuid
import urllib.request
import urllib.error
from datetime import datetime
from collections import defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import (
    get_positions, upsert_position, get_watchlist
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


def parse_etoro_json(data: dict) -> list:
    """Parse raw eToro JSON into position records."""
    cp = data.get('clientPortfolio', {})
    positions = cp.get('positions', [])
    
    aggregated = defaultdict(lambda: {"shares": 0.0, "value": 0.0, "avg_cost": 0.0, "price": 0.0})
    
    for pos in positions:
        symbol = pos.get('_instrumentSymbol', 'UNKNOWN')
        if not symbol or symbol == 'UNKNOWN':
            continue
            
        pnl = pos.get('unrealizedPnL', {})
        exposure = float(pnl.get('exposureInAccountCurrency', 0) or 0)
        close_rate = float(pnl.get('closeRate', 0) or 0)
        
        units = float(pos.get('units', 0) or 0)
        open_rate = float(pos.get('openRate', 0) or 0)
        initial = float(pos.get('initialAmountInDollars', 0) or 0)
        is_buy = pos.get('isBuy', True)
        
        if units > 0:
            shares = abs(units)
        elif close_rate > 0:
            shares = exposure / close_rate
        else:
            shares = 0
            
        if initial > 0 and shares > 0:
            avg_cost = initial / shares
        elif open_rate > 0:
            avg_cost = open_rate
        else:
            avg_cost = close_rate * 0.9 if close_rate > 0 else 0
        
        aggregated[symbol]["shares"] += shares if is_buy else -shares
        aggregated[symbol]["value"] += exposure
        aggregated[symbol]["avg_cost"] = avg_cost
        aggregated[symbol]["price"] = close_rate
    
    records = []
    for symbol, data in aggregated.items():
        shares = abs(data["shares"])
        if shares > 0:
            records.append({
                'ticker': symbol,
                'shares': float(shares),
                'avg_cost': float(data['avg_cost']),
                'live_price': float(data['price']),
                'live_value': float(data['value'])
            })
    
    return records


def to_float(val):
    """Convert Decimal or other numeric to float."""
    if isinstance(val, Decimal):
        return float(val)
    return float(val) if val else 0.0


def sync_etoro_from_json():
    """Fallback: sync from local JSON file."""
    json_path = '/app/data/etoro_portfolio.json'
    if not os.path.exists(json_path):
        print("  ⚠️ eToro JSON not found at /app/data/etoro_portfolio.json")
        return 0
    
    with open(json_path) as f:
        data = json.load(f)
    
    records = parse_etoro_json(data)
    if not records:
        print("  ⚠️ No positions parsed from eToro JSON")
        return 0
    
    existing = {p['ticker']: p for p in get_positions()}
    watchlist = {w['ticker']: w for w in get_watchlist()}
    
    print(f"  📊 eToro JSON: {len(records)} aggregated positions")
    
    count = 0
    for rec in records:
        ticker = rec['ticker']
        shares = rec['shares']
        live_price = rec['live_price']
        live_value = rec['live_value']
        avg_cost = rec['avg_cost']
        
        wl = watchlist.get(ticker, {})
        existing_pos = existing.get(ticker)
        
        if existing_pos and 'eToro' not in (existing_pos.get('brokers') or []):
            # Merge with existing
            old_brokers = existing_pos.get('brokers', []) or []
            new_brokers = list(set(old_brokers + ['eToro']))
            old_shares = to_float(existing_pos.get('shares', 0))
            old_value = to_float(existing_pos.get('live_value', 0))
            
            upsert_position({
                'ticker': ticker,
                'shares': old_shares + shares,
                'avg_cost': avg_cost,
                'live_price': live_price,
                'live_value': old_value + live_value,
                'grade': wl.get('grade', existing_pos.get('grade', 0)),
                'council': wl.get('council', existing_pos.get('council', 'N/A')),
                'brokers': new_brokers,
                'sector': wl.get('sector', existing_pos.get('sector', '')),
                'updated_at': datetime.now().isoformat()
            })
        else:
            # New or update eToro-only
            upsert_position({
                'ticker': ticker,
                'shares': shares,
                'avg_cost': avg_cost,
                'live_price': live_price,
                'live_value': live_value,
                'grade': wl.get('grade', 0),
                'council': wl.get('council', 'N/A'),
                'brokers': ['eToro'],
                'sector': wl.get('sector', ''),
                'updated_at': datetime.now().isoformat()
            })
        count += 1
    
    print(f"  ✅ Synced {count} eToro positions from JSON")
    return count


def sync_etoro():
    """Sync eToro positions — API first, JSON fallback."""
    print("🔑 Loading eToro credentials...")
    
    try:
        print("📊 Fetching portfolio from eToro API...")
        portfolio = etoro_request("/trading/info/real/pnl")
        records = parse_etoro_json(portfolio)
        
        print(f"  📊 eToro API: {len(records)} positions")
        
        existing = {p['ticker']: p for p in get_positions()}
        watchlist = {w['ticker']: w for w in get_watchlist()}
        
        for rec in records:
            ticker = rec['ticker']
            wl = watchlist.get(ticker, {})
            existing_pos = existing.get(ticker)
            
            if existing_pos and 'eToro' not in (existing_pos.get('brokers') or []):
                old_brokers = existing_pos.get('brokers', []) or []
                new_brokers = list(set(old_brokers + ['eToro']))
                upsert_position({
                    'ticker': ticker,
                    'shares': to_float(existing_pos.get('shares', 0)) + rec['shares'],
                    'avg_cost': rec['avg_cost'],
                    'live_price': rec['live_price'],
                    'live_value': to_float(existing_pos.get('live_value', 0)) + rec['live_value'],
                    'grade': wl.get('grade', existing_pos.get('grade', 0)),
                    'council': wl.get('council', existing_pos.get('council', 'N/A')),
                    'brokers': new_brokers,
                    'sector': wl.get('sector', existing_pos.get('sector', '')),
                    'updated_at': datetime.now().isoformat()
                })
            else:
                upsert_position({
                    'ticker': ticker,
                    'shares': rec['shares'],
                    'avg_cost': rec['avg_cost'],
                    'live_price': rec['live_price'],
                    'live_value': rec['live_value'],
                    'grade': wl.get('grade', 0),
                    'council': wl.get('council', 'N/A'),
                    'brokers': ['eToro'],
                    'sector': wl.get('sector', ''),
                    'updated_at': datetime.now().isoformat()
                })
        
        print(f"  ✅ eToro API sync complete: {len(records)} positions")
        return len(records)
        
    except Exception as e:
        print(f"  ⚠️ eToro API failed: {e}")
        print("  📂 Falling back to local JSON...")
        return sync_etoro_from_json()


if __name__ == "__main__":
    sync_etoro()
