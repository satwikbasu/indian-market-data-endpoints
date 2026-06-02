"""NSE clients: daily multi-index CSV archive + niftyindices.com TRI API.

Wire specs:
  endpoints/nse-daily-indices.md
  endpoints/niftyindices-tri-api.md
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterator

import httpx

log = logging.getLogger(__name__)

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
    log.info("NSE indices CSV: GET %s (timeout=%.0fs)", url, timeout)
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        for attempt in range(retries):
            t0 = time.monotonic()
            try:
                r = c.get(url)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                log.warning("NSE indices CSV: %s on attempt %d/%d after %.1fs",
                            type(exc).__name__, attempt + 1, retries, time.monotonic() - t0)
                if attempt == retries - 1:
                    raise
                log.info("NSE indices CSV: sleeping %.0fs before retry", backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            if r.status_code == 404:
                log.info("NSE indices CSV: 404 (non-trading day) for %s", d.isoformat())
                return None
            r.raise_for_status()
            # NSE error pages come as 200 OK with short bodies; real CSVs are 16-20 KB.
            if len(r.content) < 5_000:
                log.warning("NSE indices CSV: short body (%d bytes) on attempt %d/%d — error shell, retrying",
                            len(r.content), attempt + 1, retries)
                time.sleep(backoff)
                backoff *= 2
                continue
            log.info("NSE indices CSV: OK %d bytes in %.1fs", len(r.content), time.monotonic() - t0)
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

# niftyindices.com sits behind Akamai bot detection. A bot-style UA causes the
# POST to stall (server accepts the request then never sends a body). A browser
# UA passes through in <1s. The bse.py module uses the same trick.
_TRI_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
           "indian-markets-py/0.1")

_TRI_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": TRI_REFERER,
    "User-Agent": _TRI_UA,
}


def fetch_tri(
    name: str, start: str, end: str, *,
    timeout: float = 120.0, sleep_s: float = 1.0, retries: int = 5,
) -> list[dict]:
    """Fetch Total Return Index rows for one Nifty index, inception-to-today.

    name: canonical Nifty index name, e.g. 'NIFTY 50', 'NIFTY MIDCAP 150'
    start, end: 'DD-MMM-YYYY' (e.g. '01-Jan-1999')

    Returns rows sorted most-recent first. Each row:
      {'Index Name': 'Nifty 50', 'Date': '22 May 2026',
       'TotalReturnsIndex': '35793.78', 'NTR_Value': '31169.3', ...}

    Empty list = unknown index name (server returns d:"[]" with HTTP 200 — no error).

    Default timeout is 120s because the niftyindices server is slow on
    inception-to-today payloads (~6500 rows, ~600 KB) and can take 30-90s.
    """
    inner = f"{{'name':'{name}','startDate':'{start}','endDate':'{end}','indexName':'{name}'}}"
    payload = json.dumps({"cinfo": inner})
    backoff = 2.0
    log.info("niftyindices TRI: %r range %s..%s (timeout=%.0fs, retries=%d)",
             name, start, end, timeout, retries)
    with httpx.Client(timeout=timeout, headers=_TRI_HEADERS, follow_redirects=True) as c:
        # Attempt cookie prime via the report page, but with a TIGHT sub-timeout:
        # Akamai often serves the HTML page slowly or not at all to non-browser UAs,
        # while the JSON API endpoint itself responds in <1s. We do NOT want the
        # bootstrap to eat the per-request budget. The POST works without cookies
        # in practice; the bootstrap is belt-and-braces for future Akamai changes.
        try:
            log.debug("niftyindices TRI: bootstrap GET %s (5s budget)", TRI_REFERER)
            c.get(TRI_REFERER, timeout=5.0)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            log.info("niftyindices TRI: bootstrap GET %s; continuing cookieless",
                     type(exc).__name__)
        for attempt in range(retries):
            t0 = time.monotonic()
            try:
                r = c.post(TRI_URL, content=payload)
                r.raise_for_status()
                rows = json.loads(r.json()["d"])
                elapsed = time.monotonic() - t0
                log.info("niftyindices TRI: %r -> %d rows in %.1fs", name, len(rows), elapsed)
                if not rows:
                    log.warning("niftyindices TRI: empty rows for %r — canonical-name mismatch?", name)
                time.sleep(sleep_s)
                return rows
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError,
                    json.JSONDecodeError, KeyError) as exc:
                log.warning("niftyindices TRI: %s for %r on attempt %d/%d after %.1fs",
                            type(exc).__name__, name, attempt + 1, retries, time.monotonic() - t0)
                if attempt == retries - 1:
                    raise
                log.info("niftyindices TRI: sleeping %.0fs before retry", backoff)
                time.sleep(backoff)
                backoff *= 2
    return []
