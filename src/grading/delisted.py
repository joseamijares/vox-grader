"""Delisted stock checker and validator."""
import yfinance as yf
from typing import Dict, Optional

def check_ticker_status(ticker: str) -> Dict:
    """Check if a ticker is valid, delisted, or has issues."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if we got valid data
        has_price = info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None
        has_name = info.get("longName") is not None or info.get("shortName") is not None
        
        if not has_price and not has_name:
            return {
                "ticker": ticker,
                "valid": False,
                "delisted": True,
                "reason": "No price or name data - likely delisted",
                "name": None
            }
        
        # Check for very low prices (penny stock / near delisting)
        price = info.get("regularMarketPrice", info.get("currentPrice", 0))
        
        return {
            "ticker": ticker,
            "valid": True,
            "delisted": False,
            "price": price,
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", ""),
            "market_cap": info.get("marketCap", 0)
        }
        
    except Exception as e:
        return {
            "ticker": ticker,
            "valid": False,
            "delisted": True,
            "reason": str(e),
            "name": None
        }

def validate_watchlist(tickers: list) -> Dict:
    """Validate entire watchlist and return categorized results."""
    valid = []
    delisted = []
    errors = []
    
    print(f"Validating {len(tickers)} tickers...\n")
    
    for ticker in tickers:
        result = check_ticker_status(ticker)
        
        if result["delisted"]:
            delisted.append(result)
            print(f"  ⚠️  {ticker}: DELISTED - {result.get('reason', '')}")
        elif result["valid"]:
            valid.append(result)
            print(f"  ✅ {ticker}: OK (${result.get('price', 0):.2f})")
        else:
            errors.append(result)
            print(f"  ❌ {ticker}: ERROR - {result.get('reason', '')}")
    
    return {
        "valid": valid,
        "delisted": delisted,
        "errors": errors,
        "total": len(tickers),
        "valid_count": len(valid),
        "delisted_count": len(delisted),
        "error_count": len(errors)
    }

if __name__ == "__main__":
    # Test
    test_tickers = ["LILM", "AAPL", "INVALID123", "TSLA"]
    results = validate_watchlist(test_tickers)
    print(f"\nSummary: {results['valid_count']} valid, {results['delisted_count']} delisted, {results['error_count']} errors")
