"""
Analyse-module: berekent financiële statistieken op koersdata.
"""

import numpy as np
import pandas as pd


def _get_price_series(prices_df):
    """Haalt prijsserie op uit DataFrame, ongeacht kolom-casing."""
    for col in ["close", "Close", "adj_close", "Adj Close"]:
        if col in prices_df.columns:
            series = prices_df[col].dropna()
            if not series.empty:
                return series
    return pd.Series(dtype=float)


def calculate_returns(prices, period="daily"):
    if period == "daily":
        return prices.pct_change().dropna()
    elif period == "weekly":
        return prices.resample("W").last().pct_change().dropna()
    elif period == "monthly":
        return prices.resample("ME").last().pct_change().dropna()
    elif period == "yearly":
        return prices.resample("YE").last().pct_change().dropna()
    else:
        raise ValueError(f"Onbekende periode: {period}")


def total_return(prices):
    if len(prices) < 2:
        return 0.0
    return (prices.iloc[-1] / prices.iloc[0] - 1) * 100


def annualized_return(prices):
    if len(prices) < 2:
        return 0.0
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return ((prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1) * 100


def annualized_volatility(prices):
    daily_returns = calculate_returns(prices, "daily")
    if len(daily_returns) < 2:
        return 0.0
    return daily_returns.std() * np.sqrt(252) * 100


def max_drawdown(prices):
    if len(prices) < 2:
        return 0.0, None, None
    running_max = prices.cummax()
    drawdown = (prices - running_max) / running_max
    trough_idx = drawdown.idxmin()
    peak_idx = prices.loc[:trough_idx].idxmax()
    return drawdown.min() * 100, peak_idx, trough_idx


def sharpe_ratio(prices, risk_free_rate=0.02):
    daily_returns = calculate_returns(prices, "daily")
    if len(daily_returns) < 2:
        return 0.0
    excess_return = daily_returns.mean() * 252 - risk_free_rate
    volatility = daily_returns.std() * np.sqrt(252)
    if volatility == 0:
        return 0.0
    return excess_return / volatility


def calculate_all_metrics(prices_df):
    prices = _get_price_series(prices_df)
    if len(prices) < 2:
        return {}

    dd_pct, peak_date, trough_date = max_drawdown(prices)

    return {
        "start_date": prices.index[0].strftime("%Y-%m-%d"),
        "end_date": prices.index[-1].strftime("%Y-%m-%d"),
        "start_price": float(prices.iloc[0]),
        "end_price": float(prices.iloc[-1]),
        "total_return_pct": float(total_return(prices)),
        "annualized_return_pct": float(annualized_return(prices)),
        "annualized_volatility_pct": float(annualized_volatility(prices)),
        "max_drawdown_pct": float(dd_pct),
        "max_drawdown_peak": peak_date.strftime("%Y-%m-%d") if peak_date is not None else None,
        "max_drawdown_trough": trough_date.strftime("%Y-%m-%d") if trough_date is not None else None,
        "sharpe_ratio": float(sharpe_ratio(prices)),
        "n_trading_days": len(prices),
    }


def yearly_returns(prices_df):
    prices = _get_price_series(prices_df)
    if prices.empty:
        return pd.Series(dtype=float)
    yearly = prices.resample("YE").last()
    returns = yearly.pct_change() * 100
    returns.index = returns.index.year
    return returns.dropna()


def rolling_volatility(prices_df, window=30):
    prices = _get_price_series(prices_df)
    if prices.empty:
        return pd.Series(dtype=float)
    daily_returns = prices.pct_change()
    return daily_returns.rolling(window=window).std() * np.sqrt(252) * 100


def normalize_for_comparison(prices_df, base=100):
    prices = _get_price_series(prices_df)
    if len(prices) == 0:
        return prices
    return (prices / prices.iloc[0]) * base
