"""AMFI clients: NAVAll snapshot, NAV history archive, daily TER, monthly AAUM.

Wire specs:
  endpoints/amfi-navall.md
  endpoints/amfi-navhistory.md
  endpoints/amfi-ter-api.md
  endpoints/amfi-monthly-aaum.md
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

import httpx

log = logging.getLogger(__name__)

UA = "indian-markets-py/0.1 (+https://github.com/satwikbasu/indian-market-data-endpoints)"
NAVALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
NAVHIST_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
TER_AMC_LIST_URL = "https://www.amfiindia.com/api/populate-mf"
TER_DATA_URL = "https://www.amfiindia.com/api/populate-te-rdata-revised"
AAUM_MONTHLY_URL_FMT = "https://portal.amfiindia.com/spages/am{mmm}{yyyy}repo.{ext}"


# ---------------------------------------------------------------------------
# NAVAll.txt — daily snapshot of every scheme
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^(?P<type>[^()]+?)\((?P<category>.+)\)\s*$")
_AMC_SUFFIXES = (" Mutual Fund", " Trustee Ltd", " Trustee Limited", " Trustee Co Ltd")


@dataclass(frozen=True)
class NavRow:
    scheme_code: int
    nav_date: date
    nav: Decimal
    scheme_name: str
    isin_growth: str | None
    isin_reinvest: str | None
    amc: str
    scheme_type: str
    scheme_category: str


def _classify_section(line: str) -> tuple[str, str, str | None]:
    """Return ('amc', amc, category_or_None) or ('section', type, category)."""
    m = _SECTION_RE.match(line)
    if not m:
        return ("amc", line, None)
    left, right = m.group("type").strip(), m.group("category").strip()
    if any(left.endswith(s) for s in _AMC_SUFFIXES):
        return ("amc", left, right)
    return ("section", left, right)


def fetch_navall_text(timeout: float = 30.0) -> str:
    """Fetch the raw NAVAll.txt body. ~3 MB."""
    log.info("AMFI NAVAll: GET %s (timeout=%.0fs)", NAVALL_URL, timeout)
    t0 = time.monotonic()
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        r = c.get(NAVALL_URL)
        r.raise_for_status()
        log.info("AMFI NAVAll: OK %.2f MB in %.1fs",
                 len(r.content) / 1e6, time.monotonic() - t0)
        return r.text


def parse_navall(text: str) -> Iterator[NavRow]:
    """Yield one NavRow per data line. Carries AMC + scheme_type + category as rolling state."""
    amc = scheme_type = scheme_category = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            kind, a, b = _classify_section(line)
            if kind == "section":
                scheme_type, scheme_category = a, b
            else:
                amc = a
                if b is not None:
                    scheme_type, scheme_category = "Unspecified", b
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != 6 or parts[0] == "Scheme Code":
            continue
        code, isin_g, isin_r, name, nav_s, date_s = parts
        if amc is None or scheme_type is None or scheme_category is None:
            continue
        try:
            scheme_code = int(code)
            nav = Decimal(nav_s)
            nav_date = datetime.strptime(date_s, "%d-%b-%Y").date()
        except (ValueError, InvalidOperation):
            continue
        if nav == 0:
            continue
        yield NavRow(
            scheme_code=scheme_code, nav_date=nav_date, nav=nav, scheme_name=name,
            isin_growth=None if isin_g in ("", "-") else isin_g,
            isin_reinvest=None if isin_r in ("", "-") else isin_r,
            amc=amc, scheme_type=scheme_type, scheme_category=scheme_category,
        )


def fetch_navall_rows(timeout: float = 30.0) -> Iterator[NavRow]:
    """Convenience: fetch + parse in one call."""
    yield from parse_navall(fetch_navall_text(timeout=timeout))


# ---------------------------------------------------------------------------
# NAV history archive — date-range backfill (chunks of ≤7 days recommended)
# ---------------------------------------------------------------------------

STUB_BODY_BYTES_MAX = 50_000


def fetch_navhistory_text(
    from_date: str, to_date: str, *, retries: int = 3, timeout: float = 90.0
) -> str:
    """Fetch one date-range chunk. Retries on AMFI's stub-body pattern.

    Dates: 'DD-MMM-YYYY' (e.g. '01-Jan-2024').
    """
    params = {"frmdt": from_date, "todt": to_date}
    log.info("AMFI NAV history: GET %s..%s", from_date, to_date)
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        for attempt in range(retries):
            t0 = time.monotonic()
            r = c.get(NAVHIST_URL, params=params)
            r.raise_for_status()
            if len(r.content) > STUB_BODY_BYTES_MAX:
                log.info("AMFI NAV history: OK %d bytes in %.1fs",
                         len(r.content), time.monotonic() - t0)
                return r.text
            backoff = 5 * (attempt + 1)
            log.warning("AMFI NAV history: stub body (%d bytes) on attempt %d/%d; sleeping %.0fs",
                        len(r.content), attempt + 1, retries, backoff)
            time.sleep(backoff)
        raise RuntimeError(f"NAV history stub body after {retries} attempts ({from_date}..{to_date})")


def parse_navhistory(text: str) -> Iterator[NavRow]:
    """Yield NavRow per data line. Format has 8 fields (vs 6 in NAVAll)."""
    amc = scheme_type = scheme_category = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            # NAV history uses spaced parens: 'Open Ended Schemes ( ... )'
            normalised = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", line))
            kind, a, b = _classify_section(normalised)
            if kind == "section":
                scheme_type, scheme_category = a, b
            else:
                amc = a
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != 8 or parts[0] == "Scheme Code":
            continue
        code, name, isin_g, isin_r, nav_s, _repur, _sale, date_s = parts
        if amc is None or scheme_type is None or scheme_category is None:
            continue
        try:
            scheme_code = int(code)
            nav = Decimal(nav_s)
            nav_date = datetime.strptime(date_s, "%d-%b-%Y").date()
        except (ValueError, InvalidOperation):
            continue
        if nav == 0:
            continue
        yield NavRow(
            scheme_code=scheme_code, nav_date=nav_date, nav=nav, scheme_name=name,
            isin_growth=isin_g or None, isin_reinvest=isin_r or None,
            amc=amc, scheme_type=scheme_type, scheme_category=scheme_category,
        )


def fetch_navhistory_rows(from_date: str, to_date: str) -> Iterator[NavRow]:
    yield from parse_navhistory(fetch_navhistory_text(from_date, to_date))


# ---------------------------------------------------------------------------
# Daily TER JSON API
# ---------------------------------------------------------------------------

def fetch_amc_list(timeout: float = 30.0) -> list[dict]:
    """List of ~55 AMCs with mfId. Use mfId for fetch_ter()."""
    log.info("AMFI AMC list: GET %s", TER_AMC_LIST_URL)
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        r = c.get(TER_AMC_LIST_URL)
        r.raise_for_status()
        data = r.json()
        log.info("AMFI AMC list: %d AMCs", len(data))
        return data


def fetch_ter(
    mf_id: int | str, month: str, *, str_cat: str = "-1", str_type: str = "1",
    page_size: int = 10000, timeout: float = 30.0, sleep_s: float = 1.0,
    retries: int = 3,
) -> list[dict]:
    """TER rows for one AMC × one month. month='MM-YYYY' e.g. '05-2026'.

    AMFI rate-limits aggressively and may return HTTP 200 with truncated JSON;
    retry on JSONDecodeError with exponential backoff.
    """
    params = {
        "MF_ID": str(mf_id), "Month": month,
        "strCat": str_cat, "strType": str_type, "page": "1", "pageSize": str(page_size),
    }
    backoff = 2.0
    log.info("AMFI TER: mf_id=%s month=%s", mf_id, month)
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as c:
        for attempt in range(retries):
            t0 = time.monotonic()
            r = c.get(TER_DATA_URL, params=params)
            r.raise_for_status()
            try:
                payload = r.json()
                data = payload.get("data", [])
                log.info("AMFI TER: %d rows in %.1fs", len(data), time.monotonic() - t0)
                time.sleep(sleep_s)
                return data
            except json.JSONDecodeError as exc:
                log.warning("AMFI TER: %s on attempt %d/%d (%d bytes); sleeping %.0fs",
                            type(exc).__name__, attempt + 1, retries, len(r.content), backoff)
                if attempt == retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
    return []


# ---------------------------------------------------------------------------
# Monthly categorywise AAUM (raw bytes — XLS/PDF parser left to caller)
# ---------------------------------------------------------------------------

def fetch_aaum_bytes(year: int, month: int, *, prefer_revised: bool = True,
                     timeout: float = 60.0) -> tuple[bytes, str]:
    """Fetch one monthly AAUM file. Returns (bytes, format) where format ∈ {'xls', 'pdf'}.

    Tries `reporevised.xls` → `repo.xls` → `repo.pdf`. XLS for ≥ mid-2018, PDF for older.
    Caller parses with xlrd / openpyxl / pymupdf depending on era. The MCR_Report
    categorywise structure only stabilised April 2019 — older files use a legacy
    4-sheet per-AMC layout.
    """
    mmm = date(year, month, 1).strftime("%b").lower()
    candidates: list[tuple[str, str]] = []
    if prefer_revised:
        candidates.append((AAUM_MONTHLY_URL_FMT.format(mmm=mmm, yyyy=year, ext="xls").replace("repo", "reporevised"), "xls"))
    candidates.extend([
        (AAUM_MONTHLY_URL_FMT.format(mmm=mmm, yyyy=year, ext="xls"), "xls"),
        (AAUM_MONTHLY_URL_FMT.format(mmm=mmm, yyyy=year, ext="pdf"), "pdf"),
    ])
    log.info("AMFI AAUM: trying %d candidate URLs for %d-%02d", len(candidates), year, month)
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}, follow_redirects=True) as c:
        for url, fmt in candidates:
            t0 = time.monotonic()
            r = c.get(url)
            log.info("AMFI AAUM: %s -> HTTP %d (%d bytes) in %.1fs",
                     url, r.status_code, len(r.content), time.monotonic() - t0)
            if r.status_code == 200 and len(r.content) > 5_000:
                return r.content, fmt
    raise FileNotFoundError(f"no AAUM file for {year}-{month:02d}")
