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
    dropped_unquotable: int = 0
    accepted: int = 0
    model: str = ""
    provider: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def dropped(self) -> int:
        return self.proposed - self.accepted

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
                f"not quotable {self.dropped_unquotable}].")

# The API validates responses against this, so a malformed judge reply is
# impossible by construction. The hallucination filters below then police what
# the shape cannot: whether the finding is actually grounded in the text.
FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "scene_index": {"type": "integer"},
                    "evidence": {"type": "string",
                                 "description": "A short VERBATIM quote from the provided text."},
                    "message": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["rule_id", "scene_index", "evidence", "message",
                             "suggestion", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a screenplay lint engine, not a critic. You apply ONLY the \
numbered rules provided, to the scene text provided. You never invent rules, never \
comment on story quality outside the rules, and never flag stylistic choices the \
rules permit (sentence fragments, CAPS on sounds/intros, invented proper nouns).

Precision beats recall: if you are not confident a rule is violated, do not flag it.

Return findings against the schema you have been given.
- evidence MUST be a short VERBATIM quote from the provided text. A finding whose
  evidence does not appear in the text will be discarded.
- scene_index MUST be one of the provided scene indices.
- confidence in [0,1]. Return an empty list if nothing violates the rules."""


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


def _scene_block(scene) -> str:
    return f"--- SCENE {scene.index} | {scene.heading} ---\n{scene.text}"


def _parse_findings(text: str) -> list[dict]:
    """Read the findings array out of a response.

    Structured outputs make the happy path a plain json.loads. The bracket
    scan is a fallback for a model set via SLUGLINT_MODEL that does not
    support the schema contract. The engine degrades rather than crashes.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data.get("findings", []) or []
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


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
                       system: str, user: str, max_tokens: int) -> str:
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
                            "schema": FINDINGS_SCHEMA},
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


def _retry_after(err: urllib.error.HTTPError) -> float:
    """Seconds a 429 asked us to wait, capped so a bad header cannot hang a run."""
    raw = err.headers.get("retry-after", "") if err.headers else ""
    try:
        return min(float(raw), 120.0)
    except (TypeError, ValueError):
        return 0.0


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
            if err.code != 429 or attempt == MAX_RETRIES - 1:
                detail = err.read().decode("utf-8", "replace")[:200] if err.fp else ""
                return "", f"HTTP {err.code} {detail}"
            time.sleep(_retry_after(err) or 2.0 * (attempt + 1))
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
    if base_url:
        def send(system: str, user: str) -> tuple[str, str]:
            return _post_with_retry(
                lambda: _openai_compatible(base_url, api_key, model, system=system,
                                           user=user, max_tokens=MAX_TOKENS), throttle)
    else:
        try:
            import anthropic
        except ImportError:
            return [], ["Tier 3 skipped: `pip install anthropic`, or point "
                        "SLUGLINT_LLM_BASE_URL at an OpenAI-compatible endpoint."]
        client = anthropic.Anthropic()

        def send(system: str, user: str) -> tuple[str, str]:
            def call() -> str:
                resp = client.messages.create(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    # Thinking off: max_tokens caps thinking + output together,
                    # and a truncated findings array is worse than a shallower
                    # judgment.
                    thinking={"type": "disabled"},
                    output_config={
                        "effort": "low",
                        "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA},
                    },
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(b.text for b in resp.content
                               if getattr(b, "type", "") == "text")
            return _post_with_retry(call, throttle)

    rule_map = {r.id: r for r in rules}
    characters = ", ".join(sorted(script.character_registry())) or "none detected"
    rubric = _rubric(rules, profile)
    findings: list[Finding] = []

    for chunk in _chunks(script):
        scene_indices = {s.index for s in chunk}
        body = "\n\n".join(_scene_block(s) for s in chunk)
        user = (f"SCRIPT: {script.title or script.path}\nSPEAKING CHARACTERS: {characters}\n\n"
                f"RULES TO APPLY:\n{rubric}\n\nTEXT TO LINT:\n{body}")
        tally.calls += 1
        raw_text, error = send(SYSTEM_PROMPT, user)
        if error:
            tally.failed_calls += 1
            notices.append(f"Tier 3 call failed for scenes {sorted(scene_indices)}: {error}")
            continue

        chunk_text_lower = body.lower()
        for item in _parse_findings(raw_text):
            tally.proposed += 1
            rule = rule_map.get(item.get("rule_id", ""))
            evidence = str(item.get("evidence", "")).strip()
            try:
                conf = float(item.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            # Hallucination filters, counted in order so each rejection is
            # attributed to exactly one of them and the columns sum.
            if not rule:
                tally.dropped_unknown_rule += 1
                continue
            if item.get("scene_index") not in scene_indices:
                tally.dropped_out_of_window += 1
                continue
            if conf < min_confidence:
                tally.dropped_low_confidence += 1
                continue
            if evidence and evidence.lower() not in chunk_text_lower:
                tally.dropped_unquotable += 1
                continue
            tally.accepted += 1
            findings.append(Finding(
                rule_id=rule.id, rule_name=rule.name, severity=Severity(rule.severity),
                message=str(item.get("message", rule.name)),
                line_no=_locate(script, item["scene_index"], evidence),
                scene_index=item["scene_index"], evidence=evidence,
                suggestion=str(item.get("suggestion", "")), source=rule.source,
                tier=3, confidence=conf,
            ))

    notices.append(tally.summary())
    return findings, notices


def _locate(script: Script, scene_index: int, evidence: str) -> int | None:
    if not evidence:
        return None
    needle = evidence.lower()[:60]
    for el in script.elements:
        if el.scene_index == scene_index and needle in el.text.lower():
            return el.line_no
    return None
