"""Client untuk OKX public API (tanpa auth/API key -- semua endpoint yang
dipakai di sini bersifat publik). Port dari packages/fetcher, packages/engine
(fetchCandles) dan packages/tracker (fetchMarkPrice) di trading-main.

OKX dipilih (bukan Binance) karena endpoint publiknya dapat diakses tanpa
kendala geo-restriction, sesuai keputusan yang sudah diambil di kode asli
(lihat komentar "our current source (OKX public candles)" di beberapa file).
Bybit adalah alternatif yang juga layak jika suatu saat OKX bermasalah.
"""
import time
from typing import List, Optional

import requests

OKX_API_BASE = "https://www.okx.com"
INST_ID = "BTC-USDT-SWAP"  # symbol Binance-style BTCUSDT -> OKX instId

BAR_MAP = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
    "1d": "1D", "3d": "3D", "1w": "1W", "1M": "1M",
}

BAR_DURATION_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000, "12h": 43_200_000,
    "1d": 86_400_000, "3d": 259_200_000, "1w": 604_800_000, "1M": 2_592_000_000,
}

_session = requests.Session()


def _parse_candle(row: List[str], duration_ms: int) -> dict:
    """Baris candle OKX: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm].
    `volume` diambil dari volCcy (index 6), sama seperti kode asli."""
    return {
        "openTime": int(row[0]),
        "open": row[1],
        "high": row[2],
        "low": row[3],
        "close": row[4],
        "volume": row[6],
        "closeTime": int(row[0]) + duration_ms,
        "takerBuyVolume": "0",  # tidak tersedia dari OKX; tidak dipakai di scoring
        "isClosed": row[8] == "1",
    }


def fetch_candles(timeframe: str, limit: int = 100) -> List[dict]:
    """Fetch `limit` candle terakhir untuk timeframe tertentu, oldest-first,
    hanya candle yang sudah closed."""
    bar = BAR_MAP[timeframe]
    url = f"{OKX_API_BASE}/api/v5/market/candles"
    resp = _session.get(url, params={"instId": INST_ID, "bar": bar, "limit": limit}, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != "0":
        raise RuntimeError(f"OKX API error: code {body.get('code')} {body.get('msg')}")

    duration_ms = BAR_DURATION_MS.get(timeframe, 0)
    # OKX mengembalikan newest-first; reverse jadi oldest-first.
    candles = [_parse_candle(row, duration_ms) for row in reversed(body["data"])]
    return [c for c in candles if c["isClosed"]]


def fetch_historical_candles(timeframe: str, days: int) -> List[dict]:
    """Paginated fetch candle historis via endpoint history-candles, untuk
    backtest. Port dari packages/backtest/src/okxHistory.ts."""
    duration_ms = BAR_DURATION_MS[timeframe]
    cutoff = int(time.time() * 1000) - days * 86_400_000
    bar = BAR_MAP[timeframe]

    rows_by_ts = {}
    after: Optional[int] = None
    page = 0
    max_retries = 4

    while True:
        page += 1
        params = {"instId": INST_ID, "bar": bar, "limit": 100}
        if after is not None:
            params["after"] = after

        body = None
        for attempt in range(max_retries + 1):
            try:
                resp = _session.get(f"{OKX_API_BASE}/api/v5/market/history-candles", params=params, timeout=15)
                if resp.status_code == 429:
                    raise RuntimeError("rate limited (429)")
                resp.raise_for_status()
                body = resp.json()
                break
            except Exception as exc:  # noqa: BLE001
                if attempt < max_retries:
                    delay = 0.8 * (attempt + 1)
                    print(f"  fetch failed (attempt {attempt + 1}/{max_retries + 1}), retry in {delay}s: {exc}")
                    time.sleep(delay)
                else:
                    raise

        if body.get("code") != "0":
            raise RuntimeError(f"OKX history-candles error: code {body.get('code')} {body.get('msg')}")

        rows = body.get("data") or []
        if not rows:
            break

        for row in rows:
            rows_by_ts[int(row[0])] = row

        oldest_ts_in_page = int(rows[-1][0])
        print(f"  {timeframe}: page {page}, {len(rows_by_ts)} candles so far")

        if oldest_ts_in_page <= cutoff:
            break

        after = oldest_ts_in_page
        time.sleep(0.3)

    sorted_rows = sorted(rows_by_ts.items(), key=lambda kv: kv[0])
    return [_parse_candle(row, duration_ms) for ts, row in sorted_rows if ts >= cutoff]


def fetch_mark_price() -> dict:
    """Fetch mark price + funding rate BTC-USDT-SWAP dari OKX."""
    mark_resp = _session.get(
        f"{OKX_API_BASE}/api/v5/public/mark-price",
        params={"instType": "SWAP", "instId": INST_ID},
        timeout=15,
    )
    mark_resp.raise_for_status()
    funding_resp = _session.get(
        f"{OKX_API_BASE}/api/v5/public/funding-rate",
        params={"instId": INST_ID},
        timeout=15,
    )
    funding_resp.raise_for_status()

    mark_json = mark_resp.json()
    funding_json = funding_resp.json()

    if mark_json.get("code") != "0" or not mark_json.get("data"):
        raise RuntimeError(f"OKX mark-price error: code {mark_json.get('code')}")
    if funding_json.get("code") != "0" or not funding_json.get("data"):
        raise RuntimeError(f"OKX funding-rate error: code {funding_json.get('code')}")

    mark = mark_json["data"][0]
    funding = funding_json["data"][0]

    return {
        "symbol": mark["instId"],
        "markPrice": float(mark["markPx"]),
        "indexPrice": float(mark["markPx"]),  # OKX tidak punya index price terpisah
        "lastFundingRate": float(funding["fundingRate"]),
        "nextFundingTime": int(funding["nextFundingTime"]),
        "timestamp": int(time.time() * 1000),
    }


def fetch_mark_price_with_retry(retries: int = 2) -> dict:
    last_error = None
    for attempt in range(retries + 1):
        try:
            return fetch_mark_price()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1) ** 2)
    raise last_error
