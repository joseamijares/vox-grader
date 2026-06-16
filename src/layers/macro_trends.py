"""Macro Trends integration.

Tracks key macro signals that affect portfolio decisions:
- Fed policy (rates, dot plot)
- Inflation (CPI, PCE)
- Dollar strength (DXY)
- Yield curve (10Y-2Y spread)
- Geopolitical risk index
- Commodity prices (oil, gold, copper)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

from layers.env_loader import load_env
load_env()

from sync.vox_postgres_sync import get_client


def get_macro_data() -> Dict:
    """Fetch key macro indicators from Yahoo Finance."""
    indicators = {
        'DXY': 'DX-Y.NYB',      # Dollar Index
        'TNX': '^TNX',          # 10Y Treasury
        'FVX': '^FVX',          # 5Y Treasury
        'IRX': '^IRX',          # 13W Treasury
        'VIX': '^VIX',          # Volatility
        'GOLD': 'GC=F',         # Gold futures
        'OIL': 'CL=F',          # WTI Crude
        'COPPER': 'HG=F',       # Copper
        'SPX': '^GSPC',         # S&P 500
    }
    
    results = {}
    for name, ticker in indicators.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1mo")
            if len(hist) >= 2:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change_pct = (current - prev) / prev * 100
                
                results[name] = {
                    'price': round(current, 2),
                    'change_1d_pct': round(change_pct, 2),
                    'change_5d_pct': round((current - hist['Close'].iloc[-6]) / hist['Close'].iloc[-6] * 100, 2) if len(hist) >= 6 else None,
                    'change_20d_pct': round((current - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20] * 100, 2) if len(hist) >= 20 else None,
                }
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            continue
    
    return results


def compute_macro_signals(macro_data: Dict) -> List[Dict]:
    """Convert raw macro data into directional signals."""
    signals = []
    
    # Yield curve (10Y - 2Y proxy using 10Y - 5Y)
    if 'TNX' in macro_data and 'FVX' in macro_data:
        spread = float(macro_data['TNX']['price']) - float(macro_data['FVX']['price'])
        if spread < 0:
            signals.append({
                'signal_name': 'YIELD_CURVE_INVERTED',
                'signal_value': round(float(spread), 2),
                'signal_direction': 'BEARISH',
                'impact_sector': 'Financials',
                'confidence': 75,
                'source': 'Treasury spreads'
            })
        else:
            signals.append({
                'signal_name': 'YIELD_CURVE_NORMAL',
                'signal_value': round(float(spread), 2),
                'signal_direction': 'BULLISH',
                'impact_sector': 'Financials',
                'confidence': 60,
                'source': 'Treasury spreads'
            })
    
    # VIX regime
    if 'VIX' in macro_data:
        vix = float(macro_data['VIX']['price'])
        if vix > 30:
            signals.append({
                'signal_name': 'VIX_HIGH',
                'signal_value': float(vix),
                'signal_direction': 'BEARISH',
                'impact_sector': 'All',
                'confidence': 80,
                'source': 'VIX'
            })
        elif vix < 15:
            signals.append({
                'signal_name': 'VIX_LOW',
                'signal_value': float(vix),
                'signal_direction': 'BULLISH',
                'impact_sector': 'All',
                'confidence': 65,
                'source': 'VIX'
            })
    
    # Dollar strength
    if 'DXY' in macro_data:
        dxy = float(macro_data['DXY']['price'])
        dxy_5d = float(macro_data['DXY'].get('change_5d_pct', 0))
        if dxy_5d > 1:
            signals.append({
                'signal_name': 'DOLLAR_STRENGTHENING',
                'signal_value': float(dxy),
                'signal_direction': 'BEARISH',
                'impact_sector': 'Emerging Markets',
                'confidence': 70,
                'source': 'DXY'
            })
        elif dxy_5d < -1:
            signals.append({
                'signal_name': 'DOLLAR_WEAKENING',
                'signal_value': float(dxy),
                'signal_direction': 'BULLISH',
                'impact_sector': 'Emerging Markets',
                'confidence': 70,
                'source': 'DXY'
            })
    
    # Oil prices
    if 'OIL' in macro_data:
        oil = float(macro_data['OIL']['price'])
        if oil > 85:
            signals.append({
                'signal_name': 'OIL_HIGH',
                'signal_value': float(oil),
                'signal_direction': 'BEARISH',
                'impact_sector': 'Energy',
                'confidence': 65,
                'source': 'Oil'
            })
        elif oil < 65:
            signals.append({
                'signal_name': 'OIL_LOW',
                'signal_value': float(oil),
                'signal_direction': 'BULLISH',
                'impact_sector': 'Energy',
                'confidence': 60,
                'source': 'Oil'
            })
    
    # AI-Demand Energy Thesis — Nuclear + Data Center Power
    # AI data centers need 2-3x more power than traditional data centers
    # Current grid cannot supply this demand
    # Nuclear is the only clean baseload option (24/7, not weather-dependent)
    # Tech companies (Microsoft, Google, Amazon) signing nuclear deals
    # This is a structural shift, not a cyclical one
    signals.append({
        'signal_name': 'AI_DEMAND_ENERGY',
        'signal_value': 85,  # High conviction structural thesis
        'signal_direction': 'BULLISH',
        'impact_sector': 'Utilities',  # Nuclear utilities like CEG
        'confidence': 85,
        'source': 'AI-Demand Macro Thesis'
    })
    signals.append({
        'signal_name': 'AI_DEMAND_NUCLEAR',
        'signal_value': 90,  # Even higher conviction for pure nuclear plays
        'signal_direction': 'BULLISH',
        'impact_sector': 'Industrials',  # Nuclear microreactors (OKLO, SMR, NNE, BWXT)
        'confidence': 90,
        'source': 'AI-Demand Nuclear Thesis'
    })
    
    # Gold as safe haven
    if 'GLD' in macro_data:
        gld = float(macro_data['GLD']['price'])
        gld_5d = float(macro_data['GLD'].get('change_5d_pct', 0))
        if gld_5d > 2:
            signals.append({
                'signal_name': 'GOLD_RALLY',
                'signal_value': float(gld),
                'signal_direction': 'NEUTRAL',
                'impact_sector': 'All',
                'confidence': 55,
                'source': 'Gold'
            })
    
    return signals


def run_macro_scan() -> Dict:
    """Run full macro scan and store results."""
    from sync.vox_postgres_sync import get_client
    sb = get_client()
    
    print("Fetching macro data...")
    macro_data = get_macro_data()
    
    print("Computing macro signals...")
    signals = compute_macro_signals(macro_data)
    
    # Store in Postgres
    
    print(f"Storing {len(signals)} macro signals...")
    stored = 0
    for s in signals:
        s['computed_at'] = datetime.now().isoformat()
        try:
            existing = sb.table('macro_signals').select('id').eq('signal_name', s['signal_name']).execute()
            if existing.data:
                sb.table('macro_signals').update(s).eq('signal_name', s['signal_name']).execute()
            else:
                sb.table('macro_signals').insert(s).execute()
            stored += 1
        except Exception as e:
            print(f"  ❌ Error storing {s['signal_name']}: {e}")
    
    return {
        'macro_data': macro_data,
        'signals': signals,
        'stored': stored
    }


if __name__ == '__main__':
    result = run_macro_scan()
    
    print("\n📊 MACRO DATA:")
    for name, data in result['macro_data'].items():
        print(f"  {name:10s}: ${data['price']:>10.2f} (1D: {data['change_1d_pct']:+6.2f}%)")
    
    print("\n🌍 MACRO SIGNALS:")
    for s in result['signals']:
        emoji = "🟢" if s['signal_direction'] == 'BULLISH' else "🔴" if s['signal_direction'] == 'BEARISH' else "🟡"
        print(f"  {emoji} {s['signal_name']:25s} | {s['signal_direction']:10s} | Impact: {s['impact_sector']:20s} | Conf: {s['confidence']}%")
