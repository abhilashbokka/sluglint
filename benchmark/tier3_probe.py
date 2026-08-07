"""Run tier 3 over a set of scripts and report what each filter caught.

Tier 3 is 38 rubric judges and until now none of them had seen a real
screenplay, so every corpus figure in this project reads "0 of 38 tier-3 rules
fired". This closes that, and it measures the thing worth measuring: not how
many findings the model proposed, but how many survived each hallucination
filter and which filter did the work.

The drop rate is a property of model, rubric, and script together, so the
model is printed next to every number and runs are never pooled across models.
Comparing two models on the same scripts is the point.

    export SLUGLINT_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    export SLUGLINT_LLM_API_KEY_FILE=~/.config/sluglint/gemini.key
    export SLUGLINT_MODEL=gemini-3.6-flash
    python benchmark/tier3_probe.py SCRIPT [SCRIPT ...] --json out.json

See docs/tier3-providers.md for providers, costs, and their data policies.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sluglint.ingest import load_script  # noqa: E402
from sluglint.lint.tier3_llm import DEFAULT_MODEL, FilterStats, run  # noqa: E402
from sluglint.rulebook import load_rulebook, rules_by_tier  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scripts", nargs="+", type=Path)
    ap.add_argument("--profile", default="")
    ap.add_argument("--min-confidence", type=float, default=0.6)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    book = load_rulebook()
    rules = rules_by_tier(book.rules, 3)
    print(f"{len(rules)} tier-3 rules, model {DEFAULT_MODEL}\n", file=sys.stderr)

    rows, totals = [], FilterStats(model=DEFAULT_MODEL)
    for path in args.scripts:
        try:
            script, _ = load_script(path)
        except Exception as exc:                              # noqa: BLE001
            print(f"  refused {path.name}: {exc}", file=sys.stderr)
            continue
        stats = FilterStats()
        started = time.monotonic()
        findings, notices = run(script, rules, profile=args.profile,
                                min_confidence=args.min_confidence, stats=stats)
        elapsed = time.monotonic() - started

        # Which rules actually fired is the other half of the answer: a tier
        # where two rules produce everything is a different object from one
        # where thirty do.
        fired = sorted({f.rule_id for f in findings})
        rows.append({
            "script": path.name, "scenes": len(script.scenes),
            "pages": script.estimated_pages, "seconds": round(elapsed, 1),
            "calls": stats.calls, "failed_calls": stats.failed_calls,
            "proposed": stats.proposed, "accepted": stats.accepted,
            "unknown_rule": stats.dropped_unknown_rule,
            "out_of_window": stats.dropped_out_of_window,
            "low_confidence": stats.dropped_low_confidence,
            "unquotable": stats.dropped_unquotable,
            "rules_fired": fired,
            "findings": [f.to_dict() for f in findings],
        })
        for field in ("calls", "failed_calls", "proposed", "accepted"):
            setattr(totals, field, getattr(totals, field) + getattr(stats, field))
        for field in ("dropped_unknown_rule", "dropped_out_of_window",
                      "dropped_low_confidence", "dropped_unquotable"):
            setattr(totals, field, getattr(totals, field) + getattr(stats, field))
        print(f"  {path.name[:38]:40} {stats.proposed:4} proposed "
              f"{stats.accepted:4} kept  {elapsed:5.0f}s", file=sys.stderr)
        for note in notices:
            if "failed" in note:
                print(f"      {note[:110]}", file=sys.stderr)

    if not rows:
        return 1

    print(f"\n# Tier 3 on {len(rows)} scripts, model {DEFAULT_MODEL}\n")
    print("| Script | Scenes | Calls | Proposed | Kept | Unknown rule | "
          "Out of window | Low confidence | Not quotable |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(f"| {r['script'][:32]} | {r['scenes']} | {r['calls']} | {r['proposed']} | "
              f"{r['accepted']} | {r['unknown_rule']} | {r['out_of_window']} | "
              f"{r['low_confidence']} | {r['unquotable']} |")
    kept_pct = 100.0 * totals.accepted / totals.proposed if totals.proposed else 0.0
    print(f"| **total** | | **{totals.calls}** | **{totals.proposed}** | "
          f"**{totals.accepted}** | {totals.dropped_unknown_rule} | "
          f"{totals.dropped_out_of_window} | {totals.dropped_low_confidence} | "
          f"{totals.dropped_unquotable} |")
    print(f"\n**{totals.accepted} of {totals.proposed} proposed findings survived "
          f"every filter ({kept_pct:.0f}%).**")

    fired = sorted({rid for r in rows for rid in r["rules_fired"]})
    print(f"\n{len(fired)} of {len(rules)} tier-3 rules fired: {', '.join(fired)}")
    silent = sorted({r.id for r in rules} - set(fired))
    print(f"\n{len(silent)} never fired: {', '.join(silent)}")

    if args.json:
        args.json.write_text(json.dumps(
            {"model": DEFAULT_MODEL, "rules": len(rules), "scripts": rows,
             "totals": {"calls": totals.calls, "proposed": totals.proposed,
                        "accepted": totals.accepted,
                        "unknown_rule": totals.dropped_unknown_rule,
                        "out_of_window": totals.dropped_out_of_window,
                        "low_confidence": totals.dropped_low_confidence,
                        "unquotable": totals.dropped_unquotable}}, indent=2))
        print(f"\nwrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
