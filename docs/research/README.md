# Research tracker

Ideas that came out of building Sluglint and might carry a paper. One file per
idea. Each file states a claim, the evidence already in hand, the experiment
still needed, and what it is blocked on.

This is a working tracker. An idea sitting here is not a commitment, and the
most useful thing any entry does is record what would falsify it.

## The board

| # | Idea | Claim in one line | Evidence | Blocked on |
|---|---|---|---|---|
| [01](01-thresholds-vs-practice.md) | Prescriptive thresholds against practice | Quantified craft rules sit far from the distribution of produced work, measurably | **Strong**, one worked case | Corpus size |
| [02](02-fixture-corpus-gap.md) | The fixture-corpus gap | Fixture suites miss a systematic class of rule defect that only a real corpus surfaces | **Strong**, 8 of 8 cases | Nothing |
| [03](03-ingestion-confidence.md) | Ingestion confidence as a gate | A third of real PDFs fail to parse well enough to evaluate, and nobody reports it | **Medium** | Nothing |
| [04](04-dismissal-as-label.md) | Dismissal as label | A dismiss control produces the labelled data a precision measurement needs, for free | **None yet** | Building the UI |
| [05](05-federated-statistics.md) | Federated corpus statistics | Distributional claims about unshareable corpora are reproducible without the corpus | **Partial** | Contributors |
| [06](06-page-runtime-cross-language.md) | Page-to-runtime across languages | The page-a-minute convention is an English typesetting result, and is testable | **None yet** | Data collection |
| [07](07-verifiable-only-analysis.md) | Verifiable-only analysis | A scope boundary drawn at "can you point at it on the page" is implementable and defensible | Artifact | Nothing |

Measured facts, with provenance and how to reproduce them, live in
[evidence.md](evidence.md). Cite that file rather than restating numbers, so
there is one place to correct when a number changes.

---

## Assessment

**01 and 02 are the real ones, in that order.** Both survive without a precision
number and without tier 3, which is what makes them writable now. They are
different claims for different audiences and should stay two papers. Merging
them would produce something that argues two things and establishes neither.

**01 needs one thing it does not have: n.** Nineteen produced English
screenplays is enough for one worked example and too few for a percentile claim
at the tail, which is exactly where the interesting thresholds sit. Four of the
seventeen English documents are flagged suspect, so the usable set is smaller
still. Fifty documents would make the 95th and 99th percentiles reportable. This
gates the paper harder than tier 3 does.

**Sharpen 01's framing.** The finding is not that a book is wrong. Craft
teaching states an ideal a writer should aim at, and a linter needs a decision
threshold that separates a defect from ordinary practice. Those are different
objects, and nobody has measured the distance between them. That framing is
harder to dismiss, it explains why the books are not being called incompetent,
and it makes the result actionable: the rule keeps the taught number as an
opt-in, and ships the measured one.

**The selection bias argues for the result, not against it.** The corpus skews
toward award-season and critically celebrated films, because that is the
mechanism that puts a shooting script online. If the scripts held up as
exemplary are the ones violating the taught threshold, the threshold is not
describing good practice.

**367 findings per 100 pages is a finding.** It stands without any labelling,
because no screenplay contains that density of genuine defects. The better
statistic underneath it is instances per distinct issue: 209 findings on
Pellichoopulu are 41 unique issues, a 5.1x compression, and that ratio is a
label-free precision proxy that can be computed over the whole corpus today.
Proposing it as a metric is a small contribution inside 02.

**Do not write about the three-tier architecture yet.** A quarter of the
rulebook has never touched real input. Run tier 3 on five documents with
per-filter counters first; the drop rate of each hallucination filter is a
result in its own right and it costs about twenty dollars to obtain.

**04 is the highest-leverage new idea.** It converts the precision problem from
"we could not measure it" into "here is a mechanism that measures it
continuously as the tool is used". It is cheap, it needs to be designed in
before the UI ships rather than retrofitted, and it changes what 01 and 02 can
each claim in their limitations sections.

**05 is the unlock for 01.** It is also the honest answer to the corpus problem
generally: page counts and paragraph-length distributions are facts about a
document, and facts are not copyrightable expression. A contributor runs a
command locally and mails a small JSON they can read in full. That is a far
smaller ask than a screenplay, and it makes the threshold result reproducible by
a third party who also cannot redistribute their corpus.

**06 and 07 are real but secondary.** 06 is a genuinely novel small question
with a clever free ground truth (censor certificates state film length in
metres), and it is entirely blocked on data collection. 07 is a position piece
and reads better as a white paper or as a section inside 01 than as a paper.

## What is missing from this list

Two gaps worth naming rather than pretending away.

**No user study.** Every claim here is about the tool's output. Nothing measures
whether a writer's draft improves, or whether they act on a finding. That is the
question a reviewer will ask about any of these, and the answer is currently
"unknown".

**No baseline.** None of these compare Sluglint against another system, because
the comparable products sell subjective coverage and do not expose per-rule
output. For 01 that does not matter, since the claim is about thresholds rather
than about the tool. For anything framed as "our system performs better", it
matters completely, and that framing should be avoided.
