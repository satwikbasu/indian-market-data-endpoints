"""NSE clients: daily multi-index CSV archive + niftyindices.com TRI API.

Wire specs:
  endpoints/nse-daily-indices.md
  endpoints/niftyindices-tri-api.md
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterator

import httpx

UA = "indian-markets-py/0.1 (+https://github.com/satwikbasu/indian-market-data-endpoints)"
INDICES_CSV_URL_FMT = "https://archives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
TRI_URL = "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString"
TRI_REFERER = "https://www.niftyindices.com/reports/historical-data"


# ---------------------------------------------------------------------------
# NSE daily multi-index CSV archive
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexRow:
    index_name: str
    index_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    pe: Decimal | None
    pb: Decimal | None
    div_yield: Decimal | None


def fetch_indices_csv_text(d: date, *, timeout: float = 30.0, retries: int = 3) -> str | None:
    """Fetch one business-day CSV. Returns None for 404 (weekend/holiday)."""
    url = INDICES_CSV_URL_FMT.format(ddmmyyyy=d.strftime("%d%m%Y"))
    backoff = 5.0
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        for attempt in range(retries):
            try:
                r = c.get(url)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            # NSE error pages come as 200 OK with short bodies; real CSVs are 16-20 KB.
            if len(r.content) < 5_000:
                time.sleep(backoff)
                backoff *= 2
                continue
            return r.text
    return None


def _decimal_or_none(s: str) -> Decimal | None:
    s = s.strip()
    if not s or s == "-":
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def parse_indices_csv(text: str) -> Iterator[IndexRow]:
    """Yield IndexRow per data line. Skips header + derivative-index rows with '-' values."""
    lines = text.splitlines()
    if not lines:
        return
    # Header layout: Index Name,Index Date,Open,High,Low,Closing,Points Change,Change(%),Volume,Turnover,P/E,P/B,Div Yield
    for raw in lines[1:]:
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 13:
            continue
        try:
            from datetime import datetime
            d = datetime.strptime(parts[1], "%d-%m-%Y").date()
            o = _decimal_or_none(parts[2]); h = _decimal_or_none(parts[3])
            lo = _decimal_or_none(parts[4]); c = _decimal_or_none(parts[5])
            if o is None or c is None:
                continue
            yield IndexRow(
                index_name=parts[0], index_date=d,
                open=o, high=h or o, low=lo or o, close=c,
                pe=_decimal_or_none(parts[10]),
                pb=_decimal_or_none(parts[11]),
                div_yield=_decimal_or_none(parts[12]),
            )
        except Exception:
            continue


def fetch_indices_csv(*, year: int, month: int, day: int) -> list[IndexRow]:
    """Convenience: fetch + parse. Returns [] for non-trading days."""
    text = fetch_indices_csv_text(date(year, month, day))
    return list(parse_indices_csv(text)) if text else []


# ---------------------------------------------------------------------------
# niftyindices.com TRI — Total Return Index, inception-to-today
# ---------------------------------------------------------------------------

_TRI_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": TRI_REFERER,
    "User-Agent": UA,
}


def _bootstrap_session(timeout: float = 30.0) -> httpx.Client:
    """Prime cookies by visiting the report page first (Akamai-friendly)."""
    c = httpx.Client(timeout=timeout, headers=_TRI_HEADERS, follow_redirects=True)
    try:
        c.get(TRI_REFERER)
    except (httpx.TimeoutException, httpx.NetworkError):
        pass
    return c


def fetch_tri(
    name: str, start: str, end: str, *,
    timeout: float = 60.0, sleep_s: float = 1.0, retries: int = 5,
) -> list[dict]:
    """Fetch Total Return Index rows for one Nifty index, inception-to-today.

    name: canonical Nifty index name, e.g. 'NIFTY 50', 'NIFTY MIDCAP 150'
    start, end: 'DD-MMM-YYYY' (e.g. '01-Jan-1999')

    Returns rows sorted most-recent first. Each row:
      {'Index Name': 'Nifty 50', 'Date': '22 May 2026',
       'TotalReturnsIndex': '35793.78', 'NTR_Value': '31169.3', ...}

    Empty list = unknown index name (server returns d:"[]" with HTTP 200 — no error).
    """
    inner = f"{{'name':'{name}','startDate':'{start}','endDate':'{end}','indexName':'{name}'}}"
    payload = json.dumps({"cinfo": inner})
    backoff = 2.0
    with _bootstrap_session(timeout=timeout) as c:
        for attempt in range(retries):
            try:
                r = c.post(TRI_URL, content=payload)
                r.raise_for_status()
                rows = json.loads(r.json()["d"])
                time.sleep(sleep_s)
                return rows
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError,
                    json.JSONDecodeError, KeyError):
                if attempt == retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
    return []
