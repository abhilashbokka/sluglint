# 01. Prescriptive thresholds against observed practice

**Status: strongest idea on the board. Complete pass run, by a committed
harness, on 1,082 films. Results in [threshold-results.md](threshold-results.md).**

**Update, 2026-08-07, second pass.** `benchmark/thresholds.py` now exists and
every one of the 91 numeric parameters is classified and, where a document can
answer, measured. 1,082 films, 149,310 scenes, 882,948 action paragraphs.

Three things changed the shape of the idea:

**The taxonomy is a contribution in itself.** Of 91 parameters, only 36 are
decision thresholds. 26 are activation gates that decide whether a rule runs at
all, and 13 cannot be measured from a document. Any paper that reported "we
measured 91 thresholds" would be wrong about what it measured.

**19 of the 36 flagged more than one unit in ten** of produced practice as
shipped. Three are now retuned from the corpus (C021, C028, C038) and one turned
out to need a code fix instead.

**F013 is the best result and it inverts the thesis.** It was going to be a
fourth retuning: the first pass put it at p87 and called it too strict. Splitting
the corpus by draft stage showed it flagging 52% of numbered headings and 0.8%
of unnumbered ones, because a shooting script prints its scene number at both
margins and the rule measured the string as printed. The threshold of 60 was
correct. The quantity was not. A quantified rule can fail two ways and the
second one passes every check that would catch the first.

## Claim

When a prescriptive craft rule is quantified into a threshold, that threshold
systematically sits far from the distribution of the work it claims to describe,
and the distance is measurable.

Stated more carefully, because this is the version that survives review: craft
teaching states an **ideal** a practitioner should aim at. An automated checker
needs a **decision threshold** that separates a defect from ordinary practice.
Those are different objects. Nobody has measured the distance between them, and
in the one case measured here that distance was large enough to make the rule
useless.

## The worked case

F004, wall-of-text action block. Set at four lines, which is what the teaching
says. Measured across **18,299 action paragraphs in 19 produced screenplays**:

| Lines | Share | Cumulative |
|---:|---:|---:|
| 1 | 55.4% | 55.4% |
| 2 | 24.2% | 79.6% |
| 3 | 10.5% | 90.1% |
| 4 | 4.6% | 94.7% |
| 6 | | 98% |
| 8 | | 99% |

Four lines is the **95th percentile of normal practice**. As a rule it flagged
one action paragraph in eighteen, produced 2,043 findings across the corpus, and
buried the genuine cases: Parasite contains a 31-line action block that was one
row in a list of two thousand.

Reset to seven, the top 1.4%, it produces 635.

The failure mode is precise and worth naming: the rule was not wrong about what
a wall of text is. It was wrong about where the population sits.

## The experiment

**Scope: 54 of Sluglint's 150 rules carry numeric parameters**, roughly one
hundred individual thresholds. Thirty are tier 1, twenty-four are tier 2. The
full list is derivable from the rulebook with `rule.params`.

For each threshold:

1. Extract the taught value and its attribution. `principle:` and `source:` are
   already in the rulebook as data, which is why this is tractable.
2. Compute the empirical distribution of the same quantity over the corpus.
3. Report the percentile at which the taught value sits.
4. Classify: **holds** (taught value in a sensible tail, say above p95 of
   normal), **too strict** (below p90, flags ordinary practice), **too loose**
   (above p99.9, never fires), **unmeasurable** (the quantity is not computable
   from the document alone).

The output is one table with about a hundred rows. That table is the paper.

Three secondary results fall out of the same pass:

- **How many thresholds hold.** If most do, the finding inverts into "craft
  teaching is well calibrated, with these exceptions", which is a smaller but
  still publishable result. The paper should be written so either answer is
  interesting, and the analysis pre-registered so it is credible that it was.
- **Whether the misses cluster.** Measured, and they do, though not where the
  prior expected. Element-scale thresholds mostly hold (8 of 14); document-scale
  ratios mostly do not (13 of 22 flag over one in ten). The pattern is that a
  rule about one written thing is calibrated by people who looked at written
  things, and a rule about a whole-document ratio is a number somebody reasoned
  to.
- **Whether genre shifts the distribution.** Measured, and the answer is
  negative and useful: F004 varies from 1.6% to 1.9% across six genres, C021
  from 84% to 91%. A threshold that fails, fails in every genre. Only two rules
  are genuinely genre-dependent (F033 and F036, both driven by Comedy).
- **Whether era or language shifts the distribution.** Language: F004 holds in
  Telugu at p94.3. Era is still unmeasured, and the corpus spans 1926 to 2013.

## Why it generalises

The method needs three things: a prescriptive rule set with quantified
thresholds, a corpus of work the rules claim to describe, and a way to compute
the quantity. That combination exists in many places.

- Code style guides. Line length, function length, parameter count, cyclomatic
  complexity. Defaults are inherited from decades-old convention and rarely
  re-derived. There is prior work measuring conformance, less measuring whether
  the threshold matches practice.
- Prose style guides. Sentence length, passive voice share, paragraph length.
- Newsroom and technical-writing house rules.
- Readability formulas, which are quantified prescriptions applied far outside
  the population they were fitted on.

The screenplay case is a good instance to lead with because the rules are
unusually explicit, the format is unusually rigid, and the quantities are
unusually easy to compute.

## Risks and objections

**"You measured 19 scripts."** Answered four times over. The taught value of
four lines sits between p93.6 and p94.7 across 19 PDFs, 214 ScriptBase films,
1,082 ScriptBase films, and 7 Telugu drafts: three corpora of different
provenance, two languages, a 48-fold range in size. Several corpora reaching the
same number is a stronger answer than one large corpus would have been.

**"Your corpus is biased toward acclaimed films."** True, and it argues for the
result. The scripts that circulate publicly do so because of award-season
campaigns, so this is a sample of work held up as exemplary. If those are the
documents violating the taught threshold, the threshold is not describing good
practice. Say it in the paper before a reviewer says it.

**"Produced scripts are shooting scripts, and the rules are for spec drafts."**
The strongest objection, and it now has a measured answer rather than a wave.
The corpus splits on scene numbering, 284 production drafts against 798
spec-style. F008 is 64.4% outside the band on the first and 52.5% on the second,
so the result holds on both sides and is not a shooting-script artifact. C021,
C028, and C038 vary by less than three points across the split. F013 varied by
52 points, and that is how its defect was found.

Where the objection does land is F008 itself, which is why it was deliberately
NOT retuned: a produced screenplay is a later artifact than a submitted spec, so
the corpus answers a different question from the one the rule asks. Saying that
is better than moving the number.

**"You are arguing against craft teaching."** Not the claim, and the framing
above exists to prevent this reading. The teaching is doing its job. The
automation is misusing it.

**"The distribution is not the standard."** Fair, and it is the deepest
objection: a rule can be correct while most work violates it. The honest
response is that a linter has to make a decision, and a decision threshold set
where 5% of exemplary practice is flagged is a threshold that will be turned
off. The paper argues about operational usefulness rather than about aesthetics.

## Blocked on

- ~~**Corpus size.**~~ Solved. All 1,276 ScriptBase archives are measured, 1,082
  past the gate. See [corpus-options.md](corpus-options.md).
- ~~**A profile split.**~~ Done, on scene numbering as the draft-stage proxy. It
  found the F013 defect on its first run, and it answered the F008 objection:
  spec-style drafts are still 52.5% outside the band, so the length result is
  not an artifact of shooting scripts.
- ~~**A harness.**~~ `benchmark/thresholds.py`, committed, with `--verify`
  checking each extractor against the shipped detector on 150 documents.
- **A spec corpus.** The one thing still missing, and it blocks F008 and the
  comparables bands together. Produced screenplays are a later artifact than the
  drafts those rules address.
- **A second corpus per language.** F004 has four measurements. Every other row
  has one. [05](05-federated-statistics.md) is the route.

## Not blocked on

Precision, tier 3, the LLM, the UI, or a user study. This is the argument for
doing it first.

## Venue shape

Empirical study with a method that transfers. Reads naturally to a
computational-humanities or NLP-for-creative-text audience if led with the
screenplay result, and to a software-engineering or empirical-methods audience
if led with the style-guide generalisation. The second framing has the wider
reach and the harder review.
