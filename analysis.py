"""
Analyse-module: financiële statistieken + event-impact analyses.
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


# === Basis financiële metrics ===

def calculate_returns(prices, period="daily"):
    if period == "daily":
        return prices.pct_change().dropna()
    elif period == "weekly":
        return prices.resample("W").last().pct_change().dropna()
    elif period == "monthly":
        return prices.resample("ME").last().pct_change().dropna()
    elif period == "yearly":
        return prices.resample("YE").last().pct_change().dropna()


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


# === NIEUW: Event-impact analyses (fase 2) ===

def calculate_event_impact(prices_df, event_date, days_before=5, days_after=5):
    """
    Berekent koersbeweging rondom een event.

    Returns dict met:
      - return_pre_pct: rendement in dagen voor event
      - return_event_day_pct: rendement op event-dag zelf
      - return_post_pct: rendement in dagen na event
      - return_total_pct: totaal rendement (pre + event + post)
      - prices_around: dict met prijzen op key datums
    """
    prices = _get_price_series(prices_df)
    if prices.empty:
        return None

    event_date = pd.to_datetime(event_date).normalize()

    # Vind dichtstbijzijnde handelsdag op of na event
    available_dates = prices.index
    if event_date < available_dates.min() or event_date > available_dates.max():
        return None

    # Event-day price (eerste handelsdag op of na event_date)
    event_day_idx = available_dates.searchsorted(event_date)
    if event_day_idx >= len(available_dates):
        return None
    event_day_actual = available_dates[event_day_idx]

    # Pre-event: 'days_before' handelsdagen voor event
    pre_idx = event_day_idx - days_before
    if pre_idx < 0:
        return None
    pre_date = available_dates[pre_idx]

    # Post-event: 'days_after' handelsdagen na event-day
    post_idx = event_day_idx + days_after
    if post_idx >= len(available_dates):
        return None
    post_date = available_dates[post_idx]

    # Day before event (voor 'event-day return')
    day_before_idx = max(0, event_day_idx - 1)
    day_before_actual = available_dates[day_before_idx]

    pre_price = float(prices.iloc[pre_idx])
    day_before_price = float(prices.iloc[day_before_idx])
    event_price = float(prices.iloc[event_day_idx])
    post_price = float(prices.iloc[post_idx])

    return {
        "event_date_actual": event_day_actual.strftime("%Y-%m-%d"),
        "pre_date": pre_date.strftime("%Y-%m-%d"),
        "post_date": post_date.strftime("%Y-%m-%d"),
        "pre_price": pre_price,
        "event_price": event_price,
        "post_price": post_price,
        "return_pre_pct": (event_price / pre_price - 1) * 100,
        "return_event_day_pct": (event_price / day_before_price - 1) * 100 if day_before_price else 0,
        "return_post_pct": (post_price / event_price - 1) * 100,
        "return_total_pct": (post_price / pre_price - 1) * 100,
    }


def aggregate_event_impacts(prices_df, events_df, days_before=5, days_after=5):
    """
    Berekent event-impact voor alle events in events_df.

    events_df moet kolommen 'date' en 'beat' (of andere classifier) hebben.

    Returns DataFrame met event-impact per event.
    """
    if events_df.empty:
        return pd.DataFrame()

    results = []
    for _, event in events_df.iterrows():
        impact = calculate_event_impact(
            prices_df, event["date"],
            days_before=days_before, days_after=days_after
        )
        if impact is None:
            continue

        row = {
            "event_date": event["date"],
            **impact,
        }
        # Voeg event-eigenschappen toe
        for col in events_df.columns:
            if col != "date" and col not in row:
                row[col] = event[col]

        results.append(row)

    return pd.DataFrame(results)


def summarize_by_category(impacts_df, category_col="beat"):
    """
    Vat event-impacts samen per categorie (bv. beat/miss/inline).

    Returns DataFrame met gemiddelde, mediaan, std per categorie.
    """
    if impacts_df.empty or category_col not in impacts_df.columns:
        return pd.DataFrame()

    metrics = ["return_pre_pct", "return_event_day_pct", "return_post_pct", "return_total_pct"]

    summary = impacts_df.groupby(category_col)[metrics].agg(
        ["mean", "median", "std", "count"]
    )

    return summary


def cross_stock_event_response(all_impacts, response_col="return_post_pct", category_col="beat"):
    """
    Vergelijkt hoe verschillende aandelen reageren op events.

    all_impacts: DataFrame met kolommen ticker, beat, return_post_pct etc.
    Returns DataFrame met gemiddelde reactie per ticker per categorie.
    """
    if all_impacts.empty:
        return pd.DataFrame()

    if "ticker" not in all_impacts.columns or category_col not in all_impacts.columns:
        return pd.DataFrame()

    pivot = all_impacts.pivot_table(
        index="ticker",
        columns=category_col,
        values=response_col,
        aggfunc=["mean", "count"],
    )

    return pivot
