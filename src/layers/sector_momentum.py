"""Supply Chain Sector momentum tracker.

Computes sector-level momentum from watchlist + positions.
Tracks which sectors are trending up/down based on:
- Average grade per sector
- Average 1d/5d/20d returns
- Volume trends
- Number of BUY vs SELL signals
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

with open(os.path.expanduser('~/dev/vox-python/.env'), 'r') as f:
    for line in f:
        if line.startswith('SUPABASE_KEY='):
            os.environ['SUPABASE_KEY'] = line.strip().split('=', 1)[1]

from sync.vox_postgres_sync import get_client


def get_sector_returns(tickers: List[str]) -> Dict[str, float]:
    """Get 1d, 5d, 20d returns for a list of tickers."""
    returns = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1mo")
            if len(hist) >= 20:
                returns[ticker] = {
                    '1d': (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100,
                    '5d': (hist['Close'].iloc[-1] - hist['Close'].iloc[-6]) / hist['Close'].iloc[-6] * 100 if len(hist) >= 6 else 0,
                    '20d': (hist['Close'].iloc[-1] - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20] * 100,
                }
        except Exception:
            continue
    return returns


def compute_sector_momentum() -> Dict:
    """Compute sector momentum from all watchlist + positions."""
    
    # Get all tickers with sectors
    pos = sb.table('positions').select('ticker,sector,grade,council').execute().data
    watch = sb.table('watchlist').select('ticker,sector,grade,council').execute().data
    
    all_items = pos + watch
    
    # Group by sector
    from collections import defaultdict
    sector_tickers = defaultdict(list)
    sector_grades = defaultdict(list)
    sector_councils = defaultdict(lambda: {'BUY': 0, 'HOLD': 0, 'SELL': 0})
    
    for item in all_items:
        sector = item.get('sector') or 'Uncategorized'
        ticker = item['ticker']
        sector_tickers[sector].append(ticker)
        if item.get('grade'):
            sector_grades[sector].append(int(item['grade']))
        if item.get('council'):
            council = item['council']
            if 'BUY' in council:
                sector_councils[sector]['BUY'] += 1
            elif 'SELL' in council:
                sector_councils[sector]['SELL'] += 1
            else:
                sector_councils[sector]['HOLD'] += 1
    
    # Compute returns for each sector
    sector_results = []
    
    for sector, tickers in sector_tickers.items():
        unique_tickers = list(set(tickers))[:20]  # Limit to 20 per sector for speed
        returns = get_sector_returns(unique_tickers)
        
        if not returns:
            continue
        
        avg_1d = np.mean([r['1d'] for r in returns.values()])
        avg_5d = np.mean([r['5d'] for r in returns.values()])
        avg_20d = np.mean([r['20d'] for r in returns.values()])
        avg_grade = np.mean(sector_grades[sector]) if sector_grades[sector] else 50
        
        # Momentum score: weighted combination
        momentum = int(
            min(100, max(0, avg_grade)) * 0.3 +
            min(100, max(0, avg_5d + 50)) * 0.3 +
            min(100, max(0, avg_20d + 50)) * 0.2 +
            (sector_councils[sector]['BUY'] / max(1, len(tickers)) * 100) * 0.2
        )
        
        # Top tickers by return
        sorted_tickers = sorted(returns.items(), key=lambda x: x[1]['5d'], reverse=True)[:5]
        
        sector_results.append({
            'sector': sector,
            'avg_grade': round(avg_grade, 1),
            'avg_return_1d': round(avg_1d, 2),
            'avg_return_5d': round(avg_5d, 2),
            'avg_return_20d': round(avg_20d, 2),
            'momentum_score': momentum,
            'top_tickers': [t[0] for t in sorted_tickers],
            'buy_count': sector_councils[sector]['BUY'],
            'hold_count': sector_councils[sector]['HOLD'],
            'sell_count': sector_councils[sector]['SELL'],
            'computed_at': datetime.now().isoformat()
        })
    
    # Store in Supabase
    print(f"Storing {len(sector_results)} sector momentum records...")
    for sr in sector_results:
        try:
            existing = sb.table('sector_momentum').select('id').eq('sector', sr['sector']).execute()
            if existing.data:
                sb.table('sector_momentum').update(sr).eq('sector', sr['sector']).execute()
            else:
                sb.table('sector_momentum').insert(sr).execute()
        except Exception as e:
            print(f"  ❌ Error storing {sr['sector']}: {e}")
    
    return {
        'sectors_analyzed': len(sector_results),
        'results': sorted(sector_results, key=lambda x: x['momentum_score'], reverse=True)
    }


if __name__ == '__main__':
    result = compute_sector_momentum()
    print(f"\n📊 SECTOR MOMENTUM RANKINGS:")
    for i, s in enumerate(result['results'][:10], 1):
        print(f"{i:2d}. {s['sector']:20s} | Score: {s['momentum_score']:3d} | Grade: {s['avg_grade']:5.1f} | 5D: {s['avg_return_5d']:+6.2f}% | BUYs: {s['buy_count']}")
