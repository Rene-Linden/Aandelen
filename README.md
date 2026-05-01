# 📈 Stock Analyzer

Een dashboard om koersdata van ~55 aandelen (AEX + S&P 500 + Europa) te analyseren over een periode tot 20 jaar.

**Architectuur:** data wordt lokaal opgehaald via een pipeline-script, opgeslagen als parquet-bestanden, en naar GitHub gepusht. De Streamlit Cloud-app leest die bestanden — supersnel en zonder rate limits.

---

## 🚀 Eerste setup (~10 min, eenmalig per laptop)

### 1. Python installeren

**Windows:**
1. Ga naar [python.org/downloads](https://python.org/downloads)
2. Download Python 3.11 of hoger
3. **Belangrijk:** vink "Add Python to PATH" aan tijdens installatie

**Mac:**
- Open Terminal en typ: `python3 --version`. Als die nog niet bestaat: download van [python.org](https://python.org/downloads) of installeer via Homebrew: `brew install python`

**Verificatie:** open een terminal/cmd, typ `python --version` (Windows) of `python3 --version` (Mac). Je hoort `Python 3.11.x` o.i.d. te zien.

### 2. Git installeren (als je dat nog niet hebt)

- **Windows:** [git-scm.com/download/win](https://git-scm.com/download/win)
- **Mac:** komt meestal mee — typ `git --version` om te checken

### 3. Repository klonen

Open een terminal in een map waar je het project wilt hebben (bv. `Documents/`):

```bash
git clone https://github.com/JOUW-USERNAME/stock-analyzer.git
cd stock-analyzer
```

### 4. Dependencies installeren

```bash
pip install -r requirements.txt
```

Op Mac soms: `pip3 install -r requirements.txt`

Duurt 1-3 minuten.

### 5. Eerste keer data ophalen

```bash
python data_pipeline.py
```

Dit haalt ~55 aandelen × 20 jaar op. **Duurt ~3-5 minuten** (er zit een vertraging tussen requests om rate limits te ontwijken).

### 6. Data committen naar GitHub

```bash
git add data/
git commit -m "Initial data"
git push
```

Vraagt om je GitHub username + password. Bij password vraagt GitHub tegenwoordig om een **Personal Access Token** in plaats van je echte wachtwoord. Maak die aan op [github.com/settings/tokens](https://github.com/settings/tokens) → "Generate new token (classic)" → vink `repo` aan.

### 7. Klaar! 🎉

Je Streamlit Cloud app heeft nu data en werkt. Binnen 1 minuut na de push is hij bijgewerkt.

---

## 🔄 Wekelijks gebruik (~1 min)

```bash
cd stock-analyzer
python data_pipeline.py
git add data/
git commit -m "Update data"
git push
```

Klaar — verse data online.

---

## 📁 Project structuur

```
stock-analyzer/
├── app.py                  # Streamlit dashboard (leest uit data/)
├── data_pipeline.py        # Script dat data ophaalt en opslaat
├── analysis.py             # Financiële berekeningen
├── tickers.py              # Lijst van te volgen aandelen
├── requirements.txt        # Python dependencies
├── .gitignore
├── data/                   # ← wordt gecommit naar GitHub!
│   ├── prices.parquet      # Alle koersen
│   ├── dividends.parquet   # Dividenden
│   ├── splits.parquet      # Aandelensplitsingen
│   ├── stocks.parquet      # Bedrijfsmetadata
│   └── last_update.txt     # Timestamp
└── README.md
```

---

## ➕ Aandelen toevoegen

1. Open `tickers.py`
2. Voeg een entry toe:
   ```python
   "TICKER.AS": "Bedrijfsnaam",
   ```
3. Run `python data_pipeline.py`
4. `git add data/ tickers.py && git commit -m "Add ticker" && git push`

Yahoo Finance suffixen:
- `.AS` = Amsterdam
- `.DE` = Xetra (Duitsland)
- `.PA` = Parijs
- (geen suffix) = Amerikaanse beurs

---

## 💻 Lokaal testen (optioneel)

Je kunt de dashboard ook lokaal draaien, voor of na een data-update:

```bash
streamlit run app.py
```

Opent automatisch op `http://localhost:8501`. Stoppen met Ctrl+C.

---

## 🆕 Op een andere laptop installeren

Volg gewoon **stappen 1-3** hierboven (Python + Git + clone). De data zit al in de repo, dus je hoeft `data_pipeline.py` niet meteen te draaien — je hebt direct werkende data. Pas runnen wanneer je een update wilt.

---

## ❓ Troubleshooting

**`python: command not found`** (Mac)
→ Probeer `python3` in plaats van `python`

**Rate-limit errors tijdens pipeline**
→ Het script heeft retry-logica (wacht 30 sec en probeert opnieuw). Als bepaalde tickers blijven falen: run `python data_pipeline.py` later nog een keer, alleen die paar.

**`git push` vraagt om wachtwoord en weigert**
→ GitHub accepteert geen wachtwoord meer voor git. Je moet een Personal Access Token gebruiken. Zie stap 6 hierboven.

**Streamlit Cloud zegt "no data"**
→ Check of `data/` map in je GitHub repo zit. Als die leeg is: pipeline lokaal runnen en pushen.

---

## ⚠️ Disclaimer

Dit is een leertool. Niets in deze app is beleggingsadvies. Historische koersen voorspellen geen toekomstige resultaten.
