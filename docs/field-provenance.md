# Field provenance: where every number comes from

This document answers one question for every value the linter reasons about:
**did the document say this, did we work it out, or did we assume it?**

The ordering is a rule, not a preference:

> **Stated beats derived. Derived beats assumed.**
> If the source file carries a fact, read it. Never recompute a fact the file
> already states, and never assume one the file could have told us.

The reason is narrow and practical. A wrong measurement does not announce
itself as a wrong measurement. It arrives dressed as a finding about the
script, and the writer has no way to tell the two apart. Every value below is
therefore labelled with one of three provenance classes:

| class | meaning | how much we trust it |
|---|---|---|
| **STATED** | the file says it; we read it | exact |
| **DERIVED** | the file does not carry this fact, so we compute it from facts it does carry | as good as the method, and the method is written down |
| **ASSUMED** | a constant we brought with us | a liability, and every one is listed |

An ASSUMED value is not automatically wrong. It is automatically **owed a
measurement**, which is what `benchmark/thresholds.py` exists to provide.

---

## 1. The pipeline

```
   script.pdf                         script.fountain
       |                                     |
       v                                     |
  pdfplumber  ......... STATED page facts    |
       |                                     |
       v                                     |
   _rows()      words -> visual rows         |
       |                                     |
       v                                     |
  _body_size(), _action_margin()             |
       |        ... DERIVED page geometry    |
       v                                     |
  _classify()   geometry -> element type     |
       |                                     |
       v                                     |
   _emit()      rows -> Fountain text        |
       |        + page_map, one entry per line
       |                                     |
       +------------> parse_text() <---------+
                          |
                          v
                    Script{Scenes[Elements]}
                          |
                   _stamp_pages()  ... STATED page back onto each Element
                          |
                          v
                    run_rules()  -> Findings
```

Two properties of this shape matter.

**One parser.** The PDF reader emits Fountain and hands it to the same parser a
typed draft goes through. A PDF must not get a quieter reading of the same
rulebook than a `.fountain` file does.

**One trip through the bridge.** Because the PDF's structure is re-expressed as
text, anything the PDF knew that the text cannot carry has to be carried
*alongside* it. That is what `PdfIngest.page_map` is: a parallel list, one entry
per emitted line, holding the page that line printed on. Losing it is how page
numbers came to be estimated in the first place.

---

## 2. Provenance, field by field

### From the PDF

| field | class | source | code |
|---|---|---|---|
| `Script.page_count` | **STATED** | `len(pdf.pages)` | [pdf.py:416](../src/sluglint/ingest/pdf.py#L416) |
| `Element.page` | **STATED** | `page.page_number` per row, carried through `page_map` | [pdf.py:113](../src/sluglint/ingest/pdf.py#L113), [pdf.py:329](../src/sluglint/ingest/pdf.py#L329) |
| `Scene.page` | **STATED** | the page of the scene's first element | [models.py:142](../src/sluglint/models.py#L142) |
| `Line.x0`, `x1`, `top` | **STATED** | word bounding boxes | [pdf.py:113](../src/sluglint/ingest/pdf.py#L113) |
| page height | **STATED** | median `page.height` | [pdf.py:376](../src/sluglint/ingest/pdf.py#L376) |
| body font size | **DERIVED** | modal rounded `char["size"]` over 12 pages | [pdf.py:139](../src/sluglint/ingest/pdf.py#L139) |
| action margin | **DERIVED** | leftmost left-edge clearing a 4% share of rows | [pdf.py:184](../src/sluglint/ingest/pdf.py#L184) |
| line leading | **DERIVED** | median vertical step between rows | [pdf.py:132](../src/sluglint/ingest/pdf.py#L132) |
| paragraph break | **DERIVED** | a vertical step > 1.5x the leading | [pdf.py:135](../src/sluglint/ingest/pdf.py#L135) |
| element type | **DERIVED** | indent from the action margin, in inches | [pdf.py:214](../src/sluglint/ingest/pdf.py#L214) |
| text confidence | **DERIVED** | share of Latin tokens with mid-word capitals | [pdf.py:153](../src/sluglint/ingest/pdf.py#L153) |

### From the model layer

| field | class | source | code |
|---|---|---|---|
| `Script.estimated_pages` | **STATED** when `page_count` is set, otherwise **DERIVED** | real count, else printed lines / 36.5 | [models.py:166](../src/sluglint/models.py#L166) |
| `Scene.estimated_pages` | **DERIVED**, and still an estimate even for a PDF | printed lines / 36.5, scaled onto the real total | [models.py:147](../src/sluglint/models.py#L147) |
| `Scene.page_scale` | **DERIVED** | one global factor: real pages / summed estimate | [models.py:179](../src/sluglint/models.py#L179) |
| `Script.prewrapped` | **DERIVED** | spread between the median and 99th-percentile action line | [models.py:71](../src/sluglint/models.py#L71) |
| `Element.type` (Fountain) | **DERIVED** | line shape and blank-line context | [parser.py:126](../src/sluglint/parser.py#L126) |

### Why "margin" is legitimately DERIVED

A PDF has **no margin field**. Margins are a word-processor concept. What a PDF
carries is a page box and a set of glyph positions, so the only honest way to
recover a margin is to find the column the text actually starts at. That is
what `_action_margin` does, and it is derived by necessity rather than by
laziness.

The same is not true of the page number, which the file states outright. That
distinction is the whole point of this document.

---

## 3. Worked example: how `Element.page` is gathered

Tracing one field end to end, because the general shape is easier to trust
after seeing a specific case.

1. **pdfplumber states it.** `page.page_number` is a property of the page object
   the library yields. Nothing is computed.

2. **`_rows()` attaches it to the row.** Words are bucketed into visual rows by
   rounded vertical position, and the resulting `Line` carries
   `page=page.page_number` alongside its `x0`, `x1` and `top`.
   [pdf.py:113](../src/sluglint/ingest/pdf.py#L113)

3. **`_emit()` keeps it beside the text.** Every time a line of Fountain is
   written, its page is appended to a parallel list. Blank lines, which the
   Fountain format needs and the PDF never had, get `None`.
   [pdf.py:271](../src/sluglint/ingest/pdf.py#L271)

4. **`ingest()` prefixes the cover.** The title-page block is page one by
   construction, since `_title_page` only ever reads page one.
   [pdf.py:396](../src/sluglint/ingest/pdf.py#L396)

5. **`parse_text()` numbers the elements by line.** The Fountain it parses is
   exactly the list `_emit` produced, joined with newlines, so element
   `line_no` indexes straight back into `page_map`.

6. **`_stamp_pages()` puts it back.** `page_map[el.line_no - 1]`. Scenes and the
   script share the same `Element` instances, so stamping once reaches every
   layer. [pdf.py:329](../src/sluglint/ingest/pdf.py#L329)

The risky step is 5, and it is risky in a specific way: one stray blank line on
either side of the bridge shifts every page by one, silently. That is why
`test_the_page_a_line_printed_on_survives_the_trip_through_fountain` asserts on
the pages of named elements rather than on the length of the list.

**Counter-example.** `Scene.estimated_pages` is the same field one level up and
is still DERIVED. A scene's share of the document is computed by wrapping each
element to its column, counting lines, and dividing by 36.5, then stretching
the result so the scenes sum to the real page count. Every step after "real
page count" is an estimate. See section 5.

---

## 4. What the source states and we currently discard

Each row is a fact the file hands us for free and we drop on the floor.

| fact | available as | currently | consequence |
|---|---|---|---|
| **page width** | `page.width` (612 pt = 8.5in on the fixture) | collected into `widths` at [pdf.py:358](../src/sluglint/ingest/pdf.py#L358) and **never read** | no rule can normalise a measurement against page size, which is what makes a 5.5-inch-wide script look like 9pt type |
| **page box** | `page.mediabox`, `page.cropbox` | never read | A4 vs US Letter vs a reduced box is invisible to us |
| **font name** | `char["fontname"]`, e.g. `AAAAAA+CourierNewPSMT` | never read | the typography rules have no input |
| **character advance** | `char["adv"]` | never read | monospace could be tested by advance width, which survives the font-name stripping that embedded subsets do |
| **page rotation** | `page.rotation` | never read | a rotated page would be read with the wrong geometry and never flagged |

None of these are hard to wire. They are listed here so the gap is a decision
rather than an oversight.

---

## 5. What is still estimated, and what it would take to stop

**Scene length.** `Scene.estimated_pages` wraps each element to a nominal column
width and divides by 36.5 text lines per page. For a PDF this is avoidable: we
now know the page each element printed on, and `Line.top` gives the vertical
position within that page. A scene's true extent is
`(end_page + end_fraction) - (start_page + start_fraction)`. Carrying the
vertical fraction the way the page number is now carried would move this row
from DERIVED to STATED.

Until that happens, the current approach is at least bounded: `reconcile_pages`
stretches the scenes so they sum to the real total, so the error is in the split
between scenes rather than in the document length.

**Everything a `.fountain` file cannot state.** Text has no pages, no fonts and
no margins. `Element.page` is `None` there, and that is correct. A rule about
pagination must stay silent on a text draft rather than estimate one.

---

## 6. The assumed constants

Every one of these is a number we brought rather than measured. They are listed
so they can be argued with and so `benchmark/thresholds.py` knows what to aim at.

### Ingest ([pdf.py](../src/sluglint/ingest/pdf.py))

| constant | value | what it decides |
|---|---|---|
| `POINTS_PER_INCH` | 72.0 | a unit, not an assumption |
| `DIALOGUE_INDENT` | 0.6 in | at what indent a row becomes dialogue |
| `CHARACTER_INDENT` | 1.6 in | at what indent a row becomes a character cue |
| `DISPLAY_TYPE_RATIO` | 2.0 | above this multiple of body size, a word is a watermark |
| `MARGIN_BAND` | 0.06 | the head and foot band where folios live |
| `COLUMN_SHARE` | 0.04 | the share of rows a left edge needs to count as a column |
| `PARAGRAPH_GAP` | 1.5 | the multiple of leading that means a blank line |
| `TEXT_CONFIDENCE_FLOOR` | 0.95 | below this, the text layer is glyph codes |
| `SECOND_COLUMN_FLOOR` | 0.15 | above this, the page is not screenplay geometry |
| `DROPPED_GLYPH_FLOOR` | 0.02 | above this, the font's character map is broken |
| `MIN_HEADINGS_PER_PAGE` | 0.1 | below this, structural rules have nothing to run on |

### Model ([models.py](../src/sluglint/models.py))

| constant | value | what it decides |
|---|---|---|
| `BODY_LINES_PER_PAGE` | 36.5 | measured against 7 produced screenplays with known page counts |
| `COLUMN_WIDTH` | dialogue 35, parenthetical 25 | printed width at 12pt Courier |
| `DEFAULT_COLUMN` | 60 | printed width of an action line |

### Measured against the geometry a real tool ships

WriterSolo's bundled `screenplay.wdt`, read out of the application:

| element | absolute | offset from the action margin |
|---|---|---|
| page left margin | 1.500 in | (right, top, bottom 1.000 in) |
| action, scene heading | 1.500 in | 0 |
| dialogue | 2.500 in | 1.0 |
| parenthetical | 3.000 in | 1.5 |
| character cue | 3.500 in | 2.0 |

Against that geometry, the tolerance of each classification before the learned
action margin misreads it:

| element | offset | margin may be this far left | this far right |
|---|---|---|---|
| action | 0.00 in | -0.60 | +0.80 |
| dialogue | 1.00 in | -0.60 | +0.39 |
| **parenthetical** | **1.50 in** | **-0.09** | +0.80 |
| character | 2.00 in | -0.80 | +0.39 |

`CHARACTER_INDENT` at 1.6 sits a tenth of an inch above where a real tool puts
its parentheticals, so a parenthetical has a twelfth of the headroom every other
element has. The midpoint of the two columns is 1.75. A better fix than moving
the threshold is to stop relying on geometry alone: a cue written in brackets
(`(VOICE ON THE PHONE)`) is uppercase and a delivery note (`(not looking up)`)
is not, and case does not drift.

Not yet changed, because changing the classifier invalidates every corpus
measurement taken with it.

---

## 7. Dead values

Found while writing this document. Each is a value that no longer decides
anything, which makes it worse than an assumption: it reads as a live decision.

| name | where | status |
|---|---|---|
| `LINES_PER_PAGE = 55.0` | [models.py:18](../src/sluglint/models.py#L18) | superseded by `BODY_LINES_PER_PAGE`; no reader |
| `MAX_HEADINGS_PER_PAGE = 3.0` | [pdf.py:63](../src/sluglint/ingest/pdf.py#L63) | the live check is `MAX_SCENES_PER_PAGE` in [ingest/__init__.py](../src/sluglint/ingest/__init__.py); no reader |
| `widths` | [pdf.py:354](../src/sluglint/ingest/pdf.py#L354) | `page.width` is collected every page and never read |

---

## 8. The rule this document exists to enforce

Before adding any value to `Script`, `Scene` or `Element`, answer in order:

1. **Does the source file state this?** Read it. Stop.
2. **Does the source carry facts this can be computed from?** Derive it, and
   write the method down next to the code.
3. **Neither?** Then it is a constant, it goes in the table in section 6, and it
   is owed a measurement against the corpus.

And the check that catches the failure this whole document is about: if a value
is presented to a writer as a fact about their script, it has to be traceable to
a row in section 2. Anything that cannot be traced is a finding about our
measurement wearing the costume of a finding about their screenplay.
