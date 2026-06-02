# AMFI Total Expense Ratio (TER) JSON API

Daily Total Expense Ratio for every Indian mutual-fund scheme, broken into 5 SEBI Regulation 52 sub-components × {Regular plan, Direct plan}. Historical depth: ~100 monthly snapshots (back to April 2018).

**Discovered**: 2026-05-21, via Playwright MCP on `https://www.amfiindia.com/ter-of-mf-schemes`. Owner: Association of Mutual Funds in India (AMFI).

## Wire spec

Two endpoints; call `populate-mf` once at start to get AMC IDs, then `populate-te-rdata-revised` per (AMC × month) pair.

### Endpoint 1 — list AMCs

```http
GET https://www.amfiindia.com/api/populate-mf
```

Returns:
```json
[
  {"tableId": 1, "order": 1, "mfId": "9", "mfName": "HDFC Mutual Fund"},
  ...
]
```

55 AMCs as of 2026-05-21. `mfId` (string of int) feeds `MF_ID` in endpoint 2.

### Endpoint 2 — TER rows for one AMC × one month

```http
GET https://www.amfiindia.com/api/populate-te-rdata-revised
   ?MF_ID=9
   &Month=05-2026
   &strCat=-1
   &strType=1
   &page=1
   &pageSize=10000
```

| Param | Required | Example | Notes |
|---|---|---|---|
| `MF_ID` | yes | `9` | From endpoint 1 |
| `Month` | yes | `05-2026` | `MM-YYYY` |
| `strCat` | yes | `-1` | `-1` = all categories |
| `strType` | yes | `1` | `1` = open-ended (only useful value for our purpose) |
| `page` | yes | `1` | 1-indexed |
| `pageSize` | yes | `10000` | Sized to one-shot all schemes for any AMC; the largest AMC has ~1,400 rows |

Returns:
```json
{
  "data": [ /* TerRow[] */ ],
  "meta": {"page": 1, "pageSize": 10000, "total": 312, "pageCount": 1}
}
```

### TerRow shape

```json
{
  "NSDLSchemeCode": "HDFC/O/E/FCF/94/12/0002",
  "Scheme_Name": "HDFC Flexi Cap Fund",
  "SchemeType_Desc": "Open Ended",
  "SchemeCat_Desc": "Equity Scheme - Flexi Cap Fund",
  "TER_Year": "2026-2027",
  "TER_Date": "2026-05-20T00:00:00.000Z",
  "R_BER": "1.0900",
  "R_BrokerageCost": "0.0200",
  "R_TransactionCost": "0.0000",
  "R_StatutoryLevies": "0.1800",
  "R_TER": "1.3500",
  "D_BER": "0.5300",
  "D_BrokerageCost": "0.0200",
  "D_TransactionCost": "0.0000",
  "D_StatutoryLevies": "0.2100",
  "D_TER": "0.7600",
  "MF_ID": 9,
  "Month": "05-2026"
}
```

| Field | Notes |
|---|---|
| `NSDLSchemeCode` | NSDL/SEBI registration code (slash-delimited). **Not** our AMFI scheme_code |
| `Scheme_Name` | Fund-family name (no plan suffix); the match anchor for joining to `schemes.scheme_name` |
| `TER_Date` | ISO timestamp with time/zone components — slice `[:10]` before `date.fromisoformat()` |
| `R_*` / `D_*` | Regular / Direct plan values. One AMFI row → multiple `schemes.scheme_code` rows after plan-suffix split |
| `R_BER`, `D_BER` | Base Expense Ratio (manager fee, marketing, ops) |
| `R_StatutoryLevies`, `D_StatutoryLevies` | GST (currently 18% of BER for equity, 5% for debt) |
| `R_BrokerageCost`, `D_BrokerageCost` | Trading commissions — fluctuates daily |
| `R_TransactionCost`, `D_TransactionCost` | STT / stamp duty / exchange charges |
| `R_TER`, `D_TER` | Sum of the 4 components — the "full" TER |

### Sub-component reconciliation

Per SEBI Regulation 52 (rebuilt from AMC-published xls files): `R_TER = R_BER + R_BrokerageCost + R_TransactionCost + R_StatutoryLevies`. Verified to 1 bp on PPFAS daily TER xls for May 2026.

## Worked example

```bash
# 1. Get AMC list
curl -sL "https://www.amfiindia.com/api/populate-mf" | jq '.[0:3]'

# 2. Get TER rows for HDFC (mfId=9), May 2026
curl -sL "https://www.amfiindia.com/api/populate-te-rdata-revised?MF_ID=9&Month=05-2026&strCat=-1&strType=1&page=1&pageSize=10000" | jq '.data | length, .data[0]'
```


## Required headers

| Header | Required? |
|---|---|
| Any | **No** |
| Polite UA | Recommended (use any browser-like UA) |

No auth, no cookies, no referrer, no `X-Requested-With`. The API is fully cold-callable.

## Rate limit & throttle

AMFI rate-limits **aggressively** — far more than NSE Indices. Characterised across multiple test bursts:

| Burst pattern | Failure mode |
|---|---|
| 55 sequential calls in <30 s | ~35% rate-limit-as-bad-JSON failures (returns HTTP 200 with truncated/error body) |
| 1 call per second | Stable for >1,000 calls |
| Exponential backoff (base 2 s, max 6 retries) | Clears any failure within ~3 attempts |

**Production recommendation**: 1 s sleep + exponential backoff. Full all-AMCs × 1-month census = ~10–15 min wall.

The rate-limit's "bad JSON instead of HTTP 429" pattern means **you cannot rely on `response.status_code`** — you must `try: json.loads(body)` and treat parse failure as a rate-limit signal. This is documented in `scripts/fetch_amfi_ter.py`.

## Name-match strategy (joining to a scheme dimension table you maintain locally)

The `Scheme_Name` AMFI returns ("HDFC Flexi Cap Fund") matches multiple of our scheme_codes:
- `118955` "HDFC Flexi Cap Fund - Growth Option - Direct Plan"
- `101762` "HDFC Flexi Cap Fund - Growth Plan"
- `118954` "HDFC Flexi Cap Fund - IDCW Option - Direct Plan"
- ... etc.

