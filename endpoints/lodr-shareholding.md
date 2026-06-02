# BSE LODR Reg 31 shareholding-pattern API

Quarterly shareholding-pattern filings for every BSE-listed company, accessed via BSE's `api.bseindia.com` JSON endpoint, then per-quarter iXBRL filings downloaded from `www.bseindia.com/XBRLFILES/`. Each iXBRL filing contains structured mutual-fund holder rows (fund name, shares held, % of equity).

**Discovered**: 2026-06-01, by mining the BSE Angular SPA bundle. The key finding: BSE's API gate is **header-shape-sensitive**. A request with `Origin` set returns a 1814-byte "page moved" error shell at HTTP 200. The *same* request with `Referer` only (no `Origin`) returns clean JSON. This is why the legacy `CorpShareHoldingData` endpoint appeared dead to direct curl probes; the endpoint also moved to `_ng`-suffixed paths.

The handshake is fully characterised; ingest implementation is documented separately.

## Wire spec

Two endpoints; call the index endpoint once per scrip to get the quarter list + iXBRL URLs, then download each iXBRL.

### Endpoint 1: quarterly filing index

```http
GET https://api.bseindia.com/BseIndiaAPI/api/Corp_Shareholding_ng/w
    ?scripcode={SCRIP}
    &flag={FLAG}
    &indtype=
```

| Param | Required | Example | Notes |
|---|---|---|---|
| `scripcode` | yes | `500325` | BSE 6-digit scrip code (lowercase param name, `Scripcode` returns the error shell) |
| `flag` | yes | `0` | `0` = full historical listing (only useful value). `1`, `2`, `Latest`, `C` all return empty. |
| `indtype` | yes (may be empty) | `` (empty) | Industry filter; empty means "all". Omitting the param entirely returns the error shell. |

Returns:
```json
{
  "Table": [
    {
      "FLD_ScripCode": 500325,
      "Company_NAme": "Reliance Industries Ltd",
      "industry_name": "Refineries & Marketing",
      "sQtrName": "March 2026",
      "nqtrid": "129.00&Flag=New",
      "broadcastTime": "Apr 21 2026  1:17PM",
      "D": "2026-04-21T13:17:00",
      "EndDate": "2026-03-31T00:00:00",
      "IsXBRL": 1,
      "XBRLAttachment": "/XBRLFILES/SHPXBRLDataXML/500325_2142026131656_SP.html",
      "DisplayDT": "2026-03-31T00:00:00"
    }
  ]
}
```

Observed: 105 rows for scripcode=500325 (Reliance) spanning ~26 years of quarterly filings. Companies listed later will have fewer rows accordingly. `IsXBRL=1` rows have a usable `XBRLAttachment` path; older PDF-only filings may have `IsXBRL=0` and a different attachment shape (not yet verified, to characterise).

### Endpoint 2: iXBRL filing download

```http
GET https://www.bseindia.com/{XBRLAttachment}
```

Where `{XBRLAttachment}` is the path from Endpoint 1 (e.g. `/XBRLFILES/SHPXBRLDataXML/500325_2142026131656_SP.html`).

Returns iXBRL (inline XBRL) wrapped in HTML, ~1.2-1.4 MB per file. Confirmed for Reliance Mar-2026 filing:
- Root namespace `xmlns:in-bse-shp='http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp'`
- Schema reference: `https://listing.bseindia.com/xbrl//Taxonomy/Taxonomy/in-bse-shp-2025-10-31.xsd`
- Contains tagged `MutualFund` holder lines under the `MutualFundsOrUTIDomain` context
- Structured fields per holder include name, PAN, share count, % of total equity (per SEBI's standard SHP iXBRL taxonomy)

### Worked example (end-to-end)

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

# 1. Get the quarterly filing index for Reliance
curl -sL -A "$UA" -H "Referer: https://www.bseindia.com/" \
  "https://api.bseindia.com/BseIndiaAPI/api/Corp_Shareholding_ng/w?scripcode=500325&flag=0&indtype=" \
  | jq '.Table[0]'

# 2. Pick the latest quarter, download the iXBRL
curl -sL -A "$UA" -H "Referer: https://www.bseindia.com/" \
  "https://www.bseindia.com/XBRLFILES/SHPXBRLDataXML/500325_2142026131656_SP.html" \
  -o reliance_shp_mar2026.html
```

## Required headers (load-bearing)

| Header | Required? | Notes |
|---|---|---|
| `User-Agent` (browser-like) | **Yes** | A non-browser UA returns the Angular SPA shell at the API URL (12565 b text/html). |
| `Referer: https://www.bseindia.com/` | **Yes** | Without Referer, the API serves the SPA shell. |
| `Origin: https://www.bseindia.com` | **NO, must NOT be set** | Sending `Origin` triggers a 1814 b "page moved" error response. Counter-intuitive; this is the trap that made the legacy endpoint look dead. |
| `Accept: application/json, text/plain, */*` | Optional | Returned `Content-Type` is `application/json; charset=utf-8` regardless. |
| Cookies | No | No session, no CSRF token. Stateless. |

No auth, no `x-api-key`, no `Authorization` header, no Cloudflare/Akamai challenge. The gate is purely a header shape check.

## Rate limit & throttle

Not yet characterised in detail; one-off calls succeed with no delay. should probe this with a burst test before designing the backfill loop. Starting position: 1 req/sec like AMFI TER. If `Table` returns `[]` unexpectedly or `Content-Type` flips to `text/html`, treat as a rate-limit signal (similar to AMFI's "200 OK with bad body" pattern).

For the universe sketch: ~2000 BSE-listed companies × 40 quarters of history available × (1 index call + N filing downloads) ≈ tens of thousands of requests. At 1 req/sec the index pull is ~35 min; full XBRL download for one quarter is also ~35 min if every scrip filed; full 10-year backfill (40 quarters × ~2000 scrips × ~1.3 MB = ~100 GB total) is bandwidth-bound more than rate-limit-bound and should run unattended overnight.

## XBRL parsing notes

The filings are **iXBRL** (inline XBRL: XBRL facts embedded in HTML via `<ix:nonFraction>` / `<ix:nonNumeric>` tags), not plain XBRL. Standard XBRL Python libraries:

- `arelle`, full XBRL processor, handles iXBRL. Heavyweight but authoritative.
- `python-xbrl`, simpler; iXBRL support varies.
- Hand-rolled: parse the HTML with `lxml`, extract `ix:*` tags via namespace-aware XPath. Tractable for SHP-only because the SHP taxonomy is small (~30 concepts).

For the MF-holder rows specifically: the relevant taxonomy concept is `in-bse-shp:NameOfTheShareHolders` under category `MutualFundsOrUTIDomain`, with sibling tags `NumberOfShares`, `ShareholdingPercentage`, `PAN`, etc. should write a thin extractor that walks the inline-XBRL tree and yields one record per holder, not regex over raw HTML.

## Caveats

- **`Origin`-header trap**: documented above. Anyone copy-pasting a "make request with all headers" recipe from common curl snippets will trip on this, most snippets include Origin by reflex.
- **Older PDF-only filings**: rows with `IsXBRL=0` exist for pre-2018(-ish) periods and have a different attachment shape. your coverage scope should decide whether to include them; recommended cutoff is "iXBRL only, post-2018", which still gives ~32 quarters of usable data.
- **Per-scrip filings only**: the API is per-scripcode. There is no consolidated "all scrips for quarter X" endpoint. The backfill must iterate over the BSE equity universe (scripcode list available via separate BSE search endpoint, not yet catalogued).
- **Fund name reconciliation needed downstream**: the iXBRL names funds as free-text strings, e.g. `"Hdfc Small Cap Fund"`, `"Nippon Life India Trustee Ltd-A/C Nippon India Small Cap Fund"`. Joining to our `schemes.scheme_code` is a fuzzy-match step, reuse the TER matcher's family-key normaliser per spec.
- **Header drift risk**: if BSE adds Origin-checking middleware later (the current "no Origin" rule is unusual and may be transient), the client breaks silently. Mitigate by treating a sudden flip from JSON to text/html at the catalogued endpoint as the canary; pin-test in CI.
- **iXBRL taxonomy version is dated**: the 2025-10-31 schema is the active one as of probe. Older filings reference older taxonomies (e.g. 2014-03-31). The extractor must dispatch on the namespace URI, not assume one schema version.

## Provenance

- Discovery session: 2026-06-01.
- Initial probe (morning, this same session) returned only the access-path surface comparison; the handshake was cracked on the second pass.
- Cracking method: download the BSE Angular bundle (`/assets/includenew/js/main-SCBSBM2B.js`, ~15 MB), grep for endpoint name constants (`{name}:"{path}"` pattern), find the actual param-shape from `BSE_Domain_APIUrl+A.url.Corp_Shareholding+"?scripcode=..."` concatenation patterns, then verify with curl + header-matrix.
- Verification: 1 scrip (Reliance, 500325), 1 quarter (Mar-2026 iXBRL fetched, MutualFund tags confirmed present). spec should run a 10-20 scrip × 4 quarter trust artifact before bulk ingest, cross-verified against screener.in.

## NSE: still gated

NSE shareholding endpoints remain Akamai-locked and require either a headless browser solving the JS challenge or a paid Bright Data Unlocker subscription. NSE is **out of scope here**; rely on BSE-only ingest. Most BSE-listed equities also list on NSE, so coverage is not materially reduced.

## SEBI / NSDL portal: not probed

SEBI's XBRL filings portal may host the same iXBRL files. Not investigated; BSE's direct path is sufficient and BSE is closer to the regulatory source-of-truth for the data we need.
