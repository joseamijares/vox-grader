"""Alpha Zoo live runner — computes 452-factor technical scores for all tickers."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from grading.technical import score_technical, get_alpha_zoo_summary

# Supabase setup
with open(os.path.expanduser('~/dev/vox-python/.env'), 'r') as f:
    for line in f:
        if line.startswith('SUPABASE_KEY='):
            os.environ['SUPABASE_KEY'] = line.strip().split('=', 1)[1]

from sync.vox_postgres_sync import get_client

def run_alpha_zoo_scan(tickers: List[str]) -> Dict:
    """Run full Alpha Zoo 452-factor scan on tickers. Store results in Supabase."""
    
    results = []
    print(f"Running Alpha Zoo scan on {len(tickers)} tickers...")
    
    for i, ticker in enumerate(tickers):
        try:
            result = score_technical(ticker, use_alpha_zoo=True)
            results.append({
                'ticker': ticker,
                'score': result['score'],
                'rsi': result.get('rsi'),
                'macd_bullish': result.get('macd_bullish'),
                'trend': result.get('trend'),
                'volume_trend': result.get('volume_trend'),
                'alpha_zoo_enabled': result.get('alpha_zoo_enabled', False),
                'alpha_zoo_score': result.get('alpha_zoo_score'),
                'alpha_factor_count': result.get('alpha_factor_count', 0),
                'mean_reversion_signals': result.get('mean_reversion_signals', []),
                'top_factors': result.get('top_factors', {}),
                'computed_at': datetime.now().isoformat()
            })
            
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(tickers)}")
                
        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
            results.append({
                'ticker': ticker,
                'score': 50,
                'alpha_zoo_enabled': False,
                'alpha_factor_count': 0,
                'mean_reversion_signals': [],
                'top_factors': {},
                'computed_at': datetime.now().isoformat()
            })
    
    # Store in Supabase (upsert)
    print(f"\nStoring {len(results)} results in Supabase...")
    stored = 0
    for r in results:
        try:
            # Check if exists
            existing = sb.table('technical_signals').select('id').eq('ticker', r['ticker']).execute()
            if existing.data:
                # Update
                sb.table('technical_signals').update(r).eq('ticker', r['ticker']).execute()
            else:
                # Insert
                sb.table('technical_signals').insert(r).execute()
            stored += 1
        except Exception as e:
            print(f"  ❌ Store error for {r['ticker']}: {e}")
    
    print(f"✅ Stored {stored}/{len(results)} technical signals")
    
    return {
        'scanned': len(tickers),
        'stored': stored,
        'results': results
    }


if __name__ == '__main__':
    # Get all tickers from positions + watchlist
    
    pos = sb.table('positions').select('ticker').execute()
    watch = sb.table('watchlist').select('ticker').execute()
    
    all_tickers = list(set([p['ticker'] for p in pos.data] + [w['ticker'] for w in watch.data]))
    print(f"Total unique tickers: {len(all_tickers)}")
    
    result = run_alpha_zoo_scan(all_tickers)
    
    # Print top 20
    sorted_results = sorted(result['results'], key=lambda x: x['score'], reverse=True)
    print("\n🏆 TOP 20 ALPHA ZOO SCORES:")
    for i, r in enumerate(sorted_results[:20], 1):
        signals = ', '.join(r['mean_reversion_signals'][:3]) if r['mean_reversion_signals'] else 'None'
        print(f"{i:2d}. {r['ticker']:8s} Score: {r['score']:3d} | Alpha: {r['alpha_zoo_score'] or 'N/A':>3} | Factors: {r['alpha_factor_count']:3d} | Signals: {signals}")
