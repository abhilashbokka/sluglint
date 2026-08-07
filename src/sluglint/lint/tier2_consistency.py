"""Tier 2 consistency engine.

Runs over the parsed structure (character registry, location registry, scene
timeline) with fuzzy matching. Still deterministic and still free: nothing
here calls a model.

The recurring precision problem in this tier is that a name, a place, and a
prop are all just capitalised words. Handlers therefore anchor on a second
signal wherever they can: an age parenthetical for a character introduction,
an article for a prop, a known cue name for a spelling drift. That is why they
do not flag every capitalised token they find.

Production and volume metrics live in tier2_production.py.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from itertools import combinations

from .. import indic
from ..models import ElementType, Script
from ..rulebook import Rule
from .registry import detector, finding

AGE_HINT = re.compile(
    r"\b(\d{1,2}\s*s?|teens?|twenties|thirties|forties|fifties|sixties|seventies|"
    r"(?:early|mid|late)\s+\w+)\b",
    re.IGNORECASE,
)
# A capitalised name followed by an age parenthetical: an unambiguous introduction.
INTRODUCTION = re.compile(r"\b([A-Z][A-Z'\u2019\-]{2,}(?:\s+[A-Z][A-Z'\u2019\-]{2,})?)\s*\(([^)]{1,40})\)")
# 'a REVOLVER', 'the LOCKET'. The article is what marks a prop rather than a sound.
PROP = re.compile(r"\b(?:a|an|the|his|her|their|its|my|your)\s+([A-Z][A-Z'\u2019\-]{3,})\b")
NAME_TOKEN = re.compile(r"\b(?:[A-Z][a-z'\u2019\-]{3,}|[A-Z][A-Z'\u2019\-]{3,})\b")

FLASHBACK_OPEN = re.compile(r"\bFLASHBACK\b")
FLASHBACK_CLOSE = re.compile(r"\b(?:END (?:OF )?FLASHBACK|BACK TO PRESENT|PRESENT DAY)\b")
MONTAGE_OPEN = re.compile(r"\b(?:MONTAGE|SERIES OF SHOTS)\b")
MONTAGE_CLOSE = re.compile(r"\bEND (?:OF )?(?:MONTAGE|SERIES)\b")
INTERCUT_OPEN = re.compile(r"\bINTERCUT\b")
INTERCUT_CLOSE = re.compile(r"\bEND (?:OF )?INTERCUT\b")

# Caps on a sound is standard screenwriting emphasis, and 'a MOAN', 'a THUD'
# read as props to a rule that only looks for an article. Sound is a department,
# never a prop, so these are excluded rather than reported and dismissed.
SOUND_WORDS = {
    "MOAN", "GROAN", "SCREAM", "SHRIEK", "SHOUT", "YELL", "WHISPER", "GASP",
    "BANG", "BOOM", "CRASH", "THUD", "CRACK", "SNAP", "CLICK", "CLANG", "CLATTER",
    "KNOCK", "RATTLE", "RUMBLE", "ROAR", "HISS", "BUZZ", "BEEP", "RING", "CHIME",
    "SIREN", "HORN", "WHISTLE", "SPLASH", "SLAM", "SQUEAL", "SCREECH", "THUMP",
    "GUNSHOT", "EXPLOSION", "SILENCE", "LAUGHTER", "APPLAUSE", "FOOTSTEPS",
}

ABBREVIATIONS = {
    "APT": "APARTMENT", "APTS": "APARTMENTS", "HOSP": "HOSPITAL", "BLDG": "BUILDING",
    "RM": "ROOM", "ST": "STREET", "RD": "ROAD", "AVE": "AVENUE", "BLVD": "BOULEVARD",
    "HQ": "HEADQUARTERS", "HWY": "HIGHWAY", "MTN": "MOUNTAIN", "DEPT": "DEPARTMENT",
    "OFC": "OFFICE", "BR": "BEDROOM", "BSMT": "BASEMENT", "STN": "STATION",
    "UNIV": "UNIVERSITY", "SCH": "SCHOOL", "GDN": "GARDEN", "CTR": "CENTER",
    "PK": "PARK", "SQ": "SQUARE", "LN": "LANE", "CT": "COURT", "DR": "DRIVE",
}


# "CHITRA'S AUNT", "BRIDE'S FATHER": an owner and a relationship. Both
# apostrophes, because a draft that has been through Final Draft carries the
# typographic one.
RELATIVE_CUE = re.compile(r"^(.+?)['\u2019]S\s+(.+)$")
# 'ORGANIZER 2', 'SENIOR 1', 'COP #3'. The number is the whole point of the cue.
NUMBERED_CUE = re.compile(r"^(.*?)\s*#?\s*(\d+)$")


def similar(a: str, b: str) -> float:
    """Similarity of two names, in [0, 1].

    Every fuzzy matcher in this tier goes through here, which is why the Indic
    fold lives here too. Comparing an abugida by code point misses a one-vowel
    typo and can never match a cue written in Telugu against the same cue
    written in Latin. Latin-only pairs take the path they always did.
    """
    if folded := indic.comparable(a, b):
        return SequenceMatcher(None, *folded).ratio()
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _differing_core(a: str, b: str) -> tuple[str, str]:
    """Strip the shared head and tail, returning only what actually differs."""
    head = 0
    while head < min(len(a), len(b)) and a[head] == b[head]:
        head += 1
    tail = 0
    while tail < min(len(a), len(b)) - head and a[-1 - tail] == b[-1 - tail]:
        tail += 1
    return a[head:len(a) - tail], b[head:len(b) - tail]


# Typographic punctuation and its ASCII twin look identical on paper and are
# different characters to every registry downstream.
TYPOGRAPHIC = {"\u2019": "'", "\u2018": "'", "\u2013": "-", "\u2014": "-"}


def plain(text: str) -> str:
    """Fold typographic punctuation onto its ASCII twin."""
    for fancy, ascii_form in TYPOGRAPHIC.items():
        text = text.replace(fancy, ascii_form)
    return text


def _only_typography(a: str, b: str) -> bool:
    """True when two spellings differ ONLY in punctuation characters.

    'CHITRA'S FATHER' written with a typewriter apostrophe and with a
    typographic one is one name, and C031 reports it with the exact fix. Left
    unguarded, the fuzzy matchers report the same pair a second time with a
    vaguer message, which is how a rulebook starts to feel like noise.
    """
    return a != b and plain(a) == plain(b)


def _deliberately_distinct(a: str, b: str, thresh: float) -> bool:
    """True when two near-identical cues name different people on purpose.

    Two shapes cause almost every false name-drift report on a real script.
    A cast full of "X'S FATHER" and "Y'S FATHER" is normal in a family drama,
    and those cues are 85% alike by character overlap while naming two
    different actors; both halves have to match before that pair is drift.
    Numbered extras are the same problem with a simpler tell.
    """
    # 'SENIOR 1' and 'SENIOR 2' are two extras, and so are 'SENIOR' and
    # 'SENIOR 2'. Cues that agree on everything but a trailing number are the
    # one case where near-identical spelling means deliberately different people.
    na, nb = NUMBERED_CUE.match(a), NUMBERED_CUE.match(b)
    if (na or nb) and (na.group(2) if na else "") != (nb.group(2) if nb else ""):
        stem_a = na.group(1) if na else a
        stem_b = nb.group(1) if nb else b
        if similar(stem_a, stem_b) >= thresh:
            return True
    # A long shared head or tail carries the similarity score on its own.
    # "CHITRA'S HOUSE - THE NEXT DAY" and "CHITRA'S OFFICE - THE NEXT DAY" are
    # 88% alike and two sets. When what actually differs is a whole word on both
    # sides, the difference is the point; when it is punctuation, a possessive,
    # or nothing at all, the two are one thing spelled two ways.
    core_a, core_b = _differing_core(a, b)
    if (len(core_a) >= 3 and len(core_b) >= 3
            and core_a.strip().isalpha() and core_b.strip().isalpha()
            and similar(core_a, core_b) < thresh):
        return True
    ma, mb = RELATIVE_CUE.match(a), RELATIVE_CUE.match(b)
    if not (ma and mb):
        return False
    return not (similar(ma.group(1), mb.group(1)) >= thresh
                and similar(ma.group(2), mb.group(2)) >= thresh)


def _norm_location(loc: str) -> str:
    return " ".join((loc or "").upper().split())


def _expand(loc: str) -> str:
    return " ".join(ABBREVIATIONS.get(tok.rstrip("."), tok.rstrip("."))
                    for tok in _norm_location(loc).split())


def _action_text(script: Script) -> str:
    return " ".join(el.text for el in script.elements if el.type == ElementType.ACTION)


def cue_for(name: str, registry: set[str]) -> str | None:
    """Map a name as written in action onto the cue it belongs to.

    Writers routinely introduce 'PRIYA OKONKWO (30s)' and then cue her as
    'PRIYA'. Without this, every full-name introduction would look like a
    character who never speaks.
    """
    if name in registry:
        return name
    parts = set(name.split())
    for cue in sorted(registry):
        if set(cue.split()) & parts:
            return cue
    return None


def _presence(extension: str) -> str:
    """Collapse an extension into where the character is: ON / OFF / VO."""
    up = extension.upper()
    if "V" in up and ("V.O" in up or "VO" in up or "VOICE" in up):
        return "VO"
    if any(tag in up for tag in ("O.S", "OS", "O.C", "OC", "OFF")):
        return "OFF"
    return "ON"


# -------------------------------------------------------- character identity

@detector("name_drift")
def name_drift(script: Script, rule: Rule):
    registry = script.character_registry()
    thresh = float(rule.params.get("similarity_threshold", 0.80))
    for a, b in combinations(sorted(registry), 2):
        if _deliberately_distinct(a, b, thresh) or _only_typography(a, b):
            continue
        ratio = similar(a, b)
        if a in b.split() or b in a.split():  # 'RAJ' inside 'RAJ KUMAR'
            ratio = max(ratio, 0.99)
        if ratio >= thresh:
            yield finding(
                rule, f"Character cues '{a}' and '{b}' look like the same person "
                      f"(similarity {ratio:.2f}).",
                evidence=f"{a} | {b}",
                suggestion=f"'{a}' speaks in scenes {registry[a]}, '{b}' in {registry[b]}. "
                           f"Pick one spelling.",
            )


@detector("vanishing_character")
def vanishing_character(script: Script, rule: Rule):
    registry = script.character_registry()
    min_scenes = int(rule.params.get("min_scenes", 3))
    cutoff = float(rule.params.get("last_seen_before", 0.65))
    n = max(len(script.scenes), 1)
    for name, scene_idxs in registry.items():
        if len(scene_idxs) >= min_scenes and (max(scene_idxs) + 1) / n < cutoff:
            yield finding(
                rule, f"'{name}' appears in {len(scene_idxs)} scenes but is last seen at "
                      f"{(max(scene_idxs) + 1) / n:.0%} of the script.",
                evidence=f"{name} last speaks in scene {max(scene_idxs) + 1} of {n}",
                suggestion="If intentional, consider a closing beat; if not, a rewrite orphaned them.",
            )


@detector("uninitialized_character")
def uninitialized_character(script: Script, rule: Rule):
    for name in script.character_registry():
        # next() with a default: a bare next() raising StopIteration inside a
        # generator becomes a RuntimeError, not a clean stop.
        first_cue = next((el for el in script.elements
                          if el.type == ElementType.CHARACTER and el.text == name), None)
        if first_cue is None:
            continue
        introduced = any(
            el.type == ElementType.ACTION and name.upper() in el.text.upper()
            and el.line_no < first_cue.line_no
            for el in script.elements
        )
        if not introduced:
            yield finding(
                rule, f"'{name}' speaks before being introduced in an action line.",
                line_no=first_cue.line_no, scene_index=first_cue.scene_index, evidence=name,
                suggestion=f"Introduce them at first appearance: '{name.title()} (30s), ...'",
            )


@detector("single_use_character")
def single_use_character(script: Script, rule: Rule):
    registry = script.character_registry()
    counts = script.dialogue_counts()
    for name, scene_idxs in registry.items():
        if len(scene_idxs) == 1 and counts.get(name, 0) <= 1:
            yield finding(
                rule, f"'{name}' is named but speaks only {counts.get(name, 0)} line(s) "
                      f"in one scene.",
                evidence=name,
                suggestion="Consider a role name (WAITER, GUARD) unless they return in a later draft.",
            )


@detector("duplicate_introduction")
def duplicate_introduction(script: Script, rule: Rule):
    registry = set(script.character_registry())
    intros: dict[str, list] = {}
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for m in INTRODUCTION.finditer(el.text):
            name, inside = m.group(1), m.group(2)
            cue = cue_for(name, registry)
            if cue and AGE_HINT.search(inside):
                intros.setdefault(cue, []).append(el)
    for name, hits in intros.items():
        if len(hits) > 1:
            yield finding(
                rule, f"'{name}' is introduced with an age {len(hits)} times.",
                line_no=hits[1].line_no, scene_index=hits[1].scene_index,
                evidence=f"{name} introduced more than once",
                suggestion=f"Keep the first introduction (line {hits[0].line_no}); "
                           f"drop the later one.",
            )


@detector("orphan_mention")
def orphan_mention(script: Script, rule: Rule):
    registry = set(script.character_registry())
    seen: set[str] = set()
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for m in INTRODUCTION.finditer(el.text):
            name, inside = m.group(1), m.group(2)
            if cue_for(name, registry) or name in seen or not AGE_HINT.search(inside):
                continue
            seen.add(name)
            yield finding(
                rule, f"'{name}' is introduced like a character but never speaks.",
                line_no=el.line_no, scene_index=el.scene_index, evidence=name,
                suggestion="Give them a line, make them an unnamed role, or cut the name.",
            )


@detector("action_name_drift")
def action_name_drift(script: Script, rule: Rule):
    registry = set(script.character_registry())
    locations = {tok for sc in script.scenes for tok in _norm_location(sc.location or "").split()}
    thresh = float(rule.params.get("similarity_threshold", 0.80))
    tokens = {m.group(0) for m in NAME_TOKEN.finditer(_action_text(script))}
    reported: set[tuple[str, str]] = set()
    for token in sorted(tokens):
        upper = re.sub(r"['\u2019]S$", "", token.upper())
        if len(upper) < 4 or upper in registry or upper in locations:
            continue
        for name in sorted(registry):
            if len(name) < 4 or upper in (name + "S", name + "ES"):
                continue  # a plain inflection of the cue name, not drift
            if abs(len(upper) - len(name)) <= 2 and similar(upper, name) >= thresh:
                if (name, upper) in reported:
                    continue
                reported.add((name, upper))
                yield finding(
                    rule, f"Action lines spell '{token}' where the cue is '{name}'.",
                    evidence=f"{name} | {token}",
                    suggestion="Cue and action must use the identical spelling.",
                )


@detector("age_drift")
def age_drift(script: Script, rule: Rule):
    registry = set(script.character_registry())
    ages: dict[str, dict[str, int]] = {}
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for m in INTRODUCTION.finditer(el.text):
            name, inside = m.group(1), m.group(2)
            cue = cue_for(name, registry)
            if not cue:
                continue
            if hit := AGE_HINT.search(inside):
                key = re.sub(r"\s+", "", hit.group(0).lower())
                ages.setdefault(cue, {}).setdefault(key, el.line_no)
    for name, found in ages.items():
        if len(found) > 1:
            listed = ", ".join(sorted(found))
            yield finding(
                rule, f"'{name}' is given two different ages: {listed}.",
                line_no=max(found.values()), evidence=f"{name} age drift",
                suggestion="Casting reads this as an instruction; pick one.",
            )


@detector("vo_only_character")
def vo_only_character(script: Script, rule: Rule):
    cues: dict[str, list] = {}
    for el in script.elements:
        if el.type == ElementType.CHARACTER:
            cues.setdefault(el.text, []).append(el)
    for name, els in cues.items():
        if els and all(_presence(el.extension) == "VO" for el in els):
            yield finding(
                rule, f"'{name}' is only ever heard in voice-over ({len(els)} cues).",
                line_no=els[0].line_no, scene_index=els[0].scene_index,
                evidence=f"{name} voice-over only",
                suggestion="If they should appear on camera, a scene went missing in a rewrite.",
            )


@detector("extension_drift")
def extension_drift(script: Script, rule: Rule):
    for sc in script.scenes:
        by_name: dict[str, set[str]] = {}
        for el in sc.elements:
            if el.type == ElementType.CHARACTER:
                by_name.setdefault(el.text, set()).add(_presence(el.extension))
        for name, modes in by_name.items():
            if len(modes) > 1:
                yield finding(
                    rule, f"'{name}' switches between {' and '.join(sorted(modes))} "
                          f"inside one scene.",
                    line_no=sc.line_no, scene_index=sc.index,
                    evidence=f"{name} extension drift in scene {sc.index}",
                    suggestion="Write the entrance or exit that justifies the change.",
                )


# ----------------------------------------------------------- place and time

@detector("day_night_whiplash")
def day_night_whiplash(script: Script, rule: Rule):
    for i in range(len(script.scenes) - 2):
        trio = script.scenes[i:i + 3]
        tods = [s.time_of_day for s in trio]
        locs = [s.location or "" for s in trio]
        if (None not in tods
                and tods[0] == tods[2] and tods[0] != tods[1]
                and {tods[0], tods[1]} == {"DAY", "NIGHT"}
                and similar(locs[0], locs[2]) > 0.8):
            yield finding(
                rule, f"Scenes {trio[0].index + 1}-{trio[2].index + 1} flip "
                      f"{tods[0]} -> {tods[1]} -> {tods[2]} at the same location.",
                line_no=trio[1].line_no, scene_index=trio[1].index,
                evidence=" | ".join(s.heading for s in trio),
                suggestion="If a full day passes, cue it (LATER / NEXT DAY); otherwise fix the slugline.",
            )


@detector("location_drift")
def location_drift(script: Script, rule: Rule):
    thresh = float(rule.params.get("similarity_threshold", 0.82))
    locations = sorted({_norm_location(s.location) for s in script.scenes if s.location})
    for a, b in combinations(locations, 2):
        # Places take the same guard cues do: two sluglines that agree except
        # for one whole word are two places, and "ROOM 1" and "ROOM 2" are two
        # rooms. Only near-identical spelling of the same name is drift.
        if _deliberately_distinct(a, b, thresh) or _only_typography(a, b):
            continue
        ratio = similar(a, b)
        if thresh <= ratio < 1.0:
            yield finding(
                rule, f"Locations '{a}' and '{b}' look like the same set (similarity {ratio:.2f}).",
                evidence=f"{a} | {b}",
                suggestion="Keep one canonical slugline name per physical place.",
            )


@detector("int_ext_conflict")
def int_ext_conflict(script: Script, rule: Rule):
    by_location: dict[str, set[str]] = {}
    for sc in script.scenes:
        if sc.location and sc.int_ext:
            by_location.setdefault(_norm_location(sc.location), set()).add(sc.int_ext)
    for loc, modes in sorted(by_location.items()):
        if {"INT", "EXT"} <= modes and not any(m.startswith("INT/") or "/" in m for m in modes):
            yield finding(
                rule, f"'{loc}' is shot as both an interior and an exterior.",
                evidence=f"{loc} INT and EXT",
                suggestion="Use INT./EXT. on both headings, or give the two spaces distinct names.",
            )


@detector("continuous_across_locations")
def continuous_across_locations(script: Script, rule: Rule):
    for prev, cur in zip(script.scenes, script.scenes[1:]):
        if cur.time_of_day != "CONTINUOUS":
            continue
        a, b = _norm_location(prev.location or ""), _norm_location(cur.location or "")
        if a and b and similar(a, b) < 0.6:
            yield finding(
                rule, f"CONTINUOUS from '{a}' to '{b}', which are unrelated locations.",
                line_no=cur.line_no, scene_index=cur.index,
                evidence=f"CONTINUOUS {a} -> {b}",
                suggestion="CONTINUOUS means unbroken action; use SAME TIME or a new time marker.",
            )


@detector("mergeable_scenes")
def mergeable_scenes(script: Script, rule: Rule):
    for prev, cur in zip(script.scenes, script.scenes[1:]):
        if prev.heading.upper() == cur.heading.upper():
            continue  # exact duplicates belong to F015, not here
        same_place = (prev.location and cur.location
                      and _norm_location(prev.location) == _norm_location(cur.location))
        # CONTINUOUS and SAME both assert "no time has passed", so they count as
        # the same time of day as the scene above them.
        same_time = (prev.time_of_day == cur.time_of_day
                     or cur.time_of_day in {"CONTINUOUS", "SAME", "SAME TIME"})
        ends_on_transition = bool(prev.elements) and prev.elements[-1].type == ElementType.TRANSITION
        if same_place and prev.int_ext == cur.int_ext and same_time and not ends_on_transition:
            yield finding(
                rule, f"Scenes {prev.index + 1} and {cur.index + 1} share a location and time "
                      f"with no transition between them.",
                line_no=cur.line_no, scene_index=cur.index,
                evidence=f"{prev.heading} | {cur.heading}",
                suggestion="Merge them, or add the transition that separates them.",
            )


@detector("abbreviation_drift")
def abbreviation_drift(script: Script, rule: Rule):
    locations = sorted({_norm_location(s.location) for s in script.scenes if s.location})
    for a, b in combinations(locations, 2):
        if a != b and _expand(a) == _expand(b):
            yield finding(
                rule, f"'{a}' and '{b}' expand to the same place.",
                evidence=f"{a} | {b}",
                suggestion=f"Pick one spelling ('{_expand(a)}') so the breakdown counts one set.",
            )


# ------------------------------------------------------ structural continuity

def _unclosed(script: Script, rule: Rule, opener, closer, label: str):
    opens = [el for el in script.elements
             if opener.search(el.text.upper()) and not closer.search(el.text.upper())]
    closes = [el for el in script.elements if closer.search(el.text.upper())]
    if len(opens) > len(closes):
        yield finding(
            rule, f"{len(opens)} {label} marker(s) opened, {len(closes)} closed.",
            line_no=opens[len(closes)].line_no,
            scene_index=opens[len(closes)].scene_index,
            evidence=f"unclosed {label}",
            suggestion=f"Close it with END {label.upper()} (or an equivalent) so the "
                       f"time frame is unambiguous.",
        )


@detector("unclosed_flashback")
def unclosed_flashback(script: Script, rule: Rule):
    yield from _unclosed(script, rule, FLASHBACK_OPEN, FLASHBACK_CLOSE, "flashback")


@detector("unclosed_montage")
def unclosed_montage(script: Script, rule: Rule):
    yield from _unclosed(script, rule, MONTAGE_OPEN, MONTAGE_CLOSE, "montage")


@detector("unclosed_intercut")
def unclosed_intercut(script: Script, rule: Rule):
    yield from _unclosed(script, rule, INTERCUT_OPEN, INTERCUT_CLOSE, "intercut")


@detector("unpaid_prop")
def unpaid_prop(script: Script, rule: Rule):
    min_length = int(rule.params.get("min_length", 4))
    registry = set(script.character_registry())
    full_text = " ".join(el.text for el in script.elements).upper()
    first_seen: dict[str, object] = {}
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for m in PROP.finditer(el.text):
            prop = m.group(1)
            if len(prop) >= min_length and prop not in registry and prop.upper() not in SOUND_WORDS:
                first_seen.setdefault(prop, el)
    for prop, el in first_seen.items():
        # Capitalised once, and the word never appears again in any casing.
        if len(re.findall(rf"\b{re.escape(prop)}\b", full_text)) == 1:
            yield finding(
                rule, f"'{prop}' is capitalised like a key prop but never appears again.",
                line_no=el.line_no, scene_index=el.scene_index, evidence=prop,
                suggestion="Pay it off, or lowercase it so the art department stops tracking it.",
            )
