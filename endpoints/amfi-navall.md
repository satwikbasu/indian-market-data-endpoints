# AMFI NAVAll.txt — daily NAV snapshot

A single semicolon-delimited text file containing the latest Net Asset Value of every mutual-fund scheme in India (~16,000 schemes, ~3 MB). Published by AMFI on every business day after the SEBI 9 PM cutoff.

**Source**: well-known public-ish file; documented loosely in AMFI's "for developers" footnote but with no schema spec.

## Wire spec

```http
GET https://portal.amfiindia.com/spages/NAVAll.txt
```

| Header | Required? |
|---|---|
| Any | **No** |
| Polite UA | Recommended |

Returns `text/plain` (~3 MB, UTF-8). The file is overwritten in-place each business day around 9–10 PM IST.

## Body format

Each non-blank line is one of three things:

1. **Column header** (first line): `Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date`
2. **AMC header** (no semicolons, fund-house name): `Axis Mutual Fund`
3. **Section header** (no semicolons, parens): `Open Ended Schemes(Equity Scheme - Large Cap Fund)`
4. **Data row** (6 semicolon-separated fields): `120586;INF109K01480;-;ICICI Prudential Large Cap Fund - Direct Plan - Growth;1234.5678;21-May-2026`

Missing ISIN columns appear as a literal `-`. Date is `DD-MMM-YYYY`.

State is **rolling**: a parser must carry the current AMC + scheme_type + scheme_category as it walks the file, applying them to every subsequent data row.

## Quirks

| Quirk | Detail |
|---|---|
| **Stale NAVs survive in the file** | Defunct schemes keep their original final NAV date (e.g. `14-Jun-2017`). Trust the row's date, not "today". |
| **Zero NAVs** | A small fraction (~0.1%) of data rows have `0.0000` as NAV — typically funds in the process of liquidation. Skip these rows (clients typically use `Decimal(nav) > 0`). |
| **Empty trailing fields** | Some rows have a trailing `;` (missing date). Skip. |
| **No deletions** | Even merged/wound-up schemes remain in the file forever with their last NAV. The `schemes` table needs SCD-2 logic to mark them `is_current=false`. |

## Worked example

```bash
curl -sL "https://portal.amfiindia.com/spages/NAVAll.txt" | head -5
```


## Rate limit & throttle

| Observation | Detail |
|---|---|
| File is static for the day | Fetch at most once per business day |
| Practical limit | None observed; ~3 MB single GET |
| Production recommendation | One fetch per day at 9:30 PM IST after AMFI's publish window |

## Caveats

- The file is **not idempotent within a day** — AMFI sometimes republishes corrections an hour or two after the initial publish. Defensive scrapers either fetch in two passes (9:30 PM + 11:00 PM) or accept ~3 hr lag on first-touch.
- The `Scheme Code` column is AMFI's internal 5–6-digit integer (e.g. `120586`). This is the join key clients typically use throughout our database. It is **not** the NSDL/SEBI registration code that AMFI's TER endpoint returns.
- ISINs are present for ~95% of schemes; older schemes pre-ISIN and some debt funds use `-`.
- The "Net Asset Value" column is the **only** numeric column; it is a string-formatted decimal with no thousands separators.

## Comparison to alternatives

| Source | Coverage | Latency | Recommended? |
|---|---|---|---|
| `portal.amfiindia.com/spages/NAVAll.txt` (this) | All schemes, daily | T+0 (same day after 9 PM IST) | **Yes — primary** |
| `portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx` | Date-range historical | Up to T+0 | Backfill (see [amfi-navhistory](amfi-navhistory.md)) |
| `mfapi.in` community wrapper | Per-scheme daily, JSON | T+1 (mirrors AMFI daily) | Convenient for ad-hoc lookups but adds a dependency |
| AMFI XML feed | Per-AMC, more verbose | T+0 | Equivalent data with more structure but ~6× larger |

## Provenance

- In production use as a daily NAV ingest.
- Verified at 9.58 M rows backfilled from 2012-02-17 through current.
