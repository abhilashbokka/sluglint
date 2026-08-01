"""Tier 2 — production and volume metrics.

These rules answer questions a line producer asks before a script goes into
prep: how many speaking parts, how many distinct sets, what share of the
schedule is nights, is any single scene a whole day on one location. None of
them says the script is bad. They say the script has a number, and the number
is knowable now rather than in prep.

Like the tier-1 metrics, each of these yields ONE script-level finding with a
FIXED evidence string, so the count can move between drafts without the draft
diff reporting a brand new problem.
"""
from __future__ import annotations

from ..models import Script
from ..rulebook import Rule
from .registry import detector, finding


@detector("cast_size")
def cast_size(script: Script, rule: Rule):
    pages = script.estimated_pages
    if pages <= 0 or pages < float(rule.params.get("min_pages", 20)):
        return
    speaking = len(script.character_registry())
    per_page = speaking / pages
    if per_page > float(rule.params.get("max_speaking_per_page", 0.6)):
        yield finding(rule, f"{speaking} speaking parts over ~{pages} pages "
                            f"({per_page:.2f} per page).",
                      evidence="speaking cast size relative to length",
                      suggestion="Every named speaker is a contract and a call-sheet row. "
                                 "Merge the ones who serve the same function.")


@detector("location_load")
def location_load(script: Script, rule: Rule):
    pages = script.estimated_pages
    if pages <= 0 or pages < float(rule.params.get("min_pages", 20)):
        return
    locations = {(s.location or "").strip().upper() for s in script.scenes if s.location}
    per_page = len(locations) / pages
    if per_page > float(rule.params.get("max_per_page", 0.35)):
        yield finding(rule, f"{len(locations)} distinct locations over ~{pages} pages "
                            f"({per_page:.2f} per page).",
                      evidence="distinct location count relative to length",
                      suggestion="Locations drive company moves. Combining two sets buys a day.")


@detector("night_ratio")
def night_ratio(script: Script, rule: Rule):
    timed = [s for s in script.scenes if s.time_of_day]
    if len(timed) < int(rule.params.get("min_scenes", 15)):
        return
    night = [s for s in timed
             if s.time_of_day in {"NIGHT", "DUSK", "DAWN", "EVENING", "MIDNIGHT"}]
    ratio = len(night) / len(timed)
    if ratio > float(rule.params.get("max_ratio", 0.6)):
        yield finding(rule, f"{len(night)} of {len(timed)} timed scenes are night or "
                            f"low-light ({ratio:.0%}).",
                      evidence="night scene share",
                      suggestion="Night pages cost more than day pages. Worth knowing now.")


@detector("scene_length")
def scene_length(script: Script, rule: Rule):
    limit = float(rule.params.get("max_pages", 4.0))
    for sc in script.scenes:
        if sc.estimated_pages > limit:
            yield finding(rule, f"Scene runs ~{sc.estimated_pages} pages (max {limit:g}).",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="A scene this long is a shooting day on one set.")


@detector("lead_absence_gap")
def lead_absence_gap(script: Script, rule: Rule):
    if len(script.scenes) < int(rule.params.get("min_scenes", 8)):
        return
    counts = script.dialogue_counts()
    if not counts:
        return
    lead = max(counts, key=counts.get)
    present = set(script.character_registry().get(lead, []))
    longest, run, start, run_start = 0, 0, 0, 0
    for sc in script.scenes:
        if sc.index in present:
            run, run_start = 0, sc.index + 1
        else:
            run += 1
            if run > longest:
                longest, start = run, run_start
    ratio = longest / len(script.scenes)
    if ratio > float(rule.params.get("max_gap_ratio", 0.25)):
        yield finding(rule, f"'{lead}' — the most-spoken character — is absent for "
                            f"{longest} consecutive scenes ({ratio:.0%} of the script), "
                            f"from scene {start + 1}.",
                      scene_index=start, evidence=f"{lead} absence gap",
                      suggestion="Usually a subplot that grew during a rewrite.")


@detector("dialogue_share")
def dialogue_share(script: Script, rule: Rule):
    counts = script.dialogue_counts()
    total = sum(counts.values())
    if (len(counts) < int(rule.params.get("min_speakers", 4))
            or total < int(rule.params.get("min_lines", 40))):
        return
    lead = max(counts, key=counts.get)
    share = counts[lead] / total
    if share > float(rule.params.get("max_share", 0.45)):
        yield finding(rule, f"'{lead}' speaks {share:.0%} of all dialogue lines "
                            f"({counts[lead]} of {total}) across {len(counts)} speakers.",
                      evidence=f"{lead} dialogue share",
                      suggestion="Fine for a one-hander; worth checking in an ensemble.")


@detector("late_series_regular")
def late_series_regular(script: Script, rule: Rule):
    n = len(script.scenes)
    if not n:
        return
    cutoff = float(rule.params.get("introduce_before", 0.5))
    min_scenes = int(rule.params.get("min_scenes", 3))
    for name, scene_idxs in script.character_registry().items():
        if len(scene_idxs) < min_scenes:
            continue
        first = min(scene_idxs) / n
        if first > cutoff:
            yield finding(rule, f"'{name}' recurs in {len(scene_idxs)} scenes but first speaks "
                                f"at {first:.0%} of the pilot.",
                          scene_index=min(scene_idxs), evidence=f"{name} introduced late",
                          suggestion="A pilot introduces the cast the series runs on. "
                                     "Bring them in earlier.")
