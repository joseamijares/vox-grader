"""Integrated 6-Layer Grading Pipeline.

Runs all intelligence layers and integrates them into the grading engine.
Called by the Railway grader service after broker sync.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from typing import Dict, List
from datetime import datetime
import json

from sync.vox_postgres_sync import get_positions, get_watchlist, update_position, save_vox_grade
from grading.engine import calculate_grade

# Import layer modules
from layers.macro_trends import get_macro_data, compute_macro_signals
from layers.sector_momentum import compute_sector_momentum
from layers.weather_patterns import get_noaa_active_alerts, classify_weather_impact


def run_macro_layer() -> List[Dict]:
    """Run macro trends layer. Returns macro signals."""
    print("📊 Running Macro Trends layer...")
    try:
        macro_data = get_macro_data()
        signals = compute_macro_signals(macro_data)
        print(f"  ✅ {len(signals)} macro signals generated")
        return signals
    except Exception as e:
        print(f"  ❌ Macro layer error: {e}")
        return []


def run_sector_layer() -> List[Dict]:
    """Run sector momentum layer. Returns sector scores."""
    print("🏭 Running Sector Momentum layer...")
    try:
        # Use the unified scanner's approach but simplified
        from sync.vox_postgres_sync import query
        
        # Get all tickers with sectors
        positions = get_positions()
        watchlist = get_watchlist()
        
        all_items = positions + watchlist
        
        from collections import defaultdict
        sector_tickers = defaultdict(list)
        sector_grades = defaultdict(list)
        
        for item in all_items:
            sector = item.get('sector') or 'Uncategorized'
            ticker = item['ticker']
            sector_tickers[sector].append(ticker)
            if item.get('grade'):
                sector_grades[sector].append(int(item['grade']))
        
        sector_results = []
        for sector, tickers in sector_tickers.items():
            unique_tickers = list(set(tickers))
            grades = sector_grades.get(sector, [])
            
            avg_grade = sum(grades) / len(grades) if grades else 50
            
            # Count signals
            buy_count = sum(1 for t in unique_tickers if any(
                (w.get('council') or '').startswith('BUY') for w in watchlist if w['ticker'] == t
            ))
            sell_count = sum(1 for t in unique_tickers if any(
                (w.get('council') or '').startswith('SELL') for w in watchlist if w['ticker'] == t
            ))
            
            momentum_score = min(100, max(0, int(avg_grade + (buy_count - sell_count) * 5)))
            
            sector_results.append({
                'sector': sector,
                'momentum_score': momentum_score,
                'ticker_count': len(unique_tickers),
                'avg_grade': round(avg_grade, 1),
                'buy_signals': buy_count,
                'sell_signals': sell_count
            })
        
        print(f"  ✅ {len(sector_results)} sectors analyzed")
        return sector_results
    except Exception as e:
        print(f"  ❌ Sector layer error: {e}")
        return []


def run_weather_layer() -> List[Dict]:
    """Run weather patterns layer. Returns weather impacts."""
    print("🌪️  Running Weather Patterns layer...")
    try:
        alerts = get_noaa_active_alerts()
        patterns = classify_weather_impact(alerts)
        print(f"  ✅ {len(patterns)} weather patterns detected")
        return patterns
    except Exception as e:
        print(f"  ❌ Weather layer error: {e}")
        return []


def get_layer_scores(ticker: str, sector: str, 
                     macro_signals: List[Dict],
                     sector_momentum: List[Dict],
                     weather_patterns: List[Dict]) -> Dict:
    """Get layer scores for a specific ticker."""
    
    # Macro score (0-100)
    macro_score = 50
    macro_reasoning = []
    for signal in macro_signals:
        direction = signal.get('signal_direction', 'NEUTRAL')
        impact_sector = signal.get('impact_sector', 'All')
        
        if impact_sector == 'All' or impact_sector == sector:
            if direction == 'BULLISH':
                macro_score += 10
                macro_reasoning.append(f"Bullish macro: {signal['signal_name']}")
            elif direction == 'BEARISH':
                macro_score -= 10
                macro_reasoning.append(f"Bearish macro: {signal['signal_name']}")
    macro_score = max(0, min(100, macro_score))
    
    # Sector score (0-100)
    sector_score = 50
    sector_data = next((s for s in sector_momentum if s['sector'] == sector), None)
    if sector_data:
        sector_score = sector_data.get('momentum_score', 50)
    
    # Weather score (0-100, default 70 = neutral/slight positive)
    weather_score = 70
    weather_hits = [w for w in weather_patterns if sector in w.get('affected_sectors', [])]
    if weather_hits:
        max_severity = max(w.get('severity', 1) for w in weather_hits)
        weather_score = max(0, 70 - max_severity * 10)
    
    return {
        'macro_score': macro_score,
        'sector_score': sector_score,
        'weather_score': weather_score,
        'macro_reasoning': macro_reasoning
    }


def integrated_grade_all():
    """Run full integrated grading on all positions and watchlist."""
    print("=" * 70)
    print("VOX INTEGRATED 6-LAYER GRADING PIPELINE")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Run all layers
    macro_signals = run_macro_layer()
    sector_momentum = run_sector_layer()
    weather_patterns = run_weather_layer()
    
    print()
    
    # Step 2: Get all items to grade
    positions = get_positions()
    watchlist = get_watchlist()
    
    # Combine unique tickers
    all_tickers = {}
    for p in positions:
        all_tickers[p['ticker']] = {'type': 'position', 'data': p}
    for w in watchlist:
        if w['ticker'] not in all_tickers:
            all_tickers[w['ticker']] = {'type': 'watchlist', 'data': w}
    
    print(f"🎯 Grading {len(all_tickers)} unique tickers...")
    print()
    
    graded = 0
    errors = 0
    
    for ticker, info in all_tickers.items():
        try:
            # Get base grade from engine (technical + fundamental)
            base_result = calculate_grade(ticker)
            
            # Get sector
            sector = base_result.sector or info['data'].get('sector', 'Technology')
            
            # Get layer scores
            layer_scores = get_layer_scores(ticker, sector, macro_signals, sector_momentum, weather_patterns)
            
            # Calculate integrated grade with layer weights
            # Technical: 25%, Fundamental: 25%, Macro: 15%, Sector: 15%, Weather: 10%, Sentiment: 10%
            integrated_grade = int(
                base_result.technical_score * 0.25 +
                base_result.fundamental_score * 0.25 +
                layer_scores['macro_score'] * 0.15 +
                layer_scores['sector_score'] * 0.15 +
                layer_scores['weather_score'] * 0.10 +
                base_result.sentiment_score * 0.10  # Still placeholder until sentiment layer
            )
            
            # Determine council
            from grading.engine import grade_to_council
            council = grade_to_council(integrated_grade)
            
            # Update position/watchlist
            update_data = {
                'grade': integrated_grade,
                'council': council,
                'sector': sector
            }
            
            if info['type'] == 'position':
                update_position(ticker, update_data)
            
            # Save detailed grade
            save_vox_grade({
                'ticker': ticker,
                'name': base_result.name or ticker,
                'vox_grade': integrated_grade,
                'previous_grade': info['data'].get('grade', 0) or 0,
                'action': council,
                'current_price': info['data'].get('live_price', 0),
                'stop_loss': info['data'].get('live_price', 0) * 0.85 if info['data'].get('live_price') else 0,
                'entry_point': info['data'].get('live_price', 0) * 0.95 if info['data'].get('live_price') else 0,
                'position_value': info['data'].get('live_value', 0),
                'shares': info['data'].get('shares', 0),
                'technical_score': base_result.technical_score,
                'fundamental_score': base_result.fundamental_score,
                'macro_score': layer_scores['macro_score'],
                'sector_score': layer_scores['sector_score'],
                'weather_score': layer_scores['weather_score'],
                'sentiment_score': base_result.sentiment_score,
                'catalysts': '; '.join(base_result.factors.get('technical', {}).get('mean_reversion_signals', [])[:3]),
                'weather_factors': '; '.join(layer_scores['macro_reasoning'][:2]) or 'Neutral macro environment'
            })
            
            if (graded + 1) % 50 == 0:
                print(f"  Progress: {graded + 1}/{len(all_tickers)}")
            
            graded += 1
            
        except Exception as e:
            print(f"  ❌ {ticker}: {e}")
            errors += 1
    
    print()
    print("=" * 70)
    print(f"✅ Graded: {graded} | ❌ Errors: {errors}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    return {'graded': graded, 'errors': errors}


if __name__ == '__main__':
    integrated_grade_all()
