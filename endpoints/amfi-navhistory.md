# AMFI NAV history archive: date-range backfill

Historical NAV for every mutual-fund scheme over an arbitrary date range. Used to backfill `daily_nav` years deep without scraping individual scheme pages.

**Source**: AMFI portal; ASP.NET WebForms backend.

## Wire spec

```http
GET https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=01-Jan-2024&todt=07-Jan-2024
```

| Param | Required | Example | Notes |
|---|---|---|---|
| `frmdt` | yes | `01-Jan-2024` | `DD-MMM-YYYY`, yes, different from NAVAll.txt (which is also `DD-MMM-YYYY`) but different from NSE archive (which is `DDMMYYYY`) |
| `todt` | yes | `07-Jan-2024` | `DD-MMM-YYYY` |

Returns `text/plain` (~1–5 MB for a 7-day window across all schemes).

| Header | Required? |
|---|---|
| Any | **No** |

## Body format

Different from NAVAll.txt, **8** semicolon-separated fields per data row instead of 6:

```
Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date
```

Column order moves `Scheme Name` to position 2 (vs position 4 in NAVAll.txt). Missing ISINs are **empty** (`;;`), not `-`.

Section headers also differ:
- NAVAll.txt: `Open Ended Schemes(Equity Scheme - Large Cap Fund)` (no inner space)
- This endpoint: `Open Ended Schemes ( Equity Scheme - Large Cap Fund )` (extra spaces inside parens)

Each scheme appears once per available business date in the requested range.

## Quirks

| Quirk | Detail |
|---|---|
| **Stub-body response** | AMFI intermittently returns a ~13,694-byte "no-data" stub with HTTP 200 instead of the real CSV. Real chunks are 1–5 MB. Our scraper uses `STUB_BODY_BYTES_MAX = 50_000` as a defensive threshold and retries up to 3 times with 5 s / 15 s backoff. |
| **Long date ranges fail** | Empirically, ranges longer than ~14 days return stubs or timeouts. We chunk in 7-day windows (`CHUNK_DAYS = 7`), verified to return cleanly ~4 MB / ~36k rows each. |
| **Different field order** | Caller cannot reuse the NAVAll.txt parser directly; we share the section-header + AMC-line classifier (`_classify_section_line`) but not the row parser. |
| **Repurchase / Sale Price columns** | Two extra columns that we ignore. Most funds report these as identical to NAV; some debt/closed-ended funds use them. |

## Worked example

```bash
curl -sL "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=01-Jan-2024&todt=07-Jan-2024" | head -3
```


## Rate limit & throttle

| Observation | Detail |
|---|---|
| Tested burst | 50 weekly chunks back-to-back, no 4xx/5xx, but stub-body rate climbs to ~5% on bursts |
| Production recommendation | 7-day chunks, no explicit sleep between (server is slow enough on its own, each chunk takes 30–60 s) |
| Full 5-year backfill wall time | ~30 min for our universe |

## Caveats

- The endpoint is **slow**: a 7-day chunk routinely takes 30–60 s end-to-end. This dominates backfill time, not network.
- **Stub-body rate is non-zero even under perfect throttle.** Build in retry-with-backoff or accept ~1% data loss.
- The 7-day-chunk limit appears to be an internal AMFI memory limit, not documented anywhere; smaller chunks always work, larger chunks often fail.
- Date format: `DD-MMM-YYYY` with the month as a 3-letter English abbreviation. Locale matters, `01-Jan-2024` not `01-jan-2024` or `01-JAN-2024`.

## Provenance

- In production use for historical NAV backfill.
- Verified 9.58 M-row backfill from Feb 2017 to current.
