"""Core data models for Sluglint.

A parsed script is a list of Scenes; each Scene is a list of Elements.
Findings are the universal output unit of every lint tier.

Elements keep more than the linters strictly need: the raw source line, the
character extension, the dual-dialogue marker. Tier-1 rules about
document hygiene (stray tabs, smart quotes, pagination artifacts) can only be
checked against text the parser has *not* normalized.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum

LINES_PER_PAGE = 55.0  # standard rough estimate for formatted screenplay pages


class ElementType(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    TITLE_PAGE = "title_page"
    SECTION = "section"        # ACT ONE, COLD OPEN, INTERVAL, SONG: ...


class Severity(str, Enum):
    ERROR = "error"          # objectively wrong (format / hard rules)
    WARNING = "warning"      # very likely a defect (consistency, strong conventions)
    SUGGESTION = "suggestion"  # craft advice (soft rules)


@dataclass
class Element:
    type: ElementType
    text: str
    line_no: int                       # 1-based line in source file
    scene_index: int = -1              # -1 = before first scene
    character: str | None = None    # set on DIALOGUE/PARENTHETICAL (normalized owner)
    raw: str = ""                      # original source line, before stripping
    extension: str = ""                # CHARACTER only: V.O. / O.S. / CONT'D / ...
    dual: bool = False                 # CHARACTER only: fountain '^' simultaneous marker


@dataclass
class Scene:
    index: int
    heading: str                       # as written, scene number included
    line_no: int
    int_ext: str | None = None      # INT / EXT / INT./EXT
    location: str | None = None
    time_of_day: str | None = None
    number: str | None = None       # shooting-script scene number ('14', '14A')
    act: str | None = None          # enclosing act marker, if any
    elements: list[Element] = field(default_factory=list)

    @property
    def characters(self) -> list[str]:
        seen: list[str] = []
        for el in self.elements:
            if el.type == ElementType.CHARACTER and el.text not in seen:
                seen.append(el.text)
        return seen

    @property
    def text(self) -> str:
        return "\n".join(el.text for el in self.elements)

    @property
    def estimated_pages(self) -> float:
        body = [el for el in self.elements if el.text.strip()]
        return round(len(body) / LINES_PER_PAGE, 2)


@dataclass
class Script:
    path: str
    title: str | None
    scenes: list[Scene]
    elements: list[Element]            # flat, in document order
    total_lines: int
    raw_text: str = ""                 # untouched source, for hygiene checks
    title_page: dict[str, str] = field(default_factory=dict)

    @property
    def estimated_pages(self) -> float:
        """~55 formatted lines per page is the standard rough estimate."""
        non_blank = sum(1 for el in self.elements if el.text.strip())
        return round(non_blank / LINES_PER_PAGE, 1)

    def of_type(self, *types: ElementType) -> list[Element]:
        return [el for el in self.elements if el.type in types]

    def character_registry(self) -> dict[str, list[int]]:
        """Normalized character name -> scene indices where they speak."""
        reg: dict[str, list[int]] = {}
        for sc in self.scenes:
            for name in sc.characters:
                reg.setdefault(name, [])
                if sc.index not in reg[name]:
                    reg[name].append(sc.index)
        return reg

    def dialogue_counts(self) -> dict[str, int]:
        """Normalized character name -> number of dialogue lines they speak."""
        counts: dict[str, int] = {}
        for el in self.elements:
            if el.type == ElementType.DIALOGUE and el.character:
                counts[el.character] = counts.get(el.character, 0) + 1
        return counts


@dataclass
class Finding:
    rule_id: str
    rule_name: str
    severity: Severity
    message: str
    line_no: int | None = None
    scene_index: int | None = None
    evidence: str = ""
    suggestion: str = ""
    source: str = ""                   # rulebook attribution
    tier: int = 1
    confidence: float = 1.0            # <1.0 only for LLM findings

    @property
    def fingerprint(self) -> str:
        """Stable identity across drafts: rule + normalized evidence.

        Deliberately excludes line numbers so a finding survives the text
        moving around, which is what makes draft diffing meaningful.
        """
        norm = re.sub(r"[^a-z0-9]+", "", (self.evidence or self.message).lower())
        return f"{self.rule_id}:{hashlib.sha1(norm.encode()).hexdigest()[:12]}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["fingerprint"] = self.fingerprint
        return d
