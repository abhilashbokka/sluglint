# Reading a screenplay out of a PDF

PDF is the format scripts actually circulate in. Until Sluglint could read one,
every claim about linting real drafts came with an asterisk.

## Why geometry rather than a model

A screenplay page is not free-form. It is five columns on a fixed grid:

| Element | Left edge | Distance from the action margin |
|---|---|---|
| Scene heading | 1.5 in | 0 |
| Action | 1.5 in | 0 |
| Dialogue | 2.5 in | +1.0 in |
| Parenthetical | 3.0 in | +1.5 in |
| Character cue | 3.7 in | +2.2 in |
| Transition | flush right | |

Every screenwriting program in use emits that layout, so the horizontal
position of a line is a near-perfect label for what the line *is*. That signal
survives a PDF export intact even when every other structural hint is gone.

The margins themselves are not assumed. `_action_margin()` learns them from the
document: it takes the leftmost left edge that carries at least 4% of the rows.
Leftmost rather than commonest, because dialogue outnumbers action in plenty of
scripts, and because scene numbers and page folios sit further left than either.
That one decision is what makes A4, US Letter, and the shrunken page boxes some
exporters write all read the same.

A document-layout model (LayoutLMv3 and its relatives) would be the wrong tool
here. Those earn their keep on layouts that vary between documents: invoices,
forms, reports. This layout does not vary, so a rule reads it exactly where a
model would read it probabilistically, needs no labelled training data, adds no
inference cost, and can explain every decision it made. The place a model earns
its keep in this project is tier 3, which already exists.

## What gets normalized away

Two things on the page belong to the printer rather than the writer, and
leaving them in would invent findings that exist in no draft:

- **Page numbers and running heads.** Dropped when they sit in the top or
  bottom 6% of the page.
- **The `(MORE)` / `NAME (CONT'D)` pair** a paginator inserts when a speech
  crosses a page break. The speech is put back together, and the count of
  rejoins is reported.

Because those are removed, **F025 (pagination artifacts) cannot be judged from
a PDF**, and the ingester says so in its notes rather than quietly passing.

Everything else is kept. A PDF must not get a quieter reading of the same
rulebook than a `.fountain` file does.

Dropping the printed folio is not the same as forgetting which page a line was
on. The page number belongs to the printer; the *fact* that a line fell on page
47 belongs to the document, and pdfplumber states it for every row. That number
is carried out to Fountain alongside the text (`PdfIngest.page_map`) and put
back on the elements after parsing (`Element.page`, `Scene.page`), so a rule
that needs to know where a page break fell reads it instead of deriving it.
A `.fountain` draft has no pages and every element's `page` stays `None`; a
rule about pagination has to stay silent there rather than estimate.

## Back out to Fountain

The ingester emits a Fountain document and hands it to the existing parser
rather than building a `Script` directly. That keeps one parser and one set of
semantics, it lets a writer inspect what we believe their PDF says
(`sluglint convert script.pdf`), and it means a defect the Fountain parser
trips over in a typed script trips over it here too.

The one place geometry has to override the text is Fountain's forced-action
marker. `THE KITCHEN` at the action margin is a mini-slug; to a line-based
parser it is shaped exactly like a character cue, and read that way it would
invent a character, inflate the speaking-cast count, and fire the single-use
character rule. Geometry knows better, so those lines go out as `!THE KITCHEN`.

## Refusing to lint what we cannot read

Not every PDF is readable, and reporting confident findings on one that is not
would be worse than reporting nothing. Three checks run before linting, each
producing a note on the report:

**Text-layer confidence.** Pre-Unicode Indic fonts (Krutidev, Shree-Lipi,
Priyaanka and their relatives) map Devanagari and Telugu glyphs onto Latin code
points. The page prints perfectly and extracts as `lhfu;j jSfxax`, which has
letters, spaces, and plausible word lengths, so length and density checks all
pass it. What gives it away is shape: mid-word capitals and stray punctuation,
because those code points were chosen to draw a glyph rather than to spell
anything. A separate check counts NUL and replacement characters, which is how
a partially broken character map announces that it is dropping conjuncts.

**Second-column share.** A character cue is a name: short, alone on its line.
When most of the text two inches in is full-width running text, the page is a
published edition with a translation column, or a transcript, or something
whose margins we have read wrong. Across the corpus below this separates
cleanly: real screenplays put 0 to 3% of their cue-depth text over two inches
wide; the others put 20 to 70%.

**Slugline density.** Under one INT./EXT. heading per ten pages means the scene
headings are written some other way, and the structural and continuity rules
have nothing to run on.

## Measured against a private corpus

Development ran against nine Indian-language feature screenplays (Telugu and
Hindi) held privately. They are not in this repository and never will be; see
[public-domain-scripts.md](public-domain-scripts.md) for why.

Four read cleanly. Five were rejected by the checks above: two set in
pre-Unicode fonts, one whose character map drops conjuncts, one published prose
edition, one censor transcript. That ratio is worth stating plainly, because it
is the real state of the format rather than a benchmark chosen to flatter.

Running against real scripts is also what found the following, none of which
any synthetic fixture had caught:

| Defect | Effect before the fix |
|---|---|
| `EXTENSION_RE` accepted only a straight apostrophe in `(CONT'D)` | Final Draft writes the typographic one, so every continued speech forked into a second character. 61 false name-drift errors on one 85-page script. |
| `HEADING_RE` matched `INT./EXT.` but not `EXT./INT.` | The prefix parsed as `EXT` and `/INT.` went into the location name, so one set read as two. |
| `long_action_block` counted every action line between two speeches | Three separate two-line beats reported as one wall of text. |
| A parenthetical wrapping onto a second line | The closing bracket landed in the dialogue, so every wide aside reported an unbalanced bracket. |
| `name_drift` compared whole cue strings | "BRIDE'S FATHER" and "RICHA'S FATHER" are 87% alike and two actors. Same for "SENIOR 1" and "SENIOR 2". |
| `unpaid_prop` keyed on an article before a capitalised word | "a MOAN" reported as a prop the art department should track. |

Each has a regression test in `tests/test_sluglint.py` under
*real-script parsing*.

`benchmark/local_report.py` is what produced that list. Point it at a directory
of scripts and it writes a per-script findings file to `benchmark/local/`,
which is gitignored because the output names real scripts and quotes them. It
is the precision half of the harness: `run.py` measures recall against defects
we injected, and this one produces the findings a human has to read and judge.

## What it still cannot do

- **Scanned pages and pre-Unicode fonts.** Detected and refused, not read. The
  fix is an OCR fallback. Apple's Vision framework (via `ocrmac`) is fast and
  on-device but does not recognise Telugu or Devanagari, so this needs
  Tesseract with `tel` and `hin`, capability-gated the same way the LLM tier is.
- **Dual dialogue.** Two speeches printed side by side are read in row order.
- **Revision marks and coloured pages.** Ignored.
- **FDX.** Next, and much easier: it is XML with the element types already named.
