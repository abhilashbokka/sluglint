# Corpus options for the threshold study

Which public screenplay corpus can carry [01](01-thresholds-vs-practice.md), and
why the obvious answer is the wrong one.

## The decision

**Use ScriptBase.** It is the only public corpus that preserves the thing a
format linter measures.

| Corpus | Scripts | Licence | Element types | Line breaks | Punctuation | Metadata |
|---|---:|---|---|---|---|---|
| **ScriptBase** | 1,276 | **none stated** | inferred by the parser | **preserved** | **preserved** | genre, year, IMDb score, keywords, logline |
| MovieSum | 2,200 | CC BY-NC 4.0 | **labelled in XML** | destroyed | **tokenized** | IMDb id, year |
| Film Corpus 2.0 | 1,068 | none stated | separated, not labelled | unknown | unknown | none published |
| STAGE | 151 (109 en, 42 zh) | unclear | scene JSON | normalised | unknown | none published |

## Why the better-licensed, larger corpus loses

MovieSum is the one that should win. It has 2,200 screenplays against
ScriptBase's 1,276, it carries an actual CC BY-NC 4.0 licence that matches this
project's own noncommercial position, and every element is explicitly tagged in
XML rather than guessed at by a parser.

Then you read the text. From `The Boondock Saints`:

```
<scene_description>DOWNTOWN BOSTON As we open we see the inside of an enormous
church . A young looking PRIEST in his mid - thirties is finishing the delivery
of the Lord 's Prayer . ... CONNOR and MURPHY MacMANUS -LRB- mid - twenties -RRB-
are shrouded in thick waist length navy P - coats ...</scene_description>
```

Three things are gone, and each one takes a class of rule with it:

- **Line breaks.** Zero of 377 scene-description blocks in that script contain an
  internal newline. Every action paragraph is one reflowed string, so a line
  count cannot be recovered. F004 is the flagship result of the study and it
  counts lines.
- **Punctuation.** The text is Penn Treebank tokenized. Spaces before every
  period, spaces around hyphens, and parentheses replaced by `-LRB-` and
  `-RRB-`. F070 (spacing around punctuation) would fire on every sentence, F027
  (typographic characters) is meaningless, and F028 (unbalanced brackets) has no
  brackets left to balance.
- **Character counts.** The inserted spaces make every width measurement wrong,
  which takes F013 (heading length) and F017 (parenthetical length) with them.

The corpus was built for abstractive summarization, where none of this matters.
It is a good dataset that answers a different question.

## What ScriptBase preserves

The raw `script.txt` is the crawled screenplay with its typesetting intact:

```
     ANGLE ON YOUNG COLE, flanked by his PARENTS, their faces out of
     view, as they steer him away.

                    FATHER'S VOICE (o.s.)
          Come on, Son --this is no place for us.
```

Five-space action indent, twenty for the cue, ten for dialogue. Original line
breaks, original capitalisation, original punctuation, extensions in place. This
parses through Sluglint today with no ingest work: 12 Monkeys reads as 91.6
pages, 173 scenes, 103 speaking parts.

Per-film metadata sits in `processed/imdb_meta.txt` as tab-separated
`genre`, `year`, `imdb score`, `meta score`, and `keyword` rows, plus a logline
and taglines in `logTag.txt`. That is the stratification the study needs, and it
is the second reason to pick this corpus.

## Two problems to handle, not ignore

### Licence

ScriptBase has **no LICENSE file and no terms-of-use statement**. The scripts
were crawled, and the underlying screenplays are copyrighted by their studios
and writers.

What this permits and forbids:

- **Permitted:** analysing the text and publishing statistics derived from it.
  This is an established academic corpus behind two published papers
  (Gorinski and Lapata, 2015 and 2018), and computing distributions over
  copyrighted text is ordinary research practice.
- **Forbidden here:** committing any of it. Not a script, not an excerpt, not a
  fixture derived from one. `benchmark/corpus/` stays gitignored, per
  `CLAUDE.md` rule 9.
- **Required in a paper:** a data statement that says where it came from and
  that it is not redistributed by us. Reproduction runs through
  [05](05-federated-statistics.md): publish the measuring code, and a third
  party runs it on their own copy.

### The wrap-width confound

A line count is only meaningful at a known column width. Screenplay action prints
at 12pt Courier across a six-inch measure, which is 60 characters. A crawled text
file wraps wherever its source wrapped, and sources differ.

**Normalise before counting.** Re-wrap every action paragraph at 60 characters
and count the result. This makes line counts comparable across documents of
different provenance, and it is the more correct measurement anyway: the rule is
about how the paragraph prints at standard margins rather than about how one
writer's software happened to break it.

That normalisation also removes the study's dependence on format-preserving
sources for line-based rules, which is worth stating in the method section
because it is the part other people can reuse.

## Two classes of rule, two data requirements

The corpus comparison above resolves into a cleaner statement. Of the 54 rules
carrying numeric params:

**Class A needs original typesetting.** Line counts, character counts,
whitespace, capitalisation, punctuation. F004, F013, F016, F017, F032, F038,
F060, F064, F070. Only ScriptBase serves these, and only with normalisation.

**Class B needs element structure only.** Counts, ratios, presence. F006, F007,
F008, F033, F036, F037, F047, F048, C020 to C029. MovieSum serves these fine at
2,200 documents, and its labelled element types are an advantage over inferring
them.

So the honest answer is to use both, for different halves of the table, and say
which corpus produced which row. A study that reports 2,200 documents for the
ratio rules and 1,276 for the line rules is stronger than one that forces a
single corpus to do both jobs badly.

## Parse failures are part of the finding

Roughly one ScriptBase file in seven parses to zero scenes. Crawled HTML,
transcripts, and drafts whose formatting never survived the crawl.

That is [03](03-ingestion-confidence.md) reappearing in a text corpus rather
than a PDF one, and it means the threshold study needs the same three-state gate
the PDF reader has. A document that parses to zero scenes must be excluded from
every distribution, and the exclusion count must be reported.

## Sources

- ScriptBase: <https://github.com/EdinburghNLP/scriptbase>
- MovieSum: <https://huggingface.co/datasets/rohitsaxena/MovieSum>
- Film Corpus 2.0: <https://nlds.engineering.ucsc.edu/fc2>
