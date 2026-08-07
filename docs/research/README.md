# Research tracker

Ideas that came out of building Sluglint and might carry a paper. One file per
idea. Each file states a claim, the evidence already in hand, the experiment
still needed, and what it is blocked on.

This is a working tracker. An idea sitting here is not a commitment, and the
most useful thing any entry does is record what would falsify it.

## The board

| # | Idea | Claim in one line | Evidence | Blocked on |
|---|---|---|---|---|
| [01](01-thresholds-vs-practice.md) | Prescriptive thresholds against practice | Quantified craft rules sit far from the distribution of produced work, measurably | **Complete pass**, 36 decision thresholds, 1,082 films, F004 replicated 4x | A corpus of specs, for F008 alone |
| [02](02-fixture-corpus-gap.md) | The fixture-corpus gap | Fixture suites miss a systematic class of rule defect that only a real corpus surfaces | **Strong**, 11 of 11 cases | Nothing |
| [03](03-ingestion-confidence.md) | Ingestion confidence as a gate | A third of real PDFs fail to parse well enough to evaluate, and nobody reports it | **Medium** | Nothing |
| [04](04-dismissal-as-label.md) | Dismissal as label | A dismiss control produces the labelled data a precision measurement needs, for free | **None yet** | Building the UI |
| [05](05-federated-statistics.md) | Federated corpus statistics | Distributional claims about unshareable corpora are reproducible without the corpus | **Partial** | Contributors |
| [06](06-page-runtime-cross-language.md) | Page-to-runtime across languages | The page-a-minute convention is an English typesetting result, and is testable | **None yet** | Data collection |
| [07](07-verifiable-only-analysis.md) | Verifiable-only analysis | A scope boundary drawn at "can you point at it on the page" is implementable and defensible | Artifact | Nothing |

Two working documents sit alongside the ideas:
[corpus-options.md](corpus-options.md) (which public corpus can carry the work,
and why the better-licensed one loses) and
[threshold-results.md](threshold-results.md) (the first pass of 01's table).

Measured facts, with provenance and how to reproduce them, live in
[evidence.md](evidence.md). Cite that file rather than restating numbers, so
there is one place to correct when a number changes.

---

## Assessment

**01 and 02 are the real ones, in that order.** Both survive without a precision
number and without tier 3, which is what makes them writable now. They are
different claims for different audiences and should stay two papers. Merging
them would produce something that argues two things and establishes neither.

**01 is done except for one row.** 1,082 films, 882,948 action paragraphs, every
parameter classified, the harness committed, the genre and draft-stage splits
run. F004 has four measurements across three corpora and two languages. The only
thing still open is F008, and it is open for a reason that is itself a result:
produced screenplays are a later artifact than the drafts that rule addresses.

**01's shape changed and improved.** The taxonomy came out of the pass and is a
contribution on its own: of 91 numeric parameters, only 36 are decision
thresholds, 26 are activation gates, and 13 cannot be measured from a document.
A paper claiming to have measured 91 thresholds would be wrong about what it
measured. And the genre split is a clean negative: a threshold that fails, fails
in every genre, so genre-aware defaults would buy nothing.

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

**The rules-are-data claim has 16 exceptions.** An AST walk of the detector
modules finds 16 numeric literals used in a comparison or a scaling that never
came from `rule.params`, and four of them are why the harness disagrees with the
linter on four rules. Any paper describing a data-driven rule engine should
report that number about itself, because it is the form the claim usually fails
in and nobody measures it.

**249 findings per 100 pages is a finding.** It stands without any labelling,
because no screenplay contains that density of genuine defects. The better
statistic underneath it is instances per distinct issue: 209 findings on
Pellichoopulu are 41 unique issues, a 5.1x compression, and that ratio is a
label-free precision proxy that can be computed over the whole corpus today.
Proposing it as a metric is a small contribution inside 02.

**The best case on the board is now F013, and it belongs to both papers.** It
was going to be a retuning: the first pass measured it too strict and the number
was going to move. Splitting the corpus by draft stage showed it flagging 52% of
numbered headings and 0.8% of unnumbered ones, because a shooting script prints
its scene number at both margins and the rule measured the string as printed.
The threshold was right; the quantity was wrong. Its fixture existed, passed
before the fix and after it, and could never have caught this, because nobody
writes scene numbers into a hand-made fixture.

That makes F013 the exact inverse of F004 and the pair is the argument for 01:
**a quantified rule can fail because its number is wrong, or because the thing
it counts is wrong, and the second is invisible to every check that would catch
the first.** For 02 it is the sharpest instance of class 7, a measurement error
that reads as a finding about the world. Two more of that class are now in hand:
page counts a third low, and scene pages up to 30% long.

**Do not write about the three-tier architecture yet.** A quarter of the
rulebook has never touched real input. The blocker is now gone: tier 3 speaks
to any OpenAI-compatible endpoint, several of which are permanently free, and
`FilterStats` counts what each hallucination filter caught. See
[../tier3-providers.md](../tier3-providers.md).

That also turns a weak claim into a strong one. A single Claude run would have
produced one drop rate, and "we filter hallucinations" is not a finding. **The
same rubrics against three models gives three drop rates**, and a weaker model
whose filters catch more is evidence the filters work rather than evidence the
model is bad. Watch the licence line: the corpus cannot go to a provider that
trains on prompts.

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
