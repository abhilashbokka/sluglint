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

# Across 49 real drafts nothing legitimate ran past about 2.5 scenes per page.
# The two documents that did came back at 5.7 and 6.2, and in both the reader
# had lost the margin geometry and was promoting ordinary lines to sluglines.
# A document claiming six scenes a page does not have six scenes a page.
MAX_SCENES_PER_PAGE = 3.0


def implausible_density(script: Script) -> str:
    """A note when the scene count cannot be true, or "" when it can.

    Checked here rather than inside the PDF reader because the reader counts
    what ITS classifier called a heading, and the number that matters is what
    the parser finally built. Those two disagree exactly when something has
    gone wrong, which is the case worth catching.
    """
    pages = script.estimated_pages
    if pages < 5 or not script.scenes:
        return ""
    rate = len(script.scenes) / pages
    if rate <= MAX_SCENES_PER_PAGE:
        return ""
    return (f"{len(script.scenes)} scenes across ~{pages:.0f} pages is {rate:.1f} per page, "
            f"which no screenplay runs at. Ordinary lines are being read as scene headings, "
            f"so the layout was not recovered. Treat every structural and continuity "
            f"finding below as unreliable.")


def load_script(path: str | Path) -> tuple[Script, list[str]]:
    """Read a draft in whatever format it arrived in. -> (Script, ingest notes)."""
    p = Path(path)
    if p.suffix.lower() in PDF_SUFFIXES:
        from .pdf import parse_pdf  # noqa: PLC0415 - optional dependency, on demand
        script, notes = parse_pdf(p)
    else:
        script, notes = parse_file(p), []
    if warning := implausible_density(script):
        notes.append(warning)
    return script, notes
