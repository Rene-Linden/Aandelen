"""
Streamlit dashboard - leest uit parquet-bestanden.
Geen yfinance call, geen rate limits, razendsnel.

Run lokaal:    streamlit run app.py
Deploy:        push naar GitHub, Streamlit Cloud doet de rest
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pathlib import Path

import analysis

# Pagina-configuratie
st.set_page_config(
    page_title="Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"


# === Data laden met cache ===

@st.cache_data
def load_stocks():
    """Laadt aandelen-metadata."""
    path = DATA_DIR / "stocks.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data
def load_all_prices():
    """Laadt alle koersen in één keer."""
    path = DATA_DIR / "prices.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def load_all_dividends():
    path = DATA_DIR / "dividends.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def load_all_splits():
    path = DATA_DIR / "splits.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def get_last_update():
    path = DATA_DIR / "last_update.txt"
    if path.exists():
        return path.read_text().strip()
    return "onbekend"


def get_prices_for_ticker(ticker, start_date=None, end_date=None):
    """Filter koersen voor één ticker."""
    df = load_all_prices()
    if df.empty:
        return pd.DataFrame()

    df = df[df["ticker"] == ticker].copy()
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)

    if start_date:
        df = df[df.index >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df.index <= pd.to_datetime(end_date)]

    return df


def get_dividends_for_ticker(ticker):
    df = load_all_dividends()
    if df.empty:
        return pd.DataFrame()
    return df[df["ticker"] == ticker].sort_values("date")


def get_splits_for_ticker(ticker):
    df = load_all_splits()
    if df.empty:
        return pd.DataFrame()
    return df[df["ticker"] == ticker].sort_values("date")


def get_currency_symbol(ticker):
    if ticker.endswith((".AS", ".DE", ".PA")):
        return "€"
    return "$"


def check_data_available():
    """Controleert of de data beschikbaar is."""
    required = ["stocks.parquet", "prices.parquet"]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    return len(missing) == 0, missing


# === Pagina's ===

def page_single_stock():
    st.title("📈 Aandelen-analyse")

    stocks_df = load_stocks()
    if stocks_df.empty:
        st.error("Geen data beschikbaar. Run eerst lokaal: `python data_pipeline.py`")
        return

    options = {}
    for _, row in stocks_df.iterrows():
        label = f"{row['company_name']} ({row['ticker']}) - {row['market']}"
        options[label] = row['ticker']

    with st.sidebar:
        st.header("⚙️ Instellingen")
        selected_label = st.selectbox(
            "Kies een aandeel",
            options=sorted(options.keys()),
        )
        selected_ticker = options[selected_label]

        period_options = {
            "1 jaar": 365,
            "3 jaar": 365 * 3,
            "5 jaar": 365 * 5,
            "10 jaar": 365 * 10,
            "20 jaar (alles)": 365 * 25,
        }
        selected_period = st.selectbox(
            "Periode",
            options=list(period_options.keys()),
            index=4,
        )
        days_back = period_options[selected_period]

        st.divider()
        show_volume = st.checkbox("Toon volume", value=True)
        show_dividends = st.checkbox("Toon dividenden", value=True)
        show_splits = st.checkbox("Toon aandelensplitsingen", value=True)
        log_scale = st.checkbox("Log-schaal (aanbevolen voor lange periodes)", value=False)

    # Data ophalen
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    prices_df = get_prices_for_ticker(
        selected_ticker,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    if prices_df.empty:
        st.error(f"Geen data gevonden voor {selected_ticker}")
        return

    # Stock info
    stock_info = stocks_df[stocks_df["ticker"] == selected_ticker].iloc[0]
    currency = get_currency_symbol(selected_ticker)

    st.subheader(f"{stock_info['company_name']} ({selected_ticker})")
    info_parts = []
    if pd.notna(stock_info.get('sector')):
        info_parts.append(f"Sector: {stock_info['sector']}")
    info_parts.append(f"Markt: {stock_info['market']}")
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
                  help="Compound Annual Growth Rate")
    with col3:
        st.metric("Volatiliteit (jaar)", f"{metrics['annualized_volatility_pct']:.1f}%",
                  help="Geannualiseerde standaarddeviatie")
    with col4:
        st.metric("Max drawdown", f"{metrics['max_drawdown_pct']:.1f}%",
                  help=f"Van {metrics['max_drawdown_peak']} tot {metrics['max_drawdown_trough']}")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Sharpe ratio", f"{metrics['sharpe_ratio']:.2f}", help=">1 is goed")
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
            x=prices_df.index, y=prices_df["close"],
            mode="lines", name="Koers",
            line=dict(color="#1f77b4", width=2),
            hovertemplate=f"<b>%{{x|%Y-%m-%d}}</b><br>{currency}%{{y:.2f}}<extra></extra>",
        ), row=1, col=1,
    )

    # Dividenden
    if show_dividends:
        divs = get_dividends_for_ticker(selected_ticker)
        if not divs.empty:
            divs_in_range = divs[
                (divs["date"] >= prices_df.index.min()) &
                (divs["date"] <= prices_df.index.max())
            ]
            if not divs_in_range.empty:
                div_prices = []
                for d in divs_in_range["date"]:
                    closest = prices_df.index[prices_df.index <= d]
                    if len(closest) > 0:
                        div_prices.append(prices_df.loc[closest[-1], "close"])
                    else:
                        div_prices.append(None)

                fig.add_trace(
                    go.Scatter(
                        x=divs_in_range["date"], y=div_prices,
                        mode="markers", name="Dividend",
                        marker=dict(symbol="diamond", size=8, color="green"),
                        hovertemplate=f"<b>Dividend</b><br>%{{x|%Y-%m-%d}}<br>{currency}%{{customdata:.3f}}<extra></extra>",
                        customdata=divs_in_range["amount"],
                    ), row=1, col=1,
                )

    # Splits
    if show_splits:
        splits = get_splits_for_ticker(selected_ticker)
        if not splits.empty:
            splits_in_range = splits[
                (splits["date"] >= prices_df.index.min()) &
                (splits["date"] <= prices_df.index.max())
            ]
            for _, row in splits_in_range.iterrows():
                fig.add_vline(
                    x=row["date"], line_dash="dash", line_color="orange",
                    annotation_text=f"Split {row['ratio']:.0f}:1",
                    annotation_position="top", row=1, col=1,
                )

    # Volume
    if show_volume:
        fig.add_trace(
            go.Bar(
                x=prices_df.index, y=prices_df["volume"],
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

    # Rolling vol
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
        st.caption("Pieken tonen marktstress (bv. 2008, 2020).")


def page_compare():
    st.title("⚖️ Aandelen vergelijken")

    stocks_df = load_stocks()
    if stocks_df.empty:
        st.error("Geen data beschikbaar. Run eerst lokaal: `python data_pipeline.py`")
        return

    options = {}
    for _, row in stocks_df.iterrows():
        label = f"{row['company_name']} ({row['ticker']})"
        options[label] = row['ticker']

    with st.sidebar:
        st.header("⚙️ Vergelijking")
        selected_labels = st.multiselect(
            "Kies aandelen (max 5)",
            options=sorted(options.keys()),
            default=sorted(options.keys())[:2],
            max_selections=5,
        )

        period_options = {
            "1 jaar": 365, "3 jaar": 365 * 3, "5 jaar": 365 * 5,
            "10 jaar": 365 * 10, "20 jaar": 365 * 25,
        }
        selected_period = st.selectbox(
            "Periode", options=list(period_options.keys()), index=2,
        )
        days_back = period_options[selected_period]

    if not selected_labels:
        st.info("Selecteer minimaal één aandeel in de zijbalk.")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    fig = go.Figure()
    metrics_rows = []
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i, label in enumerate(selected_labels):
        ticker = options[label]
        prices_df = get_prices_for_ticker(
            ticker,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
        if prices_df.empty:
            continue

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

    last_update = get_last_update()
    stocks_df = load_stocks()
    prices_df = load_all_prices()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Aandelen", len(stocks_df))
    with col2:
        st.metric("Koersregels", f"{len(prices_df):,}")
    with col3:
        if not prices_df.empty:
            date_min = prices_df["date"].min().strftime("%Y")
            date_max = prices_df["date"].max().strftime("%Y")
            st.metric("Periode", f"{date_min} – {date_max}")

    st.info(f"📅 Data laatst bijgewerkt: **{last_update}**")

    st.markdown("""
    ### Hoe werkt deze app?

    Data wordt **lokaal opgehaald** (via `data_pipeline.py`) en als parquet-bestanden
    naar GitHub gepusht. De Streamlit-app leest die bestanden en toont alles instant —
    geen rate limits, geen wachten.

    ### Volgende stappen

    - **Fase 2:** events koppelen (kwartaalcijfers, fusies)
    - **Fase 3:** patroonherkenning en analyse

    ### ⚠️ Disclaimer

    Dit is een leertool. Niets in deze app is beleggingsadvies.
    """)

    if not stocks_df.empty:
        with st.expander(f"📋 Volledige aandelenlijst ({len(stocks_df)})"):
            st.dataframe(
                stocks_df[["ticker", "company_name", "market", "sector"]],
                use_container_width=True, hide_index=True,
            )


# === Hoofdnavigatie ===

def main():
    # Check data
    available, missing = check_data_available()

    with st.sidebar:
        st.title("📈 Stock Analyzer")
        st.caption(f"MVP fase 1 • Update: {get_last_update()[:10] if get_last_update() != 'onbekend' else 'geen data'}")

        page = st.radio(
            "Navigatie",
            ["📊 Enkel aandeel", "⚖️ Vergelijken", "ℹ️ Info"],
            label_visibility="collapsed",
        )
        st.divider()

    if not available:
        st.error(f"⚠️ Data ontbreekt: {', '.join(missing)}")
        st.markdown("""
        **Eerste keer gebruiken?** Run lokaal:
        ```bash
        pip install -r requirements.txt
        python data_pipeline.py
        git add data/
        git commit -m "Initial data"
        git push
        ```
        Daarna ververst de online app vanzelf binnen ~1 minuut.
        """)
        return

    if page == "📊 Enkel aandeel":
        page_single_stock()
    elif page == "⚖️ Vergelijken":
        page_compare()
    else:
        page_info()


if __name__ == "__main__":
    main()
