# 05. Federated statistics over an unshareable corpus

**Status: method is clear, no contributors yet. This is the unlock for
[01](01-thresholds-vs-practice.md).**

## Claim

Distributional claims about a corpus that cannot be redistributed can still be
reproducible, if the unit of exchange is the statistic rather than the document.
A contributor runs a local computation and shares a small, human-readable record
of counts. Nobody ever holds a corpus, and a third party can check the result
against a corpus of their own that they also cannot share.

## Why this project needs it

The threshold study needs about fifty produced screenplays and cannot legally
hold them. Screenplays are copyrighted, chain of title is often contested, and
the datasets circulating on Kaggle and Hugging Face under permissive licences
are mislabelled crawls. `benchmark/corpus/` is gitignored for exactly this
reason and always will be.

But the study does not need the text. It needs the length distribution of action
paragraphs. **A page count is a fact about a document, and facts are not
copyrightable expression.** The same is true of scene counts, cast size, night
share, and every threshold in the rulebook.

## The mechanism

`sluglint stats --contribute` runs locally and emits counts only:

```json
{
  "schema": 1,
  "pages": 100.4, "scenes": 147, "speaking_cast": 46,
  "action_paragraph_lines": {"1": 812, "2": 355, "3": 154, "4": 68, "5": 31},
  "dialogue_block_lines": {"1": 1104, "2": 620, "...": 0},
  "heading_time_tokens": 6, "night_share": 0.135,
  "language": "te", "profile": "indian-regional", "produced": true
}
```

Design constraints that make this acceptable to a contributor:

- **No text of any kind.** Not a title, not a character name, not a location. A
  histogram of paragraph lengths cannot be inverted into prose.
- **Small enough to read.** A couple of kilobytes. The contributor opens the
  file and sees every byte they are sending. This is what makes it a different
  ask from "send me your screenplay".
- **Local by default, explicit to send.** The command writes a file. Mailing it
  is a separate human decision.
- **Schema versioned**, because a threshold study that pools records from
  different tool versions has to know which computation produced each one.

## Why this is a contribution and not just plumbing

The general problem is common and the usual responses are poor. Domains where
the corpus is legally or ethically unshareable (clinical notes, legal filings,
student writing, internal code, screenplays) mostly either publish an
unreproducible result or do not publish. Federated learning solves a different
problem, model training, at much higher machinery cost.

The claim here is narrower and cheaper: **for descriptive distributional claims,
a versioned local statistic emitted by the same open-source code that computed
the published result is sufficient for reproduction.** A third party runs the
same command on their own inaccessible corpus and reports whether the
distribution matches. The tool is the protocol.

What makes it work in this instance is that the analysis code is open, so
"trust me about the statistic" reduces to "read the function that computed it".

## The experiment

1. Ship `--contribute` with a versioned schema.
2. Collect from a handful of writers. Twenty records covers the threshold study.
3. Publish the pooled distributions, the schema, and the computing code.
4. Have someone reproduce a distribution on a corpus nobody else can see, and
   report the agreement.

Step 4 is the paper. Steps 1 to 3 are a feature.

## Risks and objections

**"Aggregate statistics can leak."** They can, and the honest version of that
claim needs bounding. Here the released quantity is a histogram over thousands
of paragraphs per document, which is far from an identifying record, but a
paper making a privacy claim needs to say what it is claiming rather than
assert safety. The weaker and defensible claim is a copyright claim: no
expression is transmitted.

**"Nobody will contribute."** The most likely failure, and worth stating
plainly. A standalone request for statistics gives the contributor nothing. It
works only as a one-line opt-in at the bottom of a report they already found
useful, which makes this dependent on the tool being good first.

**"Twenty is not a corpus."** For a distribution over 18,000 paragraphs per
document, twenty documents is more mass than it sounds. For a claim about
variation between scripts it is thin, and the paper should report per-document
distributions rather than only the pooled one, so the variance is visible.

## Blocked on

The `--contribute` command, which is small. Then contributors, which is not a
technical problem.

## Venue shape

Methods or reproducibility track. Also the honest answer in the data-availability
statement of [01](01-thresholds-vs-practice.md), which is reason enough to build
it.
