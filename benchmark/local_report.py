"""Lint a private corpus and write the results somewhere git will not take them.

`run.py` measures recall by injecting known defects into scripts we own. This
is the other half: point it at real scripts, read what comes back, and decide by
hand whether each finding is right. That is the only way precision gets
measured, and it is what turned up most of the engine bugs fixed so far.

The output names real scripts and quotes them, so it is written to
`benchmark/local/`, which `.gitignore` keeps out of a public repo. Read
`docs/public-domain-scripts.md` before deciding to publish any of it.

    python benchmark/local_report.py ~/Scripts --profile indian-regional
    python benchmark/local_report.py a.pdf b.fountain --out /tmp/report
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sluglint.cli import run_lint  # noqa: E402
from sluglint.ingest import load_script  # noqa: E402
from sluglint.rulebook import load_rulebook  # noqa: E402

SUFFIXES = {".pdf", ".fountain", ".txt", ".spmd"}
DEFAULT_OUT = Path(__file__).resolve().parent / "local"


def collect(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            found += sorted(q for q in p.rglob("*") if q.suffix.lower() in SUFFIXES)
        elif p.suffix.lower() in SUFFIXES:
            found.append(p)
    return found


def lint_one(path: Path, rules, profile: str):
    try:
        script, notes = load_script(path)
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop the sweep
        return None, [f"could not read: {type(exc).__name__}: {exc}"], []
    findings, _ = run_lint(script, rules, False, profile)
    return script, notes, findings


def render_script(path: Path, script, notes, findings, names, severities) -> str:
    out = [f"# {path.name}", ""]
    if script is None:
        return "\n".join(out + [f"**Unreadable.** {notes[0]}", ""])
    counts = collections.Counter(f.severity.value for f in findings)
    out += [
        f"- Estimated length: **{script.estimated_pages:.0f} pages**",
        f"- Scenes: **{len(script.scenes)}**",
        f"- Speaking cues: **{len(script.character_registry())}**",
        f"- Findings: **{len(findings)}** "
        f"({counts['error']} errors, {counts['warning']} warnings, "
        f"{counts['suggestion']} suggestions)",
        "",
    ]
    if notes:
        out += ["## Ingest notes", ""] + [f"- {n}" for n in notes] + [""]
    out += ["## By rule", "", "| Rule | Severity | Count | Name |", "|---|---|--:|---|"]
    for rid, n in collections.Counter(f.rule_id for f in findings).most_common():
        out.append(f"| {rid} | {severities[rid]} | {n} | {names[rid]} |")
    out += ["", "## Every finding", ""]
    for f in sorted(findings, key=lambda x: (x.severity.value, x.rule_id, x.line_no or 0)):
        where = f"L{f.line_no}" if f.line_no else "script"
        out.append(f"- `{f.rule_id}` [{f.severity.value}] {where}: {f.message}")
        if f.evidence:
            out.append(f"  - evidence: `{f.evidence[:160]}`")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("paths", nargs="+", type=Path, help="scripts or directories of scripts")
    p.add_argument("--profile", default="indian-regional")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--rules", type=Path, default=None)
    args = p.parse_args(argv)

    book = load_rulebook(args.rules)
    rules = book.for_profile(args.profile)
    names = {r.id: r.name for r in book.rules}
    severities = {r.id: r.severity for r in book.rules}

    scripts = collect(args.paths)
    if not scripts:
        print("No scripts found.", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    summary = [
        "# Local corpus results",
        "",
        f"Profile: `{args.profile}`. {len(scripts)} files.",
        "",
        "Not for publication. These name real scripts and quote them; see",
        "`docs/public-domain-scripts.md`.",
        "",
        "| Script | Pages | Scenes | Cues | Errors | Warnings | Suggestions | Read |",
        "|---|--:|--:|--:|--:|--:|--:|---|",
    ]
    readable = unreadable = 0
    for path in scripts:
        script, notes, findings = lint_one(path, rules, args.profile)
        slug = path.stem.replace(" ", "_")[:60]
        (args.out / f"{slug}.md").write_text(
            render_script(path, script, notes, findings, names, severities), encoding="utf-8")
        if script is None or not script.scenes:
            unreadable += 1
            summary.append(f"| {path.name} | | | | | | | refused |")
            continue
        readable += 1
        c = collections.Counter(f.severity.value for f in findings)
        # A note beginning with 'Text layer' or 'Only' is the ingester saying it
        # does not trust what it read; that belongs in the table, not buried.
        flag = "clean" if not any(n.startswith(("Text layer", "Only", "31%", "71%")) or
                                  "not screenplay geometry" in n for n in notes) else "suspect"
        summary.append(
            f"| {path.name} | {script.estimated_pages:.0f} | {len(script.scenes)} | "
            f"{len(script.character_registry())} | {c['error']} | {c['warning']} | "
            f"{c['suggestion']} | {flag} |")
        print(f"{path.name}: {len(findings)} findings ({flag})")

    summary += ["", f"Readable: {readable}. Refused or empty: {unreadable}.", ""]
    (args.out / "README.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"\nWritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
