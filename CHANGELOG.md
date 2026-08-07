# Changelog

Notable changes to Sluglint. Dates are when the work landed rather than when it shipped.

## Unreleased

### Rulebook: 106 rules to 150

- **F049 to F072** (`lint/tier1_style.py`, new): the prose inside the elements.
  Caps as volume, numerals in speech, delivery notes doing the work of action,
  spacing and typography residue from a PDF round trip.
- **C031 to C040** (`lint/tier2_story.py`, new): the cast as a graph (a speaking
  part who never shares a scene, a cast that splits into groups who never meet)
  and reference decay (a set, a thread, or a plant the document never returns
  to).
- **S021 to S030** (tier 3): loose ends. Each one has to name the specific thing
  that was introduced and quote it, which is what keeps them on the checkable
  side of the scope boundary in `CLAUDE.md` rule 10.

### New modules

- `characters.py`: age band, pronoun as written, role, first appearance. Read
  off the page and never inferred from a name. Age parses as a range
  (`late fifties` becomes 56 to 59); pronoun attribution needs 5 observations
  and a 75% majority or it answers `unclear`.
- `network.py`: the co-presence graph. Edges, connected components, cut
  vertices, weighted degree, reach. Numbers only, no verdict.
- `config.py`: `.sluglint.yaml` per project. Disable a rule, re-grade its
  severity, retune its params, allow-list a name, set a minimum severity. It
  cannot invent a rule.
- `logline.py`: generated synopsis and loglines, map-reduce over the script,
  cached per draft. Fenced out of the linter and never a Finding, which a test
  enforces.
- `docs/sluglint.yaml.example`: a commented starting point for the above.

### Eleven engine defects, found by running on real corpora

Full account in [docs/corpus-sweep.md](docs/corpus-sweep.md). Every one of these
was invisible to the fixture suite, which was green throughout.

| Rule | Before | After | Cause |
|---|---:|---:|---|
| F009 | 1,925 | 18 | shooting scripts linted under the spec profile |
| F049 | 1,342 | 1 | a document-scale habit reported per occurrence |
| F002 | 2,070 | 921 | matched the spelling of a time marker instead of its meaning |
| F028 | 1,266 | 251 | a wrapped parenthetical looks unbalanced in each half |
| F004 | 2,043 | 635 | threshold taken from teaching rather than from measurement |
| F055 | 274 | 61 | the same wrap defect in quotation marks |
| F011 | 424 | 240 | one heading convention counted once per heading |
| PDF | n/a | 2 flagged | no ceiling on scenes per page, and the first fix counted the wrong number |

Corpus total went from 18,421 findings to 11,265 across four passes.

### F004 threshold set from data

Across 18,299 action paragraphs in produced screenplays the distribution runs
90% at three lines or fewer, 95% at four, 98% at six, 99% at eight. The rule had
been set at four, which flagged one paragraph in eighteen. It is now seven, the
top 1.4%. `benchmark/mutate.py` grew its injected wall from six lines to ten so
the rule and its test share one definition, and recall returned to 97%.

Writers who want the strict convention get it from config:
`params: {F004: {max_lines: 4}}`.

### Page counts were a third low

`estimated_pages` divided non-blank elements by 55 lines per page, but the
parser drops blank lines and a formatted page carries only about 36.5 lines of
text. Measured against seven produced screenplays with known page counts, the
median ratio was 0.66: Parasite reported 99.6 against a true 144, The Shining
91.8 against 148.

- A PDF states its own page count. `parse_pdf` now hands it to the `Script` and
  nothing derived overrides it.
- `printed_lines()` wraps each element to the column it prints in, because a
  Fountain source holds a whole paragraph on one line while a PDF row is
  already one line.
- `already_wrapped()` decides per document whether the source broke its own
  lines. A crawled text dump wraps action near 67 characters, so re-wrapping it
  at the standard 60 counted every second line twice.
- Scene pages rescale to the real total, so the parts still sum to the whole.

User-facing: F008 bands a feature at 85 to 125 pages, so a 130-page draft was
being told it was 82 pages and too short. Every per-page rule, the runtime
estimate, the eighths, and the dashboard carried the same error. Nothing tested
the page count, which is how it survived; five tests now do.

### Threshold measurement, and three more defects

`benchmark/thresholds.py` measures every numeric parameter in the rulebook
against a corpus, verifies each extractor against the shipped detector, and
keeps corpora in named containers that never pool. Run on **1,082 produced
screenplays** (all 1,276 ScriptBase alpha archives, 194 excluded by the gate),
149,310 scenes, 882,948 action paragraphs. Full results in
[docs/research/threshold-results.md](docs/research/threshold-results.md).

Of 91 numeric parameters: 36 are decision thresholds, 26 are activation gates,
13 cannot be measured from a document. **19 of the 36 flagged more than one unit
in ten of produced practice.**

**C021, C028, and C038 retuned** to the 90th percentile of measured practice.
C021 permitted 0.35 distinct locations per page against a median of 0.67 and
flagged 88% of screenplays; it is now 1.15 and flags 10%. C028 permitted 0.85
and flagged 96%; now 0.99. C038 capped the opening tenth at 8 speaking parts
against a median of 11 and flagged 65%; now 23. Each rule's `principle:` keeps
the taught value and states what replaced it.

**F008 measured and deliberately not retuned.** Produced screenplays run past
its 125-page ceiling 56% of the time, on both sides of the draft-stage split. A
produced screenplay is a later artifact than the spec the rule addresses, so
retuning from this corpus would move the number without improving it.

**F013 was measuring the scene number, not the heading.** A shooting script
prints its number at both margins, so `148A INT. KITCHEN - DAY 148A` is ten
characters longer than the identical heading in the spec it came from. The rule
flagged **52% of numbered headings and 0.8% of unnumbered ones**: identical
writing, judged differently because a production department renumbered it. The
median heading is 29 characters either way, so the 60-character threshold was
right all along. `overlong_heading` now strips the number first, dropping the
rule from 14.8% of headings to 1.4%. Found by splitting the corpus on draft
stage; invisible to its fixture, which has no scene numbers on it.

**Scene pages were up to 30% long on a pre-wrapped source.**
`Scene.estimated_pages` asked each scene individually whether the source had
broken its own lines, and that test needs forty action lines to answer, which a
scene almost never has. Two scenes in one document could disagree. The parser
now decides once and stamps `Scene.prewrapped` on every scene. Affects C023,
C029, and F047.

**The linter and the dashboard disagreed about how long a scene was.** When a
PDF stated its page count the metrics layer rescaled scenes onto it and the
linter did not, so a rule flagging a four-page scene and the dashboard drawing
the same scene read different numbers. `Script.reconcile_pages()` now stretches
the scenes once at parse time and the metrics layer no longer rescales. Scenes
sum to a stated PDF page count within 0.6%.

**The corpus frame was truncated.** The GitHub contents API caps a directory
listing at 1,000 entries and silently returns page 2 identical to page 1, so the
first pass saw 994 of 1,276 archives and every film alphabetically after *The
Godfather Part II* was invisible. The listing now comes from the git trees API,
which reports truncation.

Two gates were added to the harness and both earn their place: a document whose
scene headings were never recognised comes back as one 111-page scene and passes
a "has scenes" check while poisoning every per-page ratio (21 excluded), and a
duplicate weights one film's habits twice (Kill Bill Volumes 1 and 2 are the
same file in ScriptBase).

### Ingest

- `ingest/__init__.py` gained `implausible_density()`. A document running above
  three scenes per page has had a geometry failure, so the reader says so rather
  than emitting hundreds of findings. Checked on the parsed script because the
  PDF reader's own heading tally and the parser's scene count diverge exactly
  when something has gone wrong.
- `ingest/pdf.py` drops lone asterisks, which are revision marks in a production
  draft.

### Metrics and dashboard

- `CharacterMetrics` gained `page_first`, `page_last`, `spans`, `age_band`,
  `pronoun`, `role`, `described`, and a `timeline` string.
- `SceneMetrics` gained `page_start` and `page_end`.
- `ScriptMetrics` gained `network`.
- Fixed voice-only detection: a cue with no extension counts as presence in the
  room, which is the whole test.
- The dashboard draws the co-presence graph and gained cast columns for age,
  pronoun, role, pages present, and scene numbers.

### Docs

- [docs/corpus-sweep.md](docs/corpus-sweep.md), corpus composition and the eight
  defects.
- [docs/ocr-fallback.md](docs/ocr-fallback.md), the OCR design.
- [docs/report-model.md](docs/report-model.md), grouped reporting.
- [docs/research/](docs/research/), the paper-idea tracker, plus
  [threshold-results.md](docs/research/threshold-results.md) with the full
  measurement and [evidence.md](docs/research/evidence.md) as the number ledger.
- README corrected: the test badge said 153 against an actual 208, and the
  inline benchmark numbers were a corpus behind.

### Tier 3 runs on any OpenAI-compatible endpoint

`tier3_llm` gained a second provider, reached over stdlib `urllib` so core
takes no new dependency. Set `SLUGLINT_LLM_BASE_URL` and
`SLUGLINT_LLM_API_KEY` and the same 38 rubrics run on Groq, Cerebras,
OpenRouter, NVIDIA NIM, or Google's compatibility endpoint. Anthropic stays
the default when `ANTHROPIC_API_KEY` is set, and no key at all still means
tier 3 reports itself skipped while tiers 1 and 2 run.

Also new: `SLUGLINT_LLM_RPM` paces calls to a free tier's budget, a 429 is
waited out rather than treated as a failure, and `SLUGLINT_SCENES_PER_CALL`
and `SLUGLINT_MAX_TOKENS` make a small context window workable. A tier-3 call
is about 4,500 input tokens and a 130-scene feature is 22 calls, measured
rather than estimated.

**`FilterStats` counts what each hallucination filter caught.** Every judged
item is attributed to the first filter that rejected it, so the columns sum to
the number proposed, and each run prints a line like `61 findings proposed, 34
kept, 27 dropped (44%) [unknown rule 2, out of window 5, low confidence 11,
not quotable 9]`. Until this existed the claim that tier 3 filters
hallucinations had no number behind it.

Provider data policies matter more than rate limits here and are tabulated in
[docs/tier3-providers.md](docs/tier3-providers.md): some free tiers train on
the prompts they receive, and a screenplay this project may not redistribute is
one it may not hand to a trainer either.

### Known gaps

- **Tier 3 has still never run on a real screenplay.** All 38 tier-3 rules are
  silent in every corpus figure. The plumbing and the measurement now exist;
  the run does not.
- **Precision is unmeasured.** Recall is 97% on injected defects. No labelled
  set exists.
- Findings per 100 pages on the trusted corpus is **249**, and an earlier
  figure of 367 was an artifact of the page bug above.
- F026, F060, and F061 never fire through the PDF path, because ingest rebuilds
  clean Fountain. They are reachable only from Fountain input. F060 in
  particular cannot be measured on a text crawl, which double-spaces
  everything; its 94.5% firing rate on ScriptBase is a fact about the corpus.
- **Fifteen decision thresholds are measured, judged too strict, and not yet
  retuned** (F048, C040, F059, C002, C034, C029, C020, C022, C024, F006, F007,
  F033, F038, F042, F049). One corpus is thin evidence for moving fifteen
  numbers at once; see [05](docs/research/05-federated-statistics.md).
- **16 numeric literals sit in detector code rather than in the rulebook**,
  found by an AST walk. Each is a decision no rulebook edit can reach, and four
  of them are why the threshold harness disagrees with the linter on four rules.
- **Telugu has 7 usable documents.** Element-scale numbers rest on 10,811 action
  paragraphs and are worth reading; document-scale numbers rest on 7 documents
  and are not. The blocker is OCR, not licensing: 3 of 10 unique files were
  refused.
