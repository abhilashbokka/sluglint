"""Tier 2, third pass: the shape of the cast and the ends the draft left loose.

Two families live here.

**The cast as a graph.** Two people who never share a scene have no
relationship an audience can watch. Reading the script as a co-presence graph
makes three things checkable that are otherwise invisible in a linear read: a
speaking part who is never in a room with anyone, a cast that falls into two
groups who never meet, and where each person sits relative to everyone else.
The graph itself lives in `network.py` and reports numbers; only the defects
are rules.

**Reference decay.** A loose end, stated so a machine can check it, is
something the document introduces and then never refers to again. That is the
same class of defect as an unpaid prop or a vanishing character, and it is
verifiable by pointing at one place in the text and at the absence of a second.
It is emphatically NOT a judgement about whether a story resolves well; the
rules that need that judgement are tier 3, carry `suggestion` severity, and
have to quote the setup they are talking about.

Every handler here is narrowed against the same failure the rest of tier 2
guards: a name, a place, and a thing are all just capitalised words.
"""
from __future__ import annotations

import re

from .. import characters as chars
from .. import network as net
from ..models import ElementType, Script
from ..rulebook import Rule
from .registry import detector, finding
from .tier2_consistency import SOUND_WORDS, _norm_location, plain

# A capitalised word a writer uses for emphasis rather than as a thing that
# recurs. Format furniture, time markers, and the vocabulary of the page itself.
NOT_A_THREAD = {
    "INT", "EXT", "EST", "DAY", "NIGHT", "DAWN", "DUSK", "MORNING", "EVENING",
    "AFTERNOON", "CONTINUOUS", "LATER", "SAME", "MOMENTS", "CUT", "FADE", "DISSOLVE",
    "SMASH", "MATCH", "BACK", "MONTAGE", "SERIES", "SHOTS", "INTERCUT", "FLASHBACK",
    "PRESENT", "SUPER", "TITLE", "CHYRON", "SUBTITLE", "INSERT", "ANGLE", "CLOSE",
    "WIDE", "POV", "END", "THE", "AND", "BUT", "WITH", "FROM", "INTO", "THAT", "THIS",
    "ACT", "ONE", "TWO", "THREE", "FOUR", "FIVE", "COLD", "OPEN", "TEASER", "TAG",
    "INTERVAL", "SONG", "MORE", "CONTD", "OVER", "BLACK", "WHITE",
}
# Cues that describe a job rather than name a person. Fine for a role; a
# problem once the part is big enough to cast.
ROLE_WORDS = {
    "MAN", "WOMAN", "BOY", "GIRL", "GUY", "LADY", "GENTLEMAN", "KID", "CHILD",
    "DOCTOR", "NURSE", "WAITER", "WAITRESS", "DRIVER", "GUARD", "SECURITY", "COP",
    "POLICE", "OFFICER", "CLERK", "TEACHER", "STUDENT", "NEIGHBOUR", "NEIGHBOR",
    "STRANGER", "VOICE", "RECEPTIONIST", "MANAGER", "BOSS", "ASSISTANT", "SERVANT",
    "CONDUCTOR", "PASSENGER", "CUSTOMER", "SHOPKEEPER", "PRIEST", "LAWYER", "JUDGE",
    "SOLDIER", "ATTENDANT", "OLD", "YOUNG", "FIRST", "SECOND", "THIRD", "ANOTHER",
}
CAPS_TOKEN = re.compile(r"\b[A-Z][A-Z'\u2019\-]{3,}\b")
# A cue that says in its own name that it is a voice: heard, not in the room.
# Being alone in a scene is what those cues are for, so they are exempt from the
# rules about sharing one.
VOICE_CUE = re.compile(r"\b(V\.?O\.?|V\s*/\s*O|O\.?S\.?|O\s*/\s*S|VOICE|ANNOUNCER|"
                       r"RADIO|TV|TELEVISION|P\.?A\.?|LOUDSPEAKER|PHONE|INTERCOM)\b")
# ----------------------------------------------------------------- typography

@detector("apostrophe_drift")
def apostrophe_drift(script: Script, rule: Rule):
    """One name written with two different apostrophe characters.

    The single highest-yield check in this file, and the one that came out of
    reading real drafts. A script that has been through more than one editor
    carries both the typewriter apostrophe and the typographic one, and every
    registry in the pipeline then counts one character or one set as two. It
    looks identical on paper, so nobody catches it by reading, and the fix is
    one find and replace.
    """
    for label, values in (("Character cue", sorted(script.character_registry())),
                          ("Location", sorted({_norm_location(s.location)
                                               for s in script.scenes if s.location}))):
        buckets: dict[str, list[str]] = {}
        for value in values:
            buckets.setdefault(plain(value), []).append(value)
        for folded, written in buckets.items():
            if len(written) > 1:
                yield finding(
                    rule, f"{label} '{folded}' is written {len(written)} ways that differ only "
                          f"in punctuation.",
                    evidence=" | ".join(written),
                    suggestion="Straight and typographic apostrophes look the same on the page "
                               "and split every registry in two. Replace one with the other.")


# ------------------------------------------------------------- cast as a graph

@detector("isolated_character")
def isolated_character(script: Script, rule: Rule):
    min_lines = int(rule.params.get("min_lines", 2))
    counts = script.dialogue_counts()
    graph = net.build(script)
    # A one-hander has nobody to share a scene with, so "never shares one" is
    # not a fact about the writing.
    if graph.cast < int(rule.params.get("min_cast", 3)):
        return
    for name in graph.isolated:
        if counts.get(name, 0) >= min_lines and not VOICE_CUE.search(name):
            yield finding(
                rule, f"'{name}' speaks {counts[name]} lines and never shares a scene with "
                      f"another speaking part.",
                evidence=f"{name} shares no scene",
                suggestion="A relationship the audience never sees played is a relationship "
                           "that is only described. If they are on a phone or in voice-over, "
                           "the extension should say so.")


@detector("disconnected_cast")
def disconnected_cast(script: Script, rule: Rule):
    min_size = int(rule.params.get("min_group", 2))
    min_cast = int(rule.params.get("min_cast", 5))
    graph = net.build(script)
    if graph.cast < min_cast:
        return
    groups = sorted((g for g in graph.components if len(g) >= min_size), key=len, reverse=True)
    if len(groups) > 1:
        yield finding(
            rule, f"The cast falls into {len(groups)} groups who never share a scene "
                  f"(largest {len(groups[0])}, next {len(groups[1])}).",
            evidence="cast splits into separate groups",
            suggestion=f"'{groups[1][0]}' and everyone with them never meet "
                       f"'{groups[0][0]}' or anyone in that group. Usually two drafts that "
                       f"got merged, or a strand that needs one shared scene.")


@detector("lone_speaker_scene")
def lone_speaker_scene(script: Script, rule: Rule):
    min_lines = int(rule.params.get("min_lines", 6))
    for sc in script.scenes:
        speakers = sc.characters
        lines = [el for el in sc.elements if el.type == ElementType.DIALOGUE]
        if len(speakers) != 1 or len(lines) < min_lines:
            continue
        # A voice on a phone, a voice-over, or an off-screen reply all mean
        # there is a second person in the scene the cue list cannot see.
        if any(el.extension for el in sc.elements if el.type == ElementType.CHARACTER):
            continue
        if VOICE_CUE.search(speakers[0]):
            continue
        yield finding(
            rule, f"'{speakers[0]}' speaks {len(lines)} lines and is the only voice in the scene.",
            line_no=sc.line_no, scene_index=sc.index,
            evidence=f"{speakers[0]} alone in scene {sc.index + 1}",
            suggestion="If someone answers, cue them. If nobody does, mark the other side "
                       "(V.O.) or (O.S.), or the scene reads as a missing cue.")


# --------------------------------------------------------------- reference decay

@detector("dropped_location")
def dropped_location(script: Script, rule: Rule):
    min_scenes = int(rule.params.get("min_scenes", 3))
    cutoff = float(rule.params.get("last_seen_before", 0.6))
    total = len(script.scenes)
    if not total:
        return
    by_name: dict[str, list[int]] = {}
    for sc in script.scenes:
        if sc.location:
            by_name.setdefault(_norm_location(sc.location), []).append(sc.index)
    for name, idxs in sorted(by_name.items()):
        last = max(idxs)
        if len(idxs) < min_scenes or (last + 1) / total >= cutoff:
            continue
        # Named later in dialogue or action counts as still being in the story
        # even when the camera never goes back.
        later = " ".join(el.text for el in script.elements
                         if el.scene_index > last).upper()
        head = name.split(" - ")[0]
        if len(head) >= 4 and re.search(rf"\b{re.escape(head)}\b", later):
            continue
        yield finding(
            rule, f"'{name}' carries {len(idxs)} scenes and is never seen or named again after "
                  f"{(last + 1) / total:.0%} of the script.",
            evidence=f"{name} last used in scene {last + 1} of {total}",
            suggestion="A set built for a third of the film and then abandoned is either a "
                       "thread that stopped or a set two other scenes could move into.")


@detector("dropped_thread")
def dropped_thread(script: Script, rule: Rule):
    min_mentions = int(rule.params.get("min_mentions", 3))
    cutoff = float(rule.params.get("last_seen_before", 0.6))
    total = len(script.scenes)
    if total < int(rule.params.get("min_scenes", 8)):
        return
    registry = set(script.character_registry())
    place_words = {tok for sc in script.scenes
                   for tok in _norm_location(sc.location or "").replace("-", " ").split()}
    seen: dict[str, list[int]] = {}
    for el in script.elements:
        if el.type not in (ElementType.ACTION, ElementType.DIALOGUE):
            continue
        for m in CAPS_TOKEN.finditer(el.text):
            token = m.group(0)
            if (token in NOT_A_THREAD or token in SOUND_WORDS or token in registry
                    or token in place_words or any(token in name.split() for name in registry)):
                continue
            seen.setdefault(token, []).append(max(el.scene_index, 0))
    for token, idxs in sorted(seen.items()):
        last = max(idxs)
        if len(idxs) < min_mentions or (last + 1) / total >= cutoff:
            continue
        yield finding(
            rule, f"'{token}' is named {len(idxs)} times and never again after "
                  f"{(last + 1) / total:.0%} of the script.",
            evidence=f"{token} last named in scene {last + 1} of {total}",
            suggestion="Something the script capitalised and returned to three times reads as "
                       "planted. Pay it off, or stop capitalising it.")


# ------------------------------------------------------------ cast description

@detector("unaged_principal")
def unaged_principal(script: Script, rule: Rule):
    top = int(rule.params.get("top", 5))
    counts = script.dialogue_counts()
    if len(counts) < top:
        return
    principals = sorted(counts, key=lambda n: (-counts[n], n))[:top]
    profiles = chars.profiles(script)
    for name in principals:
        profile = profiles.get(name)
        if profile and not profile.age_band:
            yield finding(
                rule, f"'{name}' is a lead ({counts[name]} lines) with no age anywhere on the page.",
                evidence=f"{name} has no stated age",
                suggestion=f"Casting reads the script for exactly this. One parenthetical at "
                           f"the first appearance is enough: '{name} (30s), ...'")


@detector("unnamed_principal")
def unnamed_principal(script: Script, rule: Rule):
    """A substantial speaking part cued only by what they do.

    WAITER with two lines is a role. WAITER with forty is a part somebody gets
    cast in, fitted for, and called to set by name for three weeks, and every
    one of those steps wants a name to hang on. Numbered variants count as the
    same role, because SECURITY GUARD 2 is no more named than SECURITY GUARD.
    """
    min_lines = int(rule.params.get("min_lines", 15))
    counts = script.dialogue_counts()
    for name, lines in sorted(counts.items()):
        if lines < min_lines:
            continue
        stem = re.sub(r"\s*#?\s*\d+$", "", name).strip()
        if stem and all(word in ROLE_WORDS for word in stem.split()):
            yield finding(
                rule, f"'{name}' speaks {lines} lines and is cued by a role rather than a name.",
                evidence=f"{name} is a substantial unnamed part",
                suggestion="A part this size gets cast, fitted, and called to set. Give them a "
                           "name, or the sides and the schedule carry a job description.")


@detector("crowded_opening")
def crowded_opening(script: Script, rule: Rule):
    share = float(rule.params.get("opening_share", 0.1))
    limit = int(rule.params.get("max_cast", 8))
    total = len(script.scenes)
    if total < int(rule.params.get("min_scenes", 20)):
        return
    window = max(1, round(total * share))
    early = sorted({name for name, idxs in script.character_registry().items()
                    if min(idxs) < window})
    if len(early) > limit:
        yield finding(
            rule, f"{len(early)} speaking parts arrive in the first {window} scenes (max {limit}).",
            scene_index=0, evidence="crowded opening",
            suggestion="A reader can hold about half a dozen new names at once. Stagger the "
                       "entrances, or let some of them be unnamed roles until they matter.")


@detector("late_principal")
def late_principal(script: Script, rule: Rule):
    after = float(rule.params.get("after", 0.75))
    min_lines = int(rule.params.get("min_lines", 8))
    total = len(script.scenes)
    if not total:
        return
    counts = script.dialogue_counts()
    for name, idxs in sorted(script.character_registry().items()):
        if counts.get(name, 0) < min_lines or min(idxs) / total < after:
            continue
        yield finding(
            rule, f"'{name}' first speaks at {min(idxs) / total:.0%} of the script and then "
                  f"carries {counts[name]} lines.",
            scene_index=min(idxs), evidence=f"{name} arrives late with a substantial part",
            suggestion="A part this size arriving this late usually wants planting earlier, "
                       "even in one line.")
