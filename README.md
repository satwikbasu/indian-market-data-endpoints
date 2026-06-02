<div align="center">

# 🇮🇳 indian-market-data-endpoints

**A wire-spec'd catalogue of undocumented public HTTP endpoints for Indian capital-markets data.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Endpoints](https://img.shields.io/badge/endpoints-7-blueviolet?style=flat-square)](#-catalogue)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](wrappers/python)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)
[![Last Commit](https://img.shields.io/github/last-commit/satwikbasu/indian-market-data-endpoints?style=flat-square)](https://github.com/satwikbasu/indian-market-data-endpoints/commits/main)
[![GitHub Stars](https://img.shields.io/github/stars/satwikbasu/indian-market-data-endpoints?style=flat-square&logo=github)](https://github.com/satwikbasu/indian-market-data-endpoints/stargazers)
[![Issues](https://img.shields.io/github/issues/satwikbasu/indian-market-data-endpoints?style=flat-square)](https://github.com/satwikbasu/indian-market-data-endpoints/issues)

[**📋 Catalogue**](#-catalogue) • [**⚡ Quickstart**](#-quickstart) • [**🔎 Why this exists**](#-why-this-exists) • [**🛠 Methodology**](#-discovery-methodology) • [**🤝 Contributing**](CONTRIBUTING.md)

</div>

---

## 📋 Catalogue

> Each endpoint has its own doc with the wire spec, required headers, response shape, every quirk, and a copy-pasteable `curl` example.

| # | Endpoint | Source | What you get | Doc |
|---|---|---|---|---|
| 1 | **AMFI NAVAll.txt** | `portal.amfiindia.com` | Daily NAV for every Indian MF scheme — ~16k schemes in one ~3 MB file | [📄](endpoints/amfi-navall.md) |
| 2 | **AMFI NAV history** | `portal.amfiindia.com` | Date-range historical NAV via weekly chunks; 18+ years backfillable | [📄](endpoints/amfi-navhistory.md) |
| 3 | **AMFI TER JSON API** | `amfiindia.com/api` | Daily expense ratio per scheme — 5 SEBI Reg 52 sub-components × {Regular, Direct} | [📄](endpoints/amfi-ter-api.md) |
| 4 | **NSE daily indices CSV** | `archives.nseindia.com` | One CSV per business day with OHLC + P/E + P/B + div yield for ~140 NSE indices | [📄](endpoints/nse-daily-indices.md) |
| 5 | **niftyindices.com TRI** | `niftyindices.com/Backpage.aspx` | Total Return Index per Nifty index, inception-to-today in one POST | [📄](endpoints/niftyindices-tri-api.md) |
| 6 | **AMFI categorywise AAUM** | `portal.amfiindia.com/spages` | Monthly + quarterly industry-aggregate AUM by SEBI category (XLS/PDF) | [📄](endpoints/amfi-monthly-aaum.md) |
| 7 | **BSE LODR Reg 31 shareholding** | `api.bseindia.com` + `bseindia.com/XBRLFILES` | Quarterly per-company shareholding pattern via iXBRL; MF holders as structured rows | [📄](endpoints/lodr-shareholding.md) |

> 💡 The BSE LODR endpoint required a non-obvious `Origin`-header trick — every prior scraping attempt failed at this gate. See [the doc](endpoints/lodr-shareholding.md#required-headers-load-bearing) for the exact handshake.

---

## ⚡ Quickstart

### Python (minimal, `httpx` only)

```bash
pip install httpx
```

```python
# Latest NAV for every Indian MF scheme — one HTTP call, ~3 MB
import httpx
r = httpx.get("https://portal.amfiindia.com/spages/NAVAll.txt", timeout=30)
print(r.text.splitlines()[:5])
```

### Or use the bundled wrapper library

```bash
cd wrappers/python && pip install -e .
```

```python
from indian_markets import amfi, nse, bse

# Parse all schemes from AMFI's daily snapshot
for row in amfi.fetch_navall_rows():
    print(row.scheme_code, row.scheme_name, row.nav, row.nav_date)

# Total Return Index for Nifty 50, full inception-to-today
tri = nse.fetch_tri("NIFTY 50", "01-Jan-1999", "22-May-2026")

# Latest shareholding-pattern filing for a BSE scrip
filings = bse.fetch_shareholding_index(scripcode=500325)  # Reliance
```

Worked examples in [`examples/`](examples/):

```bash
python examples/fetch_all_navs.py
python examples/fetch_nifty_tri.py
python examples/fetch_lodr_filing.py 500325
```

---

## 🔎 Why this exists

Indian financial regulators (AMFI, NSE Indices Ltd., NSE, BSE, SEBI) host most of their public data behind **interactive web forms**. There is:

- ❌ No OpenAPI spec
- ❌ No developer portal
- ❌ No API key or auth flow
- ❌ No rate-limit documentation
- ❌ No published changelog

The data is genuinely public — regulatory disclosures, daily NAV publications, exchange archives — but the protocols are not documented anywhere. The standard developer experience is: open DevTools, fill the form, watch the network tab, copy as curl, replay until it works.

**This catalogue captures the wire specs once so that finding doesn't have to happen again.** Each doc has enough precision — exact URL, required headers, body shape, response shape, every gotcha — to write a client in any language without further investigation.

The endpoints are **stable for years**. Government and quasi-government IT in India favours backward compatibility over modernisation; the AMFI `NAVAll.txt` format has been unchanged since at least 2017, and the NSE archive URL template has been the same for nearly a decade.

---

## 🛠 Discovery methodology

For each endpoint we either:

<details>
<summary><b>1. Drove the page form via headless browser</b> — how AMFI TER and niftyindices.com TRI were found</summary>

`browser_navigate` → `browser_fill_form` → `browser_click` → `browser_network_requests` to capture the exact request/response. Works for ASP.NET WebForms and Angular SPAs alike.

</details>

<details>
<summary><b>2. Read the page's compiled JavaScript</b> — how the BSE LODR endpoint was cracked</summary>

Angular SPAs inline endpoint name constants and param-shape patterns in their bundles. Grep `{name}:"{path}"` in the minified bundle, find `BSE_Domain_APIUrl+A.url.Corp_Shareholding+"?scripcode=..."` concatenation patterns, verify with curl + header matrix.

</details>

<details>
<summary><b>3. Replayed the captured call via <code>curl</code></b></summary>

Strip cookies, JS state, and browser-only headers one at a time until the call still works. This establishes the **minimal auth surface** for a programmatic client — and reveals header traps where a header that's harmless in browser context breaks the call.

</details>

Each endpoint doc has a dedicated **Quirks** section documenting every gotcha hit. Read it before writing your client.

---

## 📐 Conventions in every endpoint doc

- **Wire spec first** — exact URL, method, headers, body shape, response shape. No prose preamble.
- **One worked example** — a `curl` you can paste verbatim.
- **Required headers table** — which headers are load-bearing and which are decorative. Especially: any **header trap** (a header that breaks the call when present).
- **Quirks** — every gotcha worth an hour.
- **Rate limit / throttle** — observed limits and the safety margin we apply.
- **Caveats** — edge cases, stub responses, ambiguous fields, version-drift risk.
- **Provenance** — when and how it was discovered.

---

## 🚫 What does NOT belong here

- Endpoints behind paywalls or subscriber logins (connect2nse, NSE EOD subscription, Value Research Pro).
- Third-party data aggregators (Investing.com, mfapi.in, mfdata.in) — useful but one step removed from primary sources.
- Endpoints needing captcha or interactive auth.
- Anything found by reverse-engineering a paid product's API.

---

## ⚖️ Legal context

The data exposed by these endpoints is regulatory disclosure data, **intended to be publicly redistributable**:

- 🟢 **AMFI** publishes NAV files specifically for downstream consumers
- 🟢 **BSE** [made its LODR XBRL taxonomies publicly available](https://www.xbrl.org/news/bse-makes-taxonomies-public/) "to promote development of software by the private sector"
- 🟢 **NSE Indices Ltd.** publishes daily index data via archives.nseindia.com as a public service
- 🟢 **SEBI Regulation 31** mandates the quarterly shareholding-pattern disclosure that the BSE LODR endpoint exposes

This catalogue documents **wire protocols, not data**. No licensed datasets are bundled; no scraped historical files are committed.

---

## 🤝 Contributing

PRs welcome for new endpoints, wrapper improvements, or worked examples in other languages. See [CONTRIBUTING.md](CONTRIBUTING.md) for the template every endpoint doc follows, or open an issue using one of the [templates](.github/ISSUE_TEMPLATE/).

If you found a new endpoint:

1. Open an issue with the [`new-endpoint`](.github/ISSUE_TEMPLATE/new-endpoint.yml) template — describe what you found, how you found it, and one quirk you ran into.
2. Or skip straight to a PR following the doc template in `endpoints/`.

---

## 🏛️ Related projects

- [`mfapi.in`](https://www.mfapi.in/) — community-run free MF NAV API (mirror of AMFI NAVAll, easier JSON access)
- [`mfdata.in`](https://mfdata.in/) — free MF API with holdings + sector analysis
- [`mf.captnemo.in`](https://mf.captnemo.in/) — ISIN → scheme metadata lookup

These wrap a subset of what AMFI publishes. This repo is about the **primary sources** so you can build your own clients without depending on a third party staying online.

---

## 📜 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

Built solo by **[Satwik Basu](https://github.com/satwikbasu)** while developing a personal mutual-fund signal system.

<sub>If this saved you a day of reverse-engineering, leave a ⭐ — that's how more developers find it.</sub>

</div>
