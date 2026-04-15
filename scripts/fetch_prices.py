import json, time, requests
from datetime import datetime, timezone, timedelta

TICKERS = {
    "ADMF": "ADMF.JK",
    "ASII": "ASII.JK",
    "BMRI": "BMRI.JK",
    "ITMG": "ITMG.JK",
    "INDF": "INDF.JK"
}
MARKET_SYMBOLS = {
    "IHSG": "%5EJKSE",
    "USDIDR": "IDR%3DX",
    "COAL": "MTF%3DF"
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AegisAlpha/1.5"}

def fetch_yf(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        res = data["chart"]["result"][0]
        meta = res["meta"]
        q = res["indicators"]["quote"][0]
        ts = res["timestamp"]
        
        bars = []
        for i in range(len(ts)):
            if q["close"][i] is not None:
                bars.append({"t": ts[i], "h": q["high"][i], "l": q["low"][i], "c": q["close"][i]})
        return {"price": meta["regularMarketPrice"], "prev": meta["chartPreviousClose"], "bars": bars[-65:]}
    except: return None

def main():
    now_utc = datetime.now(timezone.utc)
    wib = now_utc + timedelta(hours=7)
    output = {"updated_wib": wib.strftime("%d %b %Y %H:%M WIB"), "stocks": {}, "market": {}}

    for ticker, sym in TICKERS.items():
        data = fetch_yf(sym)
        if data:
            chg = round(((data["price"] - data["prev"]) / data["prev"] * 100), 2)
            output["stocks"][ticker] = {"price": data["price"], "chgPct": chg, "bars": data["bars"]}
        time.sleep(1)

    for k, sym in MARKET_SYMBOLS.items():
        data = fetch_yf(sym)
        if data:
            chg = round(((data["price"] - data["prev"]) / data["prev"] * 100), 2)
            output["market"][k] = {"price": data["price"], "chgPct": chg}

    with open("prices.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

if __name__ == "__main__":
    main()
