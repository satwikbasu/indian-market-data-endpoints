# niftyindices.com, Total Return Index API

Daily TRI (Total Return Index, price + reinvested dividends) and NTR (Net Total Return, TRI after dividend withholding tax) for every Nifty index, from inception to today, in a single call.

**Discovered**: 2026-05-22, via Playwright MCP on `https://www.niftyindices.com/reports/historical-data`. Owner: NSE Indices Ltd.

## Wire spec

```http
POST /Backpage.aspx/getTotalReturnIndexString HTTP/1.1
Host: www.niftyindices.com
Content-Type: application/json; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: https://www.niftyindices.com/reports/historical-data
User-Agent: <any normal browser UA>

{"cinfo":"{'name':'NIFTY 50','startDate':'01-Jan-1999','endDate':'22-May-2026','indexName':'NIFTY 50'}"}
```

### Body shape

`cinfo` is a **string** whose content is a JSON-like object with **single quotes** (ASP.NET ScriptService convention, not standard JSON). Fields:

| Field | Type | Example | Notes |
|---|---|---|---|
| `name` | str | `NIFTY 50` | The canonical Nifty index name |
| `startDate` | str | `01-Jan-1999` | `DD-MMM-YYYY` |
| `endDate` | str | `22-May-2026` | `DD-MMM-YYYY` |
| `indexName` | str | `NIFTY 50` | Duplicate of `name`; both required |

### Required headers

| Header | Required? | Notes |
|---|---|---|
| `Content-Type: application/json; charset=UTF-8` | yes | Server rejects other content types |
| `X-Requested-With: XMLHttpRequest` | yes | ASP.NET ScriptService gate |
| `Referer` | yes (defensive) | Akamai bot detection samples on Referer; mismatch = 403 in some cases |
| `User-Agent` | **yes** | Must be browser-like (e.g. `Mozilla/5.0 ...`). See the UA trap below — non-browser UAs do NOT 403, they **silently stall** indefinitely. |
| Cookies | **no** | Tested cold-curl with no prior GET, works |

### User-Agent trap (load-bearing, observed 2026-06-02)

A non-browser UA (e.g. `mytool/0.1`, `python-httpx/0.27`, `curl/8.x`) does **not** return 403. The server accepts the POST and then never sends a response body. The client's read-timeout fires eventually (often 60-120 s); retries hit the same stall. Diagnosis is easy if you compare against `curl -H 'User-Agent: Mozilla/5.0 ...'`, which returns in <1 s.

Use a UA that starts with `Mozilla/5.0`. A suffix identifying your client is fine: `Mozilla/5.0 (X11; Linux x86_64) ... your-tool/0.1` works.

### Response shape

```json
{"d": "[{\"RequestNumber\":\"TRI...\",\"Index Name\":\"Nifty 50\",\"Date\":\"22 May 2026\",\"TotalReturnsIndex\":\"35793.78\",\"NTR_Value\":\"31169.3\"}, ...]"}
```

`d` is a **JSON-encoded string**, parse twice: `json.loads(resp.json()['d'])`. Rows are sorted **most-recent first**. Per-row fields:

| Field | Type | Example | Notes |
|---|---|---|---|
| `RequestNumber` | str | `TRI63915064004640291500` | Opaque server tracking ID; ignore |
| `Index Name` | str | `Nifty 50` | Note: response has spaces and mixed case, **request requires uppercase** `NIFTY 50` |
| `Date` | str | `22 May 2026` | `DD MMM YYYY` with spaces, **NOT** the `DD-MMM-YYYY` of the request |
| `TotalReturnsIndex` | str | `35793.78` | TRI value (parse to float) |
| `NTR_Value` | str | `31169.3` | Net Total Return (after div withholding tax, relevant for FII benchmarks) |

## Worked example

```bash
curl -sL "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString" \
  -H "Content-Type: application/json; charset=UTF-8" \
  -H "X-Requested-With: XMLHttpRequest" \
  -H "Referer: https://www.niftyindices.com/reports/historical-data" \
  -H "User-Agent: Mozilla/5.0 Chrome/149.0.0.0" \
  --data-raw '{"cinfo":"{'\''name'\'':'\''NIFTY 50'\'','\''startDate'\'':'\''01-Jan-1999'\'','\''endDate'\'':'\''22-May-2026'\'','\''indexName'\'':'\''NIFTY 50'\''}"}'
```

Python (recommended):

```python
import json, httpx

def fetch_tri(name: str, start: str, end: str) -> list[dict]:
    payload = {"cinfo": f"{{'name':'{name}','startDate':'{start}','endDate':'{end}','indexName':'{name}'}}"}
    resp = httpx.post(
        "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString",
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.niftyindices.com/reports/historical-data",
            "User-Agent": "Mozilla/5.0 (your-tool-name)",
        },
        content=json.dumps(payload),
        timeout=60.0,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["d"])

rows = fetch_tri("NIFTY 50", "01-Jan-1999", "22-May-2026")
# rows[0] is latest, rows[-1] is earliest
```

## Verified inventory

Single call, full inception-to-today range:

| Index | Sub-category | Rows | Inception | Verified date |
|---|---|---|---|---|
| `NIFTY 50` | Broad Market | 6,690 | 30 Jun 1999 | 2026-05-22 |
| `NIFTY 500` | Broad Market | 6,815 | 01 Jan 1999 | 2026-05-22 |
| `NIFTY NEXT 50` | Broad Market | 5,848 | 08 Nov 2002 | 2026-05-22 |
| `NIFTY MIDCAP 150` | Broad Market | 5,243 | 01 Apr 2005 | 2026-05-22 |
| `NIFTY SMALLCAP 250` | Broad Market | 5,243 | 01 Apr 2005 | 2026-05-22 |
| `NIFTY100 LOW VOLATILITY 30` | Strategy | 5,243 | 01 Apr 2005 | 2026-05-22 |

## Canonical name discovery

The `name` field must match an internal canonical spelling exactly, mismatches return `d: "[]"` (empty array, **no error**). Use these sibling endpoints to enumerate valid names:

```http
POST /Backpage.aspx/gethistoricaltypeSubindexdata
Body: {"cinfo": {"indextype": "Equity", "indexgroup": ""}}
→ list of {indextype: "Broad Market Indices" | "Sectoral Indices" | "Strategy Indices" | "Thematic Indices", ...}

POST /Backpage.aspx/gethistoricaltypeindexdata
Body: {"cinfo": {"indextype": "Strategy Indices", "indexgroup": "Equity"}}
→ list of {indextype: "NIFTY100 LOW VOLATILITY 30", ...}, {indextype: "NIFTY200 MOMENTUM 30", ...}, ...
```

**Body-field semantics for `gethistoricaltypeindexdata`** (verified 2026-05-23): `indextype` carries the SUB-CATEGORY name (e.g. `"Strategy Indices"`); `indexgroup` carries the PARENT (`"Equity"`). The naming is reversed from what you might expect, `indextype` and `indexgroup` were initially documented swapped here; corrected.

Note these two sibling endpoints use **proper JSON** for `cinfo` (nested object), unlike the TRI endpoint which uses a single-quoted string. ASP.NET is inconsistent on this. Also note the response payload `d` is a JSON list directly (NOT a doubly-encoded string like the TRI endpoint).

**Publication gap warning**. The enumeration endpoint lists every Nifty index the publisher manages, but **not all of those have queryable historical data via the TRI / price-index endpoints**. Concrete case (2026-05-23): `NIFTY100 QUALITY 30` is enumerated, but both `getTotalReturnIndexString` and `getHistoricaldatatabletoString` return `{"d":"[]"}` for it with HTTP 200 (the index exists, HDFC's Nifty100 Quality 30 ETF tracks the TRI, but the public historical-data endpoints do not surface it). Always probe with a real fetch before committing to an index name from enumeration.

Authoritative offline reference: <https://www.niftyindices.com/BenchmarkCodes/Nifty_Indices_Benchmark_Codes.pdf>, every NSE-published index with its canonical name.

## Spelling quirks observed

- Broad-market names: spaced uppercase, `NIFTY 50`, `NIFTY MIDCAP 150`.
- Strategy-index names: compact, `NIFTY100 LOW VOLATILITY 30` (no space between `NIFTY` and `100`), `Nifty200 Momentum 30` (mixed case).
- The dropdown UI shows the canonical spelling; the response capitalises differently. Always use the dropdown spelling when sending.

## Rate limit & throttle

| Observation | Detail |
|---|---|
| Tested burst | 6 sequential calls in <10 s, all 200 OK |
| Akamai front | Page is on Akamai; aggressive bursts may eventually 403 |
| No documented limit | NSE Indices does not publish a limit |
| Production recommendation | **1 s sleep between calls**, exponential backoff on 4xx/5xx (base 2 s, max 5 retries) |

For a 6-index factor basket, the full historical backfill at this throttle is ~10 s wall time. Compared to AMFI TER which needs ~10 min for one month of all-AMCs, this is essentially free.

## Sibling endpoints worth noting

Discovered in the same Playwright session:

| Endpoint | Purpose | Status |
|---|---|---|
| `Backpage.aspx/getHistoricaldatatabletoString` | **Price-index** daily OHLC (no dividends) | Older alternative to our NSE archive CSV; well-documented externally |
| `Backpage.aspx/getDailyDivYieldString` | Daily dividend yield + P/E + P/B for any Nifty index | Not yet captured but DOM hints at it; useful for a sector-flow signal |
| `Backpage.aspx/gethistoricaltypedata1` | Top-level index categories (Equity / Fixed Income / Multi Asset) | Used by the dropdown chain |

## Caveats

- **Cookies are not currently required, but Akamai's bot detection can change overnight.** Production scrapers should bootstrap a cookie jar by GETting `https://www.niftyindices.com/reports/historical-data` first as a defensive measure. Give that bootstrap GET a **short sub-timeout (5 s)** — when Akamai is hostile, the HTML page can hang while the API endpoint still answers. The Python wrapper does this.
- The `cinfo` string-with-single-quotes payload format is unusual. **Do not** swap to standard JSON nested object on this endpoint, the server's deserialiser expects a string, not an object. (Tested: `{"cinfo":{"name":"NIFTY 50",...}}` returns `{"d":"[]"}`.)
- Earlier web sources (StackOverflow circa 2020) claim a ~50-day-per-call chunking limit. **This is wrong as of 2026-05-22.** Verified single-call returns of 27-year ranges (~7K rows) succeed.
- The endpoint family includes legacy ASP.NET `.axd` URLs (`ScriptResource.axd`), these are not data endpoints; don't try to call them.

## Provenance

- Page driven: `https://www.niftyindices.com/reports/historical-data`
- Form section: third panel ("Historical Total Return Index Data"), hidden by default behind a toggle. Triggering its `submit_totalindexhistorical` button via jQuery `.trigger('click')` worked even with the panel hidden.
- JS source: handler is bound in inlined `<script>` blocks of the historical-data page, not in `historicalData.js` or `developer.js` (those handle UI only).
- Network capture: request #59 in the session of 2026-05-22T16:22Z.

## Comparison to other TRI sources

| Source | Coverage | Auth | Recommended? |
|---|---|---|---|
| niftyindices.com TRI (this endpoint) | All Nifty indices, since inception | None | **Yes, primary** |
| Investing.com `NIFTRI` symbol | NIFTY 50 only, from ~2009 | None | Fallback |
| Kaggle community datasets | NIFTY 50 only, stale by weeks | None | Quick-look only |
| Reverse-derived from low-TER index-fund NAV | All Nifty indices but with ~5-10 bp TER drag | None | Last resort |
| NSE EOD subscription | All NSE indices, official | Paid + login | Not used (cost) |
