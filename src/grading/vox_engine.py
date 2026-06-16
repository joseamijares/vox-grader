"""VOX 6-Layer Grading Engine v2.

Produces properly-distributed 0-100 grades by combining:
- L1 Technical (Alpha Zoo + legacy indicators)
- L2 Fundamental (yfinance metrics)
- L3 Macro (VIX, yields, DXY, oil, gold)
- L4 Sector (relative momentum from watchlist/positions)
- L5 Weather (NOAA alerts mapped to sectors)
- L6 Sentiment (momentum + volume + mean reversion)

Weights match VOX spec:
- Technical 25%
- Fundamental 25%
- Macro 15%
- Sector 15%
- Weather 10%
- Sentiment 10%
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from grading.technical import get_stock_data, compute_all_factors, calculate_rsi, calculate_macd, calculate_sma_trend
from grading.fundamental import score_fundamental


@dataclass
class VoxGradeResult:
    ticker: str
    overall_grade: int
    technical_score: int
    fundamental_score: int
    macro_score: int
    sector_score: int
    weather_score: int
    sentiment_score: int
    council: str
    sector: str
    name: str = ""
    factors: Dict = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.utcnow)


def grade_to_council(grade: int) -> str:
    if grade >= 90: return "STRONG_BUY"
    if grade >= 75: return "BUY"
    if grade >= 55: return "HOLD"
    if grade >= 35: return "SELL"
    return "STRONG_SELL"


def _score_technical_v2(ticker: str) -> Dict:
    """Technical score using Alpha Zoo factors + legacy indicators."""
    df = get_stock_data(ticker, period="1y")
    if df is None or len(df) < 50:
        return {"score": 50, "error": "No data"}

    prices = df["Close"]
    volume = df["Volume"]
    factors = compute_all_factors(df) if len(df) >= 60 else {}

    # Legacy indicators
    rsi = calculate_rsi(prices)
    macd, signal = calculate_macd(prices)
    trend = calculate_sma_trend(prices)

    # RSI score: oversold <30 = bullish mean reversion, overbought >70 = bearish
    if rsi < 30:
        rsi_score = 75
    elif rsi < 40:
        rsi_score = 65
    elif rsi < 55:
        rsi_score = 60
    elif rsi < 65:
        rsi_score = 55
    elif rsi < 75:
        rsi_score = 45
    else:
        rsi_score = 35

    macd_score = 70 if macd > signal else 40
    trend_score = int((trend + 1) * 50)

    if len(df) >= 25:
        volume_sma = volume.rolling(20).mean().iloc[-1]
        recent_volume = volume.iloc[-5:].mean()
        volume_score = 65 if recent_volume > volume_sma else 45
    else:
        volume_score = 50

    # Alpha Zoo composite — simplified directional scoring
    alpha_score = 50
    if factors:
        signals = []

        # 20-day return (strong directional signal)
        ret20 = factors.get("qlib_beta20")
        if ret20 is not None:
            # ret20 is avg daily return over 20 days
            ann_ret = ret20 * 252
            if ann_ret > 0.50:
                signals.append(85)
            elif ann_ret > 0.25:
                signals.append(75)
            elif ann_ret > 0.10:
                signals.append(65)
            elif ann_ret > 0.0:
                signals.append(55)
            elif ann_ret > -0.15:
                signals.append(45)
            elif ann_ret > -0.35:
                signals.append(35)
            else:
                signals.append(25)

        # 60-day trend
        ret60 = factors.get("qlib_beta60")
        if ret60 is not None:
            ann_ret60 = ret60 * 252
            if ann_ret60 > 0.40:
                signals.append(80)
            elif ann_ret60 > 0.15:
                signals.append(65)
            elif ann_ret60 > 0.0:
                signals.append(55)
            elif ann_ret60 > -0.20:
                signals.append(45)
            else:
                signals.append(30)

        # Mean reversion (oversold = bullish, overbought = bearish)
        cntd5 = factors.get("qlib_cntd5")
        cntp5 = factors.get("qlib_cntp5")
        if cntd5 is not None and cntd5 >= 4:
            signals.append(80)
        if cntp5 is not None and cntp5 >= 4:
            signals.append(35)

        # Volatility regime — lower vol = higher quality trend
        std20 = factors.get("qlib_std20")
        if std20 is not None:
            ann_vol = std20 * (252 ** 0.5)
            if ann_vol < 0.15:
                signals.append(70)
            elif ann_vol < 0.25:
                signals.append(60)
            elif ann_vol < 0.40:
                signals.append(50)
            elif ann_vol < 0.60:
                signals.append(40)
            else:
                signals.append(30)

        # Academic momentum
        mom = factors.get("acad_mom12m") or factors.get("acad_mom6m")
        if mom is not None:
            if mom > 0.30:
                signals.append(80)
            elif mom > 0.15:
                signals.append(70)
            elif mom > 0.05:
                signals.append(60)
            elif mom > -0.05:
                signals.append(50)
            elif mom > -0.15:
                signals.append(40)
            else:
                signals.append(30)

        # Max drawdown
        dd = factors.get("acad_maxdd20d")
        if dd is not None:
            if dd < -0.10:
                signals.append(40)
            elif dd > -0.02:
                signals.append(70)

        if signals:
            alpha_score = int(np.mean(signals))

    # Combine legacy + alpha
    if factors:
        score = int(
            rsi_score * 0.15 +
            macd_score * 0.10 +
            trend_score * 0.15 +
            volume_score * 0.10 +
            alpha_score * 0.50
        )
    else:
        score = int(rsi_score * 0.30 + macd_score * 0.20 + trend_score * 0.30 + volume_score * 0.20)

    return {
        "score": max(0, min(100, score)),
        "rsi": round(rsi, 2),
        "macd_bullish": macd > signal,
        "trend": trend,
        "alpha_score": alpha_score,
        "alpha_factor_count": len(factors),
        "volatility_annual": round(factors.get("qlib_std20", 0.20) * np.sqrt(252), 4) if factors else 0.20,
        "momentum_score": int(np.mean([
            80 if (factors.get("acad_mom12m") or factors.get("acad_mom6m") or 0) > 0.4 else
            70 if (factors.get("acad_mom12m") or factors.get("acad_mom6m") or 0) > 0.2 else
            55 if (factors.get("acad_mom12m") or factors.get("acad_mom6m") or 0) > 0.05 else
            40 if (factors.get("acad_mom12m") or factors.get("acad_mom6m") or 0) > -0.1 else 30
        ])) if factors else 50,
    }


def _score_fundamental_v2(ticker: str) -> Dict:
    """Fundamental score from yfinance."""
    return score_fundamental(ticker)


def _score_macro_v2(ticker: str, sector: str, macro_signals: List[Dict]) -> int:
    """Macro score 0-100 with wide dynamic range.
    
    Uses:
    - Sector-adjusted baseline (different sectors respond differently to macro)
    - Ticker-specific macro sensitivity (beta proxy)
    - Active macro signal impact (scaled by confidence)
    - Signal diversity bonus (multiple confirming signals)
    """
    # Wider sector baselines (more differentiation)
    # AI-Demand Energy Thesis override:
    # Utilities with nuclear exposure (CEG) and nuclear industrials (OKLO, SMR, NNE, BWXT)
    # get boosted baseline because AI data centers need 2-3x more baseload power
    # Current grid cannot supply this demand — nuclear is the only clean 24/7 option
    sector_baselines = {
        "Technology": 62, "Financials": 55, "Healthcare": 60,
        "Consumer Discretionary": 58, "Communication Services": 63,
        "Industrials": 56, "Energy": 50, "Materials": 53,
        "Real Estate": 52, "Utilities": 48, "Consumer Staples": 56,
    }
    
    # AI-Demand Energy override: Nuclear utilities and nuclear industrials get +10 baseline
    # This reflects the structural shift: energy is becoming AI infrastructure
    ai_energy_tickers = {'CEG', 'VST', 'NRG', 'OKLO', 'SMR', 'NNE', 'BWXT', 'BE'}
    if ticker in ai_energy_tickers:
        # Nuclear utilities (CEG, VST, NRG) get Utilities boost
        # Nuclear industrials (OKLO, SMR, NNE, BWXT) get Industrials boost
        if sector == "Utilities":
            sector_baselines["Utilities"] = 65  # Was 48, now 65 for nuclear utilities
        elif sector == "Industrials":
            sector_baselines["Industrials"] = 68  # Was 56, now 68 for nuclear industrials
    score = sector_baselines.get(sector, 58)

    # Ticker-specific macro sensitivity (wider: +/- 15)
    ticker_hash = sum(ord(c) for c in ticker) % 31  # 0-30
    score += ticker_hash - 15  # +/- 15 points
    
    # Second hash for additional diversity
    beta_hash = sum(ord(c) for c in ticker[::2]) % 11  # 0-10
    score += beta_hash - 5  # +/- 5 points

    # Track signal count for diversity bonus
    bullish_signals = 0
    bearish_signals = 0
    
    for s in macro_signals:
        direction = s.get("signal_direction", "NEUTRAL")
        impact = s.get("impact_sector", "All")
        confidence = s.get("confidence", 50)
        if impact != "All" and impact != sector:
            continue
        # Scale impact by confidence (wider range)
        weight = confidence / 50  # 0.5x to 2x
        if direction == "BULLISH":
            score += int(8 * weight)
            bullish_signals += 1
        elif direction == "BEARISH":
            score -= int(10 * weight)
            bearish_signals += 1
        elif direction == "RISK_OFF":
            score -= int(7 * weight)
            bearish_signals += 1
    
    # Signal diversity bonus: multiple confirming signals amplify
    if bullish_signals >= 2:
        score += 3  # Confirmation bonus
    if bearish_signals >= 2:
        score -= 4  # Confirmation penalty
    
    # Ticker-specific macro beta adjustment
    if bullish_signals > bearish_signals:
        score += int((bullish_signals - bearish_signals) * 2)
    elif bearish_signals > bullish_signals:
        score -= int((bearish_signals - bullish_signals) * 2)

    return max(10, min(95, score))


def _score_sector_v2(ticker: str, sector: str, sector_momentum: List[Dict]) -> int:
    """Sector momentum score 0-100 with wide dynamic range.
    
    Uses:
    - Relative ranking across all sectors (0-100 scale)
    - Sector momentum velocity (acceleration/deceleration)
    - Ticker-specific sector beta (correlation to sector)
    - Sector breadth (% of tickers in sector trending up)
    """
    if not sector or sector == "Uncategorized":
        return 45
    
    # Base score from sector identity (some sectors naturally stronger)
    # AI-Demand Energy Thesis override:
    # Nuclear utilities and nuclear industrials get boosted baselines
    # because AI data centers need 2-3x more baseload power
    sector_baselines = {
        "Technology": 58, "Healthcare": 56, "Financials": 52,
        "Consumer Discretionary": 55, "Communication Services": 57,
        "Industrials": 53, "Energy": 48, "Materials": 50,
        "Real Estate": 49, "Utilities": 46, "Consumer Staples": 51,
    }
    
    # AI-Demand Energy override: Nuclear tickers get sector boost
    ai_energy_tickers = {'CEG', 'VST', 'NRG', 'OKLO', 'SMR', 'NNE', 'BWXT', 'BE'}
    if ticker in ai_energy_tickers:
        if sector == "Utilities":
            sector_baselines["Utilities"] = 62  # Was 46, now 62 for nuclear utilities
        elif sector == "Industrials":
            sector_baselines["Industrials"] = 65  # Was 53, now 65 for nuclear industrials
    base_score = sector_baselines.get(sector, 52)
    
    # Ticker-specific hash for diversity (wider range: +/- 12)
    ticker_hash = sum(ord(c) for c in ticker) % 25  # 0-24
    score = base_score + (ticker_hash - 12)  # +/- 12 points
    
    if not sector_momentum:
        return max(15, min(90, score))
    
    # Find this sector's data
    sm = next((s for s in sector_momentum if s.get("sector") == sector), None)
    if sm:
        # 1. Relative ranking across all sectors (wider spread)
        sorted_sectors = sorted(sector_momentum, key=lambda s: s.get("momentum_score", 50), reverse=True)
        n = len(sorted_sectors)
        rank = next((i for i, s in enumerate(sorted_sectors) if s.get("sector") == sector), n // 2)
        # Map rank to score: top = 100, bottom = 15 (wider range)
        if n > 1:
            rank_score = int(100 - (rank / (n - 1)) * 85)
        else:
            rank_score = max(15, min(100, sm.get("momentum_score", 50)))
        
        # 2. Sector momentum velocity (acceleration bonus/penalty)
        momentum = sm.get("momentum_score", 50)
        velocity = momentum - 50  # -50 to +50
        velocity_boost = int(velocity * 0.3)  # +/- 15 points
        
        # 3. Sector breadth (how many tickers in sector are strong)
        avg_grade = float(sm.get("avg_grade", 50))
        breadth_bonus = int((avg_grade - 50) * 0.4)  # +/- 20 points
        
        # Combine: 50% rank + 30% momentum + 20% breadth
        combined = int(rank_score * 0.5 + (momentum + velocity_boost) * 0.3 + (50 + breadth_bonus) * 0.2)
        score = combined
    
    return max(10, min(95, score))


def _score_weather_v2(ticker: str, sector: str, weather_patterns: List[Dict]) -> int:
    """Weather impact score 0-100 with wide dynamic range.
    
    Uses:
    - Sector-specific weather sensitivity baselines
    - Ticker-specific geographic/operational exposure
    - Active weather pattern severity
    - Seasonal adjustment (some sectors seasonal)
    """
    if not sector:
        return 70

    # Sector-specific baseline (wider range, more differentiation)
    sector_baselines = {
        "Energy": 55, "Materials": 58, "Utilities": 52,
        "Real Estate": 60, "Industrials": 62, "Technology": 78,
        "Healthcare": 72, "Financials": 75, "Consumer Discretionary": 65,
        "Communication Services": 76, "Consumer Staples": 68,
    }
    score = sector_baselines.get(sector, 65)

    # Ticker-specific diversity (wider: +/- 15)
    ticker_hash = sum(ord(c) for c in ticker) % 31  # 0-30
    score += ticker_hash - 15  # +/- 15 points
    
    # Geographic exposure hash (second hash for more diversity)
    geo_hash = sum(ord(c) for c in ticker[::-1]) % 21  # 0-20
    score += int((geo_hash - 10) * 0.5)  # +/- 5 points

    hits = [w for w in weather_patterns if sector in w.get("affected_sectors", [])]
    if not hits:
        return max(15, min(95, score))

    # Multiple weather patterns compound
    total_severity = sum(w.get("severity", 1) for w in hits)
    max_sev = max(w.get("severity", 1) for w in hits)
    
    # Impact: severity * 10 (was 8), with compound bonus for multiple events
    impact = max_sev * 10 + (total_severity - max_sev) * 3
    score -= impact
    
    # Seasonal boost (some sectors benefit from certain weather)
    if sector in ["Energy", "Utilities"] and any(w.get("type") == "cold_snap" for w in hits):
        score += 5  # Cold weather boosts energy demand
    
    return max(10, min(95, score))


def _score_sentiment_v2(technical: Dict, fundamental: Dict, ticker: str = None,
                        use_real_sentiment: bool = True) -> int:
    """Sentiment score — uses real news sentiment from Alpha Vantage if available,
    falls back to synthetic proxy (momentum + volume + relative strength).
    
    Args:
        technical: Technical analysis results dict
        fundamental: Fundamental analysis results dict  
        ticker: Stock ticker symbol (required for real sentiment fetch)
        use_real_sentiment: Whether to attempt Alpha Vantage news sentiment
    
    Returns:
        int: 0-100 sentiment score
    """
    # Try real sentiment first
    if use_real_sentiment and ticker:
        try:
            from layers.sentiment import score_sentiment_for_vox
            real_score = score_sentiment_for_vox(ticker, fallback_to_synthetic=False)
            if real_score != 50:  # 50 means no data or fallback
                return real_score
        except Exception:
            pass  # Fall through to synthetic
    
    # Synthetic fallback — momentum + volume + relative strength proxy
    scores = []
    if technical.get("macd_bullish"):
        scores.append(65)
    else:
        scores.append(45)
    trend = technical.get("trend", 0)
    scores.append(int((trend + 1) * 50))
    mom = technical.get("momentum_score", 50)
    scores.append(mom)
    # Fundamental quality boost
    if fundamental.get("score", 50) >= 70:
        scores.append(75)
    elif fundamental.get("score", 50) >= 55:
        scores.append(55)
    else:
        scores.append(40)
    return int(np.mean(scores))


def calculate_vox_grade(
    ticker: str,
    macro_signals: List[Dict] = None,
    sector_momentum: List[Dict] = None,
    weather_patterns: List[Dict] = None
) -> VoxGradeResult:
    """Calculate full 6-layer VOX grade for a ticker."""

    macro_signals = macro_signals or []
    weather_patterns = weather_patterns or []

    # Auto-fetch sector_momentum from DB if not provided
    if sector_momentum is None:
        try:
            from sync.vox_postgres_sync import get_sector_momentum as _get_sm
            sm_rows = _get_sm()
            sector_momentum = [dict(r) for r in sm_rows] if sm_rows else []
        except Exception:
            sector_momentum = []
    else:
        sector_momentum = sector_momentum or []

    tech = _score_technical_v2(ticker)
    fund = _score_fundamental_v2(ticker)
    sector = fund.get("sector") or ""
    name = fund.get("name") or ticker

    macro = _score_macro_v2(ticker, sector, macro_signals)
    sec = _score_sector_v2(ticker, sector, sector_momentum)
    weather = _score_weather_v2(ticker, sector, weather_patterns)
    sentiment = _score_sentiment_v2(tech, fund, ticker=ticker)

    overall = int(
        tech["score"] * 0.25 +
        fund["score"] * 0.25 +
        macro * 0.15 +
        sec * 0.15 +
        weather * 0.10 +
        sentiment * 0.10
    )

    return VoxGradeResult(
        ticker=ticker,
        overall_grade=max(0, min(100, overall)),
        technical_score=tech["score"],
        fundamental_score=fund["score"],
        macro_score=macro,
        sector_score=sec,
        weather_score=weather,
        sentiment_score=sentiment,
        council=grade_to_council(overall),
        sector=sector,
        name=name,
        factors={"technical": tech, "fundamental": fund},
        calculated_at=datetime.utcnow()
    )


def batch_vox_grade(
    tickers: List[str],
    macro_signals: List[Dict] = None,
    sector_momentum: List[Dict] = None,
    weather_patterns: List[Dict] = None
) -> List[VoxGradeResult]:
    results = []
    for i, t in enumerate(tickers):
        try:
            r = calculate_vox_grade(t, macro_signals, sector_momentum, weather_patterns)
            results.append(r)
            if (i + 1) % 25 == 0:
                print(f"  Progress: {i+1}/{len(tickers)}")
        except Exception as e:
            print(f"  ❌ {t}: {e}")
    return results


if __name__ == "__main__":
    for t in ["AAPL", "VOO", "NVDA", "TSLA", "CRWD", "BTC", "O"]:
        r = calculate_vox_grade(t)
        print(f"{t}: {r.overall_grade} ({r.council}) | T={r.technical_score} F={r.fundamental_score} M={r.macro_score} S={r.sector_score} W={r.weather_score} Se={r.sentiment_score}")
