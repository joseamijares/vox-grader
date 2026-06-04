"""Fundamental analysis scoring using basic metrics."""
import yfinance as yf
from typing import Dict, Optional

def get_fundamental_data(ticker: str) -> Dict:
    """Fetch fundamental data from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "pe_trailing": info.get("trailingPE", 0),
            "pe_forward": info.get("forwardPE", 0),
            "revenue_growth": info.get("revenueGrowth", 0),
            "earnings_growth": info.get("earningsGrowth", 0),
            "profit_margin": info.get("profitMargins", 0),
            "debt_to_equity": info.get("debtToEquity", 0),
            "roe": info.get("returnOnEquity", 0),
            "roa": info.get("returnOnAssets", 0),
            "current_ratio": info.get("currentRatio", 0),
            "quick_ratio": info.get("quickRatio", 0),
            "market_cap": info.get("marketCap", 0),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "name": info.get("longName", ticker)
        }
    except Exception:
        return {}

def score_fundamental(ticker: str) -> Dict:
    """Calculate fundamental score (0-100)."""
    data = get_fundamental_data(ticker)
    
    if not data:
        return {"score": 50, "error": "No data"}
    
    # P/E ratio (lower is better, but quality matters)
    pe = data.get("pe_trailing", 0)
    if pe <= 0:
        pe_score = 40  # Negative earnings
    elif 5 <= pe <= 15:
        pe_score = 85  # Value
    elif 15 < pe <= 25:
        pe_score = 75  # Fair
    elif 25 < pe <= 40:
        pe_score = 60  # Growth
    else:
        pe_score = 40  # Expensive
    
    # Revenue growth
    growth = data.get("revenue_growth", 0)
    if growth >= 0.30:
        growth_score = 90
    elif growth >= 0.15:
        growth_score = 75
    elif growth >= 0.05:
        growth_score = 60
    elif growth >= 0:
        growth_score = 45
    else:
        growth_score = 30
    
    # Profit margin
    margin = data.get("profit_margin", 0)
    if margin >= 0.20:
        margin_score = 90
    elif margin >= 0.10:
        margin_score = 75
    elif margin >= 0.05:
        margin_score = 60
    elif margin >= 0:
        margin_score = 40
    else:
        margin_score = 20
    
    # Debt/Equity (lower is better)
    de = data.get("debt_to_equity", 0)
    if de <= 50:
        de_score = 85
    elif de <= 100:
        de_score = 70
    elif de <= 200:
        de_score = 55
    else:
        de_score = 35
    
    # ROE
    roe = data.get("roe", 0)
    if roe >= 0.20:
        roe_score = 90
    elif roe >= 0.15:
        roe_score = 75
    elif roe >= 0.10:
        roe_score = 60
    elif roe >= 0:
        roe_score = 45
    else:
        roe_score = 30
    
    # Combined
    score = int(pe_score * 0.20 + growth_score * 0.30 + margin_score * 0.20 + de_score * 0.15 + roe_score * 0.15)
    
    return {
        "score": max(0, min(100, score)),
        "pe": round(pe, 2) if pe else None,
        "revenue_growth": round(growth, 4) if growth else None,
        "net_margin": round(margin, 4) if margin else None,
        "debt_equity": round(de, 2) if de else None,
        "roe": round(roe, 4) if roe else None,
        "name": data.get("name", ticker),
        "sector": data.get("sector", "")
    }

if __name__ == "__main__":
    print(score_fundamental("AAPL"))
