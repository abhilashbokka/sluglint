# Evidence ledger

Every measured number this project can cite, with where it came from and how to
regenerate it. Cite this file from the idea documents rather than restating a
number, so there is one place to correct.

Numbers here were produced on the corpus described in
[../corpus-sweep.md](../corpus-sweep.md), which is not redistributable.

Last regenerated: 2026-08-06.

---

## Engine state

| Fact | Value | How |
|---|---|---|
| Rules | 150 | `sluglint rules` |
| Rules carrying numeric params | **54** (30 tier 1, 24 tier 2) | `[r for r in book.rules if r.params]` |
| Profiles | 4 | `us-spec-feature`, `tv-pilot`, `shooting-script`, `indian-regional` |
| Rules resolving per profile | 139 / 142 / 139 / 142 | `sluglint rules --check --profile X` |
| Tests | 208 | `pytest -q` |
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
| Sample needed for per-rule figures | ~900, stratified at 10 per firing rule | 92 rules fired |

## The corpus sweep

| Fact | Value |
|---|---|
| Files | 56 |
| Read (trusted) | **33** |
| Suspect | 16 |
| Refused | 7 |
| Pages, trusted | 1,771 |
| Findings, trusted | **6,504** |
| Findings per 100 pages, trusted | **367** |
| Findings, all readable (49 docs, 2,933 pp) | 11,265 |
| Errors / warnings / suggestions, trusted | 247 / 2,461 / 3,796 |
| Rules that fired | 92 of 150 |
| Tier-3 rules that fired | **0 of 38** (sweep ran with the LLM tier off) |
| Top 12 rules' share of all findings | **61%** |
| Pass history | 18,421 → 13,894 → 12,672 → 11,265 |

## The F004 distribution

Action-paragraph line counts across **18,299 paragraphs in 19 produced
screenplays**:

| Lines | Share | Cumulative |
|---:|---:|---:|
| 1 | 55.4% | 55.4% |
| 2 | 24.2% | 79.6% |
| 3 | 10.5% | 90.1% |
| 4 | 4.6% | 94.7% |
| 6 | | 98% |
| 8 | | 99% |

Taught value: 4 lines, which is **p95**. Shipped value: 7 lines, which is
**p98.6**. Longest observed block: 31 lines (Parasite).

Not yet reproducible by a committed script. `benchmark/thresholds.py` is the
missing harness and is the immediate next step for
[01](01-thresholds-vs-practice.md).

## The eight defects

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

Not yet verified by ablation that the fixture suite passes with each defect
reinstated. That measurement is pending and is cheap.

## Volume and grouping

| Fact | Value |
|---|---|
| Pellichoopulu findings | 209 |
| Pellichoopulu unique rules | **41** (3 errors, 12 warnings, 26 suggestions) |
| Compression | **5.1x** |
| F062, findings / documents | 264 / 5 = **53 per document** |
| F021 | 303 / 17 = 18 per document |
| F014 | 255 / 16 = 16 per document |

## Ingest

| Fact | Value |
|---|---|
| Trusted share of readable PDFs | 33 of 49, **67%** |
| Telugu documents reading cleanly | **3 of 7** |
| English documents reading cleanly | 13 of 17 |
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
