# CLAUDE.md, Sluglint

## What this project is

A **rule-cited screenplay linter**. Every finding must
trace to a rule in `src/sluglint/rulebook.yaml` with severity, source attribution,
location, and a suggested fix. Positioning: objective/verifiable defects (the
crowded "AI coverage" market sells subjective opinions and we deliberately do not).

Three-tier engine. **T1** deterministic format lint (pure code), then **T2**
consistency engine over parsed structure (registries, timeline, fuzzy matching),
then **T3** LLM rubric judges for soft/craft rules (Claude, one scoped rubric per
rule).

**101 rules across 4 profiles** (`us-spec-feature` default, `tv-pilot`,
`shooting-script`, `indian-regional`). A rule with no `profiles:` key applies to
all; one that lists them applies only to those.

## Commands

Work inside the project venv. Never install into the system or anaconda Python:
the extras here (`pdfplumber`, `anthropic`) are the project's, not the machine's.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,pdf,llm]"                  # dev only: drop pdf and llm

pytest -q                                        # 128 tests, must stay green
ruff check . && pylint src/sluglint              # must stay clean (10.00/10)

python -m sluglint.cli lint examples/the_last_train.fountain
python -m sluglint.cli lint script.pdf                  # needs the [pdf] extra
python -m sluglint.cli convert script.pdf               # inspect the recovered Fountain
python -m sluglint.cli lint --profile tv-pilot examples/night_shift_pilot.fountain
python -m sluglint.cli diff examples/the_last_train.fountain examples/the_last_train_v2.fountain
python -m sluglint.cli rules --tier 2            # browse
python -m sluglint.cli rules --check             # fail if a rule has no handler
```

`pytest` and imports work without `PYTHONPATH`, `pyproject.toml` sets
`pythonpath = ["src"]`.

Tier 3 needs `ANTHROPIC_API_KEY`; model default `claude-sonnet-5` (override with
`SLUGLINT_MODEL`). Missing key must never crash, tiers 1-2 run, tier 3 reports
itself skipped. Keep it that way.

## Architecture map

| Path | Role |
|---|---|
| `src/sluglint/rulebook.yaml` | THE product. 101 rules + 4 profile definitions, as data. |
| `src/sluglint/ingest/pdf.py` | PDF to Fountain by margin geometry. Learns the document's own margins, drops printer furniture, refuses PDFs it cannot read. `pdfplumber` behind the `pdf` extra. |
| `src/sluglint/parser.py` | Fountain-lite → `Script{Scenes[Elements]}`. Forgiving on purpose. Keeps raw lines, extensions, dual markers, scene numbers, act markers. |
| `src/sluglint/models.py` | Dataclasses. `Finding.fingerprint` powers draft diffing. |
| `src/sluglint/rulebook.py` | YAML loader, `Rule`, `Profile`, profile filtering. |
| `src/sluglint/lint/registry.py` | `@detector(key)` registry + `finding()` factory. The ONLY rule→code mapping. |
| `src/sluglint/lint/tier1_format.py` | How elements are written (headings, cues, hygiene, action lines). |
| `src/sluglint/lint/tier1_metrics.py` | Document ratios + profile-gated structure rules. |
| `src/sluglint/lint/tier2_consistency.py` | Identity, place/time, structural continuity. |
| `src/sluglint/lint/tier2_production.py` | Cast size, location load, night ratio, lead absence. |
| `src/sluglint/lint/tier3_llm.py` | Claude judges: rubric build, chunking, schema-enforced JSON, hallucination filters. |
| `src/sluglint/diff.py` | Resolved/new/persisting findings + scene-level diff. |
| `src/sluglint/report.py` | Console/JSON rendering. |
| `src/sluglint/cli.py` | `lint` / `diff` / `rules`. |
| `examples/` | `clean_pages` (must stay clean), one fixture per profile, the v1 to v2 diff pair. |
| `benchmark/` | Fault-injection mutators, measured recall, draft-drift demo. `corpus/` is gitignored. |
| `tests/` | 128 tests. Positive fixture per deterministic rule + clean-script gate. |
| `docs/` | Competitive landscape, product and business model, script licensing. |

## Hard rules for working in this repo

1. **Never reproduce text from screenwriting books.** Rule `principle:` fields
   are original formulations; `source:` attributes where the idea is taught.
   Adding quoted book content is a copyright problem and is forbidden.
2. **Rules are data.** New checks go through `rulebook.yaml`. T1/T2 checks add a
   `detect:` key + a `@detector` handler; T3 rules need zero code (rubric is
   built from the YAML). Never hardcode a rule's text, severity, or threshold in
   Python, read thresholds from `rule.params`.
3. **Every rule must be provably alive.** `sluglint rules --check` must pass, and
   every T1/T2 rule needs a positive fixture in `SNIPPETS` / `PROFILE_SNIPPETS`.
   `test_snippet_coverage_is_complete` enforces this.
4. **Precision over recall.** `examples/clean_pages.fountain` must produce zero
   errors and zero warnings in every profile. Where a naive check would
   over-fire, narrow it by anchoring on a second signal (an age parenthetical,
   an article before a capitalised prop, a known cue name). T3 keeps its
   hallucination filters (known rule id, in-window scene index, verbatim
   evidence check, confidence threshold), never remove them to boost recall.
5. **The parser is forgiving; the linters complain.** Malformed input must still
   parse, a parse failure on bad formatting would hide the very defects we
   exist to report.
6. **Fingerprint stability.** `Finding.fingerprint` excludes line numbers so
   draft diffs work. Script-level metric findings use *stable* evidence strings
   (counts belong in `message` and `evidence` stays fixed). Preserve this or diffs churn.
7. **No heavyweight deps** in core (`pyyaml` only). `anthropic` stays optional
   behind the `llm` extra with guarded import.
8. **Tests, lint, and the benchmark stay green.** If you change a fixture, update
   `tests/test_sluglint.py` in the same commit. Keep the README's badges truthful
   (test count, rule count, pylint score), CI checks the rule count.
9. **This repo is PUBLIC.** No API keys, tokens, or personal data in code,
   fixtures, or git history, ever. Config via env vars only.
   No third-party screenplay text is ever committed. `benchmark/corpus/` is
   gitignored for exactly that reason; see `docs/public-domain-scripts.md`.
10. **Scope boundary, do not cross it.** Sluglint checks the screenplay as a
    *document*: formatting, internal consistency (characters, locations, time),
    and craft rules about how scenes and lines are written. It does NOT evaluate
    plot logic, premise, theme, or whether the story is good. Never add a rule
    that requires judging story quality, and never let README or marketing copy
    imply we do, the whole positioning rests on claiming only what is
    verifiable. Rules like S005 (passive protagonist) and S006 (late inciting
    disruption) sit at the edge of this line: they are `suggestion` severity and
    flag observable patterns rather than verdicts on the story.
11. **Licence boundary is permanent.** The project is PolyForm Noncommercial:
    free for writers and noncommercial use, paid for commercial use. Every rule
    stays visible and stays free for noncommercial use, forever. Paid features
    live around the engine (hosting, teams, exports) and never inside it. Never
    move a rule behind a paywall.

12. **No em dashes anywhere.** Not in prose, code comments, docstrings, or the
    rulebook. Python source is ASCII; typographic characters the linter hunts
    for are written as `\uXXXX` escapes. Also avoid the "X, not Y" antithesis
    construction; say the thing plainly instead.

## Branching

`main` (protected, releasable) ← `develop` (integration) ← short-lived
`feat/…` `fix/…` `rule/…` `docs/…`. PRs into `develop`; release PRs
`develop → main`. See `CONTRIBUTING.md` and `.github/pull_request_template.md`.

## Prioritized next steps

1. **OCR fallback for PDFs the geometry reader refuses.** Pre-Unicode Indic
   fonts and scans. Apple Vision (`ocrmac`) does not cover Telugu or
   Devanagari, so this needs Tesseract `tel`/`hin`, capability-gated the way
   tier 3 is. See `docs/pdf-ingestion.md`.
2. **Precision measurement.** `benchmark/` already measures recall (97% on
   injected defects). Precision on real scripts is spot-checked on a private
   corpus, not measured at scale. Closing it needs either a Creative Commons
   corpus or a human verdict per finding.
3. **FDX ingestion.** XML with element types already named; much easier than PDF.
4. **Story-bible extraction** (T2.5): one LLM pass building props/story-day/fact
   registries; feed existing tier-2 style checks over that structure.
5. **Batch + caching for T3**: findings cache keyed by (scene text hash, rule id,
   model) so re-lints of unchanged scenes are free.
6. **FastAPI service** wrapping `run_lint`, then a web UI with an annotated
   script view and accept/dismiss per finding, that feedback loop is the
   labelled data the eval harness wants.
7. **More profiles**: stage play, radio drama, documentary; more regional
   conventions.

## Context: why this exists

Personal project by Abhi (AI/ML engineer + screenwriter). Also serves as a
demonstrable LLM-engineering artifact: rubric-based LLM-as-judge with structured
output contracts, hallucination filtering, eval-first methodology, and
cost-tiered architecture (deterministic → structured → LLM). Keep the code
interview-walkable: small modules, docstrings that explain *why*, no cleverness
for its own sake.
