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

### Eight engine defects, found by running on 49 real drafts

Full account in [docs/corpus-sweep.md](docs/corpus-sweep.md). Every one of these
was invisible to the 208-test fixture suite.

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
- [docs/research/](docs/research/), the paper-idea tracker.
- README corrected: the test badge said 153 against an actual 208, and the
  inline benchmark numbers were a corpus behind.

### Known gaps

- **Tier 3 has never run on a real screenplay.** All 38 tier-3 rules are silent
  across the 49-document sweep because it ran with the LLM tier off.
- **Precision is unmeasured.** Recall is 97% on injected defects. No labelled
  set exists.
- Findings per 100 pages on the trusted corpus is **249**, and an earlier
  figure of 367 was an artifact of the page bug above.
- F026, F060, and F061 never fire through the PDF path, because ingest rebuilds
  clean Fountain. They are reachable only from Fountain input.
