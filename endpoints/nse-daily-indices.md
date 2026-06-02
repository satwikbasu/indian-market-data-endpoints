# NSE daily multi-index CSV (price index)

Daily OHLC + P/E + P/B + dividend yield for every NSE-listed index (~140 indices in one file). This is the **price index**, does NOT include dividends; for total return, see [niftyindices-tri-api.md](niftyindices-tri-api.md).

**Source**: NSE India archive; static daily CSV.

## Wire spec

```http
GET https://archives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
```

URL is filled with the target date in `DDMMYYYY` format (no separators).

| Header | Required? | Notes |
|---|---|---|
| `User-Agent` | **Yes** (defensive) | Empty / curl UA sometimes 403; use any browser-like UA |
| Cookies | No | |

Returns:
- `200 OK` + CSV body on business days
- `404 Not Found` on weekends and exchange holidays (caller treats as "no trading day, skip")

## Body format

CSV with header:
```
Index Name,Index Date,Open,High,Low,Closing,Points Change,Change(%),Volume,Turnover,P/E,P/B,Div Yield
```

| Field | Type | Notes |
|---|---|---|
| `Index Name` | str | Display name with spaces: `Nifty 50`, `Nifty Bank`, `Nifty Midcap 150` |
| `Index Date` | str | `DD-MM-YYYY`, different from AMFI's `DD-MMM-YYYY` |
| `Open`, `High`, `Low`, `Closing` | str (decimal) | Price-index value, no thousands separators |
| `Points Change`, `Change(%)` | str (decimal) | Day-over-day deltas |
| `Volume`, `Turnover` | str (int) | Often 0 for index series (vs futures) |
| `P/E`, `P/B`, `Div Yield` | str (decimal) or `-` | Derivative indices (e.g., "Nifty 50 Futures Index") use `-` |

## Quirks

| Quirk | Detail |
|---|---|
| **Weekends / holidays = 404** | `fetch_indices_csv()` returns `None` and the caller skips. No silent "empty body" failure. |
| **Short-body anomaly** | Real files are 16–20 KB. Anything noticeably smaller (< 5 KB) is an NSE error page served as 200, defensive retry with 5 s / 15 s backoff. |
| **`Index Date` ≠ filename date** | The filename has the request date in `DDMMYYYY`; the in-CSV `Index Date` is the actual data date in `DD-MM-YYYY`. They always match in practice but the parser should trust the in-CSV value. |
| **Transport-level read timeouts** | NSE archive occasionally takes >30 s; we wrap `httpx.TimeoutException` / `httpx.NetworkError` in the same retry loop as 5xx. run #2 died here on a one-off NSE read timeout. |
| **Derivative indices with `-` values** | Filter them out at parse time, not at the SQL layer. |
| **No future-dated requests** | Requesting today's CSV before ~6 PM IST returns 404; NSE doesn't pre-publish. |

## Worked example

```bash
curl -sL -A "Mozilla/5.0" "https://archives.nseindia.com/content/indices/ind_close_all_22052026.csv" | head -3
```


## Rate limit & throttle

| Observation | Detail |
|---|---|
| Burst pattern | 200+ day-by-day calls back-to-back: stable as long as UA is set |
| 5xx rate | <1% under normal load |
| Production recommendation | No explicit sleep; the implicit ~200 ms per CSV is throttle enough |
| Full 5-year backfill | ~3 min wall time |

## Caveats

- **Filename date format is `DDMMYYYY`** (no separators). Easy to confuse with `YYYYMMDD` and `DD-MM-YYYY` used elsewhere.
- The archive only goes back to ~2018-09 for daily multi-index CSVs. Older history requires per-index CSV downloads from `niftyindices.com/reports/historical-data` (see TRI endpoint doc).
- The price index is **not** what most fund alpha analyses want, funds reinvest dividends, so benchmarking against the price index understates the benchmark and overstates fund alpha. **Use the TRI** (via [niftyindices-tri-api](niftyindices-tri-api.md)) for any return-comparison work.
- Index names in this CSV (`Nifty 50`, spaced, title case) differ from niftyindices.com's canonical (`NIFTY 50`, all caps). Normalise both to a common form when joining.

## Provenance

- In production use as the index OHLC backfill.
- Verified 106 K-row backfill across ~140 indices × ~750 business days.
