# The corpus sweep

What happened when the linter was pointed at real screenplays instead of at
fixtures, and what it cost.

The short version: the first sweep produced 18,421 findings, and the number was
not trustworthy. Hand-checking the highest-volume rules exposed eight defects in
the engine. Four passes took the corpus to 11,265, a 39% reduction, and every
finding removed was confirmed wrong by reading it.

---

## The corpus

**Not redistributable and not committed.** `benchmark/corpus/` and
`benchmark/local/` are both gitignored for the reason set out in
[public-domain-scripts.md](public-domain-scripts.md). The composition is written
down here so the numbers are checkable by someone who assembles a comparable
set, which is the most that can be offered without a licence.

56 files, of which 49 were read and 7 refused.

| Group | Files | Read | Suspect | Refused | Pages | Findings |
|---|---:|---:|---:|---:|---:|---:|
| Produced, English | 17 | 13 | 4 | 0 | 1,593 | 6,237 |
| Produced, Telugu | 7 | 3 | 3 | 1 | 583 | 1,609 |
| Produced, Hindi | 4 | 1 | 2 | 1 | 437 | 1,095 |
| Produced, Kannada | 1 | 0 | 1 | 0 | 116 | 1,209 |
| Unproduced drafts, privately held | 27 | 16 | 6 | 5 | 205 | 1,115 |

**Produced** means the film was released theatrically or on a streaming service,
determined by the title rather than by any property of the document. The English set
skews hard toward award-season publication, because the For Your Consideration
cycle is the mechanism that puts a shooting script online at all. Era runs 1941
to 2026.

Titles in the produced set, listed so the composition can be reconstructed:
2001: A Space Odyssey, Annie Hall, Citizen Kane, Get Out, Gone Girl, Her,
Inside Out, Lage Raho Munna Bhai, Marty Supreme, Memento, Moneyball, Obsession,
Parasite, The Matrix, The Shining, Whiplash, Everything Everywhere All At Once;
3 Idiots, Kapoor and Sons, Rockstar, Tumbbad; Brochevarevarura, Jathi Ratnalu,
Kanya Raasi, Middle Class Melodies, Pellichoopulu, Prasthanam, Sammohanam;
Ulidavaru Kandante.

The unproduced set is not itemised. Those are working drafts held in confidence,
and naming them in a public repository would publish something about their
authors that they did not agree to.

**Profiles:** 43 documents linted as `us-spec-feature`, 13 as
`indian-regional`, assigned by language group rather than by inspection.

### Three states, and why the middle one matters

- **read** (33): the geometry reader recovered the document and its own
  confidence checks passed.
- **suspect** (16): recovered, but a confidence check failed. Findings from
  these are reported and excluded from any rate.
- **refused** (7): the reader declined. Broken character map, no recoverable
  text layer, or a document that is not a screenplay.

A third of real PDFs land outside **read**. Any evaluation that does not gate on
ingest confidence is partly measuring the reader rather than the script.

---

## The eight defects

None of these were visible to 208 fixture tests. A fixture is written by the
same person who wrote the rule, so it encodes the same assumption.

### 1. F002 matched spelling instead of meaning (2,070 to 921)

Fired on `LATE AFTERNOON`, `HOURS LATER`, `FAINT DAWN`, and `OFFICE-DAY`. All of
those state a time of day. The rule now tests whether a heading carries a time
marker at all, using stems, and stays silent when the marker is written
unconventionally. F011 already exists for that.

### 2. F009 was one profile error rather than 1,907 defects

Memento and Gone Girl are shooting scripts. Scene numbers are correct in a
shooting script. The reader now recognises a document whose headings carry
numbers at scale and says the profile is wrong, once.

### 3. F049 reported a document-scale decision per occurrence (1,342 to 1)

Inside Out sets dialogue in capitals 180 times deliberately. The rule became a
density rule with a floor: it fires when the habit is occasional, and stays
silent when it is the document's convention.

### 4. F028 and F055 misread element boundaries (1,540 to 312)

A parenthetical wide enough to wrap puts its closing bracket in the next
element, so each half looks unbalanced alone. Both rules now count bracket and
quote balance across the whole scene. On Whiplash this took F028 from 130 to 0.

The first attempt at this fix moved the total by two findings, because the two
halves were on lines 660 and 662 rather than adjacent lines. Adjacency was the
wrong model.

### 5. F004's threshold came from teaching rather than from measurement (2,043 to 635)

Measured across 18,299 action paragraphs in produced screenplays:

| Lines | Share | Cumulative |
|---:|---:|---:|
| 1 | 55.4% | 55.4% |
| 2 | 24.2% | 79.6% |
| 3 | 10.5% | 90.1% |
| 4 | 4.6% | 94.7% |
| 6 | | 98% |
| 8 | | 99% |

The rule was set at four, the 95th percentile of normal practice, so it flagged
one action paragraph in eighteen and buried the genuine walls. Parasite contains
a 31-line action block. The threshold is now seven.

This one has a research life of its own; see
[research/01-thresholds-vs-practice.md](research/01-thresholds-vs-practice.md).

### 6. F011 counted one decision per heading (424 to 240)

Memento tags every heading `<<COLOUR SEQUENCE>>`. That is one convention. The
rule now reports once per distinct token.

### 7. The PDF reader had a floor and no ceiling

Two documents came back at 5.7 and 6.2 scenes per page, which no screenplay runs
at. In both cases the geometry had failed and ordinary lines were being read as
sluglines. A ceiling at three per page now flags the document instead.

### 8. The ceiling was checked against the wrong number

The first version of that fix counted what the PDF reader's own classifier had
called a heading, against the PDF's page count. The number that matters is what
the parser finally built, against estimated pages, and the two diverge exactly
when something has gone wrong. Moved to `ingest/__init__.py`, above both.

---

## Where the numbers landed

Pass history: **18,421 to 13,894 to 12,672 to 11,265.**

On the 33 trusted documents:

| | |
|---|---:|
| Pages | 1,771 |
| Findings | 6,504 |
| Findings per 100 pages | 367 |
| Errors | 247 |
| Warnings | 2,461 |
| Suggestions | 3,796 |
| Rules that fired | 92 of 150 |

**367 findings per 100 pages is itself a result.** It says the tool over-fires,
independent of what a labelling pass would show, because no screenplay contains
that density of genuine defects. The severity mix says the same thing from
another angle: 58% of output is the lowest tier.

The top twelve rules produce 61% of all findings. Concentration is the specific
shape of the problem.

### Rules still reporting a habit per occurrence

| Rule | Findings | Documents | Per document |
|---|---:|---:|---:|
| F062 scene heading ends in punctuation | 264 | 5 | 53 |
| F021 non-standard character extension | 303 | 17 | 18 |
| F014 non-standard heading separator | 255 | 16 | 16 |

A writer who ends every slugline with a period made one decision and is told
about it 53 times.

---

## What this does and does not show

**Shows:** that a fixture suite and a real corpus catch different classes of
defect, and that the second class is systematic rather than incidental. Eight of
eight defects found this way were of one family: a rule that is correct about a
single instance and wrong about a document.

**Does not show:** precision. No finding in this sweep carries a human verdict.
The 39% removed were confirmed wrong by reading, which bounds the pre-sweep
precision at 61% or below and says nothing about what remains. See
[research/02-fixture-corpus-gap.md](research/02-fixture-corpus-gap.md) for what
a precision measurement would take.

**Also does not show** anything about tier 3. The sweep ran with the LLM tier
off, so all 38 tier-3 rules are silent in every number on this page.

---

## Reproducing it

The sweep script is not committed, because it walks a private directory. It is
about forty lines: glob the corpus, pick a profile per folder, call `run_lint`,
record `by_rule` counts and the ingest status per document, dump JSON. Rebuild
it against your own corpus and the per-rule counts are comparable even though
the documents are not.

```bash
python benchmark/local_report.py ~/Scripts   # the precision pass, output gitignored
```
