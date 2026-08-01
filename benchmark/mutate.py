"""Fault injection: turn a clean script into a labelled defective draft.

Each mutator makes ONE change that a specific rule is supposed to catch, and
declares which rule id that is. That gives a labelled corpus without anyone
hand-annotating scripts, which is what makes per-rule recall measurable at all.

A mutator returns None when the script has no suitable place to inject its
defect (no repeated location, no dialogue to orphan). Skipping honestly is
better than forcing a mutation the rule was never meant to see.
"""
from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass

HEADING = re.compile(r"^(INT|EXT|INT\.?/EXT|I/E|EST)[.\s]", re.IGNORECASE)
CUE = re.compile(r"^[A-Z][A-Z0-9 '.()^]*$")
TIME_TAIL = re.compile(r"\s+-\s+(DAY|NIGHT|MORNING|EVENING|DAWN|DUSK|CONTINUOUS|LATER|SAME)\s*$",
                       re.IGNORECASE)

ABBREVIATIONS = {"APARTMENT": "APT.", "STATION": "STN.", "STREET": "ST.",
                 "BUILDING": "BLDG.", "HOSPITAL": "HOSP.", "ROOM": "RM."}


@dataclass
class Mutation:
    """One injected defect and the rule that should find it."""
    rule_id: str
    name: str
    text: str
    note: str


Mutator = Callable[[str, random.Random], Mutation | None]

REGISTRY: list[tuple[str, str, str, Mutator]] = []


def mutator(rule_id: str, description: str):
    """Register a mutator. Keyed on the function name so results can be joined."""
    def wrap(fn: Mutator) -> Mutator:
        REGISTRY.append((rule_id, fn.__name__, description, fn))
        return fn
    return wrap


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _headings(lines: list[str]) -> list[int]:
    return [i for i, ln in enumerate(lines)
            if HEADING.match(ln.strip()) and ln.strip() == ln.strip().upper()]


def _cues(lines: list[str]) -> list[int]:
    """Indices of lines that look like character cues with dialogue under them."""
    out = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if (s and CUE.match(s) and len(s.split()) <= 4 and not HEADING.match(s)
                and i > 0 and not lines[i - 1].strip()
                and i + 1 < len(lines) and lines[i + 1].strip()
                and not s.endswith(":") and not s.endswith(".")):
            out.append(i)
    return out


def _action_lines(lines: list[str]) -> list[int]:
    heads = set(_headings(lines))
    cues = set(_cues(lines))
    out = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if (s and i not in heads and i not in cues and s != s.upper()
                and not s.startswith("(") and (i == 0 or not lines[i - 1].strip())):
            out.append(i)
    return out


# ------------------------------------------------------------ character drift

@mutator("C001", "misspell a character cue in some scenes")
def rename_character(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    cues = _cues(lines)
    if not cues:
        return None
    names: dict[str, list[int]] = {}
    for i in cues:
        names.setdefault(lines[i].strip(), []).append(i)
    candidates = [n for n, idx in names.items() if len(idx) >= 3 and len(n) >= 4 and n.isalpha()]
    if not candidates:
        return None
    name = rng.choice(sorted(candidates))
    typo = name[:-1] if len(name) > 4 else name + "E"
    hits = names[name][len(names[name]) // 2:]
    for i in hits:
        lines[i] = lines[i].replace(name, typo)
    return Mutation("C001", "rename_character", "\n".join(lines),
                    f"{name} spelled {typo} in {len(hits)} of {len(names[name])} cues")


# ------------------------------------------------------------------ locations

@mutator("C005", "spell one location slightly differently")
def split_location(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = _headings(lines)
    seen: dict[str, list[int]] = {}
    for i in heads:
        seen.setdefault(lines[i].strip(), []).append(i)
    repeats = [h for h, idx in seen.items() if len(idx) >= 2 and len(h) > 14]
    if not repeats:
        return None
    heading = rng.choice(sorted(repeats))
    i = seen[heading][-1]
    body = TIME_TAIL.sub("", heading)
    lines[i] = lines[i].replace(heading, body + "S" + (TIME_TAIL.search(heading).group(0)
                                                       if TIME_TAIL.search(heading) else ""))
    return Mutation("C005", "split_location", "\n".join(lines),
                    f"one instance of {body} pluralised")


@mutator("C019", "abbreviate a location in one heading")
def abbreviate_location(text: str, _rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = _headings(lines)
    for full, short in ABBREVIATIONS.items():
        word = re.compile(rf"\b{full}\b", re.IGNORECASE)
        hosts = [i for i in heads if word.search(lines[i])]
        # Abbreviating the only occurrence creates no conflict to detect, so
        # the word has to survive somewhere else in the script.
        if len(hosts) < 2:
            continue
        i = hosts[-1]
        lines[i] = word.sub(short, lines[i], count=1)
        return Mutation("C019", "abbreviate_location", "\n".join(lines),
                        f"{full} written as {short} in one of {len(hosts)} headings")
    return None


@mutator("F002", "strip the time of day off one heading")
def drop_time_of_day(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = [i for i in _headings(lines) if TIME_TAIL.search(lines[i])]
    if not heads:
        return None
    i = rng.choice(heads)
    before = lines[i].strip()
    lines[i] = TIME_TAIL.sub("", lines[i])
    return Mutation("F002", "drop_time_of_day", "\n".join(lines),
                    f"time marker removed from {before}")


@mutator("C004", "flip the middle of three scenes at one location")
def day_night_whiplash(text: str, _rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = _headings(lines)
    for a, b, c in zip(heads, heads[1:], heads[2:]):
        first, mid, last = (lines[x].strip().upper() for x in (a, b, c))
        if first == last and first.endswith(" - DAY") and mid.endswith(" - DAY"):
            lines[b] = lines[b][: lines[b].upper().rfind(" - DAY")] + " - NIGHT"
            return Mutation("C004", "day_night_whiplash", "\n".join(lines),
                            "middle of three scenes at one location flipped to NIGHT")
    return None


# ----------------------------------------------------------------- formatting

@mutator("F005", "add a camera direction")
def insert_camera_direction(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = _headings(lines)
    if not heads:
        return None
    i = rng.choice(heads)
    lines.insert(i + 1, "")
    lines.insert(i + 2, "ANGLE ON the doorway. Nobody there.")
    return Mutation("F005", "insert_camera_direction", "\n".join(lines),
                    "ANGLE ON added after a scene heading")


@mutator("F004", "grow an action block into a wall of text")
def wall_of_text(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    actions = _action_lines(lines)
    if not actions:
        return None
    i = rng.choice(actions)
    filler = [lines[i]] * 5
    lines[i:i + 1] = filler
    return Mutation("F004", "wall_of_text", "\n".join(lines),
                    "one action line repeated into a six-line block")


@mutator("F003", "leave a character cue with nothing under it")
def orphan_cue(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    cues = _cues(lines)
    if not cues:
        return None
    i = rng.choice(cues)
    name = lines[i].strip()
    # Deleting the dialogue outright makes the parser stop reading the line as
    # a cue, and an undetectable defect is not a useful test. A cue followed by
    # a transition is the shape that actually reaches the rule.
    j = i + 1
    while j < len(lines) and lines[j].strip():
        del lines[j]
    lines.insert(i + 1, "CUT TO:")
    return Mutation("F003", "orphan_cue", "\n".join(lines),
                    f"dialogue under {name} replaced by a transition")


@mutator("F019", "cue the same character twice in a row")
def consecutive_same_cue(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    cues = _cues(lines)
    if not cues:
        return None
    i = rng.choice(cues)
    name = lines[i].strip()
    end = i + 1
    while end < len(lines) and lines[end].strip():
        end += 1
    lines[end:end] = ["", name, "And another thing."]
    return Mutation("F019", "consecutive_same_cue", "\n".join(lines),
                    f"{name} cued twice with nothing between")


@mutator("F027", "introduce word-processor typography")
def smart_typography(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    actions = _action_lines(lines)
    if not actions:
        return None
    i = rng.choice(actions)
    # Escaped so the source stays ASCII; this is the character being injected.
    lines[i] = lines[i].rstrip(".") + " \u2014 and then nothing."
    return Mutation("F027", "smart_typography", "\n".join(lines),
                    "an em dash pasted into an action line")


@mutator("F025", "leave a pagination artifact behind")
def pagination_artifact(text: str, rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    cues = _cues(lines)
    if not cues:
        return None
    i = rng.choice(cues)
    lines[i:i] = ["(MORE)", ""]
    return Mutation("F025", "pagination_artifact", "\n".join(lines),
                    "(MORE) left in from a PDF conversion")


@mutator("C014", "open a flashback and never close it")
def unclosed_flashback(text: str, _rng: random.Random) -> Mutation | None:
    lines = _lines(text)
    heads = _headings(lines)
    if len(heads) < 2:
        return None
    i = heads[len(heads) // 2]
    lines[i:i] = ["BEGIN FLASHBACK", ""]
    return Mutation("C014", "unclosed_flashback", "\n".join(lines),
                    "BEGIN FLASHBACK inserted with no matching close")


def apply_all(text: str, seed: int = 0) -> list[Mutation]:
    """Every mutation that this script can host, one at a time."""
    out = []
    for _rule_id, _name, _desc, fn in REGISTRY:
        m = fn(text, random.Random(seed))
        if m is not None:
            out.append(m)
    return out


def chain(text: str, mutations: list[str], seed: int = 0) -> list[Mutation]:
    """Apply mutators cumulatively to simulate a script drifting over drafts."""
    by_name = {name: fn for _rid, name, _desc, fn in REGISTRY}
    drafts: list[Mutation] = []
    current = text
    for name in mutations:
        fn = by_name.get(name)
        if fn is None:
            continue
        m = fn(current, random.Random(seed))
        if m is None:
            continue
        current = m.text
        drafts.append(m)
    return drafts
