"""Tier 3 LLM rubric judges for soft and craft rules.

Design decisions that matter for precision:
  * One scoped rubric per rule (id, principle, few-shot pairs). There is no
    single "critique this script" prompt anywhere in this file.
  * Scene-window chunking with a global context header (title, character
    list) so judgments stay grounded.
  * Strict JSON output contract enforced by the API (structured outputs), so
    the shape is guaranteed and the caller only has to police the *content*.
  * Every finding must carry verbatim evidence from the text, which the
    caller re-verifies before accepting (cheap hallucination filter).
  * Findings carry model confidence; the report layer can threshold.

Two settings here are deliberate, not defaults:

  * `thinking` is disabled. The current Sonnet runs adaptive thinking when the
    parameter is omitted, and `max_tokens` caps thinking *plus* output, so a
    judge returning a long findings array would truncate mid-JSON.
  * `effort: low`. The judge extracts findings against a fixed rubric, which
    is shallow work, and low effort keeps the per-script cost in cents.

**Two providers.** Anthropic through its SDK, and anything speaking the
OpenAI chat-completions shape through `urllib`. The second path exists so the
rubrics can be run on more than one model without the project taking a second
dependency: hard rule 7 keeps core to `pyyaml`, and an HTTP POST is not worth
an SDK. Groq, Cerebras, OpenRouter, NVIDIA NIM, and Google's compatibility
endpoint all answer the same request.

    export SLUGLINT_LLM_BASE_URL=https://api.groq.com/openai/v1
    export SLUGLINT_LLM_API_KEY=...
    export SLUGLINT_MODEL=llama-3.3-70b-versatile

**Read the provider's data policy before pointing this at a corpus.** Some free
tiers train on the prompts they are sent, and a screenplay this project is not
allowed to redistribute is a screenplay it is not allowed to hand to a trainer
either. That is a licence decision, not a rate-limit one, and it is the reason
`SLUGLINT_LLM_BASE_URL` has no default.

Without any key, tier 3 is skipped with a notice and tiers 1-2 still run.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from ..models import Finding, Script, Severity
from ..rulebook import Rule


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


DEFAULT_MODEL = os.environ.get("SLUGLINT_MODEL", "claude-sonnet-5")
# Six scenes is a comfortable window on a large-context model. A free tier
# capped at 8k tokens of context needs it lower, which is why it is tunable
# rather than a constant: the rubric alone is about 3.7k tokens.
SCENES_PER_CALL = _env_int("SLUGLINT_SCENES_PER_CALL", 6)
MAX_TOKENS = _env_int("SLUGLINT_MAX_TOKENS", 8000)
# Free tiers meter by the minute. Pacing the calls costs nothing when the
# limit is generous and is the difference between a run and a wall of 429s
# when it is not.
REQUESTS_PER_MINUTE = _env_int("SLUGLINT_LLM_RPM", 0)
HTTP_TIMEOUT = _env_int("SLUGLINT_LLM_TIMEOUT", 180)
MAX_RETRIES = 4


@dataclass
class FilterStats:
    """What each hallucination filter caught.

    The filters are the part of this tier worth defending, and until this
    existed there was no number behind them. Every judged item is counted
    once, against the first filter that rejected it, so the columns sum to
    `proposed`.
    """
    calls: int = 0
    failed_calls: int = 0
    proposed: int = 0
    dropped_unknown_rule: int = 0
    dropped_out_of_window: int = 0
    dropped_low_confidence: int = 0
    dropped_unquotable: int = 0       # the quote is nowhere in the text
    dropped_misattributed: int = 0    # the quote is real, the cited line is not it
    accepted: int = 0
    scenes_expected: int = 0
    scenes_answered: int = 0
    model: str = ""
    provider: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def dropped(self) -> int:
        return self.proposed - self.accepted

    @property
    def coverage(self) -> float:
        """Share of the scenes shown that the judge actually answered about."""
        if not self.scenes_expected:
            return 1.0
        return self.scenes_answered / self.scenes_expected

    def summary(self) -> str:
        if not self.proposed:
            return (f"Tier 3 ({self.provider}/{self.model}): {self.calls} calls, "
                    f"no findings proposed.")
        pct = 100.0 * self.dropped / self.proposed
        return (f"Tier 3 ({self.provider}/{self.model}): {self.calls} calls, "
                f"{self.proposed} findings proposed, {self.accepted} kept, "
                f"{self.dropped} dropped ({pct:.0f}%) "
                f"[unknown rule {self.dropped_unknown_rule}, "
                f"out of window {self.dropped_out_of_window}, "
                f"low confidence {self.dropped_low_confidence}, "
                f"not quotable {self.dropped_unquotable}, "
                f"misattributed {self.dropped_misattributed}]. "
                f"Scene coverage {self.coverage:.0%}.")

# The API validates responses against this, so a malformed judge reply is
# impossible by construction. The hallucination filters below then police what
# the shape cannot: whether the finding is actually grounded in the text.
_FINDING = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string"},
        # Both, deliberately. A line id alone makes a fabricated quote
        # inexpressible, which sounds like the fix and is not: a judge that
        # wants to report something then cites the nearest plausible real
        # line, and a measurable failure becomes an invisible one. Carrying
        # the quote as well means fabrication fails the lookup and
        # misattribution fails the comparison, and both stay countable.
        "line_id": {"type": "integer",
                    "description": "The [Lnnnn] id of the offending line."},
        "evidence": {"type": "string",
                     "description": "A short VERBATIM quote from that line."},
        "message": {"type": "string"},
        "suggestion": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["rule_id", "line_id", "evidence", "message", "suggestion",
                 "confidence"],
    "additionalProperties": False,
}

# The API validates responses against this, so a malformed judge reply is
# impossible by construction. The hallucination filters below then police what
# the shape cannot: whether the finding is actually grounded in the text.
#
# One entry per scene, including the scenes with nothing wrong. Asking for a
# flat findings array let a judge shown forty scenes answer about six of them:
# widening the window from 6 scenes to 40 was 6.8x cheaper and found a quarter
# as much. A row per scene makes skipping visible, and `scenes_expected`
# against `scenes_answered` measures it.
FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer"},
                    "findings": {"type": "array", "items": _FINDING},
                },
                "required": ["scene_index", "findings"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scenes"],
    "additionalProperties": False,
}

# The document pass has no scene rows: its rules are about the whole script,
# so a finding names the scene it points at and nothing is enumerated.
DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": _FINDING}},
    "required": ["findings"],
    "additionalProperties": False,
}

_RULES_OF_ENGAGEMENT = """You are a screenplay lint engine, not a critic. You apply \
ONLY the numbered rules provided, to the text provided. You never invent rules, never \
comment on story quality outside the rules, and never flag stylistic choices the \
rules permit (sentence fragments, CAPS on sounds/intros, invented proper nouns).

Precision beats recall: if you are not confident a rule is violated, do not flag it.

Every line you are shown carries an id in the form [Lnnnn].
- line_id MUST be the number from the marker on the offending line. Never invent one.
- evidence MUST be a short VERBATIM quote from THAT line. A finding whose quote does
  not appear on the line it cites will be discarded.
- confidence in [0,1]."""

SYSTEM_PROMPT = _RULES_OF_ENGAGEMENT + """

Return one entry per scene you were shown, in order, including scenes where you
found nothing. A scene with no violations gets an empty findings array. Do not
omit a scene."""

DOCUMENT_PROMPT = _RULES_OF_ENGAGEMENT + """

You are being shown the WHOLE script, because these rules ask whether it ever
returns to something it introduced. Answer only from what is in front of you,
and quote the line that introduced the thing you are reporting."""


def _rubric(rules: list[Rule], profile: str = "") -> str:
    parts = []
    for r in rules:
        block = f"[{r.id}] {r.name} (severity: {r.severity})\n  Principle: {r.principle}"
        if note := r.note_for(profile):
            block += f"\n  In this profile: {note}"
        for ex in r.examples[:2]:
            if isinstance(ex, dict):
                block += f"\n  Violates: {ex.get('bad', '')}\n  Acceptable: {ex.get('good', '')}"
        parts.append(block)
    return "\n\n".join(parts)


def _chunks(script: Script):
    for i in range(0, len(script.scenes), SCENES_PER_CALL):
        yield script.scenes[i:i + SCENES_PER_CALL]


def _parse_findings(text: str) -> tuple[list[dict], set[int]]:
    """-> (findings, scene indices the judge answered about).

    Structured outputs make the happy path a plain json.loads. The rest is a
    fallback for a model set via SLUGLINT_MODEL that does not honour the schema
    contract: the older flat `findings` array is still read, and so is a bare
    array, so the engine degrades rather than crashes.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = None
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end != -1:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                data = None
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)], set()
    if not isinstance(data, dict):
        return [], set()
    if isinstance(rows := data.get("scenes"), list):
        out, answered = [], set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if isinstance(idx := row.get("scene_index"), int):
                answered.add(idx)
            for item in row.get("findings") or []:
                if isinstance(item, dict):
                    # The scene row carries the index; a finding inherits it so
                    # the window check downstream has something to check.
                    item.setdefault("scene_index", row.get("scene_index"))
                    out.append(item)
        return out, answered
    return [x for x in (data.get("findings") or []) if isinstance(x, dict)], set()


def _numbered(scenes) -> tuple[str, dict[int, str]]:
    """Scene text with an id on every line, and the table to resolve them.

    The id is the source line number, so a finding resolves straight back to
    the place in the file the writer would open.
    """
    lines, table = [], {}
    for scene in scenes:
        lines.append(f"--- SCENE {scene.index} | {scene.heading} ---")
        for el in scene.elements:
            body = el.text.strip()
            if body:
                table[el.line_no] = body
                lines.append(f"[L{el.line_no:04d}] {body}")
    return "\n".join(lines), table


# ------------------------------------------------------------------- filters

def _norm(text: str) -> str:
    """Whitespace-folded lowercase, so a quote that crossed a line break matches."""
    return " ".join(text.lower().split())


def _cited_context(table: dict[int, str], line_id: int, span: int = 4) -> str:
    """The cited line and the few after it, joined as they would read.

    A PDF-ingested script holds one PRINTED line per element, median 35
    characters, so a sentence runs across three of them. A judge quotes the
    sentence and cites the line it starts on, which is the correct answer.
    Demanding the quote fit inside one element rejected 37 of 186 findings on
    Whiplash for being right.
    """
    keys = sorted(k for k in table if k >= line_id)[:span]
    return _norm(" ".join(table[k] for k in keys))


def _accept(item: dict, rule_map: dict, table: dict[int, str], *,
            min_confidence: float, tally: FilterStats) -> Finding | None:
    """One judged item through every filter, or None with a reason counted.

    `table` holds exactly the lines this call was shown, so membership in it is
    the window check. Asking the judge for a scene index instead rejected 67 of
    186 findings on Whiplash, because a judge shown scenes 6 to 11 numbers them
    0 to 5. The line id is unambiguous and the scene is derived from it.

    Order matters only in that each rejection is attributed to exactly one
    filter, so the columns sum to `proposed`.
    """
    tally.proposed += 1
    rule = rule_map.get(str(item.get("rule_id", "")))
    if rule is None:
        tally.dropped_unknown_rule += 1
        return None
    try:
        line_id = int(item.get("line_id", -1))
    except (TypeError, ValueError):
        line_id = -1
    cited = table.get(line_id, "")
    if not cited:
        tally.dropped_out_of_window += 1
        return None
    try:
        confidence = float(item.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < min_confidence:
        tally.dropped_low_confidence += 1
        return None

    evidence = _norm(str(item.get("evidence", "")))
    if evidence and evidence not in _cited_context(table, line_id):
        # Told apart because they are different failures and only one of them
        # is the model inventing text. A line-id-only design would have made
        # the second invisible, which is why the quote is required as well.
        if evidence in _norm(" ".join(table[k] for k in sorted(table))):
            tally.dropped_misattributed += 1
        else:
            tally.dropped_unquotable += 1
        return None

    tally.accepted += 1
    return Finding(
        rule_id=rule.id, rule_name=rule.name, severity=Severity(rule.severity),
        message=str(item.get("message", rule.name)), line_no=line_id,
        scene_index=None, evidence=str(item.get("evidence", "")).strip() or cited,
        suggestion=str(item.get("suggestion", "")),
        source=rule.source, tier=3, confidence=confidence,
    )


def _locate_finding(script: Script, finding: Finding) -> Finding:
    """Derive the scene from the cited line, rather than asking for it.

    A judge shown a window numbers the scenes in front of it from zero, so its
    scene index is not the document's. The line id is, and the parser already
    knows which scene each line belongs to.
    """
    for el in script.elements:
        if el.line_no == finding.line_no:
            finding.scene_index = el.scene_index
            break
    return finding


# ------------------------------------------------------------------ providers
# Two ways to ask a model the same question. Anthropic through its SDK, and
# everything else through the OpenAI chat-completions shape over `urllib`,
# because a POST is not worth a second dependency (hard rule 7).


class _Throttle:
    """Space calls to a requests-per-minute budget. No-op when unset."""

    def __init__(self, rpm: int):
        self.gap = 60.0 / rpm if rpm > 0 else 0.0
        self.last = 0.0

    def wait(self) -> None:
        if not self.gap:
            return
        due = self.last + self.gap - time.monotonic()
        if due > 0:
            time.sleep(due)
        self.last = time.monotonic()


def _openai_compatible(base_url: str, api_key: str, model: str, *,
                       system: str, user: str, max_tokens: int,
                       schema: dict) -> str:
    """One chat completion, asking for the findings schema where supported.

    Providers disagree about structured outputs: some honour a JSON schema,
    some only `json_object`, some neither. Rather than maintain a table of who
    does what, this asks for the strictest thing and lets `_parse_findings`
    recover from a model that answered in prose with JSON in it. Degrading is
    the right behaviour here because the hallucination filters downstream do
    not care how the JSON arrived.
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "findings", "strict": True,
                            "schema": schema},
        },
    }
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"] or ""


class QuotaExhausted(Exception):
    """A budget that will not come back before the run ends.

    A per-minute limit is worth waiting out. A per-day one is not: retrying it
    burns wall-clock on calls that cannot succeed, and the run that found this
    spent twenty minutes grinding through four more scripts producing nothing
    but 429s. Told apart, the second aborts the whole run.
    """


def _quota_detail(err: urllib.error.HTTPError) -> tuple[float, bool]:
    """-> (seconds to wait, whether the budget is a daily one).

    Providers disagree about where they put this. A `retry-after` header is the
    standard; Google sends neither that nor a bare object, but a JSON ARRAY
    wrapping an error whose `details` carry a RetryInfo and a QuotaFailure. Both
    shapes are read, and anything unrecognised falls back to a short wait.
    """
    wait = 0.0
    header = err.headers.get("retry-after", "") if err.headers else ""
    try:
        wait = min(float(header), 120.0)
    except (TypeError, ValueError):
        pass
    try:
        body = json.loads(err.read())
    except Exception:                                       # noqa: BLE001
        return wait, False
    if isinstance(body, list):
        body = body[0] if body else {}
    error = body.get("error", {}) if isinstance(body, dict) else {}
    daily = False
    for detail in error.get("details", []):
        if not isinstance(detail, dict):
            continue
        if raw := detail.get("retryDelay"):
            try:
                wait = max(wait, min(float(str(raw).rstrip("s")), 120.0))
            except ValueError:
                pass
        for violation in detail.get("violations", []):
            quota_id = str(violation.get("quotaId", ""))
            # "GenerateRequestsPerDayPerProjectPerModel-FreeTier" is the one
            # that ends a run; "PerMinute" is the one worth sleeping through.
            if "PerDay" in quota_id:
                daily = True
    return wait, daily


def _post_with_retry(call, throttle: _Throttle) -> tuple[str, str]:
    """-> (text, error). Retries a rate limit; gives up on anything else.

    A 429 on a free tier is the expected case rather than a failure, so it is
    waited out. A 400 means the request is wrong and retrying it just burns
    the same quota again.
    """
    for attempt in range(MAX_RETRIES):
        throttle.wait()
        try:
            return call(), ""
        except urllib.error.HTTPError as err:
            if err.code != 429:
                detail = err.read().decode("utf-8", "replace")[:200] if err.fp else ""
                return "", f"HTTP {err.code} {detail}"
            wait, daily = _quota_detail(err)
            if daily:
                raise QuotaExhausted(
                    "the provider's per-day quota for this model is spent") from err
            if attempt == MAX_RETRIES - 1:
                return "", "rate limited after retries"
            time.sleep(wait or 2.0 * (attempt + 1))
        except Exception as exc:                        # noqa: BLE001
            return "", str(exc)
    return "", "rate limited"


def _key_from_file(var: str) -> str:
    """Read a key out of the file named by `<var>_FILE`.

    A file beats an environment variable for a credential: `export` puts the
    key in shell history and in `ps` output for every process on the machine,
    and a key pasted into a terminal tends to end up somewhere it was not
    meant to be. Only the first line is read, so a trailing newline or a
    comment underneath is harmless. Failing to read it returns empty, and the
    caller then reports a missing key rather than crashing.
    """
    path = os.environ.get(var + "_FILE", "").strip()
    if not path:
        return ""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as fh:
            line = fh.readline().strip()
    except OSError:
        return ""
    # A key copied out of a shell snippet arrives as NAME="value". Both the
    # assignment and the quotes are tolerated, because the alternative is a
    # 401 whose message says nothing about a stray quotation mark.
    name, sep, rest = line.partition("=")
    if sep and name.replace("_", "").isalnum() and name.upper() == name:
        line = rest.strip()
    if len(line) >= 2 and line[0] == line[-1] and line[0] in "\"'":
        line = line[1:-1].strip()
    return line


def _describe_provider() -> tuple[str, str, str]:
    """-> (provider, base_url, api_key). An explicit base URL always wins."""
    base = os.environ.get("SLUGLINT_LLM_BASE_URL", "").strip()
    if base:
        key = (os.environ.get("SLUGLINT_LLM_API_KEY")
               or _key_from_file("SLUGLINT_LLM_API_KEY")
               or os.environ.get("OPENAI_API_KEY")
               or _key_from_file("OPENAI_API_KEY") or "")
        host = base.split("//")[-1].split("/")[0]
        return host, base, key
    key = (os.environ.get("ANTHROPIC_API_KEY")
           or _key_from_file("ANTHROPIC_API_KEY") or "")
    return "anthropic", "", key


def _sender(base_url: str, api_key: str, model: str, throttle: _Throttle,
            schema: dict):
    """-> send(system, user) for whichever provider is configured.

    One place that knows the difference between the two, so the windowed pass
    and the document pass cannot drift apart in how they ask.
    """
    if base_url:
        def send_http(system: str, user: str) -> tuple[str, str]:
            return _post_with_retry(
                lambda: _openai_compatible(base_url, api_key, model, system=system,
                                           user=user, max_tokens=MAX_TOKENS,
                                           schema=schema), throttle)
        return send_http

    # `anthropic` lives behind the `llm` extra and CI installs without it, so
    # pylint cannot resolve the name there. That is the dependency being
    # genuinely optional rather than a missing requirement; the guarded import
    # is the whole point. See hard rule 7.
    import anthropic  # noqa: PLC0415  # pylint: disable=import-error
    client = anthropic.Anthropic()

    def send_sdk(system: str, user: str) -> tuple[str, str]:
        def call() -> str:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                # Thinking off: max_tokens caps thinking + output together, and
                # a truncated findings array is worse than a shallower judgment.
                thinking={"type": "disabled"},
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content
                           if getattr(b, "type", "") == "text")
        return _post_with_retry(call, throttle)
    return send_sdk


def _document_body(script: Script) -> tuple[str, dict[int, str]]:
    """The whole script, numbered, with the scene headings kept as landmarks."""
    return _numbered(script.scenes)


def run_document_scale(script: Script, rules: list[Rule], *,
                       model: str = DEFAULT_MODEL, min_confidence: float = 0.6,
                       profile: str = "", stats: FilterStats | None = None,
                       ) -> tuple[list[Finding], list[str]]:
    """Judge the rules a scene window cannot answer, against the whole script.

    Fourteen of the 38 tier-3 rules ask whether the document ever returns to
    something it introduced. On Parasite all fourteen were silent while every
    rule that fired was window scale, and the reason is structural: a judge
    shown scenes 12 to 17 cannot say whether a prop is paid off in scene 90.
    The rule was unanswerable, not unviolated.

    So this sends the script in one call. That is about 100k tokens for a
    feature, which a 1M-context model takes and a small-context one cannot, so
    an oversized script is reported as skipped rather than truncated. Truncating
    would produce exactly the failure this function exists to remove.
    """
    notices: list[str] = []
    tally = stats if stats is not None else FilterStats()
    if not rules:
        return [], notices

    provider, base_url, api_key = _describe_provider()
    tally.provider, tally.model = provider, model
    if not api_key:
        want = "SLUGLINT_LLM_API_KEY" if base_url else "ANTHROPIC_API_KEY"
        return [], [f"Tier 3 document pass skipped ({len(rules)} rules): set {want}."]

    body, table = _document_body(script)
    budget = _env_int("SLUGLINT_DOC_CHAR_BUDGET", 900_000)
    if len(body) > budget:
        return [], [f"Tier 3 document pass skipped: the script is "
                    f"{len(body):,} characters against a budget of {budget:,}. "
                    f"These {len(rules)} rules need the whole document, so a "
                    f"truncated one would answer the wrong question. Raise "
                    f"SLUGLINT_DOC_CHAR_BUDGET on a large-context model."]

    characters = ", ".join(sorted(script.character_registry())) or "none detected"
    user = (f"SCRIPT: {script.title or script.path}\n"
            f"SPEAKING CHARACTERS: {characters}\n"
            f"SCENES: {len(script.scenes)}\n\n"
            f"RULES TO APPLY:\n{_rubric(rules, profile)}\n\n"
            f"WHOLE SCRIPT:\n{body}")

    throttle = _Throttle(REQUESTS_PER_MINUTE)
    send = _sender(base_url, api_key, model, throttle, DOCUMENT_SCHEMA)
    tally.calls += 1
    try:
        raw_text, error = send(DOCUMENT_PROMPT, user)
    except QuotaExhausted as exc:
        tally.calls -= 1
        return [], [f"Tier 3 document pass stopped: {exc}."]
    if error:
        tally.failed_calls += 1
        return [], [f"Tier 3 document pass failed: {error}"]

    rule_map = {r.id: r for r in rules}
    items, _ = _parse_findings(raw_text)
    findings = []
    for item in items:
        # No window: these rules are about the whole script by construction.
        if (finding := _accept(item, rule_map, table,
                               min_confidence=min_confidence,
                               tally=tally)) is not None:
            findings.append(_locate_finding(script, finding))
    notices.append(tally.summary())
    return findings, notices


def run(script: Script, rules: list[Rule], *, model: str = DEFAULT_MODEL,
        min_confidence: float = 0.6, profile: str = "",
        stats: FilterStats | None = None) -> tuple[list[Finding], list[str]]:
    """-> (findings, notices). Never raises on a missing key or a dead provider.

    `stats` is filled in if given, so a caller measuring the hallucination
    filters gets the per-filter drop counts without re-running anything.
    """
    notices: list[str] = []
    tally = stats if stats is not None else FilterStats()
    if not rules:
        return [], notices

    provider, base_url, api_key = _describe_provider()
    tally.provider, tally.model = provider, model
    if not api_key:
        want = "SLUGLINT_LLM_API_KEY" if base_url else "ANTHROPIC_API_KEY"
        return [], [f"Tier 3 skipped ({len(rules)} LLM rules): set {want}, "
                    f"or {want}_FILE pointing at a file that holds it."]

    throttle = _Throttle(REQUESTS_PER_MINUTE)
    try:
        send = _sender(base_url, api_key, model, throttle, FINDINGS_SCHEMA)
    except ImportError:
        return [], ["Tier 3 skipped: `pip install anthropic`, or point "
                    "SLUGLINT_LLM_BASE_URL at an OpenAI-compatible endpoint."]

    rule_map = {r.id: r for r in rules}
    characters = ", ".join(sorted(script.character_registry())) or "none detected"
    rubric = _rubric(rules, profile)
    findings: list[Finding] = []

    for chunk in _chunks(script):
        scene_indices = {s.index for s in chunk}
        body, table = _numbered(chunk)
        tally.scenes_expected += len(chunk)
        user = (f"SCRIPT: {script.title or script.path}\nSPEAKING CHARACTERS: {characters}\n\n"
                f"RULES TO APPLY:\n{rubric}\n\nTEXT TO LINT:\n{body}")
        tally.calls += 1
        try:
            raw_text, error = send(SYSTEM_PROMPT, user)
        except QuotaExhausted as exc:
            # Stop the whole document rather than asking again for every
            # remaining chunk. What was judged before this point still counts,
            # and the notice says how far it got.
            tally.calls -= 1
            notices.append(
                f"Tier 3 stopped at scene {min(scene_indices)} of "
                f"{len(script.scenes)}: {exc}.")
            break
        if error:
            tally.failed_calls += 1
            notices.append(f"Tier 3 call failed for scenes {sorted(scene_indices)}: {error}")
            continue

        items, answered = _parse_findings(raw_text)
        tally.scenes_answered += len(answered & scene_indices)

        for item in items:
            finding = _accept(item, rule_map, table,
                              min_confidence=min_confidence, tally=tally)
            if finding is not None:
                findings.append(_locate_finding(script, finding))

    notices.append(tally.summary())
    return findings, notices
