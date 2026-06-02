# Examples

Each script is self-contained, just `pip install -e ../wrappers/python` and run.

| Script | What it does |
|---|---|
| [`fetch_all_navs.py`](fetch_all_navs.py) | Pull the daily NAV snapshot from AMFI and print the 5 most expensive equity-fund NAVs |
| [`fetch_nifty_tri.py`](fetch_nifty_tri.py) | Fetch Total Return Index for Nifty 50, Midcap 150, Smallcap 250 (inception-to-today) and compute 5-year CAGR |
| [`fetch_lodr_filing.py`](fetch_lodr_filing.py) | For a BSE scripcode, list quarterly shareholding filings and download the latest iXBRL |

Run any of them:

```bash
pip install -e ../wrappers/python
python fetch_all_navs.py
python fetch_nifty_tri.py
python fetch_lodr_filing.py 500325  # Reliance
```
