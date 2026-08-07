# 07. Verifiable-only analysis of creative documents

**Status: position piece. Artifact exists. Reads better as a white paper or as a
section inside [01](01-thresholds-vs-practice.md) than as a paper of its own.**

## Claim

A useful scope boundary for automated analysis of creative work is: report only
what can be pointed at on the page. The boundary is implementable, it is
narrower than what the market currently sells, and drawing it produces a system
whose output can be argued with.

## The boundary, as implemented

Sluglint's `CLAUDE.md` rule 10 is the artifact. Three cuts, each of which had to
be defended against a plausible feature request:

**Numbers carry no verdict.** The metrics layer reports presence per character,
page load per location, day and night split, company moves. It never grades. A
band says a value sits outside it and stops. Genre is permitted because it is an
observable category rather than a judgment of quality.

**Loose ends are inside the line; resolution is not.** "Does this document come
back to what it introduced" is reference continuity, checkable by pointing at a
page, and it is the same class as an unpaid prop. "Does this story resolve well"
is a verdict. Every rule of this kind has to name the specific thing that was
introduced and quote it, which is what keeps the first from sliding into the
second.

**No attribute is inferred from a name.** Age and pronouns are read off what the
script writes down, and answer "unspecified" otherwise. Guessing gender, age,
region, or caste from a name would be wrong often and harmful when wrong.

The third is the one with the sharpest evidence behind it. A pronoun-drift rule
was built and removed after it fired on a script where a character is referred to
with both pronouns sixty and ninety-seven times across the document, because
correct attribution needs coreference resolution and the rule was doing
frequency counting. Building the rule and deleting it is a better story than
never building it.

## Why it is a position worth arguing

The market position is the opposite. Automated coverage sells a verdict: a
score, a recommendation, a comparison to films that succeeded. Those are the
claims a writer most wants and the ones a system is least able to support.

The narrower claim has a property the broader one does not: **it can be wrong in
a way the user can check.** A finding cites a rule, a severity, a location, a
source, and a suggested fix, and a writer can look at the page and disagree.
That is a different relationship with the reader than a score.

There is a second-order argument worth making. Building the boundary in
constrained what could be built, and every constraint produced a better
artifact: the volume discipline in rule 4 came from precision, the profile
system came from refusing to average across traditions, and the metrics layer
became genuinely useful precisely because it was forbidden from grading.

## What would make it a paper rather than an essay

An essay asserting this is not worth much. Two things would give it evidence:

- **A taxonomy of the boundary decisions**, with the request that prompted each
  and the reason it was refused. The pronoun rule, the joke counter, the quality
  score, the generated logline (built, and fenced outside the linter with a test
  enforcing that it never becomes a Finding). Six or seven of these with real
  detail is an artifact-grounded contribution.
- **A survey of what comparable systems claim**, matched against what they can
  support. That is doing work rather than asserting a position, and it is the
  half that makes it publishable.

## Risks and objections

**"This is a design philosophy, not a result."** Correct as currently written.
See above.

**"Verifiability is too restrictive to be useful."** The response is the
artifact: 150 rules, all of them inside the boundary. Whether that is *useful*
is the user-study question nobody has answered, and the paper should concede it.

## Blocked on

Nothing to write it. Blocked on being worth writing before
[01](01-thresholds-vs-practice.md) and [02](02-fixture-corpus-gap.md), which it
is not.

## Venue shape

White paper, or a position track. Also serviceable as the framing section of the
threshold paper, which is probably its best use.
