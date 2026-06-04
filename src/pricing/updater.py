"""Daily price updater for all portfolio positions."""
import yfinance as yf
from typing import Dict, List
from datetime import datetime


def get_current_price(ticker: str) -> Dict:
    """Get current price for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        prev_close = info.get('regularMarketPreviousClose') or info.get('previousClose')
        
        if price and prev_close:
            change_pct = ((price - prev_close) / prev_close) * 100
        else:
            change_pct = 0
        
        return {
            'ticker': ticker,
            'price': price,
            'change_pct': change_pct,
            'currency': info.get('currency', 'USD'),
            'timestamp': datetime.now().isoformat(),
            'valid': True
        }
    except Exception as e:
        return {
            'ticker': ticker,
            'price': None,
            'change_pct': None,
            'error': str(e),
            'valid': False
        }


def update_all_prices(sb_client) -> Dict:
    """Update prices for all positions in Supabase."""
    # Get all positions
    resp = sb_client.table('positions').select('ticker').execute()
    tickers = list(set([p['ticker'] for p in resp.data]))
    
    updated = 0
    failed = 0
    alerts = []
    
    print(f"Updating prices for {len(tickers)} tickers...\n")
    
    for ticker in tickers:
        result = get_current_price(ticker)
        
        if not result['valid'] or result['price'] is None:
            print(f"  ❌ {ticker}: {result.get('error', 'Price unavailable')}")
            failed += 1
            continue
        
        try:
            # Update position price (price_change_pct calculated on read, not stored)
            sb_client.table('positions').update({
                'live_price': result['price'],
                'updated_at': datetime.now().isoformat()
            }).eq('ticker', ticker).execute()
            
            # Check for alerts (>10% move)
            if abs(result['change_pct']) >= 10:
                alerts.append({
                    'ticker': ticker,
                    'change_pct': result['change_pct'],
                    'price': result['price']
                })
            
            print(f"  ✅ {ticker}: ${result['price']:.2f} ({result['change_pct']:+.2f}%)")
            updated += 1
            
        except Exception as e:
            print(f"  ❌ {ticker}: DB error - {e}")
            failed += 1
    
    return {
        'updated': updated,
        'failed': failed,
        'alerts': alerts,
        'total': len(tickers)
    }
