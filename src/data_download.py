"""Compatibility imports for the implemented observational data pipeline.

Use ``python -m src.real_data --help`` for the auditable command-line stages.
The implementation lives in :mod:`src.real_data`; this module remains so links
to the prototype's former acquisition outline do not break.
"""

from .real_data import build_aphis, build_landcover, build_modis, build_prism

__all__ = ["build_aphis", "build_landcover", "build_modis", "build_prism"]
