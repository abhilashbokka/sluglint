"""Measure every numeric threshold in the rulebook against observed practice.

A craft book states an IDEAL a writer should aim at. A linter needs a DECISION
THRESHOLD that separates a defect from ordinary practice. Those are different
objects, and this script measures the distance between them: for each parameter
in `rulebook.yaml`, compute the same quantity the detector computes over a
corpus of produced screenplays, and report where the shipped value sits in that
distribution.

Three things keep the result honest.

**Containers never pool.** A corpus is named on the command line and its numbers
stay under that name. English-language produced screenplays and Telugu drafts
are different populations, and the page-a-minute convention every band rests on
is an English typesetting result. Merging them would produce a number that
describes neither.

**Extractors reuse the shipped code.** Every quantity below is computed by
calling the same helpers the detector calls (`_paragraphs`, `dialogue_blocks`,
`Script.character_registry`). `--verify` closes the loop: it runs the real
detector over a sample and checks that the number of elements the extractor puts
past the threshold equals the number of findings the detector produced. A
mismatch means the harness is measuring something other than what ships, which
is worse than not measuring it at all.

**Parameters are classified, and the unmeasurable ones are named.** A parameter
is one of: a DECISION threshold (measured here), a GATE that decides whether the
rule runs at all (reported as the share of the corpus it excludes), or
UNMEASURABLE from the document alone (a similarity cutoff needs labelled pairs;
a TV band needs a corpus of pilots). Silence about the third class would let a
partial table read as a complete one.

Usage:

    python benchmark/thresholds.py CORPUS --label english-produced \\
        --layout scriptbase --json out.json --genres --verify 25

`--layout scriptbase` reads `<corpus>/<title>/script.txt` alongside an optional
`imdb_meta.txt`. `--layout flat` reads `*.fountain`, `*.txt`, and `*.pdf` from
the directory. Neither corpus is redistributable, which is why this reads a
path rather than shipping data.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sluglint.lint import registry  # noqa: E402
from sluglint.lint.tier1_format import EMPHASIS_MARKUP, _paragraphs, dialogue_blocks  # noqa: E402
from sluglint.lint.tier1_style import BEAT_PARENTHETICAL  # noqa: E402
from sluglint.lint.tier2_story import VOICE_CUE  # noqa: E402
from sluglint.models import ElementType, Script  # noqa: E402
from sluglint.parser import parse_text, split_scene_number  # noqa: E402
from sluglint.rulebook import load_rulebook  # noqa: E402

# A file that parses to no scenes never became a screenplay, and one under 20
# pages is a fragment. Both are excluded and both are counted, the same
# three-state gate the PDF reader applies. See docs/research/03.
MIN_PAGES = 20

# The third state, and the one that was missing. A crawl whose scene headings
# were never recognised still parses: it comes back as one 111-page scene with
# everything before it, and it passes both checks above while poisoning every
# ratio with a page count in the denominator. The share of elements the parser
# could not place inside any scene says so directly, and says nothing about
# screenwriting, which is what keeps this gate from being circular with the
# thresholds it protects.
MAX_ORPHAN_SHARE = 0.20

SPOKEN_NUMERAL = re.compile(r"(?<![\w:/.-])(\d{1,3})(?![\w:/.-])")
YEAR = re.compile(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)")


# --------------------------------------------------------------------- corpus

@dataclass
class Doc:
    """One parsed screenplay plus whatever the corpus knows about the film."""
    title: str
    script: Script
    genres: list[str] = field(default_factory=list)
    year: int | None = None

    @property
    def pages(self) -> float:
        return self.script.estimated_pages


def _meta(path: Path) -> tuple[list[str], int | None]:
    genres: list[str] = []
    year: int | None = None
    if not path.exists():
        return genres, year
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        key, _, value = line.partition("\t")
        if key == "genre":
            genres.append(value.strip())
        elif key == "year" and value.strip().isdigit():
            year = int(value.strip())
    return genres, year


def load(root: Path, layout: str, limit: int | None) -> tuple[list[Doc], dict]:
    """Parse a corpus directory. Returns the documents that passed the gate."""
    if layout == "scriptbase":
        sources = [(d.name, d / "script.txt", d / "imdb_meta.txt")
                   for d in sorted(root.iterdir()) if (d / "script.txt").exists()]
    else:
        sources = [(p.stem, p, p.with_suffix(".meta"))
                   for p in sorted(root.iterdir())
                   if p.suffix.lower() in (".fountain", ".txt", ".pdf")]
    if limit:
        sources = sources[:limit]

    docs: list[Doc] = []
    gate = collections.Counter()
    seen: dict[str, str] = {}
    for title, script_path, meta_path in sources:
        try:
            if script_path.suffix.lower() == ".pdf":
                from sluglint.ingest.pdf import parse_pdf
                script, _ = parse_pdf(script_path)
            else:
                script = parse_text(script_path.read_text("utf-8", errors="ignore"),
                                    str(script_path))
        except Exception as exc:                                    # noqa: BLE001
            gate["unreadable"] += 1
            print(f"  refused {title[:40]}: {exc}", file=sys.stderr)
            continue
        if not script.scenes:
            gate["no scenes"] += 1
            continue
        if script.estimated_pages < MIN_PAGES:
            gate["under 20 pages"] += 1
            continue
        orphaned = sum(1 for el in script.elements if el.scene_index < 0)
        if orphaned / max(len(script.elements), 1) > MAX_ORPHAN_SHARE:
            gate["unsegmented"] += 1
            continue
        # The same draft filed twice would weight one film's habits double. A
        # small corpus is exactly where that matters, and exactly where a
        # duplicate is easiest to acquire by accident.
        digest = hashlib.sha256(script.raw_text.encode("utf-8", "ignore")).hexdigest()
        if digest in seen:
            gate["duplicate"] += 1
            print(f"  duplicate {title[:38]} == {seen[digest][:38]}", file=sys.stderr)
            continue
        seen[digest] = title
        genres, year = _meta(meta_path)
        docs.append(Doc(title=title, script=script, genres=genres, year=year))
        gate["read"] += 1
    return docs, dict(gate)


# ---------------------------------------------------------------- extractors
# Each returns one value per unit of measurement. An element measure returns
# many values per document and they pool across the corpus; a document measure
# returns exactly one. Every one calls the same helper the detector calls, so
# the two cannot drift apart without --verify saying so.
#
# Where a rule has more than one condition, the extractor applies all of them
# EXCEPT the parameter under test, and measures the distribution over what
# survives. Measuring the whole population instead would answer a question the
# rule never asks: C002 does not care where a one-scene walk-on was last seen.

def _els(d: Doc, *types: ElementType) -> list:
    return [el for el in d.script.elements if el.type in types]


def _counts(d: Doc) -> dict[str, int]:
    return d.script.dialogue_counts()


def action_paragraph_lines(d: Doc, _p: dict) -> list[float]:
    return [len(b) for b in _paragraphs(d.script, (ElementType.ACTION,))]


def dialogue_block_lines(d: Doc, _p: dict) -> list[float]:
    return [len([e for e in b[1:] if e.type is ElementType.DIALOGUE])
            for b in dialogue_blocks(d.script)]


def heading_chars(d: Doc, _p: dict) -> list[float]:
    """Heading length with the scene number off, which is what F013 measures."""
    return [len(split_scene_number(sc.heading)[0]) for sc in d.script.scenes]


def parenthetical_words(d: Doc, _p: dict) -> list[float]:
    return [len(el.text.strip("()").split())
            for el in _els(d, ElementType.PARENTHETICAL)]


def cue_words(d: Doc, _p: dict) -> list[float]:
    return [len(el.text.split()) for el in _els(d, ElementType.CHARACTER)]


def scene_pages(d: Doc, _p: dict) -> list[float]:
    return [sc.estimated_pages for sc in d.script.scenes]


def location_pages(d: Doc, _p: dict) -> list[float]:
    by_name: dict[str, float] = {}
    for sc in d.script.scenes:
        name = (sc.location or "").strip().upper()
        if name:
            by_name[name] = by_name.get(name, 0.0) + sc.estimated_pages
    return list(by_name.values())


def lone_speaker_scene_lines(d: Doc, _p: dict) -> list[float]:
    """Dialogue lines in scenes with one cued speaker and nobody answering."""
    out = []
    for sc in d.script.scenes:
        speakers = sc.characters
        if len(speakers) != 1 or VOICE_CUE.search(speakers[0]):
            continue
        if any(el.extension for el in sc.elements if el.type is ElementType.CHARACTER):
            continue
        out.append(sum(1 for el in sc.elements if el.type is ElementType.DIALOGUE))
    return out


def unstaged_scene_lines(d: Doc, _p: dict) -> list[float]:
    """Dialogue lines in scenes carrying no action line at all."""
    return [sum(1 for el in sc.elements if el.type is ElementType.DIALOGUE)
            for sc in d.script.scenes
            if not any(el.type is ElementType.ACTION for el in sc.elements)]


def single_scene_role_lines(d: Doc, _p: dict) -> list[float]:
    """Lines spoken by a character who appears in exactly one scene."""
    counts = _counts(d)
    return [counts.get(name, 0) for name, idxs in d.script.character_registry().items()
            if len(idxs) == 1]


def late_arrival_position(d: Doc, params: dict) -> list[float]:
    """Where a part big enough for the rule to care about first appears."""
    total = len(d.script.scenes) or 1
    floor = int(params.get("min_lines", 8))
    counts = _counts(d)
    return [min(idxs) / total for name, idxs in d.script.character_registry().items()
            if counts.get(name, 0) >= floor]


def last_seen_position(d: Doc, params: dict) -> list[float]:
    """Where a recurring speaking part is last seen, as a share of the script."""
    total = len(d.script.scenes) or 1
    floor = int(params.get("min_scenes", 3))
    return [(max(idxs) + 1) / total for idxs in d.script.character_registry().values()
            if len(idxs) >= floor]


def location_last_seen(d: Doc, params: dict) -> list[float]:
    """Where a recurring location is last used, as a share of the script.

    A set named later in dialogue is still in the story even when the camera
    never goes back, and the detector excludes those. So does this.
    """
    total = len(d.script.scenes) or 1
    floor = int(params.get("min_scenes", 3))
    by_name: dict[str, list[int]] = {}
    for sc in d.script.scenes:
        if sc.location:
            by_name.setdefault(sc.location.strip().upper(), []).append(sc.index)
    out = []
    for name, idxs in by_name.items():
        if len(idxs) < floor:
            continue
        last = max(idxs)
        later = " ".join(el.text for el in d.script.elements
                         if el.scene_index > last).upper()
        head = name.split(" - ")[0]
        if len(head) >= 4 and re.search(rf"\b{re.escape(head)}\b", later):
            continue
        out.append((last + 1) / total)
    return out


def montage_items(d: Doc, _p: dict) -> list[float]:
    """Beats listed under each montage header."""
    head = re.compile(r"\b(MONTAGE|SERIES OF SHOTS)\b")
    out = []
    for i, el in enumerate(d.script.elements):
        if el.type is not ElementType.ACTION or not head.search(el.text.upper()):
            continue
        if re.search(r"\bEND\b", el.text.upper()):
            continue
        items = 0
        for nxt in d.script.elements[i + 1:]:
            if nxt.type in (ElementType.SCENE_HEADING, ElementType.TRANSITION):
                break
            if nxt.type is ElementType.ACTION and nxt.text.strip():
                if head.search(nxt.text.upper()):
                    break
                items += 1
        out.append(items)
    return out


# ------------------------------------------------------------ document scale

def doc_pages(d: Doc, _p: dict | None = None) -> float:
    return d.pages


def scenes_per_page(d: Doc, _p: dict) -> float:
    return len(d.script.scenes) / max(d.pages, 1)


def dialogue_share_of_body(d: Doc, _p: dict) -> float:
    dial = len(_els(d, ElementType.DIALOGUE))
    act = len(_els(d, ElementType.ACTION))
    return dial / max(dial + act, 1)


def cast_per_page(d: Doc, _p: dict | None = None) -> float:
    return len(d.script.character_registry()) / max(d.pages, 1)


def locations_per_page(d: Doc, _p: dict) -> float:
    names = {(s.location or "").strip().upper() for s in d.script.scenes if s.location}
    return len(names) / max(d.pages, 1)


def night_share(d: Doc, _p: dict) -> float:
    timed = [s for s in d.script.scenes if s.time_of_day]
    night = [s for s in timed
             if s.time_of_day in {"NIGHT", "DUSK", "DAWN", "EVENING", "MIDNIGHT"}]
    return len(night) / len(timed) if timed else 0.0


def lead_dialogue_share(d: Doc, _p: dict) -> float:
    counts = _counts(d)
    total = sum(counts.values())
    return max(counts.values()) / total if total else 0.0


def company_move_ratio(d: Doc, _p: dict) -> float:
    ordered = [(s.location or "").strip().upper() for s in d.script.scenes]
    moves = sum(1 for a, b in zip(ordered, ordered[1:]) if a != b)
    return moves / max(len(ordered) - 1, 1)


def lead_absence_ratio(d: Doc, _p: dict) -> float:
    counts = _counts(d)
    if not counts:
        return 0.0
    lead = max(counts, key=counts.get)
    present = set(d.script.character_registry().get(lead, []))
    longest = run = 0
    for sc in d.script.scenes:
        run = 0 if sc.index in present else run + 1
        longest = max(longest, run)
    return longest / max(len(d.script.scenes), 1)


def transitions_per_10_scenes(d: Doc, _p: dict) -> float:
    n = sum(1 for el in _els(d, ElementType.TRANSITION) if el.text.endswith("TO:"))
    return n * 10 / max(len(d.script.scenes), 1)


def parentheticals_per_cue(d: Doc, _p: dict) -> float:
    cues = len(_els(d, ElementType.CHARACTER))
    return len(_els(d, ElementType.PARENTHETICAL)) / cues if cues else 0.0


def caps_action_share(d: Doc, _p: dict) -> float:
    action = _els(d, ElementType.ACTION)
    if not action:
        return 0.0
    shouted = [el for el in action if len(el.text.split()) >= 5
               and el.text == el.text.upper() and re.search(r"[A-Z]", el.text)]
    return len(shouted) / len(action)


def exclamations_per_page(d: Doc, _p: dict) -> float:
    body = _els(d, ElementType.ACTION, ElementType.DIALOGUE)
    return sum(el.text.count("!") for el in body) / max(d.pages, 1)


def ellipsis_dialogue_share(d: Doc, _p: dict) -> float:
    lines = _els(d, ElementType.DIALOGUE)
    if not lines:
        return 0.0
    hits = [el for el in lines if "..." in el.text or "\u2026" in el.text]
    return len(hits) / len(lines)


def emphasis_markup_count(d: Doc, _p: dict) -> float:
    return float(sum(1 for el in _els(d, ElementType.ACTION) if EMPHASIS_MARKUP.search(el.text)))


def caps_dialogue_count(d: Doc, params: dict) -> float:
    limit = int(params.get("min_words", 3))
    return float(sum(1 for el in _els(d, ElementType.DIALOGUE)
                     if any(c.isalpha() for c in el.text)
                     and el.text == el.text.upper()
                     and len(el.text.split()) >= limit))


def caps_dialogue_per_page(d: Doc, params: dict) -> float:
    return caps_dialogue_count(d, params) / max(d.pages, 1)


def numeral_dialogue_count(d: Doc, _p: dict | None = None) -> float:
    return float(sum(1 for el in _els(d, ElementType.DIALOGUE)
                     if SPOKEN_NUMERAL.search(YEAR.sub(" ", el.text))))


def numerals_per_page(d: Doc, _p: dict) -> float:
    return numeral_dialogue_count(d) / max(d.pages, 1)


def beat_count(d: Doc, _p: dict | None = None) -> float:
    return float(sum(1 for el in _els(d, ElementType.PARENTHETICAL)
                     if BEAT_PARENTHETICAL.match(el.text.strip())))


def beats_per_page(d: Doc, _p: dict) -> float:
    return beat_count(d) / max(d.pages, 1)


def longest_blank_run(d: Doc, _p: dict) -> float:
    """The rule reports the worst run once, so the document is the unit."""
    worst = run = 0
    for line in d.script.raw_text.splitlines():
        run = 0 if line.strip() else run + 1
        worst = max(worst, run)
    return float(worst)


def numbered_heading_share(d: Doc, _p: dict) -> float:
    numbered = sum(1 for sc in d.script.scenes if sc.number is not None)
    return numbered / max(len(d.script.scenes), 1)


def opening_window_cast(d: Doc, params: dict) -> float:
    total = len(d.script.scenes)
    window = max(1, round(total * float(params.get("opening_share", 0.1))))
    return float(sum(1 for idxs in d.script.character_registry().values()
                     if min(idxs) < window))


def act_length_ratio(d: Doc, _p: dict) -> float | None:
    acts: dict[str, int] = {}
    for sc in d.script.scenes:
        if sc.act:
            acts[sc.act] = acts.get(sc.act, 0) + len([e for e in sc.elements if e.text.strip()])
    if len(acts) < 2 or not min(acts.values()):
        return None
    return max(acts.values()) / min(acts.values())


# ------------------------------------------------------------------ the table

@dataclass(frozen=True)
class Measure:
    """One quantity a rule decides on, and which side of the value fires.

    `fires` matters more than it looks. The rulebook writes some bounds as a
    ceiling the document should stay under (F004 max_lines), some as a floor
    the element should reach before the rule cares (C030 min_lines), and some
    as a position the rule wants something to happen before (C002
    last_seen_before). Reading all three as "max" produced verdicts that were
    backwards, which is what `--verify` is for.
    """
    rule: str
    quantity: str
    unit: str                              # what one value describes
    extract: Callable[[Doc, dict], object]
    fires: str                             # above | atleast | below | outside
    bound: str | None = None            # param name, for a one-sided rule
    lo: str | None = None               # param names, for a band
    hi: str | None = None
    hidden: str = ""                       # conditions the rulebook does not state

    @property
    def per_document(self) -> bool:
        return self.unit == "document"

    def fired(self, value: float, params: dict) -> bool:
        if self.fires == "outside":
            return (value < float(params[self.lo])) or (value > float(params[self.hi]))
        cut = float(params[self.bound])
        if self.fires == "above":
            return value > cut
        if self.fires == "atleast":
            return value >= cut
        return value < cut


MEASURES: list[Measure] = [
    # ---- element scale: the threshold decides about one written element
    Measure("F004", "printed lines per action paragraph", "action paragraph",
            action_paragraph_lines, "above", bound="max_lines"),
    Measure("F016", "printed lines per unbroken speech", "dialogue block",
            dialogue_block_lines, "above", bound="max_lines"),
    Measure("F013", "characters per scene heading", "scene heading",
            heading_chars, "above", bound="max_chars"),
    Measure("F017", "words per parenthetical", "parenthetical",
            parenthetical_words, "above", bound="max_words"),
    Measure("F064", "words per character cue", "character cue",
            cue_words, "above", bound="max_words"),
    Measure("F059", "beats listed under a montage header", "montage",
            montage_items, "below", bound="min_items"),
    Measure("F048", "dialogue lines in a scene with no action line", "unstaged scene",
            unstaged_scene_lines, "atleast", bound="min_lines"),
    Measure("C023", "pages per scene", "scene", scene_pages, "above",
            bound="max_pages"),
    Measure("C029", "pages carried by one location", "location",
            location_pages, "below", bound="max_pages",
            hidden="fires only when such locations are more than a third of all "
                   "locations, a ratio the rulebook does not carry"),
    Measure("C030", "lines spoken by a character who appears in one scene",
            "one-scene part", single_scene_role_lines, "atleast", bound="min_lines"),
    Measure("C040", "dialogue lines in a scene with a single cued speaker",
            "lone-speaker scene", lone_speaker_scene_lines, "atleast",
            bound="min_lines"),
    Measure("C002", "where a recurring speaking part is last seen",
            "recurring part", last_seen_position, "below", bound="last_seen_before"),
    Measure("C034", "where a recurring location is last used", "recurring location",
            location_last_seen, "below", bound="last_seen_before"),
    Measure("C039", "where a substantial speaking part first appears",
            "substantial part", late_arrival_position, "atleast", bound="after"),

    # ---- document scale: the threshold decides about the whole script
    Measure("F008", "pages", "document", doc_pages, "outside",
            lo="min_pages", hi="max_pages"),
    Measure("F037", "scenes per page", "document", scenes_per_page, "outside",
            lo="min_per_page", hi="max_per_page"),
    Measure("F036", "dialogue share of body text", "document",
            dialogue_share_of_body, "outside", lo="min_ratio", hi="max_ratio"),
    Measure("F006", "transitions per 10 scenes", "document",
            transitions_per_10_scenes, "above", bound="max_per_10_scenes",
            hidden="a floor of 2 transitions, written as a literal in the detector"),
    Measure("F007", "parentheticals per dialogue block", "document",
            parentheticals_per_cue, "above", bound="max_ratio"),
    Measure("F032", "share of action lines fully capitalised", "document",
            caps_action_share, "above", bound="max_ratio"),
    Measure("F033", "exclamation marks per page", "document",
            exclamations_per_page, "above", bound="max_per_page"),
    Measure("F034", "share of dialogue lines with an ellipsis", "document",
            ellipsis_dialogue_share, "above", bound="max_ratio"),
    Measure("F038", "action lines carrying emphasis markup", "document",
            emphasis_markup_count, "above", bound="max_count"),
    Measure("F042", "longest act over shortest act", "document",
            act_length_ratio, "above", bound="max_ratio"),
    Measure("F009", "share of headings carrying a scene number", "document",
            numbered_heading_share, "atleast", bound="profile_mismatch_share",
            hidden="below the share the rule still fires, with a different message"),
    Measure("F049", "speeches set in capitals, per page", "document",
            caps_dialogue_per_page, "above", bound="max_per_page"),
    Measure("F050", "speeches with a bare numeral, per page", "document",
            numerals_per_page, "above", bound="max_per_page"),
    Measure("F052", "(beat) parentheticals per page", "document",
            beats_per_page, "above", bound="max_per_page"),
    Measure("F060", "longest run of blank lines", "document",
            longest_blank_run, "above", bound="max_blank"),
    Measure("C020", "speaking parts per page", "document", cast_per_page,
            "above", bound="max_speaking_per_page"),
    Measure("C021", "distinct locations per page", "document", locations_per_page,
            "above", bound="max_per_page"),
    Measure("C022", "share of timed scenes at night", "document", night_share,
            "above", bound="max_ratio"),
    Measure("C024", "longest lead absence, as a share of scenes", "document",
            lead_absence_ratio, "above", bound="max_gap_ratio"),
    Measure("C025", "share of dialogue spoken by the lead", "document",
            lead_dialogue_share, "above", bound="max_share"),
    Measure("C028", "share of cuts that change location", "document",
            company_move_ratio, "above", bound="max_ratio"),
    Measure("C038", "speaking parts arriving in the first tenth", "document",
            opening_window_cast, "above", bound="max_cast"),
]

# Parameters that decide whether a rule RUNS rather than what it flags. A gate
# is not miscalibrated in the same sense: it is either doing its job or it is
# silencing the rule. What matters is the share of the corpus it excludes.
GATES: dict[str, list[tuple[str, Callable[[Doc], float]]]] = {
    "F007": [("min_cues", lambda d: len(_els(d, ElementType.CHARACTER)))],
    "F029": [("min_pages", doc_pages)],
    "F030": [("min_pages", doc_pages)],
    "F032": [("min_action_lines", lambda d: len(_els(d, ElementType.ACTION)))],
    "F033": [("min_pages", doc_pages)],
    "F034": [("min_lines", lambda d: len(_els(d, ElementType.DIALOGUE)))],
    "F036": [("min_lines", lambda d: len(_els(d, ElementType.ACTION,
                                              ElementType.DIALOGUE)))],
    "F037": [("min_pages", doc_pages)],
    "F047": [("min_scenes", lambda d: len(d.script.scenes))],
    "F049": [("min_count", lambda d: caps_dialogue_count(d, {}))],
    "F050": [("min_count", numeral_dialogue_count)],
    "F052": [("min_count", beat_count)],
    "F056": [("min_pages", doc_pages)],
    "C020": [("min_pages", doc_pages)],
    "C021": [("min_pages", doc_pages)],
    "C022": [("min_scenes", lambda d: sum(1 for s in d.script.scenes if s.time_of_day))],
    "C024": [("min_scenes", lambda d: len(d.script.scenes))],
    "C025": [("min_speakers", lambda d: len(_counts(d))),
             ("min_lines", lambda d: sum(_counts(d).values()))],
    "C028": [("min_scenes", lambda d: len(d.script.scenes))],
    "C029": [("min_locations", lambda d: len(location_pages(d, {})))],
    "C032": [("min_cast", lambda d: len(d.script.character_registry()))],
    "C033": [("min_cast", lambda d: len(d.script.character_registry()))],
    "C035": [("min_scenes", lambda d: len(d.script.scenes))],
    "C036": [("top", lambda d: len(_counts(d)))],
    "C038": [("min_scenes", lambda d: len(d.script.scenes))],
}

# Named so a partial table cannot read as a complete one.
UNMEASURABLE: dict[str, str] = {
    "C001": "similarity_threshold needs labelled name-drift pairs, not a corpus",
    "C005": "similarity_threshold needs labelled location-drift pairs",
    "C012": "similarity_threshold needs labelled name-drift pairs",
    "F029": "`required` lists title-page fields; it is not a numeric threshold",
    "F043": "pilot page bands need a corpus of TV pilots; none is in hand",
    "F045": "interval placement is an Indian-format convention. Measure it on "
            "the Telugu container, never on English features",
    "C027": "late series regular is a TV rule and needs a pilot corpus",
    "C026": "min_length bounds a prop NAME. The population is every capitalised "
            "noun, which is not a distribution the rule reasons about",
    "C037": "min_lines applies only to role-cued parts, and which cues are roles "
            "is a lexicon decision rather than a threshold",
    "F054": "min_count and min_lines gate a document-scale habit whose population "
            "is the characters a script chose to capitalise",
    "F070": "min_count gates a PDF round-trip artifact, not a writing choice",
    "C033": "min_group is a graph-shape parameter with no distribution over "
            "documents",
    "F047": "min_eighths is measured, but the rule fires on the SHARE of scenes "
            "under it, and that share is a literal in the detector",
}


# --------------------------------------------------------------------- stats

def q(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * p), len(ordered) - 1)]


def verdict(fires_pct: float) -> str:
    """Read the firing rate as a decision about a linter.

    Above 10% the rule is flagging ordinary practice, which is the failure that
    makes a writer switch the tool off. Below 0.1% it effectively never fires
    and the threshold is doing no work. In between it is separating a tail from
    a population, which is what a decision threshold is for.
    """
    if fires_pct > 10:
        return "too strict"
    if fires_pct < 0.1:
        return "too loose"
    return "holds"


def gated_off(d: Doc, rule) -> bool:
    """Would this rule decline to run on this document?

    A rule silenced by its own gate has not disagreed with anything, and has
    not flagged anything either. Counting those documents in either place
    would understate how often the rule speaks to the writer it does reach.
    """
    for param, extract in GATES.get(rule.id, []):
        if param in rule.params and extract(d) < float(rule.params[param]):
            return True
    return False


def measure_one(m: Measure, docs: list[Doc], rule) -> dict | None:
    """The distribution of one quantity, and the share the shipped value flags.

    Gated-off documents are dropped first. A rule that never runs on three
    quarters of the corpus is not flagging 2% of screenplays, it is flagging
    11% of the ones it looks at, and only the second number describes what a
    writer experiences.
    """
    params = rule.params
    before = len(docs)
    docs = [d for d in docs if not gated_off(d, rule)]
    gated = before - len(docs)
    if not docs:
        return None
    if m.per_document:
        values = [v for v in (m.extract(d, params) for d in docs) if v is not None]
    else:
        values = [v for d in docs for v in m.extract(d, params)]
    if not values:
        return None
    needed = [m.lo, m.hi] if m.fires == "outside" else [m.bound]
    if any(k not in params for k in needed):
        return None
    fires = sum(1 for v in values if m.fired(v, params))
    row = {
        "rule": m.rule, "quantity": m.quantity, "unit": m.unit,
        "fires": m.fires, "hidden": m.hidden,
        "n": len(values), "documents": len(docs),
        "gated_out": gated,
        "p05": round(q(values, .05), 3), "p50": round(q(values, .50), 3),
        "p90": round(q(values, .90), 3), "p95": round(q(values, .95), 3),
        "p99": round(q(values, .99), 3),
        "max": round(max(values), 3), "mean": round(statistics.fmean(values), 3),
        "fires_pct": round(100 * fires / len(values), 1),
    }
    if m.fires == "outside":
        lo, hi = float(params[m.lo]), float(params[m.hi])
        row["lo"], row["hi"] = lo, hi
        row["below_pct"] = round(100 * sum(1 for v in values if v < lo) / len(values), 1)
        row["above_pct"] = round(100 * sum(1 for v in values if v > hi) / len(values), 1)
        row["verdict"] = ("holds" if row["fires_pct"] <= 10
                          else "loose fit" if row["fires_pct"] <= 40 else "band is wrong")
    else:
        row["ships_at"] = float(params[m.bound])
        row["verdict"] = verdict(row["fires_pct"])
    return row


def measure_gates(docs: list[Doc], book) -> list[dict]:
    """What share of the corpus each activation gate silences."""
    by_id = {r.id: r for r in book.rules}
    out = []
    for rule_id, entries in sorted(GATES.items()):
        rule = by_id.get(rule_id)
        if rule is None:
            continue
        for param, extract in entries:
            if param not in rule.params:
                continue
            floor = float(rule.params[param])
            values = [extract(d) for d in docs]
            below = sum(1 for v in values if v < floor)
            out.append({
                "rule": rule_id, "param": param, "value": floor,
                "quantity_p50": round(q(values, .50), 2),
                "excluded": below, "documents": len(values),
                "excluded_pct": round(100 * below / len(values), 1) if values else 0.0,
            })
    return out


# --------------------------------------------------------------- verification

def verify(docs: list[Doc], book, sample: int) -> list[dict]:
    """Does the extractor count what the shipped detector reports?

    For an element-scale rule the two must agree exactly: the number of values
    on the firing side IS the number of findings. Where they disagree the
    harness is measuring something the linter does not, and the row it produced
    is not evidence about screenwriting. Document-scale rules are checked as a
    yes/no, because they report once for the document either way.

    Disagreement is reported rather than repaired, because the usual cause is a
    condition the detector carries as a literal and the rulebook does not carry
    at all. That gap is a finding about the rulebook.
    """
    by_id = {r.id: r for r in book.rules}
    picked = docs[:sample]
    out = []
    for m in MEASURES:
        rule = by_id.get(m.rule)
        handler = registry._REGISTRY.get(rule.detect) if rule else None   # noqa: SLF001
        if handler is None:
            continue
        agree = disagree = skipped = 0
        example = ""
        for d in picked:
            if gated_off(d, rule):
                skipped += 1
                continue
            found = len(list(handler(d.script, rule)))
            if m.per_document:
                value = m.extract(d, rule.params)
                if value is None:
                    continue
                ok = bool(found) == m.fired(value, rule.params)
                detail = f"expected {'a finding' if not found else 'silence'}"
            else:
                values = m.extract(d, rule.params)
                expected = sum(1 for v in values if m.fired(v, rule.params))
                ok = expected == found
                detail = f"extractor {expected}, detector {found}"
            agree += ok
            disagree += not ok
            if not ok and not example:
                example = f"{d.title[:28]}: {detail}"
        out.append({"rule": m.rule, "scale": m.unit, "agree": agree,
                    "disagree": disagree, "gated_out": skipped,
                    "example": example, "hidden": m.hidden})
    return out


# -------------------------------------------------------------------- report

FIRES = {"above": "fires above", "atleast": "fires at or above",
         "below": "fires below", "outside": "fires outside"}


# ---------------------------------------------------------- corpus integrity

def integrity(docs: list[Doc]) -> dict:
    """Is the corpus parsed well enough for its numbers to mean anything?

    Every threshold below is a ratio whose denominator is a page count, and a
    page count is derived from a wrap decision. Three passes of this table were
    published-looking and wrong because that chain broke silently, so the chain
    is now reported next to the results rather than assumed.

    Four things are checked. Whether each document's own line breaks were
    recognised, and how close it sits to the boundary where that decision
    flips. Whether the per-scene pages still sum to the document, which is what
    caught the scene-level wrap bug. Whether the parser placed the text inside
    scenes rather than orphaning it before the first heading. And where the
    page count came from, because a real one from a PDF beats every estimate.
    """
    wrapped = sum(1 for d in docs if d.script.prewrapped)
    real_pages = sum(1 for d in docs if d.script.page_count)
    ratios, drifts, orphans = [], [], []
    for d in docs:
        lengths = sorted(len(el.text.strip()) for el in d.script.elements
                         if el.type is ElementType.ACTION and el.text.strip())
        if len(lengths) >= 40:
            mid = lengths[len(lengths) // 2]
            if mid:
                ratios.append(lengths[int(len(lengths) * 0.99)] / mid)
        loose = sum(sc.estimated_pages for sc in d.script.scenes)
        if d.pages:
            drifts.append(abs(loose - d.pages) / d.pages * 100)
        total = len(d.script.elements) or 1
        orphans.append(100 * sum(1 for el in d.script.elements
                                 if el.scene_index < 0) / total)
    return {
        "documents": len(docs),
        "prewrapped": wrapped, "paragraph_source": len(docs) - wrapped,
        "wrap_ratio_p50": round(q(ratios, .50), 2) if ratios else 0.0,
        "wrap_ratio_p95": round(q(ratios, .95), 2) if ratios else 0.0,
        # How many documents sit within 15% of the 1.6 cut, where a small
        # change in the corpus would flip the decision and every page with it.
        "near_the_wrap_cut": sum(1 for r in ratios if 1.36 <= r <= 1.84),
        "page_drift_p50": round(q(drifts, .50), 2) if drifts else 0.0,
        "page_drift_p95": round(q(drifts, .95), 2) if drifts else 0.0,
        "page_drift_max": round(max(drifts), 2) if drifts else 0.0,
        "orphan_p50": round(q(orphans, .50), 2) if orphans else 0.0,
        "orphan_p95": round(q(orphans, .95), 2) if orphans else 0.0,
        "real_page_counts": real_pages,
    }


# --------------------------------------------------- the rules-are-data audit

DETECTOR_MODULES = ("tier1_format", "tier1_metrics", "tier1_style",
                    "tier2_consistency", "tier2_production", "tier2_story")
# 0 and 1 appear in every emptiness test and every off-by-one. They are not
# thresholds and counting them would drown the ones that are.
BORING = {0, 1, -1}


def _params_default(node: ast.AST) -> set[int]:
    """Line-and-col of every literal that is a `rule.params.get` default.

    Those restate the rulebook's own value, so they are duplication rather than
    a hidden decision, and they move when the rulebook moves.
    """
    out: set[tuple[int, int]] = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            continue
        if call.func.attr != "get":
            continue
        for arg in call.args[1:]:
            for lit in ast.walk(arg):
                if isinstance(lit, ast.Constant):
                    out.add((lit.lineno, lit.col_offset))
    return out


def audit_literals() -> list[dict]:
    """Numbers a detector decides on that the rulebook cannot reach.

    Hard rule 2 of this project says rules are data: a threshold lives in the
    rulebook and the handler reads it from `rule.params`. This walks each
    detector's syntax tree and reports every numeric constant used in a
    comparison or an arithmetic scaling, minus the ones that are just a
    `params.get` default. Each survivor is a decision no rulebook edit can
    change, and `--verify` shows what it costs: three of the disagreements
    between this harness and the shipped detectors are exactly these.
    """
    root = Path(__file__).resolve().parent.parent / "src" / "sluglint" / "lint"
    out = []
    for name in DETECTOR_MODULES:
        tree = ast.parse((root / f"{name}.py").read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not any(isinstance(dec, ast.Call)
                       and getattr(dec.func, "id", "") == "detector"
                       for dec in fn.decorator_list):
                continue
            skip = _params_default(fn)
            for node in ast.walk(fn):
                operands: list[ast.AST] = []
                if isinstance(node, ast.Compare):
                    operands = [node.left, *node.comparators]
                elif isinstance(node, ast.BinOp) and isinstance(
                        node.op, (ast.Div, ast.Mult)):
                    operands = [node.left, node.right]
                for operand in operands:
                    if not isinstance(operand, ast.Constant):
                        continue
                    if not isinstance(operand.value, (int, float)):
                        continue
                    if operand.value in BORING:
                        continue
                    if (operand.lineno, operand.col_offset) in skip:
                        continue
                    out.append({"module": name, "detector": fn.name,
                                "line": operand.lineno, "value": operand.value})
    return out


def render(label: str, docs: list[Doc], gate: dict, health: dict,
           rows: list[dict], gates: list[dict], checks: list[dict],
           genres: dict | None, drafts: dict | None) -> str:
    lines: list[str] = []
    add = lines.append
    scenes = sum(len(d.script.scenes) for d in docs)
    paras = sum(len(action_paragraph_lines(d, {})) for d in docs)
    years = sorted(d.year for d in docs if d.year)

    add(f"# Thresholds against practice: {label}\n")
    add(f"**{len(docs)} documents, {scenes:,} scenes, {paras:,} action paragraphs.**")
    if years:
        add(f"Years {years[0]} to {years[-1]}, median {years[len(years) // 2]}.")
    add("")
    add("Gate: " + ", ".join(f"{v} {k}" for k, v in sorted(gate.items())) + ".")
    add("")
    add("## Corpus integrity\n")
    add("Every number below is a ratio over a page count, and a page count comes")
    add("from a wrap decision. That chain broke silently three times, so it is")
    add("reported next to the results rather than assumed.\n")
    add("| Check | Value |")
    add("|---|---:|")
    add(f"| Documents measured | {health['documents']} |")
    add(f"| Sources that broke their own lines | {health['prewrapped']} |")
    add(f"| Sources holding whole paragraphs | {health['paragraph_source']} |")
    add(f"| Wrap ratio p99/p50, median | {health['wrap_ratio_p50']:g} |")
    add(f"| Wrap ratio p99/p50, p95 | {health['wrap_ratio_p95']:g} |")
    add(f"| Documents within 15% of the 1.6 wrap cut | "
        f"{health['near_the_wrap_cut']} |")
    add(f"| Scene pages vs document pages, median drift | "
        f"{health['page_drift_p50']:g}% |")
    add(f"| Scene pages vs document pages, p95 drift | "
        f"{health['page_drift_p95']:g}% |")
    add(f"| Scene pages vs document pages, worst drift | "
        f"{health['page_drift_max']:g}% |")
    add(f"| Elements orphaned before the first heading, median | "
        f"{health['orphan_p50']:g}% |")
    add(f"| Elements orphaned before the first heading, p95 | "
        f"{health['orphan_p95']:g}% |")
    add(f"| Documents whose page count is stated by the source | "
        f"{health['real_page_counts']} |")
    add("")
    add("`Flags` is the share of the population the shipped value reports. A")
    add("threshold flagging more than one unit in ten is describing ordinary")
    add("practice rather than a tail.")
    add("")

    add("## Element-scale thresholds\n")
    add("| Rule | Quantity | Ships at | Direction | Flags | p50 | p90 | p95 | p99 | Max | Verdict |")
    add("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        if r["unit"] == "document":
            continue
        add(f"| {r['rule']} | {r['quantity']} | {r['ships_at']:g} | "
            f"{FIRES[r['fires']]} | {r['fires_pct']}% | {r['p50']:g} | {r['p90']:g} | "
            f"{r['p95']:g} | {r['p99']:g} | {r['max']:g} | {r['verdict']} |")
    add("")
    add("Units: " + ", ".join(f"{r['n']:,} {r['unit']}s" for r in rows
                               if r["unit"] != "document"))

    add("\n## Document-scale thresholds\n")
    add("| Rule | Quantity | Band | Direction | Flags | p05 | p50 | p95 | Verdict |")
    add("|---|---|---|---|---:|---:|---:|---:|---|")
    for r in rows:
        if r["unit"] != "document":
            continue
        band = (f"{r['lo']:g} to {r['hi']:g}" if r["fires"] == "outside"
                else f"{r['ships_at']:g}")
        add(f"| {r['rule']} | {r['quantity']} | {band} | {FIRES[r['fires']]} | "
            f"{r['fires_pct']}% | {r['p05']:g} | {r['p50']:g} | {r['p95']:g} | "
            f"{r['verdict']} |")

    add("\n## Activation gates\n")
    add("A gate decides whether the rule runs at all. What matters is the share")
    add("of the corpus it silences.\n")
    add("| Rule | Gate | Set at | Corpus median | Documents excluded |")
    add("|---|---|---:|---:|---:|")
    for g in gates:
        add(f"| {g['rule']} | {g['param']} | {g['value']:g} | {g['quantity_p50']:g} | "
            f"{g['excluded']} of {g['documents']} ({g['excluded_pct']:.0f}%) |")

    add("\n## Extractor agreement with the shipped detector\n")
    bad = [c for c in checks if c["disagree"]]
    add(f"{len(checks) - len(bad)} of {len(checks)} extractors agree with their")
    add("detector on every sampled document. Where they disagree the cause is")
    add("named, because a condition the detector carries and the rulebook does")
    add("not is a defect in the claim that rules are data.\n")
    if bad:
        add("| Rule | Agree | Disagree | Example | Condition not in the rulebook |")
        add("|---|---:|---:|---|---|")
        for c in bad:
            add(f"| {c['rule']} | {c['agree']} | {c['disagree']} | {c['example']} | "
                f"{c['hidden'] or 'unexplained'} |")

    for title, note, split in (
            ("Genre split", "each genre", genres),
            ("Draft-stage split",
             "each draft stage, taken from whether the headings are numbered",
             drafts)):
        if not split:
            continue
        add(f"\n## {title}\n")
        add(f"Share of the population each threshold flags, inside {note}.\n")
        add("| Rule | Quantity | " + " | ".join(split["order"]) + " | All |")
        add("|---|---|" + "---:|" * (len(split["order"]) + 1))
        for rule_id, quantity, cells, overall in split["rows"]:
            add(f"| {rule_id} | {quantity} | " + " | ".join(cells) + f" | {overall} |")
        add("")
        add("| Group | Documents |")
        add("|---|---:|")
        for name in split["order"]:
            add(f"| {name} | {split['counts'][name]} |")

    add("\n## Thresholds the rulebook does not carry\n")
    literals = audit_literals()
    add(f"{len(literals)} numeric literals sit inside detector code rather than in")
    add("`rulebook.yaml`. Each is a decision no rulebook edit can reach.\n")
    if literals:
        add("| Rule handler | Module | Line | Value |")
        add("|---|---|---:|---:|")
        for lit in literals:
            add(f"| `{lit['detector']}` | {lit['module']} | {lit['line']} | "
                f"{lit['value']:g} |")

    add("\n## Parameters this corpus cannot measure\n")
    add("| Rule | Why |")
    add("|---|---|")
    for rule_id, why in sorted(UNMEASURABLE.items()):
        add(f"| {rule_id} | {why} |")
    return "\n".join(lines)


def split_by(docs: list[Doc], book, groups: list[tuple[str, list[Doc]]],
             floor: int = 40) -> dict | None:
    """The same measures, computed inside each subset.

    A threshold that fails overall may hold inside a subset, and if it does the
    fix is a subset-aware default rather than one number. Groups under `floor`
    documents are dropped rather than reported thin: a rate from thirty
    documents does not belong in a table next to one from five hundred.
    """
    kept = [(name, subset) for name, subset in groups if len(subset) >= floor]
    if not kept:
        return None
    by_id = {r.id: r for r in book.rules}
    rows = []
    for m in MEASURES:
        rule = by_id.get(m.rule)
        if rule is None:
            continue
        overall = measure_one(m, docs, rule)
        if overall is None:
            continue
        cells = []
        for _, subset in kept:
            r = measure_one(m, subset, rule)
            cells.append(f"{r['fires_pct']}%" if r else "-")
        rows.append((m.rule, m.quantity, cells, f"{overall['fires_pct']}%"))
    return {"order": [name for name, _ in kept],
            "counts": {name: len(subset) for name, subset in kept},
            "rows": rows}


def draft_split(docs: list[Doc], book) -> dict | None:
    """Production drafts against spec-style drafts.

    ScriptBase does not label draft stage, and F008's page band was written for
    a spec. Scene numbering is the usable proxy: a draft that numbers most of
    its headings has been locked for a shoot, and shooting scripts run longer
    than the specs they came from. This is the split that decides whether
    F008's failure is a fact about screenwriting or about the corpus.
    """
    numbered, plain = [], []
    for d in docs:
        share = sum(1 for sc in d.script.scenes if sc.number is not None)
        (numbered if share / max(len(d.script.scenes), 1) >= 0.6 else plain).append(d)
    return split_by(docs, book, [("production draft", numbered),
                                 ("spec-style draft", plain)])


def genre_split(docs: list[Doc], book, top: int) -> dict | None:
    """The measures again, inside each of the corpus's largest genres."""
    counts = collections.Counter(g for d in docs for g in set(d.genres))
    groups = [(name, [d for d in docs if name in d.genres])
              for name, _ in counts.most_common(top)]
    return split_by(docs, book, groups)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--label", required=True,
                    help="container name; results are never pooled across labels")
    ap.add_argument("--layout", choices=("scriptbase", "flat"), default="scriptbase")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--verify", type=int, default=25,
                    help="documents to check extractor against detector on")
    ap.add_argument("--genres", action="store_true")
    ap.add_argument("--drafts", action="store_true",
                    help="split by scene numbering, a draft-stage proxy")
    ap.add_argument("--genre-top", type=int, default=6)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None, help="write the markdown report")
    args = ap.parse_args()

    book = load_rulebook()
    docs, gate = load(args.corpus, args.layout, args.limit)
    if not docs:
        print("no documents passed the gate", file=sys.stderr)
        return 1
    print(f"{args.label}: {len(docs)} documents read, "
          + ", ".join(f"{v} {k}" for k, v in sorted(gate.items())), file=sys.stderr)

    by_id = {r.id: r for r in book.rules}
    rows = []
    for m in MEASURES:
        rule = by_id.get(m.rule)
        if rule is None:
            continue
        row = measure_one(m, docs, rule)
        if row:
            rows.append(row)

    gates = measure_gates(docs, book)
    checks = verify(docs, book, args.verify) if args.verify else []
    genres = genre_split(docs, book, args.genre_top) if args.genres else None
    drafts = draft_split(docs, book) if args.drafts else None

    health = integrity(docs)
    report = render(args.label, docs, gate, health, rows, gates, checks,
                    genres, drafts)
    if args.out:
        args.out.write_text(report + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(report)
    if args.json:
        args.json.write_text(json.dumps({
            "label": args.label, "documents": len(docs), "gate": gate,
            "integrity": health, "measures": rows,
            "genre_split": genres, "draft_split": drafts, "gates": gates, "verification": checks,
            "unmeasurable": UNMEASURABLE,
        }, indent=2))
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
