# Product levels and business model

## The decision: open core, not freemium

The engine and the entire rulebook are MIT and stay that way. Paid tiers sell
**hosting, collaboration, and production integration** — never rules.

### Why not closed freemium

A tool whose entire pitch is *"unlike coverage tools, our findings are
verifiable"* cannot then ask you to take its rulebook on faith. The credibility
argument and the open rulebook are the same argument. Hiding the rules would
undercut the only thing that differentiates this from a GPT wrapper.

Three more reasons:

1. **The rulebook is the moat, and openness grows it.** Rules are a corpus that
   compounds. Contributions — especially regional profiles from writers who
   actually work in those industries — are worth more than the revenue lost by
   publishing them.
2. **Distribution.** Screenwriters don't buy unproven tools. They will `pip
   install` a free one, and a free CLI in CI is how this reaches the developer-
   adjacent writers who become the first paying users of level 2.
3. **It's a public portfolio artifact.** A closed repo can't be walked through
   in an interview.

### What open core gives up

Someone can self-host level 2. In practice almost nobody does — the people
willing to run a FastAPI service and hold their own API key are exactly the
people happy on level 1 anyway. That's an acceptable trade.

### The relicense trap, avoided

Open core only works if the boundary is drawn once, at the start, and never
moved. The commitment: **anything that decides whether a line of a screenplay is
a defect is MIT, forever.** Paid features are always *around* the engine — a UI,
a database, a team, an export — never *inside* it. No rule is ever moved behind
a paywall, because doing that once destroys the trust that makes the open
rulebook worth anything.

---

## Level 1 — CLI + rulebook

**Free. MIT. Forever.**

| | |
|---|---|
| **Who** | Writers comfortable in a terminal; developers; anyone with a script in git |
| **What** | 101 rules, 4 profiles, `lint` / `diff` / `rules`, JSON output, CI-friendly exit codes, the full tier-3 judge (bring your own `ANTHROPIC_API_KEY`) |
| **Cost to run** | Tiers 1–2: zero, no network. Tier 3: ~$0.01–0.05/script, paid directly to Anthropic |
| **Job it does** | "Tell me what's mechanically wrong with this draft before I send it" |
| **Success looks like** | Installs, stars, and — the one that matters — contributed rules and profiles |

**Deliberately not paywalled:** every rule, every profile, the diff engine, and
the LLM tier. If it decides what counts as a defect, it's free.

---

## Level 2 — Hosted

**Paid. For working writers who don't want a terminal.**

| | |
|---|---|
| **Who** | Working and aspiring screenwriters; anyone who found level 1 and doesn't own a Python install |
| **What** | Everything in level 1, plus: upload a script and see it annotated inline; accept or dismiss each finding; draft timeline showing the error count falling over time; **PDF and FDX import**; hosted LLM tier with no API key to manage; shareable read-only report links |
| **Pricing hypothesis** | Free tier: 3 scripts/month, tiers 1–2 only. Paid: **$12–15/month**, unlimited scripts, LLM tier included, full draft history |
| **Job it does** | "Show me my script with the problems marked, and let me watch them go away" |
| **Why it's worth paying for** | Not the rules — those are free. You're paying for PDF ingestion, the annotated view, draft history, and never handling an API key |

**Why this price:** it has to sit clearly below per-script AI coverage ($10–29)
and far below a single Final Draft licence (~$250), while being an easy monthly
next to WriterDuet at $6–10. A writer who reruns Sluglint across four drafts of
one script is already ahead of a single $29 coverage report.

**The retention loop is the diff.** Coverage is a one-shot purchase — you buy a
report, you read it, you're done. Sluglint gets re-run on every draft, and the
falling error count is the reason to come back. That's the difference between a
transaction and a subscription.

**The feedback loop is the product's real asset.** Accept/dismiss on every
finding produces exactly the labelled data the eval harness needs. A rule with a
70% dismissal rate is a rule with a threshold problem, and now that's a number
instead of a hunch.

---

## Level 3 — Production

**Paid, per seat. For writers' rooms, production companies, and studios.**

| | |
|---|---|
| **Who** | Showrunners and writers' rooms; script coordinators; line producers; production companies with a house style |
| **What** | Everything in level 2, plus: **shared team rulebooks** (your house style, versioned, enforced across every script); breakdown exports (cast, locations, story days); production reports (speaking-cast size, distinct locations, night-scene share, scene-length outliers); API and webhooks; SSO; audit trail |
| **Pricing hypothesis** | **$99–199/month** per production or small team |
| **Job it does** | "Every script that reaches us should already be consistent, and I want the budget signals before prep, not during it" |

**Why this is where the money is.** Level 3 sells against a cost, not a
preference. Name drift discovered in prep is a day of a script coordinator's
life. A speaking-cast count that grew 20% during rewrites is a line-item nobody
noticed. The tier-2 production metrics — `cast_size`, `location_load`,
`night_ratio`, `scene_length` — exist for this tier specifically: they don't
say the script is bad, they say the script has a number, and the number is
knowable now instead of in prep.

**Shared rulebooks are the lock-in.** Once a production's house style lives in a
Sluglint rulebook — "we always mark song sequences as blocks," "we never allow
camera direction in a writer's draft" — that rulebook is theirs and leaving
means rebuilding it.

---

## Sequencing

The order matters more than the tiers.

1. **Now → next:** eval harness with per-rule precision, then **PDF ingestion**.
   PDF is the single highest-leverage item on the roadmap, because PDF is the
   format scripts actually circulate in. Without it, level 2 addresses a
   fraction of the real market.
2. **Then:** level 2 as a thin FastAPI wrapper over `run_lint` plus an annotated
   script view. The accept/dismiss loop from day one — it's the labelled data.
3. **Only then:** level 3, and only with a real production as a design partner.
   Building breakdown exports without one is guessing.

## What would make me abandon this

Stated up front so it's a decision and not a slow drift:

- **The eval harness shows the rules can't clear 0.9 precision** on real
  scripts, not fixtures. A linter that cries wolf is worse than no linter, and
  no amount of product wrapping fixes it.
- **Nobody re-runs it.** If level 2 usage is one script per user and no second
  draft, there is no subscription — it's a one-shot tool and should be priced
  and positioned like one.
- **A coverage tool ships a credible deterministic pass** and gives it away.
  Then the wedge is gone and the honest move is to focus entirely on level 3,
  where the competitor isn't a coverage tool.
