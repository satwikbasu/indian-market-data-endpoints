"""Offline smoke tests: parsers work on synthetic samples; modules import cleanly.

Run: `pytest -q` from wrappers/python/.

These tests do NOT hit the network. The real endpoints have their own integration
tests downstream of the catalogue.
"""
from datetime import date
from decimal import Decimal

import indian_markets
from indian_markets import amfi, bse, nse


def test_modules_import():
    assert indian_markets.__version__
    assert hasattr(amfi, "fetch_navall_text")
    assert hasattr(nse, "fetch_tri")
    assert hasattr(bse, "fetch_shareholding_index")


def test_navall_parser_handles_basic_sample():
    sample = (
        "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date\n"
        "\n"
        "Axis Mutual Fund\n"
        "Open Ended Schemes(Equity Scheme - Large Cap Fund)\n"
        "120586;INF109K01480;-;Axis Bluechip Fund - Direct Plan - Growth;58.4321;21-May-2026\n"
        "120587;-;-;Axis Bluechip Fund - Growth;55.1234;21-May-2026\n"
    )
    rows = list(amfi.parse_navall(sample))
    assert len(rows) == 2
    r = rows[0]
    assert r.scheme_code == 120586
    assert r.amc == "Axis Mutual Fund"
    assert r.scheme_type == "Open Ended Schemes"
    assert r.scheme_category == "Equity Scheme - Large Cap Fund"
    assert r.nav == Decimal("58.4321")
    assert r.nav_date == date(2026, 5, 21)
    assert r.isin_growth == "INF109K01480"
    assert r.isin_reinvest is None


def test_navall_parser_skips_zero_nav():
    sample = (
        "Axis Mutual Fund\n"
        "Open Ended Schemes(Equity Scheme - Large Cap Fund)\n"
        "999999;-;-;Axis Wound-Up Scheme;0.0000;14-Jun-2017\n"
    )
    assert list(amfi.parse_navall(sample)) == []


def test_navall_parser_skips_no_context_rows():
    """Rows without prior AMC + section context should be skipped silently."""
    sample = "120586;-;-;Orphan Row;58.4321;21-May-2026\n"
    assert list(amfi.parse_navall(sample)) == []


def test_navhistory_parser_handles_8field_format():
    sample = (
        "Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date\n"
        "Axis Mutual Fund\n"
        "Open Ended Schemes ( Equity Scheme - Large Cap Fund )\n"
        "120586;Axis Bluechip Fund - Direct Plan - Growth;INF109K01480;;58.4321;58.4321;58.4321;01-Jan-2024\n"
    )
    rows = list(amfi.parse_navhistory(sample))
    assert len(rows) == 1
    assert rows[0].scheme_code == 120586
    assert rows[0].scheme_category == "Equity Scheme - Large Cap Fund"


def test_indices_csv_parser_filters_dash_values():
    sample = (
        "Index Name,Index Date,Open,High,Low,Closing,Points Change,Change(%),Volume,Turnover,P/E,P/B,Div Yield\n"
        "Nifty 50,22-05-2026,24500.50,24650.75,24400.20,24580.40,80.5,0.33,0,0,22.45,3.85,1.25\n"
        "Nifty 50 Futures Index,22-05-2026,-,-,-,-,-,-,0,0,-,-,-\n"
    )
    rows = list(nse.parse_indices_csv(sample))
    assert len(rows) == 1
    assert rows[0].index_name == "Nifty 50"
    assert rows[0].close == Decimal("24580.40")
    assert rows[0].pe == Decimal("22.45")
