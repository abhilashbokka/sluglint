"""Input adapters.

Every adapter returns the same `Script` the Fountain parser returns, so the
rulebook never learns what format a draft arrived in. Adapters may also return
notes: things they had to assume or normalize, which the report prints so a
reader can tell a finding about the script from an artifact of the conversion.
"""
from __future__ import annotations

from pathlib import Path

from ..models import Script
from ..parser import parse_file

PDF_SUFFIXES = {".pdf"}


def load_script(path: str | Path) -> tuple[Script, list[str]]:
    """Read a draft in whatever format it arrived in. -> (Script, ingest notes)."""
    p = Path(path)
    if p.suffix.lower() in PDF_SUFFIXES:
        from .pdf import parse_pdf  # optional dependency, imported on demand
        return parse_pdf(p)
    return parse_file(p), []
