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
# How many pages to sample when asking what the document is set in. The title
# page is the worst possible sample (display type, its own margins, no body),
# so this is a sample of many rather than a look at page one.
FONT_SAMPLE_PAGES = 12
# Share of glyphs that must sit at one advance width for the type to be
# monospaced. MEASURED against 12 produced screenplays: the ten set in a
# Courier variant score 0.87 to 1.00, and the two that are not (Annie Hall in
# Times, Gone Girl in Helvetica) score 0.30 and 0.38. Nothing lands between.
# 0.70 sits in that empty band with room either side; the 0.90 first guessed
# here would have called Get Out proportional, and it is set in Courier.
MONOSPACE_SHARE = 0.70
# A feature averages well over one scene per page; a tenth of that is a floor.
# The matching ceiling lives in `ingest/__init__.py` as MAX_SCENES_PER_PAGE,
# because it has to count what the parser finally built rather than what this
# module's classifier called a heading. Those two disagree exactly when
# something has gone wrong, which is the case worth catching.
MIN_HEADINGS_PER_PAGE = 0.1
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
    # One entry per line of `fountain`, holding the PDF page that line printed
    # on (None for the blank lines Fountain needs and the PDF never had). The
    # page a line fell on is something the document states, so it is carried
    # rather than derived; see `_stamp_pages`.
    page_map: list[int | None] = field(default_factory=list)
    # What the file states about itself: page size, font, monospace.
    # Kept rather than discarded; see docs/field-provenance.md.
    source_meta: dict = field(default_factory=dict)


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


def _emit(typed: list[tuple[str, Line]]) -> tuple[list[str], list[int | None], int]:
    """Typed rows -> Fountain lines. -> (text, page per line, speeches rejoined).

    The page list runs alongside the text so the page each row printed on
    survives the trip out to Fountain and back. Without it the only thing left
    downstream is a line number in a file that never had pages, and every rule
    about a page break would have to estimate where the breaks were.
    """
    out: list[str] = []
    pages: list[int | None] = []
    rejoined = 0
    last_cue: str | None = None
    prev_kind: str | None = None

    def write(text: str, page: int | None) -> None:
        out.append(text)
        pages.append(page)

    def blank():
        if out and out[-1] != "":
            write("", None)

    for kind, ln in typed:
        text = ln.text.strip()
        if kind == "heading":
            blank()
            write(text, ln.page)
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
            write(text, ln.page)
            last_cue = base
        elif kind in {"dialogue", "parenthetical"}:
            write(text, ln.page)
        elif kind == "transition":
            blank()
            write(text, ln.page)
            last_cue = None
        else:
            if prev_kind != "action" or ln.gap_before:
                blank()
            # Geometry says action; a line-based parser would read an all-caps
            # one as a cue. Fountain's '!' says otherwise.
            write("!" + text if FORCE_ACTION_RE.match(text) else text, ln.page)
            last_cue = None
        prev_kind = kind
    return out, pages, rejoined


def _stamp_pages(script: Script, page_map: list[int | None]) -> None:
    """Put each element back on the page it came off.

    `parse_text` numbers its elements by line in the Fountain it was handed,
    and that text was built one line at a time from rows that each knew their
    page. So the line number indexes straight back into the page list. Scene
    and script objects share these Element instances, so stamping once is
    enough for every layer that reads them.
    """
    for el in script.elements:
        index = el.line_no - 1
        if 0 <= index < len(page_map):
            el.page = page_map[index]




def _source_facts(pdf, widths: list[float], heights: list[float],
                  rotated: int) -> dict:
    """The facts the PDF states about itself, kept rather than discarded.

    None of these are findings and none are derived. They are what the file
    says: how big its pages are, what it is set in, whether the type is
    monospaced. Page size in particular is what makes a size measurement
    comparable at all, because a script printed on a 5.5-inch page is set in
    9pt and is perfectly normal.

    Monospace is tested by advance width rather than by font name. An embedded
    subset is routinely renamed to `AAAAAA+` or `F1`, which makes the name
    useless and leaves the metric intact.
    """
    fonts: Counter[str] = Counter()
    advances: Counter[float] = Counter()
    for page in pdf.pages[:FONT_SAMPLE_PAGES]:
        for ch in page.chars:
            if not ch.get("text", " ").strip():
                continue
            fonts[str(ch.get("fontname", "")).split("+")[-1]] += 1
            advances[round(float(ch.get("adv", 0.0)), 2)] += 1
    facts: dict = {"pages": len(pdf.pages), "rotated_pages": rotated}
    if widths and heights:
        facts["page_width_in"] = round(sorted(widths)[len(widths) // 2] / POINTS_PER_INCH, 2)
        facts["page_height_in"] = round(sorted(heights)[len(heights) // 2] / POINTS_PER_INCH, 2)
    if fonts:
        name, n = fonts.most_common(1)[0]
        facts["font"] = name or "unnamed"
        facts["font_share"] = round(n / sum(fonts.values()), 3)
        facts["font_count"] = len(fonts)
    if advances:
        _, n = advances.most_common(1)[0]
        share = n / sum(advances.values())
        facts["monospace_share"] = round(share, 3)
        facts["monospace"] = share >= MONOSPACE_SHARE
    return facts


def ingest(path: str | Path) -> PdfIngest:
    """Read a screenplay PDF and recover a Fountain document from its geometry."""
    pdfplumber = _require_pdfplumber()
    notes: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        body = _body_size(pdf)
        lines: list[Line] = []
        heights: list[float] = []
        widths: list[float] = []
        # Rotation matters before the geometry is read, never after. A page
        # turned 90 degrees has its axes swapped, so an indent measured off it
        # would really be a vertical position and the classifier would report
        # confident nonsense. pdfplumber already applies the page's own
        # /Rotate (it normalises the box and rotates every point), so the
        # coordinates below are upright and the correction is not ours to
        # make. What was missing is noticing: a rotated page is worth saying
        # out loud, because it is the shape of document that arrives scanned.
        rotated = sum(1 for page in pdf.pages if page.rotation)
        for page in pdf.pages:
            lines.extend(_rows(page, body))
            heights.append(page.height)
            widths.append(page.width)
        n_pages = len(pdf.pages)
        meta = _source_facts(pdf, widths, heights, rotated)

    if rotated:
        notes.append(f"{rotated} of {n_pages} pages carry a /Rotate. They were read "
                     f"upright, but a rotated page usually means a scan or a "
                     f"reassembled document, so check the element types below.")
    if not lines:
        notes.append("No extractable text. The PDF is probably a scan, or its "
                     "fonts carry no Unicode mapping.")
        return PdfIngest("", n_pages, 0.0, notes, source_meta=meta)

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
    body, body_pages, rejoined = _emit(kept)
    out = cover + body
    # `_title_page` only ever reads page one, and its last entry is the blank
    # line that closes the Fountain title block.
    page_map = [1 if key else None for key in cover] + body_pages

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
    return PdfIngest("\n".join(out) + "\n", n_pages, action_x, notes, page_map, meta)


def parse_pdf(path: str | Path) -> tuple[Script, list[str]]:
    """PDF -> (Script, ingest notes)."""
    result = ingest(path)
    script = parse_text(result.fountain, str(path))
    # The PDF states its own page count. Nothing derived beats that, and the
    # derived estimate was a third low before this was wired through.
    script.page_count = result.pages
    script.source_meta = result.source_meta
    # It also states which page every line fell on, so that is carried back
    # onto the elements rather than reconstructed from a line number.
    _stamp_pages(script, result.page_map)
    # Scene *lengths* are still shares of the whole, so they are stretched onto
    # the real total; a rule reading a scene's length and a dashboard drawing
    # it must never disagree.
    script.reconcile_pages()
    return script, result.notes
