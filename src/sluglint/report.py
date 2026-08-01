"""Render findings and draft diffs for humans (console) and machines (JSON).

The console report groups by severity because that is the order a writer
fixes in: errors are unambiguous defects, warnings are near-certain, and
suggestions are craft notes they may reasonably reject.
"""
from __future__ import annotations

import json

from .diff import DraftDiff
from .models import Finding, Script, Severity

ICON = {Severity.ERROR: "[E]", Severity.WARNING: "[W]", Severity.SUGGESTION: "[S]"}
ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.SUGGESTION: 2}
RULE_WIDTH = 72


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (ORDER[f.severity], f.line_no or 10**9, f.rule_id))


def render_console(script: Script, findings: list[Finding], notices: list[str],
                   profile: str = "") -> str:
    header = f"Sluglint — {script.title or script.path}"
    lines = [
        header,
        f"{len(script.scenes)} scenes | ~{script.estimated_pages} pages | "
        f"{len(script.character_registry())} speaking characters"
        + (f" | profile: {profile}" if profile else ""),
        "=" * RULE_WIDTH,
    ]
    if not findings:
        lines.append("No findings. Clean draft.")
    for f in _sorted(findings):
        loc = f"L{f.line_no}" if f.line_no else (
            f"scene {f.scene_index + 1}" if f.scene_index is not None else "script")
        conf = f" (conf {f.confidence:.2f})" if f.tier == 3 else ""
        lines.append(f"{ICON[f.severity]} {f.rule_id} {f.rule_name} @ {loc}{conf}")
        lines.append(f"    {f.message}")
        if f.evidence:
            lines.append(f"    > {f.evidence[:100]}")
        if f.suggestion:
            lines.append(f"    fix: {f.suggestion}")
        if f.source:
            lines.append(f"    rule source: {f.source}")
    counts = {s: sum(1 for f in findings if f.severity == s) for s in Severity}
    lines.append("-" * RULE_WIDTH)
    lines.append(f"{counts[Severity.ERROR]} errors, {counts[Severity.WARNING]} warnings, "
                 f"{counts[Severity.SUGGESTION]} suggestions")
    lines.extend(f"note: {n}" for n in notices)
    return "\n".join(lines)


def render_diff_console(diff: DraftDiff) -> str:
    fd = diff.findings
    lines = [
        "Draft comparison",
        "=" * RULE_WIDTH,
        f"Pages: {diff.old_pages} -> {diff.new_pages}",
        f"Findings: {len(fd.resolved)} resolved, {len(fd.introduced)} new, "
        f"{len(fd.persisting)} persisting",
        "",
    ]
    for label, group in (("RESOLVED", fd.resolved), ("NEW", fd.introduced),
                         ("PERSISTING", fd.persisting)):
        if group:
            lines.append(f"{label}:")
            lines += [f"  {ICON[f.severity]} {f.rule_id} {f.rule_name} — {f.message}"
                      for f in _sorted(group)]
            lines.append("")
    if diff.scenes:
        lines.append("Scene changes:")
        for ch in diff.scenes:
            extra = f" (similarity {ch.similarity})" if ch.kind == "modified" else ""
            lines.append(f"  {ch.kind:<9} {ch.heading}{extra}")
    return "\n".join(lines)


def to_json(script: Script, findings: list[Finding], profile: str = "") -> str:
    return json.dumps({
        "script": {"path": script.path, "title": script.title,
                   "scenes": len(script.scenes), "estimated_pages": script.estimated_pages,
                   "speaking_characters": len(script.character_registry())},
        "profile": profile,
        "summary": {s.value: sum(1 for f in findings if f.severity == s) for s in Severity},
        "findings": [f.to_dict() for f in _sorted(findings)],
    }, indent=2)
