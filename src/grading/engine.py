"""Grading engine — combines all scoring modules."""
from .technical import score_technical
from .fundamental import score_fundamental
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class GradeResult:
    """Grading engine output."""
    ticker: str
    overall_grade: int
    technical_score: int
    fundamental_score: int
    sentiment_score: int
    momentum_score: int
    risk_score: int
    council: str
    calculated_at: datetime
    factors: Dict
    name: str = ""
    sector: str = ""

def grade_to_council(grade: int) -> str:
    """Convert numeric grade to council signal."""
    if grade >= 90:
        return "STRONG_BUY"
    elif grade >= 75:
        return "BUY"
    elif grade >= 50:
        return "HOLD"
    elif grade >= 25:
        return "SELL"
    else:
        return "STRONG_SELL"

def calculate_grade(ticker: str, use_fundamental: bool = True) -> GradeResult:
    """Calculate overall grade for a stock."""
    
    # Technical score
    tech = score_technical(ticker)
    technical_score = tech.get("score", 50)
    
    # Fundamental score
    if use_fundamental:
        fund = score_fundamental(ticker)
        fundamental_score = fund.get("score", 50)
        name = fund.get("name", ticker)
        sector = fund.get("sector", "")
    else:
        fundamental_score = 50
        fund = {}
        name = ticker
        sector = ""
    
    # Momentum score from technical module (12-month momentum if available)
    momentum_score = tech.get("momentum_score", 50)
    
    # Risk score from volatility (inverse of std20 annualized)
    vol_annual = tech.get("volatility_annual", 0.20)
    if vol_annual <= 0.15:
        risk_score = 80
    elif vol_annual <= 0.25:
        risk_score = 65
    elif vol_annual <= 0.40:
        risk_score = 50
    elif vol_annual <= 0.60:
        risk_score = 35
    else:
        risk_score = 20
    
    # Sentiment placeholder — will be overridden by integrated grader's sentiment layer
    sentiment_score = tech.get("sentiment_score", 50)
    
    # Weighted average — 6-layer VOX weights
    # Technical 25%, Fundamental 25%, Macro 15%, Sector 15%, Weather 10%, Sentiment 10%
    # When called standalone (no macro/sector/weather), approximate with:
    overall = int(
        technical_score * 0.30 +
        fundamental_score * 0.30 +
        momentum_score * 0.15 +
        risk_score * 0.15 +
        sentiment_score * 0.10
    )
    
    # Determine council signal
    council = grade_to_council(overall)
    
    return GradeResult(
        ticker=ticker,
        overall_grade=overall,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        sentiment_score=sentiment_score,
        momentum_score=momentum_score,
        risk_score=risk_score,
        council=council,
        calculated_at=datetime.utcnow(),
        name=name,
        sector=sector,
        factors={
            "technical": tech,
            "fundamental": fund,
            "sentiment": {"score": sentiment_score},
            "momentum": {"score": momentum_score},
            "risk": {"score": risk_score}
        }
    )

def batch_grade(tickers: List[str]) -> List[GradeResult]:
    """Grade multiple stocks."""
    results = []
    for ticker in tickers:
        try:
            result = calculate_grade(ticker)
            results.append(result)
            print(f"  ✅ {ticker}: Grade {result.overall_grade} ({result.council})")
        except Exception as e:
            print(f"  ❌ {ticker}: ERROR - {e}")
            results.append(GradeResult(
                ticker=ticker,
                overall_grade=0,
                technical_score=0,
                fundamental_score=0,
                sentiment_score=0,
                momentum_score=0,
                risk_score=0,
                council="ERROR",
                calculated_at=datetime.utcnow(),
                factors={"error": str(e)}
            ))
    return results

if __name__ == "__main__":
    # Test
    result = calculate_grade("AAPL")
    print(f"\n{result.ticker}: {result.overall_grade} ({result.council})")
    print(f"  Technical: {result.technical_score}")
    print(f"  Fundamental: {result.fundamental_score}")
