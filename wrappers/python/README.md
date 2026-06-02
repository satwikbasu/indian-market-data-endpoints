# indian-markets (Python wrapper library)

Minimal Python clients for the endpoints catalogued in this repo. Fetcher + parser, no DB, no caching, no retry framework. ~80-120 LOC per module.

## Install

```bash
pip install -e .
# optional: XLS/XBRL extras for AAUM and LODR parsing
pip install -e ".[xls,xbrl]"
```

## Usage

```python
from indian_markets import amfi, nse, bse

# AMFI — latest NAV for every Indian MF scheme
for row in amfi.fetch_navall_rows():
    print(row.scheme_code, row.scheme_name, row.nav, row.nav_date)

# AMFI — historical NAV in 7-day chunks
for row in amfi.fetch_navhistory_rows("01-Jan-2024", "07-Jan-2024"):
    ...

# AMFI — list AMCs + TER for one AMC × one month
amcs = amfi.fetch_amc_list()
ter = amfi.fetch_ter(mf_id=9, month="05-2026")  # 9 = HDFC

# NSE — daily multi-index CSV
rows = nse.fetch_indices_csv(year=2024, month=5, day=22)

# NSE Indices — Total Return Index, inception-to-today, one POST
tri = nse.fetch_tri("NIFTY 50", "01-Jan-1999", "22-May-2026")

# BSE — quarterly filings index for a scrip; then download one iXBRL
index = bse.fetch_shareholding_index(scripcode=500325)  # Reliance
filing_bytes = bse.fetch_xbrl_filing(index[0]["XBRLAttachment"])
```

## Design notes

- **No DB integration.** Wrappers return iterators or lists of dicts/dataclasses. Plug into whatever store you want.
- **No retry framework.** AMFI's stub-body pattern is handled with one inline retry; everything else is plain `httpx`.
- **Defensive headers.** Every client sets a polite User-Agent and the load-bearing headers documented in `endpoints/`.
- **Header traps respected.** The BSE client deliberately does NOT set the `Origin` header (see `endpoints/lodr-shareholding.md`).

## Module map

| Module | Endpoints covered |
|---|---|
| `indian_markets.amfi` | NAVAll, NAV history, TER, monthly AAUM |
| `indian_markets.nse` | Daily indices CSV, niftyindices.com TRI |
| `indian_markets.bse` | LODR Reg 31 shareholding (filings index + iXBRL download) |

For wire-spec details and quirks, see [`../../endpoints/`](../../endpoints/).
