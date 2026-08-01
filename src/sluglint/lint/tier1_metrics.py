"""Tier 1 — deterministic document metrics and profile-gated structure rules.

Two kinds of check live here:

  * Ratios and counts across the whole document (transitions per scene,
    exclamation marks per page, scenes per page). These produce ONE
    script-level finding, and their `evidence` is a fixed string rather than
    the count — counts go in `message`. If the count went in the evidence,
    every re-lint with one more exclamation mark would look like a brand new
    finding and the draft diff would churn.

  * Rules that only exist inside a profile: scene numbers are an amateur tell
    on a spec and mandatory on a shooting script, so both rules live in the
    rulebook and the profile decides which one runs.
"""
from __future__ import annotations

import re

from ..models import ElementType, Script
from ..rulebook import Rule
from .registry import detector, finding

NON_LATIN_SCRIPT = re.compile(r"[ऀ-෿]")  # Devanagari .. Sinhala
SCENE_NUMBER = re.compile(r"^(\d{1,4})([A-Z]{0,2})$")
ACT_MARKER = re.compile(r"^(ACT [A-Z0-9]+|COLD OPEN|TEASER|TAG)$")
SONG_IN_ACTION = re.compile(r"\bSONG\b", re.IGNORECASE)
INTERVAL_MARKER = re.compile(r"^(INTERVAL|INTERMISSION)$")


def _sections(script: Script) -> list:
    return [el for el in script.elements if el.type == ElementType.SECTION]


# ------------------------------------------------------------- ratio metrics

@detector("transition_overuse")
def transition_overuse(script: Script, rule: Rule):
    n_trans = sum(1 for el in script.elements
                  if el.type == ElementType.TRANSITION and el.text.endswith("TO:"))
    n_scenes = max(len(script.scenes), 1)
    limit = float(rule.params.get("max_per_10_scenes", 3)) * n_scenes / 10.0
    if n_trans > max(limit, 2):
        yield finding(rule, f"{n_trans} transitions across {n_scenes} scenes.",
                      evidence="transition overuse",
                      suggestion="Cuts are implied between scenes; keep only deliberate ones.")


@detector("parenthetical_overuse")
def parenthetical_overuse(script: Script, rule: Rule):
    n_par = sum(1 for el in script.elements if el.type == ElementType.PARENTHETICAL)
    n_cues = sum(1 for el in script.elements if el.type == ElementType.CHARACTER)
    if n_cues < int(rule.params.get("min_cues", 10)):
        return
    if n_par / n_cues > float(rule.params.get("max_ratio", 0.30)):
        yield finding(rule, f"{n_par} parentheticals across {n_cues} dialogue blocks "
                            f"({n_par / n_cues:.0%}).",
                      evidence="parenthetical overuse",
                      suggestion="Let the line imply its own delivery.")


@detector("page_count")
def page_count(script: Script, rule: Rule):
    pages = script.estimated_pages
    lo = float(rule.params.get("min_pages", 85))
    hi = float(rule.params.get("max_pages", 125))
    if script.scenes and not lo <= pages <= hi:
        yield finding(rule, f"Estimated length {pages} pages is outside {lo:g}-{hi:g}.",
                      evidence="length outside feature band",
                      suggestion="Fine for a short film; a red flag for a feature spec.")


@detector("scene_numbers")
def scene_numbers(script: Script, rule: Rule):
    for sc in script.scenes:
        if sc.number is not None:
            yield finding(rule, "Scene heading carries a scene number (shooting-script style).",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Strip scene numbers from a spec draft.")


@detector("caps_overuse")
def caps_overuse(script: Script, rule: Rule):
    action = [el for el in script.elements if el.type == ElementType.ACTION]
    if len(action) < int(rule.params.get("min_action_lines", 20)):
        return
    shouted = [el for el in action
               if len(el.text.split()) >= 5 and el.text == el.text.upper()
               and re.search(r"[A-Z]", el.text)]
    ratio = len(shouted) / len(action)
    if ratio > float(rule.params.get("max_ratio", 0.15)):
        yield finding(rule, f"{len(shouted)} of {len(action)} action lines are fully "
                            f"capitalised ({ratio:.0%}).",
                      line_no=shouted[0].line_no, evidence="ALL-CAPS overuse in action",
                      suggestion="Reserve capitals for first appearances, sounds, and key props.")


@detector("exclamation_overuse")
def exclamation_overuse(script: Script, rule: Rule):
    pages = script.estimated_pages
    if pages <= 0 or pages < float(rule.params.get("min_pages", 5)):
        return
    body = [el for el in script.elements
            if el.type in (ElementType.ACTION, ElementType.DIALOGUE)]
    total = sum(el.text.count("!") for el in body)
    per_page = total / pages
    if per_page > float(rule.params.get("max_per_page", 2.0)):
        yield finding(rule, f"{total} exclamation marks over ~{pages} pages "
                            f"({per_page:.1f} per page).",
                      evidence="exclamation overuse",
                      suggestion="Volume on the page is not intensity on the screen.")


@detector("ellipsis_overuse")
def ellipsis_overuse(script: Script, rule: Rule):
    lines = [el for el in script.elements if el.type == ElementType.DIALOGUE]
    if len(lines) < int(rule.params.get("min_lines", 20)):
        return
    hits = [el for el in lines if "..." in el.text or "…" in el.text]
    ratio = len(hits) / len(lines)
    if ratio > float(rule.params.get("max_ratio", 0.20)):
        yield finding(rule, f"{len(hits)} of {len(lines)} dialogue lines trail off "
                            f"({ratio:.0%}).",
                      evidence="ellipsis overuse",
                      suggestion="A tic every character shares flattens all of them.")


@detector("dialogue_ratio")
def dialogue_ratio(script: Script, rule: Rule):
    n_dialogue = sum(1 for el in script.elements if el.type == ElementType.DIALOGUE)
    n_action = sum(1 for el in script.elements if el.type == ElementType.ACTION)
    total = n_dialogue + n_action
    if total < int(rule.params.get("min_lines", 100)):
        return
    ratio = n_dialogue / total
    lo = float(rule.params.get("min_ratio", 0.20))
    hi = float(rule.params.get("max_ratio", 0.70))
    if not lo <= ratio <= hi:
        side = "dialogue-heavy" if ratio > hi else "action-heavy"
        yield finding(rule, f"Dialogue is {ratio:.0%} of the body text ({side}; "
                            f"usual band {lo:.0%}-{hi:.0%}).",
                      evidence="dialogue/action balance outside band",
                      suggestion="Not wrong — but it should be a decision, not an accident.")


@detector("scene_density")
def scene_density(script: Script, rule: Rule):
    pages = script.estimated_pages
    if pages <= 0 or pages < float(rule.params.get("min_pages", 10)):
        return
    density = len(script.scenes) / pages
    lo = float(rule.params.get("min_per_page", 0.3))
    hi = float(rule.params.get("max_per_page", 2.0))
    if not lo <= density <= hi:
        yield finding(rule, f"{len(script.scenes)} scenes over ~{pages} pages "
                            f"({density:.2f} per page; usual band {lo}-{hi}).",
                      evidence="scene density outside band",
                      suggestion="High density means many company moves; low means long scenes.")


# --------------------------------------------------- profile: shooting script

@detector("missing_scene_numbers")
def missing_scene_numbers(script: Script, rule: Rule):
    if not script.scenes:
        return
    unnumbered = [sc for sc in script.scenes if sc.number is None]
    if len(unnumbered) == len(script.scenes):
        yield finding(rule, f"No scene in this draft is numbered ({len(script.scenes)} scenes).",
                      line_no=script.scenes[0].line_no, evidence="shooting draft has no scene numbers",
                      suggestion="Lock the script and number every scene before it goes to a set.")
        return
    for sc in unnumbered:
        yield finding(rule, "Scene has no number in a numbered draft.",
                      line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                      suggestion="Give it the next available letter suffix (e.g. 14A).")


@detector("scene_number_sequence")
def scene_number_sequence(script: Script, rule: Rule):
    numbered = [sc for sc in script.scenes if sc.number]
    seen: dict[str, int] = {}
    prev_key = None
    for sc in numbered:
        if sc.number in seen:
            yield finding(rule, f"Scene number {sc.number} is used more than once.",
                          line_no=sc.line_no, scene_index=sc.index,
                          evidence=f"duplicate scene number {sc.number}",
                          suggestion="Scene numbers must be unique; insert as 14A, 14B, ...")
        seen[sc.number] = sc.index
        if m := SCENE_NUMBER.match(sc.number):
            key = (int(m.group(1)), m.group(2))
            if prev_key is not None and key < prev_key:
                yield finding(rule, f"Scene number {sc.number} goes backwards.",
                              line_no=sc.line_no, scene_index=sc.index,
                              evidence=f"out-of-sequence scene number {sc.number}",
                              suggestion="Numbers ascend; inserted scenes take letter suffixes.")
            prev_key = max(key, prev_key) if prev_key else key


# --------------------------------------------------------- profile: TV pilot

@detector("missing_act_markers")
def missing_act_markers(script: Script, rule: Rule):
    if not script.scenes:
        return
    if not any(ACT_MARKER.match(el.text) for el in _sections(script)):
        yield finding(rule, "No act markers found (COLD OPEN / TEASER / ACT ONE ...).",
                      line_no=script.scenes[0].line_no, evidence="no act structure markers",
                      suggestion="Label the acts; a pilot is delivered and timed by act.")


@detector("act_length_balance")
def act_length_balance(script: Script, rule: Rule):
    acts: dict[str, int] = {}
    for sc in script.scenes:
        if sc.act:
            acts[sc.act] = acts.get(sc.act, 0) + len([e for e in sc.elements if e.text.strip()])
    if len(acts) < 2:
        return
    longest = max(acts, key=acts.get)
    shortest = min(acts, key=acts.get)
    if not acts[shortest]:
        return
    ratio = acts[longest] / acts[shortest]
    if ratio > float(rule.params.get("max_ratio", 2.5)):
        yield finding(rule, f"{longest} is {ratio:.1f}x the length of {shortest}.",
                      evidence=f"act imbalance {longest} vs {shortest}",
                      suggestion="An act break in the wrong place is the usual cause.")


@detector("pilot_page_count")
def pilot_page_count(script: Script, rule: Rule):
    if not script.scenes:
        return
    pages = script.estimated_pages
    half = [float(x) for x in rule.params.get("half_hour", [22, 40])]
    hour = [float(x) for x in rule.params.get("hour", [45, 70])]
    split = float(rule.params.get("split_at", 42))
    band, label = (half, "half-hour") if pages < split else (hour, "one-hour")
    if not band[0] <= pages <= band[1]:
        yield finding(rule, f"Estimated length {pages} pages is outside the {label} band "
                            f"({band[0]:g}-{band[1]:g}).",
                      evidence="pilot length outside format band",
                      suggestion="Pick a format and cut or build to its band.")


# ------------------------------------------------- profile: Indian / regional

@detector("song_cue_format")
def song_cue_format(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.ACTION and SONG_IN_ACTION.search(el.text):
            yield finding(rule, "Song sequence is described in action rather than marked "
                                "as a block.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:80],
                          suggestion="Head it with 'SONG:' or 'SONG SEQUENCE' on its own line — "
                                     "it is a scheduled production unit.")


@detector("interval_marker")
def interval_marker(script: Script, rule: Rule):
    if not script.elements:
        return
    markers = [el for el in _sections(script) if INTERVAL_MARKER.match(el.text)]
    if not markers:
        yield finding(rule, "No INTERVAL marker found.",
                      evidence="no interval marker",
                      suggestion="Place INTERVAL near the midpoint and build the beat before it.")
        return
    expected = float(rule.params.get("expected_at", 0.5))
    tolerance = float(rule.params.get("tolerance", 0.12))
    position = script.elements.index(markers[0]) / max(len(script.elements) - 1, 1)
    if abs(position - expected) > tolerance:
        yield finding(rule, f"INTERVAL falls at {position:.0%} of the script "
                            f"(expected {expected:.0%} ± {tolerance:.0%}).",
                      line_no=markers[0].line_no, evidence="interval placement",
                      suggestion="Rebalance the halves, or move the marker to the real midpoint.")


@detector("mixed_script_cue")
def mixed_script_cue(script: Script, rule: Rule):
    cues = list(script.character_registry())
    native = sorted(c for c in cues if NON_LATIN_SCRIPT.search(c))
    latin = sorted(c for c in cues if not NON_LATIN_SCRIPT.search(c))
    if native and latin:
        yield finding(rule, f"Cues use two writing systems: {len(latin)} in Latin, "
                            f"{len(native)} in a native script.",
                      evidence="mixed writing systems in character cues",
                      suggestion=f"Pick one. Native-script cues: {', '.join(native[:5])}")
