# Competitive landscape

*Researched July 2026. Prices are list prices as advertised and move often, so
treat them as order-of-magnitude.*

## The short answer

**Nothing does this job today.** The market splits into four camps. Each one
either checks the script *while you type it*, judges it *subjectively*, or works
on it *after it is locked for production*. None of them tells a writer, about a
draft that already exists, "here are the objective defects, cited to a rule."

That gap is Sluglint's whole reason to exist. It is also a warning. A gap that
stays open in a mature market usually means the demand is smaller than it looks.
See [Honest risks](#honest-risks).

---

## Camp 1, Screenwriting software

Final Draft (~$250 one-time), Fade In (~$80 one-time), WriterDuet (~$6-10/mo),
Celtx (~$15/user/mo), Trelby (free), ScreenWeaver, Arc Studio, Highland.

**What they do:** enforce format *as you type*. Correct margins, correct
elements, correct pagination. Some add outlining, revision colours, and
collaboration.

**What they can't do:** tell you whether the 110-page draft you already have is
internally consistent. Final Draft will happily let you spell a character two
ways for 40 pages, flip a location from DAY to NIGHT and back, and open a
FLASHBACK you never close. It formats; it does not audit.

**Relationship to Sluglint:** these are complements. Sluglint runs on the output
of any of them, in any tool, at any point in the draft.

---

## Camp 2, AI coverage

Greenlight Coverage, Prescene AI, ScriptReader.ai, ScreenplayIQ (WriterDuet),
Ovassa, and a growing tail of GPT wrappers.

| Service | Price | Delivers |
|---|---|---|
| ScriptReader.ai | ~$10/script | Scene-by-scene grades and critiques |
| Prescene AI | ~$29/script, or subscription | Story intelligence, character breakdowns, production feedback |
| Greenlight Coverage | ~$50/mo; 3-script pack ~$209 | Full coverage report, plot assessment, category scores, follow-up Q&A |
| Human coverage (for reference) | $150 to $300 and up | A person's actual opinion |

**What they do:** produce a coverage report, plot assessment, character notes,
scores, marketability. Fast and much cheaper than a human reader.

**What they cannot do:** be checked. "Your second act sags" is not falsifiable.
Neither is a 7.2/10. These tools sell judgment, and judgment cannot be
regression-tested, precision-measured, or cited to a rule. When two of them
disagree there is no way to say which one was right.

**Relationship to Sluglint:** adjacent, and honestly a good funnel. Sluglint is
the pass you run before spending $29 to $209, so the reader spends attention on
your story instead of your typos. Several of these tools would be better
products if they ran something like Sluglint first and stopped reporting "the
formatting is inconsistent" as a finding.

**Where they compete:** if a coverage tool bolts on a deterministic
consistency-check module, it eats a chunk of this. That is a real risk. The
defence is the rulebook described below.

---

## Camp 3, Production and continuity software

ScriptE, Filmustage, StudioBinder, Movie Magic, Yamdu.

**What they do:** import a *locked* script and generate breakdowns, cast lists,
prop lists, wardrobe, story-day continuity, schedules, script supervisor reports.
ScriptE will even auto-fill a story-day breakdown by looking at which script days
have already been used.

**What they cannot do:** help the writer. These tools arrive after the script is
finished and greenlit. They are built for the script supervisor and the line
producer rather than the person on draft four. And they inherit every defect: a
script with two spellings of one character produces two characters on the
breakdown, and nobody notices until prep.

**Relationship to Sluglint:** this is where product level 3 eventually competes,
and where the tier-2 production metrics (cast size, location load, night-scene
share) are pointed. Fixing name drift before the breakdown is worth real money;
fixing it after is a day of someone's life.

---

## Camp 4, Open-source Fountain tooling

`vilcans/screenplain`, `nyousefi/Fountain`, `wildwinter/screenplay-tools`,
various parsers in JS/Python/C#/C++.

**What they do:** parse and render Fountain, convert to PDF or FDX.

**What they cannot do:** lint. Every one of these is a parser or a converter.
None ships a rule engine, a severity model, or a single check. A search across
the Fountain ecosystem turns up no linter.

**Relationship to Sluglint:** these are potential dependencies. A mature
Fountain parser is a reasonable thing to adopt later in place of the hand-rolled
one.

---

## Why the position is defensible (and where it isn't)

**The moat is the rulebook.** Anyone competent can write a Fountain parser in a
weekend. What takes real time is 101 rules that each carry an original
principle, a source attribution, a severity, a tuned threshold, a positive
fixture, and a clean-script regression. That is a corpus, and it compounds:
every rule added makes the next one cheaper to justify and harder to match.

**Measurability is the wedge.** Sluglint is the only tool in this market that
can publish a per-rule accuracy number. No coverage tool can, because there is
no ground truth for "the second act sags." That is why the fault-injection
harness in `benchmark/` shipped before any of the product work, and why recall
is published at 97% while precision is openly marked untested.

**Profiles are a durable differentiator.** The `indian-regional` profile covers
song sequences as scheduled production units, INTERVAL placement, and
mixed-script cue consistency. No US-built coverage tool has looked at that
market, and it produces more features per year than Hollywood.

### Honest risks

1. **The gap may be open because the market is small.** Screenwriters are
   famously reluctant to pay for tools, and "objectively correct" is a harder
   sell than "will this sell." Level 1 being free is partly a distribution
   answer to this.
2. **A coverage tool could bolt this on.** Greenlight or Prescene adding a
   deterministic consistency pass is a weekend for the easy 20 rules. The
   defence is the long tail: the profile system, the production metrics, and
   measured accuracy. The first 20 rules are not defensible.
3. **Writers do not use terminals.** Level 1's real audience is small. Level 2
   is the product for everyone who is not a developer.
4. **PDF is the actual format of record.** Most scripts circulate as PDF rather
   than Fountain. Until PDF ingestion ships, addressable usage is a fraction of
   the real market. This is the single highest-leverage item on the roadmap.

---

5. **Script licensing blocks the proof.** Precision cannot be measured on
   produced screenplays without a corpus, and nearly every famous script is
   copyrighted. See [public-domain-scripts.md](public-domain-scripts.md).

## Sources

- [10 Best Screenplay Coverage Services in 2026: AI, Human & Hybrid](https://glcoverage.com/blog/best-screenplay-coverage-services/)
- [Greenlight Coverage, Pricing](https://glcoverage.com/pricing/)
- [Prescene, Pricing](https://www.prescene.ai/pricing)
- [Cheap AI Script Coverage in 2026: The Sub-$25 Tier Compared](https://www.storynotes.app/blog/cheap-ai-script-coverage-comparison)
- [9 Best Tools for AI Script Coverage in 2026, Scriptation](https://scriptation.com/blog/best-ai-script-coverage-feedback-analysis/)
- [9 Best Free Screenwriting Software in 2026, StudioBinder](https://www.studiobinder.com/blog/screenwriting-software/)
- [Best Screenwriting Software in 2026 (Including Free Options), InVideo](https://invideo.io/blog/best-screenwriting-software/)
- [Script Supervising Goes Digital, Filmmaker Magazine](https://filmmakermagazine.com/58188-script-supervising-goes-digital/)
- [Script supervisors: Mastering the art of script breakdowns, Filmustage](https://filmustage.com/blog/script-supervisors-mastering-the-art-of-script-breakdowns-in-filmmaking/)
- [screenplain, Fountain to PDF](https://github.com/vilcans/screenplain)
- [wildwinter/screenplay-tools](https://github.com/wildwinter/screenplay-tools)
