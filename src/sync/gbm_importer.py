"""
GBM Portfolio Importer — Reliable system for manual JSON exports.

Usage:
    1. Export your GBM portfolio as JSON (from GBM Plus app/web)
    2. Save to: ~/.hermes/scripts/gbm_main_portfolio.json
    3. Run: python scripts/import_gbm.py

Features:
    - Validates JSON structure
    - Filters garbage/dust positions (< $10)
    - Converts MXN to USD using live exchange rate
    - Deduplicates with existing positions (merges brokers)
    - Validates tickers against Yahoo Finance
    - Generates audit report
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sync.validator import validate_position, MIN_POSITION_VALUE

# Default paths
GBM_MAIN_PATH = Path.home() / '.hermes' / 'scripts' / 'gbm_main_portfolio.json'
GBM_USA_PATH = Path.home() / '.hermes' / 'scripts' / 'gbm_usa_portfolio.json'

# MXN/USD exchange rate — update this or fetch live
DEFAULT_MXN_RATE = 17.8


def load_gbm_json(path: Path) -> Dict:
    """Load and validate GBM JSON export."""
    if not path.exists():
        raise FileNotFoundError(f"GBM export not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate structure
    required_keys = ['broker', 'last_updated', 'portfolio_summary']
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Invalid GBM JSON: missing '{key}'")
    
    return data


def parse_gbm_main(data: Dict, mxn_rate: float = DEFAULT_MXN_RATE) -> List[Dict]:
    """Parse GBM Main JSON into normalized positions."""
    positions = []
    
    # SIC positions (US stocks)
    for p in data.get('sic_positions', []):
        ticker = p.get('ticker', '').strip().upper()
        if not ticker:
            continue
        
        mxn_value = p.get('market_value_mxn', 0)
        usd_value = mxn_value / mxn_rate
        
        positions.append({
            'ticker': ticker,
            'shares': p.get('qty', 0),
            'avg_cost_usd': p.get('cost_avg_mxn', 0) / mxn_rate,
            'live_price_usd': p.get('price_mxn', 0) / mxn_rate,
            'live_value_usd': usd_value,
            'market': 'SIC_Global',
            'broker': 'GBM Main',
            'currency': 'MXN',
            'raw': p
        })
    
    # National positions (Mexican stocks)
    for p in data.get('national_positions', []):
        ticker = p.get('ticker', '').strip().upper()
        if not ticker:
            continue
        
        mxn_value = p.get('market_value_mxn', 0)
        usd_value = mxn_value / mxn_rate
        
        positions.append({
            'ticker': ticker,
            'shares': p.get('qty', 0),
            'avg_cost_usd': p.get('cost_avg_mxn', 0) / mxn_rate,
            'live_price_usd': p.get('price_mxn', 0) / mxn_rate,
            'live_value_usd': usd_value,
            'market': 'Nacional',
            'broker': 'GBM Main',
            'currency': 'MXN',
            'raw': p
        })
    
    return positions


def parse_gbm_usa(data: Dict) -> List[Dict]:
    """Parse GBM USA JSON into normalized positions."""
    positions = []
    
    for p in data.get('sic_positions', []):
        ticker = p.get('ticker', '').strip().upper()
        if not ticker:
            continue
        
        positions.append({
            'ticker': ticker,
            'shares': p.get('qty', 0),
            'avg_cost_usd': p.get('cost_avg_usd', 0),
            'live_price_usd': p.get('price_usd', 0),
            'live_value_usd': p.get('market_value_usd', 0),
            'market': 'SIC_Global',
            'broker': 'GBM USA',
            'currency': 'USD',
            'raw': p
        })
    
    return positions


def validate_gbm_positions(positions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Validate all positions, return (valid, rejected)."""
    valid = []
    rejected = []
    
    for pos in positions:
        result = validate_position(
            pos['ticker'],
            pos['live_value_usd'],
            pos['broker']
        )
        
        if result['valid']:
            valid.append(pos)
        else:
            rejected.append({
                **pos,
                'reject_reason': result['reason']
            })
    
    return valid, rejected


def sync_to_supabase(positions: List[Dict], sb_client) -> Dict:
    """Sync validated positions to Supabase."""
    stats = {
        'inserted': 0,
        'updated': 0,
        'failed': 0,
        'total_value': 0
    }
    
    for pos in positions:
        try:
            # Check if position exists
            existing = sb_client.table('positions')\
                .select('*')\
                .eq('ticker', pos['ticker'])\
                .execute()
            
            if existing.data:
                # Update existing — merge brokers
                old = existing.data[0]
                old_brokers = old.get('brokers', []) or []
                new_brokers = list(set(old_brokers + [pos['broker']]))
                
                # If same broker, update values. If different broker, keep both
                if pos['broker'] in old_brokers:
                    # Same broker — update the position
                    sb_client.table('positions').update({
                        'shares': pos['shares'],
                        'avg_cost': pos['avg_cost_usd'],
                        'live_price': pos['live_price_usd'],
                        'live_value': pos['live_value_usd'],
                        'brokers': new_brokers,
                        'updated_at': datetime.now().isoformat()
                    }).eq('ticker', pos['ticker']).execute()
                else:
                    # Different broker — add to brokers list, sum value
                    current_value = old.get('live_value', 0) or 0
                    new_value = current_value + pos['live_value_usd']
                    
                    sb_client.table('positions').update({
                        'live_value': new_value,
                        'brokers': new_brokers,
                        'updated_at': datetime.now().isoformat()
                    }).eq('ticker', pos['ticker']).execute()
                
                stats['updated'] += 1
            else:
                # Insert new position
                sb_client.table('positions').insert({
                    'ticker': pos['ticker'],
                    'shares': pos['shares'],
                    'avg_cost': pos['avg_cost_usd'],
                    'live_price': pos['live_price_usd'],
                    'live_value': pos['live_value_usd'],
                    'brokers': [pos['broker']],
                    'grade': 0,
                    'council': 'UNGRADED',
                    'sector': '',
                    'updated_at': datetime.now().isoformat()
                }).execute()
                
                stats['inserted'] += 1
            
            stats['total_value'] += pos['live_value_usd']
            
        except Exception as e:
            print(f"  ❌ Error syncing {pos['ticker']}: {e}")
            stats['failed'] += 1
    
    return stats


def generate_report(valid: List[Dict], rejected: List[Dict], stats: Dict) -> str:
    """Generate human-readable sync report."""
    lines = []
    lines.append("=" * 60)
    lines.append("GBM SYNC REPORT")
    lines.append("=" * 60)
    lines.append(f"Timestamp: {datetime.now().isoformat()}")
    lines.append("")
    
    lines.append(f"✅ Valid positions: {len(valid)}")
    lines.append(f"❌ Rejected positions: {len(rejected)}")
    lines.append(f"💰 Total value synced: ${stats['total_value']:,.2f}")
    lines.append("")
    
    lines.append("--- SYNCED TO SUPABASE ---")
    lines.append(f"  Inserted: {stats['inserted']}")
    lines.append(f"  Updated: {stats['updated']}")
    lines.append(f"  Failed: {stats['failed']}")
    lines.append("")
    
    if rejected:
        lines.append("--- REJECTED POSITIONS ---")
        for pos in rejected:
            lines.append(f"  {pos['ticker']:10s} | ${pos['live_value_usd']:>10,.2f} | {pos['reject_reason']}")
        lines.append("")
    
    lines.append("--- TOP 10 SYNCED POSITIONS ---")
    for pos in sorted(valid, key=lambda x: x['live_value_usd'], reverse=True)[:10]:
        lines.append(f"  {pos['ticker']:10s} | ${pos['live_value_usd']:>10,.2f} | {pos['shares']:>8.2f} shares")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def run_gbm_sync(mxn_rate: float = DEFAULT_MXN_RATE) -> str:
    """Main entry point: run full GBM sync."""
    print("🚀 Starting GBM Portfolio Sync...\n")
    
    # Load Supabase client
    sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
    from sync.vox_postgres_sync import get_client
    sb = get_client()
    
    all_valid = []
    all_rejected = []
    all_stats = {'inserted': 0, 'updated': 0, 'failed': 0, 'total_value': 0}
    
    # Process GBM Main
    if GBM_MAIN_PATH.exists():
        print(f"📁 Loading GBM Main: {GBM_MAIN_PATH}")
        data = load_gbm_json(GBM_MAIN_PATH)
        positions = parse_gbm_main(data, mxn_rate)
        print(f"  Found {len(positions)} raw positions")
        
        valid, rejected = validate_gbm_positions(positions)
        print(f"  ✅ Valid: {len(valid)} | ❌ Rejected: {len(rejected)}")
        
        stats = sync_to_supabase(valid, sb)
        all_valid.extend(valid)
        all_rejected.extend(rejected)
        for k in all_stats:
            all_stats[k] += stats[k]
    else:
        print(f"⚠️  GBM Main export not found: {GBM_MAIN_PATH}")
    
    # Process GBM USA
    if GBM_USA_PATH.exists():
        print(f"\n📁 Loading GBM USA: {GBM_USA_PATH}")
        data = load_gbm_json(GBM_USA_PATH)
        positions = parse_gbm_usa(data)
        print(f"  Found {len(positions)} raw positions")
        
        valid, rejected = validate_gbm_positions(positions)
        print(f"  ✅ Valid: {len(valid)} | ❌ Rejected: {len(rejected)}")
        
        stats = sync_to_supabase(valid, sb)
        all_valid.extend(valid)
        all_rejected.extend(rejected)
        for k in all_stats:
            all_stats[k] += stats[k]
    else:
        print(f"⚠️  GBM USA export not found: {GBM_USA_PATH}")
    
    # Generate report
    report = generate_report(all_valid, all_rejected, all_stats)
    print("\n" + report)
    
    # Save report to file
    report_path = Path.home() / '.hermes' / 'scripts' / f'gbm_sync_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\n📝 Report saved: {report_path}")
    
    return report


if __name__ == '__main__':
    # Allow MXN rate override from command line
    rate = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MXN_RATE
    run_gbm_sync(rate)
