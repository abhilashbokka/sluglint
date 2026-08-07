# Evidence ledger

Every measured number this project can cite, with where it came from and how to
regenerate it. Cite this file from the idea documents rather than restating a
number, so there is one place to correct.

Numbers here were produced on the corpus described in
[../corpus-sweep.md](../corpus-sweep.md), which is not redistributable.

Last regenerated: 2026-08-07, after the page-count fix. Every per-page
number on this page moved by about a third; the old ones were wrong.

---

## Engine state

| Fact | Value | How |
|---|---|---|
| Rules | 150 | `sluglint rules` |
| Rules carrying numeric params | **54** (30 tier 1, 24 tier 2) | `[r for r in book.rules if r.params]` |
| Profiles | 4 | `us-spec-feature`, `tv-pilot`, `shooting-script`, `indian-regional` |
| Rules resolving per profile | 139 / 142 / 139 / 142 | `sluglint rules --check --profile X` |
| Tests | 213 | `pytest -q` |
| pylint | 10.00/10 | `pylint src/sluglint` |
| Clean-fixture findings | 0 errors, 0 warnings, all profiles | `test_clean_script_is_clean` |

## Recall

| Fact | Value | How |
|---|---|---|
| Injected-defect recall | **97%, 64 of 66** | `python benchmark/run.py` |
| Corpus | 7 scripts, seeded (`--seed 7`) | |
| Misses | C019 abbreviated location 50%, F025 pagination 86% | |
| Baseline findings on unmutated corpus | **54** across 7 scripts | `benchmark/REPORT.md` |

Recall is measured on defects that were injected, which is a different quantity
from recall on defects that occur naturally. No number exists for the second.

## Precision

**No precision figure exists.** No finding in any corpus run carries a human
verdict.

| Fact | Value | Note |
|---|---|---|
| Upper bound on pre-sweep precision | **at most 61%** | 7,156 of 18,421 findings removed after being confirmed wrong by reading |
| Post-sweep precision | unmeasured | |
| Sample needed for an overall figure | ~400 findings | ±5% at 95% confidence |
| Sample needed for per-rule figures | ~900, stratified at 10 per firing rule | 93 rules fired |

## The corpus sweep

| Fact | Value |
|---|---|
| Files | 60 |
| Read (trusted) | **36** |
| Suspect | 17 |
| Refused | 7 |
| Pages, trusted | 2,995 |
| Findings, trusted | **7,445** |
| Findings per 100 pages, trusted | **249** |
| Findings, all readable (53 docs, 4,884 pp) | 12,671 |
| Errors / warnings / suggestions, trusted | 283 / 3,003 / 4,159 |
| Rules that fired | 93 of 150 |
| Tier-3 rules that fired | **0 of 38** (sweep ran with the LLM tier off) |
| Top 12 rules' share of all findings | **60%** |

An earlier run of this table reported 367 findings per 100 pages across 1,771
pages. Both were wrong: page counts were a third low. Do not cite them.

## The F004 distribution

Two independent measurements. The second is the one to cite.

**ScriptBase, 214 gated scripts, 189,078 action paragraphs:** taught value 4
sits at **p94.5**, shipped value 7 at **p98.7**. Full table and method in
[threshold-results.md](threshold-results.md).

**PDF corpus, 19 produced screenplays, 18,299 paragraphs:**

| Lines | Share | Cumulative |
|---:|---:|---:|
| 1 | 55.4% | 55.4% |
| 2 | 24.2% | 79.6% |
| 3 | 10.5% | 90.1% |
| 4 | 4.6% | 94.7% |
| 6 | | 98% |
| 8 | | 99% |

Taught value 4 is **p94.7**, shipped value 7 is **p98.6**. The two corpora
agree to within half a percentage point at both points.

Longest block observed: 1,119 lines (ScriptBase), 31 lines (Parasite, PDF).

Not yet reproducible by a committed script. `benchmark/thresholds.py` is the
missing harness and is the immediate next step for
[01](01-thresholds-vs-practice.md).

## The nine defects

| Rule | Before | After | Class |
|---|---:|---:|---|
| F002 | 2,070 | 921 | lexical for semantic |
| F004 | 2,043 | 635 | threshold from authority |
| F009 | 1,925 | 18 | context misassignment |
| F049 | 1,342 | 1 | habit per occurrence |
| F028 | 1,266 | 251 | upstream artifact |
| F011 | 424 | 240 | habit per occurrence |
| F055 | 274 | 61 | upstream artifact |
| ingest | n/a | 2 flagged | missing plausibility bound |
| pages | a third low | exact | **measurement error in the harness** |

The ninth is the page counter, found later and worse than the other eight: a
PDF's real page count was never used, and the derived estimate divided
non-blank elements by 55 lines per page. Measured against seven scripts with
known page counts the ratio was 0.66. It flipped three of six threshold
verdicts in [threshold-results.md](threshold-results.md) before it was caught.

Not yet verified by ablation that the fixture suite passes with each defect
reinstated. That measurement is pending and is cheap.

## Thresholds measured against practice

Eleven of 54 rules with numeric params. Full table in
[threshold-results.md](threshold-results.md).

| Rule | Ships at | Sits at | Verdict |
|---|---:|---:|---|
| F004 lines per action paragraph | 7 | p98.7 | holds |
| F016 lines per dialogue block | 6 | p97.3 | holds |
| **F013 characters per scene heading** | 60 | **p87.0** | **too strict** |
| F017 words per parenthetical | 5 | p96.4 | holds |
| F064 words per character cue | 5 | p99.9 | holds |
| F037 scenes per page | 0.3 to 2.0 | 10% outside | holds |
| C020 cast per page | 0.6 | 19% above | loose |
| **C021 locations per page** | 0.35 | **88% above** | **band is wrong** |
| C022 night share | 0.6 | 14% above | loose |
| F036 dialogue share | 0.2 to 0.7 | 16% outside | loose |
| F008 pages | 85 to 125 | 3% below, 42% above | needs a profile split |

Corpus: ScriptBase, 250 sampled, 36 excluded by the parse gate, **214 scripts,
28,730 scenes, 189,078 action paragraphs**, years 1931 to 2012.

## Corpus overlap

| Fact | Value |
|---|---|
| MovieSum titles | 2,164 |
| ScriptBase titles | 994 listed |
| In both | **826** |
| Overlap | 83% of ScriptBase, 38% of MovieSum |

MovieSum is Penn Treebank tokenized and reflowed, so it cannot carry any
line, character, or punctuation threshold. See
[corpus-options.md](corpus-options.md).

## Volume and grouping

| Fact | Value |
|---|---|
| Pellichoopulu findings | 209 |
| Pellichoopulu unique rules | **41** (3 errors, 12 warnings, 26 suggestions) |
| Compression | **5.1x** |
| F062, findings / documents | 272 / 6 = **45 per document** |
| F025 | 124 / 5 = 25 per document |
| C005 | 532 / 23 = 23 per document |
| F016 | 690 / 33 = 21 per document |

## Ingest

| Fact | Value |
|---|---|
| Trusted share of readable PDFs | 36 of 53, **68%** |
| Telugu documents reading cleanly | **6 of 11** |
| English documents reading cleanly | 13 of 17 |
| ScriptBase files parsing to no scenes | **36 of 250, 14%** |
| Density ceiling | 3.0 scenes per page |
| Documents exceeding it before the fix | 2, at 5.7 and 6.2 |

## Rules that never fired

| Group | Count | Note |
|---|---:|---|
| Tier 3 | 38 | the tier was off |
| Tier 1 | 13 | includes profile-gated pilot rules with no pilot in the corpus |
| Tier 2 | 2 | C022, C027 |

F026, F060, and F061 are structurally unreachable through the PDF path, because
ingest rebuilds clean Fountain. They can only fire on Fountain input.
