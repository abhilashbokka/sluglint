"""Production metrics: the numbers, without a verdict attached.

The lint tiers report a metric only when it crosses a threshold, because a
finding is a claim that something is wrong. A producer reading a script for the
first time wants the numbers whether or not anything is wrong with them, which
is what this module computes: who is in it and for how long, which sets carry
the schedule, how the day and night load splits, roughly how long it runs.

Everything here is arithmetic over the parsed script. Nothing calls a model and
nothing is an opinion, which is what makes it safe to put on a dashboard. Where
a number is an estimate rather than a measurement it is named as one, because
the whole value of this layer is that a reader can check it.

**Eighths.** Production measures scene length in eighths of a page and a page
is taken as roughly one minute of screen time. Both conventions are rough and
both are what every schedule in the world is built on, so they are the units
used here.

**Screen time.** Real screen time is decided in the edit and cannot be known
from a script. Two things can: how many pages a character is present for, and
how many words they speak. Both are reported, neither is called screen time
without the word estimated attached.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from . import characters as chars
from . import network as net
from .models import BODY_LINES_PER_PAGE, ElementType, Script, printed_lines

EIGHTHS = 8
NIGHT_TOKENS = {"NIGHT", "DUSK", "DAWN", "EVENING", "MIDNIGHT", "LATE NIGHT"}
DAY_TOKENS = {"DAY", "MORNING", "AFTERNOON", "NOON", "MIDDAY", "SUNRISE", "SUNSET"}
EXTERIOR = {"EXT", "EXT/INT", "INT/EXT", "I/E", "E/I"}

# Vocabulary probes for the genre signals. These are counted, never judged: the
# output is "this script uses N words from the action set", and what that means
# is left to whoever reads it next to a comparable.
ACTION_WORDS = re.compile(
    r"\b(gun|guns|shot|shoots|shooting|fires|blood|bleeding|punch|punches|kick|kicks|"
    r"fight|fights|fighting|chase|chases|chasing|explode|explodes|explosion|crash|"
    r"crashes|blade|knife|sword|rifle|pistol|bullet|bullets|slams|smash|smashes)\b",
    re.IGNORECASE)
INTIMACY_WORDS = re.compile(
    r"\b(kiss|kisses|kissing|embrace|embraces|hugs|hug|tears|weeps|weeping|cries|"
    r"crying|smiles|smiling|laughs|laughing|holds her|holds his|hand in hand)\b",
    re.IGNORECASE)
DREAD_WORDS = re.compile(
    r"\b(dark|darkness|shadow|shadows|silence|silent|creaks|creaking|whispers|"
    r"scream|screams|screaming|blood|corpse|body|dead|grave|flickers|flickering)\b",
    re.IGNORECASE)


def _eighths(pages: float) -> int:
    """Pages to eighths, the unit a schedule is actually written in."""
    return max(1, round(pages * EIGHTHS))


def _fmt_eighths(pages: float) -> str:
    """0.625 -> '5/8'. 2.25 -> '2 2/8'. The way it appears on a strip board."""
    total = _eighths(pages)
    whole, part = divmod(total, EIGHTHS)
    if whole and part:
        return f"{whole} {part}/8"
    if whole:
        return str(whole)
    return f"{part}/8"


@dataclass
class CharacterMetrics:
    name: str
    scenes: list[int]
    dialogue_lines: int
    words: int
    present_pages: float          # pages of the scenes they appear in
    speaking_share: float         # share of all dialogue lines in the script
    first_scene: int
    last_scene: int
    longest_absence: int          # consecutive scenes without them, mid-script
    voice_only: bool
    # Where on the page they are, which is the unit a schedule and a read-through
    # both work in. Scene indices answer "which scene"; these answer "when".
    page_first: float = 0.0
    page_last: float = 0.0
    spans: list[list[int]] = field(default_factory=list)   # runs of consecutive scenes
    # What the script says about them. Extracted, never inferred; see characters.py.
    age_band: str = ""
    pronoun: str = "unspecified"
    role: str = ""
    described: bool = False

    @property
    def estimated_minutes(self) -> float:
        """Presence in pages, read as minutes. An upper bound, not screen time."""
        return round(self.present_pages, 1)

    @property
    def shoot_days_hint(self) -> int:
        """Distinct scenes is the number of setups they must be called for."""
        return len(self.scenes)

    @property
    def timeline(self) -> str:
        """The scenes they are in, collapsed to runs: '3, 7-9, 14'."""
        return ", ".join(f"{a + 1}" if a == b else f"{a + 1}-{b + 1}" for a, b in self.spans)


@dataclass
class LocationMetrics:
    name: str
    scenes: list[int]
    pages: float
    day_scenes: int
    night_scenes: int
    interior: bool
    exterior: bool

    @property
    def eighths(self) -> str:
        return _fmt_eighths(self.pages)

    @property
    def unit_moves(self) -> int:
        """A day and a night at one set are two lighting setups, not one."""
        return int(bool(self.day_scenes)) + int(bool(self.night_scenes))


@dataclass
class SceneMetrics:
    index: int
    heading: str
    location: str | None
    time_of_day: str | None
    int_ext: str | None
    pages: float
    characters: list[str]
    dialogue_lines: int
    action_lines: int
    page_start: float = 0.0        # cumulative page this scene opens on
    page_end: float = 0.0

    @property
    def eighths(self) -> str:
        return _fmt_eighths(self.pages)


@dataclass
class GenreSignals:
    """Observable proportions, with no genre named.

    A genre label is a judgment and this project does not make those. What it
    can do is measure the things genres correlate with and put them next to a
    convention band, so a reader draws their own conclusion and can see exactly
    what it was drawn from.
    """
    night_ratio: float
    exterior_ratio: float
    dialogue_ratio: float
    scenes_per_page: float
    avg_scene_pages: float
    cast_per_page: float
    locations_per_page: float
    action_word_density: float     # per page
    intimacy_word_density: float
    dread_word_density: float
    short_exchange_ratio: float    # speeches under 2 lines, a rhythm measure
    question_ratio: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScriptMetrics:
    title: str | None
    pages: float
    runtime_minutes: float
    scene_count: int
    speaking_cast: int
    location_count: int
    company_moves: int
    day_pages: float
    night_pages: float
    interior_pages: float
    exterior_pages: float
    dialogue_lines: int
    action_lines: int
    characters: list[CharacterMetrics] = field(default_factory=list)
    locations: list[LocationMetrics] = field(default_factory=list)
    scenes: list[SceneMetrics] = field(default_factory=list)
    signals: GenreSignals | None = None
    network: net.CharacterNetwork | None = None

    @property
    def night_share(self) -> float:
        total = self.day_pages + self.night_pages
        return self.night_pages / total if total else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["night_share"] = round(self.night_share, 3)
        for c, src in zip(d["characters"], self.characters):
            c["estimated_minutes"] = src.estimated_minutes
            c["shoot_days_hint"] = src.shoot_days_hint
            c["timeline"] = src.timeline
        for loc, src in zip(d["locations"], self.locations):
            loc["eighths"] = src.eighths
            loc["unit_moves"] = src.unit_moves
        for sc, src in zip(d["scenes"], self.scenes):
            sc["eighths"] = src.eighths
        d["network"] = self.network.to_dict() if self.network else None
        return d


def _scene_pages(scene) -> float:
    """Unrounded scene pages, so a sum of them does not accumulate rounding.

    `prewrapped` and `page_scale` are both the document's decisions, stamped
    onto the scene, which is what makes every layer measure a scene the same
    way. Rounding is the only thing this does differently from
    `Scene.estimated_pages`.
    """
    lines = sum(printed_lines(el.text, el.type, scene.prewrapped)
                for el in scene.elements)
    return lines / BODY_LINES_PER_PAGE * scene.page_scale


def _longest_absence(scene_idxs: list[int]) -> int:
    """Longest run of consecutive scenes between first and last appearance."""
    if len(scene_idxs) < 2:
        return 0
    present = set(scene_idxs)
    longest = run = 0
    for i in range(min(scene_idxs), max(scene_idxs) + 1):
        run = 0 if i in present else run + 1
        longest = max(longest, run)
    return longest


def _spans(scene_idxs: list[int]) -> list[list[int]]:
    """Consecutive scene indices collapsed into [start, end] runs."""
    out: list[list[int]] = []
    for i in scene_idxs:
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def character_metrics(script: Script,
                      attributes: dict[str, chars.CharacterProfile] | None = None,
                      page_starts: dict[int, float] | None = None) -> list[CharacterMetrics]:
    registry = script.character_registry()
    counts = script.dialogue_counts()
    total_lines = sum(counts.values()) or 1
    pages_by_scene = {sc.index: _scene_pages(sc) for sc in script.scenes}
    starts = page_starts or {}
    attrs = attributes or {}
    words: Counter[str] = Counter()
    presence: dict[str, set[str]] = {}
    for el in script.elements:
        if el.type == ElementType.DIALOGUE and el.character:
            words[el.character] += len(el.text.split())
        elif el.type == ElementType.CHARACTER:
            presence.setdefault(el.text, set()).add(el.extension.upper())

    out = []
    for name, scene_idxs in registry.items():
        exts = presence.get(name, set())
        tagged = {e for e in exts if e}
        # Every cue carrying a voice-over tag and none without: heard, never seen.
        # A cue with no extension at all counts against this, which is the whole
        # test: one bare cue means the character is in the room.
        voice_only = bool(tagged) and tagged == exts and all(
            any(tag in e for tag in ("V.O", "VO", "VOICE")) for e in tagged)
        ordered = sorted(scene_idxs)
        first, last = (ordered[0], ordered[-1]) if ordered else (-1, -1)
        profile = attrs.get(name, chars.CharacterProfile(name=name))
        out.append(CharacterMetrics(
            name=name,
            scenes=ordered,
            dialogue_lines=counts.get(name, 0),
            words=words.get(name, 0),
            present_pages=round(sum(pages_by_scene.get(i, 0.0) for i in scene_idxs), 2),
            speaking_share=round(counts.get(name, 0) / total_lines, 4),
            first_scene=first,
            last_scene=last,
            longest_absence=_longest_absence(ordered),
            voice_only=voice_only,
            page_first=round(starts.get(first, 0.0), 2),
            page_last=round(starts.get(last, 0.0) + pages_by_scene.get(last, 0.0), 2),
            spans=_spans(ordered),
            age_band=profile.age_band,
            pronoun=profile.pronoun,
            role=profile.role,
            described=profile.described,
        ))
    out.sort(key=lambda c: (-c.dialogue_lines, c.name))
    return out


def location_metrics(script: Script) -> list[LocationMetrics]:
    by_name: dict[str, LocationMetrics] = {}
    for sc in script.scenes:
        name = (sc.location or "UNSPECIFIED").strip().upper()
        m = by_name.get(name)
        if m is None:
            m = by_name[name] = LocationMetrics(name, [], 0.0, 0, 0, False, False)
        m.scenes.append(sc.index)
        m.pages = round(m.pages + _scene_pages(sc), 2)
        tod = (sc.time_of_day or "").upper()
        if tod in NIGHT_TOKENS:
            m.night_scenes += 1
        elif tod in DAY_TOKENS:
            m.day_scenes += 1
        if (sc.int_ext or "").upper() in EXTERIOR:
            m.exterior = True
        else:
            m.interior = True
    return sorted(by_name.values(), key=lambda loc: (-loc.pages, loc.name))


def scene_metrics(script: Script) -> list[SceneMetrics]:
    out = []
    cursor = 0.0
    for sc in script.scenes:
        dialogue = sum(1 for el in sc.elements if el.type == ElementType.DIALOGUE)
        action = sum(1 for el in sc.elements if el.type == ElementType.ACTION)
        pages = _scene_pages(sc)
        out.append(SceneMetrics(
            index=sc.index, heading=sc.heading, location=sc.location,
            time_of_day=sc.time_of_day, int_ext=sc.int_ext,
            pages=round(pages, 2),
            characters=sc.characters, dialogue_lines=dialogue, action_lines=action,
            page_start=round(cursor, 2), page_end=round(cursor + pages, 2),
        ))
        cursor += pages
    return out


def genre_signals(script: Script, pages: float) -> GenreSignals:
    scenes = script.scenes
    timed = [s for s in scenes if s.time_of_day]
    night = sum(1 for s in timed if (s.time_of_day or "").upper() in NIGHT_TOKENS)
    exterior = sum(1 for s in scenes if (s.int_ext or "").upper() in EXTERIOR)
    dialogue = [el for el in script.elements if el.type == ElementType.DIALOGUE]
    action = [el for el in script.elements if el.type == ElementType.ACTION]
    body = len(dialogue) + len(action) or 1
    action_text = " ".join(el.text for el in action)
    pages = pages or 1.0

    # Speech length is the one rhythm measure that survives translation: a run
    # of one-line exchanges reads fast in any language, and a page of unbroken
    # speech reads slow. It says nothing about whether either is funny.
    speech_runs: list[int] = []
    run = 0
    for el in script.elements:
        if el.type == ElementType.DIALOGUE:
            run += 1
        elif el.type == ElementType.CHARACTER:
            if run:
                speech_runs.append(run)
            run = 0
    if run:
        speech_runs.append(run)
    short = sum(1 for r in speech_runs if r <= 2)

    return GenreSignals(
        night_ratio=round(night / len(timed), 3) if timed else 0.0,
        exterior_ratio=round(exterior / len(scenes), 3) if scenes else 0.0,
        dialogue_ratio=round(len(dialogue) / body, 3),
        scenes_per_page=round(len(scenes) / pages, 3),
        avg_scene_pages=round(pages / len(scenes), 3) if scenes else 0.0,
        cast_per_page=round(len(script.character_registry()) / pages, 3),
        locations_per_page=round(
            len({(s.location or "").upper() for s in scenes if s.location}) / pages, 3),
        action_word_density=round(len(ACTION_WORDS.findall(action_text)) / pages, 3),
        intimacy_word_density=round(len(INTIMACY_WORDS.findall(action_text)) / pages, 3),
        dread_word_density=round(len(DREAD_WORDS.findall(action_text)) / pages, 3),
        short_exchange_ratio=round(short / len(speech_runs), 3) if speech_runs else 0.0,
        question_ratio=round(
            sum(1 for el in dialogue if "?" in el.text) / len(dialogue), 3) if dialogue else 0.0,
    )


@dataclass
class BandCheck:
    """One measurement against one band, with the numbers left visible."""
    signal: str
    value: float
    low: float
    high: float

    @property
    def inside(self) -> bool:
        return self.low <= self.value <= self.high

    @property
    def verdict(self) -> str:
        if self.inside:
            return "within"
        return "below" if self.value < self.low else "above"


@dataclass
class GenreMatch:
    key: str
    name: str
    matched: int
    total: int
    checks: list[BandCheck]

    @property
    def score(self) -> float:
        return round(self.matched / self.total, 3) if self.total else 0.0


def score_genres(signals: GenreSignals, genres: dict) -> list[GenreMatch]:
    """Rank declared genre signatures by how many of their bands the script sits in.

    Deliberately a count rather than a probability. A count is a thing a reader
    can audit line by line, and calling 3 of 5 bands a 60% confidence would
    dress a heuristic up as a measurement.
    """
    values = signals.as_dict()
    out = []
    for key, genre in genres.items():
        checks = [BandCheck(name, values[name], lo, hi)
                  for name, (lo, hi) in genre.signals.items() if name in values]
        out.append(GenreMatch(key, genre.name, sum(c.inside for c in checks),
                              len(checks), checks))
    out.sort(key=lambda g: (-g.score, -g.matched, g.name))
    return out


def compare(metrics: ScriptMetrics, bands: dict) -> list[BandCheck]:
    """The script's headline numbers against the bands for its profile."""
    values = {
        "pages": metrics.pages,
        "scene_count": float(metrics.scene_count),
        "speaking_cast": float(metrics.speaking_cast),
        "location_count": float(metrics.location_count),
        "night_share": round(metrics.night_share, 3),
    }
    return [BandCheck(k, values[k], lo, hi) for k, (lo, hi) in bands.items() if k in values]


def analyse(script: Script) -> ScriptMetrics:
    """Every production number this script can be asked for, in one pass."""
    pages = script.estimated_pages
    # `Scene.page_scale` already stretches the scenes onto a stated page count,
    # so this layer no longer rescales. It used to, and the linter did not,
    # which is how the two came to disagree about how long a scene was.
    scenes = scene_metrics(script)
    page_starts = {sc.index: sc.page_start for sc in scenes}
    cast = character_metrics(script, chars.profiles(script), page_starts)
    locs = location_metrics(script)

    day_pages = night_pages = int_pages = ext_pages = 0.0
    for sc, m in zip(script.scenes, scenes):
        tod = (sc.time_of_day or "").upper()
        if tod in NIGHT_TOKENS:
            night_pages += m.pages
        elif tod in DAY_TOKENS:
            day_pages += m.pages
        if (sc.int_ext or "").upper() in EXTERIOR:
            ext_pages += m.pages
        else:
            int_pages += m.pages

    # A company move is a change of location between consecutive scenes. It is
    # the single biggest lever on a shooting schedule, and it is countable from
    # scene order alone.
    ordered = [(s.location or "").strip().upper() for s in script.scenes]
    moves = sum(1 for a, b in zip(ordered, ordered[1:]) if a != b)

    return ScriptMetrics(
        title=script.title,
        pages=round(pages, 1),
        runtime_minutes=round(pages, 1),   # the one page, one minute convention
        scene_count=len(script.scenes),
        speaking_cast=len(cast),
        location_count=len(locs),
        company_moves=moves,
        # Two places, not one: a short scene rounds to nothing at one decimal
        # and a schedule still has to carry it.
        day_pages=round(day_pages, 2),
        night_pages=round(night_pages, 2),
        interior_pages=round(int_pages, 2),
        exterior_pages=round(ext_pages, 2),
        dialogue_lines=sum(c.dialogue_lines for c in cast),
        action_lines=sum(1 for el in script.elements if el.type == ElementType.ACTION),
        characters=cast, locations=locs, scenes=scenes,
        signals=genre_signals(script, pages),
        network=net.build(script),
    )
