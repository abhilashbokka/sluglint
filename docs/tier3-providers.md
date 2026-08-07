# Running tier 3, and on whose hardware

Tier 3 is 38 rubric judges. Until now they needed an Anthropic key and had
never run on a real screenplay, which is why every corpus figure in this
project says "0 of 38 tier-3 rules fired". This document is how to change that.

Two providers are supported. Anthropic through its SDK, and **anything that
speaks the OpenAI chat-completions shape** through `urllib`. The second path
takes no new dependency, because hard rule 7 keeps core to `pyyaml` and an HTTP
POST is not worth an SDK.

```bash
# Anthropic, the default when ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY=...
python -m sluglint.cli lint script.pdf --llm

# Google Gemini, which has a free tier and a 1M context window
export SLUGLINT_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export SLUGLINT_LLM_API_KEY_FILE=~/.config/sluglint/gemini.key
export SLUGLINT_MODEL=gemini-3.6-flash
python -m sluglint.cli lint script.pdf --llm

# Groq, fastest of the free tiers, small context so chunk smaller
export SLUGLINT_LLM_BASE_URL=https://api.groq.com/openai/v1
export SLUGLINT_LLM_API_KEY_FILE=~/.config/sluglint/groq.key
export SLUGLINT_MODEL=llama-3.3-70b-versatile
export SLUGLINT_LLM_RPM=30
python -m sluglint.cli lint script.pdf --llm
```

Gemini's compatibility layer **silently ignores parameters it does not
support** rather than erroring, so confirm on a short script that the output is
not being truncated before starting a long run.

An explicit `SLUGLINT_LLM_BASE_URL` always wins. No key at all means tier 3
reports itself skipped and tiers 1 and 2 still run, which is behaviour the
project has always had and is not allowed to lose.

| Variable | Default | What it does |
|---|---|---|
| `SLUGLINT_LLM_BASE_URL` | unset | OpenAI-compatible endpoint. Unset means use Anthropic. |
| `SLUGLINT_LLM_API_KEY` | falls back to `OPENAI_API_KEY` | Bearer token for that endpoint. |
| `SLUGLINT_LLM_API_KEY_FILE` | unset | Path to a file whose first line is the key. Prefer this. |
| `SLUGLINT_MODEL` | `claude-sonnet-5` | Model id. |
| `SLUGLINT_LLM_RPM` | 0 (no pacing) | Requests per minute. Set it to the free tier's limit. |
| `SLUGLINT_SCENES_PER_CALL` | 6 | Lower it for a provider with a small context cap. |
| `SLUGLINT_MAX_TOKENS` | 8000 | Output cap per call. |
| `SLUGLINT_LLM_TIMEOUT` | 180 | Seconds per request. |

## Where to put the key

Prefer a file. `export` writes the key into shell history and exposes it in
`ps` output to every process on the machine, and a key pasted into a terminal
has a way of ending up somewhere it was not meant to be.

```bash
mkdir -p ~/.config/sluglint && chmod 700 ~/.config/sluglint
printf '%s\n' 'YOUR_KEY_HERE' > ~/.config/sluglint/gemini.key
chmod 600 ~/.config/sluglint/gemini.key

export SLUGLINT_LLM_API_KEY_FILE=~/.config/sluglint/gemini.key
```

Only the first line is read, so a comment underneath is harmless. A path that
does not exist reports a missing key rather than crashing.

Keep the file **outside the repository**. `.env` is gitignored, but a gitignore
is one `git add -f` away from a public commit and this repository is public
(hard rule 9). A path under `~/.config` cannot be committed by accident.

## Read this before pointing it at a corpus

**Some free tiers train on the prompts you send them.** Worth knowing, but
worth keeping in proportion: the corpora this project measures are already
public. ScriptBase is a public GitHub repository and the regional PDFs are
published pages, so they are in every crawl already and sending them to a model
is not redistribution in any meaningful sense. The gitignores on
`benchmark/corpus/` and `benchmark/local/` are about what this repository
commits, which is a different question. See
[public-domain-scripts.md](public-domain-scripts.md).

Where it would matter is a draft that is not public: a script a writer sends
to the tool, which is the whole product. For that case the column below is the
one to read, and it is why `SLUGLINT_LLM_BASE_URL` has no default.

| Provider | Trains on free-tier prompts? | Can it see a writer's unpublished draft? |
|---|---|---|
| [Groq](https://console.groq.com/docs/rate-limits) | No | Yes |
| [Cerebras](https://inference-docs.cerebras.ai/support/pricing) | No | Yes |
| [Anthropic](https://www.anthropic.com/legal/commercial-terms) | No | Yes |
| [Google AI Studio](https://ai.google.dev/gemini-api/docs/pricing) | **Yes**, outside the UK, Switzerland, EEA and EU | Paid tier only |
| [Mistral](https://docs.mistral.ai/deployment/laplateforme/tier/) | **Yes**, opting in is required to get the tier | No |
| [OpenRouter](https://openrouter.ai/docs/api-reference/limits) | Per upstream model | Check the model |
| [NVIDIA NIM](https://build.nvidia.com/) | Check current terms | Check |
| [opencode](https://opencode.ai/data/deepseek/deepseek-v4-flash) | **Not stated on the model page**, which links a privacy policy without detailing training use | Unverified |

For measuring this project's corpora, every row is fine. The column matters
the day the tool takes a script from someone who has not published it, and it
is cheaper to pick a provider now than to migrate later.

## Paid, and cheap enough to change the decision

Free tiers cost rate-limit juggling. Two paid options remove it for less than
the price of a coffee, priced against this rulebook's measured 99,000 input
tokens and roughly 18,000 output tokens per feature:

| Model | Input / output per 1M | Per feature | Five features | All 1,082 ScriptBase films |
|---|---|---:|---:|---:|
| [DeepSeek V4 Flash](https://opencode.ai/data/deepseek/deepseek-v4-flash) | $0.14 / $0.28 | **$0.02** | $0.10 | about $20 |
| Claude Sonnet 5 | $3.00 / $15.00 | $0.56 | $2.80 | about $600 |

DeepSeek V4 Flash carries a **1M context window**, which removes the chunking
constraint entirely: `SLUGLINT_SCENES_PER_CALL` could hold a whole feature in
one call, and the rubric would then be paid for once per script rather than 22
times. That is the single biggest cost lever available here.

Its data policy is the open question. The model page states pricing and context
but says nothing about training on prompts, so treat it as unverified until the
privacy policy is read.

## What a run costs in requests

Measured on this rulebook rather than estimated:

| Quantity | Value |
|---|---:|
| Tier-3 rules | 38 |
| Rubric, all 38 rules | 14,921 chars, about 3,700 tokens |
| Scene text per call at 6 scenes | about 600 tokens |
| **Input tokens per call** | **about 4,500** |
| Calls for a 130-scene feature | 22 |
| **Input tokens for one feature** | **about 99,000** |

The rubric is the dominant cost and it is identical in every call, so a
provider with prompt caching is worth much more here than a fast one.

Against the free tiers, for five features (110 calls, roughly 500k input
tokens):

| Provider | Limits | Five features |
|---|---|---|
| Groq | 30 RPM, 1,000 RPD, 12k TPM | Fits, paced by tokens: about 12 minutes per feature |
| Cerebras | 30 RPM, 14,400 RPD, 1M TPD | Fits on requests, **but see the context cap below** |
| Google AI Studio | **20 requests per day, per model**, measured | One script per model per day |
| OpenRouter unfunded | 50 RPD | Two features per day |

**Cerebras caps free-tier context at 8,192 tokens.** A call is 4,500 tokens of
input before the model writes anything, so `SLUGLINT_MAX_TOKENS` has to come
down to about 3,000 and it is still tight. Lower `SLUGLINT_SCENES_PER_CALL` to
3 and it fits with room, at the cost of doubling the call count and paying for
the rubric twice as often.

**Gemini's free tier is 20 requests per day per model.** Measured rather than
looked up: Google stopped publishing free-tier limits and now assigns them per
project, so the only way to learn one is the quota error, which names it
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 20`). A
158-scene feature needs 27 calls, so one screenplay does not fit in one model's
daily budget. The limit is per MODEL and 59 are reachable, so rotating models is
the free route: `gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-2.5-flash`
and the rest each carry their own budget. Check yours at
<https://aistudio.google.com/rate-limit>.

A per-day quota now aborts the run instead of being retried. The first run of
this spent twenty minutes grinding through four more scripts producing nothing
but 429s, because the retry logic could not tell a per-minute limit from a
per-day one. Google reports the difference in the quota id, inside a JSON array
wrapping the error, and carries neither a `retry-after` header nor a bare
object; both shapes are now read.

Numbers on free tiers move. Every one above should be checked in the
provider's own console before a long run; the code does not depend on any of
them.

## Measured, on real screenplays

First live run, 2026-08-07, `gemini-3.6-flash` against Parasite. This is the
first time any of the 38 tier-3 rules has seen a produced screenplay.

| | |
|---|---:|
| Scenes | 158 |
| Calls made | 27, of which 8 died on quota |
| Findings proposed | 40 |
| **Kept after every filter** | **19 (48%)** |
| Dropped: unknown rule | 0 |
| Dropped: out of window | 1 |
| Dropped: low confidence | 0 |
| **Dropped: evidence not in the text** | **20** |

**One filter does all the work.** The model stayed inside the rubric and inside
the scene window without exception, and then fabricated its quote in half the
findings it proposed. Nothing was rejected for citing a rule that does not
exist or a scene it was not shown. On a 7-scene fixture the same pattern held:
3 of 3 drops were unquotable.

That is worth stating precisely because it inverts the intuition the filters
were built on. The cheap syntactic checks (known rule id, in-window scene
index) cost nothing and catch nothing. The verbatim-evidence check is the whole
defence, and removing it would roughly double the finding count with fabricated
quotes.

The 19 that survived are sound. `S001` on "Yon-Kyo is freaked out of her mind"
and "She's unaware that --", `L006` on "It's rather poignant.", `L005` on
"Ki-Woo begins to step out". Each quotes the page and points at a line, which
is the scope boundary in the root `CLAUDE.md` rule 10.

## Scene window trades cost against recall, and not linearly

`SLUGLINT_SCENES_PER_CALL` is a hidden hyperparameter and it matters more than
it looks. Same script, same rubric, two windows:

| Scenes per call | Calls | Proposed | Kept | Rules that fired |
|---:|---:|---:|---:|---:|
| 6 | 27 | 40 | **19** | 5 |
| 40 | **4** | 7 | 5 | 3 |

Widening the window is 6.8 times cheaper in requests and finds a quarter as
much. Per call the wide window looks better (1.25 kept against 0.70); per
script it is far worse, because a judge asked to scan forty scenes against
thirty-eight rules does not scan them as closely as one asked to scan six.

The practical consequence is that the free tier cannot buy its way out of a
quota by chunking wider, and the honest default stays at 6.

## The measurement this unlocks

`tier3_llm.FilterStats` counts what each hallucination filter caught. Every
judged item is attributed to the first filter that rejected it, so the columns
sum to the number proposed:

```
Tier 3 (api.groq.com/llama-3.3-70b-versatile): 22 calls, 61 findings proposed,
34 kept, 27 dropped (44%) [unknown rule 2, out of window 5,
low confidence 11, not quotable 9].
```

That line is the result the research tracker has been waiting for. Until it
existed, the claim that tier 3 has hallucination filters had no number behind
it, and "we filter hallucinations" is not a finding. The drop rate per filter
per model is.

It also makes a comparison possible that a single provider could not: **the
same rubrics, the same script, three models, three drop rates.** A weaker model
whose filters catch more is evidence the filters do their job rather than
evidence the model is bad, and that is a stronger claim than anything a single
Claude run could support. See
[research/02-fixture-corpus-gap.md](research/02-fixture-corpus-gap.md) for
where it lands.

## Sources

The provider list came from a Reddit roundup of permanent free tiers, checked
against first-party documentation where possible. Rate limits are the numbers
most likely to be stale.

- Free-tier roundup: <https://www.reddit.com/r/better_claw/comments/1vef1nz/free_llm_api_list_permanent_free_tiers_only/>
- Groq rate limits: <https://console.groq.com/docs/rate-limits>
- Cerebras pricing and limits: <https://inference-docs.cerebras.ai/support/pricing>
- Google AI Studio pricing and data use: <https://ai.google.dev/gemini-api/docs/pricing>
- Mistral tiers: <https://docs.mistral.ai/deployment/laplateforme/tier/>
- OpenRouter limits: <https://openrouter.ai/docs/api-reference/limits>
- NVIDIA NIM catalogue: <https://build.nvidia.com/>
- Gemini OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- DeepSeek V4 Flash on opencode: <https://opencode.ai/data/deepseek/deepseek-v4-flash>
- Comparison writeups, useful but secondhand:
  <https://openrouter.ai/blog/tutorials/free-llm-apis-compared/> and
  <https://tokenmix.ai/blog/free-llm-apis-2026-every-provider-free-tier-tested>
