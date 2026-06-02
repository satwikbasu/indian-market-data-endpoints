<!-- Thanks for the PR! Please fill in what applies. -->

## What does this change?

<!-- One paragraph. New endpoint? Doc fix? Wrapper improvement? -->

## Type

- [ ] New endpoint doc
- [ ] Update to existing endpoint doc (drift, new quirk, header change)
- [ ] Wrapper library code
- [ ] Worked example
- [ ] Repo infrastructure (CI, templates, docs)

## Checklist (for new endpoints)

- [ ] Follows the doc template used by every existing entry in `endpoints/`
- [ ] Wire spec includes exact URL, method, params table, required headers, response shape
- [ ] At least one worked `curl` (or equivalent) verified within the last week
- [ ] **Quirks** section documents every gotcha discovered
- [ ] **Required headers** table flags any header trap
- [ ] Endpoint is publicly accessible (no paywall, no subscriber login)
- [ ] Catalogue table in README is updated

## Checklist (for wrapper / example changes)

- [ ] No new heavy dependencies added (httpx-only baseline preserved)
- [ ] Minimal LOC; matches the "fetcher + parser, no DB, no caching" standard
