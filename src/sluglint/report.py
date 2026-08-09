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


def _pages(script: Script) -> tuple[dict[int, int], dict[int, int]]:
    """Real page per source line and per scene, empty when the source has none.

    A PDF records the page every line printed on, so a finding can point at
    the page a writer is looking at instead of a line number in a file that
    was reconstructed from it. Fountain text has no pages and gets neither.
    """
    by_line = {el.line_no: el.page for el in script.elements if el.page is not None}
    by_scene = {sc.index: sc.page for sc in script.scenes if sc.page is not None}
    return by_line, by_scene


def render_console(script: Script, findings: list[Finding], notices: list[str],
                   profile: str = "") -> str:
    header = f"Sluglint: {script.title or script.path}"
    by_line, by_scene = _pages(script)
    # A PDF states its length; only a text draft has to be measured.
    about = "" if script.page_count else "~"
    lines = [
        header,
        f"{len(script.scenes)} scenes | {about}{script.estimated_pages:g} pages | "
        f"{len(script.character_registry())} speaking characters"
        + (f" | profile: {profile}" if profile else ""),
        "=" * RULE_WIDTH,
    ]
    if not findings:
        lines.append("No findings. Clean draft.")
    for f in _sorted(findings):
        if f.line_no:
            loc, page = f"L{f.line_no}", by_line.get(f.line_no)
        elif f.scene_index is not None:
            loc, page = f"scene {f.scene_index + 1}", by_scene.get(f.scene_index)
        else:
            loc, page = "script", None
        if page:
            loc = f"{loc} p{page}"
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
            lines += [f"  {ICON[f.severity]} {f.rule_id} {f.rule_name}: {f.message}"
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


# ----------------------------------------------------------------- stats view

def _bar(value: float, peak: float, width: int = 22) -> str:
    """A proportional bar. Terminals are the first dashboard anyone gets."""
    if peak <= 0:
        return ""
    filled = max(1, round(width * value / peak)) if value > 0 else 0
    return "#" * filled + "." * (width - filled)


def _clip(text: str, width: int) -> str:
    """Truncate a comma-separated list at a comma, never mid-number."""
    if len(text) <= width:
        return text
    head = text[:width].rsplit(",", 1)[0]
    return f"{head}, ..."


def _band_line(check) -> str:
    mark = "  ok " if check.inside else f" {check.verdict:>4}"
    return f"  [{mark}] {check.signal:<16} {check.value:<9} band {check.low:g} to {check.high:g}"


def render_stats_console(metrics, genres=None, comparables=None, top: int = 12) -> str:
    """The production numbers, with no finding and no verdict anywhere in it."""
    m = metrics
    out = [
        f"Sluglint stats: {m.title or 'untitled'}",
        f"~{m.pages} pages, read as ~{m.runtime_minutes:.0f} minutes at a page a minute",
        f"{m.scene_count} scenes | {m.speaking_cast} speaking cast | "
        f"{m.location_count} locations | {m.company_moves} company moves",
        f"day {m.day_pages:g}pp / night {m.night_pages:g}pp ({m.night_share:.0%} night) | "
        f"INT {m.interior_pages:g}pp / EXT {m.exterior_pages:g}pp",
        "=" * RULE_WIDTH,
    ]

    if m.characters:
        peak = m.characters[0].present_pages or 1.0
        out += ["", "CAST  (present pages, an upper bound on screen time)", ""]
        for c in m.characters[:top]:
            flag = " (voice only)" if c.voice_only else ""
            out.append(
                f"  {c.name[:22]:<22} {_bar(c.present_pages, peak)} "
                f"{c.present_pages:>6.1f}pp  {c.dialogue_lines:>4} lines  "
                f"{len(c.scenes):>3} sc  {c.speaking_share:>5.1%}{flag}")
        if len(m.characters) > top:
            out.append(f"  ... and {len(m.characters) - top} more speaking parts")

        # Age, pronoun, and role are read back from what the script writes down.
        # A dash is an honest answer and is the common one.
        out += ["", "AS THE SCRIPT DESCRIBES THEM  (extracted, never inferred from a name)",
                "  A dash means the page does not say. 'unclear' means two people share too",
                "  many sentences for the pronoun to be attributed to one of them.", ""]
        out.append(f"  {'character':<22} {'age':<8} {'pronoun':<9} {'on pages':<12} "
                   f"{'role as written':<20} scenes")
        for c in m.characters[:top]:
            pages = f"{c.page_first:g}-{c.page_last:g}"
            out.append(
                f"  {c.name[:22]:<22} {(c.age_band or '-'):<8} "
                f"{('-' if c.pronoun == 'unspecified' else c.pronoun):<9} {pages:<12} "
                f"{(c.role or '-')[:20]:<20} {_clip(c.timeline, 30)}")

    if m.network and m.network.nodes:
        g = m.network
        groups = [grp for grp in g.components if len(grp) > 1]
        out += ["", "WHO PLAYS AGAINST WHOM  (two people share an edge when they share a scene)", ""]
        out.append(f"  {g.density:.0%} of all possible pairings actually share a scene")
        out.append(f"  {len(groups)} group(s) of two or more; "
                   f"{len(g.isolated)} never in a room with another speaker")
        if g.cut_vertices:
            out.append(f"  only link between two groups: {', '.join(g.cut_vertices[:6])}")
        if g.isolated:
            out.append(f"  never share a scene: {', '.join(g.isolated[:6])}")
        out.append("")
        for node in g.nodes[:min(top, 8)]:
            mark = " *" if node.cut_vertex else "  "
            out.append(f"  {node.name[:22]:<22}{mark} plays against {node.degree:>3} of the cast "
                       f"({node.reach:.0%})  {node.weighted_degree:>4} shared scenes")

    if m.locations:
        peak = m.locations[0].pages or 1.0
        out += ["", "LOCATIONS  (page load, which is what a schedule is built from)", ""]
        for loc in m.locations[:top]:
            where = "INT/EXT" if loc.interior and loc.exterior else (
                "EXT" if loc.exterior else "INT")
            out.append(
                f"  {loc.name[:22]:<22} {_bar(loc.pages, peak)} "
                f"{loc.eighths:>7}  {len(loc.scenes):>3} sc  D{loc.day_scenes}/N{loc.night_scenes}"
                f"  {where}")
        if len(m.locations) > top:
            out.append(f"  ... and {len(m.locations) - top} more locations")

    if comparables:
        out += ["", "AGAINST THE PROFILE BANDS", ""]
        out += [_band_line(c) for c in comparables]

    if genres:
        out += ["", "GENRE SIGNATURE  (bands over measurements, not a verdict)", ""]
        for g in genres[:3]:
            inside = ", ".join(c.signal for c in g.checks if c.inside) or "nothing"
            out.append(f"  {g.name:<20} {g.matched}/{g.total} bands: {inside}")
        out.append("")
        out.append("  These bands are conventional heuristics, not measured from a")
        out.append("  corpus. Read a match as a prompt to look, never as a fact.")

    if m.signals:
        out += ["", "RAW SIGNALS", ""]
        for k, v in m.signals.as_dict().items():
            out.append(f"  {k:<24} {v}")
    return "\n".join(out)


def stats_to_json(metrics, genres=None, comparables=None, profile: str = "") -> str:
    payload = {"profile": profile, "metrics": metrics.to_dict()}
    if genres:
        payload["genres"] = [
            {"key": g.key, "name": g.name, "matched": g.matched, "total": g.total,
             "score": g.score,
             "checks": [{"signal": c.signal, "value": c.value, "low": c.low,
                         "high": c.high, "verdict": c.verdict} for c in g.checks]}
            for g in genres]
    if comparables:
        payload["comparables"] = [
            {"signal": c.signal, "value": c.value, "low": c.low, "high": c.high,
             "verdict": c.verdict} for c in comparables]
    return json.dumps(payload, indent=2, ensure_ascii=False)
