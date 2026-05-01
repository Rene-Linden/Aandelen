"""
Data Pipeline - lokaal te draaien
==================================

Haalt op:
  - Dagelijkse koersen
  - Dividenden en aandelensplitsingen
  - Earnings (kwartaalcijfers): verwachte vs werkelijke EPS

Slaat op als parquet-bestanden in data/:
  - prices.parquet     - dagelijkse koersen
  - dividends.parquet  - dividenduitkeringen
  - splits.parquet     - aandelensplitsingen
  - stocks.parquet     - bedrijfsmetadata
  - earnings.parquet   - kwartaalcijfers (NIEUW in fase 2)
  - last_update.txt    - timestamp

Gebruik:
    python data_pipeline.py
"""

import time
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf

from tickers import ALL_TICKERS, get_market

# Configuratie
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DELAY_BETWEEN_REQUESTS = 2.0
MAX_RETRIES = 3
RETRY_DELAY = 30


def fetch_with_retry(ticker, period="20y", max_retries=MAX_RETRIES):
    """Haalt prijs- en event-data op met retry-logica."""
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            prices = stock.history(period=period, auto_adjust=False)

            if prices.empty:
                return None

            if prices.index.tz is not None:
                prices.index = prices.index.tz_localize(None)

            actions = stock.actions if hasattr(stock, 'actions') else pd.DataFrame()
            if not actions.empty and actions.index.tz is not None:
                actions.index = actions.index.tz_localize(None)

            # Bedrijfsinfo
            info = {}
            try:
                raw_info = stock.info
                info = {
                    "sector": raw_info.get("sector"),
                    "industry": raw_info.get("industry"),
                }
            except Exception:
                pass

            # NIEUW: Earnings ophalen
            earnings_df = fetch_earnings(stock, ticker)

            return {
                "prices": prices,
                "actions": actions,
                "info": info,
                "earnings": earnings_df,
            }

        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "rate" in error_msg or "too many" in error_msg or "429" in error_msg

            if is_rate_limit and attempt < max_retries - 1:
                print(f"\n  ⏸️  Rate limit, wacht {RETRY_DELAY}s... (poging {attempt + 1}/{max_retries})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"\n  ⚠️  Fout: {e}")
                return None

    return None


def fetch_earnings(stock, ticker):
    """
    Haalt earnings-historie op via yfinance.

    yfinance heeft twee bronnen die we combineren:
      - earnings_dates: datums + verwachte/werkelijke EPS (vaak ~4-8 kwartalen)
      - quarterly_income_stmt: kwartaaldata (revenue, etc) als backup

    Returns DataFrame met kolommen:
      ticker, date, eps_estimate, eps_actual, surprise_pct, beat
    """
    try:
        # Hoofdbron: earnings_dates
        earnings_dates = stock.earnings_dates
        if earnings_dates is None or earnings_dates.empty:
            return pd.DataFrame()

        df = earnings_dates.copy()

        # Tijdzone weghalen
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Reset index zodat datum een kolom wordt
        df = df.reset_index()
        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

        # Kolomnamen normaliseren - yfinance gebruikt verschillende namen
        rename_map = {
            "Earnings Date": "date",
            "EPS Estimate": "eps_estimate",
            "Reported EPS": "eps_actual",
            "Surprise(%)": "surprise_pct",
        }
        df = df.rename(columns=rename_map)

        # Zorg dat alle vereiste kolommen bestaan
        for col in ["date", "eps_estimate", "eps_actual", "surprise_pct"]:
            if col not in df.columns:
                df[col] = None

        # Alleen earnings die al PLAATSGEVONDEN hebben (niet toekomstige)
        df = df[df["eps_actual"].notna()].copy()

        if df.empty:
            return pd.DataFrame()

        # Beat/miss bepalen op basis van surprise
        # Beat = werkelijk > verwacht, Miss = werkelijk < verwacht
        def classify(row):
            est = row["eps_estimate"]
            act = row["eps_actual"]
            if pd.isna(est) or pd.isna(act):
                return None
            if act > est:
                return "beat"
            elif act < est:
                return "miss"
            else:
                return "inline"

        df["beat"] = df.apply(classify, axis=1)
        df["ticker"] = ticker

        # Selecteer en sorteer
        result = df[["ticker", "date", "eps_estimate", "eps_actual", "surprise_pct", "beat"]].copy()
        result = result.sort_values("date").reset_index(drop=True)

        # Datums normaliseren naar pure datum (zonder tijd)
        result["date"] = pd.to_datetime(result["date"]).dt.normalize()

        return result

    except Exception as e:
        # Earnings-data is optioneel, fail silent
        return pd.DataFrame()


def main():
    print(f"🚀 Data Pipeline gestart (Fase 2 - met earnings)")
    print(f"📂 Data wordt opgeslagen in: {DATA_DIR}")
    print(f"📊 Aantal tickers: {len(ALL_TICKERS)}")
    print(f"⏱️  Geschatte tijd: ~{len(ALL_TICKERS) * (DELAY_BETWEEN_REQUESTS + 1) / 60:.1f} minuten\n")
    print("=" * 60)

    all_prices = []
    all_dividends = []
    all_splits = []
    all_stocks = []
    all_earnings = []

    success = 0
    failed = []

    for i, (ticker, name) in enumerate(ALL_TICKERS.items(), 1):
        print(f"[{i}/{len(ALL_TICKERS)}] 📥 {ticker} ({name})...", end=" ", flush=True)

        data = fetch_with_retry(ticker)

        if data is None:
            print("❌")
            failed.append(ticker)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        # Stock metadata
        all_stocks.append({
            "ticker": ticker,
            "company_name": name,
            "market": get_market(ticker),
            "sector": data["info"].get("sector"),
            "industry": data["info"].get("industry"),
        })

        # Prijzen
        prices = data["prices"].copy()
        prices["ticker"] = ticker
        prices.reset_index(inplace=True)
        prices.rename(columns={"Date": "date"}, inplace=True)
        all_prices.append(prices)

        # Dividenden en splits
        actions = data["actions"]
        n_div = 0
        n_split = 0
        if not actions.empty:
            if "Dividends" in actions.columns:
                divs = actions[actions["Dividends"] > 0]["Dividends"]
                if not divs.empty:
                    div_df = pd.DataFrame({
                        "ticker": ticker,
                        "date": divs.index,
                        "amount": divs.values,
                    })
                    all_dividends.append(div_df)
                    n_div = len(divs)
            if "Stock Splits" in actions.columns:
                splits = actions[actions["Stock Splits"] > 0]["Stock Splits"]
                if not splits.empty:
                    split_df = pd.DataFrame({
                        "ticker": ticker,
                        "date": splits.index,
                        "ratio": splits.values,
                    })
                    all_splits.append(split_df)
                    n_split = len(splits)

        # NIEUW: Earnings
        earnings = data["earnings"]
        n_earnings = 0
        if earnings is not None and not earnings.empty:
            all_earnings.append(earnings)
            n_earnings = len(earnings)

        print(f"✅ {len(prices)} dagen, {n_div} div, {n_split} splits, {n_earnings} earnings")
        success += 1

        if i < len(ALL_TICKERS):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # === Opslaan ===
    print("\n" + "=" * 60)
    print("💾 Opslaan...")

    if all_prices:
        prices_df = pd.concat(all_prices, ignore_index=True)
        prices_df.columns = [c.lower().replace(" ", "_") for c in prices_df.columns]
        prices_df.to_parquet(DATA_DIR / "prices.parquet", index=False)
        print(f"  ✓ prices.parquet ({len(prices_df):,} rijen)")

    if all_dividends:
        dividends_df = pd.concat(all_dividends, ignore_index=True)
        dividends_df.to_parquet(DATA_DIR / "dividends.parquet", index=False)
        print(f"  ✓ dividends.parquet ({len(dividends_df)} rijen)")
    else:
        pd.DataFrame(columns=["ticker", "date", "amount"]).to_parquet(
            DATA_DIR / "dividends.parquet", index=False)

    if all_splits:
        splits_df = pd.concat(all_splits, ignore_index=True)
        splits_df.to_parquet(DATA_DIR / "splits.parquet", index=False)
        print(f"  ✓ splits.parquet ({len(splits_df)} rijen)")
    else:
        pd.DataFrame(columns=["ticker", "date", "ratio"]).to_parquet(
            DATA_DIR / "splits.parquet", index=False)

    # NIEUW: earnings opslaan
    if all_earnings:
        earnings_df = pd.concat(all_earnings, ignore_index=True)
        earnings_df.to_parquet(DATA_DIR / "earnings.parquet", index=False)
        print(f"  ✓ earnings.parquet ({len(earnings_df)} rijen)")
    else:
        pd.DataFrame(columns=["ticker", "date", "eps_estimate", "eps_actual",
                              "surprise_pct", "beat"]).to_parquet(
            DATA_DIR / "earnings.parquet", index=False)
        print(f"  ⚠ earnings.parquet (leeg - geen data beschikbaar)")

    stocks_df = pd.DataFrame(all_stocks)
    stocks_df.to_parquet(DATA_DIR / "stocks.parquet", index=False)
    print(f"  ✓ stocks.parquet ({len(stocks_df)} rijen)")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (DATA_DIR / "last_update.txt").write_text(timestamp)
    print(f"  ✓ last_update.txt ({timestamp})")

    # Samenvatting
    print("\n" + "=" * 60)
    print(f"✅ Klaar: {success}/{len(ALL_TICKERS)} succesvol")
    if failed:
        print(f"❌ Mislukt: {', '.join(failed)}")

    if all_earnings:
        total_earnings = sum(len(e) for e in all_earnings)
        tickers_with_earnings = len(all_earnings)
        print(f"\n📊 Earnings-coverage: {tickers_with_earnings}/{success} aandelen, {total_earnings} events totaal")

    total_size = sum(f.stat().st_size for f in DATA_DIR.glob("*.parquet"))
    print(f"\n📦 Totale data-grootte: {total_size / 1024 / 1024:.1f} MB")
    print(f"\n💡 Volgende stap: commit en push naar GitHub")
    print(f"   git add data/")
    print(f"   git commit -m \"Update data {datetime.now().strftime('%Y-%m-%d')}\"")
    print(f"   git push")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Onderbroken door gebruiker")
        sys.exit(1)
