# Threshold results, first pass

The experiment from [01](01-thresholds-vs-practice.md), run for the first time.
Eleven of the 54 rules that carry numeric params, measured against produced
practice.

**Headline: F004 replicates on an independent corpus, and two more thresholds
fail the same way it did.**

## Method

250 films sampled deterministically from ScriptBase (every eighth archive of
994 listed), parsed with Sluglint, no rules run. See
[corpus-options.md](corpus-options.md) for why this corpus and not the
better-licensed one.

**36 of 250 excluded** for parsing to no scenes or under 20 pages. Those are
crawls that kept HTML scaffolding, transcripts, and fragments. The exclusion is
the same three-state gate the PDF reader uses, and the count is reported rather
than quietly dropped. See [03](03-ingestion-confidence.md).

**214 scripts, 28,730 scenes, 189,078 action paragraphs.** Years 1931 to 2012,
median 1999. Genres, which a film can carry several of: Drama 118, Thriller 78,
Comedy 70, Crime 62, Action 52, Romance 50, Sci-Fi 32, Adventure 30,
Biography 30, Mystery 28.

The median action wrap width is 60 characters, so this corpus is already at
standard measure and the normalisation warned about in
[corpus-options.md](corpus-options.md) turns out to matter less than expected.

## Element-level thresholds

Where the shipped value sits in the distribution of produced practice.

| Rule | Quantity | Ships at | Percentile | p90 | p95 | p99 | Max | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|
| F004 | lines per action paragraph | 7 | **p98.7** | 4 | 5 | 8 | 1119 | holds |
| F016 | lines per dialogue block | 6 | p97.3 | 4 | 5 | 9 | 132 | holds |
| **F013** | characters per scene heading | 60 | **p87.0** | 67 | 71 | 77 | 288 | **too strict** |
| F017 | words per parenthetical | 5 | p96.4 | 4 | 5 | 10 | 78 | holds |
| F064 | words per character cue | 5 | p99.9 | 2 | 2 | 3 | 10 | holds |

**F013 flags one scene heading in eight.** The threshold is 60 characters and
p90 of practice is 67. This is the same failure as F004: a number that describes
an ideal heading, used as the line between a defect and ordinary writing.

## Document-level bands

| Rule | Band | Below | Above | Median | Verdict |
|---|---|---:|---:|---:|---|
| F008 | pages 85 to 125 | 3% | **42%** | 122.2 | loose fit, 45% outside |
| C020 | cast per page, max 0.6 | | 19% | 0.37 | loose fit |
| **C021** | locations per page, max 0.35 | | **88%** | 0.68 | **band is wrong** |
| C022 | night share, max 0.6 | | 14% | 0.41 | loose fit |
| F037 | scenes per page, 0.3 to 2.0 | 4% | 6% | 1.07 | holds |
| F036 | dialogue share, 0.2 to 0.7 | 9% | 7% | 0.50 | loose fit |

**C021 is the strongest result on this page.** The threshold permits 0.35
distinct locations per page. The median produced screenplay runs 0.68, and
**88% sit above the line**. The threshold is near the 5th percentile of
practice, which means the rule is not describing an unusual document, it is
describing almost every document.

**F008 fails asymmetrically**, which is informative. Only 3% of scripts are
shorter than the 85-page floor, so the low end is well calibrated. 42% run past
the 125-page ceiling. Caveat worth keeping: ScriptBase skews toward shooting
scripts, which run longer than the spec drafts this band was written for. This
row needs the profile split before it can be reported as a finding.

**F037 holds cleanly**, 4% below and 6% above with the median mid-band. Worth
reporting as much as the failures are: the claim is that thresholds are often
miscalibrated, not that they always are.

## The F004 replication

| Lines | Share | Cumulative | PDF corpus |
|---:|---:|---:|---:|
| 1 | 55.4% | 55.4% | 55.4% |
| 2 | 22.9% | 78.4% | 79.6% |
| 3 | 11.2% | 89.5% | 90.1% |
| 4 | 4.9% | **94.5%** | **94.7%** |
| 5 | 2.3% | 96.8% | |
| 6 | 1.2% | 98.0% | |
| 7 | 0.7% | **98.7%** | **98.6%** |
| 8 | 0.4% | 99.1% | |

Taught value 4: **p94.5 here, p94.7 on the PDFs.** Shipped value 7: **p98.7
here, p98.6 there.** 189,078 paragraphs against 18,299, a crawled text corpus
against a set of PDFs read by margin geometry, 214 films against 19.

The original finding was not an artifact of nineteen documents.

## A result about the harness, not the world

The first two runs of this table produced different verdicts, and both were
wrong, because the page counter was broken. Recorded here because it is the
most transferable thing on the page.

| Rule | Pass 1 outside band | Pass 2 | Final |
|---|---:|---:|---:|
| F037 scenes per page | 42% | 7% | 9% |
| C020 cast per page | 39% | 13% | 19% |
| F008 pages | 67%, low | 68%, high | 45%, high |
| C021 locations per page | 81% | 83% | 88% |

Pass 1 divided non-blank elements by 55 lines per page, understating every
script by a third. Pass 2 wrapped every element to the standard column, which
double-counted a corpus that had already wrapped its own lines. Only the third
pass, which detects whether a source is pre-wrapped, is trustworthy.

Three of six verdicts flipped between passes. Had the table been published from
pass 1, three findings would have been wrong, and each would have looked like a
statement about screenwriting rather than a bug in a page counter. This belongs
in [02](02-fixture-corpus-gap.md) as a seventh defect class: **a measurement
error in the harness reads as a finding about the world**, and nothing in the
output distinguishes the two.

Only C021 survived unchanged across all three passes, which is why it is the
result reported with most confidence.

## What is not done

**43 of 54 thresholds are unmeasured.** The eleven here were the ones computable
from what the probe already collected. The rest need per-rule quantities
extracted, which is the `benchmark/thresholds.py` harness that still does not
exist.

**No profile split.** F008 in particular cannot be read without separating spec
drafts from shooting scripts, and ScriptBase does not label draft stage. Scene
numbering is a usable proxy and is already detected.

**No genre split.** The metadata is there and unused. Whether a threshold that
fails overall holds within a genre is the obvious next question, and the corpus
supports it: Drama 118, Thriller 78, Comedy 70.

**Single corpus.** F004 has two independent measurements. Nothing else here has
more than one.
