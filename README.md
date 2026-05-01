# 📈 Stock Analyzer — Cloud versie

Een dashboard om koersdata van ~55 aandelen (AEX + S&P 500 + Europa) te analyseren over een periode tot 20 jaar. Data komt live van Yahoo Finance, gecached voor 24 uur.

## 🚀 Online deployen via Streamlit Community Cloud (gratis)

### Stap 1: Maak een nieuwe GitHub repository
1. Ga naar [github.com/new](https://github.com/new)
2. Naam: bijvoorbeeld `stock-analyzer`
3. Zet op **Public** (vereist voor gratis Streamlit Cloud)
4. Klik **Create repository**

### Stap 2: Upload de bestanden
Drie manieren, kies wat je het makkelijkst vindt:

**Makkelijkst — via de website:**
1. In je nieuwe repo, klik **"uploading an existing file"**
2. Sleep alle 4 bestanden (`app.py`, `analysis.py`, `tickers.py`, `requirements.txt`) erin
3. Klik **"Commit changes"**

**Of via Git command line:**
```bash
git clone https://github.com/JOUW-USERNAME/stock-analyzer.git
cd stock-analyzer
# Kopieer de bestanden hierin
git add .
git commit -m "Initial version"
git push
```

### Stap 3: Deploy op Streamlit Cloud
1. Ga naar [share.streamlit.io](https://share.streamlit.io)
2. Log in met je GitHub-account
3. Klik **"New app"**
4. Vul in:
   - Repository: `JOUW-USERNAME/stock-analyzer`
   - Branch: `main`
   - Main file path: `app.py`
5. Klik **"Deploy!"**

Na ~2 minuten heb je een URL zoals `https://JOUW-USERNAME-stock-analyzer.streamlit.app`

### Stap 4: Klaar! 🎉
- App is live, deelbaar via URL
- Werkt op laptop, telefoon, tablet
- Wijzigingen op GitHub → automatisch live binnen 1 minuut

## 💻 Lokaal testen (optioneel)

Wil je eerst lokaal testen voor je deployt:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📁 Bestanden

```
stock-analyzer/
├── app.py              # De Streamlit app (frontend + logic)
├── analysis.py         # Financiële berekeningen
├── tickers.py          # Lijst van aandelen
└── requirements.txt    # Python dependencies
```

## ➕ Aandelen toevoegen

Open `tickers.py`, voeg een entry toe, push naar GitHub. Yahoo Finance suffixen:
- `.AS` = Amsterdam
- `.DE` = Xetra (Duitsland)
- `.PA` = Parijs

## ⚙️ Hoe het werkt

- Yfinance haalt data op van Yahoo Finance
- Streamlit cached die data 24 uur per aandeel
- Eerste opvraag: ~5-30 seconden afhankelijk van periode
- Daarna: instant uit cache

## ⚠️ Disclaimer

Dit is een leertool. Niets in deze app is beleggingsadvies. Historische koersen voorspellen geen toekomstige resultaten.
