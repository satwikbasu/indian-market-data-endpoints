"""Fetch the daily NAV snapshot for every Indian MF scheme and print the top 5 by NAV.

Pulls one ~3 MB file from AMFI. No auth, no API key.

Usage:
    pip install -e ../wrappers/python
    python fetch_all_navs.py
"""
import logging

from indian_markets import amfi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    print("fetching AMFI NAVAll.txt (~3 MB) ...", flush=True)
    rows = list(amfi.fetch_navall_rows())
    print(f"parsed {len(rows):,} schemes from AMFI NAVAll.txt", flush=True)

    equity = [r for r in rows if "Equity" in r.scheme_category]
    print(f"  of which {len(equity):,} are equity schemes")

    by_nav = sorted(equity, key=lambda r: r.nav, reverse=True)[:5]
    print("\nTop 5 equity schemes by NAV:")
    for r in by_nav:
        print(f"  {r.scheme_code:>7}  {r.nav:>12}  {r.scheme_name[:60]}")


if __name__ == "__main__":
    main()
