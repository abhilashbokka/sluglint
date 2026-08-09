"""Core data models for Sluglint.

A parsed script is a list of Scenes; each Scene is a list of Elements.
Findings are the universal output unit of every lint tier.

Elements keep more than the linters strictly need: the raw source line, the
character extension, the dual-dialogue marker. Tier-1 rules about
document hygiene (stray tabs, smart quotes, pagination artifacts) can only be
checked against text the parser has *not* normalized.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum

# A formatted page holds about 55 lines counting the blank ones, but only about
# 36 carry text. The parser drops blank lines, so
# counting elements against 55 understates a script by a third. Measured
# against seven produced screenplays whose real page count is known: Parasite
# 38.1 text lines per page, Her 39.8, 2001 40.5, The Matrix 36.5, Whiplash
# 34.4, The Shining 34.1, Inside Out 34.8. The median is the constant below.
BODY_LINES_PER_PAGE = 36.5
# Printed width of each element at 12pt Courier, in characters. Action runs the
# full six-inch measure; dialogue and parentheticals sit in narrower columns.
# A Fountain source holds a whole paragraph on one line, so its printed length
# has to be recovered by wrapping before any page count means anything.
COLUMN_WIDTH = {
    "dialogue": 35,
    "parenthetical": 25,
}
DEFAULT_COLUMN = 60


class ElementType(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    TITLE_PAGE = "title_page"
    SECTION = "section"        # ACT ONE, COLD OPEN, INTERVAL, SONG: ...


class Severity(str, Enum):
    ERROR = "error"          # objectively wrong (format / hard rules)
    WARNING = "warning"      # very likely a defect (consistency, strong conventions)
    SUGGESTION = "suggestion"  # craft advice (soft rules)


def printed_lines(text: str, kind: str, prewrapped: bool = False) -> int:
    """How many lines this element takes on a formatted page.

    A Fountain source holds a whole paragraph on one line, so its printed
    length has to be recovered by wrapping. A PDF row and a crawled text dump
    are already one line each, and re-wrapping those at a narrower standard
    column counts every line twice. `prewrapped` says which kind of source
    this is; `already_wrapped()` decides it once per document.
    """
    body = text.strip()
    if not body:
        return 0
    if prewrapped:
        return 1
    width = COLUMN_WIDTH.get(kind, DEFAULT_COLUMN)
    return max(1, -(-len(body) // width))


def already_wrapped(elements) -> bool:
    """Did this source break its own lines, or is it holding paragraphs?

    A wrapped source has a hard ceiling: lengths cluster under it and almost
    nothing passes it. A paragraph source has a long tail instead. The gap
    between the middle and the far end tells them apart, which is the same
    learn-the-document trick the PDF reader uses on margins rather than a
    constant anybody has to keep true.
    """
    lengths = sorted(len(el.text.strip()) for el in elements
                     if el.type is ElementType.ACTION and el.text.strip())
    if len(lengths) < 40:
        return False
    mid = lengths[len(lengths) // 2]
    far = lengths[int(len(lengths) * 0.99)]
    # A wrapped source sits inside a narrow band: on a ScriptBase crawl the
    # far end is 1.2x the middle. A paragraph source runs 3x to 5x.
    return mid >= 20 and far <= mid * 1.6


@dataclass
class Element:
    type: ElementType
    text: str
    line_no: int                       # 1-based line in source file
    scene_index: int = -1              # -1 = before first scene
    character: str | None = None    # set on DIALOGUE/PARENTHETICAL (normalized owner)
    raw: str = ""                      # original source line, before stripping
    extension: str = ""                # CHARACTER only: V.O. / O.S. / CONT'D / ...
    dual: bool = False                 # CHARACTER only: fountain '^' simultaneous marker
    # The 1-based page this element printed on, when the source paginated
    # itself. A PDF knows exactly where every line fell and there is no reason
    # to derive it; None means the source has no pages (Fountain text), and a
    # rule about page breaks has to stay silent rather than guess.
    page: int | None = None
    # Where it fell, in pages, counting the fraction down the page: 12.25 is a
    # quarter of the way down page 12. This is what makes a scene's LENGTH
    # measurable rather than estimated, because the distance between two of
    # these is the distance on paper. `page` is just its whole part.
    page_pos: float | None = None


@dataclass
class Scene:
    index: int
    heading: str                       # as written, scene number included
    line_no: int
    int_ext: str | None = None      # INT / EXT / INT./EXT
    location: str | None = None
    time_of_day: str | None = None
    number: str | None = None       # shooting-script scene number ('14', '14A')
    act: str | None = None          # enclosing act marker, if any
    elements: list[Element] = field(default_factory=list)
    # Whether the SOURCE broke its own lines. Decided once for the whole
    # document and stamped here, because a single scene rarely holds the forty
    # action lines `already_wrapped` needs to tell the two kinds of source
    # apart. Deciding it per scene made a wrapped script's scenes measure up to
    # 30% long, and made two adjacent scenes in one document disagree.
    prewrapped: bool = False
    # Set when the source states its own page count, so the scenes sum to the
    # real document rather than to an estimate. See `Script.reconcile_pages`.
    page_scale: float = 1.0
    # The scene's length in pages, MEASURED off the page rather than counted
    # from its text. Set by `Script.measure_scenes` when the source paginated
    # itself; None otherwise, and then the estimate above is used instead.
    page_span: float | None = None

    @property
    def characters(self) -> list[str]:
        seen: list[str] = []
        for el in self.elements:
            if el.type == ElementType.CHARACTER and el.text not in seen:
                seen.append(el.text)
        return seen

    @property
    def text(self) -> str:
        return "\n".join(el.text for el in self.elements)

    @property
    def page(self) -> int | None:
        """The page the heading printed on, or None when the source has no pages."""
        return next((el.page for el in self.elements if el.page is not None), None)

    @property
    def start_pos(self) -> float | None:
        """Where the scene begins, in pages including the fraction."""
        return next((el.page_pos for el in self.elements if el.page_pos is not None), None)

    @property
    def estimated_pages(self) -> float:
        """Measured when the source paginated itself, counted otherwise.

        `page_span` is the distance on paper between this scene's first line
        and the next scene's first line, which is the scene's length rather
        than a proxy for it. Without it the length is recovered by wrapping
        each element to its column and dividing by the lines a page carries,
        then stretched onto the document's real total.
        """
        if self.page_span is not None:
            return self.page_span
        lines = sum(printed_lines(el.text, el.type, self.prewrapped)
                    for el in self.elements)
        return round(lines / BODY_LINES_PER_PAGE * self.page_scale, 2)


@dataclass
class Script:
    path: str
    title: str | None
    scenes: list[Scene]
    elements: list[Element]            # flat, in document order
    total_lines: int
    raw_text: str = ""                 # untouched source, for hygiene checks
    title_page: dict[str, str] = field(default_factory=dict)
    page_count: int | None = None      # real pages, when the source has them
    # What the SOURCE stated about itself: page size, font, monospace share.
    # Facts, never findings, and never derived. Empty for a text draft,
    # which states nothing. See docs/field-provenance.md.
    source_meta: dict = field(default_factory=dict)
    prewrapped: bool = False           # source broke its own lines; see Scene

    @property
    def estimated_pages(self) -> float:
        """Real pages when the source knows them, otherwise printed lines.

        A PDF states its own page count and nothing beats that. Everything
        else gets counted: wrap each element to its column, sum the lines,
        divide by the ~36.5 text lines a page carries.
        """
        if self.page_count:
            return float(self.page_count)
        lines = sum(printed_lines(el.text, el.type, self.prewrapped)
                    for el in self.elements)
        return round(lines / BODY_LINES_PER_PAGE, 1)

    def measure_scenes(self) -> None:
        """Measure each scene's length off the page, when the page is known.

        A scene runs from its own first line to the next scene's first line,
        and both of those are positions the document states. Subtracting them
        gives the length on paper, which is the thing every scene-length rule
        and the dashboard were previously approximating by counting characters
        and dividing by a constant.

        The last scene has no successor, so it ends at the last line of the
        document. That understates it by whatever sits below that line on the
        final page, which is at most a few lines and only ever on one scene.

        Does nothing for a source with no pages. `reconcile_pages` still
        handles that case.
        """
        starts = [sc.start_pos for sc in self.scenes]
        if not any(s is not None for s in starts):
            return
        last = max((el.page_pos for el in self.elements if el.page_pos is not None),
                   default=None)
        for i, scene in enumerate(self.scenes):
            start = starts[i]
            if start is None:
                continue
            nxt = next((s for s in starts[i + 1:] if s is not None), None)
            end = nxt if nxt is not None else last
            if end is not None and end >= start:
                scene.page_span = round(end - start, 2)

    def reconcile_pages(self) -> None:
        """Scale every scene so the scenes sum to the document's real length.

        A PDF states its page count and the estimate does not have to agree
        with it. Left alone the two drifted up to 10%, which meant the rule
        that flags a four-page scene and the dashboard that draws the same
        scene were reading different numbers off the same document. Only the
        estimated share of the whole is knowable per scene; the total is known
        exactly, so the shares are stretched onto it.
        """
        if not self.page_count or not self.scenes:
            return
        for scene in self.scenes:
            scene.page_scale = 1.0
        loose = sum(sc.estimated_pages for sc in self.scenes)
        if loose <= 0:
            return
        scale = float(self.page_count) / loose
        for scene in self.scenes:
            scene.page_scale = scale

    def of_type(self, *types: ElementType) -> list[Element]:
        return [el for el in self.elements if el.type in types]

    def character_registry(self) -> dict[str, list[int]]:
        """Normalized character name -> scene indices where they speak."""
        reg: dict[str, list[int]] = {}
        for sc in self.scenes:
            for name in sc.characters:
                reg.setdefault(name, [])
                if sc.index not in reg[name]:
                    reg[name].append(sc.index)
        return reg

    def dialogue_counts(self) -> dict[str, int]:
        """Normalized character name -> number of dialogue lines they speak."""
        counts: dict[str, int] = {}
        for el in self.elements:
            if el.type == ElementType.DIALOGUE and el.character:
                counts[el.character] = counts.get(el.character, 0) + 1
        return counts


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    line_no: int | None = None
    scene_index: int | None = None
    evidence: str = ""
    suggestion: str = ""
    source: str = ""                   # rulebook attribution
    tier: int = 1
    confidence: float = 1.0            # <1.0 only for LLM findings

    @property
    def fingerprint(self) -> str:
        """Stable identity across drafts: rule + normalized evidence.

        Deliberately excludes line numbers so a finding survives the text
        moving around, which is what makes draft diffing meaningful.
        """
        norm = re.sub(r"[^a-z0-9]+", "", (self.evidence or self.message).lower())
        return f"{self.rule_id}:{hashlib.sha1(norm.encode()).hexdigest()[:12]}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["fingerprint"] = self.fingerprint
        return d
