"""Weather Patterns tracker.

Tracks weather events that impact commodity/agriculture/energy sectors:
- Hurricane season (Gulf energy production)
- Droughts (agriculture, water utilities)
- Cold snaps (natural gas demand)
- Heat waves (energy demand, agriculture)
- Flooding (supply chain disruption)

Uses NOAA data and correlates with portfolio sectors.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta

from layers.env_loader import load_env
load_env()

from sync.vox_postgres_sync import get_client


def get_noaa_active_alerts() -> List[Dict]:
    """Fetch active weather alerts from NOAA."""
    try:
        url = "https://api.weather.gov/alerts/active"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            alerts = data.get('features', [])
            
            # Filter for high-impact events
            high_impact = []
            for alert in alerts:
                props = alert.get('properties', {})
                event = props.get('event', '')
                severity = props.get('severity', '')
                
                if severity in ['Extreme', 'Severe'] and any(x in event for x in ['Hurricane', 'Tornado', 'Flood', 'Drought', 'Heat', 'Winter Storm', 'Blizzard']):
                    high_impact.append({
                        'event': event,
                        'severity': severity,
                        'area': props.get('areaDesc', 'Unknown'),
                        'headline': props.get('headline', ''),
                        'effective': props.get('effective', ''),
                        'expires': props.get('expires', '')
                    })
            
            return high_impact
    except Exception as e:
        print(f"  ❌ NOAA error: {e}")
    
    return []


def classify_weather_impact(alerts: List[Dict]) -> List[Dict]:
    """Classify weather alerts by sector impact."""
    patterns = []
    
    for alert in alerts:
        event = alert['event'].lower()
        
        if 'hurricane' in event or 'tropical storm' in event:
            patterns.append({
                'region': alert['area'],
                'pattern_type': 'HURRICANE',
                'severity': 5 if 'hurricane' in event else 3,
                'affected_sectors': ['Energy', 'Materials', 'Insurance'],
                'affected_tickers': [],  # Would map from portfolio
                'start_date': alert['effective'][:10] if alert['effective'] else None,
                'end_date': alert['expires'][:10] if alert['expires'] else None,
            })
        
        elif 'drought' in event:
            patterns.append({
                'region': alert['area'],
                'pattern_type': 'DROUGHT',
                'severity': 4,
                'affected_sectors': ['Agriculture', 'Materials', 'Consumer Staples'],
                'affected_tickers': [],
                'start_date': alert['effective'][:10] if alert['effective'] else None,
                'end_date': alert['expires'][:10] if alert['expires'] else None,
            })
        
        elif 'heat' in event or 'excessive heat' in event:
            patterns.append({
                'region': alert['area'],
                'pattern_type': 'HEAT_WAVE',
                'severity': 3,
                'affected_sectors': ['Energy', 'Utilities', 'Agriculture'],
                'affected_tickers': [],
                'start_date': alert['effective'][:10] if alert['effective'] else None,
                'end_date': alert['expires'][:10] if alert['expires'] else None,
            })
        
        elif 'flood' in event:
            patterns.append({
                'region': alert['area'],
                'pattern_type': 'FLOODING',
                'severity': 4,
                'affected_sectors': ['Materials', 'Insurance', 'Transportation'],
                'affected_tickers': [],
                'start_date': alert['effective'][:10] if alert['effective'] else None,
                'end_date': alert['expires'][:10] if alert['expires'] else None,
            })
        
        elif 'winter storm' in event or 'blizzard' in event:
            patterns.append({
                'region': alert['area'],
                'pattern_type': 'COLD_SNAP',
                'severity': 4,
                'affected_sectors': ['Energy', 'Utilities', 'Transportation'],
                'affected_tickers': [],
                'start_date': alert['effective'][:10] if alert['effective'] else None,
                'end_date': alert['expires'][:10] if alert['expires'] else None,
            })
    
    return patterns


def map_tickers_to_weather(sb_client, patterns: List[Dict]) -> List[Dict]:
    """Map portfolio/watchlist tickers to weather patterns by sector."""
    # Get all tickers with sectors
    pos = sb_client.table('positions').select('ticker,sector').execute().data
    watch = sb_client.table('watchlist').select('ticker,sector').execute().data
    
    all_tickers = {}
    for item in pos + watch:
        if item.get('sector'):
            all_tickers[item['ticker']] = item['sector']
    
    # Map tickers to patterns
    for pattern in patterns:
        affected = []
        for ticker, sector in all_tickers.items():
            if sector in pattern['affected_sectors']:
                affected.append(ticker)
        pattern['affected_tickers'] = affected[:10]  # Limit to 10
    
    return patterns


def run_weather_scan() -> Dict:
    """Run full weather pattern scan."""
    from sync.vox_postgres_sync import get_client
    sb = get_client()
    
    print("Fetching NOAA weather alerts...")
    alerts = get_noaa_active_alerts()
    print(f"  Found {len(alerts)} high-impact alerts")
    
    print("Classifying weather impacts...")
    patterns = classify_weather_impact(alerts)
    
    # Map to tickers
    patterns = map_tickers_to_weather(sb, patterns)
    
    # Store in Postgres
    print(f"Storing {len(patterns)} weather patterns...")
    for p in patterns:
        p['computed_at'] = datetime.now().isoformat()
        try:
            sb.table('weather_patterns').insert(p).execute()
        except Exception as e:
            print(f"  ❌ Error storing pattern: {e}")
    
    return {
        'alerts_found': len(alerts),
        'patterns': patterns
    }


if __name__ == '__main__':
    result = run_weather_scan()
    
    print(f"\n🌪️ WEATHER PATTERNS ({len(result['patterns'])} active):")
    for p in result['patterns']:
        emoji = {"HURRICANE": "🌀", "DROUGHT": "🏜️", "HEAT_WAVE": "🔥", "FLOODING": "🌊", "COLD_SNAP": "❄️"}.get(p['pattern_type'], "⚠️")
        tickers = ', '.join(p['affected_tickers'][:5]) if p['affected_tickers'] else 'None'
        print(f"  {emoji} {p['pattern_type']:15s} | Severity: {p['severity']}/5 | Sectors: {', '.join(p['affected_sectors'][:3])} | Tickers: {tickers}")
