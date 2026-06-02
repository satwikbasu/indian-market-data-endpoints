"""BSE LODR Reg 31 shareholding-pattern client.

Wire spec: endpoints/lodr-shareholding.md

Two calls per scrip:
  1. fetch_shareholding_index(scripcode) -> list of quarterly filings + iXBRL paths
  2. fetch_xbrl_filing(attachment_path) -> raw iXBRL bytes

HEADER TRAP: do NOT set Origin. With Origin: https://www.bseindia.com the API
returns a 1814-byte error shell at HTTP 200. The User-Agent + Referer combo
without Origin returns clean JSON.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

# Browser-like UA is required; a non-browser UA returns the SPA shell.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
      "indian-markets-py/0.1")

_API_BASE = "https://api.bseindia.com/BseIndiaAPI/api/Corp_Shareholding_ng/w"
_FILING_BASE = "https://www.bseindia.com"

# Load-bearing headers. Origin is INTENTIONALLY OMITTED.
_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json, text/plain, */*",
}


def fetch_shareholding_index(
    scripcode: int | str, *, flag: str = "0", indtype: str = "",
    timeout: float = 30.0, retries: int = 3,
) -> list[dict[str, Any]]:
    """List quarterly shareholding-pattern filings for one BSE scrip.

    Returns the `Table` array. Each row has FLD_ScripCode, sQtrName, EndDate,
    IsXBRL, XBRLAttachment, etc. Pass the attachment path to fetch_xbrl_filing().

    flag='0' is the only useful value (full historical list).
    indtype='' (empty string) means "all industries"; param must be present.
    """
    params = {"scripcode": str(scripcode), "flag": flag, "indtype": indtype}
    backoff = 2.0
    with httpx.Client(timeout=timeout, headers=_HEADERS, follow_redirects=False) as c:
        for attempt in range(retries):
            try:
                r = c.get(_API_BASE, params=params)
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                # Canary: if Origin enforcement gets added later, the response
                # flips from JSON to text/html. Treat that as the breakage signal.
                if "html" in ctype.lower():
                    raise RuntimeError(
                        "BSE returned text/html — Origin enforcement may have been added, "
                        "or User-Agent is not browser-like enough."
                    )
                data = r.json()
                return data.get("Table", []) or []
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError):
                if attempt == retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
    return []


def fetch_xbrl_filing(attachment_path: str, *, timeout: float = 60.0) -> bytes:
    """Download one iXBRL filing. Returns raw bytes (~1.2-1.4 MB).

    attachment_path: the XBRLAttachment value from fetch_shareholding_index(),
                     e.g. '/XBRLFILES/SHPXBRLDataXML/500325_2142026131656_SP.html'
    """
    if not attachment_path.startswith("/"):
        attachment_path = "/" + attachment_path
    url = _FILING_BASE + attachment_path
    with httpx.Client(timeout=timeout, headers=_HEADERS, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content
