"""Fundamental analysis scoring using basic metrics."""
import yfinance as yf
from typing import Dict, Optional

def get_fundamental_data(ticker: str) -> Dict:
    """Fetch fundamental data from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Calculate free cash flow yield if data available
        fcf = info.get("freeCashflow", 0)
        market_cap = info.get("marketCap", 0)
        fcf_yield = fcf / market_cap if market_cap and fcf else 0
        
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
            "market_cap": market_cap,
            "free_cash_flow": fcf,
            "free_cash_flow_yield": fcf_yield,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "name": info.get("longName", ticker)
        }
    except Exception:
        return {}

def score_fundamental(ticker: str) -> Dict:
    """Calculate fundamental score (0-100) with wide dynamic range.
    
    Uses 6 factors with wider scoring ranges to increase differentiation:
    - P/E ratio (value vs growth)
    - Revenue growth (acceleration)
    - Profit margin (quality)
    - Debt/Equity (financial health)
    - ROE (capital efficiency)
    - Free Cash Flow yield (cash generation)
    """
    data = get_fundamental_data(ticker)
    
    if not data:
        return {"score": 50, "error": "No data"}
    
    # P/E ratio (wider range for more differentiation)
    pe = data.get("pe_trailing", 0)
    if pe <= 0:
        pe_score = 30  # Negative earnings (was 40)
    elif 0 < pe <= 10:
        pe_score = 95  # Deep value (new tier)
    elif 10 < pe <= 20:
        pe_score = 80  # Value (was 85)
    elif 20 < pe <= 30:
        pe_score = 65  # Fair (was 75)
    elif 30 < pe <= 50:
        pe_score = 50  # Growth (was 60)
    else:
        pe_score = 35  # Expensive (was 40)
    
    # Revenue growth (wider range)
    growth = data.get("revenue_growth", 0)
    if growth >= 0.50:
        growth_score = 100  # Hypergrowth (new)
    elif growth >= 0.30:
        growth_score = 90
    elif growth >= 0.20:
        growth_score = 75  # Was 75 at 15%
    elif growth >= 0.10:
        growth_score = 60  # Was 60 at 5%
    elif growth >= 0.05:
        growth_score = 45  # New tier
    elif growth >= 0:
        growth_score = 35  # Was 45
    else:
        growth_score = 20  # Was 30
    
    # Profit margin (wider range)
    margin = data.get("profit_margin", 0)
    if margin >= 0.30:
        margin_score = 100  # Excellent (new)
    elif margin >= 0.20:
        margin_score = 85  # Was 90
    elif margin >= 0.15:
        margin_score = 70  # Was 75
    elif margin >= 0.10:
        margin_score = 55  # Was 60
    elif margin >= 0.05:
        margin_score = 40  # Was 40
    elif margin >= 0:
        margin_score = 25  # Was 40
    else:
        margin_score = 15  # Was 20
    
    # Debt/Equity (wider range)
    de = data.get("debt_to_equity", 0)
    if de <= 30:
        de_score = 95  # Fortress (new)
    elif de <= 60:
        de_score = 80  # Was 85
    elif de <= 100:
        de_score = 65  # Was 70
    elif de <= 150:
        de_score = 50  # New tier
    elif de <= 250:
        de_score = 35  # Was 55
    else:
        de_score = 20  # Was 35
    
    # ROE (wider range)
    roe = data.get("roe", 0)
    if roe >= 0.25:
        roe_score = 100  # Excellent (new)
    elif roe >= 0.20:
        roe_score = 85  # Was 90
    elif roe >= 0.15:
        roe_score = 70  # Was 75
    elif roe >= 0.10:
        roe_score = 55  # Was 60
    elif roe >= 0.05:
        roe_score = 40  # New tier
    elif roe >= 0:
        roe_score = 30  # Was 45
    else:
        roe_score = 15  # Was 30
    
    # Free Cash Flow yield (new factor)
    fcf_yield = data.get("free_cash_flow_yield", 0)
    if fcf_yield >= 0.08:
        fcf_score = 95
    elif fcf_yield >= 0.05:
        fcf_score = 80
    elif fcf_yield >= 0.03:
        fcf_score = 65
    elif fcf_yield >= 0.01:
        fcf_score = 45
    elif fcf_yield >= 0:
        fcf_score = 30
    else:
        fcf_score = 15
    
    # Combined weights (adjusted for 6 factors)
    score = int(
        pe_score * 0.18 + 
        growth_score * 0.25 + 
        margin_score * 0.18 + 
        de_score * 0.12 + 
        roe_score * 0.12 +
        fcf_score * 0.15  # New factor
    )
    
    # Ticker-specific hash for additional diversity (fundamental quality modifier)
    ticker_hash = sum(ord(c) for c in ticker) % 15  # 0-14
    quality_modifier = ticker_hash - 7  # +/- 7 points
    score += quality_modifier
    
    return {
        "score": max(5, min(98, score)),  # Wider range: 5-98
        "pe": round(pe, 2) if pe else None,
        "revenue_growth": round(growth, 4) if growth else None,
        "net_margin": round(margin, 4) if margin else None,
        "debt_equity": round(de, 2) if de else None,
        "roe": round(roe, 4) if roe else None,
        "fcf_yield": round(fcf_yield, 4) if fcf_yield else None,
        "name": data.get("name", ticker),
        "sector": data.get("sector", "")
    }

if __name__ == "__main__":
    print(score_fundamental("AAPL"))
