# Evidence ledger

Every measured number this project can cite, with where it came from and how to
regenerate it. Cite this file from the idea documents rather than restating a
number, so there is one place to correct.

Numbers here were produced on the corpus described in
[../corpus-sweep.md](../corpus-sweep.md), which is not redistributable.

Last regenerated: 2026-08-07, after the full threshold pass on 1,082 films.
Threshold numbers from the 214-film first pass are superseded; where a figure
changed, the old one is marked rather than deleted.

---

## Engine state

| Fact | Value | How |
|---|---|---|
| Rules | 150 | `sluglint rules` |
| Rules carrying numeric params | **54** (30 tier 1, 24 tier 2) | `[r for r in book.rules if r.params]` |
| Profiles | 4 | `us-spec-feature`, `tv-pilot`, `shooting-script`, `indian-regional` |
| Rules resolving per profile | 139 / 142 / 139 / 142 | `sluglint rules --check --profile X` |
| Tests | 215 | `pytest -q` |
| pylint | 10.00/10 | `pylint src/sluglint` |
| Clean-fixture findings | 0 errors, 0 warnings, all profiles | `test_clean_script_stays_clean` |

The clean-fixture gate excludes document-scale rules by name, because the
fixture is 1.6 pages and F008 correctly reports that a 1.6-page draft is not a
feature. That exemption is in the test rather than implicit.

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

Four measurements across three corpora and two languages. Cite the third row.

| Corpus | Paragraphs | Taught value 4 | Shipped value 7 |
|---|---:|---:|---:|
| PDF, 19 produced screenplays | 18,299 | p94.7 | p98.6 |
| ScriptBase, 214 films (superseded) | 189,078 | p94.5 | p98.7 |
| **ScriptBase, 1,082 films** | **884,746** | **p93.6** | **p98.3** |
| Telugu, 7 drafts | 10,811 | p94.3 | p98.0 |

Reproduce with `python benchmark/thresholds.py CORPUS --label NAME`.

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

## The eleven defects

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
| pages | a third low | exact | measurement error, document scale |
| scene pages | up to 30% long | 0.5% drift | measurement error, element scale |
| F013 | 52% of numbered headings | 0.8% | measures the wrong string |

The last three are all class 7, a measurement error that reads as a finding
about the world, and none was found by reading findings.

**Pages.** A PDF's real page count was never used, and the derived estimate
divided non-blank elements by 55 lines per page. Measured against seven scripts
with known page counts the ratio was 0.66. It flipped three of six threshold
verdicts before it was caught.

**Scene pages.** `Scene.estimated_pages` asked each scene whether the source had
wrapped its own lines. That test needs forty action lines and a scene rarely has
forty, so scenes in a wrapped document measured up to 30% long and two scenes in
one document could disagree. Affects C023, C029, F047. Scene pages now reconcile
to the document within 0.5%, and to a stated PDF page count within 0.6%.

**F013.** Detailed in [threshold-results.md](threshold-results.md).

Not yet verified by ablation that the fixture suite passes with each defect
reinstated. Three of the eleven are already known to: the suite was green before
and after each fix.

## Thresholds measured against practice

Complete pass. Full tables, method, and per-container results in
[threshold-results.md](threshold-results.md).

| Fact | Value |
|---|---|
| Rules carrying numeric params | 54 |
| Individual parameters | 91 |
| **Decision thresholds** (measured) | **36** |
| Activation gates (share of corpus silenced, reported) | 26 |
| Unmeasurable from a document (named, not guessed) | 13 |
| Decision thresholds flagging over 1 unit in 10, as shipped | **19 of 36** |
| Extractors agreeing exactly with their detector | **32 of 36** |
| Numeric literals in detector code, not in the rulebook | **16** |

**The four changed by this pass:**

| Rule | Was | Flagged | Now | Flags |
|---|---:|---:|---:|---:|
| C021 locations per page | 0.35 | 88.4% | 1.15 | 10.4% |
| C028 cuts that change location | 0.85 | 96.4% | 0.99 | 14.1% |
| C038 parts in the opening tenth | 8 | 64.6% | 23 | 9.4% |
| F013 characters per scene heading | 60 | 14.8% | 60, code fixed | 1.4% |

F008 was measured at 55.6% outside its band and deliberately **not** retuned: a
produced screenplay is a later artifact than the spec the rule addresses.

Corpus: ScriptBase alpha, all **1,276 archives**, 194 excluded by the gate
(170 no scenes, 21 unsegmented, 2 under 20 pages, 1 duplicate), **1,082
documents, 149,310 scenes, 882,948 action paragraphs**, years 1926 to 2013.

An earlier entry reported 11 thresholds against 214 films and put F013 at p87.
Both the frame and that verdict were wrong: the GitHub contents API truncated
the corpus listing at 1,000 of 1,276 archives, and F013 was measuring a scene
number. Do not cite them.

## Containers

Never pooled. Each is measured and reported under its own name.

| Container | Documents | Read rate | Note |
|---|---:|---|---|
| english-produced | 1,082 | 1,082 of 1,276 (85%) | ScriptBase alpha crawl |
| telugu | 7 | 7 of 10 unique (70%) | PDF, all state their own page count |
| english-pdf | 17 | 17 of 17 | includes the 7 with known page counts |

## Corpus integrity

| Check | english-produced | telugu |
|---|---:|---:|
| Sources that broke their own lines | 819 | 0 |
| **Documents within 15% of the wrap-decision cut** | **219** | 3 |
| Scene pages vs document, median drift | 0.33% | 0.05% |
| Elements orphaned before the first heading, median | 0.27% | 0.05% |

219 of 1,082 documents sit near the boundary where the wrap decision flips, and
flipping it changes that document's page count by about a third. That is the
fragility under every per-page figure on this page.

## Page ground truth

Seven PDFs with a known page count, all exact after the fix:

| Script | True | Sluglint | Scenes sum to |
|---|---:|---:|---:|
| Parasite | 144 | 144 | 144.0 |
| Her | 106 | 106 | 106.1 |
| 2001 | 65 | 65 | 65.0 |
| The Matrix | 133 | 133 | 133.2 |
| Whiplash | 114 | 114 | 114.2 |
| The Shining | 148 | 148 | 148.3 |
| Inside Out | 130 | 130 | 130.8 |

## Genre

Share of the population each threshold flags, inside each genre. The result is
negative and that is the useful part: a threshold that fails, fails everywhere.

| Rule | Drama 573 | Thriller 412 | Comedy 313 | Action 264 | Crime 260 | Romance 214 |
|---|---:|---:|---:|---:|---:|---:|
| F004 action paragraph | 1.9% | 1.7% | 1.9% | 1.6% | 1.7% | 1.7% |
| C021 locations per page (pre-retune) | 88.0% | 88.6% | 84.3% | 91.3% | 88.8% | 87.9% |
| **F033 exclamations per page** | 15.4% | 12.6% | **30.4%** | 22.3% | **11.5%** | 16.4% |
| **F036 dialogue share** | 17.1% | 12.6% | **26.2%** | 13.3% | **11.5%** | 23.8% |

Only F033 and F036 show a genre gap larger than the roughly 9-point margin that
a 214-to-573-film comparison carries. Per-genre thresholds would need about
2,400 films per genre.

## Draft stage

Split on scene numbering: 284 production drafts, 798 spec-style.

| Rule | Production | Spec-style | All |
|---|---:|---:|---:|
| **F013 heading length, before the fix** | **52.4%** | **0.8%** | 14.8% |
| F013 heading length, after the fix | 3.1% | 0.7% | 1.4% |
| F008 pages | 64.4% | 52.5% | 55.6% |
| C021 locations per page | 90.1% | 87.7% | 88.4% |

## Corpus overlap

| Fact | Value |
|---|---|
| MovieSum titles | 2,164 |
| ScriptBase alpha archives | **1,276** (994 in the first pass; the listing API truncated) |
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
