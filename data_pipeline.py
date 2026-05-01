"""
Data Pipeline - lokaal te draaien
==================================

Haalt alle koersdata op via yfinance en slaat op als parquet bestanden:
  - data/prices.parquet     - dagelijkse koersen (alle tickers samen)
  - data/dividends.parquet  - dividenduitkeringen
  - data/splits.parquet     - aandelensplitsingen
  - data/stocks.parquet     - bedrijfsmetadata (sector, industrie)
  - data/last_update.txt    - timestamp van laatste run

Gebruik:
    python data_pipeline.py

Daarna committen naar GitHub:
    git add data/
    git commit -m "Update data"
    git push
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

# Vertraging tussen requests om rate limits te voorkomen
DELAY_BETWEEN_REQUESTS = 2.0  # seconden
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconden bij rate-limit


def fetch_with_retry(ticker, period="20y", max_retries=MAX_RETRIES):
    """Haalt data op met retry-logica bij rate limits."""
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            prices = stock.history(period=period, auto_adjust=False)

            if prices.empty:
                return None

            # Tijdzone weghalen
            if prices.index.tz is not None:
                prices.index = prices.index.tz_localize(None)

            # Actions (dividenden, splits)
            actions = stock.actions if hasattr(stock, 'actions') else pd.DataFrame()
            if not actions.empty and actions.index.tz is not None:
                actions.index = actions.index.tz_localize(None)

            # Info (sector etc) - mag falen
            info = {}
            try:
                raw_info = stock.info
                info = {
                    "sector": raw_info.get("sector"),
                    "industry": raw_info.get("industry"),
                }
            except Exception:
                pass

            return {
                "prices": prices,
                "actions": actions,
                "info": info,
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


def main():
    print(f"🚀 Data Pipeline gestart")
    print(f"📂 Data wordt opgeslagen in: {DATA_DIR}")
    print(f"📊 Aantal tickers: {len(ALL_TICKERS)}")
    print(f"⏱️  Geschatte tijd: ~{len(ALL_TICKERS) * (DELAY_BETWEEN_REQUESTS + 1) / 60:.1f} minuten\n")
    print("=" * 60)

    # Verzamel alle data in lijsten, combineer aan het eind
    all_prices = []
    all_dividends = []
    all_splits = []
    all_stocks = []

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

        # Prijzen - voeg ticker-kolom toe
        prices = data["prices"].copy()
        prices["ticker"] = ticker
        prices.reset_index(inplace=True)
        prices.rename(columns={"Date": "date"}, inplace=True)
        all_prices.append(prices)

        # Dividenden en splits uit actions
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

        print(f"✅ {len(prices)} dagen, {n_div} div, {n_split} splits")
        success += 1

        # Pauze tussen requests
        if i < len(ALL_TICKERS):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # === Alles opslaan als parquet ===
    print("\n" + "=" * 60)
    print("💾 Opslaan...")

    if all_prices:
        prices_df = pd.concat(all_prices, ignore_index=True)
        # Compactere kolomnamen
        prices_df.columns = [c.lower().replace(" ", "_") for c in prices_df.columns]
        prices_df.to_parquet(DATA_DIR / "prices.parquet", index=False)
        print(f"  ✓ prices.parquet ({len(prices_df):,} rijen)")

    if all_dividends:
        dividends_df = pd.concat(all_dividends, ignore_index=True)
        dividends_df.to_parquet(DATA_DIR / "dividends.parquet", index=False)
        print(f"  ✓ dividends.parquet ({len(dividends_df)} rijen)")
    else:
        # Lege placeholder
        pd.DataFrame(columns=["ticker", "date", "amount"]).to_parquet(
            DATA_DIR / "dividends.parquet", index=False
        )

    if all_splits:
        splits_df = pd.concat(all_splits, ignore_index=True)
        splits_df.to_parquet(DATA_DIR / "splits.parquet", index=False)
        print(f"  ✓ splits.parquet ({len(splits_df)} rijen)")
    else:
        pd.DataFrame(columns=["ticker", "date", "ratio"]).to_parquet(
            DATA_DIR / "splits.parquet", index=False
        )

    stocks_df = pd.DataFrame(all_stocks)
    stocks_df.to_parquet(DATA_DIR / "stocks.parquet", index=False)
    print(f"  ✓ stocks.parquet ({len(stocks_df)} rijen)")

    # Timestamp van update
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (DATA_DIR / "last_update.txt").write_text(timestamp)
    print(f"  ✓ last_update.txt ({timestamp})")

    # === Samenvatting ===
    print("\n" + "=" * 60)
    print(f"✅ Klaar: {success}/{len(ALL_TICKERS)} succesvol")
    if failed:
        print(f"❌ Mislukt: {', '.join(failed)}")
        print(f"\nTip: voer dit script later opnieuw uit, ontbrekende tickers worden opnieuw geprobeerd.")

    # Bestandsgroottes
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
