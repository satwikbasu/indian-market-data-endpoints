# AMFI Monthly / Quarterly Categorywise AAUM disclosure files

Monthly and quarterly Average Assets Under Management published by AMFI as static XLS / PDF downloads on the legacy `portal.amfiindia.com` subdomain. Data is **industry-aggregate, broken down by SEBI scheme category**, NOT per-AMC and NOT per-scheme.

**Discovered**: 2026-06-01, while researching whether AMFI categorywise AAUM could substitute for per-fund AUM in a capacity-strain signal. The new `www.amfiindia.com` Next.js site embeds these URLs in the SSR'd payload of `/research-information/amfi-data`.

## Wire spec

Two file families, both on the legacy `portal.amfiindia.com/spages/` static host.

### Monthly categorywise AAUM

```
GET https://portal.amfiindia.com/spages/am{mmm}{yyyy}repo.xls
GET https://portal.amfiindia.com/spages/am{mmm}{yyyy}repo.pdf
```

| Param | Format | Example |
|---|---|---|
| `mmm` | lowercase 3-letter English month | `apr`, `jul`, `dec` |
| `yyyy` | 4-digit year | `2026` |

Working example: `https://portal.amfiindia.com/spages/amapr2026repo.xls`

Coverage observed (probe 2026-06-01):
- **PDF**: Jan 2009 → Apr 2026 continuous (latest available; May 2026 not yet posted)
- **XLS**: from ~mid-2018 → Apr 2026 continuous
- Some revised re-uploads with `repo` → `reporevised` suffix (e.g. `amdec2021reporevised.xls`, `amjan2022reporevised.xls`), both URL variants are live; the `revised` is the corrected one if both exist
- Publishing cadence: ~10–15 days after month-end (Apr 2026 was live by 2026-06-01)

### Quarterly categorywise AAUM

```
GET https://portal.amfiindia.com/spages/aqu-vol{N}-issue{R}.xls
GET https://portal.amfiindia.com/spages/aqu-vol{N}-issue{R}.pdf
```

| Param | Format | Notes |
|---|---|---|
| `N` | volume number, 1..25 (2026) | Volume 1 starts FY 2001-02 |
| `R` | Roman numeral I/II/III/IV | Quarter within FY |

Working example: `https://portal.amfiindia.com/spages/aqu-vol25-issueIV.xls` (Q4 FY 2025-26 = Jan-Mar 2026)

Coverage:
- PDF: vol1 onwards (2001-02 FY) → vol25 (current)
- XLS: vol19 onwards (~2019-20 FY) → vol25

### Sub-classification of "Other Scheme" (related, narrower)

Listed on `/research-information/sub-classification-of-other-scheme`:

```
GET https://portal.amfiindia.com/spages/Sub-classification-{MMM}{YY}.{xls,pdf}
```

Example: `https://portal.amfiindia.com/spages/Sub-classification-Apr23.xls` (case-sensitive month abbreviation: `Apr`, `Aug`, `Dec` etc.)

Quirk: the latest 2026 sub-classification URLs listed on the page (e.g. `Sub-classification-Apr26.xls`) currently 404. The 2023–2025 issues are live. This file breaks "Other Schemes" (ETFs, FoFs, index funds, gold ETFs) into finer categories, **not relevant to a per-fund capacity signal**.

## Worked example (the load-bearing one for this catalogue entry)

```bash
curl -sL -A "Mozilla/5.0 (your-tool-name)" \
  -o /tmp/amfi_apr2026.xls \
  "https://portal.amfiindia.com/spages/amapr2026repo.xls"

# Parses as legacy XLS (BIFF8 / Composite Document File V2)
python -c "
import xlrd
wb = xlrd.open_workbook('/tmp/amfi_apr2026.xls')
print(wb.sheet_names())  # ['MCR_Report', 'New Scheme Report']
s = wb.sheet_by_name('MCR_Report')
print(s.nrows, s.ncols)  # 92 11
"
```

Sheet `MCR_Report` row schema (header on row 2, data from row 5):

| Col | Header | Example value (row 5: Overnight Fund) |
|---|---|---|
| 0 | Sr (Roman numeral or letter) | `i` |
| 1 | Scheme Name (= SEBI category label) | `Overnight Fund` |
| 2 | No. of Schemes as on {month-end} | `37.0` |
| 3 | No. of Folios as on {month-end} | `764557.0` |
| 4 | Funds Mobilized for the month (Rs. crore) | `564711.92` |
| 5 | Repurchase/Redemption for the month | `533291.47` |
| 6 | Net Inflow(+)/Outflow(-) | `31420.45` |
| 7 | **Net Assets Under Management** as on {month-end} | `104919.86` |
| 8 | **Average Net Assets Under Management** for the month | `118330.62` |
| 9 | No. of segregated portfolios created | `0.0` |
| 10 | Net AUM in segregated portfolios | `0.0` |

92 rows total, structured as a SEBI category tree:
- `A` Open ended Schemes
  - `I` Income/Debt Oriented Schemes (i–xvi: Overnight, Liquid, Ultra Short, … Floater)
  - `II` Growth/Equity Oriented Schemes (i–xi: Multi-cap, Large-cap, Mid-cap, Small-cap, …)
  - `III` Hybrid Schemes
  - `IV` Solution Oriented
  - `V` Other Schemes (ETF, Index, FoF, …)
- `B` Close ended Schemes
- `C` Interval Schemes
- Totals row at bottom

The second sheet `New Scheme Report` lists NFOs launched during the month (~20 rows, 4 cols).

## Required headers

| Header | Required? |
|---|---|
| Any | **No** |
| Polite UA | Recommended; use any browser-like UA |
| `Referer` | No |

Static-asset CDN. No auth, no cookies, no JS-handshake. Identical access discipline to the AMFI NAVAll.txt host.

## Rate limit & throttle

Not characterised, these are CDN-cached static files, expected to be effectively unlimited within polite ranges. For a one-shot historical pull of ~17 years of monthly XLS (~200 files at 100–150 KB each = ~25 MB), 1 file/sec with a 0.5 s sleep margin is conservative.

## Coverage decision

**This endpoint is NOT a substitute for per-fund AUM in a per-fund capacity signal.** A per-fund capacity-strain signal needs `AUM(scheme_code, month)`, per-fund granularity, because the diagnostic fires when *a single fund* is being forced up the market-cap curve by its own size.

What this endpoint provides:
- AUM(SEBI category, month), e.g. all Small-cap Funds aggregated to a single row
- No per-AMC, no per-scheme breakdown
- No per-fund holdings information

Use cases this DOES support (none of which are blocking the current build plan):
- Industry-wide flow analysis (net inflows by category, useful for context only)
- Sanity-check / cross-source verification of category totals derivable from per-fund data once lands
- Discussion / dashboard "industry overview" widgets

## What is still missing

Per-fund AUM time series remains gated on either:
1. **LODR Reg 31 ingest** (quarterly, ~2000 listed companies, XBRL parsing). The original plan; not shortened by this discovery.
2. **Per-AMC monthly factsheet scraping** (~45 AMCs × heterogeneous PDF/XLSX formats × monthly). Substantially harder, because each AMC publishes in its own house format with no industry-wide standard.
3. **A paid aggregator** (Morningstar India, Value Research Pro, Bloomberg). Outside the ₹2K/mo budget unless reframed.

## Caveats

- These are **legacy static-asset URLs** on a subdomain (`portal.amfiindia.com`) that does not host the new Next.js site. If AMFI ever sunsets this subdomain, this catalogue entry breaks. Track via periodic HEAD requests.
- `am{mmm}{yyyy}repo.xls` filenames are lowercase month, no separator. Some quarters use `reporevised` instead of `repo`, handle by trying both URLs and preferring the revised file when it exists.
- The XLS files are BIFF8 (`Composite Document File V2`), use `xlrd 2.x` to parse; `openpyxl` will reject as "old xls" because it only handles xlsx.
- "Average Net AUM" (col 8) is the per-month average and is the metric distributors use for commission slabs; "Net AUM as on month-end" (col 7) is the point-in-time snapshot. For a per-fund capacity signal use cases (if we ever do industry-context work) prefer col 8 to align with how the industry quotes AUM.
- Values are in **Rs. crore** (= 10 million Rs).
- Row order is stable: SEBI category labels in col 1 have not changed since at least 2018. New categories (e.g. `Banking and PSU Fund`, `Floater Fund`) inserted via reordering, not renumbering, so name-match by `Scheme Name` not sr index.
- The file occasionally posts a few days late (~12-15th of the following month). The May-2026 file was not yet live at 2026-06-01.

## Provenance

- Discovery: 2026-06-01, embedded as href targets in the SSR'd Strapi payload of `https://www.amfiindia.com/research-information/amfi-data`. Extracted via `curl | grep -oE 'https?://[^"\\ ]{4,200}\.(xls|xlsx|pdf)'`.
- Verification: parsed Apr-2026 XLS with xlrd, confirmed `MCR_Report` structure end-to-end.
