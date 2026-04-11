"""
Aegis Alpha — Price Fetcher
Runs server-side (no CORS), writes prices.json to repo root.
GitHub Actions calls this every 15 min on trading days.
"""

import json, time, requests
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────
TICKERS = {
    "ADMF": "ADMF.JK",
    "ASII": "ASII.JK",
    "BMRI": "BMRI.JK",
    "ITMG": "ITMG.JK",
    "POWR": "POWR.JK",
}
MARKET_SYMBOLS = {
    "IHSG":  "%5EJKSE",    # Jakarta Composite
    "USDIDR": "IDR%3DX",   # USD/IDR exchange rate
    "COAL":  "MTF%3DF",    # ICE Rotterdam coal futures (Newcastle proxy)
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AegisAlphaBot/1.0)",
    "Accept": "application/json",
}
TIMEOUT = 20

# ── HELPERS ───────────────────────────────────────────────────────────────────
def yf_fetch(symbol: str) -> dict | None:
    """Fetch Yahoo Finance v8 chart endpoint — returns meta dict or None."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo"
    for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
        try:
            url = f"{base}/v8/finance/chart/{symbol}?interval=1d&range=3mo"
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            result = data.get("chart", {}).get("result", [None])[0]
            if result:
                return result
        except Exception as e:
            print(f"  YF {symbol} attempt failed: {e}")
            time.sleep(1)
    return None


def extract_price_and_ohlcv(result: dict) -> dict:
    """Pull price, change%, and last 65 bars of OHLCV from a YF result."""
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice") or meta.get("previousClose", 0)
    prev  = meta.get("chartPreviousClose") or meta.get("previousClose") or price
    chg_pct = round(((price - prev) / prev * 100), 2) if prev else 0.0

    # OHLCV bars (last 65 days for Ichimoku calculation)
    ts   = result.get("timestamp", [])
    q    = result.get("indicators", {}).get("quote", [{}])[0]
    bars = []
    for i, t in enumerate(ts):
        c = q.get("close", [None])[i]
        h = q.get("high",  [None])[i]
        l = q.get("low",   [None])[i]
        o = q.get("open",  [None])[i]
        if c is not None and h is not None and l is not None:
            bars.append({"t": t, "c": round(c, 2), "h": round(h, 2),
                         "l": round(l, 2), "o": round(o or c, 2)})

    # Keep only last 65 bars (enough for Ichimoku 52-period)
    bars = bars[-65:]

    return {
        "price":   round(price, 2),
        "chgPct":  chg_pct,
        "bars":    bars,
        "source":  "yahoo",
    }


def fetch_stooq_price(ticker_lower: str) -> float | None:
    """Stooq CSV fallback — price only."""
    url = f"https://stooq.com/q/l/?s={ticker_lower}.jk&f=sd2t2ohlcv&h&e=csv"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        lines = r.text.strip().split("\n")
        if len(lines) >= 2:
            cols = lines[1].split(",")
            p = float(cols[6]) if len(cols) > 6 else None
            if p and p > 0:
                return round(p, 2)
    except Exception as e:
        print(f"  Stooq {ticker_lower} failed: {e}")
    return None


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    now_utc = datetime.now(timezone.utc)
    output = {
        "updated_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_wib": "",  # filled below
        "stocks": {},
        "market": {},
    }

    # WIB = UTC+7
    from datetime import timedelta
    wib = now_utc + timedelta(hours=7)
    output["updated_wib"] = wib.strftime("%d %b %Y %H:%M WIB")

    print(f"\n{'='*50}")
    print(f"Aegis Price Fetch  —  {output['updated_wib']}")
    print(f"{'='*50}")

    # ── Stock prices ──────────────────────────────────────────────────────────
    for ticker, yf_sym in TICKERS.items():
        print(f"\n[{ticker}] fetching {yf_sym}...")
        result = yf_fetch(yf_sym)
        if result:
            data = extract_price_and_ohlcv(result)
            output["stocks"][ticker] = data
            print(f"  ✓ {ticker}: Rp{data['price']:,}  ({data['chgPct']:+.2f}%)  bars={len(data['bars'])}")
        else:
            # Stooq fallback
            p = fetch_stooq_price(ticker.lower())
            if p:
                output["stocks"][ticker] = {"price": p, "chgPct": 0.0, "bars": [], "source": "stooq"}
                print(f"  ✓ {ticker}: Rp{p:,}  (stooq fallback, no OHLCV)")
            else:
                output["stocks"][ticker] = None
                print(f"  ✕ {ticker}: FAILED — will use cached value in browser")
        time.sleep(0.4)  # be polite to Yahoo

    # ── Market data ───────────────────────────────────────────────────────────
    print("\n[MARKET] fetching IHSG / USD-IDR / Coal...")
    for key, sym in MARKET_SYMBOLS.items():
        result = yf_fetch(sym)
        if result:
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice") or 0
            prev  = meta.get("chartPreviousClose") or price
            chg   = round(((price - prev) / prev * 100), 2) if prev else 0.0
            output["market"][key] = {"price": round(price, 2), "chgPct": chg}
            print(f"  ✓ {key}: {price}  ({chg:+.2f}%)")
        else:
            output["market"][key] = None
            print(f"  ✕ {key}: FAILED")
        time.sleep(0.4)

    # ── Write output ──────────────────────────────────────────────────────────
    with open("prices.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))

    ok = sum(1 for v in output["stocks"].values() if v)
    print(f"\n{'='*50}")
    print(f"Done. Stocks OK: {ok}/{len(TICKERS)}  |  prices.json written.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
