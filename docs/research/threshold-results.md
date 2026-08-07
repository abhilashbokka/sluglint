# Threshold results

The experiment from [01](01-thresholds-vs-practice.md), run over every numeric
parameter in the rulebook by a committed harness. Regenerate with:

```bash
python benchmark/thresholds.py CORPUS --label NAME --layout scriptbase \
    --genres --drafts --verify 150 --json out.json --out out.md
```

**Headline: 36 of 91 parameters are decision thresholds measurable from a
document. As shipped before this pass, 19 of the 36 flagged more than one unit
in ten of produced practice. Four are now retuned or fixed. F004 replicates a
third time and holds in Telugu. F013's failure turned out to be a defect in the
rule rather than in its number, which is the result on this page with the most
to teach.**

Corpora are named and never pooled. See [Containers](#containers).

---

## Method

### What is being measured

**54 of Sluglint's 150 rules carry numeric parameters, 91 individual values.**
Each is one of three things, and saying which is half the contribution:

| Class | Count | What it is |
|---|---:|---|
| **Decision threshold** | 36 | The value that separates a defect from ordinary practice. Measured here. |
| **Activation gate** | 26 | Decides whether the rule runs at all. Reported as the share of the corpus it silences. |
| **Unmeasurable from a document** | 13 | A similarity cutoff needs labelled pairs; a pilot band needs pilots. Named, not guessed at. |

The remaining 16 are gates that duplicate one already listed for the same rule.
A partial table that did not say so would read as a complete one.

### Which side fires

The rulebook writes bounds three ways and reading all three as a ceiling
produced verdicts that were backwards. F004's `max_lines` is a ceiling. C030's
`min_lines` is a floor a part must reach before the rule cares. C002's
`last_seen_before` is a position the rule wants something to happen before. Each
measure declares its direction, and `Flags` throughout is the share of the
population the shipped value reports, whichever side that is.

A threshold flagging **more than one unit in ten** is describing ordinary
practice rather than a tail, which is the failure that makes a writer switch the
tool off. Below **one in a thousand** it is doing no work.

### Holding everything else fixed

Where a rule has more than one condition, the extractor applies all of them
except the parameter under test. C002 does not care where a one-scene walk-on
was last seen, so one-scene parts are not in its population. Documents a rule's
own gates would silence are dropped before its distribution is computed: a rule
that never runs on three quarters of the corpus is not flagging 2% of
screenplays, it is flagging 11% of the ones it looks at, and only the second
number describes what a writer experiences.

### Verifying the harness against the linter

Every extractor calls the same helper the detector calls. `--verify` closes the
loop: run the real detector over 150 documents and check that the number of
values on the firing side equals the number of findings produced. For an
element-scale rule the two must agree exactly.

**32 of 36 agree on every sampled document.** All four exceptions are the same
thing, and it is a finding rather than a bug:

| Rule | Disagreements | Cause |
|---|---:|---|
| C029 | 147 of 148 | Fires only when such locations exceed a third of all locations. That ratio is a literal in the code. |
| F009 | 14 of 150 | Below the share the rule still fires, with a different message. The rulebook expresses one branch. |
| F006 | 1 of 150 | A floor of two transitions, written as a literal. |
| C034 | 2 of 150 | Unexplained. The likeliest cause is location-name normalisation differing by a case the extractor does not reproduce. |

**An AST walk of the six detector modules finds 16 numeric literals used in a
comparison or a scaling that did not come from `rule.params`.** Hard rule 2 of
this project says rules are data. Each of these is a decision no rulebook edit
can reach, and two of them (`day_night_whiplash` at 0.8,
`continuous_across_locations` at 0.6) are similarity cutoffs duplicating
parameters that C001 and C005 already expose. That gap is worth a paragraph in
any paper claiming a data-driven rule engine, because it is the form the claim
usually fails in.

### Corpus integrity, reported next to the results

Every number here is a ratio over a page count, and a page count comes from a
decision about whether the source broke its own lines. That chain broke silently
three times. It is now reported rather than assumed.

| Check | english-produced | telugu |
|---|---:|---:|
| Documents measured | 1,082 | 7 |
| Sources that broke their own lines | 819 | 0 |
| Sources holding whole paragraphs | 263 | 7 |
| Wrap ratio p99/p50, median | 1.22 | 1.87 |
| **Documents within 15% of the wrap cut** | **219** | **3** |
| Scene pages vs document, median drift | 0.33% | 0.05% |
| Scene pages vs document, worst drift | 17.5% | 0.08% |
| Elements orphaned before the first heading, median | 0.27% | 0.05% |
| Page count stated by the source | 0 | 7 |

**219 of 1,082 documents sit within 15% of the boundary where the wrap decision
flips**, and flipping it changes that document's page count by about a third.
That is the fragility underneath every per-page row below, and it is the reason
the Telugu container, which states its own page counts, is the more trustworthy
of the two on any per-page quantity despite being 150 times smaller.

### The gate

| Outcome | english-produced | telugu |
|---|---:|---:|
| Read | 1,082 | 7 |
| Parsed to no scenes | 170 | 1 |
| Under 20 pages | 2 | 0 |
| **Unsegmented** | **21** | **2** |
| Duplicate of another document | 1 | 1 |

`Unsegmented` is a gate that did not exist in the first pass and should have. A
crawl whose scene headings were never recognised still parses: it comes back as
one 111-page scene with everything before it, passes a "has scenes" check, and
poisons every ratio with a page count in the denominator. The share of elements
the parser could not place inside any scene says so directly and says nothing
about screenwriting, which is what keeps the gate from being circular with the
thresholds it protects.

The duplicate check earns its place too: Kill Bill Volumes 1 and 2 are the same
file in ScriptBase, and both Kanya Raasi PDFs are byte-identical.

---

## Containers

Three corpora, kept apart. Pooling them would produce a number describing none
of them, and the F013 and F008 rows below are the demonstration.

| Container | n | What it is |
|---|---:|---|
| `english-produced` | 1,082 | ScriptBase alpha, every archive, crawled text of produced English-language films, 1926 to 2013 |
| `telugu` | 7 | Telugu-language feature drafts, read from PDF by margin geometry |
| `english-pdf` | 17 | The produced English screenplays read from PDF, including the seven with a known page count |

ScriptBase alpha holds **1,276 archives**. The first pass listed 994 and sampled
250 of them, because the GitHub contents API truncates at 1,000 entries and the
listing stopped alphabetically at *The Godfather Part II*. Every film after that
was invisible. The frame now comes from the git trees API, which does not
truncate.

---

## Element-scale thresholds: english-produced

The unit is one written element, pooled across 1,082 documents.

| Rule | Quantity | Ships at | Direction | Flags | p50 | p90 | p95 | p99 | Units | Verdict |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| F004 | printed lines per action paragraph | 7 | above | **1.7%** | 1 | 4 | 5 | 9 | 882,948 | holds |
| F016 | printed lines per unbroken speech | 6 | above | 3.9% | 1 | 4 | 6 | 11 | 826,434 | holds |
| F013 | characters per scene heading | 60 | above | **1.4%** | 29 | 46 | 51 | 65 | 149,310 | holds, after a fix |
| F017 | words per parenthetical | 5 | above | 1.9% | 2 | 4 | 4 | 6 | 158,444 | holds |
| F064 | words per character cue | 5 | above | 0.2% | 1 | 2 | 2 | 3 | 826,434 | holds |
| C023 | pages per scene | 4 | above | 3.1% | 0.41 | 2.27 | 3.26 | 6.25 | 149,310 | holds |
| C030 | lines by a one-scene character | 12 | at or above | 7.0% | 2 | 9 | 14 | 33 | 44,676 | holds |
| C039 | where a substantial part first appears | 0.75 | at or above | 8.3% | 0.196 | 0.71 | 0.84 | 0.966 | 22,855 | holds |
| F048 | dialogue lines in a scene with no action | 8 | at or above | 14.0% | 2 | 9 | 14 | 29 | 1,862 | too strict |
| C040 | dialogue lines in a single-speaker scene | 6 | at or above | 14.4% | 2 | 7 | 11 | 24 | 19,339 | too strict |
| F059 | beats under a montage header | 2 | below | 19.1% | 7 | 40 | 61 | 144 | 1,116 | too strict |
| C002 | where a recurring part is last seen | 0.65 | below | **24.3%** | 0.877 | 1 | 1 | 1 | 14,813 | too strict |
| C034 | where a recurring location is last used | 0.6 | below | **30.2%** | 0.774 | 0.983 | 0.994 | 1 | 6,312 | too strict |
| C029 | pages carried by one location | 0.5 | below | **43.9%** | 0.65 | 3.36 | 4.96 | 10.55 | 96,189 | see the verify note |

Eight of fourteen hold. That matters as much as the failures: the claim is that
thresholds are often miscalibrated, not that they always are, and a table where
everything failed would read as a broken instrument.

## Document-scale thresholds: english-produced

The unit is one screenplay. `Documents` is the number the rule actually runs on
after its own gates.

| Rule | Quantity | Band | Direction | Flags | p50 | p90 | Documents | Verdict |
|---|---|---|---|---:|---:|---:|---:|---|
| F032 | share of action lines fully capitalised | 0.15 | above | 1.2% | 0.008 | 0.046 | 1082 | holds |
| F052 | (beat) parentheticals per page | 0.5 | above | 4.6% | 0.106 | 0.335 | 417 | holds |
| F050 | speeches with a bare numeral, per page | 0.5 | above | 4.7% | 0.095 | 0.296 | 558 | holds |
| C025 | share of dialogue spoken by the lead | 0.45 | above | 4.8% | 0.28 | 0.413 | 1031 | holds |
| F034 | dialogue lines with an ellipsis | 0.2 | above | 6.0% | 0.064 | 0.169 | 1039 | holds |
| C024 | longest lead absence | 0.25 | above | 10.5% | 0.098 | 0.255 | 1069 | too strict |
| F049 | speeches set in capitals, per page | 0.5 | above | 10.9% | 0.119 | 0.547 | 267 | too strict |
| F037 | scenes per page | 0.3 to 2 | outside | 11.1% | 1.075 | 1.761 | 1082 | loose fit |
| F038 | action lines carrying emphasis markup | 10 | above | 14.3% | 0 | 14 | 1082 | too strict |
| C022 | share of timed scenes at night | 0.6 | above | 15.1% | 0.373 | 0.667 | 797 | too strict |
| F036 | dialogue share of body text | 0.2 to 0.7 | outside | 18.0% | 0.519 | 0.713 | 1082 | loose fit |
| F033 | exclamation marks per page | 2 | above | 20.1% | 1.069 | 2.729 | 1082 | too strict |
| C020 | speaking parts per page | 0.6 | above | 20.5% | 0.393 | 0.843 | 1082 | too strict |
| F007 | parentheticals per dialogue block | 0.3 | above | 20.6% | 0.161 | 0.441 | 1036 | too strict |
| F006 | transitions per 10 scenes | 3 | above | 23.2% | 0.5 | 7.211 | 1082 | too strict |
| F009 | headings carrying a scene number | 0.6 | at or above | 26.2% | 0 | 1 | 1082 | measures the corpus |
| F042 | longest act over shortest act | 2.5 | above | 33.3% | 1.083 | 4.329 | 1082 | thin, 3 documents carry acts |
| **F008** | pages | 85 to 125 | outside | **55.6%** | 125.4 | 163.9 | 1082 | **wrong population** |
| F060 | longest run of blank lines | 2 | above | 94.5% | 5 | 16 | 1082 | wrong population |

### The four that were retuned

Measured, found to be describing ordinary practice, and reset to the 90th
percentile of the corpus. The taught value stays in each rule's `principle:`
field, so nothing is lost and the change is auditable.

| Rule | Quantity | Was | Flagged | Now | Flags | Median practice |
|---|---|---:|---:|---:|---:|---:|
| **C021** | distinct locations per page | 0.35 | **88.4%** | **1.15** | **10.4%** | 0.67 |
| **C028** | share of cuts that change location | 0.85 | **96.4%** | **0.99** | **14.1%** | 0.959 |
| **C038** | parts arriving in the first tenth | 8 | **64.6%** | **23** | **9.4%** | 11 |
| **F013** | characters per scene heading | 60 | **14.8%** | 60, fixed code | **1.4%** | 29 |

C028 lands at 14.1% rather than 10% because the distribution is so concentrated
that the 90th percentile and the maximum are almost the same number. That is
itself the finding: the measure barely separates one draft from another, and the
rulebook now says so.

F013 is the odd one out and the important one: its threshold did not move at all.
See [below](#3-f013-was-a-correct-threshold-measuring-the-wrong-string).

**F060 is measured on the wrong population and the row is kept to say so.** It
is a Fountain source-hygiene rule and ScriptBase is a raw text crawl, which
double-spaces everything. The number says nothing about screenwriting and
everything about the corpus. Reporting it as a threshold failure would have been
the class-7 error this project has already made three times.

**F009 is not a miscalibration.** A quarter of the corpus is a production draft
being read against a spec rule, which is what F009 exists to report. The row
measures the corpus, not the threshold.

---

## The three results worth carrying into a paper

### 1. F004 replicates a third time

| Corpus | n paragraphs | Taught value 4 | Shipped value 7 |
|---|---:|---:|---:|
| PDF, 19 produced screenplays | 18,299 | p94.7 | p98.6 |
| ScriptBase, 214 films (first pass) | 189,078 | p94.5 | p98.7 |
| **ScriptBase, 1,082 films** | **884,746** | **p93.6** | **p98.3** |
| Telugu, 7 drafts | 10,811 | p94.3 | p98.0 |

Four measurements, three corpora of different provenance, two languages, and a
48-fold range in size. The taught value of four printed lines sits between p93.6
and p94.7 in all four; the shipped value of seven sits between p98.0 and p98.7.
Four lines is roughly the 94th percentile of an action paragraph wherever you
measure it. The original finding was not an artifact of nineteen documents, and
it is not an artifact of English.

### 2. C021 and C028 describe almost every screenplay

**C021** permitted 0.35 distinct locations per page. The median produced
screenplay runs **0.67** and **88.4%** sit above the line, which puts the
threshold near the 5th percentile of practice. It is now 1.15, the 90th
percentile, and flags 10.4%. This is the one result that survived every pass of
this table unchanged, including the two passes that were wrong for other
reasons, which is why it is the row reported with most confidence.

**C028** permitted 0.85 as the share of cuts that change location, and
**96.4%** of screenplays are above it. The median is 0.959. The rule's stated
premise is that "when almost every scene sits at a different place from the one
before it, the schedule is being written by scene order rather than by
geography". Almost every scene does. The threshold is now 0.99, which still
flags 14.1%, and the honest reading, written into the rulebook, is that this
measure barely separates one draft from another.

**C038** capped the opening tenth at 8 speaking parts against a median of 11,
flagging **64.6%**. Now 23, the 90th percentile, flagging 9.4%. The taught claim
that a reader holds about six new names may well be true about readers; it is
not true about what produced screenplays ask of them, and the rulebook now
records both.

**F008 was deliberately not retuned**, and that is the interesting half. Produced
screenplays run past its 125-page ceiling more than half the time, on both sides
of the draft split. But a produced screenplay is a later artifact than the draft
the rule addresses: scripts are bought at 120 pages and shot at 150. Retuning
from this corpus would have moved the number without improving it. The band needs
a corpus of specs as submitted, which is the one corpus nobody can obtain.
Naming that is worth more than a number would have been.

### 3. F013 was a correct threshold measuring the wrong string

The first pass reported F013 as too strict at p87 and it was going to be
retuned. The draft-stage split says otherwise:

| Population | Median heading | Over 60 characters |
|---|---:|---:|
| Numbered headings, as printed | 65 | **53.4%** |
| The same headings, scene number removed | 30 | 2.8% |
| Unnumbered headings | 29 | 0.8% |

A shooting script prints its scene number at both margins, so
`148A INT. KITCHEN - DAY 148A` is ten characters longer than the identical
heading in the spec it came from. F013 read the string as printed. Identical
writing was flagged or not depending on whether a production department had
renumbered it.

The threshold of 60 was correct all along. The median scene heading is 29
characters whichever population you take. Measuring the slugline without its
number drops the rule from 14.8% of headings to **1.4%**.

This is the exact inverse of F004, and the pair is the argument: **a
quantified rule can fail because its number is wrong, or because the quantity it
measures is wrong, and the second is invisible to every check the first would
pass.** F013's positive fixture exists, passes, and passed before and after the
fix, because nobody writes scene numbers into a hand-made fixture.

It was found by splitting the corpus on a variable that should not have mattered.
That is a method, not luck, and it is the transferable part.

---

## Genre split

Share flagged inside each genre, from `imdb_meta.txt`. A film carries several.

| Rule | Drama 573 | Thriller 412 | Comedy 313 | Action 264 | Crime 260 | Romance 214 | All |
|---|---:|---:|---:|---:|---:|---:|---:|
| F004 action paragraph | 1.9% | 1.7% | 1.9% | 1.6% | 1.7% | 1.7% | 1.7% |
| F016 dialogue block | 4.1% | 3.6% | 4.0% | 3.6% | 3.7% | 3.5% | 3.9% |
| C021 locations per page | 88.0% | 88.6% | 84.3% | 91.3% | 88.8% | 87.9% | 88.4% |
| C028 company moves | 95.5% | 95.1% | 96.2% | 95.8% | 97.3% | 95.8% | 96.4% |
| C038 crowded opening | 61.8% | 62.4% | 67.4% | 70.8% | 63.8% | 59.8% | 64.6% |
| F008 pages | 59.7% | 54.4% | 60.1% | 51.9% | 58.5% | 62.6% | 55.6% |
| **F033 exclamations per page** | 15.4% | 12.6% | **30.4%** | 22.3% | **11.5%** | 16.4% | 20.1% |
| **F036 dialogue share** | 17.1% | 12.6% | **26.2%** | 13.3% | **11.5%** | 23.8% | 18.0% |
| C022 night share | 12.2% | 18.0% | 10.5% | 19.3% | 14.2% | 8.4% | 14.7% |
| F037 scenes per page | 9.8% | 14.6% | 8.9% | 17.0% | 13.5% | 7.0% | 11.1% |

**The headline is negative and it is useful: genre does not explain the
failures.** F004 varies between 1.6% and 1.9% across six genres. C021 varies
between 84% and 91%. C028 between 95% and 97%. A threshold that fails, fails
in every genre, so a genre-aware default would buy nothing on any of the rules
that need help most.

Two rules are genuinely genre-dependent and both make sense. **Comedy carries
2.6 times the exclamation marks of Crime** and **2.3 times the dialogue share**.
Those are the two rules where a genre-aware band would be defensible, and they
are also the two least worth the complexity.

**Sample sizes**, for a follow-up that wants per-genre thresholds rather than
per-genre firing rates. A proportion estimated to plus or minus 2 percentage
points at 95% confidence needs about **2,400 units**. Every element-scale row
clears that inside every genre by two orders of magnitude, so F004's 1.6% to
1.9% spread is a real measurement of a real non-difference.

The document-scale rows do not clear it. At 214 Romance films a 60% firing rate
carries a margin of about 6.6 points, and the difference between two genres
carries roughly 9 points. Only two gaps in the whole table exceed that: F033
(Comedy 30.4% against Crime 11.5%, a gap of 18.9) and F036 (26.2% against 11.5%,
a gap of 14.7). Everything else that looks like a genre effect is noise, which
is the more useful half of this result. Closing the document-scale rows to the
same standard needs roughly **2,400 films per genre**, an order of magnitude
more than ScriptBase holds.

## Draft-stage split

ScriptBase does not label draft stage. Scene numbering is the usable proxy: a
draft that numbers most of its headings has been locked for a shoot.

| Rule | Production draft (284) | Spec-style (798) | All |
|---|---:|---:|---:|
| **F013 heading length, before the fix** | **52.4%** | **0.8%** | 14.8% |
| F013 heading length, after the fix | 3.1% | 0.7% | 1.4% |
| F008 pages | 64.4% | 52.5% | 55.6% |
| F049 dialogue in capitals | 16.0% | 8.1% | 10.9% |
| F007 parentheticals per cue | 25.0% | 19.0% | 20.6% |
| C021 locations per page | 90.1% | 87.7% | 88.4% |
| C028 company moves | 96.0% | 96.5% | 96.4% |
| C038 crowded opening | 65.5% | 64.3% | 64.6% |

This split earned its keep on its first run by finding the F013 defect. It also
answers the strongest objection to F008: production drafts run longer, as
expected, but **spec-style drafts are still 52.5% outside the band**, so the
length result is not an artifact of the corpus skewing toward shooting scripts.

---

## Telugu

Seven drafts, kept in their own container. Every one states its own page count,
which makes its per-page rows more trustworthy than the English ones despite the
size. Element-scale rows rest on 10,199 action paragraphs and are worth reading;
**document-scale rows rest on seven documents and are not**, so they are listed
for the record rather than as findings.

| Rule | Quantity | Ships at | Telugu flags | English flags |
|---|---|---:|---:|---:|
| F004 | lines per action paragraph | 7 | 1.9% | 1.7% |
| F016 | lines per unbroken speech | 6 | 3.2% | 3.9% |
| **F013** | characters per scene heading | 60 | **0.3%** | 1.4% |
| F017 | words per parenthetical | 5 | 4.8% | 1.9% |
| F064 | words per character cue | 5 | 0.0% | 0.2% |
| C023 | pages per scene | 4 | 3.2% | 3.1% |
| C002 | where a recurring part is last seen | 0.65 | **7.4%** | 24.3% |
| C034 | where a recurring location is last used | 0.6 | 28.8% | 30.2% |
| C029 | pages carried by one location | 0.5 | 28.5% | 43.9% |
| C040 | lines in a single-speaker scene | 6 | 11.8% | 14.4% |

**F013 never fired here even before the fix**, which is worth stating because
it is a near miss. Telugu drafts in this container are heavily scene-numbered
(57% of them, median 0.996 of headings), so they carry exactly the artifact that
broke F013 in English. They escaped it because the PDF reader recovers only the
leading scene number from these layouts, not the trailing one, so the heading
gained four characters instead of ten. Had the corpus been Telugu alone the
defect would never have surfaced. After the fix the two containers agree: p95 of
53 characters here against 51 in English, and the rule fires on neither.

**C002 holds in Telugu at 7.4% and fails in English at 24.3%.** A character who
recurs and then disappears before two thirds of the way through is three times
rarer here. That is a claim about the corpus, not about either film industry,
and seven documents cannot support more.

Eleven Telugu PDFs, of which one is a byte-identical duplicate: two of the ten
unique files were refused as unsegmented and one parsed to no scenes, **a read
rate of 7 in 10 against 1,082 of 1,276 (85%) for the English crawl**.
That gap is the OCR problem in [../ocr-fallback.md](../ocr-fallback.md) showing
up as a number, and it is the real blocker on this container, not licensing.

**The page-a-minute convention these bands rest on is an English typesetting
result** and nothing here tests it in Telugu. That is idea
[06](06-page-runtime-cross-language.md) and it is still blocked on runtime data.

---

## What is still not done

**13 parameters remain unmeasurable from a document.** Three similarity cutoffs
need labelled drift pairs. The pilot bands (F043, C027) need a corpus of TV
pilots. F045's interval placement is an Indian-format convention and needs the
Telugu container to grow. Each is named in the harness rather than left blank.

**The 16 hidden literals should move into the rulebook**, or be documented as
deliberate. Until then the claim that rules are data has 16 exceptions.

**One corpus per language.** F004 now has four measurements. Every other row has
one, and [05](05-federated-statistics.md) is the route to a second without
anybody shipping a screenplay.

**No spec corpus.** F008 cannot be settled without one, and neither can the
comparables bands. This is the same bottleneck named in the root CLAUDE.md.
