"""VOX Test Suite — pytest-based tests for grading engine, sentiment, and sync.

Run: pytest tests/ -v
"""
import os
import sys
import pytest
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from grading.vox_engine import calculate_vox_grade, VoxGradeResult
from layers.sentiment import _compute_synthetic_sentiment, score_sentiment_for_vox
from grading.technical import get_stock_data, calculate_rsi, calculate_macd, calculate_sma_trend
from grading.fundamental import score_fundamental


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_technical():
    """Sample technical indicators for testing."""
    return {
        "score": 65,
        "macd_bullish": True,
        "trend": 0.3,
        "momentum_score": 70,
    }

@pytest.fixture
def sample_fundamental():
    """Sample fundamental score for testing."""
    return {
        "score": 60,
        "pe_ratio": 20.5,
        "debt_to_equity": 0.4,
    }


# ---------------------------------------------------------------------------
# Synthetic Sentiment Tests
# ---------------------------------------------------------------------------

class TestSyntheticSentiment:
    """Test synthetic sentiment computation (no API calls)."""

    def test_bullish_technical(self, sample_technical, sample_fundamental):
        """Bullish technical indicators should score > 50."""
        score = _compute_synthetic_sentiment(sample_technical, sample_fundamental)
        assert 50 <= score <= 100
        assert isinstance(score, int)

    def test_bearish_technical(self, sample_fundamental):
        """Bearish technical indicators should score < 50."""
        bearish_tech = {
            "score": 40,
            "macd_bullish": False,
            "trend": -0.4,
            "momentum_score": 30,
        }
        score = _compute_synthetic_sentiment(bearish_tech, sample_fundamental)
        assert 0 <= score <= 50

    def test_neutral(self):
        """Neutral indicators should score ~50."""
        neutral = {
            "score": 50,
            "macd_bullish": False,
            "trend": 0.0,
            "momentum_score": 50,
        }
        fund = {"score": 50}
        score = _compute_synthetic_sentiment(neutral, fund)
        assert 45 <= score <= 55

    def test_no_api_calls(self):
        """Synthetic sentiment should not require API keys."""
        # Clear any API keys
        os.environ.pop('ALPHA_VANTAGE_API_KEY', None)
        os.environ.pop('ALPHA_VANTAGE_API_KEYS', None)
        score = score_sentiment_for_vox('AAPL')
        assert 0 <= score <= 100
        assert isinstance(score, int)


# ---------------------------------------------------------------------------
# Grade Engine Tests
# ---------------------------------------------------------------------------

class TestVoxGradeEngine:
    """Test VOX grade calculation for known tickers."""

    def test_grade_structure(self):
        """Grade result should have all 6 layers."""
        result = calculate_vox_grade('AAPL')
        assert isinstance(result, VoxGradeResult)
        assert hasattr(result, 'overall_grade')
        assert hasattr(result, 'technical_score')
        assert hasattr(result, 'fundamental_score')
        assert hasattr(result, 'macro_score')
        assert hasattr(result, 'sector_score')
        assert hasattr(result, 'weather_score')
        assert hasattr(result, 'sentiment_score')

    def test_grade_range(self):
        """Grade should be 0-100."""
        result = calculate_vox_grade('MSFT')
        assert 0 <= result.overall_grade <= 100
        assert 0 <= result.technical_score <= 100
        assert 0 <= result.fundamental_score <= 100

    def test_invalid_ticker(self):
        """Invalid ticker should return grade with error handling."""
        result = calculate_vox_grade('INVALID_TICKER_12345')
        assert result is not None
        assert 0 <= result.overall_grade <= 100
        # Technical should show error
        assert result.technical_score == 50  # Neutral on error

    def test_multiple_tickers(self):
        """Grading multiple tickers should work."""
        tickers = ['AAPL', 'MSFT', 'GOOGL']
        results = {}
        for t in tickers:
            result = calculate_vox_grade(t)
            results[t] = result.overall_grade
        
        assert len(results) == 3
        assert all(0 <= g <= 100 for g in results.values())


# ---------------------------------------------------------------------------
# Technical Analysis Tests
# ---------------------------------------------------------------------------

class TestTechnicalAnalysis:
    """Test technical indicator calculations."""

    def test_get_stock_data(self):
        """Should fetch stock data for valid ticker."""
        df = get_stock_data('AAPL', period='1mo')
        assert df is not None
        assert len(df) > 0
        assert 'Close' in df.columns

    def test_rsi_calculation(self):
        """RSI should be 0-100."""
        df = get_stock_data('AAPL', period='3mo')
        prices = df['Close']
        rsi = calculate_rsi(prices)
        assert 0 <= rsi <= 100

    def test_macd_calculation(self):
        """MACD should return two values."""
        df = get_stock_data('AAPL', period='3mo')
        prices = df['Close']
        macd, signal = calculate_macd(prices)
        assert isinstance(macd, float)
        assert isinstance(signal, float)

    def test_trend_calculation(self):
        """Trend should be -1 to +1."""
        df = get_stock_data('AAPL', period='3mo')
        prices = df['Close']
        trend = calculate_sma_trend(prices)
        assert -1 <= trend <= 1


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline(self):
        """Full pipeline: data → technical → fundamental → sentiment → grade."""
        ticker = 'NVDA'
        
        # Step 1: Get data
        df = get_stock_data(ticker, period='6mo')
        assert df is not None
        
        # Step 2: Calculate grade
        result = calculate_vox_grade(ticker)
        assert result is not None
        assert 0 <= result.overall_grade <= 100
        
        # Step 3: Verify all layers contributed
        assert result.technical_score > 0
        assert result.fundamental_score > 0
        assert result.sentiment_score > 0

    def test_grade_consistency(self):
        """Same ticker should produce similar grades on re-run."""
        ticker = 'TSLA'
        result1 = calculate_vox_grade(ticker)
        result2 = calculate_vox_grade(ticker)
        
        # Grades should be within 5 points (market data may shift slightly)
        assert abs(result1.overall_grade - result2.overall_grade) <= 5


# ---------------------------------------------------------------------------
# Performance Tests
# ---------------------------------------------------------------------------

class TestPerformance:
    """Test grading performance."""

    def test_single_ticker_speed(self):
        """Single ticker should grade in < 5 seconds."""
        import time
        start = time.time()
        calculate_vox_grade('AAPL')
        elapsed = time.time() - start
        assert elapsed < 5.0

    def test_batch_speed(self):
        """10 tickers should grade in < 30 seconds."""
        import time
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'WMT']
        start = time.time()
        for t in tickers:
            calculate_vox_grade(t)
        elapsed = time.time() - start
        assert elapsed < 30.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
