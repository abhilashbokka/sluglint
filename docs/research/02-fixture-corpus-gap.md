# 02. The fixture-corpus gap

**Status: strong. Eight of eight cases in hand. Not blocked on anything.**

## Claim

A rule-based analysis system evaluated against hand-written fixtures develops a
systematic blind spot: rules that are correct about a single instance and wrong
about a document. That class of defect is invisible to fixtures by construction,
because the fixture is written by the same person who wrote the rule and encodes
the same assumption. Only a real corpus surfaces it.

The secondary claim, which is the one practitioners will use: **volume is a
precision failure mode**. A rule that reports a real defect a hundred times
buries the one thing the reader needed to see, and the usual precision measure
does not notice, because every one of those hundred is technically a true
positive.

## Evidence

213 fixture tests passing, ruff clean, pylint 10.00. Pointing the same engine at
53 real screenplays surfaced **nine defects, none of which any fixture caught**.
Full account in [../corpus-sweep.md](../corpus-sweep.md).

| Rule | Before | After | Class |
|---|---:|---:|---|
| F009 | 1,925 | 18 | wrong profile assumed |
| F049 | 1,342 | 1 | document-scale habit per occurrence |
| F002 | 2,070 | 921 | lexical match where semantic was meant |
| F028 | 1,266 | 251 | element-boundary artifact from ingest |
| F055 | 274 | 61 | same |
| F004 | 2,043 | 635 | threshold inherited from authority |
| F011 | 424 | 240 | document-scale habit per occurrence |
| ingest | n/a | 2 flagged | no plausibility ceiling |
| pages | a third low | exact | harness measurement error |

Corpus total moved 18,421 to 11,265, a 39% reduction, every removal confirmed
wrong by reading.

**A taxonomy of six classes**, which is the transferable part:

1. **Context misassignment.** The rule is right for one class of document and
   was applied to another (F009: scene numbers are correct in a shooting
   script).
2. **Habit reported as repeated error.** One authorial decision, N reports
   (F049, F011, and still F062 at 53 reports per document).
3. **Lexical standing in for semantic.** The check matched a spelling where it
   meant a meaning (F002 fired on `LATE AFTERNOON`).
4. **Upstream artifact read as content.** A wrapped parenthetical splits across
   elements and each half looks unbalanced (F028, F055).
5. **Threshold inherited from authority.** See [01](01-thresholds-vs-practice.md).
6. **Missing plausibility bound.** A floor with no ceiling; a document at 6.2
   scenes per page emitting hundreds of findings rather than one.
7. **A measurement error in the harness reads as a finding about the world.**
   Page counts were a third low for the life of the project, because the parser
   drops blank lines and the estimator divided what was left by 55 lines per
   page. Nothing in the output distinguishes this from a claim about
   screenplays. It flipped three of six threshold verdicts in
   [threshold-results.md](threshold-results.md) across successive passes, and
   the only reason it was caught is that the numbers looked implausible.

Classes 2, 6, and 7 are the ones that fixtures structurally cannot catch. A fixture
is a small document. Class 2 needs a large one to become visible at all, and
class 6 needs a broken one.

## What can be claimed without any labelling

This is the part worth emphasising, because it sidesteps the precision problem
entirely.

- **249 findings per 100 pages** across 36 trusted documents. No screenplay
  contains that density of genuine defects, so the tool over-fires regardless of
  what a labelling pass would show.
- **56% of output is the lowest severity tier** (4,159 suggestions against 283
  errors).
- **The top twelve rules produce 60% of all findings.**
- **Instances per unique issue.** Pellichoopulu: 209 findings collapse to 41
  distinct rules, a 5.1x compression. F062: 272 findings, 6 documents, 45 per
  document.

That last one is a **metric proposal**. Instances-per-unique-issue is a
label-free precision proxy: it needs no verdicts, it is computable on any rule
system with grouped output, and it isolates exactly the failure that ordinary
precision hides. A rule with a high ratio is either reporting a document-scale
habit per occurrence, or is genuinely firing on a document with a pervasive
problem, and the two are distinguishable by whether the ratio is high on *one*
document or on all of them.

## The experiment still worth running

**Ablation.** Take the nine fixed rules, revert each in turn, and confirm that
the fixture suite still passes with the defect reinstated. That converts "no
fixture caught these" from a recollection into a measurement, and it is a couple
of hours of work. Do this before writing, because it is the sentence a reviewer
will want a number behind.

**A second system.** The claim would be much stronger with one non-screenplay
rule system given the same treatment: a linter with a fixture suite, run over a
large real corpus, defects classified into the same six buckets. A code linter
is the obvious candidate and the corpus problem does not exist there.

## Risks and objections

**"This is just saying testing on real data is good."** The specific contribution
is the taxonomy and the claim that two of the six classes are structurally
invisible to fixtures rather than merely absent from them. Lead with class 2 and
class 6.

**"Eight is a small n."** True. Eight out of eight is what makes it interesting;
the ablation makes it defensible. Reporting the classes rather than the count is
the safer framing.

**"You fixed your own bugs and called it a result."** The honest framing is that
the evaluation method found them, and the evaluation method is the contribution.
Report the fixes as evidence about the method rather than as achievements.

## Blocked on

Nothing. This can be written today. The ablation strengthens it and is cheap.

## Venue shape

Software engineering, testing, or an evaluation-methods workshop. The audience
is anyone shipping a rule-based analyser with a fixture suite, which is a large
population.
