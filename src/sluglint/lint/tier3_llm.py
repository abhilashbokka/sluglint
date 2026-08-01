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

Requires ANTHROPIC_API_KEY. Without it, tier 3 is skipped with a notice and
tiers 1-2 still run. Swap the client for anthropic.AnthropicBedrock to run
on AWS Bedrock instead.
"""
from __future__ import annotations

import json
import os
import re

from ..models import Finding, Script, Severity
from ..rulebook import Rule

DEFAULT_MODEL = os.environ.get("SLUGLINT_MODEL", "claude-sonnet-5")
SCENES_PER_CALL = 6
MAX_TOKENS = 8000

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


def _rubric(rules: list[Rule]) -> str:
    parts = []
    for r in rules:
        block = f"[{r.id}] {r.name} (severity: {r.severity})\n  Principle: {r.principle}"
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


def run(script: Script, rules: list[Rule], model: str = DEFAULT_MODEL,
        min_confidence: float = 0.6) -> tuple[list[Finding], list[str]]:
    """-> (findings, notices). Never raises on missing key; returns a notice instead."""
    notices: list[str] = []
    if not rules:
        return [], notices
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return [], [f"Tier 3 skipped ({len(rules)} LLM rules): set ANTHROPIC_API_KEY to enable."]
    try:
        import anthropic
    except ImportError:
        return [], ["Tier 3 skipped: `pip install anthropic` to enable."]

    client = anthropic.Anthropic()
    rule_map = {r.id: r for r in rules}
    characters = ", ".join(sorted(script.character_registry())) or "none detected"
    rubric = _rubric(rules)
    findings: list[Finding] = []

    for chunk in _chunks(script):
        scene_indices = {s.index for s in chunk}
        body = "\n\n".join(_scene_block(s) for s in chunk)
        user = (f"SCRIPT: {script.title or script.path}\nSPEAKING CHARACTERS: {characters}\n\n"
                f"RULES TO APPLY:\n{rubric}\n\nTEXT TO LINT:\n{body}")
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                # Thinking off: max_tokens caps thinking + output together, and a
                # truncated findings array is worse than a shallower judgment.
                thinking={"type": "disabled"},
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA},
                },
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # keep tiers 1-2 usable if the API hiccups
            notices.append(f"Tier 3 call failed for scenes {sorted(scene_indices)}: {exc}")
            continue

        raw_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        chunk_text_lower = body.lower()
        for item in _parse_findings(raw_text):
            rule = rule_map.get(item.get("rule_id", ""))
            evidence = str(item.get("evidence", "")).strip()
            conf = float(item.get("confidence", 0.0) or 0.0)
            # Hallucination filters: known rule, in-window scene, verbatim evidence.
            if (not rule or item.get("scene_index") not in scene_indices
                    or conf < min_confidence
                    or (evidence and evidence.lower() not in chunk_text_lower)):
                continue
            line_no = _locate(script, item["scene_index"], evidence)
            findings.append(Finding(
                rule_id=rule.id, rule_name=rule.name, severity=Severity(rule.severity),
                message=str(item.get("message", rule.name)), line_no=line_no,
                scene_index=item["scene_index"], evidence=evidence,
                suggestion=str(item.get("suggestion", "")), source=rule.source,
                tier=3, confidence=conf,
            ))
    return findings, notices


def _locate(script: Script, scene_index: int, evidence: str) -> int | None:
    if not evidence:
        return None
    needle = evidence.lower()[:60]
    for el in script.elements:
        if el.scene_index == scene_index and needle in el.text.lower():
            return el.line_no
    return None
