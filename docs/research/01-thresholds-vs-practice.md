# 01. Prescriptive thresholds against observed practice

**Status: strongest idea on the board. One worked case, method defined, blocked
on corpus size.**

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
- **Whether the misses cluster.** A prior worth testing: rules about *quantity*
  (how long, how many) are miscalibrated more often than rules about *form*
  (whether a marker is present). Form has a right answer; quantity has a
  distribution, and teaching tends to state the aspirational end of it.
- **Whether era or language shifts the distribution.** Citizen Kane and Marty
  Supreme are eighty-five years apart in the same corpus.

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

**"You measured 19 scripts."** The real weakness. Percentile claims at p95 and
p99 need more mass than that, and the tail is where the thresholds live. Fifty
documents is the number to reach. This gates the paper.

**"Your corpus is biased toward acclaimed films."** True, and it argues for the
result. The scripts that circulate publicly do so because of award-season
campaigns, so this is a sample of work held up as exemplary. If those are the
documents violating the taught threshold, the threshold is not describing good
practice. Say it in the paper before a reviewer says it.

**"Produced scripts are shooting scripts, and the rules are for spec drafts."**
The strongest objection, and it needs a real answer rather than a wave. Some
rules genuinely differ by draft stage, which is why Sluglint has profiles. The
paper should report the profile alongside each threshold and exclude any rule
whose taught value is explicitly stage-specific.

**"You are arguing against craft teaching."** Not the claim, and the framing
above exists to prevent this reading. The teaching is doing its job. The
automation is misusing it.

**"The distribution is not the standard."** Fair, and it is the deepest
objection: a rule can be correct while most work violates it. The honest
response is that a linter has to make a decision, and a decision threshold set
where 5% of exemplary practice is flagged is a threshold that will be turned
off. The paper argues about operational usefulness rather than about aesthetics.

## Blocked on

- **Corpus size.** 33 trusted documents, of which 13 are produced English. Needs
  roughly 50 usable. See [05](05-federated-statistics.md) for the route that
  does not require holding them.
- **A harness.** `benchmark/thresholds.py` does not exist yet: read every rule
  with params, compute the matching empirical distribution, emit the table. This
  is a day of work and is the immediate next step.

## Not blocked on

Precision, tier 3, the LLM, the UI, or a user study. This is the argument for
doing it first.

## Venue shape

Empirical study with a method that transfers. Reads naturally to a
computational-humanities or NLP-for-creative-text audience if led with the
screenplay result, and to a software-engineering or empirical-methods audience
if led with the style-guide generalisation. The second framing has the wider
reach and the harder review.
