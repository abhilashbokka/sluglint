"""What the script itself says about each person in it.

Casting, costume, and the first AD all read a screenplay for the same four
facts about every speaking part: how old, which pronouns, what they do, and
where they first walk in. Those facts are on the page, written by the author,
which is what makes reading them back an extraction problem rather than a
judgement.

Three deliberate boundaries:

  * **Nothing is inferred from a name.** A name does not carry an age, a
    gender, a region, or a caste, and a tool that guessed any of those from
    one would be wrong often and harmful when it was. Pronouns come from the
    pronouns the script uses in the same sentence as the character; age comes
    from an age the script writes down. When the page does not say, the answer
    is "unspecified" and stays that way.
  * **Pronouns, not gender.** What is observable is which pronoun the author
    chose. Gender is a fact about a person, pronouns are a fact about the
    document, and only the second one is on the page. The column is labelled
    the way it is measured.
  * **A range, never a number.** "30s" is a casting band and is stored as one.
    A script that writes 34 gets 34, and everything else keeps the width the
    author gave it.

Precision anchor: a pronoun is only attributed to a character when their name
is the ONLY registered name in that sentence. In a sentence with two people in
it, "she" is ambiguous to a reader and must stay ambiguous here.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .models import ElementType, Script

# 'PRIYA (30s)', 'RAJU (early 40s, a mechanic)'. The parenthetical directly
# after a capitalised name is the one place a script reliably states an age.
INTRO = re.compile(
    r"\b([A-Z][A-Z'\u2019\-]{2,}(?:\s+[A-Z][A-Z'\u2019\-]{2,}){0,2})\s*\(([^)]{1,60})\)")

DECADE_WORDS = {
    "teens": 13, "twenties": 20, "thirties": 30, "forties": 40, "fifties": 50,
    "sixties": 60, "seventies": 70, "eighties": 80, "nineties": 90,
}
# Where inside a decade each qualifier sits. Casting reads these as real
# instructions, so they are kept rather than flattened to the decade.
QUALIFIERS = {"early": (0, 3), "mid": (4, 6), "late": (6, 9)}

AGE_RANGE = re.compile(r"\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\b")
AGE_DECADE = re.compile(
    r"\b(?:(early|mid|late)[\s-]+)?(\d{1,2})\s*'?s\b|"
    r"\b(?:(early|mid|late)[\s-]+)?(teens|twenties|thirties|forties|fifties|"
    r"sixties|seventies|eighties|nineties)\b",
    re.IGNORECASE)
AGE_EXACT = re.compile(r"\b(?:age[ds]?\s+)?(\d{1,2})\b")

FEMININE = re.compile(r"\b(she|her|hers|herself)\b", re.IGNORECASE)
MASCULINE = re.compile(r"\b(he|him|his|himself)\b", re.IGNORECASE)
NEUTRAL = re.compile(r"\b(they|them|their|theirs|themself|themselves)\b", re.IGNORECASE)

SENTENCE = re.compile(r"[^.!?]+[.!?]?")

# Words that would otherwise be read as an occupation because they follow the
# age in the same parenthetical.
NOT_A_ROLE = {"years", "year", "old", "ish", "or", "so", "about", "around"}


@dataclass
class CharacterProfile:
    """Everything the document states about one speaking part."""
    name: str
    age_text: str = ""              # exactly as the script writes it
    age_low: int | None = None
    age_high: int | None = None
    pronoun: str = "unspecified"    # she / he / they / unclear / unspecified
    pronoun_counts: dict[str, int] = field(default_factory=dict)
    role: str = ""                  # the non-age part of the introduction
    introduction: str = ""          # the action line they first appear in
    intro_line: int | None = None
    intro_scene: int | None = None

    @property
    def age_band(self) -> str:
        """'30s', '34', '28-35', or '' when the page never says."""
        if self.age_low is None:
            return ""
        if self.age_high is None or self.age_high == self.age_low:
            return str(self.age_low)
        return f"{self.age_low}-{self.age_high}"

    @property
    def described(self) -> bool:
        return bool(self.introduction)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["age_band"] = self.age_band
        d["described"] = self.described
        return d


def parse_age(text: str) -> tuple[str, int | None, int | None]:
    """Read an age out of an introduction parenthetical.

    Returns (as written, low, high). A decade keeps its width because that is
    what the author meant by writing it that way; an exact number keeps its
    precision for the same reason.
    """
    if m := AGE_RANGE.search(text):
        lo, hi = int(m.group(1)), int(m.group(2))
        if 1 <= lo <= hi <= 99:
            return m.group(0), lo, hi
    if m := AGE_DECADE.search(text):
        qualifier = (m.group(1) or m.group(3) or "").lower()
        if m.group(2):
            base = int(m.group(2))
            base = base - base % 10 if base >= 10 else base
        else:
            base = DECADE_WORDS[m.group(4).lower()]
        if not 1 <= base <= 99:
            return "", None, None
        lo_off, hi_off = QUALIFIERS.get(qualifier, (0, 9))
        if base == 13:                      # 'teens' runs 13 to 19, not 13 to 22
            hi_off = min(hi_off, 6)
        return m.group(0), base + lo_off, base + hi_off
    if m := AGE_EXACT.search(text):
        age = int(m.group(1))
        if 1 <= age <= 99:
            return m.group(0), age, age
    return "", None, None


def _role_from(inside: str, age_text: str) -> str:
    """Whatever the parenthetical says besides the age."""
    rest = inside.replace(age_text, " ", 1) if age_text else inside
    rest = re.sub(r"[\s,;]+", " ", rest).strip(" ,;-")
    words = [w for w in rest.split() if w.lower().strip(".,") not in NOT_A_ROLE]
    return " ".join(words)[:48]


def _pronoun_counts(script: Script, registry: set[str]) -> dict[str, dict[str, int]]:
    """Pronoun tallies per character, from two narrow signals.

    1. A sentence that names exactly one character. Reliable when that person
       is the only subject, and wrong when they are not: "MEERA blocks his
       path" is about two people and offers "his" to Meera. This is the noisy
       signal, and it is why nothing is reported off a single observation.
    2. A sentence that BEGINS with a pronoun, directly after a sentence that
       named exactly one character. That is ordinary anaphora and is the clean
       signal, but a screenplay usually repeats the name instead, so on its own
       it finds almost nothing.

    Neither is trustworthy once. Both are trustworthy in aggregate, which is
    what `_dominant` requires before it will answer at all. A sentence naming
    two people is skipped entirely rather than split between them.
    """
    counts: dict[str, dict[str, int]] = {}
    names = sorted(registry, key=len, reverse=True)
    patterns = {n: re.compile(rf"\b{re.escape(n)}\b", re.IGNORECASE) for n in names}
    kinds = (("she", FEMININE), ("he", MASCULINE), ("they", NEUTRAL))

    def tally(name: str, text: str) -> None:
        bucket = counts.setdefault(name, {})
        for key, pattern in kinds:
            if hits := len(pattern.findall(text)):
                bucket[key] = bucket.get(key, 0) + hits

    antecedent: str | None = None
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for sentence in SENTENCE.findall(el.text):
            present = [n for n in names if patterns[n].search(sentence)]
            opens_on_pronoun = re.match(r"\s*(she|he|they)\b", sentence, re.IGNORECASE)
            if len(present) == 1:
                tally(present[0], sentence)
                antecedent = present[0]
            elif not present and opens_on_pronoun and antecedent:
                tally(antecedent, opens_on_pronoun.group(1))
            elif present:
                antecedent = None      # two people named: no safe antecedent left
    return counts


def _dominant(tally: dict[str, int], min_observations: int = 5) -> str:
    """The pronoun the script uses for someone, or an honest non-answer.

    Two guards, both of which decline to answer rather than guess. Too few
    observations and there is nothing to be confident about; no clear majority
    and the evidence genuinely conflicts.

    The bar is set high because of what a two-hander does to the noisy signal.
    In a film about two people, most sentences that name one of them are also
    about the other, so both pronouns show up against both names. A
    three-quarters majority is roughly where that noise stops winning. The
    result is that plenty of characters read "unspecified" who are perfectly
    clear to a human reader, which is the correct trade: a wrong pronoun on a
    cast sheet is worse than a blank one. This is also why there is no rule
    built on this field. Deciding that a script is inconsistent about a
    character needs coreference resolution, which is a model rather than a
    regular expression, and tier 1 does not get to guess.
    """
    total = sum(tally.values())
    if total < min_observations:
        return "unspecified"
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    top, count = ranked[0]
    if count / total < 0.75:
        # "unclear" rather than "mixed" on purpose. Mixed would be a claim about
        # the script; what is actually true is that this method could not tell,
        # and in a two-hander it usually cannot.
        return "unclear"
    return top


def profiles(script: Script) -> dict[str, CharacterProfile]:
    """One profile per speaking part, keyed by the cue name."""
    registry = set(script.character_registry())
    if not registry:
        return {}
    out = {name: CharacterProfile(name=name) for name in registry}
    tallies = _pronoun_counts(script, registry)

    for name, profile in out.items():
        tally = tallies.get(name, {})
        profile.pronoun_counts = dict(sorted(tally.items()))
        profile.pronoun = _dominant(tally)

    # Ages and roles come from the first introduction that carries one, so a
    # later restatement never overwrites the author's first answer.
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        for m in INTRO.finditer(el.text):
            cue = _match_cue(m.group(1), registry)
            if cue is None:
                continue
            profile = out[cue]
            age_text, low, high = parse_age(m.group(2))
            if age_text and not profile.age_text:
                profile.age_text, profile.age_low, profile.age_high = age_text, low, high
            if not profile.role and (role := _role_from(m.group(2), age_text)):
                profile.role = role

    # The first action line that names them: what a reader meets them as.
    seen: set[str] = set()
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        upper = el.text.upper()
        for name in registry - seen:
            if re.search(rf"\b{re.escape(name)}\b", upper):
                seen.add(name)
                out[name].introduction = " ".join(el.text.split())[:160]
                out[name].intro_line = el.line_no
                out[name].intro_scene = el.scene_index
    return out


def _match_cue(written: str, registry: set[str]) -> str | None:
    """Map a name written in action onto the cue it belongs to.

    'PRIYA OKONKWO (30s)' introduces the character cued as 'PRIYA'. Matching on
    a shared word rather than on the whole string is what keeps a full-name
    introduction attached to the short cue underneath it.
    """
    if written in registry:
        return written
    parts = set(written.split())
    for cue in sorted(registry):
        if set(cue.split()) & parts:
            return cue
    return None
