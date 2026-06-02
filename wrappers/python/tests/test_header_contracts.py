"""Regression tests for header / UA contracts that, if broken, cause the
endpoint to silently hang or return error shells.

These bugs slipped through the initial smoke tests because they don't fire
without a real network call. The tests below assert the *configuration*
that is known to keep the endpoint healthy.

History:
  2026-06-02 — fetch_tri silently stalled because _TRI_HEADERS used a
    non-browser UA. Akamai accepted the POST but never replied.
  2026-06-02 — fetch_tri raised "Cannot open a client instance more than
    once" because _bootstrap_session opened the client before the `with`
    block tried to open it again.
"""
from indian_markets import bse, nse


def test_tri_user_agent_is_browser_like():
    """niftyindices.com Akamai stalls forever on non-browser UAs (not 403).

    The UA must start with 'Mozilla/' so Akamai routes the POST normally.
    """
    ua = nse._TRI_HEADERS["User-Agent"]
    assert ua.startswith("Mozilla/"), (
        f"TRI UA must be browser-like (Mozilla/...) or the POST stalls; got {ua!r}"
    )


def test_tri_required_headers_present():
    """ASP.NET ScriptService gate + Akamai bot-detection inputs."""
    h = nse._TRI_HEADERS
    assert h["Content-Type"] == "application/json; charset=UTF-8"
    assert h["X-Requested-With"] == "XMLHttpRequest"
    assert "niftyindices.com" in h["Referer"]


def test_bse_user_agent_is_browser_like():
    """BSE returns the SPA shell (12 KB text/html) on non-browser UAs."""
    assert bse.UA.startswith("Mozilla/"), (
        f"BSE UA must be browser-like or API returns SPA shell; got {bse.UA!r}"
    )


def test_bse_origin_header_is_absent():
    """Origin trap: setting Origin makes BSE return a 1814-byte error shell.

    Documented in endpoints/lodr-shareholding.md.
    """
    assert "Origin" not in bse._HEADERS, (
        "BSE rejects requests with Origin header — must not be set in _HEADERS"
    )


def test_bse_referer_header_present():
    """Without Referer, BSE serves the Angular SPA shell instead of JSON."""
    assert bse._HEADERS.get("Referer", "").startswith("https://www.bseindia.com")


def test_fetch_tri_signature_has_safe_default_timeout():
    """Inception-to-today payloads are ~600 KB; 60s default is too tight.

    Bumped to 120s after observing repeated ReadTimeout on 5-year ranges.
    """
    import inspect
    sig = inspect.signature(nse.fetch_tri)
    assert sig.parameters["timeout"].default >= 120
