"""Fetch Total Return Index for Nifty 50 / Midcap 150 / Smallcap 250 and compute 5y CAGR.

One POST per index returns the full inception-to-today series. ~6,000 rows for Nifty 50.

Usage:
    pip install -e ../wrappers/python
    python fetch_nifty_tri.py
"""
from datetime import date, timedelta

from indian_markets import nse


def cagr(start_value: float, end_value: float, years: float) -> float:
    return (end_value / start_value) ** (1 / years) - 1


def main() -> None:
    today = date.today()
    five_years_ago = today - timedelta(days=365 * 5)

    end = today.strftime("%d-%b-%Y")
    start = "01-Jan-1999"

    for name in ("NIFTY 50", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250"):
        rows = nse.fetch_tri(name, start, end)
        if not rows:
            print(f"{name}: no data (check canonical name)")
            continue

        # rows are most-recent-first
        latest = float(rows[0]["TotalReturnsIndex"])

        # Find row closest to 5y ago
        from datetime import datetime
        target = datetime.combine(five_years_ago, datetime.min.time())
        closest = min(rows, key=lambda r: abs(datetime.strptime(r["Date"], "%d %b %Y") - target))
        old = float(closest["TotalReturnsIndex"])
        old_date = closest["Date"]

        years = (today - five_years_ago).days / 365.25
        r = cagr(old, latest, years) * 100

        print(f"{name:<22}  TRI {old:>10.2f} ({old_date})  →  {latest:>10.2f} ({rows[0]['Date']})  CAGR {r:+.2f}% / yr")


if __name__ == "__main__":
    main()
