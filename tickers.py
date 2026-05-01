"""
Lijst met aandelen om te volgen.
Yahoo Finance gebruikt suffixen voor niet-US beurzen:
  .AS = Amsterdam (AEX)
  .DE = Xetra (Duitsland)
  .PA = Parijs
US-aandelen hebben geen suffix.
"""

AEX_TICKERS = {
    "ASML.AS": "ASML Holding",
    "SHELL.AS": "Shell",
    "UNA.AS": "Unilever",
    "INGA.AS": "ING Groep",
    "PHIA.AS": "Philips",
    "AD.AS": "Ahold Delhaize",
    "HEIA.AS": "Heineken",
    "ADYEN.AS": "Adyen",
    "MT.AS": "ArcelorMittal",
    "AKZA.AS": "AkzoNobel",
    "RAND.AS": "Randstad",
    "WKL.AS": "Wolters Kluwer",
    "REN.AS": "Relx",
    "KPN.AS": "KPN",
    "PRX.AS": "Prosus",
    "ABN.AS": "ABN AMRO",
    "ASRNL.AS": "ASR Nederland",
    "NN.AS": "NN Group",
    "BESI.AS": "BE Semiconductor",
    "DSFIR.AS": "DSM-Firmenich",
}

US_TICKERS = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet (Google)",
    "AMZN": "Amazon",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "NVDA": "NVIDIA",
    "JPM": "JPMorgan Chase",
    "JNJ": "Johnson & Johnson",
    "V": "Visa",
    "WMT": "Walmart",
    "PG": "Procter & Gamble",
    "XOM": "ExxonMobil",
    "BAC": "Bank of America",
    "KO": "Coca-Cola",
    "DIS": "Walt Disney",
    "NFLX": "Netflix",
    "INTC": "Intel",
    "CSCO": "Cisco",
    "PFE": "Pfizer",
    "BA": "Boeing",
    "GE": "General Electric",
    "GS": "Goldman Sachs",
    "MCD": "McDonald's",
    "NKE": "Nike",
    "IBM": "IBM",
    "ORCL": "Oracle",
    "PYPL": "PayPal",
    "ADBE": "Adobe",
    "CRM": "Salesforce",
}

EUROPE_OTHER = {
    "SAP.DE": "SAP",
    "SIE.DE": "Siemens",
    "VOW3.DE": "Volkswagen",
    "MC.PA": "LVMH",
    "OR.PA": "L'Oréal",
}

ALL_TICKERS = {**AEX_TICKERS, **US_TICKERS, **EUROPE_OTHER}


def get_ticker_list():
    return list(ALL_TICKERS.keys())


def get_company_name(ticker):
    return ALL_TICKERS.get(ticker, ticker)


def get_market(ticker):
    if ticker.endswith(".AS"):
        return "AEX"
    elif ticker.endswith(".DE"):
        return "Xetra"
    elif ticker.endswith(".PA"):
        return "Paris"
    else:
        return "US"
