"""Fountain-lite parser.

Parses plain-text screenplays (Fountain conventions) into a structured
Script. Intentionally forgiving: malformed input still parses, because the
lint tiers are what report the problems. A parse failure on bad formatting
would hide the very defects Sluglint exists to report.

v1 replaces this with PDF/FDX ingestion feeding the same models.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import Element, ElementType, Scene, Script

HEADING_RE = re.compile(r"^(INT\.?/EXT|I/E|INT|EXT|EST)[.\s]", re.IGNORECASE)
TRANSITION_RE = re.compile(
    r"^(?:[A-Z][A-Z ']*TO:|FADE (?:IN:|OUT\.?|TO BLACK\.?)|SMASH CUT\.?|CUT TO BLACK\.?)$"
)
EXTENSION_RE = re.compile(
    r"\s*\((V\.?O\.?|O\.?S\.?|O\.?C\.?|CONT'?D|VOICE ?OVER|OFF ?SCREEN|OFF|PRE-?LAP|"
    r"FILTERED|SUBTITLED|INTO PHONE|ON PHONE)\)\s*",
    re.IGNORECASE,
)
# Scene numbers on a shooting-script slugline: leading '14', trailing '14A'.
LEADING_NUMBER_RE = re.compile(r"^(\d{1,4}[A-Z]{0,2})[.)]?\s+(?=INT|EXT|I/E|EST)", re.IGNORECASE)
TRAILING_NUMBER_RE = re.compile(r"\s+(\d{1,4}[A-Z]{0,2})\s*$")
# Act / structural markers. Must be a standalone uppercase line to qualify.
SECTION_RE = re.compile(
    r"^(COLD OPEN|TEASER|TAG|MAIN TITLES?|END OF (?:COLD OPEN|TEASER|TAG|SHOW|ACT [A-Z0-9]+)|"
    r"ACT (?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|\d+)|"
    r"INTERVAL|INTERMISSION|SONG(?: SEQUENCE)?\s*[:\-].*|SONG SEQUENCE)\s*[.:]?$"
)
CENTERED_RE = re.compile(r"^>\s*(.+?)\s*<$")
INDIC_SCRIPT = re.compile(r"[ऀ-෿]")  # Devanagari .. Sinhala
TITLE_PAGE_KEYS = {
    "title", "credit", "author", "authors", "written by", "draft date", "date",
    "contact", "source", "copyright", "notes", "revision",
}
TIMES_OF_DAY = {
    "DAY", "NIGHT", "MORNING", "AFTERNOON", "EVENING", "DAWN", "DUSK",
    "SUNRISE", "SUNSET", "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME TIME", "SAME",
}


def normalize_character(raw: str) -> str:
    """'JOHN (V.O.) (CONT'D)' -> 'JOHN'."""
    name = EXTENSION_RE.sub(" ", raw)
    name = re.sub(r"\s+", " ", name).strip()
    return name.rstrip("^").strip()  # ^ = fountain dual-dialogue marker


def character_extensions(raw: str) -> str:
    """'JOHN (V.O.) (CONT'D)' -> "V.O., CONT'D". Empty when there are none."""
    return ", ".join(m.group(1).upper() for m in EXTENSION_RE.finditer(raw))


def split_scene_number(heading: str) -> tuple[str, str | None]:
    """'14 INT. BAR - NIGHT 14' -> ('INT. BAR - NIGHT', '14')."""
    text = heading.strip()
    number = None
    if m := LEADING_NUMBER_RE.match(text):
        number = m.group(1).upper()
        text = text[m.end():].strip()
    if m := TRAILING_NUMBER_RE.search(text):
        # Only strip a trailing number when it mirrors the leading one, or when
        # there is no leading one — otherwise '- STAGE 2' loses its '2'.
        candidate = m.group(1).upper()
        if number is None or candidate == number:
            number = number or candidate
            text = text[: m.start()].strip()
    return text, number


def _is_character_cue(line: str, prev_blank: bool, next_line: str | None) -> bool:
    stripped = line.strip()
    if not stripped or not prev_blank:
        return False
    if HEADING_RE.match(stripped) or TRANSITION_RE.match(stripped) or SECTION_RE.match(stripped):
        return False
    base = normalize_character(stripped)
    if not base or len(base) > 40:
        return False
    # A cue is normally uppercase Latin. Indic scripts are caseless, so accept a
    # short native-script line too — the indian-regional profile lints the mix.
    if not re.search(r"[A-Z]", base) and not (
            INDIC_SCRIPT.search(base) and len(base.split()) <= 4):
        return False
    if base != base.upper() or re.search(r"[a-z]", stripped):
        return False
    if re.search(r"[!?.:;,]$", base):  # 'BANG!' style sound lines are action, not cues
        return False
    # A cue must be followed by dialogue or a parenthetical.
    return bool(next_line and next_line.strip())


def parse_heading(heading: str) -> tuple[str | None, str | None, str | None]:
    """-> (int_ext, location, time_of_day). Scene numbers are stripped first."""
    text, _ = split_scene_number(heading)
    m = HEADING_RE.match(text)
    int_ext = m.group(1).upper().rstrip(".") if m else None
    rest = text[m.end():].strip() if m else text
    location, time_of_day = rest, None
    if " - " in rest:
        head, _, tail = rest.rpartition(" - ")
        if tail.strip().upper() in TIMES_OF_DAY:
            location, time_of_day = head.strip(), tail.strip().upper()
    return int_ext, location or None, time_of_day


def parse_file(path: str | Path) -> Script:
    return parse_text(Path(path).read_text(encoding="utf-8"), str(path))


def parse_text(text: str, path: str = "<memory>") -> Script:
    lines = text.splitlines()
    elements: list[Element] = []
    scenes: list[Scene] = []
    title_page: dict[str, str] = {}
    title: str | None = None

    current_scene: Scene | None = None
    current_act: str | None = None
    in_dialogue_for: str | None = None
    prev_blank = True

    for i, raw in enumerate(lines):
        line_no = i + 1
        stripped = raw.strip()
        next_line = lines[i + 1] if i + 1 < len(lines) else None

        if not stripped:
            prev_blank = True
            in_dialogue_for = None
            continue

        # Title page (key: value pairs before the first scene)
        if current_scene is None and ":" in stripped and not scenes and not HEADING_RE.match(stripped):
            key, _, val = stripped.partition(":")
            norm_key = key.strip().lower()
            if norm_key in TITLE_PAGE_KEYS:
                value = val.strip() or (next_line.strip() if next_line else "")
                title_page[norm_key] = value
                if norm_key == "title":
                    title = value or None
                elements.append(Element(ElementType.TITLE_PAGE, stripped, line_no, raw=raw))
                prev_blank = False
                continue

        scene_index = current_scene.index if current_scene else -1

        # Structural markers (act breaks, interval, song blocks). '>CENTERED<'
        # is how many writers set them, so unwrap that first.
        centered = CENTERED_RE.match(stripped)
        marker_text = (centered.group(1) if centered else stripped).upper()
        if SECTION_RE.match(marker_text) and (centered or stripped == stripped.upper()):
            el = Element(ElementType.SECTION, marker_text, line_no, scene_index, raw=raw)
            elements.append(el)
            if current_scene is not None:
                current_scene.elements.append(el)
            if marker_text.startswith("ACT ") or marker_text in {"COLD OPEN", "TEASER", "TAG"}:
                current_act = marker_text
            prev_blank = False
            in_dialogue_for = None
            continue

        forced_heading = stripped.startswith(".") and not stripped.startswith("..")
        # A shooting-script slugline leads with its scene number ('14 INT. BAR - DAY'),
        # so strip that before asking whether the line is a heading at all.
        unnumbered, _ = split_scene_number(stripped)
        if (HEADING_RE.match(unnumbered) and prev_blank) or forced_heading:
            heading_text = stripped[1:].strip() if forced_heading else stripped
            int_ext, location, tod = parse_heading(heading_text)
            _, number = split_scene_number(heading_text)
            current_scene = Scene(
                index=len(scenes), heading=heading_text, line_no=line_no,
                int_ext=int_ext, location=location, time_of_day=tod,
                number=number, act=current_act,
            )
            scenes.append(current_scene)
            el = Element(ElementType.SCENE_HEADING, heading_text, line_no,
                         current_scene.index, raw=raw)
            elements.append(el)
            current_scene.elements.append(el)
            prev_blank = False
            in_dialogue_for = None
            continue

        if TRANSITION_RE.match(stripped):
            el = Element(ElementType.TRANSITION, stripped, line_no, scene_index, raw=raw)
            in_dialogue_for = None
        elif in_dialogue_for is not None:
            etype = ElementType.PARENTHETICAL if stripped.startswith("(") else ElementType.DIALOGUE
            el = Element(etype, stripped, line_no, scene_index,
                         character=in_dialogue_for, raw=raw)
        elif _is_character_cue(raw, prev_blank, next_line):
            name = normalize_character(stripped)
            in_dialogue_for = name
            el = Element(ElementType.CHARACTER, name, line_no, scene_index, raw=raw,
                         extension=character_extensions(stripped),
                         dual=stripped.rstrip().endswith("^"))
        else:
            el = Element(ElementType.ACTION, stripped, line_no, scene_index, raw=raw)

        elements.append(el)
        if current_scene is not None:
            current_scene.elements.append(el)
        prev_blank = False

    return Script(path=path, title=title, scenes=scenes, elements=elements,
                  total_lines=len(lines), raw_text=text, title_page=title_page)
