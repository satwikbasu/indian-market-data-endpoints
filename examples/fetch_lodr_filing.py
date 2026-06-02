"""List BSE LODR Reg 31 shareholding filings for one scrip; download the latest iXBRL.

Two endpoints called, both via the wrapper client:
  1. /BseIndiaAPI/api/Corp_Shareholding_ng/w  → filings index
  2. /XBRLFILES/...                            → iXBRL file (1.2-1.4 MB)

Usage:
    pip install -e ../wrappers/python
    python fetch_lodr_filing.py 500325       # Reliance
    python fetch_lodr_filing.py 532540       # TCS
    python fetch_lodr_filing.py 532174       # ICICI Bank

The downloaded iXBRL contains MutualFundsOrUTIDomain rows naming every fund
holding ≥1% of the company. Use lxml to walk the ix:* tagged tree:

    pip install lxml
    # then parse `filing_bytes` and select tags like:
    # //ix:nonNumeric[@name="in-bse-shp:NameOfTheShareHolders"]
"""
import sys
from pathlib import Path

from indian_markets import bse


def main(scripcode: int) -> None:
    print(f"fetching shareholding filings index for scrip {scripcode}...")
    filings = bse.fetch_shareholding_index(scripcode)
    if not filings:
        print(f"no filings returned for scrip {scripcode}")
        return

    print(f"found {len(filings)} quarterly filings")
    print(f"  earliest: {filings[-1].get('sQtrName')}")
    print(f"  latest:   {filings[0].get('sQtrName')}  ({filings[0].get('EndDate', '')[:10]})")

    latest = filings[0]
    attachment = latest.get("XBRLAttachment", "")
    if not attachment or not latest.get("IsXBRL"):
        print("latest filing has no iXBRL attachment; skipping download")
        return

    print(f"\ndownloading iXBRL: {attachment}")
    content = bse.fetch_xbrl_filing(attachment)
    out = Path(f"shp_{scripcode}_{latest.get('EndDate', '')[:10]}.html")
    out.write_bytes(content)
    print(f"  saved {len(content):,} bytes → {out}")
    print(f"\nparse with lxml + namespace 'in-bse-shp' to extract MutualFund holder rows.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python fetch_lodr_filing.py <scripcode>")
        sys.exit(1)
    main(int(sys.argv[1]))
