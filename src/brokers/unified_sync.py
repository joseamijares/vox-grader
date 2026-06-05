#!/usr/bin/env python3
"""
Unified Broker Sync for Railway
Reads portfolio JSON files and syncs to Railway Postgres.
Supports: eToro, GBM Main, GBM USA, IBKR, Schwab, Binance, Bitso
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import (
    get_positions, upsert_position, delete_positions_by_broker,
    get_watchlist
)

# MXN to USD rate
MXN_USD_RATE = 17.5


def load_json(path):
    """Load JSON file, return None if not found."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def get_watchlist_grades():
    """Get watchlist for grade lookups."""
    try:
        return {w['ticker']: w for w in get_watchlist()}
    except:
        return {}


def sync_gbm_main():
    """Sync GBM Main (MXN) portfolio."""
    data = load_json('/app/data/gbm_main_portfolio.json')
    if not data:
        print("  ⚠️ GBM Main JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    sic = data.get('sic_positions', [])
    national = data.get('national_positions', [])
    
    print(f"  📊 GBM Main: {len(sic)} SIC + {len(national)} national")
    
    count = 0
    for pos in sic + national:
        ticker = pos['ticker']
        qty = pos.get('qty', 0)
        price_mxn = pos.get('price_mxn', 0)
        cost_avg_mxn = pos.get('cost_avg_mxn', 0)
        market_value_mxn = pos.get('market_value_mxn', 0)
        
        # Convert to USD
        price_usd = price_mxn / MXN_USD_RATE if price_mxn else 0
        avg_cost_usd = cost_avg_mxn / MXN_USD_RATE if cost_avg_mxn else 0
        live_value_usd = market_value_mxn / MXN_USD_RATE if market_value_mxn else 0
        
        wl = watchlist.get(ticker, {})
        
        upsert_position({
            'ticker': ticker,
            'shares': qty,
            'avg_cost': avg_cost_usd,
            'live_price': price_usd,
            'live_value': live_value_usd,
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['GBM Main'],
            'sector': wl.get('sector', ''),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} GBM Main positions")
    return count


def sync_gbm_usa():
    """Sync GBM USA (USD) portfolio."""
    data = load_json('/app/data/gbm_usa_portfolio.json')
    if not data:
        print("  ⚠️ GBM USA JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    positions = data.get('positions', [])
    
    print(f"  📊 GBM USA: {len(positions)} positions")
    
    count = 0
    for pos in positions:
        ticker = pos['ticker']
        wl = watchlist.get(ticker, {})
        
        upsert_position({
            'ticker': ticker,
            'shares': pos.get('qty', 0),
            'avg_cost': pos.get('cost_avg_usd', 0),
            'live_price': pos.get('price_usd', 0),
            'live_value': pos.get('market_value_usd', 0),
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['GBM USA'],
            'sector': wl.get('sector', ''),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} GBM USA positions")
    return count


def sync_ibkr():
    """Sync IBKR portfolio."""
    data = load_json('/app/data/ibkr_portfolio.json')
    if not data:
        print("  ⚠️ IBKR JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    positions = data.get('positions', [])
    
    print(f"  📊 IBKR: {len(positions)} positions")
    
    count = 0
    for pos in positions:
        ticker = pos['ticker']
        shares = pos.get('shares', 0)
        last_price = pos.get('last_price', 0)
        
        # Derive avg_cost from cost_basis if available
        cost_basis = pos.get('cost_basis', 0)
        avg_cost = cost_basis / shares if shares and cost_basis else last_price * 0.9
        
        wl = watchlist.get(ticker, {})
        
        upsert_position({
            'ticker': ticker,
            'shares': shares,
            'avg_cost': avg_cost,
            'live_price': last_price,
            'live_value': shares * last_price,
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['IBKR'],
            'sector': wl.get('sector', ''),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} IBKR positions")
    return count


def sync_schwab():
    """Sync Schwab portfolio."""
    data = load_json('/app/data/schwab_portfolio.json')
    if not data:
        print("  ⚠️ Schwab JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    positions = data.get('positions', [])
    
    print(f"  📊 Schwab: {len(positions)} positions")
    
    count = 0
    for pos in positions:
        ticker = pos['ticker']
        shares = pos.get('shares', 0)
        last_price = pos.get('last_price', 0)
        market_value = pos.get('market_value', 0)
        
        # Derive avg_cost from unrealized_pnl if available
        unrealized = pos.get('unrealized_pnl', 0)
        cost_basis = pos.get('cost_basis', 0)
        if cost_basis and shares:
            avg_cost = cost_basis / shares
        elif market_value and unrealized and shares:
            avg_cost = (market_value - unrealized) / shares
        else:
            avg_cost = last_price * 0.9
        
        wl = watchlist.get(ticker, {})
        
        upsert_position({
            'ticker': ticker,
            'shares': shares,
            'avg_cost': avg_cost,
            'live_price': last_price,
            'live_value': market_value,
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['Schwab'],
            'sector': pos.get('sector', wl.get('sector', '')),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} Schwab positions")
    return count


def sync_binance():
    """Sync Binance portfolio."""
    data = load_json('/app/data/binance_portfolio.json')
    if not data:
        print("  ⚠️ Binance JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    balances = data.get('balances', [])
    
    # Filter meaningful balances (> $10)
    meaningful = [b for b in balances if b.get('value_usd', 0) > 10]
    
    print(f"  📊 Binance: {len(meaningful)} meaningful balances")
    
    count = 0
    for bal in meaningful:
        asset = bal['asset']
        total = bal.get('total', 0)
        price_usd = bal.get('price_usd', 0)
        value_usd = bal.get('value_usd', 0)
        
        wl = watchlist.get(asset, {})
        
        upsert_position({
            'ticker': asset,
            'shares': total,
            'avg_cost': price_usd * 0.85,  # Estimate
            'live_price': price_usd,
            'live_value': value_usd,
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['Binance'],
            'sector': wl.get('sector', 'Crypto'),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} Binance positions")
    return count


def sync_bitso():
    """Sync Bitso portfolio (tiny, mostly ignore)."""
    data = load_json('/app/data/bitso_portfolio.json')
    if not data:
        print("  ⚠️ Bitso JSON not found")
        return 0
    
    watchlist = get_watchlist_grades()
    balances = data.get('balances', [])
    
    # Filter meaningful balances (> $5)
    meaningful = [b for b in balances if b.get('value_usd', 0) > 5]
    
    print(f"  📊 Bitso: {len(meaningful)} meaningful balances")
    
    count = 0
    for bal in meaningful:
        asset = bal['currency'].upper()
        total = bal.get('total', 0)
        price_usd = bal.get('price_usd', 0)
        value_usd = bal.get('value_usd', 0)
        
        wl = watchlist.get(asset, {})
        
        upsert_position({
            'ticker': asset,
            'shares': total,
            'avg_cost': price_usd * 0.85,
            'live_price': price_usd,
            'live_value': value_usd,
            'grade': wl.get('grade', 0),
            'council': wl.get('council', 'N/A'),
            'brokers': ['Bitso'],
            'sector': wl.get('sector', 'Crypto'),
            'updated_at': datetime.now().isoformat()
        })
        count += 1
    
    print(f"  ✅ Synced {count} Bitso positions")
    return count


def sync_all_brokers():
    """Sync all broker portfolios."""
    print(f"\n{'='*60}")
    print(f"[Unified Sync] Starting all broker syncs...")
    print(f"{'='*60}\n")
    
    total = 0
    total += sync_gbm_main()
    total += sync_gbm_usa()
    total += sync_ibkr()
    total += sync_schwab()
    total += sync_binance()
    total += sync_bitso()
    
    print(f"\n{'='*60}")
    print(f"[Unified Sync] Total: {total} positions synced")
    print(f"{'='*60}\n")
    return total


if __name__ == "__main__":
    sync_all_brokers()
