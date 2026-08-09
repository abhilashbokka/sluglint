# The report model

A report is about unique issues. It is not about instances.

## The problem

Linting Pellichoopulu produces 209 findings. Presented one per line, that is a
list nobody finishes, and it hides the three things that are actually wrong.
Grouped by rule, the same output is **41 rows, of which 3 are errors**.

Nothing was suppressed. Same script, same rules, same findings.

| | Rules | Places |
|---|---:|---:|
| Errors | 3 | 11 |
| Warnings | 12 | 83 |
| Suggestions | 26 | 115 |

Across the whole [corpus sweep](corpus-sweep.md) the same pressure shows up as
concentration: the top twelve rules produce 61% of all findings, and F062 fires
264 times across 5 documents, which is 53 reports of one decision.

This is the same principle as `CLAUDE.md` rule 4, applied to presentation rather
than to detection. A rule that reports a real defect a hundred times buries the
one thing the writer needed to see.

## The shape

One row per rule. Every row carries:

- rule id and name
- **count** as `20x`, or the word `once` when it happened once (`1x` reads as
  noise)
- the **first example only**: its message and its evidence, quoted
- where: `first at page 6.5, 19 more`, or `whole document` for a rule that is
  about the document rather than a place in it
- an **ignore** control

Never a second row for the same rule. Every other instance is reachable as a
jump target from the first.

Ordered errors, then warnings, then suggestions. Errors are the tier that has to
stay small and stay right: 247 errors against 6,504 findings across the trusted
corpus is close to the correct proportion.

## Ignoring

Per rule, and per severity tier in bulk. A writer who does not want the
suggestion tier should be able to remove all 26 rows in one action.

**Ignores persist across drafts.** The point of the linter is the second pass,
and re-reading the same 26 dismissed suggestions on every upload trains people
to stop reading the report.

The persistence target is `.sluglint.yaml`, which `config.py` already reads.
That keeps a mute portable to the CLI and to CI rather than trapped in one
browser, and it means the UI and the command line cannot disagree about what is
muted.

Every mute needs an undo. A control that silently deletes an entire rule from a
report is the one thing that would make the tool untrustworthy.

## Fixing

Some rules have a deterministic fix: F062 trailing punctuation, F068 `INT.`
against `INT`, C031 mixed apostrophes, F070 spacing around punctuation. Most do
not.

Split the rulebook on that axis and render a fix control only where a fix
exists. A **Fix all** that silently does nothing on two thirds of rows is worse
than no button.

## The viewer

Findings are shown against **the recovered Fountain** rather than against the
original PDF render.

That looks like the lesser choice and it is the honest one. What the linter read
is the only thing a finding can be explained by, and when ingest has gone wrong
it is visible immediately instead of leaving the reader to wonder why a rule
fired on text that looks fine on the page.

## Status

A working prototype exists at `benchmark/local/sluglint-ui.html`, built from a
real lint of a real script. It is gitignored because it embeds the recovered
text of a third-party screenplay.

The grouping logic currently lives in the prototype's build script. It belongs
in `report.py` as a `group(findings)` returning rule-level records, because the
console report needs exactly the same treatment.

### Also pending

- `report.py` grouping, shared by console, JSON, and any UI.
- Mute round-trip through `.sluglint.yaml`.
- The fixable/not-fixable split in the rulebook.
- **Log every mute against the finding fingerprint.** A dismissal is a human
  verdict on a finding, which is the labelled data the precision problem needs.
  See [research/04-dismissal-as-label.md](research/04-dismissal-as-label.md).
