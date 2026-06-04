"""Portfolio sync validator — prevents garbage data from entering database."""
import yfinance as yf
from typing import List, Dict

# Minimum value threshold for positions (in USD)
MIN_POSITION_VALUE = 10.0

# Known garbage/meme tokens that should never be tracked
GARBAGE_TICKERS = {
    '0G', '1000CAT', '2Z', 'ACE', 'AIGENSYN', 'ALLO', 'AMB', 'ANIME', 'AT', 'AVNT',
    'BABY', 'BARD', 'BERA', 'BETH', 'BIO', 'BMT', 'BONK', 'BREV', 'CHIP', 'DOLO',
    'DOT', 'EDEN', 'ENSO', 'ERA', 'ETHW', 'EUL', 'FDUSD', 'FF', 'GPS', 'GUN',
    'HAEDAL', 'HEMI', 'HOLO', 'HOME', 'HUMA', 'HYPER', 'INIT', 'KAITO', 'KERNEL',
    'KITE', 'LA', 'LAYER', 'LINEA', 'MANA', 'MEME', 'MITO', 'MMT', 'MORPHO', 'MOVE',
    'NIGHT', 'NIL', 'NXPC', 'OPEN', 'OPN', 'PARTI', 'PENGU', 'PLUME', 'PROVE', 'RED',
    'RESOLV', 'ROBO', 'SAHARA', 'SAPIEN', 'SHELL', 'SIGN', 'SOLV', 'SOMI', 'SOPH',
    'SPK', 'STO', 'SXT', 'THE', 'TOWNS', 'TREE', 'TURTLE', 'USDT', 'USUAL', 'VANA',
    'WAL', 'WCT', 'XPL', 'YB', 'ZBT', 'ZKC'
}

# Tickers that are valid but should be filtered (stablecoins, etc.)
FILTERED_TICKERS = {'USDT', 'FDUSD', 'USDC'}


def is_valid_stock_ticker(ticker: str) -> bool:
    """Check if stock ticker exists on Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return bool(info.get('regularMarketPrice') or info.get('currentPrice'))
    except Exception:
        return False


def validate_position(ticker: str, value: float, broker: str) -> Dict:
    """Validate a single position. Returns dict with status."""
    result = {
        'ticker': ticker,
        'value': value,
        'broker': broker,
        'valid': True,
        'reason': None
    }
    
    # Check minimum value
    if value < MIN_POSITION_VALUE:
        result['valid'] = False
        result['reason'] = f'Value ${value:.2f} below minimum ${MIN_POSITION_VALUE}'
        return result
    
    # Check known garbage tokens
    if ticker in GARBAGE_TICKERS:
        result['valid'] = False
        result['reason'] = f'Known garbage/meme token: {ticker}'
        return result
    
    # Check filtered tickers (stablecoins)
    if ticker in FILTERED_TICKERS:
        result['valid'] = False
        result['reason'] = f'Stablecoin not tracked: {ticker}'
        return result
    
    # Check for suspicious single-letter tickers on crypto brokers
    if len(ticker) == 1 and broker in ['Binance', 'Bitso']:
        result['valid'] = False
        result['reason'] = f'Single-letter ticker suspicious on {broker}: {ticker}'
        return result
    
    # Validate stock tickers against Yahoo Finance
    if broker in ['eToro', 'GBM Main', 'GBM USA', 'IBKR', 'Schwab']:
        if not is_valid_stock_ticker(ticker):
            # Allow some exceptions for known valid tickers
            known_valid = {'GBM O', 'NAFTRAC', 'NAFTRAC ISHRS', '0700.HK'}
            if ticker not in known_valid:
                result['valid'] = False
                result['reason'] = f'Invalid stock ticker: {ticker}'
                return result
    
    return result


def validate_portfolio(positions: List[Dict]) -> Dict:
    """Validate entire portfolio. Returns summary."""
    valid = []
    rejected = []
    
    for pos in positions:
        result = validate_position(
            pos.get('ticker', ''),
            pos.get('value', 0),
            pos.get('broker', '')
        )
        if result['valid']:
            valid.append(result)
        else:
            rejected.append(result)
    
    return {
        'valid': valid,
        'rejected': rejected,
        'valid_count': len(valid),
        'rejected_count': len(rejected),
        'valid_value': sum(p['value'] for p in valid),
        'rejected_value': sum(p['value'] for p in rejected)
    }


def sync_portfolio_to_supabase(positions: List[Dict], sb_client) -> Dict:
    """Sync validated positions to Supabase, replacing all existing."""
    validation = validate_portfolio(positions)
    
    # Delete all existing positions
    sb_client.table('positions').delete().neq('id', 0).execute()
    
    # Insert validated positions
    for pos in validation['valid']:
        sb_client.table('positions').insert({
            'ticker': pos['ticker'],
            'live_value': pos['value'],
            'brokers': [pos['broker']],
            'grade': 0,
            'council': 'UNGRADED'
        }).execute()
    
    return validation
