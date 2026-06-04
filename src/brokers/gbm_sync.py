#!/usr/bin/env python3
"""
GBM Sync - Reads GBM JSON exports and updates Supabase
Handles both GBM Main (MXN) and GBM USA (USD)
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from sync.vox_postgres_sync import get_client

def sync_gbm_main():
    """Sync GBM Main from JSON export."""
    sb = get_client()
    
    print("📊 Loading GBM Main portfolio...")
    with open('/Users/jos/.hermes/scripts/gbm_main_portfolio.json') as f:
        data = json.load(f)
    
    sic = data.get('sic_positions', [])
    national = data.get('national_positions', [])
    
    print(f"  SIC positions: {len(sic)}")
    print(f"  National positions: {len(national)}")
    
    # MXN to USD rate (you should update this)
    rate = 17.5
    
    # Combine all positions (no duplicates - different markets)
    all_positions = []
    
    for p in sic:
        ticker = p.get('ticker')
        if not ticker:
            continue
        mxn = p.get('market_value_mxn', 0)
        usd = mxn / rate
        qty = p.get('qty', 0)
        price_mxn = p.get('price_mxn', 0)
        price_usd = price_mxn / rate
        cost_mxn = p.get('cost_avg_mxn', 0)
        cost_usd = cost_mxn / rate
        
        all_positions.append({
            'ticker': ticker,
            'qty': qty,
            'value_usd': usd,
            'price_usd': price_usd,
            'cost_usd': cost_usd,
            'market': 'SIC_Global',
            'source': 'GBM Main'
        })
    
    for p in national:
        ticker = p.get('ticker')
        if not ticker:
            continue
        mxn = p.get('market_value_mxn', 0)
        usd = mxn / rate
        qty = p.get('qty', 0)
        price_mxn = p.get('price_mxn', 0)
        price_usd = price_mxn / rate
        cost_mxn = p.get('cost_avg_mxn', 0)
        cost_usd = cost_mxn / rate
        
        all_positions.append({
            'ticker': ticker,
            'qty': qty,
            'value_usd': usd,
            'price_usd': price_usd,
            'cost_usd': cost_usd,
            'market': 'Nacional',
            'source': 'GBM Main'
        })
    
    total_usd = sum(p['value_usd'] for p in all_positions)
    print(f"\n💰 GBM Main Total: ${total_usd:,.2f} USD")
    
    # Get watchlist grades
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}
    
    # Clear old GBM Main positions
    try:
        all_pos = sb.table("positions").select("*").execute().data or []
        gbm_ids = [p['id'] for p in all_pos if 'GBM Main' in (p.get('brokers') or [])]
        for pid in gbm_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(gbm_ids)} old GBM Main positions")
    except Exception as e:
        print(f"⚠️ Could not clear: {e}")
    
    # Insert/update positions
    inserted = 0
    for p in all_positions:
        if p['value_usd'] < 1:
            continue
            
        wl = watchlist.get(p['ticker'], {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")
        
        position = {
            "ticker": p['ticker'],
            "shares": p['qty'],
            "avg_cost": p['cost_usd'],
            "live_price": p['price_usd'],
            "live_value": p['value_usd'],
            "grade": grade,
            "council": council,
            "brokers": ["GBM Main"],
            "sector": "",
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            existing = sb.table("positions").select("*").eq("ticker", p['ticker']).execute()
            
            if existing.data:
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["GBM Main"]))
                
                sb.table("positions").update({
                    "shares": p['qty'],
                    "live_price": p['price_usd'],
                    "live_value": p['value_usd'],
                    "grade": grade,
                    "brokers": new_brokers,
                    "updated_at": datetime.now().isoformat()
                }).eq("ticker", p['ticker']).execute()
                print(f"  🔄 Updated {p['ticker']}: ${p['value_usd']:,.2f}")
            else:
                sb.table("positions").insert(position).execute()
                print(f"  ✅ Inserted {p['ticker']}: ${p['value_usd']:,.2f}")
            
            inserted += 1
        except Exception as e:
            print(f"❌ Error with {p['ticker']}: {e}")
    
    print(f"✅ Processed {inserted} GBM Main positions")
    return total_usd

def sync_gbm_usa():
    """Sync GBM USA from JSON export."""
    sb = get_client()
    
    print("\n📊 Loading GBM USA portfolio...")
    with open('/Users/jos/.hermes/scripts/gbm_usa_portfolio.json') as f:
        data = json.load(f)
    
    positions = data.get('positions', [])
    print(f"  Positions: {len(positions)}")
    
    total_usd = sum(p.get('market_value_usd', 0) for p in positions)
    print(f"\n💰 GBM USA Total: ${total_usd:,.2f} USD")
    
    # Get watchlist grades
    try:
        watchlist_response = sb.table("watchlist").select("*").execute()
        watchlist = {w['ticker']: w for w in (watchlist_response.data or [])}
    except:
        watchlist = {}
    
    # Clear old GBM USA positions
    try:
        all_pos = sb.table("positions").select("*").execute().data or []
        gbm_ids = [p['id'] for p in all_pos if 'GBM USA' in (p.get('brokers') or [])]
        for pid in gbm_ids:
            sb.table("positions").delete().eq("id", pid).execute()
        print(f"🗑️ Cleared {len(gbm_ids)} old GBM USA positions")
    except Exception as e:
        print(f"⚠️ Could not clear: {e}")
    
    # Insert/update positions
    inserted = 0
    for p in positions:
        ticker = p.get('ticker')
        if not ticker:
            continue
            
        value_usd = p.get('market_value_usd', 0)
        if value_usd < 1:
            continue
            
        wl = watchlist.get(ticker, {})
        grade = wl.get("grade", 0)
        council = wl.get("council", "N/A")
        
        position = {
            "ticker": ticker,
            "shares": p.get('qty', 0),
            "avg_cost": p.get('cost_avg_usd', 0),
            "live_price": p.get('price_usd', 0),
            "live_value": value_usd,
            "grade": grade,
            "council": council,
            "brokers": ["GBM USA"],
            "sector": "",
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            existing = sb.table("positions").select("*").eq("ticker", ticker).execute()
            
            if existing.data:
                old_brokers = existing.data[0].get('brokers', []) or []
                new_brokers = list(set(old_brokers + ["GBM USA"]))
                
                sb.table("positions").update({
                    "shares": p.get('qty', 0),
                    "live_price": p.get('price_usd', 0),
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
    
    print(f"✅ Processed {inserted} GBM USA positions")
    return total_usd

if __name__ == "__main__":
    try:
        main_total = sync_gbm_main()
        usa_total = sync_gbm_usa()
        print(f"\n🎉 GBM sync complete:")
        print(f"   GBM Main: ${main_total:,.2f}")
        print(f"   GBM USA: ${usa_total:,.2f}")
        print(f"   Total: ${main_total + usa_total:,.2f}")
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        sys.exit(1)
