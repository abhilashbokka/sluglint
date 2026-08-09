"""CLI.

  sluglint lint    SCRIPT [--profile P] [--llm] [--json OUT] [--rules PATH]
  sluglint diff    OLD NEW [--profile P] [--llm] [--rules PATH]
  sluglint rules   [--profile P] [--tier N] [--check] [--rules PATH]
  sluglint stats   SCRIPT [--profile P] [--json OUT] [--html OUT]
  sluglint logline SCRIPT [--n 3] [--refresh] [--json OUT]
  sluglint convert SCRIPT.pdf [--out FILE]

SCRIPT may be Fountain text or a PDF; the ingester picks the reader.

A `.sluglint.yaml` beside the script (or anywhere above it) selects the profile
and turns rules off, re-grades them, or retunes their thresholds. `--config`
points at one explicitly; `--no-config` ignores whatever is found.

Exit codes: 0 clean or warnings only, 1 at least one error, 2 bad usage.
That makes `sluglint lint` usable as a pre-commit or CI gate on a script repo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as configmod
from . import diff as diffmod
from . import logline as loglinemod
from . import metrics as metricsmod
from . import report
from .ingest import load_script
from .lint import run_rules, tier3_llm, unimplemented
from .models import Finding, Script
from .rulebook import Rule, load_rulebook, rules_by_tier


def run_lint(script: Script, rules: list[Rule], use_llm: bool,
             profile: str = "") -> tuple[list[Finding], list[str]]:
    """Tiers 1 and 2 always run (free). Tier 3 only on request."""
    findings = run_rules(script, rules_by_tier(rules, 1))
    findings += run_rules(script, rules_by_tier(rules, 2))
    notices: list[str] = []
    if use_llm:
        # Two request shapes, because 14 of the 38 tier-3 rules ask whether the
        # script ever comes back to something and a scene window cannot answer
        # that. The rulebook says which is which; see `Rule.scope`.
        tier3 = rules_by_tier(rules, 3)
        windowed = [r for r in tier3 if r.scope != "document"]
        whole = [r for r in tier3 if r.scope == "document"]
        llm_findings, notices = tier3_llm.run(script, windowed, profile=profile)
        findings += llm_findings
        doc_findings, doc_notices = tier3_llm.run_document_scale(
            script, whole, profile=profile)
        findings += doc_findings
        notices += doc_notices
    else:
        n3 = len(rules_by_tier(rules, 3))
        notices.append(f"Tier 3 not requested ({n3} LLM rules available; pass --llm).")
    return findings, notices


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=None,
                       help="script profile (see `sluglint rules --help`)")
    parser.add_argument("--rules", type=Path, default=None, help="path to an alternate rulebook")
    parser.add_argument("--config", type=Path, default=None,
                        help="path to a .sluglint.yaml (default: search upward from the script)")
    parser.add_argument("--no-config", action="store_true",
                        help="ignore any .sluglint.yaml that would otherwise be found")


def _resolve_config(args) -> configmod.Config:
    """Explicit --config beats discovery; --no-config beats both."""
    if getattr(args, "no_config", False):
        return configmod.Config()
    if getattr(args, "config", None):
        return configmod.load(args.config)
    start = getattr(args, "script", None) or getattr(args, "old", None) or Path.cwd()
    return configmod.discover(start)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sluglint", description="A rule-cited linter for screenplays")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="lint one script")
    pl.add_argument("script", type=Path)
    pl.add_argument("--llm", action="store_true",
                    help="run tier-3 LLM rubric judges (see docs/tier3-providers.md)")
    pl.add_argument("--json", type=Path, default=None, help="also write findings JSON here")
    _add_common(pl)

    pd = sub.add_parser("diff", help="compare two drafts")
    pd.add_argument("old", type=Path)
    pd.add_argument("new", type=Path)
    pd.add_argument("--llm", action="store_true")
    _add_common(pd)

    pr = sub.add_parser("rules", help="list the rulebook")
    pr.add_argument("--tier", type=int, default=None, choices=[1, 2, 3])
    pr.add_argument("--check", action="store_true",
                    help="fail if any tier-1/2 rule has no implementation")
    _add_common(pr)

    ps = sub.add_parser("stats", help="production numbers, with no findings attached")
    ps.add_argument("script", type=Path)
    ps.add_argument("--json", type=Path, default=None, help="also write the numbers here")
    ps.add_argument("--html", type=Path, default=None,
                    help="write the dashboard view here and open it in a browser")
    ps.add_argument("--top", type=int, default=12, help="rows per table (default 12)")
    _add_common(ps)

    pg = sub.add_parser("logline", help="GENERATED synopsis and candidate loglines (needs a key)")
    pg.add_argument("script", type=Path)
    pg.add_argument("--n", type=int, default=3, help="how many logline versions (default 3)")
    pg.add_argument("--refresh", action="store_true", help="ignore the cache and regenerate")
    pg.add_argument("--json", type=Path, default=None, help="also write the summary here")

    pc = sub.add_parser("convert", help="show the Fountain text recovered from a PDF")
    pc.add_argument("script", type=Path)
    pc.add_argument("--out", type=Path, default=None, help="write it here instead of stdout")

    args = p.parse_args(argv)
    if args.cmd == "convert":
        from .ingest.pdf import ingest  # optional dependency, imported on demand
        try:
            result = ingest(args.script)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        for note in result.notes:
            print(f"note: {note}", file=sys.stderr)
        if args.out:
            args.out.write_text(result.fountain, encoding="utf-8")
            print(f"{result.pages} PDF pages written to {args.out}", file=sys.stderr)
        else:
            print(result.fountain)
        return 0

    if args.cmd == "logline":
        try:
            script, _ = load_script(args.script)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        summary, notices = loglinemod.generate(script, n=args.n, refresh=args.refresh)
        if summary is None:
            for note in notices:
                print(f"note: {note}", file=sys.stderr)
            return 2
        print(loglinemod.render_console(summary))
        for note in notices:
            print(f"\nnote: {note}", file=sys.stderr)
        if args.json:
            args.json.write_text(
                json.dumps(summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\nJSON written to {args.json}")
        return 0

    try:
        cfg = _resolve_config(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    book = cfg.apply(load_rulebook(args.rules or cfg.rulebook))
    profile_arg = args.profile or cfg.profile
    try:
        rules = book.for_profile(profile_arg)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    profile = profile_arg or book.default_profile
    if summary := cfg.summary():
        print(f"config: {summary}", file=sys.stderr)

    if args.cmd == "lint":
        try:
            script, ingest_notes = load_script(args.script)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        findings, notices = run_lint(script, rules, args.llm, profile)
        findings = cfg.filter(findings)
        print(report.render_console(script, findings, ingest_notes + notices, profile=profile))
        if args.json:
            args.json.write_text(report.to_json(script, findings, profile=profile),
                                 encoding="utf-8")
            print(f"\nJSON written to {args.json}")
        return 1 if any(f.severity.value == "error" for f in findings) else 0

    if args.cmd == "stats":
        try:
            script, ingest_notes = load_script(args.script)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        m = metricsmod.analyse(script)
        genres = metricsmod.score_genres(m.signals, book.genres) if m.signals else []
        bands = metricsmod.compare(m, book.comparables.get(profile, {}))
        print(report.render_stats_console(m, genres, bands, top=args.top))
        for note in ingest_notes:
            print(f"\nnote: {note}", file=sys.stderr)
        if args.json:
            args.json.write_text(
                report.stats_to_json(m, genres, bands, profile=profile), encoding="utf-8")
            print(f"\nJSON written to {args.json}")
        if args.html:
            from . import dashboard  # noqa: PLC0415 - only needed for this flag
            args.html.write_text(
                "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{script.title or args.script.name} stats</title></head><body>"
                + dashboard.render(m, genres, bands, profile=profile, top=args.top)
                + "</body></html>", encoding="utf-8")
            print(f"\nDashboard written to {args.html}")
        return 0

    if args.cmd == "diff":
        (old_s, _), (new_s, _) = load_script(args.old), load_script(args.new)
        old_f, _ = run_lint(old_s, rules, args.llm, profile)
        new_f, _ = run_lint(new_s, rules, args.llm, profile)
        old_f, new_f = cfg.filter(old_f), cfg.filter(new_f)
        print(report.render_diff_console(diffmod.diff_drafts(old_s, new_s, old_f, new_f)))
        return 0

    if args.cmd == "rules":
        if args.check:
            gaps = unimplemented(rules)
            if gaps:
                print(f"Rules with no implementation: {', '.join(gaps)}", file=sys.stderr)
                return 1
            print(f"All {len(rules)} rules in profile '{profile}' resolve to an "
                  f"implementation or an LLM rubric.")
            return 0
        print(f"Profile: {profile} ({book.profiles[profile].name})")
        print(f"{book.profiles[profile].description}\n")
        shown = [r for r in rules if args.tier is None or r.tier == args.tier]
        for r in shown:
            scope = "" if not r.profiles else f"  [{', '.join(r.profiles)}]"
            print(f"[T{r.tier}] {r.id:<5} {r.severity:<10} {r.name}  ({r.source}){scope}")
        by_tier = {t: sum(1 for r in shown if r.tier == t) for t in (1, 2, 3)}
        print(f"\n{len(shown)} rules  |  tier 1: {by_tier[1]}  tier 2: {by_tier[2]}  "
              f"tier 3: {by_tier[3]}  |  {len(book.rules)} in the full rulebook")
        print(f"Profiles: {', '.join(book.profiles)}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
