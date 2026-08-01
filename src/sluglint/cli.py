"""CLI.

  sluglint lint  SCRIPT [--profile P] [--llm] [--json OUT] [--rules PATH]
  sluglint diff  OLD NEW [--profile P] [--llm] [--rules PATH]
  sluglint rules [--profile P] [--tier N] [--check] [--rules PATH]

Exit codes: 0 clean or warnings only, 1 at least one error, 2 bad usage.
That makes `sluglint lint` usable as a pre-commit or CI gate on a script repo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import diff as diffmod
from . import report
from .lint import run_rules, tier3_llm, unimplemented
from .models import Finding, Script
from .parser import parse_file
from .rulebook import Rule, load_rulebook, rules_by_tier


def run_lint(script: Script, rules: list[Rule], use_llm: bool) -> tuple[list[Finding], list[str]]:
    """Tiers 1 and 2 always run (free). Tier 3 only on request."""
    findings = run_rules(script, rules_by_tier(rules, 1))
    findings += run_rules(script, rules_by_tier(rules, 2))
    notices: list[str] = []
    if use_llm:
        llm_findings, notices = tier3_llm.run(script, rules_by_tier(rules, 3))
        findings += llm_findings
    else:
        n3 = len(rules_by_tier(rules, 3))
        notices.append(f"Tier 3 not requested ({n3} LLM rules available; pass --llm).")
    return findings, notices


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=None,
                       help="script profile (see `sluglint rules --help`)")
    parser.add_argument("--rules", type=Path, default=None, help="path to an alternate rulebook")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sluglint", description="A rule-cited linter for screenplays")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="lint one script")
    pl.add_argument("script", type=Path)
    pl.add_argument("--llm", action="store_true", help="run tier-3 LLM rubric judges")
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

    args = p.parse_args(argv)
    book = load_rulebook(args.rules)
    try:
        rules = book.for_profile(args.profile)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    profile = args.profile or book.default_profile

    if args.cmd == "lint":
        script = parse_file(args.script)
        findings, notices = run_lint(script, rules, args.llm)
        print(report.render_console(script, findings, notices, profile=profile))
        if args.json:
            args.json.write_text(report.to_json(script, findings, profile=profile),
                                 encoding="utf-8")
            print(f"\nJSON written to {args.json}")
        return 1 if any(f.severity.value == "error" for f in findings) else 0

    if args.cmd == "diff":
        old_s, new_s = parse_file(args.old), parse_file(args.new)
        old_f, _ = run_lint(old_s, rules, args.llm)
        new_f, _ = run_lint(new_s, rules, args.llm)
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
