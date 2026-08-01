"""Load and query the YAML rulebook. Rules are data; engines dispatch on them.

A rule with no `profiles:` key applies to every profile. A rule that lists
profiles applies only to those — which is how one rulebook holds both "scene
numbers are an amateur tell" (spec) and "scene numbers are mandatory"
(shooting script) without either becoming a special case in code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Ships inside the package so an installed wheel can find it, not just a
# source checkout.
DEFAULT_RULEBOOK = Path(__file__).resolve().parent / "rulebook.yaml"


@dataclass
class Profile:
    key: str
    name: str
    description: str = ""
    default: bool = False


@dataclass
class Rule:
    id: str
    name: str
    tier: int
    category: str
    severity: str
    principle: str
    source: str = ""
    detect: str = ""
    params: dict = field(default_factory=dict)
    examples: list = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)  # empty = applies to all

    def applies_to(self, profile: str) -> bool:
        return not self.profiles or profile in self.profiles


@dataclass
class Rulebook:
    rules: list[Rule]
    profiles: dict[str, Profile]

    @property
    def default_profile(self) -> str:
        for key, prof in self.profiles.items():
            if prof.default:
                return key
        return next(iter(self.profiles), "us-spec-feature")

    def for_profile(self, profile: str | None) -> list[Rule]:
        key = profile or self.default_profile
        if key not in self.profiles:
            raise KeyError(f"unknown profile {key!r}; known: {', '.join(self.profiles)}")
        return [r for r in self.rules if r.applies_to(key)]


def load_rulebook(path: str | Path | None = None) -> Rulebook:
    p = Path(path) if path else DEFAULT_RULEBOOK
    data = yaml.safe_load(p.read_text(encoding="utf-8"))

    profiles = {
        key: Profile(
            key=key,
            name=raw.get("name", key),
            description=" ".join(str(raw.get("description", "")).split()),
            default=bool(raw.get("default", False)),
        )
        for key, raw in (data.get("profiles") or {}).items()
    }

    rules = [
        Rule(
            id=raw["id"], name=raw["name"], tier=int(raw["tier"]),
            category=raw.get("category", ""), severity=raw["severity"],
            principle=" ".join(str(raw.get("principle", "")).split()),
            source=raw.get("source", ""), detect=raw.get("detect", ""),
            params=raw.get("params", {}) or {}, examples=raw.get("examples", []) or [],
            profiles=list(raw.get("profiles", []) or []),
        )
        for raw in data.get("rules", [])
    ]
    return Rulebook(rules=rules, profiles=profiles)


def load_rules(path: str | Path | None = None, profile: str | None = None) -> list[Rule]:
    """Rules that apply to `profile` (the rulebook's default profile if omitted)."""
    return load_rulebook(path).for_profile(profile)


def rules_by_tier(rules: list[Rule], tier: int) -> list[Rule]:
    return [r for r in rules if r.tier == tier]


def rule_index(rules: list[Rule]) -> dict[str, Rule]:
    return {r.id: r for r in rules}
