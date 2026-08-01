"""Detector registry for tiers 1 and 2.

Rules are data; this is the only place that maps a rule's `detect:` key to
code. A handler is a generator that takes (script, rule) and yields Findings.
It reads every threshold from `rule.params` rather than from a constant in
the handler, so a rulebook edit changes behaviour with no code change.

Registering by key rather than dispatching in a long if-chain means the
engine can also answer "which rules in the YAML have no implementation?",
which `sluglint rules --check` uses to keep the rulebook honest.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from ..models import Finding, Script, Severity
from ..rulebook import Rule

Detector = Callable[[Script, Rule], Iterable[Finding]]

_REGISTRY: dict[str, Detector] = {}


def detector(key: str) -> Callable[[Detector], Detector]:
    """Register a handler for a rulebook `detect:` key."""
    def wrap(fn: Detector) -> Detector:
        if key in _REGISTRY:
            raise ValueError(f"duplicate detector key: {key!r}")
        _REGISTRY[key] = fn
        return fn
    return wrap


def finding(
    rule: Rule,
    message: str,
    *,
    line_no: int | None = None,
    scene_index: int | None = None,
    evidence: str = "",
    suggestion: str = "",
) -> Finding:
    """Build a Finding from a Rule.

    `evidence` must be STABLE across drafts. It is what the diff fingerprints
    on. Put counts and line numbers in `message` and keep `evidence` fixed, or every
    re-lint churns the diff.
    """
    return Finding(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=Severity(rule.severity),
        message=message,
        line_no=line_no,
        scene_index=scene_index,
        evidence=evidence,
        suggestion=suggestion,
        source=rule.source,
        tier=rule.tier,
    )


def run_rules(script: Script, rules: list[Rule]) -> list[Finding]:
    """Run every rule that has a registered handler. Unimplemented rules are skipped."""
    out: list[Finding] = []
    for rule in rules:
        handler = _REGISTRY.get(rule.detect)
        if handler is None:
            continue
        out.extend(handler(script, rule))
    return out


def registered_keys() -> set[str]:
    return set(_REGISTRY)


def unimplemented(rules: list[Rule]) -> list[str]:
    """Rule ids whose `detect:` key has no handler. Should always be empty."""
    return [r.id for r in rules if r.tier in (1, 2) and r.detect not in _REGISTRY]


def iter_runs(items: Iterable, key) -> Iterator[tuple[int, list]]:
    """Yield (start_index, run) for maximal runs of equal `key(item)`.

    Several format rules ("N of these in a row") reduce to run-length
    detection, so it lives here once rather than in each handler.
    """
    run: list = []
    start = 0
    last = object()
    for i, item in enumerate(items):
        k = key(item)
        if k != last and run:
            yield start, run
            run, start = [], i
        if not run:
            start = i
        run.append(item)
        last = k
    if run:
        yield start, run
