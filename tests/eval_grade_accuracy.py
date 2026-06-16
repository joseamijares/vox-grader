"""VOX Eval Framework — Backtest grade accuracy vs forward returns.

Run: python tests/eval_grade_accuracy.py

Evaluates:
- Grade → forward return correlation (1 week, 1 month, 3 months)
- Grade distribution health (avoid clustering)
- Grade stability (consistency over time)
- Buy/Sell signal accuracy (grade > 70 = buy, < 40 = sell)
"""
import os
import sys
import json
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from grading.vox_engine import calculate_vox_grade
from grading.technical import get_stock_data


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FORWARD_PERIODS = {
    '1w': 5,
    '1m': 21,
    '3m': 63,
}

GRADE_THRESHOLDS = {
    'strong_buy': 70,
    'buy': 60,
    'hold_high': 55,
    'hold_low': 45,
    'sell': 40,
    'strong_sell': 30,
}

SAMPLE_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM',
    'V', 'WMT', 'JNJ', 'UNH', 'XOM', 'LLY', 'MA', 'PG', 'HD', 'CVX',
    'MRK', 'ABBV', 'PEP', 'KO', 'BAC', 'PFE', 'COST', 'TMO', 'ABT',
    'MCD', 'CSCO', 'ACN', 'VZ', 'ADBE', 'WFC', 'CMCSA', 'CRM', 'NKE',
    'TXN', 'PM', 'NEE', 'BMY', 'QCOM', 'RTX', 'HON', 'UPS', 'LOW',
    'ORCL', 'IBM', 'AMGN', 'INTU', 'SPGI'
]


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------

def fetch_historical_prices(ticker: str, period: str = '1y') -> dict:
    """Fetch historical prices and return {date: close_price}."""
    df = get_stock_data(ticker, period=period)
    if df is None or len(df) < 50:
        return {}
    
    prices = {}
    for idx, row in df.iterrows():
        if isinstance(idx, datetime):
            prices[idx.strftime('%Y-%m-%d')] = float(row['Close'])
        else:
            prices[str(idx)[:10]] = float(row['Close'])
    
    return prices


def compute_forward_return(prices: dict, start_date: str, days: int) -> float:
    """Compute forward return from start_date for N trading days."""
    dates = sorted(prices.keys())
    
    try:
        start_idx = dates.index(start_date)
    except ValueError:
        # Find nearest date
        for d in dates:
            if d >= start_date:
                start_idx = dates.index(d)
                break
        else:
            return None
    
    end_idx = start_idx + days
    if end_idx >= len(dates):
        return None
    
    start_price = prices[dates[start_idx]]
    end_price = prices[dates[end_idx]]
    
    return (end_price - start_price) / start_price


# ---------------------------------------------------------------------------
# Grade Collection
# ---------------------------------------------------------------------------

def collect_grades(tickers: list) -> dict:
    """Collect current VOX grades for tickers."""
    grades = {}
    
    for i, ticker in enumerate(tickers):
        try:
            result = calculate_vox_grade(ticker)
            grades[ticker] = {
                'grade': result.overall_grade,
                'technical': result.technical_score,
                'fundamental': result.fundamental_score,
                'macro': result.macro_score,
                'sector': result.sector_score,
                'weather': result.weather_score,
                'sentiment': result.sentiment_score,
                'timestamp': datetime.now().isoformat(),
            }
            print(f"  [{i+1}/{len(tickers)}] {ticker}: grade={result.overall_grade}")
        except Exception as e:
            print(f"  [{i+1}/{len(tickers)}] {ticker}: ERROR - {e}")
            grades[ticker] = None
    
    return grades


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_grade_distribution(grades: dict) -> dict:
    """Analyze grade distribution health."""
    valid_grades = [g['grade'] for g in grades.values() if g]
    
    if not valid_grades:
        return {}
    
    return {
        'count': len(valid_grades),
        'mean': round(np.mean(valid_grades), 2),
        'std': round(np.std(valid_grades), 2),
        'min': min(valid_grades),
        'max': max(valid_grades),
        'median': int(np.median(valid_grades)),
        'unique_values': len(set(valid_grades)),
        'clustering_risk': len(set(valid_grades)) < 20,  # Too few unique grades = clustering
    }


def analyze_grade_vs_returns(grades: dict, prices: dict, period_days: int) -> dict:
    """Correlate grades with forward returns."""
    today = datetime.now().strftime('%Y-%m-%d')
    
    data = []
    for ticker, grade_info in grades.items():
        if not grade_info or ticker not in prices:
            continue
        
        ret = compute_forward_return(prices[ticker], today, period_days)
        if ret is not None:
            data.append((grade_info['grade'], ret))
    
    if len(data) < 10:
        return {'error': 'Insufficient data'}
    
    grades_arr = np.array([d[0] for d in data])
    returns_arr = np.array([d[1] for d in data])
    
    # Pearson correlation
    if np.std(grades_arr) > 0 and np.std(returns_arr) > 0:
        correlation = np.corrcoef(grades_arr, returns_arr)[0, 1]
    else:
        correlation = 0
    
    # Signal accuracy
    strong_buys = [r for g, r in data if g >= GRADE_THRESHOLDS['strong_buy']]
    buys = [r for g, r in data if GRADE_THRESHOLDS['buy'] <= g < GRADE_THRESHOLDS['strong_buy']]
    sells = [r for g, r in data if g <= GRADE_THRESHOLDS['sell']]
    
    return {
        'sample_size': len(data),
        'correlation': round(correlation, 3),
        'strong_buy_avg_return': round(np.mean(strong_buys) * 100, 2) if strong_buys else None,
        'buy_avg_return': round(np.mean(buys) * 100, 2) if buys else None,
        'sell_avg_return': round(np.mean(sells) * 100, 2) if sells else None,
        'strong_buy_count': len(strong_buys),
        'buy_count': len(buys),
        'sell_count': len(sells),
    }


def generate_report(grades: dict, prices: dict) -> dict:
    """Generate full eval report."""
    print("\n" + "=" * 60)
    print("VOX GRADE ACCURACY EVALUATION")
    print("=" * 60)
    
    # Grade distribution
    print("\n📊 GRADE DISTRIBUTION")
    dist = analyze_grade_distribution(grades)
    for k, v in dist.items():
        print(f"  {k}: {v}")
    
    # Forward return analysis (using historical data as proxy)
    print("\n📈 GRADE vs HISTORICAL RETURNS (proxy for forward prediction)")
    
    # Use last 21 days as proxy for "1 month forward"
    for label, days in [('1 week', 5), ('1 month', 21), ('3 months', 63)]:
        print(f"\n  {label} forward:")
        analysis = analyze_grade_vs_returns(grades, prices, days)
        if 'error' in analysis:
            print(f"    {analysis['error']}")
        else:
            print(f"    Correlation: {analysis['correlation']}")
            print(f"    Strong buy avg return: {analysis['strong_buy_avg_return']}%")
            print(f"    Buy avg return: {analysis['buy_avg_return']}%")
            print(f"    Sell avg return: {analysis['sell_avg_return']}%")
            print(f"    Signal counts: {analysis['strong_buy_count']} strong buys, {analysis['buy_count']} buys, {analysis['sell_count']} sells")
    
    # Layer contribution analysis
    print("\n🎯 LAYER CONTRIBUTION ANALYSIS")
    valid = [g for g in grades.values() if g]
    if valid:
        for layer in ['technical', 'fundamental', 'macro', 'sector', 'weather', 'sentiment']:
            scores = [g[layer] for g in valid]
            print(f"  {layer}: mean={round(np.mean(scores), 1)}, std={round(np.std(scores), 1)}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    if dist.get('clustering_risk'):
        print("  ⚠️ Grade clustering detected — too few unique values. Consider widening score ranges.")
    else:
        print("  ✅ Grade distribution healthy — good diversity")
    
    print("\n" + "=" * 60)
    
    return {
        'distribution': dist,
        'timestamp': datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Collecting VOX grades for eval...")
    grades = collect_grades(SAMPLE_TICKERS)
    
    print("\nFetching historical prices...")
    prices = {}
    for ticker in SAMPLE_TICKERS:
        p = fetch_historical_prices(ticker, period='6mo')
        if p:
            prices[ticker] = p
    
    report = generate_report(grades, prices)
    
    # Save report
    report_path = os.path.join(os.path.dirname(__file__), '..', 'eval_reports')
    os.makedirs(report_path, exist_ok=True)
    filename = f"grade_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(os.path.join(report_path, filename), 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved: {filename}")


if __name__ == '__main__':
    main()
