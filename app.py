"""
Streamlit dashboard - Cloud versie.
Haalt data direct op via yfinance met caching (24 uur).
Geen lokale database nodig.

Run lokaal met: streamlit run app.py
Of deploy via Streamlit Community Cloud.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

import analysis
from tickers import ALL_TICKERS, get_market


# Pagina-configuratie
st.set_page_config(
    page_title="Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# === Data ophalen met cache ===
# 24 uur cache - data wordt 1x per dag ververst per ticker

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_stock_data(ticker, period="20y"):
    """
    Haalt koersdata op via yfinance.
    Gecached voor 24 uur per ticker.
    """
    try:
        stock = yf.Ticker(ticker)
        prices = stock.history(period=period, auto_adjust=False)

        if prices.empty:
            return None

        # Tijdzone weghalen voor consistentie
        if prices.index.tz is not None:
            prices.index = prices.index.tz_localize(None)

        # Dividenden en splits ophalen
        actions = stock.actions if hasattr(stock, 'actions') else pd.DataFrame()
        dividends = pd.Series(dtype=float)
        splits = pd.Series(dtype=float)

        if not actions.empty:
            if actions.index.tz is not None:
                actions.index = actions.index.tz_localize(None)
            if "Dividends" in actions.columns:
                dividends = actions["Dividends"][actions["Dividends"] > 0]
            if "Stock Splits" in actions.columns:
                splits = actions["Stock Splits"][actions["Stock Splits"] > 0]

        # Bedrijfsinfo
        info = {}
        try:
            raw_info = stock.info
            info = {
                "sector": raw_info.get("sector"),
                "industry": raw_info.get("industry"),
                "currency": raw_info.get("currency", "USD"),
            }
        except Exception:
            pass

        return {
            "prices": prices,
            "dividends": dividends,
            "splits": splits,
            "info": info,
        }
    except Exception as e:
        st.error(f"Fout bij ophalen {ticker}: {e}")
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_multiple_stocks(tickers_tuple):
    """Haalt meerdere stocks tegelijk op (voor vergelijkings-pagina)."""
    results = {}
    for ticker in tickers_tuple:
        data = fetch_stock_data(ticker)
        if data is not None:
            results[ticker] = data
    return results


def get_currency_symbol(ticker):
    """Bepaalt valutasymbool op basis van markt."""
    if ticker.endswith((".AS", ".DE", ".PA")):
        return "€"
    return "$"


# === Pagina's ===

def page_single_stock():
    st.title("📈 Aandelen-analyse")

    options = {f"{name} ({ticker}) - {get_market(ticker)}": ticker
               for ticker, name in ALL_TICKERS.items()}

    with st.sidebar:
        st.header("⚙️ Instellingen")
        selected_label = st.selectbox(
            "Kies een aandeel",
            options=sorted(options.keys()),
        )
        selected_ticker = options[selected_label]

        period_options = {
            "1 jaar": "1y",
            "3 jaar": "3y",
            "5 jaar": "5y",
            "10 jaar": "10y",
            "20 jaar (max)": "max",
        }
        selected_period = st.selectbox(
            "Periode",
            options=list(period_options.keys()),
            index=4,
        )

        st.divider()
        show_volume = st.checkbox("Toon volume", value=True)
        show_dividends = st.checkbox("Toon dividenden", value=True)
        show_splits = st.checkbox("Toon aandelensplitsingen", value=True)
        log_scale = st.checkbox("Log-schaal (aanbevolen voor lange periodes)", value=False)

    # Data ophalen
    with st.spinner(f"📡 Data ophalen voor {selected_ticker}..."):
        data = fetch_stock_data(selected_ticker, period=period_options[selected_period])

    if data is None or data["prices"].empty:
        st.error(f"Geen data gevonden voor {selected_ticker}")
        return

    prices_df = data["prices"]
    currency = get_currency_symbol(selected_ticker)
    company_name = ALL_TICKERS[selected_ticker]

    # Header
    st.subheader(f"{company_name} ({selected_ticker})")
    info_parts = []
    if data["info"].get("sector"):
        info_parts.append(f"Sector: {data['info']['sector']}")
    info_parts.append(f"Markt: {get_market(selected_ticker)}")
    st.caption(" • ".join(info_parts))

    # Metrics
    metrics = analysis.calculate_all_metrics(prices_df)
    if not metrics:
        st.warning("Niet genoeg data om metrics te berekenen.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Totaal rendement", f"{metrics['total_return_pct']:.1f}%",
                  help="Totaal rendement over de geselecteerde periode")
    with col2:
        st.metric("Geann. rendement (CAGR)", f"{metrics['annualized_return_pct']:.2f}%",
                  help="Compound Annual Growth Rate - jaarlijks gemiddeld rendement")
    with col3:
        st.metric("Volatiliteit (jaar)", f"{metrics['annualized_volatility_pct']:.1f}%",
                  help="Geannualiseerde standaarddeviatie. Hoger = grilliger.")
    with col4:
        st.metric("Max drawdown", f"{metrics['max_drawdown_pct']:.1f}%",
                  help=f"Grootste piek-tot-dal daling. Van {metrics['max_drawdown_peak']} tot {metrics['max_drawdown_trough']}.")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Sharpe ratio", f"{metrics['sharpe_ratio']:.2f}",
                  help=">1 is goed, >2 zeer goed")
    with col6:
        st.metric("Startprijs", f"{currency}{metrics['start_price']:.2f}")
    with col7:
        st.metric("Huidige prijs", f"{currency}{metrics['end_price']:.2f}")
    with col8:
        st.metric("Handelsdagen", f"{metrics['n_trading_days']:,}")

    st.divider()

    # === Hoofdgrafiek ===
    if show_volume:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.05, row_heights=[0.75, 0.25],
            subplot_titles=("Koers", "Volume"),
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    fig.add_trace(
        go.Scatter(
            x=prices_df.index, y=prices_df["Close"],
            mode="lines", name="Koers",
            line=dict(color="#1f77b4", width=2),
            hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{currency}%{{y:.2f}}<extra></extra>",
        ), row=1, col=1,
    )

    # Dividenden
    if show_dividends and not data["dividends"].empty:
        divs = data["dividends"]
        divs_in_range = divs[
            (divs.index >= prices_df.index.min()) &
            (divs.index <= prices_df.index.max())
        ]
        if not divs_in_range.empty:
            div_prices = []
            for d in divs_in_range.index:
                closest = prices_df.index[prices_df.index <= d]
                if len(closest) > 0:
                    div_prices.append(prices_df.loc[closest[-1], "Close"])
                else:
                    div_prices.append(None)

            fig.add_trace(
                go.Scatter(
                    x=divs_in_range.index, y=div_prices,
                    mode="markers", name="Dividend",
                    marker=dict(symbol="diamond", size=8, color="green"),
                    hovertemplate=f"<b>Dividend</b><br>%{{x|%Y-%m-%d}}<br>{currency}%{{customdata:.3f}}<extra></extra>",
                    customdata=divs_in_range.values,
                ), row=1, col=1,
            )

    # Splits
    if show_splits and not data["splits"].empty:
        splits = data["splits"]
        splits_in_range = splits[
            (splits.index >= prices_df.index.min()) &
            (splits.index <= prices_df.index.max())
        ]
        for date, ratio in splits_in_range.items():
            fig.add_vline(
                x=date, line_dash="dash", line_color="orange",
                annotation_text=f"Split {ratio:.0f}:1",
                annotation_position="top", row=1, col=1,
            )

    # Volume
    if show_volume:
        fig.add_trace(
            go.Bar(
                x=prices_df.index, y=prices_df["Volume"],
                name="Volume", marker=dict(color="#888", opacity=0.5),
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>%{y:,.0f}<extra></extra>",
            ), row=2, col=1,
        )

    fig.update_layout(
        height=600 if show_volume else 500,
        hovermode="x unified", showlegend=True,
        margin=dict(t=40, b=20, l=20, r=20),
    )
    if log_scale:
        fig.update_yaxes(type="log", row=1, col=1)
    fig.update_yaxes(title_text=f"Prijs ({currency})", row=1, col=1)
    if show_volume:
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # Jaarrendementen
    st.divider()
    st.subheader("📊 Jaarlijkse rendementen")
    yearly = analysis.yearly_returns(prices_df)
    if not yearly.empty:
        colors = ["#2ecc71" if v > 0 else "#e74c3c" for v in yearly.values]
        bar_fig = go.Figure(go.Bar(
            x=yearly.index.astype(str), y=yearly.values,
            marker=dict(color=colors),
            text=[f"{v:.1f}%" for v in yearly.values],
            textposition="outside",
        ))
        bar_fig.update_layout(
            height=350, xaxis_title="Jaar", yaxis_title="Rendement (%)",
            showlegend=False, margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    # Rolling volatility
    with st.expander("📉 Geavanceerd: rolling volatiliteit (30 dagen)"):
        rv = analysis.rolling_volatility(prices_df, window=30)
        rv_fig = go.Figure(go.Scatter(
            x=rv.index, y=rv.values, mode="lines",
            line=dict(color="#e67e22"),
            fill="tozeroy", fillcolor="rgba(230, 126, 34, 0.2)",
        ))
        rv_fig.update_layout(
            height=300, yaxis_title="Volatiliteit (%, jaarlijks)",
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(rv_fig, use_container_width=True)
        st.caption("Pieken in deze grafiek tonen marktstress (bv. 2008, 2020).")


def page_compare():
    st.title("⚖️ Aandelen vergelijken")

    options = {f"{name} ({ticker})": ticker for ticker, name in ALL_TICKERS.items()}

    with st.sidebar:
        st.header("⚙️ Vergelijking")
        selected_labels = st.multiselect(
            "Kies aandelen (max 5)",
            options=sorted(options.keys()),
            default=sorted(options.keys())[:2],
            max_selections=5,
        )

        period_options = {
            "1 jaar": "1y", "3 jaar": "3y", "5 jaar": "5y",
            "10 jaar": "10y", "20 jaar": "max",
        }
        selected_period = st.selectbox(
            "Periode", options=list(period_options.keys()), index=2,
        )

    if not selected_labels:
        st.info("Selecteer minimaal één aandeel in de zijbalk.")
        return

    selected_tickers = tuple(sorted([options[l] for l in selected_labels]))

    with st.spinner(f"📡 Data ophalen voor {len(selected_tickers)} aandelen..."):
        all_data = fetch_multiple_stocks(selected_tickers)

    fig = go.Figure()
    metrics_rows = []
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i, label in enumerate(selected_labels):
        ticker = options[label]
        data = all_data.get(ticker)
        if data is None or data["prices"].empty:
            continue

        prices_df = data["prices"]
        normalized = analysis.normalize_for_comparison(prices_df, base=100)

        fig.add_trace(go.Scatter(
            x=normalized.index, y=normalized.values,
            mode="lines", name=label.split(" (")[0],
            line=dict(color=colors[i % len(colors)], width=2),
        ))

        m = analysis.calculate_all_metrics(prices_df)
        metrics_rows.append({
            "Aandeel": label.split(" (")[0],
            "Totaal rend. (%)": round(m["total_return_pct"], 1),
            "CAGR (%)": round(m["annualized_return_pct"], 2),
            "Volatiliteit (%)": round(m["annualized_volatility_pct"], 1),
            "Max drawdown (%)": round(m["max_drawdown_pct"], 1),
            "Sharpe": round(m["sharpe_ratio"], 2),
        })

    fig.update_layout(
        height=500, title="Genormaliseerde vergelijking (start = 100)",
        xaxis_title="Datum", yaxis_title="Indexwaarde (start=100)",
        hovermode="x unified", margin=dict(t=50, b=20, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    if metrics_rows:
        st.subheader("📊 Vergelijkingstabel")
        df = pd.DataFrame(metrics_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


def page_info():
    st.title("ℹ️ Over deze app")

    st.markdown(f"""
    ### 📈 Stock Analyzer — MVP Fase 1

    **Aantal aandelen:** {len(ALL_TICKERS)}
    **Bron:** Yahoo Finance (via yfinance)
    **Cache:** Data wordt 24 uur gecached per aandeel

    ### Wat zit erin

    - **Enkel aandeel:** koersgrafiek over max 20 jaar, met dividenden en aandelensplitsingen op de tijdlijn
    - **Vergelijken:** tot 5 aandelen genormaliseerd naast elkaar
    - **Metrics:** rendement, volatiliteit, max drawdown, Sharpe ratio, jaarrendementen

    ### Volgende stappen

    - **Fase 2:** events koppelen (kwartaalcijfers, fusies, regulering)
    - **Fase 3:** patroonherkenning - "wat doet aandeel X gemiddeld na event Y?"

    ### ⚠️ Disclaimer

    Dit is een leertool. Niets in deze app is beleggingsadvies.
    Historische koersen voorspellen geen toekomstige resultaten.
    """)

    with st.expander("📋 Volledige aandelenlijst"):
        df = pd.DataFrame([
            {"Ticker": t, "Bedrijf": n, "Markt": get_market(t)}
            for t, n in ALL_TICKERS.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)


# === Hoofdnavigatie ===

def main():
    with st.sidebar:
        st.title("📈 Stock Analyzer")
        st.caption("MVP – fase 1")

        page = st.radio(
            "Navigatie",
            ["📊 Enkel aandeel", "⚖️ Vergelijken", "ℹ️ Info"],
            label_visibility="collapsed",
        )
        st.divider()

    if page == "📊 Enkel aandeel":
        page_single_stock()
    elif page == "⚖️ Vergelijken":
        page_compare()
    else:
        page_info()


if __name__ == "__main__":
    main()
