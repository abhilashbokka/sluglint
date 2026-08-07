"""Load and query the YAML rulebook. Rules are data; engines dispatch on them.

A rule with no `profiles:` key applies to every profile. A rule that lists
profiles applies only to those. That is how one rulebook holds both "scene
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
    # Per-profile amendment to the principle, for rules that hold everywhere but
    # need different boundaries in one market. A Telugu draft is written in
    # transliterated Telugu, so the spelling rule has to be told that a word
    # outside an English dictionary is the norm rather than a typo.
    profile_notes: dict[str, str] = field(default_factory=dict)

    def applies_to(self, profile: str) -> bool:
        return not self.profiles or profile in self.profiles

    def note_for(self, profile: str) -> str:
        return self.profile_notes.get(profile, "")


@dataclass
class Genre:
    """A named set of bands over measurements, never a verdict.

    Genre is an observable category rather than a judgment of quality, which is
    the only reason it belongs in this rulebook at all. The bands are data so
    they can be argued with, and so they can be replaced by measured values
    the day a licensed corpus exists to measure them from.
    """
    key: str
    name: str
    principle: str = ""
    signals: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class Rulebook:
    rules: list[Rule]
    profiles: dict[str, Profile]
    genres: dict[str, Genre] = field(default_factory=dict)
    comparables: dict[str, dict[str, list[float]]] = field(default_factory=dict)

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


def _read(path: Path) -> dict:
    """Read one rulebook file, resolving `extends:` first.

    `extends: default` (or a path to another rulebook) is what makes a private
    ruleset practical. A studio that wants the shipped 150 rules plus nine of
    its own, with two thresholds moved, writes eleven entries rather than
    forking a 1500-line file and losing every later fix. Rules merge by id, so
    an entry with an existing id patches that rule field by field and an entry
    with a new id adds one.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_ref = data.pop("extends", None)
    if not base_ref:
        return data
    base_path = (DEFAULT_RULEBOOK if str(base_ref) == "default"
                 else (path.parent / str(base_ref)).resolve())
    base = _read(base_path)

    merged = dict(base)
    by_id = {r["id"]: dict(r) for r in base.get("rules", [])}
    order = list(by_id)
    for raw in data.get("rules", []) or []:
        if raw["id"] in by_id:
            by_id[raw["id"]].update(raw)
        else:
            by_id[raw["id"]] = dict(raw)
            order.append(raw["id"])
    merged["rules"] = [by_id[i] for i in order]
    for section in ("profiles", "genres", "comparables"):
        combined = dict(base.get(section) or {})
        combined.update(data.get(section) or {})
        merged[section] = combined
    return merged


def load_rulebook(path: str | Path | None = None) -> Rulebook:
    p = Path(path) if path else DEFAULT_RULEBOOK
    data = _read(p)

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
            profile_notes={k: " ".join(str(v).split())
                           for k, v in (raw.get("profile_notes", {}) or {}).items()},
        )
        for raw in data.get("rules", [])
    ]
    genres = {
        key: Genre(
            key=key,
            name=raw.get("name", key),
            principle=" ".join(str(raw.get("principle", "")).split()),
            signals={k: [float(v[0]), float(v[1])]
                     for k, v in (raw.get("signals", {}) or {}).items()},
        )
        for key, raw in (data.get("genres") or {}).items()
    }
    comparables = {
        profile: {k: [float(v[0]), float(v[1])] for k, v in bands.items()}
        for profile, bands in (data.get("comparables") or {}).items()
    }
    return Rulebook(rules=rules, profiles=profiles, genres=genres, comparables=comparables)


def load_rules(path: str | Path | None = None, profile: str | None = None) -> list[Rule]:
    """Rules that apply to `profile` (the rulebook's default profile if omitted)."""
    return load_rulebook(path).for_profile(profile)


def rules_by_tier(rules: list[Rule], tier: int) -> list[Rule]:
    return [r for r in rules if r.tier == tier]


def rule_index(rules: list[Rule]) -> dict[str, Rule]:
    return {r.id: r for r in rules}
