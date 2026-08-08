# Product levels and business model

## The licence decision

Sluglint is under [PolyForm Noncommercial 1.0.0](../LICENSE). The source is
public and readable. Commercial use requires a paid licence.

**Why not MIT.** MIT was the wrong tool for the goal. It explicitly permits free
commercial use and requires only that the notice stay in source copies. Under
MIT a studio could embed Sluglint in a product it sells and owe nothing. That is
the opposite of the intent.

**Why not closed source.** The whole claim of this project is that its findings
are checkable. Asking anyone to trust a hidden rulebook would undercut the only
thing separating it from a chatbot with a system prompt. The rules stay visible.

**Why not AGPL.** AGPL keeps OSI open-source status, which has real value. But it
only triggers on distribution or offering a network service. A studio running the
CLI internally on its own slate would owe nothing, and internal studio use is
exactly the case worth charging for.

**The cost, stated plainly.** PolyForm Noncommercial is not OSI open source.
GitHub labels it source-available. Some developers will not contribute to or
depend on a non-OSI project, and that is a real loss of reach traded for the
ability to charge the people who should pay.

**The boundary, fixed now.** Every rule stays visible and every rule stays free
for noncommercial use, permanently. Paid tiers sell hosting, collaboration, and
production integration. No rule ever moves behind a paywall, because doing that
once destroys the trust that makes an open rulebook worth anything.

**Prior MIT commits.** The first four commits were published under MIT. Anyone
who cloned in that window keeps MIT rights to that snapshot. Everything from the
licence change onward is PolyForm.

---

## Level 1: CLI and rulebook

**Free for writers. Always.**

| | |
|---|---|
| **Who** | Writers comfortable in a terminal, developers, anyone with a script in git |
| **What** | 148 rules, 4 profiles, `lint` / `diff` / `rules`, JSON output, CI exit codes, the benchmark harness, the full tier-3 judge with your own API key |
| **Cost** | Tiers 1 and 2 cost nothing and never touch the network. Tier 3 runs about $0.01 to $0.05 a script, paid to Anthropic |
| **Job** | "Tell me what is mechanically wrong with this draft before I send it" |
| **Success** | Installs, and above all contributed rules and profiles |

Never paywalled: every rule, every profile, the diff engine, the benchmark. If
it decides what counts as a defect, it is free for a writer.

**What that promise covers, and what it does not.** The floor above is
permanent: anything that decides whether something is a defect stays free and
stays readable, forever. Everything else is a product decision. Visual output,
exports, conversion, hosting, collaboration and batch runs may move between
tiers as we learn what people actually pay for, in either direction.

That is deliberate rather than a hedge. The tiering here was drawn before there
were any customers, and a guess made that early should not bind the project
forever simply because it was written down first. Three things keep the freedom
honest: a release already published keeps the terms it shipped with and its tag
stays up, any move is stated in the release notes for the version it happens
in, and the reason goes in the changelog. A feature that quietly stops working
is a bug report from somebody who trusted us.

---

## Level 2: Hosted

**Free while in beta.**

| | |
|---|---|
| **Who** | Working and aspiring screenwriters who do not own a Python install |
| **What** | Everything in level 1, plus upload a script and see it annotated inline, accept or dismiss each finding, a draft timeline showing the error count falling, PDF and FDX import, hosted LLM tier with no API key to manage, shareable read-only report links |
| **Price today** | Free. No card, no trial clock |
| **Job** | "Show me my script with the problems marked, and let me watch them go away" |

Level 2 is free during the beta because the accept-and-dismiss data is worth
more right now than the subscription revenue would be. Every dismissal is a
labelled example saying a rule fired when it should not have, which is exactly
what the precision gap in the benchmark needs. Paying users would be buying an
unfinished product and generating the same data.

Early users keep beta access through the beta and get told well before anything
changes.

**Pricing hypothesis for later**, recorded so the decision is deliberate: around
$12 to $15 a month. It has to sit below per-script AI coverage ($10 to $29) and
far below a Final Draft licence (about $250), while reading as an easy monthly
next to WriterDuet at $6 to $10. A writer running four drafts of one script is
already ahead of a single $29 coverage report.

**The retention loop is the diff.** Coverage is bought once and read once.
Sluglint gets re-run on every draft, and the falling error count is the reason
to come back.

---

## Level 3: Production

**Paid, per seat.**

| | |
|---|---|
| **Who** | Writers' rooms, script coordinators, line producers, production companies with a house style |
| **What** | Everything in level 2, plus shared team rulebooks (your house style, versioned, enforced across every script), breakdown exports, production reports (speaking-cast size, distinct locations, night-scene share, scene-length outliers), API and webhooks, SSO, audit trail |
| **Price hypothesis** | $99 to $199 a month per production or small team |
| **Job** | "Every script that reaches us should already be consistent, and I want the budget signals before prep" |

This is where the money is, because level 3 sells against a cost rather than a
preference. Name drift found in prep is a day of a script coordinator's life. A
speaking-cast count that grew 20% during rewrites is a line item nobody noticed.
The tier-2 production metrics exist for this tier: they never say the script is
bad, they say the script has a number and the number is knowable now.

Shared rulebooks are the lock-in. Once a production's house style lives in a
Sluglint rulebook, that rulebook is theirs and leaving means rebuilding it.

---

## What could an integration deal be worth?

You asked directly, so here is a direct answer with the uncertainty attached.
These are industry heuristics applied to a project with no users yet. Treat them
as ranges to negotiate against, not forecasts.

**OEM or embedded licence.** A screenwriting vendor (WriterDuet, Celtx, Arc
Studio, Fade In) putting Sluglint inside their editor. Small vendors in this
market are small businesses, and a realistic first deal is **$15k to $60k a
year**, or a per-seat royalty of roughly $0.50 to $2 per subscriber per year. A
major (Final Draft, or Cast and Crew who own a chunk of the production stack)
could justify **$75k to $250k a year**, but they move slowly, will demand an
indemnity, and will ask whether they should just build it.

**What actually moves those numbers:** a measured precision figure on real
scripts, at least one named production using it, and PDF ingestion. Without PDF
ingestion the integration story is weak, because their users' scripts are PDFs.

**Direct production or studio licences.** $5k to $25k a year per production
company for level 3, higher for a studio with a slate. Realistic to sell one or
two on a relationship before there is any product marketing.

**Selling the whole thing.** Blunt version: **pre-revenue with no users, it is
worth roughly nothing** as an acquisition. Nobody buys a linter with zero
adoption. What it is worth today is as a portfolio artifact and a door-opener.

With traction, the usual shapes:

| Stage | Rough valuation |
|---|---|
| No users, no revenue | Effectively $0. An acquihire values you, not it |
| A few hundred users, no revenue | $0 to $50k, mostly a talent conversation |
| $50k ARR | $150k to $400k (3x to 8x, vertical SaaS range) |
| $250k ARR with production logos | $750k to $2M |
| $1M ARR | $3M to $8M, and a strategic buyer might stretch past that |

Vertical SaaS in a small market trades at the low end of those multiples,
because the total addressable market is genuinely small. There are tens of
thousands of working screenwriters, not millions. A strategic buyer pays for the
rulebook and the position rather than the code, which is the argument for
growing the rulebook and getting real production users above everything else.

**The honest read.** The most likely good outcome is not an acquisition. It is a
handful of production and vendor licences, a few thousand noncommercial users
who make the rulebook better, and a portfolio piece that is hard to argue with
in an interview. Optimise for that and the bigger outcome stays possible.

---

## Sequencing

1. **PDF ingestion.** Highest leverage on the roadmap. PDF is the format scripts
   circulate in, and without it both level 2 and any integration deal address a
   fraction of the real market.
2. **Precision measurement.** Recall is measured. Precision is not. Either a
   Creative Commons corpus large enough to matter, or a human verdict on every
   finding across a private corpus.
3. **Level 2 as a thin FastAPI wrapper** over `run_lint`, with accept and
   dismiss from day one.
4. **Level 3, only with a real production as a design partner.** Building
   breakdown exports without one is guessing.

## What would make me stop

Written down now so it stays a decision rather than a slow drift.

- **Precision cannot clear 0.9 on real scripts.** A linter that cries wolf is
  worse than no linter, and no amount of product wrapping fixes it.
- **Nobody re-runs it.** If level 2 usage is one script per user and no second
  draft, there is no subscription. It is a one-shot tool and should be priced
  like one.
- **A coverage tool ships a credible deterministic pass and gives it away.**
  Then the wedge is gone and the honest move is to focus entirely on level 3,
  where the competitor is a script coordinator's time.
