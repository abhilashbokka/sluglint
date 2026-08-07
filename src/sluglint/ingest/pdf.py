"""PDF ingestion.

Screenplay layout is geometry. Where a line starts horizontally is what tells a
reader whether it is action, dialogue, a parenthetical, or a character cue, and
that signal survives a PDF export even when every other structural hint is gone.
This module reads word positions with pdfplumber, learns the document's own
margins instead of assuming US Letter, and re-emits a Fountain document that
`parser.parse_text` already understands.

Going back out to Fountain rather than building `Script` directly is deliberate.
It keeps one parser and one set of semantics, it lets a writer inspect what we
believe their PDF says (`sluglint convert`), and it means a defect the Fountain
parser would trip over in a typed script trips over it here too. A PDF must not
get a quieter reading of the same rulebook than a .fountain file does.

Two things are normalized away because they belong to the printer rather than
the writer: page numbers, and the (MORE) / (CONT'D) pair that a paginator
inserts when it splits a speech across a page break. Leaving them in would
invent findings that exist in no draft. `PdfIngest.notes` records what was
dropped so the report can say so.

pdfplumber is an optional dependency (`pip install "sluglint[pdf]"`).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Script
from ..parser import HEADING_RE, TRANSITION_RE, parse_text, split_scene_number

# A cue sits about two inches right of the action margin, dialogue about one.
# Stored in inches from the action margin so the numbers survive A4, US Letter,
# and the reduced page boxes that some exporters write.
POINTS_PER_INCH = 72.0
DIALOGUE_INDENT = 0.6
CHARACTER_INDENT = 1.6
# A word more than twice the body size is display type: a watermark, a cover
# title, a stamped SCREENPLAY across the page. It is not a line of script.
DISPLAY_TYPE_RATIO = 2.0
# Rows this far into the head or foot of the page are running heads and folios.
MARGIN_BAND = 0.06
# A left edge needs this share of the document's rows before it counts as a
# column rather than as one stray indent.
COLUMN_SHARE = 0.04
# A vertical step this much bigger than the leading is a blank line.
PARAGRAPH_GAP = 1.5
# Below this share of well-formed Latin words the text layer is glyph codes.
TEXT_CONFIDENCE_FLOOR = 0.95
# Above this share of wide text at cue depth the page is not a screenplay.
SECOND_COLUMN_FLOOR = 0.15
# Above this share of unmapped glyphs the font's character map is broken.
DROPPED_GLYPH_FLOOR = 0.02
# A feature averages well over one scene per page; a tenth of that is a floor.
MIN_HEADINGS_PER_PAGE = 0.1
# And a ceiling. Across 49 real drafts nothing legitimate ran past about 2.5
# scenes per page; the two that did were 5.7 and 6.2, and in both cases the
# geometry had failed and ordinary lines were being read as sluglines. A
# document that claims six scenes a page is not a document with six scenes a
# page, so the reader says so rather than emitting hundreds of false findings.
MAX_HEADINGS_PER_PAGE = 3.0
# A lone asterisk in the margin of a production draft is a revision mark.
REVISION_MARK_RE = re.compile(r"^\*+$")

PAGE_FOLIO_RE = re.compile(r"^\(?\d{1,4}[A-Z]?\.?\)?$")
CONTINUED_RE = re.compile(
    r"^\(?\s*(?:CONTINUED|CONT['\u2019]?D|MORE)\s*[:.]?\s*\)?$", re.IGNORECASE)
CONTD_SUFFIX_RE = re.compile(r"\s*\(\s*CONT['\u2019]?D\s*\)\s*$", re.IGNORECASE)
# 'ANGLE ON', 'THE KITCHEN', 'LATER' and other all-caps action lines look
# exactly like character cues to a line-based parser. Geometry knows better, so
# those get Fountain's forced-action marker on the way out.
FORCE_ACTION_RE = re.compile(r"^[^a-z]*$")


@dataclass
class Line:
    """One visual row of the PDF, with the geometry that classifies it."""
    text: str
    x0: float
    x1: float
    top: float
    page: int
    gap_before: bool = False   # blank vertical space above: a paragraph break


@dataclass
class PdfIngest:
    """The Fountain text recovered from a PDF, plus what we had to assume."""
    fountain: str
    pages: int
    action_x: float
    notes: list[str] = field(default_factory=list)


def _require_pdfplumber():
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised by the CLI message
        raise RuntimeError(
            "PDF ingestion needs pdfplumber. Install it with: "
            'pip install "sluglint[pdf]"'
        ) from exc
    return pdfplumber


def _rows(page, body_size: float) -> list[Line]:
    """Group a page's words into visual rows, dropping display type."""
    words = [
        w for w in page.extract_words(extra_attrs=["size", "upright"])
        if w.get("upright", True) and w.get("size", body_size) <= body_size * DISPLAY_TYPE_RATIO
    ]
    buckets: dict[int, list[dict]] = {}
    for w in words:
        buckets.setdefault(round(w["top"] / 3.0), []).append(w)
    lines: list[Line] = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ws).strip()
        if text:
            lines.append(Line(text, ws[0]["x0"], max(w["x1"] for w in ws),
                              min(w["top"] for w in ws), page.page_number))
    # Blank space is the only mark a paragraph break leaves in a PDF. The
    # ordinary gap between two rows of one paragraph is the leading; anything
    # meaningfully larger is the writer pressing return.
    gaps = sorted(b.top - a.top for a, b in zip(lines, lines[1:]) if b.top > a.top)
    leading = gaps[len(gaps) // 2] if gaps else 0.0
    for prev, cur in zip(lines, lines[1:]):
        cur.gap_before = leading > 0 and (cur.top - prev.top) > leading * PARAGRAPH_GAP
    return lines


def _body_size(pdf, sample: int = 12) -> float:
    """Median font size over a sample of pages: the size ordinary script is set in."""
    sizes: Counter[int] = Counter()
    for page in pdf.pages[:sample]:
        for ch in page.chars:
            sizes[round(ch.get("size", 12))] += 1
    return float(sizes.most_common(1)[0][0]) if sizes else 12.0


# A lowercase letter followed by a capital inside one word: 'jSfxax', 'BIik'.
# Real prose does this almost never; a legacy Indic font does it constantly.
MOJIBAKE_SHAPE = re.compile(r"[a-z][A-Z]")


def text_confidence(lines: list[Line]) -> float:
    """How much of the Latin text reads as words rather than as glyph codes.

    Legacy Indic fonts (Krutidev, Shree-Lipi, Priyaanka and their relatives)
    predate Unicode and map Devanagari and Telugu glyphs onto Latin code
    points. The page prints perfectly and extracts as 'lhfu;j jSfxax': it has
    letters, spaces, and sensible word lengths, so length and density checks
    all pass it. What gives it away is shape. Those strings are full of
    mid-word capitals and stray punctuation, because the code points were
    chosen to draw a glyph rather than to spell anything.

    A low score means the PDF is readable to a person and gibberish to us.
    Linting it would report defects in the encoding rather than in the script.
    """
    tokens = [t.strip(".,;:!?()[]'\"") for ln in lines for t in ln.text.split()]
    # A NUL or a replacement character is a glyph the font's character map could
    # not name. A few are a stray ligature; a steady stream means whole Telugu
    # and Devanagari conjuncts are being dropped, and what is left is not the
    # word that was written.
    body = "".join(tokens)
    if body and sum(c in "\x00\ufffd" for c in body) / len(body) > DROPPED_GLYPH_FLOOR:
        return 0.0
    latin = [t for t in tokens
             if len(t) >= 3 and any(c.isalpha() for c in t) and all(ord(c) < 0x250 for c in t)]
    if len(latin) < 50:
        return 1.0  # too little Latin text to judge; native script is handled by Unicode
    garbled = sum(1 for w in latin
                  if MOJIBAKE_SHAPE.search(w) or any(c in ";^+\\|~`" for c in w))
    return round(1.0 - garbled / len(latin), 3)


def _action_margin(lines: list[Line]) -> float:
    """The leftmost left edge that carries a real share of the document.

    Not the most common one. Dialogue outnumbers action in plenty of scripts,
    and scene numbers and folios sit further left than either, so the answer is
    the leftmost edge that clears a share threshold.
    """
    edges = Counter(round(ln.x0) for ln in lines)
    floor = max(3, int(len(lines) * COLUMN_SHARE))
    columns = sorted(x for x, n in edges.items() if n >= floor)
    return float(columns[0]) if columns else 0.0


def _second_column_share(lines: list[Line], action_x: float) -> float:
    """How much of the text at cue depth is too wide to be a character cue.

    A cue is a name: short, and alone on its line. When most of what sits two
    inches in is full-width running text, the page is not laid out as a
    screenplay at all. It is a published edition with a translation column, a
    censor transcript, or a document whose margins we read wrong. Measured
    across the local corpus this separates cleanly: real screenplays put 0 to
    3 percent of their cue-depth text over two inches wide, the others 20 to 70.
    """
    deep = [ln for ln in lines if (ln.x0 - action_x) / POINTS_PER_INCH >= CHARACTER_INDENT]
    if not deep:
        return 0.0
    wide = sum(1 for ln in deep if (ln.x1 - ln.x0) > 2 * POINTS_PER_INCH)
    return wide / len(deep)


def _classify(ln: Line, action_x: float, page_height: float, right_edge: float) -> str:
    """-> heading | character | parenthetical | dialogue | transition | action | drop."""
    text = ln.text.strip()
    in_margin = ln.top < page_height * MARGIN_BAND or ln.top > page_height * (1 - MARGIN_BAND)
    if in_margin and (PAGE_FOLIO_RE.match(text) or CONTINUED_RE.match(text)):
        return "drop"
    if CONTINUED_RE.match(text) or REVISION_MARK_RE.match(text):
        return "drop"
    indent = (ln.x0 - action_x) / POINTS_PER_INCH
    unnumbered, _ = split_scene_number(text)
    if indent < DIALOGUE_INDENT and HEADING_RE.match(unnumbered):
        return "heading"
    if TRANSITION_RE.match(text) and ln.x1 > right_edge - 1.5 * POINTS_PER_INCH:
        return "transition"
    # The cue column is tested before the parenthetical one. Writers do set a
    # speaker as '(VOICE ON THE PHONE)', and at cue depth that is who is
    # talking. Read as a parenthetical it would hand the speech to whoever
    # spoke last, which is a wrong answer rather than a missing one.
    if indent >= CHARACTER_INDENT:
        return "character"
    if text.startswith("(") and indent >= DIALOGUE_INDENT:
        return "parenthetical"
    if indent >= DIALOGUE_INDENT:
        return "dialogue"
    return "action"


BY_LINE_RE = re.compile(
    r"^(?:written|screenplay|story and screenplay|screenplay and dialogues?|a screenplay)?\s*by:?$",
    re.IGNORECASE)
CONTACT_RE = re.compile(r"[@]|^\+?[\d ()\-]{7,}$")


def _title_page(lines: list[Line]) -> tuple[list[str], int]:
    """Recover Fountain title-page keys from page one. -> (keys, rows consumed).

    A cover page is centered text with no keys on it, so the Fountain parser
    reads it as action and F031 reports a missing title page on every PDF ever
    exported. The 'by' line is the anchor: whatever sits above it is the title
    and whatever sits below it is the writer.
    """
    front = [ln for ln in lines if ln.page == 1]
    if not front:
        return [], 0
    by_at = next((i for i, ln in enumerate(front) if BY_LINE_RE.match(ln.text.strip())), None)
    if by_at is None or by_at == 0 or by_at + 1 >= len(front):
        return [], 0
    keys = [f"Title: {front[by_at - 1].text.strip()}",
            f"Credit: {front[by_at].text.strip().lower()}",
            f"Author: {front[by_at + 1].text.strip()}"]
    contact = [ln.text.strip() for ln in front[by_at + 2:] if CONTACT_RE.search(ln.text.strip())]
    if contact:
        keys.append(f"Contact: {contact[0]}")
    keys.append("")
    return keys, len(front)


def _emit(typed: list[tuple[str, Line]]) -> tuple[list[str], int]:
    """Typed rows -> Fountain lines. Returns the text and the speeches rejoined."""
    out: list[str] = []
    rejoined = 0
    last_cue: str | None = None
    prev_kind: str | None = None

    def blank():
        if out and out[-1] != "":
            out.append("")

    for kind, ln in typed:
        text = ln.text.strip()
        if kind == "heading":
            blank()
            out.append(text)
            last_cue = None
        elif kind == "character":
            base = CONTD_SUFFIX_RE.sub("", text).strip()
            # A paginator splits a speech with (MORE) and restarts it as
            # 'NAME (CONT'D)'. Same speaker, no intervening element: that is one
            # speech in the writer's draft and it gets put back together.
            if base == last_cue and prev_kind in {"dialogue", "parenthetical"} \
                    and CONTD_SUFFIX_RE.search(text):
                rejoined += 1
                prev_kind = kind
                continue
            blank()
            out.append(text)
            last_cue = base
        elif kind in {"dialogue", "parenthetical"}:
            out.append(text)
        elif kind == "transition":
            blank()
            out.append(text)
            last_cue = None
        else:
            if prev_kind != "action" or ln.gap_before:
                blank()
            # Geometry says action; a line-based parser would read an all-caps
            # one as a cue. Fountain's '!' says otherwise.
            out.append("!" + text if FORCE_ACTION_RE.match(text) else text)
            last_cue = None
        prev_kind = kind
    return out, rejoined




def ingest(path: str | Path) -> PdfIngest:
    """Read a screenplay PDF and recover a Fountain document from its geometry."""
    pdfplumber = _require_pdfplumber()
    notes: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        body = _body_size(pdf)
        lines: list[Line] = []
        heights: list[float] = []
        widths: list[float] = []
        for page in pdf.pages:
            lines.extend(_rows(page, body))
            heights.append(page.height)
            widths.append(page.width)
        n_pages = len(pdf.pages)

    if not lines:
        notes.append("No extractable text. The PDF is probably a scan, or its "
                     "fonts carry no Unicode mapping.")
        return PdfIngest("", n_pages, 0.0, notes)

    confidence = text_confidence(lines)
    if confidence < TEXT_CONFIDENCE_FLOOR:
        notes.append(
            f"Text layer scores {confidence:.0%}. Either the PDF is set in a "
            f"pre-Unicode Indic font whose text extracts as glyph codes, or its "
            f"character map drops conjuncts. Either way it prints correctly and "
            f"reads as gibberish. Findings below describe the encoding rather "
            f"than the script. This one needs OCR.")

    action_x = _action_margin(lines)
    page_height = sorted(heights)[len(heights) // 2]
    right_edge = max(ln.x1 for ln in lines)

    second_column = _second_column_share(lines, action_x)
    if second_column > SECOND_COLUMN_FLOOR:
        notes.append(
            f"{second_column:.0%} of the text at character-cue depth is full-width "
            f"running text. This is not screenplay geometry: it reads as a "
            f"published edition, a transcript, or a two-language layout, and "
            f"element types below are guesses.")

    cover, consumed = _title_page(lines)
    typed = [(_classify(ln, action_x, page_height, right_edge), ln)
             for ln in lines[consumed:]]
    dropped = sum(1 for kind, _ in typed if kind == "drop")
    kept = [(k, ln) for k, ln in typed if k != "drop"]
    body, rejoined = _emit(kept)
    out = cover + body

    headings = sum(1 for kind, _ in kept if kind == "heading")
    if headings < n_pages * MIN_HEADINGS_PER_PAGE:
        notes.append(
            f"Only {headings} INT./EXT. sluglines across {n_pages} pages. Either "
            f"the scene headings are written some other way, or this is not a "
            f"screenplay. Structural and continuity rules have nothing to run on.")
    if dropped:
        notes.append(f"Removed {dropped} page numbers and CONTINUED markers. "
                     f"F025 (pagination artifacts) cannot be judged from a PDF.")
    if rejoined:
        notes.append(f"Rejoined {rejoined} speeches split across a page break.")
    cues = sum(1 for kind, _ in kept if kind == "character")
    if cues == 0:
        notes.append("No character cues found at a dialogue indent. The layout "
                     "is not standard screenplay geometry.")
    return PdfIngest("\n".join(out) + "\n", n_pages, action_x, notes)


def parse_pdf(path: str | Path) -> tuple[Script, list[str]]:
    """PDF -> (Script, ingest notes)."""
    result = ingest(path)
    script = parse_text(result.fountain, str(path))
    # The PDF states its own page count. Nothing derived beats that, and the
    # derived estimate was a third low before this was wired through.
    script.page_count = result.pages
    return script, result.notes
