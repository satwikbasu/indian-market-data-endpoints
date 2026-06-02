# Contributing

Pull requests welcome — new endpoints, wrapper improvements, bug fixes, or worked examples in other languages.

## Adding a new endpoint

Create `endpoints/<source>-<purpose>.md` following the template every existing entry uses:

1. **One-line summary** at the top.
2. **Discovery** — when and how you found it. Be specific about the method (page form inspection, JS bundle grep, accidental find).
3. **Wire spec** — exact URL, method, params table, headers required, body shape, response shape. No prose padding.
4. **Worked example** — a `curl` (or equivalent) that produces a known-good response when pasted into a terminal.
5. **Required headers** table — which headers are load-bearing and which are decorative. Note any header trap (a header that breaks the call when present).
6. **Rate limit / throttle** — observed limits and the production safety margin you applied.
7. **Caveats** — every gotcha you burned an hour on. Future readers will thank you.

Then add a row to the README catalogue table.

## Wrapper code

The Python wrappers in `wrappers/python/indian_markets/` are deliberately minimal — fetcher + parser, no DB, no caching, no retry framework. Keep additions to that standard. If you want a richer client (caching, batching, async), open a discussion first; it might belong in a separate repo.

## What does NOT belong here

- Endpoints behind paywalls or subscriber logins.
- Endpoints requiring captcha or interactive auth.
- Third-party data aggregators (mfapi.in, mfdata.in, Investing.com, etc.) — this catalogue is about primary sources from Indian capital-markets regulators and exchanges.
- Anything you found by reverse-engineering a subscription product's API.

## Provenance

If you copy a wire spec from another open-source project, link the original. If you discovered it yourself, mention the date and method.
