"""
Streamlit dashboard - Fase 2.
Met earnings-markers op grafiek + Event Analyzer pagina.

Run lokaal:    streamlit run app.py
Deploy:        push naar GitHub, Streamlit Cloud doet de rest
"""

import streamlit as st
import pandas as pd
import numpy as np
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
    path = DATA_DIR / "stocks.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data
def load_all_prices():
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
def load_all_earnings():
    """NIEUW: Laad earnings-data."""
    path = DATA_DIR / "earnings.parquet"
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


def get_earnings_for_ticker(ticker):
    """NIEUW."""
    df = load_all_earnings()
    if df.empty:
        return pd.DataFrame()
    return df[df["ticker"] == ticker].sort_values("date")


def get_currency_symbol(ticker):
    if ticker.endswith((".AS", ".DE", ".PA")):
        return "€"
    return "$"


def check_data_available():
    required = ["stocks.parquet", "prices.parquet"]
    missing = [f for f in required if not (DATA_DIR / f).exists()]
    return len(missing) == 0, missing


# === Pagina: Enkel aandeel (uitgebreid met earnings) ===

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
            "1 jaar": 365, "3 jaar": 365 * 3, "5 jaar": 365 * 5,
            "10 jaar": 365 * 10, "20 jaar (alles)": 365 * 25,
        }
        selected_period = st.selectbox(
            "Periode", options=list(period_options.keys()), index=4,
        )
        days_back = period_options[selected_period]

        st.divider()
        show_volume = st.checkbox("Toon volume", value=True)
        show_dividends = st.checkbox("Toon dividenden", value=True)
        show_splits = st.checkbox("Toon aandelensplitsingen", value=True)
        show_earnings = st.checkbox("📊 Toon earnings (NIEUW)", value=True)
        log_scale = st.checkbox("Log-schaal", value=False)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    prices_df = get_prices_for_ticker(
        selected_ticker,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    if prices_df.empty:
        st.error(f"Geen data voor {selected_ticker}")
        return

    stock_info = stocks_df[stocks_df["ticker"] == selected_ticker].iloc[0]
    currency = get_currency_symbol(selected_ticker)

    st.subheader(f"{stock_info['company_name']} ({selected_ticker})")
    info_parts = []
    if pd.notna(stock_info.get('sector')):
        info_parts.append(f"Sector: {stock_info['sector']}")
    info_parts.append(f"Markt: {stock_info['market']}")
    st.caption(" • ".join(info_parts))

    metrics = analysis.calculate_all_metrics(prices_df)
    if not metrics:
        st.warning("Niet genoeg data voor metrics.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Totaal rendement", f"{metrics['total_return_pct']:.1f}%")
    with col2:
        st.metric("CAGR", f"{metrics['annualized_return_pct']:.2f}%")
    with col3:
        st.metric("Volatiliteit (jaar)", f"{metrics['annualized_volatility_pct']:.1f}%")
    with col4:
        st.metric("Max drawdown", f"{metrics['max_drawdown_pct']:.1f}%")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Sharpe ratio", f"{metrics['sharpe_ratio']:.2f}")
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

    # NIEUW: Earnings markers
    if show_earnings:
        earnings = get_earnings_for_ticker(selected_ticker)
        if not earnings.empty:
            earnings_in_range = earnings[
                (earnings["date"] >= prices_df.index.min()) &
                (earnings["date"] <= prices_df.index.max())
            ].copy()

            if not earnings_in_range.empty:
                # Voor elke earning, vind dichtstbijzijnde koers
                earnings_in_range["price_at_event"] = None
                for idx, e in earnings_in_range.iterrows():
                    closest = prices_df.index[prices_df.index <= e["date"]]
                    if len(closest) > 0:
                        earnings_in_range.at[idx, "price_at_event"] = prices_df.loc[closest[-1], "close"]

                # Splits naar beat/miss/inline voor verschillende kleuren
                for category, color, symbol in [
                    ("beat", "#2ecc71", "triangle-up"),
                    ("miss", "#e74c3c", "triangle-down"),
                    ("inline", "#95a5a6", "circle"),
                ]:
                    subset = earnings_in_range[earnings_in_range["beat"] == category]
                    if subset.empty:
                        continue

                    hover_text = []
                    for _, e in subset.iterrows():
                        surprise = e.get("surprise_pct")
                        surprise_str = f"{surprise:+.1f}%" if pd.notna(surprise) else "n/a"
                        eps_est = e.get("eps_estimate")
                        eps_act = e.get("eps_actual")
                        hover_text.append(
                            f"<b>Earnings {category.upper()}</b><br>"
                            f"{e['date'].strftime('%Y-%m-%d')}<br>"
                            f"Verwacht EPS: {eps_est:.2f}<br>"
                            f"Werkelijk EPS: {eps_act:.2f}<br>"
                            f"Surprise: {surprise_str}"
                        )

                    fig.add_trace(
                        go.Scatter(
                            x=subset["date"], y=subset["price_at_event"],
                            mode="markers",
                            name=f"Earnings ({category})",
                            marker=dict(symbol=symbol, size=12, color=color,
                                        line=dict(color="white", width=1)),
                            hovertemplate="%{text}<extra></extra>",
                            text=hover_text,
                        ), row=1, col=1,
                    )

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

    # NIEUW: Earnings-tabel
    earnings = get_earnings_for_ticker(selected_ticker)
    if not earnings.empty:
        with st.expander(f"📊 Earnings-historie ({len(earnings)} kwartalen)", expanded=False):
            display_df = earnings.copy()
            display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
            display_df = display_df.sort_values("date", ascending=False)
            display_df = display_df.rename(columns={
                "date": "Datum",
                "eps_estimate": "Verwacht EPS",
                "eps_actual": "Werkelijk EPS",
                "surprise_pct": "Surprise %",
                "beat": "Resultaat",
            })
            st.dataframe(
                display_df[["Datum", "Verwacht EPS", "Werkelijk EPS", "Surprise %", "Resultaat"]],
                use_container_width=True, hide_index=True,
            )

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


# === Pagina: Vergelijken ===

def page_compare():
    st.title("⚖️ Aandelen vergelijken")

    stocks_df = load_stocks()
    if stocks_df.empty:
        st.error("Geen data beschikbaar.")
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
        st.info("Selecteer minimaal één aandeel.")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    fig = go.Figure()
    metrics_rows = []
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i, label in enumerate(selected_labels):
        ticker = options[label]
        prices_df = get_prices_for_ticker(
            ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
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
        xaxis_title="Datum", yaxis_title="Indexwaarde",
        hovermode="x unified", margin=dict(t=50, b=20, l=20, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    if metrics_rows:
        st.subheader("📊 Vergelijkingstabel")
        df = pd.DataFrame(metrics_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


# === NIEUWE PAGINA: Event Analyzer ===

def page_event_analyzer():
    st.title("🔬 Event Analyzer")
    st.caption("Analyseer hoe aandelen reageren op kwartaalcijfers")

    earnings_all = load_all_earnings()
    stocks_df = load_stocks()

    if earnings_all.empty:
        st.warning("Geen earnings-data beschikbaar. Run de pipeline opnieuw om earnings op te halen.")
        return

    # Statistieken bovenaan
    n_events = len(earnings_all)
    n_tickers_with_data = earnings_all["ticker"].nunique()
    n_beats = (earnings_all["beat"] == "beat").sum()
    n_misses = (earnings_all["beat"] == "miss").sum()
    n_inline = (earnings_all["beat"] == "inline").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Events totaal", f"{n_events}")
    col2.metric("Aandelen met data", f"{n_tickers_with_data}/{len(stocks_df)}")
    col3.metric("Beats", f"{n_beats} ({n_beats/n_events*100:.0f}%)")
    col4.metric("Misses", f"{n_misses} ({n_misses/n_events*100:.0f}%)")

    st.divider()

    # Tabs binnen Event Analyzer
    tab1, tab2, tab3 = st.tabs([
        "📍 Per aandeel",
        "🌐 Cross-aandeel vergelijking",
        "📊 Statistieken alle events",
    ])

    # --- Tab 1: Per aandeel ---
    with tab1:
        st.subheader("Hoe reageert één aandeel op zijn earnings?")

        tickers_with_earnings = sorted(earnings_all["ticker"].unique())
        ticker_options = {}
        for t in tickers_with_earnings:
            stock_row = stocks_df[stocks_df["ticker"] == t]
            if not stock_row.empty:
                name = stock_row.iloc[0]["company_name"]
                ticker_options[f"{name} ({t})"] = t

        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            selected = st.selectbox("Kies aandeel", options=list(ticker_options.keys()))
        with col_b:
            days_before = st.number_input("Dagen vóór event", 1, 30, 5)
        with col_c:
            days_after = st.number_input("Dagen ná event", 1, 30, 5)

        ticker = ticker_options[selected]
        ticker_earnings = earnings_all[earnings_all["ticker"] == ticker].copy()
        prices = get_prices_for_ticker(ticker)

        if prices.empty:
            st.warning("Geen prijsdata beschikbaar.")
            return

        # Bereken event impacts
        impacts = analysis.aggregate_event_impacts(
            prices, ticker_earnings,
            days_before=days_before, days_after=days_after,
        )

        if impacts.empty:
            st.warning("Geen events binnen de prijsdata-range.")
            return

        # Samenvatting per categorie
        st.markdown("##### 📊 Gemiddelde koersbeweging rondom earnings")

        summary_cols = st.columns(3)
        for i, category in enumerate(["beat", "miss", "inline"]):
            subset = impacts[impacts["beat"] == category]
            if subset.empty:
                continue
            avg_pre = subset["return_pre_pct"].mean()
            avg_event = subset["return_event_day_pct"].mean()
            avg_post = subset["return_post_pct"].mean()
            n = len(subset)

            with summary_cols[i]:
                st.markdown(f"**{category.upper()}** (n={n})")
                st.metric(f"-{days_before}d → event", f"{avg_pre:+.2f}%")
                st.metric("Event-dag", f"{avg_event:+.2f}%")
                st.metric(f"event → +{days_after}d", f"{avg_post:+.2f}%")

        # Visualisatie: spaghetti-plot van alle events
        st.markdown("##### 📈 Koersbeweging per event (genormaliseerd op event-dag = 100)")

        spaghetti_fig = go.Figure()

        category_colors = {"beat": "#2ecc71", "miss": "#e74c3c", "inline": "#95a5a6"}

        for _, event in ticker_earnings.iterrows():
            event_date = pd.to_datetime(event["date"])
            window_start = event_date - timedelta(days=days_before * 2 + 5)
            window_end = event_date + timedelta(days=days_after * 2 + 5)

            window_prices = prices[
                (prices.index >= window_start) & (prices.index <= window_end)
            ]
            if window_prices.empty:
                continue

            # Vind event-day index
            available = window_prices.index
            event_idx = available.searchsorted(event_date)
            if event_idx >= len(available):
                continue

            # Selecteer window: -days_before tot +days_after handelsdagen
            start_idx = max(0, event_idx - days_before)
            end_idx = min(len(available), event_idx + days_after + 1)

            window = window_prices.iloc[start_idx:end_idx].copy()
            if window.empty or event_idx - start_idx >= len(window):
                continue

            # Normaliseer op event-day = 100
            event_price = window["close"].iloc[event_idx - start_idx]
            normalized = (window["close"] / event_price) * 100

            # X-as: handelsdagen relatief tot event
            x_values = list(range(-(event_idx - start_idx), len(window) - (event_idx - start_idx)))

            color = category_colors.get(event["beat"], "#888")

            spaghetti_fig.add_trace(go.Scatter(
                x=x_values, y=normalized.values,
                mode="lines", line=dict(color=color, width=1.5),
                opacity=0.4,
                name=f"{event['date'].strftime('%Y-%m-%d')} ({event['beat']})",
                hovertemplate=f"%{{x}} dagen<br>%{{y:.1f}}<br>{event['date'].strftime('%Y-%m-%d')} ({event['beat']})<extra></extra>",
                showlegend=False,
            ))

        # Voeg event-day verticale lijn toe
        spaghetti_fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)
        spaghetti_fig.add_hline(y=100, line_dash="dot", line_color="gray", line_width=1)

        spaghetti_fig.update_layout(
            height=400,
            xaxis_title="Handelsdagen relatief tot event (0 = earnings-dag)",
            yaxis_title="Genormaliseerde prijs (event-dag = 100)",
            margin=dict(t=20, b=20, l=20, r=20),
        )
        st.plotly_chart(spaghetti_fig, use_container_width=True)
        st.caption("Elk lijntje = één earnings event. Groen = beat, rood = miss, grijs = inline.")

        # Detail-tabel
        with st.expander("📋 Detail per event"):
            display = impacts[["event_date_actual", "beat", "return_pre_pct",
                               "return_event_day_pct", "return_post_pct", "return_total_pct",
                               "eps_estimate", "eps_actual", "surprise_pct"]].copy()
            display = display.rename(columns={
                "event_date_actual": "Datum",
                "beat": "Resultaat",
                "return_pre_pct": f"Pre ({days_before}d)",
                "return_event_day_pct": "Event-dag",
                "return_post_pct": f"Post ({days_after}d)",
                "return_total_pct": "Totaal",
                "eps_estimate": "Verwacht EPS",
                "eps_actual": "Werkelijk EPS",
                "surprise_pct": "Surprise %",
            })
            for col in [f"Pre ({days_before}d)", "Event-dag", f"Post ({days_after}d)", "Totaal"]:
                display[col] = display[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "")
            st.dataframe(display.sort_values("Datum", ascending=False),
                         use_container_width=True, hide_index=True)

    # --- Tab 2: Cross-aandeel vergelijking ---
    with tab2:
        st.subheader("Welk aandeel reageert het sterkst?")

        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            cross_days_before = st.number_input("Dagen vóór", 1, 30, 5, key="cross_pre")
        with col_b:
            cross_days_after = st.number_input("Dagen ná", 1, 30, 5, key="cross_post")
        with col_c:
            min_events = st.slider("Minimum events per aandeel", 1, 10, 3,
                                    help="Filter aandelen met te weinig data")

        # Bereken impact voor alle aandelen
        with st.spinner("Bereken event-impact voor alle aandelen..."):
            all_impacts_list = []
            for ticker in earnings_all["ticker"].unique():
                ticker_earnings = earnings_all[earnings_all["ticker"] == ticker]
                ticker_prices = get_prices_for_ticker(ticker)
                if ticker_prices.empty:
                    continue
                imp = analysis.aggregate_event_impacts(
                    ticker_prices, ticker_earnings,
                    days_before=cross_days_before, days_after=cross_days_after,
                )
                if not imp.empty:
                    imp["ticker"] = ticker
                    all_impacts_list.append(imp)

        if not all_impacts_list:
            st.warning("Geen data voor cross-vergelijking.")
            return

        all_impacts = pd.concat(all_impacts_list, ignore_index=True)

        # Aggregeer per ticker en categorie
        agg = all_impacts.groupby(["ticker", "beat"]).agg(
            mean_post=("return_post_pct", "mean"),
            mean_event=("return_event_day_pct", "mean"),
            n=("return_post_pct", "count"),
        ).reset_index()

        # Filter op minimum events
        ticker_counts = agg.groupby("ticker")["n"].sum()
        valid_tickers = ticker_counts[ticker_counts >= min_events].index
        agg = agg[agg["ticker"].isin(valid_tickers)]

        if agg.empty:
            st.warning(f"Geen aandelen met minstens {min_events} events.")
            return

        # Visualisatie: bar chart per categorie
        st.markdown(f"##### 📊 Gemiddelde koersbeweging in {cross_days_after} dagen na earnings")

        for category, color, label in [
            ("beat", "#2ecc71", "Beats (werkelijk > verwacht)"),
            ("miss", "#e74c3c", "Misses (werkelijk < verwacht)"),
        ]:
            cat_data = agg[agg["beat"] == category].copy()
            if cat_data.empty:
                continue
            cat_data = cat_data.sort_values("mean_post", ascending=True)

            # Voeg bedrijfsnaam toe
            cat_data = cat_data.merge(
                stocks_df[["ticker", "company_name"]], on="ticker", how="left"
            )
            cat_data["display"] = cat_data["company_name"].fillna(cat_data["ticker"])

            bar_fig = go.Figure(go.Bar(
                y=cat_data["display"],
                x=cat_data["mean_post"],
                orientation="h",
                marker=dict(color=color),
                text=[f"{v:+.1f}% (n={n})" for v, n in zip(cat_data["mean_post"], cat_data["n"])],
                textposition="outside",
            ))
            bar_fig.update_layout(
                title=label,
                height=max(300, 30 * len(cat_data)),
                xaxis_title=f"Gem. rendement {cross_days_after}d na earnings (%)",
                margin=dict(t=40, b=20, l=20, r=20),
            )
            bar_fig.add_vline(x=0, line_dash="dash", line_color="gray", line_width=1)
            st.plotly_chart(bar_fig, use_container_width=True)

    # --- Tab 3: Statistieken alle events ---
    with tab3:
        st.subheader("Statistische samenvatting alle events")

        col_a, col_b = st.columns(2)
        with col_a:
            stat_days_before = st.number_input("Dagen vóór", 1, 30, 5, key="stat_pre")
        with col_b:
            stat_days_after = st.number_input("Dagen ná", 1, 30, 5, key="stat_post")

        with st.spinner("Berekenen..."):
            all_impacts_list = []
            for ticker in earnings_all["ticker"].unique():
                ticker_earnings = earnings_all[earnings_all["ticker"] == ticker]
                ticker_prices = get_prices_for_ticker(ticker)
                if ticker_prices.empty:
                    continue
                imp = analysis.aggregate_event_impacts(
                    ticker_prices, ticker_earnings,
                    days_before=stat_days_before, days_after=stat_days_after,
                )
                if not imp.empty:
                    all_impacts_list.append(imp)

        if not all_impacts_list:
            st.warning("Geen data.")
            return

        all_impacts = pd.concat(all_impacts_list, ignore_index=True)

        # Statistische samenvatting
        st.markdown("##### Verdeling van rendementen per categorie")

        for metric_col, metric_label in [
            ("return_event_day_pct", "Event-dag rendement"),
            ("return_post_pct", f"Rendement {stat_days_after} dagen na event"),
        ]:
            st.markdown(f"**{metric_label}**")

            stats = all_impacts.groupby("beat")[metric_col].agg(
                ["mean", "median", "std", "min", "max", "count"]
            ).round(2)
            stats.columns = ["Gemiddelde", "Mediaan", "Std", "Min", "Max", "N"]
            st.dataframe(stats, use_container_width=True)

            # Histogram
            hist_fig = go.Figure()
            for category, color in [("beat", "#2ecc71"), ("miss", "#e74c3c"), ("inline", "#95a5a6")]:
                subset = all_impacts[all_impacts["beat"] == category][metric_col].dropna()
                if subset.empty:
                    continue
                hist_fig.add_trace(go.Histogram(
                    x=subset, name=category,
                    marker_color=color, opacity=0.6,
                    nbinsx=30,
                ))
            hist_fig.update_layout(
                barmode="overlay",
                height=300,
                xaxis_title=f"{metric_label} (%)",
                yaxis_title="Aantal events",
                margin=dict(t=20, b=20, l=20, r=20),
            )
            hist_fig.add_vline(x=0, line_dash="dash", line_color="black", line_width=1)
            st.plotly_chart(hist_fig, use_container_width=True)


def page_info():
    st.title("ℹ️ Over deze app")

    last_update = get_last_update()
    stocks_df = load_stocks()
    prices_df = load_all_prices()
    earnings_df = load_all_earnings()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Aandelen", len(stocks_df))
    col2.metric("Koersregels", f"{len(prices_df):,}")
    col3.metric("Earnings events", len(earnings_df))
    if not prices_df.empty:
        date_min = prices_df["date"].min().strftime("%Y")
        date_max = prices_df["date"].max().strftime("%Y")
        col4.metric("Periode", f"{date_min} – {date_max}")

    st.info(f"📅 Data laatst bijgewerkt: **{last_update}**")

    st.markdown("""
    ### Wat zit erin?

    **Fase 1 — Basis koersanalyse (klaar):**
    - 20 jaar koersdata van 55 aandelen
    - Dividenden en aandelensplitsingen
    - Metrics: rendement, volatiliteit, drawdown, Sharpe ratio

    **Fase 2 — Event Analyzer (klaar):**
    - Earnings (kwartaalcijfers): verwachte vs werkelijke EPS
    - Beat/miss/inline classificatie
    - Per-aandeel event-impact analyse
    - Cross-aandeel vergelijking
    - Statistische verdeling van reacties

    **Fase 3 — Patroonherkenning (toekomstig):**
    - Voorspelmodel op basis van historische events
    - Sector- en marktbrede analyses

    ### ⚠️ Disclaimer

    Dit is een leertool. Niets in deze app is beleggingsadvies.
    """)


# === Hoofdnavigatie ===

def main():
    available, missing = check_data_available()

    with st.sidebar:
        st.title("📈 Stock Analyzer")
        st.caption(f"Fase 2 • Update: {get_last_update()[:10] if get_last_update() != 'onbekend' else 'geen data'}")

        page = st.radio(
            "Navigatie",
            ["📊 Enkel aandeel", "⚖️ Vergelijken", "🔬 Event Analyzer", "ℹ️ Info"],
            label_visibility="collapsed",
        )
        st.divider()

    if not available:
        st.error(f"⚠️ Data ontbreekt: {', '.join(missing)}")
        return

    if page == "📊 Enkel aandeel":
        page_single_stock()
    elif page == "⚖️ Vergelijken":
        page_compare()
    elif page == "🔬 Event Analyzer":
        page_event_analyzer()
    else:
        page_info()


if __name__ == "__main__":
    main()
