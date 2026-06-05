"""Unified 6-Layer Scanner.

Combines all 6 intelligence layers into a single scoring system:
1. Portfolio Analysis
2. Famous Traders
3. Supply Chain Sectors
4. Weather Patterns
5. Macro Trends
6. Alpha Zoo Technical

Outputs: Cross-layer conviction scores with full reasoning.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from typing import Dict, List
from datetime import datetime

with open(os.path.expanduser('~/dev/vox-python/.env'), 'r') as f:
    for line in f:
        if line.startswith('SUPABASE_KEY='):
            os.environ['SUPABASE_KEY'] = line.strip().split('=', 1)[1]

from sync.vox_postgres_sync import get_client


def load_all_layers(sb_client) -> Dict:
    """Load data from all 6 layers."""
    
    # Layer 1: Portfolio
    positions = sb_client.table('positions').select('*').execute().data
    portfolio_tickers = {p['ticker'] for p in positions}
    
    # Layer 2: Famous Traders
    watchlist = sb_client.table('watchlist').select('*').execute().data
    famous_traders = [w for w in watchlist if w.get('sector') == 'Famous Traders']
    
    # Layer 3: Sector Momentum
    try:
        sector_mom = sb_client.table('sector_momentum').select('*').execute().data
    except:
        sector_mom = []
    
    # Layer 4: Weather
    try:
        weather = sb_client.table('weather_patterns').select('*').execute().data
    except:
        weather = []
    
    # Layer 5: Macro
    try:
        macro = sb_client.table('macro_signals').select('*').execute().data
    except:
        macro = []
    
    # Layer 6: Alpha Zoo
    try:
        alpha = sb_client.table('technical_signals').select('*').execute().data
    except:
        alpha = []
    
    return {
        'positions': positions,
        'portfolio_tickers': portfolio_tickers,
        'watchlist': watchlist,
        'famous_traders': famous_traders,
        'sector_momentum': sector_mom,
        'weather': weather,
        'macro': macro,
        'alpha_zoo': alpha
    }


def score_candidate(ticker: str, layers: Dict) -> Dict:
    """Score a single ticker across all 6 layers."""
    scores = {
        'ticker': ticker,
        'layers': {},
        'layer_count': 0,
        'conviction_score': 0,
        'reasoning': []
    }
    
    # Layer 1: Portfolio Analysis
    pos = next((p for p in layers['positions'] if p['ticker'] == ticker), None)
    if pos:
        scores['layers']['portfolio'] = {
            'held': True,
            'value': pos.get('live_value', 0),
            'grade': pos.get('grade', 0),
            'weight': 0.2
        }
        if pos.get('live_value', 0) > 5000 and (pos.get('grade', 0) or 0) < 55:
            scores['reasoning'].append(f"Portfolio gap: Large position (${pos['live_value']:,.0f}) with low grade ({pos.get('grade')})")
            scores['layer_count'] += 1
    else:
        scores['layers']['portfolio'] = {'held': False, 'weight': 0.2}
    
    # Layer 2: Famous Traders
    ft = next((w for w in layers['famous_traders'] if w['ticker'] == ticker), None)
    if ft:
        scores['layers']['famous_trader'] = {
            'present': True,
            'grade': ft.get('grade', 0),
            'council': ft.get('council'),
            'weight': 0.25
        }
        scores['reasoning'].append(f"Famous Trader pick: Grade {ft.get('grade')}, Council {ft.get('council')}")
        scores['layer_count'] += 1
    
    # Layer 3: Sector Momentum
    wl_item = next((w for w in layers['watchlist'] if w['ticker'] == ticker), None)
    if wl_item and wl_item.get('sector'):
        sector = wl_item['sector']
        sm = next((s for s in layers['sector_momentum'] if s['sector'] == sector), None)
        if sm:
            scores['layers']['sector'] = {
                'sector': sector,
                'momentum_score': sm.get('momentum_score', 0),
                'avg_return_5d': sm.get('avg_return_5d', 0),
                'weight': 0.15
            }
            if sm.get('momentum_score', 0) >= 60:
                scores['reasoning'].append(f"Strong sector momentum: {sector} (score {sm['momentum_score']})")
                scores['layer_count'] += 1
    
    # Layer 4: Weather
    weather_hits = [w for w in layers['weather'] if ticker in w.get('affected_tickers', [])]
    if weather_hits:
        scores['layers']['weather'] = {
            'patterns': [w['pattern_type'] for w in weather_hits],
            'severity': max(w.get('severity', 1) for w in weather_hits),
            'weight': 0.1
        }
        scores['reasoning'].append(f"Weather impact: {', '.join(scores['layers']['weather']['patterns'])}")
        scores['layer_count'] += 1
    
    # Layer 5: Macro
    if wl_item and wl_item.get('sector'):
        sector = wl_item['sector']
        macro_hits = [m for m in layers['macro'] if m.get('impact_sector') == sector or m.get('impact_sector') == 'All']
        if macro_hits:
            scores['layers']['macro'] = {
                'signals': [m['signal_name'] for m in macro_hits],
                'direction': macro_hits[0].get('signal_direction'),
                'weight': 0.15
            }
            scores['reasoning'].append(f"Macro alignment: {', '.join(scores['layers']['macro']['signals'][:2])}")
            scores['layer_count'] += 1
    
    # Layer 6: Alpha Zoo
    az = next((a for a in layers['alpha_zoo'] if a['ticker'] == ticker), None)
    if az:
        scores['layers']['alpha_zoo'] = {
            'score': az.get('score', 50),
            'alpha_score': az.get('alpha_zoo_score'),
            'factor_count': az.get('alpha_factor_count', 0),
            'mean_reversion': az.get('mean_reversion_signals', []),
            'weight': 0.25
        }
        if az.get('score', 0) >= 65:
            scores['reasoning'].append(f"Alpha Zoo bullish: Score {az['score']}, {az.get('alpha_factor_count', 0)} factors")
            scores['layer_count'] += 1
        elif az.get('mean_reversion_signals'):
            scores['reasoning'].append(f"Mean reversion signals: {', '.join(az['mean_reversion_signals'][:3])}")
            scores['layer_count'] += 1
    
    # Calculate conviction score
    weighted_sum = 0
    total_weight = 0
    
    for layer_name, layer_data in scores['layers'].items():
        if layer_name == 'portfolio' and not layer_data.get('held'):
            continue
        if layer_name == 'famous_trader' and not layer_data.get('present'):
            continue
        
        weight = layer_data.get('weight', 0.1)
        
        if layer_name == 'portfolio':
            score = layer_data.get('grade', 50)
        elif layer_name == 'famous_trader':
            score = layer_data.get('grade', 50)
        elif layer_name == 'sector':
            score = layer_data.get('momentum_score', 50)
        elif layer_name == 'weather':
            score = 50  # Neutral, just flags risk
        elif layer_name == 'macro':
            score = 70 if layer_data.get('direction') == 'BULLISH' else 30 if layer_data.get('direction') == 'BEARISH' else 50
        elif layer_name == 'alpha_zoo':
            score = layer_data.get('score', 50)
        else:
            score = 50
        
        weighted_sum += score * weight
        total_weight += weight
    
    if total_weight > 0:
        scores['conviction_score'] = int(weighted_sum / total_weight)
    else:
        scores['conviction_score'] = 50
    
    return scores


def run_unified_scan() -> Dict:
    """Run full 6-layer unified scan."""
    
    print("=" * 70)
    print("VOX 6-LAYER UNIFIED SCAN")
    print("=" * 70)
    
    print("\nLoading all intelligence layers...")
    layers = load_all_layers(sb)
    print(f"  Portfolio: {len(layers['positions'])} positions")
    print(f"  Watchlist: {len(layers['watchlist'])} items")
    print(f"  Famous Traders: {len(layers['famous_traders'])} picks")
    print(f"  Sector Momentum: {len(layers['sector_momentum'])} sectors")
    print(f"  Weather Patterns: {len(layers['weather'])} active")
    print(f"  Macro Signals: {len(layers['macro'])} signals")
    print(f"  Alpha Zoo: {len(layers['alpha_zoo'])} computed")
    
    # Score all candidates (not in portfolio or in portfolio with gaps)
    candidates = []
    
    # All watchlist items not in portfolio
    for w in layers['watchlist']:
        if w['ticker'] not in layers['portfolio_tickers']:
            candidates.append(w['ticker'])
    
    # Portfolio items with low grades
    for p in layers['positions']:
        if (p.get('grade', 0) or 0) < 55:
            candidates.append(p['ticker'])
    
    candidates = list(set(candidates))
    print(f"\nScoring {len(candidates)} candidates...")
    
    results = []
    for i, ticker in enumerate(candidates):
        result = score_candidate(ticker, layers)
        results.append(result)
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(candidates)}")
    
    # Sort by conviction score and layer count
    results.sort(key=lambda x: (-x['layer_count'], -x['conviction_score']))
    
    return {
        'candidates_scored': len(results),
        'layers_loaded': {
            'portfolio': len(layers['positions']),
            'watchlist': len(layers['watchlist']),
            'famous_traders': len(layers['famous_traders']),
            'sector_momentum': len(layers['sector_momentum']),
            'weather': len(layers['weather']),
            'macro': len(layers['macro']),
            'alpha_zoo': len(layers['alpha_zoo'])
        },
        'top_candidates': results[:30]
    }


if __name__ == '__main__':
    result = run_unified_scan()
    
    print("\n" + "=" * 70)
    print("TOP 20 HIGHEST-CONVICTION PLAYS")
    print("=" * 70)
    
    for i, r in enumerate(result['top_candidates'][:20], 1):
        layers_hit = ', '.join(r['layers'].keys())
        reasoning = ' | '.join(r['reasoning'][:3])
        print(f"\n{i:2d}. {r['ticker']:8s} | Conviction: {r['conviction_score']:3d} | Layers: {r['layer_count']} ({layers_hit})")
        print(f"     Reasoning: {reasoning}")
