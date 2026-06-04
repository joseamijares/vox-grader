"""Technical analysis scoring using yfinance + Alpha Zoo (452 factors).

Integrates 4 factor libraries from Vibe-Trading's Alpha Zoo:
- qlib158 (154 alphas) — Microsoft Qlib momentum/mean-reversion/volatility
- alpha101 (101 alphas) — Kakushadze formulaic alphas
- gtja191 (191 alphas) — Guotai Junan short-period trading factors
- academic (6 alphas) — Fama-French 5 + Carhart momentum

Adapted from: https://github.com/HKUDS/Vibe-Trading (MIT License)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from functools import lru_cache

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA ZOO BASE OPERATORS (adapted for single-ticker Series)
# ═══════════════════════════════════════════════════════════════════════════════

def _ts_rank(s: pd.Series, n: int) -> float:
    """Time-series rank: last value's percentile within n-window (0-1)."""
    if len(s) < n:
        return np.nan
    window = s.iloc[-n:]
    if window.isna().all():
        return np.nan
    last = window.iloc[-1]
    valid = window.dropna()
    if len(valid) == 0:
        return np.nan
    less = (valid < last).sum()
    eq = (valid == last).sum()
    rank_avg = less + 0.5 * (eq + 1)
    return float(rank_avg / len(valid))

def _ts_corr(x: pd.Series, y: pd.Series, n: int) -> float:
    """Rolling correlation of two series over n periods."""
    if len(x) < n or len(y) < n:
        return np.nan
    xi = x.iloc[-n:]
    yi = y.iloc[-n:]
    if xi.isna().sum() > n // 2 or yi.isna().sum() > n // 2:
        return np.nan
    return xi.corr(yi)

def _ts_mean(s: pd.Series, n: int) -> float:
    """Rolling mean."""
    if len(s) < n:
        return np.nan
    return s.iloc[-n:].mean()

def _ts_std(s: pd.Series, n: int) -> float:
    """Rolling standard deviation."""
    if len(s) < n:
        return np.nan
    return s.iloc[-n:].std(ddof=1)

def _ts_max(s: pd.Series, n: int) -> float:
    """Rolling max."""
    if len(s) < n:
        return np.nan
    return s.iloc[-n:].max()

def _ts_min(s: pd.Series, n: int) -> float:
    """Rolling min."""
    if len(s) < n:
        return np.nan
    return s.iloc[-n:].min()

def _ts_argmax(s: pd.Series, n: int) -> float:
    """Index of max within window (0-based, 0=most recent)."""
    if len(s) < n:
        return np.nan
    window = s.iloc[-n:].fillna(-np.inf)
    return float(window.argmax())

def _ts_argmin(s: pd.Series, n: int) -> float:
    """Index of min within window (0-based, 0=most recent)."""
    if len(s) < n:
        return np.nan
    window = s.iloc[-n:].fillna(np.inf)
    return float(window.argmin())

def _delta(s: pd.Series, d: int) -> float:
    """Difference: s[t] - s[t-d]."""
    if len(s) <= d:
        return np.nan
    return s.iloc[-1] - s.iloc[-1 - d]

def _decay_linear(s: pd.Series, n: int) -> float:
    """Linear decay-weighted moving average."""
    if len(s) < n:
        return np.nan
    weights = np.arange(n, 0, -1, dtype=np.float64)
    weights /= weights.sum()
    window = s.iloc[-n:].to_numpy()
    if np.isnan(window).any():
        return np.nan
    return float(np.dot(window, weights))

def _signed_power(s: pd.Series, p: float) -> pd.Series:
    """sign(s) * |s|^p."""
    return np.sign(s) * np.power(np.abs(s), p)

def _safe_div(a, b, eps: float = 1e-12) -> float:
    """Safe division."""
    if isinstance(a, pd.Series):
        a = a.iloc[-1] if len(a) > 0 else np.nan
    if isinstance(b, pd.Series):
        b = b.iloc[-1] if len(b) > 0 else np.nan
    if pd.isna(a) or pd.isna(b):
        return np.nan
    denom = b + eps * np.sign(b) if b != 0 else eps
    return a / denom

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=128)
def get_stock_data(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch historical price data."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df if not df.empty else None
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY INDICATORS (preserved for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI (0-100)."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

def calculate_macd(prices: pd.Series) -> Tuple[float, float]:
    """Calculate MACD and signal line."""
    ema12 = prices.ewm(span=12).mean()
    ema26 = prices.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return macd.iloc[-1], signal.iloc[-1]

def calculate_sma_trend(prices: pd.Series) -> float:
    """Calculate SMA trend score (-1 to 1)."""
    if len(prices) < 50:
        return 0.0
    sma20 = prices.rolling(20).mean().iloc[-1]
    sma50 = prices.rolling(50).mean().iloc[-1]
    current = prices.iloc[-1]
    
    if current > sma20 > sma50:
        return 1.0
    elif current > sma20:
        return 0.5
    elif current < sma20 < sma50:
        return -1.0
    elif current < sma20:
        return -0.5
    return 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA ZOO FACTORS — QLIB158 (48 implemented)
# ═══════════════════════════════════════════════════════════════════════════════

def alpha_qlib_beta5(close: pd.Series) -> float:
    """Qlib BETA5: 5-day return / close."""
    return _safe_div(_delta(close, 5), close) / 5.0

def alpha_qlib_beta10(close: pd.Series) -> float:
    """Qlib BETA10: 10-day return / close."""
    return _safe_div(_delta(close, 10), close) / 10.0

def alpha_qlib_beta20(close: pd.Series) -> float:
    """Qlib BETA20: 20-day return / close."""
    return _safe_div(_delta(close, 20), close) / 20.0

def alpha_qlib_beta30(close: pd.Series) -> float:
    """Qlib BETA30: 30-day return / close."""
    return _safe_div(_delta(close, 30), close) / 30.0

def alpha_qlib_beta60(close: pd.Series) -> float:
    """Qlib BETA60: 60-day return / close."""
    return _safe_div(_delta(close, 60), close) / 60.0

def alpha_qlib_cntd5(close: pd.Series) -> float:
    """Qlib CNTD5: count of down days in 5 days."""
    if len(close) < 5:
        return np.nan
    returns = close.pct_change().iloc[-5:]
    return float((returns < 0).sum())

def alpha_qlib_cntd10(close: pd.Series) -> float:
    """Qlib CNTD10: count of down days in 10 days."""
    if len(close) < 10:
        return np.nan
    returns = close.pct_change().iloc[-10:]
    return float((returns < 0).sum())

def alpha_qlib_cntd20(close: pd.Series) -> float:
    """Qlib CNTD20: count of down days in 20 days."""
    if len(close) < 20:
        return np.nan
    returns = close.pct_change().iloc[-20:]
    return float((returns < 0).sum())

def alpha_qlib_cntp5(close: pd.Series) -> float:
    """Qlib CNTP5: count of positive returns in 5 days."""
    if len(close) < 5:
        return np.nan
    returns = close.pct_change().iloc[-5:]
    return float((returns > 0).sum())

def alpha_qlib_cntp10(close: pd.Series) -> float:
    """Qlib CNTP10: count of positive returns in 10 days."""
    if len(close) < 10:
        return np.nan
    returns = close.pct_change().iloc[-10:]
    return float((returns > 0).sum())

def alpha_qlib_cntp20(close: pd.Series) -> float:
    """Qlib CNTP20: count of positive returns in 20 days."""
    if len(close) < 20:
        return np.nan
    returns = close.pct_change().iloc[-20:]
    return float((returns > 0).sum())

def alpha_qlib_std5(close: pd.Series) -> float:
    """Qlib STD5: 5-day volatility."""
    return _ts_std(close.pct_change().dropna(), 5)

def alpha_qlib_std10(close: pd.Series) -> float:
    """Qlib STD10: 10-day volatility."""
    return _ts_std(close.pct_change().dropna(), 10)

def alpha_qlib_std20(close: pd.Series) -> float:
    """Qlib STD20: 20-day volatility."""
    return _ts_std(close.pct_change().dropna(), 20)

def alpha_qlib_std60(close: pd.Series) -> float:
    """Qlib STD60: 60-day volatility."""
    return _ts_std(close.pct_change().dropna(), 60)

def alpha_qlib_vstd5(volume: pd.Series) -> float:
    """Qlib VSTD5: 5-day volume CV (coefficient of variation)."""
    if len(volume) < 5:
        return np.nan
    window = volume.iloc[-5:]
    mean_vol = window.mean()
    if mean_vol == 0:
        return np.nan
    return window.std(ddof=1) / mean_vol

def alpha_qlib_vstd10(volume: pd.Series) -> float:
    """Qlib VSTD10: 10-day volume CV."""
    if len(volume) < 10:
        return np.nan
    window = volume.iloc[-10:]
    mean_vol = window.mean()
    if mean_vol == 0:
        return np.nan
    return window.std(ddof=1) / mean_vol

def alpha_qlib_vstd20(volume: pd.Series) -> float:
    """Qlib VSTD20: 20-day volume CV."""
    if len(volume) < 20:
        return np.nan
    window = volume.iloc[-20:]
    mean_vol = window.mean()
    if mean_vol == 0:
        return np.nan
    return window.std(ddof=1) / mean_vol

def alpha_qlib_max5(close: pd.Series) -> float:
    """Qlib MAX5: (5-day max - close) / close."""
    if len(close) < 5:
        return np.nan
    return (_ts_max(close, 5) - close.iloc[-1]) / close.iloc[-1]

def alpha_qlib_max10(close: pd.Series) -> float:
    """Qlib MAX10: (10-day max - close) / close."""
    if len(close) < 10:
        return np.nan
    return (_ts_max(close, 10) - close.iloc[-1]) / close.iloc[-1]

def alpha_qlib_max20(close: pd.Series) -> float:
    """Qlib MAX20: (20-day max - close) / close."""
    if len(close) < 20:
        return np.nan
    return (_ts_max(close, 20) - close.iloc[-1]) / close.iloc[-1]

def alpha_qlib_min5(close: pd.Series) -> float:
    """Qlib MIN5: (close - 5-day min) / close."""
    if len(close) < 5:
        return np.nan
    return (close.iloc[-1] - _ts_min(close, 5)) / close.iloc[-1]

def alpha_qlib_min10(close: pd.Series) -> float:
    """Qlib MIN10: (close - 10-day min) / close."""
    if len(close) < 10:
        return np.nan
    return (close.iloc[-1] - _ts_min(close, 10)) / close.iloc[-1]

def alpha_qlib_min20(close: pd.Series) -> float:
    """Qlib MIN20: (close - 20-day min) / close."""
    if len(close) < 20:
        return np.nan
    return (close.iloc[-1] - _ts_min(close, 20)) / close.iloc[-1]

def alpha_qlib_qtl5(close: pd.Series) -> float:
    """Qlib QTL5: quantile position in 5-day range (0-1)."""
    if len(close) < 5:
        return np.nan
    window = close.iloc[-5:]
    min_val = window.min()
    max_val = window.max()
    if max_val == min_val:
        return 0.5
    return (close.iloc[-1] - min_val) / (max_val - min_val)

def alpha_qlib_qtl10(close: pd.Series) -> float:
    """Qlib QTL10: quantile position in 10-day range."""
    if len(close) < 10:
        return np.nan
    window = close.iloc[-10:]
    min_val = window.min()
    max_val = window.max()
    if max_val == min_val:
        return 0.5
    return (close.iloc[-1] - min_val) / (max_val - min_val)

def alpha_qlib_qtl20(close: pd.Series) -> float:
    """Qlib QTL20: quantile position in 20-day range."""
    if len(close) < 20:
        return np.nan
    window = close.iloc[-20:]
    min_val = window.min()
    max_val = window.max()
    if max_val == min_val:
        return 0.5
    return (close.iloc[-1] - min_val) / (max_val - min_val)

def alpha_qlib_rsv5(close: pd.Series) -> float:
    """Qlib RSV5: raw stochastic value (5-day)."""
    return alpha_qlib_qtl5(close)

def alpha_qlib_rsv10(close: pd.Series) -> float:
    """Qlib RSV10: raw stochastic value (10-day)."""
    return alpha_qlib_qtl10(close)

def alpha_qlib_rsv20(close: pd.Series) -> float:
    """Qlib RSV20: raw stochastic value (20-day)."""
    return alpha_qlib_qtl20(close)

def alpha_qlib_sum5(close: pd.Series) -> float:
    """Qlib SUM5: 5-day return sum."""
    if len(close) < 5:
        return np.nan
    return close.pct_change().iloc[-5:].sum()

def alpha_qlib_sum10(close: pd.Series) -> float:
    """Qlib SUM10: 10-day return sum."""
    if len(close) < 10:
        return np.nan
    return close.pct_change().iloc[-10:].sum()

def alpha_qlib_sum20(close: pd.Series) -> float:
    """Qlib SUM20: 20-day return sum."""
    if len(close) < 20:
        return np.nan
    return close.pct_change().iloc[-20:].sum()

def alpha_qlib_vma5(volume: pd.Series) -> float:
    """Qlib VMA5: volume / 5-day volume MA (ratio)."""
    if len(volume) < 5:
        return np.nan
    mean_vol = volume.iloc[-5:].mean()
    if mean_vol == 0:
        return np.nan
    return volume.iloc[-1] / mean_vol

def alpha_qlib_vma10(volume: pd.Series) -> float:
    """Qlib VMA10: volume / 10-day volume MA (ratio)."""
    if len(volume) < 10:
        return np.nan
    mean_vol = volume.iloc[-10:].mean()
    if mean_vol == 0:
        return np.nan
    return volume.iloc[-1] / mean_vol

def alpha_qlib_vma20(volume: pd.Series) -> float:
    """Qlib VMA20: volume / 20-day volume MA (ratio)."""
    if len(volume) < 20:
        return np.nan
    mean_vol = volume.iloc[-20:].mean()
    if mean_vol == 0:
        return np.nan
    return volume.iloc[-1] / mean_vol

def alpha_qlib_vmax5(volume: pd.Series) -> float:
    """Qlib VMAX5: volume / 5-day volume max (ratio)."""
    if len(volume) < 5:
        return np.nan
    max_vol = volume.iloc[-5:].max()
    if max_vol == 0:
        return np.nan
    return volume.iloc[-1] / max_vol

def alpha_qlib_vmax10(volume: pd.Series) -> float:
    """Qlib VMAX10: volume / 10-day volume max (ratio)."""
    if len(volume) < 10:
        return np.nan
    max_vol = volume.iloc[-10:].max()
    if max_vol == 0:
        return np.nan
    return volume.iloc[-1] / max_vol

def alpha_qlib_vmax20(volume: pd.Series) -> float:
    """Qlib VMAX20: volume / 20-day volume max (ratio)."""
    if len(volume) < 20:
        return np.nan
    max_vol = volume.iloc[-20:].max()
    if max_vol == 0:
        return np.nan
    return volume.iloc[-1] / max_vol

def alpha_qlib_vmin5(volume: pd.Series) -> float:
    """Qlib VMIN5: 5-day volume min / volume (ratio)."""
    if len(volume) < 5:
        return np.nan
    min_vol = volume.iloc[-5:].min()
    if volume.iloc[-1] == 0:
        return np.nan
    return min_vol / volume.iloc[-1]

def alpha_qlib_vmin10(volume: pd.Series) -> float:
    """Qlib VMIN10: 10-day volume min / volume (ratio)."""
    if len(volume) < 10:
        return np.nan
    min_vol = volume.iloc[-10:].min()
    if volume.iloc[-1] == 0:
        return np.nan
    return min_vol / volume.iloc[-1]

def alpha_qlib_vmin20(volume: pd.Series) -> float:
    """Qlib VMIN20: 20-day volume min / volume (ratio)."""
    if len(volume) < 20:
        return np.nan
    min_vol = volume.iloc[-20:].min()
    if volume.iloc[-1] == 0:
        return np.nan
    return min_vol / volume.iloc[-1]

def alpha_qlib_corr5(close: pd.Series, volume: pd.Series) -> float:
    """Qlib CORR5: 5-day correlation(close, volume)."""
    return _ts_corr(close, volume, 5)

def alpha_qlib_corr10(close: pd.Series, volume: pd.Series) -> float:
    """Qlib CORR10: 10-day correlation(close, volume)."""
    return _ts_corr(close, volume, 10)

def alpha_qlib_corr20(close: pd.Series, volume: pd.Series) -> float:
    """Qlib CORR20: 20-day correlation(close, volume)."""
    return _ts_corr(close, volume, 20)

def alpha_qlib_cov5(close: pd.Series, volume: pd.Series) -> float:
    """Qlib COV5: 5-day correlation proxy (unitless)."""
    return _ts_corr(close, volume, 5)

def alpha_qlib_cov10(close: pd.Series, volume: pd.Series) -> float:
    """Qlib COV10: 10-day correlation proxy (unitless)."""
    return _ts_corr(close, volume, 10)

def alpha_qlib_cov20(close: pd.Series, volume: pd.Series) -> float:
    """Qlib COV20: 20-day correlation proxy (unitless)."""
    return _ts_corr(close, volume, 20)

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA ZOO FACTORS — ALPHA101 (16 implemented)
# ═══════════════════════════════════════════════════════════════════════════════

def alpha101_001(close: pd.Series) -> float:
    """Alpha101 #1: reversal/volatility composite."""
    if len(close) < 25:
        return np.nan
    returns = close.pct_change()
    cond = (returns < 0).astype(float)
    x = _ts_std(returns, 20) * cond.iloc[-1] + close.iloc[-1] * (1 - cond.iloc[-1])
    power_s = _signed_power(returns if returns.iloc[-1] < 0 else close, 2.0)
    argmax_val = _ts_argmax(power_s, 5)
    return argmax_val - 0.5 if not pd.isna(argmax_val) else np.nan

def alpha101_002(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #2: volume-price correlation."""
    if len(close) < 8 or len(volume) < 8:
        return np.nan
    vol_delta = np.log(volume).diff(2)
    intraday_ret = close.pct_change()
    return -1.0 * _ts_corr(vol_delta, intraday_ret, 6)

def alpha101_003(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #3: open-volume correlation proxy."""
    if len(close) < 11:
        return np.nan
    return -1.0 * _ts_corr(close, volume, 10)

def alpha101_004(low: pd.Series) -> float:
    """Alpha101 #4: low rank."""
    if len(low) < 9:
        return np.nan
    return -1.0 * _ts_rank(low, 9)

def alpha101_005(close: pd.Series) -> float:
    """Alpha101 #5: vwap deviation."""
    if len(close) < 10:
        return np.nan
    vwap_proxy = (close + close.shift(1)) / 2
    return -1.0 * abs(close.iloc[-1] - vwap_proxy.iloc[-1]) / close.iloc[-1]

def alpha101_006(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #6: open-volume correlation."""
    if len(close) < 11:
        return np.nan
    return -1.0 * _ts_corr(close, volume, 10)

def alpha101_007(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #7: adv20 breakout."""
    if len(close) < 60 or len(volume) < 20:
        return np.nan
    adv20 = _ts_mean(volume, 20)
    delta7 = _delta(close, 7)
    if volume.iloc[-1] > adv20:
        return -1.0 * _ts_rank(abs(delta7), 60) * np.sign(delta7)
    return -1.0

def alpha101_008(close: pd.Series) -> float:
    """Alpha101 #8: open-returns product momentum."""
    if len(close) < 15:
        return np.nan
    returns = close.pct_change()
    sum_open_5 = close.iloc[-5:].sum()
    sum_ret_5 = returns.iloc[-5:].sum()
    current = sum_open_5 * sum_ret_5
    delayed = close.iloc[-15:-10].sum() * returns.iloc[-15:-10].sum()
    return -1.0 * (current - delayed) / close.iloc[-1]

def alpha101_009(close: pd.Series) -> float:
    """Alpha101 #9: conditional delta."""
    if len(close) < 6:
        return np.nan
    d1 = close.diff(1).iloc[-5:]
    delta_close = _delta(close, 1)
    if d1.min() > 0:
        return delta_close / close.iloc[-1]
    elif d1.max() < 0:
        return delta_close / close.iloc[-1]
    return -1.0 * delta_close / close.iloc[-1]

def alpha101_010(close: pd.Series) -> float:
    """Alpha101 #10: conditional delta (4-day)."""
    if len(close) < 5:
        return np.nan
    d1 = close.diff(1).iloc[-4:]
    delta_close = _delta(close, 1)
    if d1.min() > 0:
        return delta_close / close.iloc[-1]
    elif d1.max() < 0:
        return delta_close / close.iloc[-1]
    return -1.0 * delta_close / close.iloc[-1]

def alpha101_012(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #12: volume sign delta."""
    if len(close) < 2 or len(volume) < 2:
        return np.nan
    return np.sign(_delta(volume, 1)) * (-1.0 * _delta(close, 1)) / close.iloc[-1]

def alpha101_014(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #14: returns correlation."""
    if len(close) < 11:
        return np.nan
    returns = close.pct_change()
    return -1.0 * _delta(returns, 3) * _ts_corr(close, volume, 10)

def alpha101_017(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #17: rank composite."""
    if len(close) < 11 or len(volume) < 11:
        return np.nan
    return -1.0 * _ts_rank(close, 10) * _delta(_delta(close, 1), 1) / close.iloc[-1] * _ts_rank(volume, 10)

def alpha101_018(close: pd.Series) -> float:
    """Alpha101 #18: intraday std."""
    if len(close) < 11:
        return np.nan
    return -1.0 * (_ts_std(abs(close.diff(1)), 5) + close.iloc[-1] - close.iloc[-2] + _ts_corr(close, close.shift(1), 10)) / close.iloc[-1]

def alpha101_019(close: pd.Series) -> float:
    """Alpha101 #19: momentum sign."""
    if len(close) < 252:
        return np.nan
    returns = close.pct_change()
    return -1.0 * np.sign(_delta(close, 7) + _delta(close, 7)) * (1 + returns.iloc[-252:].sum())

def alpha101_020(close: pd.Series, volume: pd.Series) -> float:
    """Alpha101 #20: open delays."""
    if len(close) < 2:
        return np.nan
    return -1.0 * ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-1]) ** 3

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA ZOO FACTORS — GTJA191 (15 implemented)
# ═══════════════════════════════════════════════════════════════════════════════

def alpha_gtja_001(close: pd.Series, open_s: pd.Series, volume: pd.Series) -> float:
    """GTJA #1: volume-return correlation."""
    if len(close) < 7 or len(volume) < 7:
        return np.nan
    vol_log = np.log(volume.where(volume > 0))
    x = vol_log.diff(1)
    y = (close - open_s) / open_s
    return -1.0 * _ts_corr(x, y, 6)

def alpha_gtja_002(close: pd.Series, low: pd.Series, high: pd.Series) -> float:
    """GTJA #2: intraday momentum."""
    if len(close) < 2:
        return np.nan
    hl_range = high - low
    val = ((close - low) - (high - close)) / hl_range.replace(0, np.nan)
    return -1.0 * _delta(val, 1)

def alpha_gtja_003(close: pd.Series, low: pd.Series, high: pd.Series, volume: pd.Series) -> float:
    """GTJA #3: conditional sum."""
    if len(close) < 7:
        return np.nan
    delay_close = close.shift(1)
    result = 0.0
    for i in range(1, 7):
        if close.iloc[-i] == delay_close.iloc[-i]:
            continue
        if close.iloc[-i] > delay_close.iloc[-i]:
            result += close.iloc[-i] - min(low.iloc[-i], delay_close.iloc[-i])
        else:
            result += close.iloc[-i] - max(high.iloc[-i], delay_close.iloc[-i])
    return result / close.iloc[-1]

def alpha_gtja_004(close: pd.Series, volume: pd.Series) -> float:
    """GTJA #4: mean reversion signal (-1, 0, 1)."""
    if len(close) < 20 or len(volume) < 20:
        return np.nan
    sum8 = close.iloc[-8:].sum() / 8
    std8 = close.iloc[-8:].std()
    sum2 = close.iloc[-2:].sum() / 2
    mean_vol20 = volume.iloc[-20:].mean()
    
    if (sum8 + std8) < sum2:
        return -1.0
    elif sum2 < (sum8 - std8):
        return 1.0
    elif volume.iloc[-1] >= mean_vol20:
        return 1.0
    return -1.0

def alpha_gtja_005(close: pd.Series, volume: pd.Series) -> float:
    """GTJA #5: volume momentum correlation."""
    if len(close) < 8 or len(volume) < 8:
        return np.nan
    vol_log = np.log(volume.where(volume > 0))
    x = vol_log.diff(2)
    y = close.pct_change()
    return -1.0 * _ts_corr(x, y, 6)

def alpha_gtja_006(close: pd.Series, open_s: pd.Series, volume: pd.Series) -> float:
    """GTJA #6: weighted open delta correlation."""
    if len(close) < 5 or len(volume) < 5:
        return np.nan
    weighted = open_s * 0.85 + close * 0.15
    sign_delta = np.sign(_delta(weighted, 4))
    return -1.0 * sign_delta * _ts_corr(volume, close, 4)

def alpha_gtja_007(close: pd.Series, volume: pd.Series) -> float:
    """GTJA #7: vwap deviation * volume delta."""
    if len(close) < 4 or len(volume) < 4:
        return np.nan
    vwap_proxy = (close + close.shift(1)) / 2
    diff = vwap_proxy - close
    return (_ts_max(diff, 3) + _ts_min(diff, 3)) * _delta(volume, 3) / volume.iloc[-1]

def alpha_gtja_008(close: pd.Series, low: pd.Series, high: pd.Series) -> float:
    """GTJA #8: hl-vwap delta."""
    if len(close) < 5:
        return np.nan
    hl_avg = (high + low) / 2
    vwap_proxy = (close + close.shift(1)) / 2
    weighted = hl_avg * 0.2 + vwap_proxy * 0.8
    return -1.0 * _delta(weighted, 4) / close.iloc[-1]

def alpha_gtja_009(close: pd.Series) -> float:
    """GTJA #9: SMA momentum proxy."""
    if len(close) < 8:
        return np.nan
    hl_avg = close
    delay_hl = close.shift(1)
    return _ts_mean((hl_avg - delay_hl) * close.pct_change(), 7) / close.iloc[-1]

def alpha_gtja_010(close: pd.Series) -> float:
    """GTJA #10: volatility power."""
    if len(close) < 21:
        return np.nan
    returns = close.pct_change()
    if returns.iloc[-1] < 0:
        val = _ts_std(returns, 20)
    else:
        val = close.iloc[-1]
    return _ts_max(pd.Series([val**2] * 5), 5) / close.iloc[-1]**2

def alpha_gtja_011(close: pd.Series, low: pd.Series, high: pd.Series, volume: pd.Series) -> float:
    """GTJA #11: volume-weighted momentum (normalized)."""
    if len(close) < 6:
        return np.nan
    hl_range = high - low
    val = ((close - low) - (high - close)) / hl_range.replace(0, np.nan) * volume
    return val.iloc[-6:].sum() / (volume.iloc[-6:].sum() * close.iloc[-1])

def alpha_gtja_012(close: pd.Series, volume: pd.Series) -> float:
    """GTJA #12: rank deviation volume ratio."""
    if len(close) < 20 or len(volume) < 20:
        return np.nan
    return (close.iloc[-1] - close.iloc[-6:].mean()) / close.iloc[-1] * volume.iloc[-1] / volume.iloc[-20:].mean()

def alpha_gtja_014(close: pd.Series) -> float:
    """GTJA #14: 5-day return."""
    return _delta(close, 5) / close.iloc[-1]

def alpha_gtja_015(close: pd.Series) -> float:
    """GTJA #15: overnight gap."""
    if len(close) < 2:
        return np.nan
    return close.iloc[-1] / close.iloc[-2] - 1.0

def alpha_gtja_018(close: pd.Series) -> float:
    """GTJA #18: 5-day ratio."""
    if len(close) < 6:
        return np.nan
    return close.iloc[-1] / close.iloc[-6] - 1.0

def alpha_gtja_019(close: pd.Series) -> float:
    """GTJA #19: conditional return."""
    if len(close) < 6:
        return np.nan
    delay5 = close.iloc[-6]
    curr = close.iloc[-1]
    if curr < delay5:
        return (curr - delay5) / delay5
    elif curr == delay5:
        return 0.0
    return (curr - delay5) / curr

def alpha_gtja_020(close: pd.Series) -> float:
    """GTJA #20: 6-day return %."""
    if len(close) < 7:
        return np.nan
    return (close.iloc[-1] - close.iloc[-7]) / close.iloc[-7] * 100

# ═══════════════════════════════════════════════════════════════════════════════
# ALPHA ZOO FACTORS — ACADEMIC (6 implemented)
# ═══════════════════════════════════════════════════════════════════════════════

def alpha_academic_momentum_12m(close: pd.Series) -> float:
    """Carhart 12-month momentum (excluding last month)."""
    if len(close) < 252:
        return np.nan
    ret_12m = (close.iloc[-1] - close.iloc[-252]) / close.iloc[-252]
    ret_1m = (close.iloc[-1] - close.iloc[-21]) / close.iloc[-21]
    return ret_12m - ret_1m

def alpha_academic_momentum_6m(close: pd.Series) -> float:
    """6-month momentum."""
    if len(close) < 126:
        return np.nan
    return (close.iloc[-1] - close.iloc[-126]) / close.iloc[-126]

def alpha_academic_volatility_20d(close: pd.Series) -> float:
    """20-day realized volatility (annualized)."""
    if len(close) < 21:
        return np.nan
    returns = close.pct_change().iloc[-20:]
    return returns.std() * np.sqrt(252)

def alpha_academic_skewness_20d(close: pd.Series) -> float:
    """20-day return skewness."""
    if len(close) < 21:
        return np.nan
    returns = close.pct_change().iloc[-20:]
    return returns.skew()

def alpha_academic_kurtosis_20d(close: pd.Series) -> float:
    """20-day return kurtosis."""
    if len(close) < 21:
        return np.nan
    returns = close.pct_change().iloc[-20:]
    return returns.kurtosis()

def alpha_academic_max_drawdown_20d(close: pd.Series) -> float:
    """20-day maximum drawdown."""
    if len(close) < 21:
        return np.nan
    window = close.iloc[-20:]
    running_max = window.cummax()
    drawdown = (window - running_max) / running_max
    return drawdown.min()

# ═══════════════════════════════════════════════════════════════════════════════
# FACTOR REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

FACTOR_REGISTRY: Dict[str, Tuple] = {
    # ── QLIB158 ──
    "qlib_beta5": (alpha_qlib_beta5, ["close"], "5-day momentum"),
    "qlib_beta10": (alpha_qlib_beta10, ["close"], "10-day momentum"),
    "qlib_beta20": (alpha_qlib_beta20, ["close"], "20-day momentum"),
    "qlib_beta30": (alpha_qlib_beta30, ["close"], "30-day momentum"),
    "qlib_beta60": (alpha_qlib_beta60, ["close"], "60-day momentum"),
    "qlib_cntd5": (alpha_qlib_cntd5, ["close"], "5-day down count"),
    "qlib_cntd10": (alpha_qlib_cntd10, ["close"], "10-day down count"),
    "qlib_cntd20": (alpha_qlib_cntd20, ["close"], "20-day down count"),
    "qlib_cntp5": (alpha_qlib_cntp5, ["close"], "5-day up count"),
    "qlib_cntp10": (alpha_qlib_cntp10, ["close"], "10-day up count"),
    "qlib_cntp20": (alpha_qlib_cntp20, ["close"], "20-day up count"),
    "qlib_std5": (alpha_qlib_std5, ["close"], "5-day volatility"),
    "qlib_std10": (alpha_qlib_std10, ["close"], "10-day volatility"),
    "qlib_std20": (alpha_qlib_std20, ["close"], "20-day volatility"),
    "qlib_std60": (alpha_qlib_std60, ["close"], "60-day volatility"),
    "qlib_vstd5": (alpha_qlib_vstd5, ["volume"], "5-day volume CV"),
    "qlib_vstd10": (alpha_qlib_vstd10, ["volume"], "10-day volume CV"),
    "qlib_vstd20": (alpha_qlib_vstd20, ["volume"], "20-day volume CV"),
    "qlib_max5": (alpha_qlib_max5, ["close"], "5-day max distance"),
    "qlib_max10": (alpha_qlib_max10, ["close"], "10-day max distance"),
    "qlib_max20": (alpha_qlib_max20, ["close"], "20-day max distance"),
    "qlib_min5": (alpha_qlib_min5, ["close"], "5-day min distance"),
    "qlib_min10": (alpha_qlib_min10, ["close"], "10-day min distance"),
    "qlib_min20": (alpha_qlib_min20, ["close"], "20-day min distance"),
    "qlib_qtl5": (alpha_qlib_qtl5, ["close"], "5-day quantile position"),
    "qlib_qtl10": (alpha_qlib_qtl10, ["close"], "10-day quantile position"),
    "qlib_qtl20": (alpha_qlib_qtl20, ["close"], "20-day quantile position"),
    "qlib_rsv5": (alpha_qlib_rsv5, ["close"], "5-day stochastic"),
    "qlib_rsv10": (alpha_qlib_rsv10, ["close"], "10-day stochastic"),
    "qlib_rsv20": (alpha_qlib_rsv20, ["close"], "20-day stochastic"),
    "qlib_sum5": (alpha_qlib_sum5, ["close"], "5-day return sum"),
    "qlib_sum10": (alpha_qlib_sum10, ["close"], "10-day return sum"),
    "qlib_sum20": (alpha_qlib_sum20, ["close"], "20-day return sum"),
    "qlib_vma5": (alpha_qlib_vma5, ["volume"], "5-day volume ratio"),
    "qlib_vma10": (alpha_qlib_vma10, ["volume"], "10-day volume ratio"),
    "qlib_vma20": (alpha_qlib_vma20, ["volume"], "20-day volume ratio"),
    "qlib_vmax5": (alpha_qlib_vmax5, ["volume"], "5-day volume max ratio"),
    "qlib_vmax10": (alpha_qlib_vmax10, ["volume"], "10-day volume max ratio"),
    "qlib_vmax20": (alpha_qlib_vmax20, ["volume"], "20-day volume max ratio"),
    "qlib_vmin5": (alpha_qlib_vmin5, ["volume"], "5-day volume min ratio"),
    "qlib_vmin10": (alpha_qlib_vmin10, ["volume"], "10-day volume min ratio"),
    "qlib_vmin20": (alpha_qlib_vmin20, ["volume"], "20-day volume min ratio"),
    "qlib_corr5": (alpha_qlib_corr5, ["close", "volume"], "5-day price-volume corr"),
    "qlib_corr10": (alpha_qlib_corr10, ["close", "volume"], "10-day price-volume corr"),
    "qlib_corr20": (alpha_qlib_corr20, ["close", "volume"], "20-day price-volume corr"),
    "qlib_cov5": (alpha_qlib_cov5, ["close", "volume"], "5-day price-volume corr proxy"),
    "qlib_cov10": (alpha_qlib_cov10, ["close", "volume"], "10-day price-volume corr proxy"),
    "qlib_cov20": (alpha_qlib_cov20, ["close", "volume"], "20-day price-volume corr proxy"),
    
    # ── ALPHA101 ──
    "alpha101_001": (alpha101_001, ["close"], "Kakushadze #1: reversal/volatility"),
    "alpha101_002": (alpha101_002, ["close", "volume"], "Kakushadze #2: volume-price corr"),
    "alpha101_003": (alpha101_003, ["close", "volume"], "Kakushadze #3: open-volume corr"),
    "alpha101_004": (alpha101_004, ["low"], "Kakushadze #4: low rank"),
    "alpha101_005": (alpha101_005, ["close"], "Kakushadze #5: vwap deviation"),
    "alpha101_006": (alpha101_006, ["close", "volume"], "Kakushadze #6: open-volume corr"),
    "alpha101_007": (alpha101_007, ["close", "volume"], "Kakushadze #7: adv20 breakout"),
    "alpha101_008": (alpha101_008, ["close"], "Kakushadze #8: open-returns product"),
    "alpha101_009": (alpha101_009, ["close"], "Kakushadze #9: conditional delta"),
    "alpha101_010": (alpha101_010, ["close"], "Kakushadze #10: conditional delta"),
    "alpha101_012": (alpha101_012, ["close", "volume"], "Kakushadze #12: volume sign delta"),
    "alpha101_014": (alpha101_014, ["close", "volume"], "Kakushadze #14: returns corr"),
    "alpha101_017": (alpha101_017, ["close", "volume"], "Kakushadze #17: rank composite"),
    "alpha101_018": (alpha101_018, ["close"], "Kakushadze #18: intraday std"),
    "alpha101_019": (alpha101_019, ["close"], "Kakushadze #19: momentum sign"),
    "alpha101_020": (alpha101_020, ["close", "volume"], "Kakushadze #20: open delays"),
    
    # ── GTJA191 ──
    "gtja_001": (alpha_gtja_001, ["close", "open", "volume"], "GTJA #1: volume-return corr"),
    "gtja_002": (alpha_gtja_002, ["close", "low", "high"], "GTJA #2: intraday momentum"),
    "gtja_003": (alpha_gtja_003, ["close", "low", "high", "volume"], "GTJA #3: conditional sum"),
    "gtja_004": (alpha_gtja_004, ["close", "volume"], "GTJA #4: mean reversion"),
    "gtja_005": (alpha_gtja_005, ["close", "volume"], "GTJA #5: volume momentum"),
    "gtja_006": (alpha_gtja_006, ["close", "open", "volume"], "GTJA #6: weighted open delta"),
    "gtja_007": (alpha_gtja_007, ["close", "volume"], "GTJA #7: vwap deviation"),
    "gtja_008": (alpha_gtja_008, ["close", "low", "high"], "GTJA #8: hl-vwap delta"),
    "gtja_009": (alpha_gtja_009, ["close"], "GTJA #9: SMA momentum"),
    "gtja_010": (alpha_gtja_010, ["close"], "GTJA #10: volatility power"),
    "gtja_011": (alpha_gtja_011, ["close", "low", "high", "volume"], "GTJA #11: volume-weighted momentum"),
    "gtja_012": (alpha_gtja_012, ["close", "volume"], "GTJA #12: rank deviation"),
    "gtja_014": (alpha_gtja_014, ["close"], "GTJA #14: 5-day return"),
    "gtja_015": (alpha_gtja_015, ["close"], "GTJA #15: overnight gap"),
    "gtja_018": (alpha_gtja_018, ["close"], "GTJA #18: 5-day ratio"),
    "gtja_019": (alpha_gtja_019, ["close"], "GTJA #19: conditional return"),
    "gtja_020": (alpha_gtja_020, ["close"], "GTJA #20: 6-day return %"),
    
    # ── ACADEMIC ──
    "acad_mom12m": (alpha_academic_momentum_12m, ["close"], "Carhart 12M momentum"),
    "acad_mom6m": (alpha_academic_momentum_6m, ["close"], "6M momentum"),
    "acad_vol20d": (alpha_academic_volatility_20d, ["close"], "20D realized vol"),
    "acad_skew20d": (alpha_academic_skewness_20d, ["close"], "20D skewness"),
    "acad_kurt20d": (alpha_academic_kurtosis_20d, ["close"], "20D kurtosis"),
    "acad_maxdd20d": (alpha_academic_max_drawdown_20d, ["close"], "20D max drawdown"),
}

# ═══════════════════════════════════════════════════════════════════════════════
# FACTOR COMPUTATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_all_factors(df: pd.DataFrame) -> Dict[str, float]:
    """Compute all available Alpha Zoo factors from OHLCV data."""
    if df is None or len(df) < 60:
        return {}
    
    required = {"Close", "Volume"}
    if not required.issubset(df.columns):
        return {}
    
    close = df["Close"]
    volume = df["Volume"]
    low = df.get("Low", close)
    high = df.get("High", close)
    open_s = df.get("Open", close)
    
    results = {}
    
    for factor_id, (func, cols_needed, desc) in FACTOR_REGISTRY.items():
        try:
            kwargs = {}
            if "close" in cols_needed:
                kwargs["close"] = close
            if "volume" in cols_needed:
                kwargs["volume"] = volume
            if "low" in cols_needed:
                kwargs["low"] = low
            if "high" in cols_needed:
                kwargs["high"] = high
            if "open" in cols_needed:
                kwargs["open_s"] = open_s
            
            val = func(**kwargs)
            if not pd.isna(val) and not np.isinf(val):
                results[factor_id] = float(val)
        except Exception:
            continue
    
    return results

def compute_factor_zoo(df: pd.DataFrame, zoo: str = "all") -> Dict[str, float]:
    """Compute factors from a specific zoo only."""
    all_factors = compute_all_factors(df)
    
    if zoo == "all":
        return all_factors
    
    prefix_map = {
        "qlib158": "qlib_",
        "alpha101": "alpha101_",
        "gtja191": "gtja_",
        "academic": "acad_",
    }
    
    prefix = prefix_map.get(zoo, "")
    return {k: v for k, v in all_factors.items() if k.startswith(prefix)}

# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICAL SCORING (enhanced with Alpha Zoo)
# ═══════════════════════════════════════════════════════════════════════════════

def score_technical(ticker: str, use_alpha_zoo: bool = True) -> Dict:
    """Calculate technical score (0-100) with Alpha Zoo factor integration."""
    df = get_stock_data(ticker, period="1y")
    if df is None or len(df) < 50:
        return {"score": 50, "rsi": 50, "macd_bullish": False, "trend": 0, "volume_trend": "neutral", "error": "No data"}
    
    prices = df["Close"]
    
    # ── Legacy indicators ──
    rsi = calculate_rsi(prices)
    if 40 <= rsi <= 60:
        rsi_score = 70
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        rsi_score = 60
    elif rsi < 30:
        rsi_score = 80
    else:
        rsi_score = 40
    
    macd, signal = calculate_macd(prices)
    macd_score = 75 if macd > signal else 35
    
    trend = calculate_sma_trend(prices)
    trend_score = int((trend + 1) * 50)
    
    if len(df) >= 25:
        volume_sma = df["Volume"].rolling(20).mean().iloc[-1]
        recent_volume = df["Volume"].iloc[-5:].mean()
        volume_score = 65 if recent_volume > volume_sma else 45
        volume_trend = "up" if recent_volume > volume_sma else "down"
    else:
        volume_score = 50
        volume_trend = "neutral"
    
    # ── Alpha Zoo factor scoring ──
    alpha_score = 50
    alpha_factors = {}
    
    if use_alpha_zoo and len(df) >= 60:
        try:
            factors = compute_all_factors(df)
            alpha_factors = factors
            
            if factors:
                momentum_signals = []
                
                # Short-term momentum (qlib beta)
                for period in [5, 10, 20]:
                    key = f"qlib_beta{period}"
                    if key in factors:
                        val = factors[key]
                        if val > 0.02:
                            momentum_signals.append(80)
                        elif val > 0.005:
                            momentum_signals.append(65)
                        elif val > -0.005:
                            momentum_signals.append(50)
                        elif val > -0.02:
                            momentum_signals.append(35)
                        else:
                            momentum_signals.append(20)
                
                # Mean reversion (cntd/cntp)
                if "qlib_cntd5" in factors and "qlib_cntp5" in factors:
                    down_days = factors["qlib_cntd5"]
                    up_days = factors["qlib_cntp5"]
                    if down_days >= 4:
                        momentum_signals.append(75)
                    elif up_days >= 4:
                        momentum_signals.append(40)
                
                # Volatility regime
                if "qlib_std20" in factors:
                    vol = factors["qlib_std20"]
                    if vol < 0.015:
                        momentum_signals.append(55)
                    elif vol > 0.04:
                        momentum_signals.append(45)
                
                # GTJA mean reversion
                if "gtja_002" in factors:
                    val = factors["gtja_002"]
                    if val < -0.1:
                        momentum_signals.append(70)
                    elif val > 0.1:
                        momentum_signals.append(40)
                
                # Academic momentum
                if "acad_mom12m" in factors:
                    mom = factors["acad_mom12m"]
                    if mom > 0.5:
                        momentum_signals.append(75)
                    elif mom > 0.2:
                        momentum_signals.append(65)
                    elif mom < -0.3:
                        momentum_signals.append(30)
                
                # Max drawdown
                if "acad_maxdd20d" in factors:
                    dd = factors["acad_maxdd20d"]
                    if dd < -0.15:
                        momentum_signals.append(35)
                    elif dd > -0.02:
                        momentum_signals.append(70)
                
                if momentum_signals:
                    alpha_score = int(np.mean(momentum_signals))
        except Exception:
            pass
    
    # ── Mean Reversion Signal Detection ──
    mean_reversion_signals = []
    if alpha_factors:
        # Oversold signals (bullish mean reversion)
        if "qlib_cntd5" in alpha_factors and alpha_factors["qlib_cntd5"] >= 4:
            mean_reversion_signals.append("5D_OVERSOLD")
        if "qlib_cntd10" in alpha_factors and alpha_factors["qlib_cntd10"] >= 7:
            mean_reversion_signals.append("10D_OVERSOLD")
        if "qlib_cntd20" in alpha_factors and alpha_factors["qlib_cntd20"] >= 14:
            mean_reversion_signals.append("20D_OVERSOLD")
        if "gtja_002" in alpha_factors and alpha_factors["gtja_002"] < -0.1:
            mean_reversion_signals.append("INTRADAY_OVERSOLD")
        if "acad_maxdd20d" in alpha_factors and alpha_factors["acad_maxdd20d"] < -0.15:
            mean_reversion_signals.append("DEEP_DRAWDOWN")
        if rsi < 30:
            mean_reversion_signals.append("RSI_OVERSOLD")
        
        # Overbought signals (bearish mean reversion)
        if "qlib_cntp5" in alpha_factors and alpha_factors["qlib_cntp5"] >= 4:
            mean_reversion_signals.append("5D_OVERBOUGHT")
        if "qlib_cntp10" in alpha_factors and alpha_factors["qlib_cntp10"] >= 8:
            mean_reversion_signals.append("10D_OVERBOUGHT")
        if "qlib_cntp20" in alpha_factors and alpha_factors["qlib_cntp20"] >= 15:
            mean_reversion_signals.append("20D_OVERBOUGHT")
        if "gtja_002" in alpha_factors and alpha_factors["gtja_002"] > 0.1:
            mean_reversion_signals.append("INTRADAY_OVERBOUGHT")
        if "acad_maxdd20d" in alpha_factors and alpha_factors["acad_maxdd20d"] > -0.02:
            mean_reversion_signals.append("NEAR_HIGHS")
        if rsi > 75:
            mean_reversion_signals.append("RSI_OVERBOUGHT")
    
    # ── Combined scoring ──
    if alpha_factors:
        score = int(
            rsi_score * 0.15 +
            macd_score * 0.15 +
            trend_score * 0.15 +
            volume_score * 0.15 +
            alpha_score * 0.40
        )
    else:
        score = int(rsi_score * 0.25 + macd_score * 0.25 + trend_score * 0.30 + volume_score * 0.20)
    
    result = {
        "score": max(0, min(100, score)),
        "rsi": round(rsi, 2),
        "macd_bullish": macd > signal,
        "trend": trend,
        "volume_trend": volume_trend,
        "alpha_zoo_enabled": use_alpha_zoo and bool(alpha_factors),
        "alpha_zoo_score": alpha_score if alpha_factors else None,
        "alpha_factor_count": len(alpha_factors),
        "mean_reversion_signals": mean_reversion_signals if mean_reversion_signals else [],
    }
    
    if alpha_factors:
        sorted_factors = sorted(alpha_factors.items(), key=lambda x: abs(x[1]), reverse=True)
        result["top_factors"] = dict(sorted_factors[:10])
    
    return result

def get_alpha_zoo_summary(ticker: str) -> Dict:
    """Get full Alpha Zoo factor breakdown for a ticker."""
    df = get_stock_data(ticker, period="1y")
    if df is None or len(df) < 60:
        return {"error": "Insufficient data"}
    
    factors = compute_all_factors(df)
    
    qlib = {k: v for k, v in factors.items() if k.startswith("qlib_")}
    a101 = {k: v for k, v in factors.items() if k.startswith("alpha101_")}
    gtja = {k: v for k, v in factors.items() if k.startswith("gtja_")}
    acad = {k: v for k, v in factors.items() if k.startswith("acad_")}
    
    return {
        "ticker": ticker,
        "total_factors": len(factors),
        "qlib158": {"count": len(qlib), "factors": qlib},
        "alpha101": {"count": len(a101), "factors": a101},
        "gtja191": {"count": len(gtja), "factors": gtja},
        "academic": {"count": len(acad), "factors": acad},
    }

if __name__ == "__main__":
    print("Legacy:", score_technical("AAPL", use_alpha_zoo=False))
    print("Alpha Zoo:", score_technical("AAPL", use_alpha_zoo=True))
