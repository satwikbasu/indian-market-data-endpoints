"""Minimal Python clients for undocumented Indian capital-markets endpoints.

See https://github.com/satwikbasu/indian-market-data-endpoints for the wire-spec
catalogue each module is implemented against.
"""
from . import amfi, bse, nse

__all__ = ["amfi", "nse", "bse"]
__version__ = "0.1.0"
