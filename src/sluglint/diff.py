"""Draft comparison.

Two layers:
  1. Findings diff: resolved / new / persisting, keyed by Finding.fingerprint
     (rule + normalized evidence), so a note survives text moving to a
     different page and dies when the underlying defect is actually fixed.
  2. Structural diff: scenes added / removed / modified, matched by
     normalized heading with fuzzy content comparison.

This is the retention loop: re-upload draft 2, see exactly what you fixed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .models import Finding, Script


@dataclass
class FindingsDiff:
    resolved: list[Finding] = field(default_factory=list)   # in old, gone in new
    introduced: list[Finding] = field(default_factory=list)  # new in new
    persisting: list[Finding] = field(default_factory=list)  # in both


@dataclass
class SceneChange:
    kind: str          # added | removed | modified
    heading: str
    similarity: float = 1.0


@dataclass
class DraftDiff:
    findings: FindingsDiff
    scenes: list[SceneChange]
    old_pages: float
    new_pages: float


def diff_findings(old: list[Finding], new: list[Finding]) -> FindingsDiff:
    old_fp = {f.fingerprint: f for f in old}
    new_fp = {f.fingerprint: f for f in new}
    return FindingsDiff(
        resolved=[f for fp, f in old_fp.items() if fp not in new_fp],
        introduced=[f for fp, f in new_fp.items() if fp not in old_fp],
        persisting=[f for fp, f in new_fp.items() if fp in old_fp],
    )


def _norm_heading(h: str) -> str:
    return " ".join(h.upper().split())


def diff_scenes(old: Script, new: Script, modified_below: float = 0.98) -> list[SceneChange]:
    old_map: dict[str, list] = {}
    for s in old.scenes:
        old_map.setdefault(_norm_heading(s.heading), []).append(s)
    changes: list[SceneChange] = []
    for s in new.scenes:
        key = _norm_heading(s.heading)
        if old_map.get(key):
            prev = old_map[key].pop(0)
            ratio = SequenceMatcher(None, prev.text, s.text).ratio()
            if ratio < modified_below:
                changes.append(SceneChange("modified", s.heading, round(ratio, 3)))
        else:
            changes.append(SceneChange("added", s.heading))
    for leftovers in old_map.values():
        changes.extend(SceneChange("removed", s.heading) for s in leftovers)
    return changes


def diff_drafts(old_script: Script, new_script: Script,
                old_findings: list[Finding], new_findings: list[Finding]) -> DraftDiff:
    return DraftDiff(
        findings=diff_findings(old_findings, new_findings),
        scenes=diff_scenes(old_script, new_script),
        old_pages=old_script.estimated_pages,
        new_pages=new_script.estimated_pages,
    )
