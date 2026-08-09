# 03. Ingestion confidence as an evaluation gate

**Status: medium. Real numbers in hand, needs framing work.**

## Claim

For any analysis pipeline over PDFs, ingestion failure masquerades as content
defect. The failure rate on real documents is high enough that an evaluation
which does not gate on ingest confidence is partly measuring its own reader.

A parser that reports confidence in its own output, and a downstream stage that
refuses to score low-confidence documents, should be standard. It currently is
not.

## Evidence

Of 49 readable documents in the [corpus sweep](../corpus-sweep.md):

- **33 trusted**, 16 flagged unreliable, and 7 more refused outright before that.
- **A third of real PDFs land outside the trusted state.**
- Two documents parsed at 5.7 and 6.2 scenes per page. No screenplay runs at
  that rate. The geometry had failed and ordinary lines were being read as scene
  headings, and each of those documents emitted over a thousand findings.

The failure modes are distinct and worth separating:

- **No text layer.** Scanned pages.
- **Broken character map.** Text present, renders correctly, extracts as
  garbage. Middle Class Melodies.
- **Legacy encoding.** Pre-Unicode Indic DTP fonts carry glyph positions with no
  recoverable text.
- **Not the document you think.** A censor transcript rather than a screenplay.

The multilingual dimension is sharp: of seven Telugu documents, three read
cleanly. The same pipeline on English documents reads 13 of 17. That gap is not
about the language, it is about the typesetting stack that language was
published with, and it means any cross-lingual document study inherits a
confound before the first measurement.

## What the reader does about it

Three states rather than two: **read**, **suspect**, **refused**. The middle one
is the contribution. A reader that only succeeds or fails will silently succeed
on a document it has mangled.

The checks that produce the states are cheap and generalise:

- text confidence, the share of well-formed words in the extracted layer
- dropped-glyph share, which catches a broken character map directly
- a **floor and a ceiling** on structural density. The floor was there from the
  start; the ceiling was the eighth defect in [02](02-fixture-corpus-gap.md).
- second-column share, which catches a document that is not a screenplay

The ceiling had a second bug inside it worth reporting, because it generalises:
the first version checked the count the PDF reader's own classifier produced
against the PDF's page count. The number that matters is what the downstream
parser finally built. Those two agree on healthy documents and diverge exactly
on broken ones, which is to say the check was blind precisely when it was
needed.

## The experiment

**Quantify the cost of not gating.** Compute every headline number over the full
49 and over the trusted 33. The gap between them is the size of the error an
ungated evaluation would have reported. On findings per 100 pages this is
already visible: 11,265 over 2,933 pages against 6,504 over 1,771.

**Generalise beyond screenplays.** The claim is about document pipelines, so it
wants a second domain. Any PDF corpus with a downstream structured task will do.

## Risks and objections

**"Everyone knows PDFs are hard."** Known and not reported. The contribution is
the number (a third), the three-state design, and the observation that the
natural place to put a plausibility check is downstream of the parser rather
than inside the reader.

**"Your confidence checks are ad hoc."** They are, and they are domain-specific.
The transferable part is the shape rather than the thresholds.

## Blocked on

Nothing to write it. The OCR work in [../ocr-fallback.md](../ocr-fallback.md)
would let the paper report a before and after on the refusal rate, which would
make it considerably stronger.

## Venue shape

Document engineering or document analysis. Fits as a short paper.
