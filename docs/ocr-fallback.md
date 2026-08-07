# OCR fallback

Design for the pages the geometry reader cannot read. Not yet built.

## Why it is needed

A third of the documents in the [corpus sweep](corpus-sweep.md) came back
outside the trusted state, and the Telugu set is the worst of it: of seven
files, three read cleanly, three were suspect, and one was refused outright.

Three distinct failures hide under "cannot read":

1. **Scanned pages.** No text layer at all.
2. **Broken character maps.** Text is present and renders correctly on screen,
   but the glyph-to-Unicode mapping is wrong, so extraction returns garbage.
3. **Pre-Unicode Indic fonts.** Telugu publishing ran on legacy DTP fonts (the
   Anu family and its relatives) for decades. A PDF typeset that way carries
   glyph positions with no recoverable text.

Rendering the page and reading the pixels fixes all three, because in every case
the page looks right to a human.

## The pipeline

Per page rather than per document. `text_confidence()` already scores the text layer;
make it per page and OCR only the pages that fail. A production draft with three
scanned inserts then works, and a clean document pays nothing.

```
page -> text layer -> confidence ok?  -> yes: use it
                                      -> no:  render at fixed DPI
                                              -> OCR backend chain
                                              -> Lines
```

### Backends, in order

**Apple Vision**, through `ocrmac`, on macOS. On-device, fast, no network,
already a dependency pattern this project uses elsewhere.

**Tesseract** with `tel` and `hin` traineddata, everywhere else and for every
language Vision does not cover.

Vision does not recognise Telugu or Devanagari. Do not hardcode that: ask at
runtime with `VNRecognizeTextRequest.supportedRecognitionLanguages()` and route
on the answer, because the list grows between OS releases. If neither backend
covers the document's script, the reader refuses, the way it does today.

Both sit behind one interface whose job is to return `Line` objects. That is the
whole integration: the OCR path plugs in above `_rows()`, and `_body_size`,
`_action_margin`, `_classify`, `_emit`, and the margin learning all work
unchanged.

### The one thing to get right

`ocrmac` defaults to `detail=False`, which returns bare strings. That discards
the bounding boxes, and this reader classifies **entirely by geometry**. Use
`detail=True`, which gives `(text, confidence, quad)` per observation, flip the
y axis (Vision uses a bottom-left origin, pdfplumber uses top-left), and scale
by the render size.

Capability gating follows the tier-3 shape: `is_available()`, an empty result on
any failure, and never a crash.

## Stamps, signatures, and handwriting

Censor scripts carry a signature on every page. Production drafts carry
watermarks. Annotated drafts carry a director's handwriting in the margin. None
of it is script text and all of it OCRs.

The reframe: do not filter text, filter geometry. A screenplay is the most
rigid document format in common use, and the reader already learns each
document's own margins. Furniture loses because it does not respect columns.

**1. Cross-page repetition. Build this first.** Bucket every observation by
(rounded x, rounded y, casefolded text) and drop any bucket appearing on more
than about 60% of pages. This kills watermarks, censor stamps, registration
seals, production banners, and running heads in one pass. Script text never
repeats at a fixed position across a document; furniture is defined by doing so.
It improves the text-layer path too, so it pays for itself before OCR ships.

**2. Column discipline.** Already built. `COLUMN_SHARE` requires a left edge to
carry 4% of the document's rows before it counts as a column, so a signature at
bottom right, a margin note, or a corner stamp never accumulates enough to
become one.

**3. Display type.** Already built as `DISPLAY_TYPE_RATIO`, which drops anything
over twice body size. OCR has no font size, so substitute bounding-box height
and use the median observation height as body size. Same constant.

**4. Rotation.** Watermarks and stamps are usually diagonal. The text path uses
pdfplumber's `upright`; the OCR path computes the baseline angle from the quad
and drops anything more than a few degrees off horizontal.

**5. Confidence.** Handwriting scored by a print-oriented recogniser comes back
low while clean print comes back high. A threshold near 0.5 is the last layer,
not the first.

### What none of this solves

A handwritten revision inserted into the dialogue column, at the right indent,
over the print. Confidence catches most of it. The geometry filters cannot help,
because the whole point is that it sits in the right place.

Do not pretend otherwise. Reduce it to a flag. An OCR'd page should raise the
bar for acceptance rather than lower it, and `implausible_density()` remains the
backstop. A reader that says "this page is annotated, treat its findings as
unreliable" is honest. One that lints a director's handwriting as dialogue is
the thing `CLAUDE.md` rule 4 exists to prevent.

## Order of work

1. Per-page text confidence, so OCR is only paid for where it is needed.
2. Cross-page repetition filter, on the existing text path.
3. Vision backend with `detail=True` and runtime language gating.
4. Tesseract backend for Indic scripts.
5. Rotation and bbox-height filters on the OCR path.
