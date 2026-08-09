"""Per-project ruleset configuration.

The rulebook says what is checkable. A project says what it wants checked, and
those are different questions. A production company running a shooting draft
does not want the spec-script rules; a writers room has a house style on
parentheticals; somebody writing for a market this tool has never seen needs to
turn off two rules and move three thresholds without forking anything.

`.sluglint.yaml`, found next to the script or anywhere above it:

    profile: indian-regional
    rulebook: house-rules.yaml   # optional; that file may `extends: default`
    disable: [F013, F050]
    only: []                     # if non-empty, ONLY these ids run
    severity:
      F062: error                # promote or demote any rule
    params:
      F013: {max_chars: 70}      # retune any threshold
    min_severity: warning        # drop everything softer from the report

Two properties are deliberate. Nothing here can invent a rule, because a rule
that is not in a rulebook has no principle, no source, and no handler; adding
one goes through a rulebook file, where it has to carry its attribution.
And nothing here is hidden: `sluglint rules` prints what the config left
standing, so a report is always explainable by a file the reader can open.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from .models import Finding, Severity
from .rulebook import Rule, Rulebook

CONFIG_NAMES = (".sluglint.yaml", ".sluglint.yml", "sluglint.yaml")
SEVERITY_ORDER = {Severity.SUGGESTION: 0, Severity.WARNING: 1, Severity.ERROR: 2}


@dataclass
class Config:
    path: Path | None = None
    profile: str | None = None
    rulebook: Path | None = None
    disable: set[str] = field(default_factory=set)
    only: set[str] = field(default_factory=set)
    severity: dict[str, str] = field(default_factory=dict)
    params: dict[str, dict] = field(default_factory=dict)
    min_severity: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.disable or self.only or self.severity or self.params
                    or self.profile or self.rulebook or self.min_severity)

    def summary(self) -> str:
        if self.path is None:
            return ""
        parts = []
        if self.only:
            parts.append(f"{len(self.only)} rules allowed")
        if self.disable:
            parts.append(f"{len(self.disable)} disabled")
        if self.severity:
            parts.append(f"{len(self.severity)} re-graded")
        if self.params:
            parts.append(f"{len(self.params)} retuned")
        if self.min_severity:
            parts.append(f"reporting {self.min_severity} and above")
        return f"{self.path.name}: {', '.join(parts) or 'no changes'}"

    def apply(self, book: Rulebook) -> Rulebook:
        """A copy of the rulebook with this project's decisions applied."""
        kept: list[Rule] = []
        for rule in book.rules:
            if self.only and rule.id not in self.only:
                continue
            if rule.id in self.disable:
                continue
            changes = {}
            if new_severity := self.severity.get(rule.id):
                if new_severity not in {s.value for s in Severity}:
                    raise ValueError(f"{rule.id}: unknown severity {new_severity!r}")
                changes["severity"] = new_severity
            if overrides := self.params.get(rule.id):
                changes["params"] = {**rule.params, **overrides}
            kept.append(replace(rule, **changes) if changes else rule)
        return Rulebook(rules=kept, profiles=book.profiles,
                        genres=book.genres, comparables=book.comparables)

    def filter(self, findings: list[Finding]) -> list[Finding]:
        """Drop anything below `min_severity`. Applied after the rules run."""
        if not self.min_severity:
            return findings
        floor = SEVERITY_ORDER[Severity(self.min_severity)]
        return [f for f in findings if SEVERITY_ORDER[f.severity] >= floor]


def _as_set(value) -> set[str]:
    if not value:
        return set()
    return {str(v).strip() for v in (value if isinstance(value, list) else [value])}


def load(path: str | Path) -> Config:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    unknown = set(data) - {"profile", "rulebook", "rules", "disable", "only",
                           "severity", "params", "min_severity"}
    if unknown:
        raise ValueError(f"{p}: unknown config keys: {', '.join(sorted(unknown))}")
    book = data.get("rulebook") or data.get("rules")
    return Config(
        path=p,
        profile=data.get("profile"),
        rulebook=(p.parent / str(book)).resolve() if book else None,
        disable=_as_set(data.get("disable")),
        only=_as_set(data.get("only")),
        severity={k: str(v) for k, v in (data.get("severity") or {}).items()},
        params={k: dict(v) for k, v in (data.get("params") or {}).items()},
        min_severity=str(data.get("min_severity") or ""),
    )


def discover(start: str | Path) -> Config:
    """The nearest config at or above `start`. An empty Config when there is none.

    Walking upward is what lets one file at the root of a script repository
    cover every draft in it, which is the shape these projects actually take:
    a folder per film, a file per draft.
    """
    here = Path(start).resolve()
    for folder in ([here] if here.is_dir() else []) + list(here.parents):
        for name in CONFIG_NAMES:
            candidate = folder / name
            if candidate.is_file():
                return load(candidate)
    return Config()
