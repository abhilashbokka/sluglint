# 04. Dismissal as label

**Status: no evidence yet. Highest-leverage idea on the board. Must be designed
in before the UI ships.**

## Claim

The labelled data a precision measurement needs can be collected as a byproduct
of ordinary use, if the interface is designed for it. Every dismissal of a
finding is a human verdict on that finding. A system that records dismissals
against a stable finding identity measures its own precision continuously,
without anyone ever running a labelling exercise.

## Why this matters here

Precision is the open problem. Recall is 97% and measured; precision has no
number, because it needs a verdict per finding and nobody has given one. The
usual answer is a labelling pass: roughly 400 findings sampled at random gives
an overall figure at about plus or minus 5% at 95% confidence, and about 900
stratified gives per-rule figures. That is hours of reading, it is stale the
moment a rule changes, and it has to be repeated.

A dismiss control produces the same verdicts, from the person best placed to
give them, on findings they actually care about, forever.

## The design that makes it work

**Stable finding identity.** `Finding.fingerprint` already excludes line numbers
so that draft diffs survive edits. That is exactly the property a verdict needs:
a dismissal on draft 3 has to still apply on draft 7.

**A rule id alone is not enough.** The current design writes a rule id
into `.sluglint.yaml`. That is the right persistence, and it throws away the
signal: a rule-level mute says nothing about which instance was wrong. Log the
fingerprint, the rule, the document, and the scope of the dismissal.

**Three scopes, and the difference between them is the whole signal.**

| Action | What it means |
|---|---|
| Dismiss this instance | this finding is wrong, or does not apply here |
| Ignore this rule for this script | the rule is right in general and not for this document |
| Ignore this rule everywhere | the rule is wrong, or not my house style |

Only the first is a precision label. The second is a profile signal: a rule
being muted per-document at a high rate is a rule that needs a profile gate. The
third is a rulebook signal. Collapsing all three into one button, which is the
obvious implementation, destroys the distinction.

**Accept as well as dismiss.** A dismiss-only interface produces only negative
labels and a biased estimate. Something that records "fixed this" is the
positive class. The cheapest honest version is a re-lint: a finding that
disappears in the next draft without being dismissed was probably acted on. That
is a weak label and it is free, and `diff.py` already computes it.

## The experiment

1. Ship the three-scope dismissal with fingerprint logging.
2. Instrument locally first, on the author's own drafts, before any external
   user exists. That alone produces a labelled set on documents that can be
   inspected.
3. Report per-rule precision from dismissals, alongside a hand-labelled sample
   on the same findings, to measure how much the two disagree.

Step 3 is what makes it a paper rather than a feature. The interesting question
is not "can you collect labels this way", it is **how biased are they**. Users
dismiss what annoys them, ignore what they do not understand, and never touch
what they did not scroll to. Quantifying that gap against a ground-truth sample
is the contribution.

## Risks and objections

**"Dismissal is not the same as wrong."** Correct, and it is the point of the
paper. A writer dismisses a true positive they disagree with, and a false
positive they spot, with the same click. The three scopes separate some of this
and not all of it.

**"n of 1 user."** Real. Anything published on a single user's dismissals is a
case study. It is still worth instrumenting now, because the alternative is
having nothing when there are users.

**Privacy.** A dismissal log is a record of what someone was told about their
unfinished script. It stays local by default, and any aggregation follows the
route in [05](05-federated-statistics.md): counts leave, content does not.

## Blocked on

The UI, which exists as a prototype (`benchmark/local/sluglint-ui.html`) and is
not wired to anything persistent. The logging design has to land with it rather
than after it, because retrofitted instrumentation loses every verdict given
before it existed.

## Venue shape

Human-in-the-loop evaluation, or an interactive-systems venue. Also a strong
limitations-section answer for [01](01-thresholds-vs-practice.md) and
[02](02-fixture-corpus-gap.md), which is reason enough to build it even if it
never becomes its own paper.
