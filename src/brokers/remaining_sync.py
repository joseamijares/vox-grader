#!/usr/bin/env python3
"""
Sync IBKR, Schwab, and Bitso from JSON exports
"""

import json
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import get_client

def sync_ibkr():
    """Sync IBKR from JSON export."""
    sb = get_client()
    
    print("📊 Loading IBKR portfolio...")
    with open('/Users/jos/.hermes/scripts/ibkr_portfolio.json') as f:
        data = json.load(f)
    
    positions = data.get('positions', [])
    summary = data.get('portfolio_summary', {})
    
    print(f"  Positions: {len(positions)}")
    
    total_value = summary.get('market_value', 0)
    cash = summary.get('cash_usd', 0)
    
    print(f"\n💰 IBKR Total: ${total_value:,.2f} USD")
    print(f"💵 Cash: ${cash:,.2f}")
    
    # Get watchlist grades
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}
    
    # Clear old IBKR positions
    try:
        all_pos = sb.table("positions").select("*").execute().data or []
        ibkr_ids = [p['id'] for p in all_pos if 'IBKR' in (p.get('brokers') or [])]
        for pid in ibkr_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(ibkr_ids)} old IBKR positions")
    except Exception as e:
        print(f"⚠️ Could not clear: {e}")
    
    # Insert/update positions
    inserted = 0
    for p in positions:
        ticker = p.get('ticker')
        if not ticker:
            continue
            
        shares = p.get('shares', 0)
        price = p.get('last_price', 0)
        value = shares * price
        
        if value < 1:
            continue
            
        wl = watchlist.get(ticker, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")
        
        position = {
            "ticker": ticker,
            "shares": shares,
            "avg_cost": price * 0.7,  # Estimate
            "live_price": price,
            "live_value": value,
            "grade": grade,
            "council": council,
            "brokers": ["IBKR"],
            "sector": "",
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            existing = sb.table("positions").select("*").eq("ticker", ticker).execute()
            
            if existing.data:
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["IBKR"]))
                
                sb.table("positions").update({
                    "shares": shares,
                    "live_price": price,
                    "live_value": value,
                    "grade": grade,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", ticker).execute()
                print(f"  🔄 Updated {ticker}: ${value:,.2f}")
            else:
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {ticker}: ${value:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {ticker}: {e}")
    
    print(f"✅ Processed {inserted} IBKR positions")
    return total_value

def sync_schwab():
    """Sync Schwab from JSON export."""
    sb = get_client()
    
    print("\n📊 Loading Schwab portfolio...")
    with open('/Users/jos/.hermes/scripts/schwab_portfolio.json') as f:
        data = json.load(f)
    
    positions = data.get('positions', [])
    cash = data.get('cash', 0)
    
    print(f"  Positions: {len(positions)}")
    print(f"  Cash: ${cash:,.2f}")
    
    total_value = sum(p.get('market_value', 0) for p in positions)
    print(f"\n💰 Schwab Total: ${total_value:,.2f} USD")
    
    # Get watchlist grades
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}
    
    # Clear old Schwab positions
    try:
        all_pos = sb.table("positions").select("*").execute().data or []
        schwab_ids = [p['id'] for p in all_pos if 'Schwab' in (p.get('brokers') or [])]
        for pid in schwab_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(schwab_ids)} old Schwab positions")
    except Exception as e:
        print(f"⚠️ Could not clear: {e}")
    
    # Insert/update positions
    inserted = 0
    for p in positions:
        ticker = p.get('ticker')
        if not ticker:
            continue
            
        value = p.get('market_value', 0)
        if value < 1:
            continue
            
        wl = watchlist.get(ticker, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")
        
        position = {
            "ticker": ticker,
            "shares": p.get('shares', 0),
            "avg_cost": p.get('cost_basis', 0),
            "live_price": p.get('last_price', 0),
            "live_value": value,
            "grade": grade,
            "council": council,
            "brokers": ["Schwab"],
            "sector": p.get('sector', ''),
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            existing = sb.table("positions").select("*").eq("ticker", ticker).execute()
            
            if existing.data:
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["Schwab"]))
                
                sb.table("positions").update({
                    "shares": p.get('shares', 0),
                    "live_price": p.get('last_price', 0),
                    "live_value": value,
                    "grade": grade,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", ticker).execute()
                print(f"  🔄 Updated {ticker}: ${value:,.2f}")
            else:
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {ticker}: ${value:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {ticker}: {e}")
    
    print(f"✅ Processed {inserted} Schwab positions")
    return total_value

def sync_bitso():
    """Sync Bitso from JSON export."""
    sb = get_client()
    
    print("\n📊 Loading Bitso portfolio...")
    with open('/Users/jos/.hermes/scripts/bitso_portfolio.json') as f:
        data = json.load(f)
    
    balances = data.get('balances', [])
    total_usd = data.get('total_usd', 0)
    
    print(f"  Balances: {len(balances)}")
    print(f"\n💰 Bitso Total: ${total_usd:,.2f} USD")
    
    # Get watchlist grades
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}
    
    # Clear old Bitso positions
    try:
        all_pos = sb.table("positions").select("*").execute().data or []
        bitso_ids = [p['id'] for p in all_pos if 'Bitso' in (p.get('brokers') or [])]
        for pid in bitso_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(bitso_ids)} old Bitso positions")
    except Exception as e:
        print(f"⚠️ Could not clear: {e}")
    
    # Insert/update positions
    inserted = 0
    for b in balances:
        currency = b.get('currency', '').upper()
        value_usd = b.get('value_usd', 0)
        
        if value_usd < 1:  # Skip tiny amounts
            continue
            
        # Map currency to ticker
        ticker = currency
        if currency == 'BTC':
            ticker = 'BTC'
        elif currency == 'ETH':
            ticker = 'ETH'
        elif currency == 'USD':
            continue  # Skip cash
            
        wl = watchlist.get(ticker, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")
        
        # Crypto grades
        if grade == 0:
            if ticker in ['BTC', 'ETH']:
                grade = 65
            else:
                grade = 35
        
        position = {
            "ticker": ticker,
            "shares": b.get('total', 0),
            "avg_cost": b.get('price_usd', 0) * 0.9,
            "live_price": b.get('price_usd', 0),
            "live_value": value_usd,
            "grade": grade,
            "council": council,
            "brokers": ["Bitso"],
            "sector": "Crypto",
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            existing = sb.table("positions").select("*").eq("ticker", ticker).execute()
            
            if existing.data:
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["Bitso"]))
                
                sb.table("positions").update({
                    "shares": b.get('total', 0),
                    "live_price": b.get('price_usd', 0),
                    "live_value": value_usd,
                    "grade": grade,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", ticker).execute()
                print(f"  🔄 Updated {ticker}: ${value_usd:,.2f}")
            else:
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {ticker}: ${value_usd:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {ticker}: {e}")
    
    print(f"✅ Processed {inserted} Bitso positions")
    return total_usd

if __name__ == "__main__":
    try:
        ibkr_total = sync_ibkr()
        schwab_total = sync_schwab()
        bitso_total = sync_bitso()
        
        print(f"\n🎉 All syncs complete:")
        print(f"   IBKR: ${ibkr_total:,.2f}")
        print(f"   Schwab: ${schwab_total:,.2f}")
        print(f"   Bitso: ${bitso_total:,.2f}")
        print(f"   Total: ${ibkr_total + schwab_total + bitso_total:,.2f}")
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)
