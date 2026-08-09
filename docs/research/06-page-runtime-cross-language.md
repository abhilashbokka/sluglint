# 06. Page count to runtime, across languages

**Status: no data yet. Small, novel, entirely blocked on collection.**

## Claim

The page-a-minute convention is a result about English-language screenplay
typesetting, and it is repeated as though it were a property of film. It is
testable, and there is a free public ground truth for the dependent variable
that nobody uses.

## Why it is worth asking

Every comparables band in the rulebook rests on the page-a-minute assumption. A
page of Telugu or Hindi dialogue does not run for the same time as a page of
English, because the convention is downstream of a fixed-pitch 12-point
typesetting standard, a specific dialogue column width, and the reading rate of
English. The `indian-regional` bands currently widen the page count without
claiming to have measured anything, and the rulebook says so next to the
numbers.

If the relationship differs by language, every page-based estimate in the
industry is wrong outside English, including budgeting and scheduling
heuristics that are used with real money.

## The free ground truth

Indian censor certificates state film length in **metres**, and the certificates
are public. 35mm four-perf at 24 frames per second runs 27.432 metres per
minute, so a certificate converts directly into a runtime with no rounding to
the nearest minute and no reliance on a streaming platform's listing.

This is a better dependent variable than the usual sources: it is official, it
is contemporaneous with release, it covers regional cinema thoroughly, and it is
free.

## The model, and why the naive regression fails

Runtime is not a linear function of page count in any tradition, and it is
especially not one in Indian commercial cinema. The decomposition:

```
runtime = a * dialogue_and_action_pages
        + songs      (each 3 to 6 minutes, often one line in the script)
        + set_pieces (a fight written in four lines can run five minutes)
        + fixed      (titles, production banners, end credits)
```

The interesting parameter is `a`, and the whole difficulty is that the other
three terms are large and are written on the page in a form that hides them. A
song cue occupies one line and four minutes. That is precisely why the naive
page-a-minute rule should be expected to fail harder here than in English.

Sluglint already detects the song block (F044) and the interval marker (F045),
so the terms are separable from the document rather than only from the film.

## The experiment

1. Assemble scripts with known released runtimes. Twenty per language is a
   start; the scripts are the hard part, the runtimes are not.
2. Extract pages, song count, interval position, and action-to-dialogue ratio.
3. Fit `a` per language, with the song and fixed terms estimated.
4. Report whether `a` differs across English, Hindi, and Telugu, and by how
   much.

The negative result is publishable and would be genuinely useful: if `a` is
stable across languages once songs and credits are separated out, then the
convention is more robust than expected and the correction is purely additive.

## Risks and objections

**"Runtime is decided in the edit."** The strongest objection. A script does not
determine a runtime, an editor does. The claim has to be about the conditional
expectation and about whether it shifts by language, rather than about
prediction accuracy for any single film.

**"The certificate length is the certified cut."** Which may differ from the
release cut, and after censor cuts often does. Worth reporting as a known
measurement error rather than ignoring.

**"Scripts and released films differ."** Always. A shooting script is closer
than a spec draft, which is another reason to record draft stage.

## Blocked on

Scripts with runtimes, in three languages. This is the same corpus problem as
[01](01-thresholds-vs-practice.md) with a harder constraint, because the film
also has to be identifiable. It is not solvable by
[05](05-federated-statistics.md) alone, since a contributor would also need to
name the film, and for an unproduced draft there is no runtime at all.

## Venue shape

Small empirical paper. Would land well in a film-studies-adjacent or
computational-humanities venue, and the censor-certificate trick is the part
most likely to be reused by other people.
