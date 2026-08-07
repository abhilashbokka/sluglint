"""Tier 1 deterministic format lint: how individual elements are written.

Pure code over the parse, zero LLM cost, 100% precision by design. Every
handler here answers a question with one right answer ("does this heading
have a time of day?"), never a judgement call.

Where a naive check would over-fire, the handler is deliberately narrowed.
F014 only flags a bad separator immediately before a *recognised* time of
day, so hyphenated place names (DRIVE-IN) stay clean. F023 only flags a
mixed-case cue when the name is already a known speaker. A linter that cries
wolf gets uninstalled.

Volume and ratio rules live in tier1_metrics.py.
"""
from __future__ import annotations

import re

from ..models import Element, ElementType, Script
from ..parser import HEADING_RE, TIMES_OF_DAY, split_scene_number
from ..rulebook import Rule
from .registry import detector, finding

ALMOST_SLUG = re.compile(r"^(int|ext|int/ext|i/e)[.\s]", re.IGNORECASE)

# Time markers ordered longest-first so 'MOMENTS LATER' matches before 'LATER'.
_TOD_SORTED = sorted(TIMES_OF_DAY, key=len, reverse=True)
# Words that mean "this is a time of day" even when the exact token is not standard.
TIME_STEMS = re.compile(
    r"\b(DAY|NIGHT|MORNING|AFTERNOON|EVENING|DAWN|DUSK|NOON|MIDNIGHT|SUNRISE|"
    r"SUNSET|TWILIGHT|LATER|CONTINUOUS|MOMENTS|O'CLOCK)\b|DAYTIME|NIGHTTIME|MIDDAY"
)

CAMERA_TERMS = re.compile(
    r"\b(ANGLE ON|CLOSE UP|CLOSE ON|WIDE SHOT|TRACKING SHOT|PAN(?:S|NING)? (?:TO|ACROSS)|"
    r"ZOOM(?:S)? (?:IN|OUT)|DOLLY|CRANE SHOT|POV SHOT|CAMERA (?:MOVES|PUSHES|PULLS))\b"
)
READER_ADDRESS = re.compile(
    r"\b(we see|we hear|we watch|we find|we follow|we cut|"
    r"the camera|camera (?:finds|moves|holds|pushes|pulls|drifts))\b",
    re.IGNORECASE,
)

# Extensions the industry actually uses; anything else is read as part of the name.
CANONICAL_EXTENSIONS = {"VO", "OS", "OC", "CONTD"}
CANONICAL_TRANSITIONS = {
    "CUT TO:", "DISSOLVE TO:", "SMASH CUT TO:", "MATCH CUT TO:", "HARD CUT TO:",
    "JUMP CUT TO:", "TIME CUT TO:", "INTERCUT WITH:", "BACK TO:", "FADE TO:",
    "FADE IN:", "FADE OUT.", "FADE OUT", "FADE TO BLACK.", "FADE TO BLACK",
    "CUT TO BLACK.", "CUT TO BLACK", "SMASH CUT.",
}

PAGINATION_ARTIFACTS = re.compile(
    r"^\s*(?:\(MORE\)|\(CONT(?:'|\u2019)?D\)|CONTINUED:?|\(CONTINUED\)|\d{1,3}\.)\s*$",
    re.IGNORECASE,
)
EXOTIC_WHITESPACE = {"\t": "tab", "\u00a0": "non-breaking space",
                     "\u2028": "line separator", "\u200b": "zero-width space"}
# Written as escapes so the source stays ASCII; these are the characters the
# rule hunts for, so they cannot simply be removed.
SMART_TYPOGRAPHY = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                    "\u2013": "-", "\u2014": "--", "\u2026": "..."}
EMPHASIS_MARKUP = re.compile(r"\*\*?[^*\n]+\*\*?|_[^_\n]+_")


def _norm_ext(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper())


def _trailing_segment(heading: str) -> str:
    """The text after the last ' - ' in a heading, uppercased. '' when absent."""
    text, _ = split_scene_number(heading)
    m = HEADING_RE.match(text)
    rest = text[m.end():].strip() if m else text
    return rest.rpartition(" - ")[2].strip().upper() if " - " in rest else ""


def dialogue_blocks(script: Script) -> list[list[Element]]:
    """Dialogue blocks: each CHARACTER cue plus the elements it owns."""
    out: list[list[Element]] = []
    current: list[Element] = []
    for el in script.elements:
        if el.type == ElementType.CHARACTER:
            if current:
                out.append(current)
            current = [el]
        elif current and el.type in (ElementType.DIALOGUE, ElementType.PARENTHETICAL):
            current.append(el)
        elif current:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


_SPEECH_TYPES = (ElementType.ACTION, ElementType.DIALOGUE,
                 ElementType.PARENTHETICAL, ElementType.CHARACTER)


def _written_body(scene) -> list:
    """Everything in a scene a human typed, in order."""
    return [el for el in scene.elements if el.type in _SPEECH_TYPES and el.text.strip()]


def _paragraphs(script: Script, types: tuple[ElementType, ...]):
    """Consecutive same-type elements on consecutive lines: one written paragraph.

    A paragraph reaches the parser as one element per printed line, so a
    bracket opened on one line and closed on the next is balanced. Grouping
    first is what stops every wrapped aside from reading as a defect.
    """
    block: list = []
    for el in script.elements:
        continues = (block and el.type in types and el.type == block[-1].type
                     and el.character == block[-1].character
                     and el.line_no == block[-1].line_no + 1)
        if not continues and block:
            yield block
            block = []
        if el.type in types:
            block.append(el)
    if block:
        yield block


# ---------------------------------------------------------------- headings

@detector("slugline_prefix")
def slugline_prefix(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.ACTION and ALMOST_SLUG.match(el.text) and not el.text.isupper():
            yield finding(rule, "Line looks like a scene heading but is not formatted as one.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Uppercase it and use the INT./EXT. LOCATION - TIME pattern.")
    for sc in script.scenes:
        if sc.int_ext is None:
            yield finding(rule, "Scene heading is missing an INT./EXT. prefix.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading)


@detector("missing_time_of_day")
def missing_time_of_day(script: Script, rule: Rule):
    """No time marker at all, as opposed to one written unconventionally.

    The parser only recognises the canonical tokens, so 'LATE AFTERNOON',
    'HOURS LATER', 'FAINT DAWN', and 'OFFICE-DAY' all arrive here with
    `time_of_day` unset. None of them is a heading with no time of day; they
    are a heading whose time of day is spelled a way the parser does not
    accept, which is F011's business and F014's, not this rule's.

    Reporting them here cost more than any other single mistake in the book:
    on a sweep of 49 real drafts it was the largest source of findings and
    almost all of them were wrong. So the test is meaning, not spelling. If
    the tail carries a word that MEANS a time, this rule stays quiet and lets
    the formatting rules describe what is actually wrong with it.
    """
    for sc in script.scenes:
        if sc.int_ext is None or sc.time_of_day is not None:
            continue
        if TIME_STEMS.search(sc.heading.upper()):
            continue
        yield finding(rule, "Scene heading has no time of day.",
                      line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                      suggestion=f"e.g. '{sc.heading} - DAY'")


@detector("heading_not_uppercase")
def heading_not_uppercase(script: Script, rule: Rule):
    for sc in script.scenes:
        if sc.heading != sc.heading.upper():
            yield finding(rule, "Scene heading is not in full capitals.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion=f"'{sc.heading.upper()}'")


@detector("nonstandard_time_of_day")
def nonstandard_time_of_day(script: Script, rule: Rule):
    """One report per distinct token, not per scene that uses it.

    A draft that marks every heading '- DAY <<COLOUR SEQUENCE>>' has made one
    decision, not eighty. Reporting the token once and saying how many headings
    carry it is the same information in a form a writer can act on.
    """
    seen: dict[str, list] = {}
    for sc in script.scenes:
        tail = _trailing_segment(sc.heading)
        # Only fire when the tail READS as a time marker but is not a standard
        # one. Otherwise every sub-location ('- KITCHEN') would be a finding.
        if tail and tail not in TIMES_OF_DAY and TIME_STEMS.search(tail):
            seen.setdefault(tail, []).append(sc)
    for tail, scenes in seen.items():
        where = "" if len(scenes) == 1 else f" ({len(scenes)} headings)"
        yield finding(rule, f"Time marker '{tail}' is not one of the standard tokens{where}.",
                      line_no=scenes[0].line_no, scene_index=scenes[0].index,
                      evidence=f"time marker {tail}",
                      suggestion="Use DAY, NIGHT, DAWN, DUSK, MORNING, EVENING, "
                                 "CONTINUOUS, LATER, or SAME.")


@detector("empty_location")
def empty_location(script: Script, rule: Rule):
    for sc in script.scenes:
        loc = (sc.location or "").strip(" -\u2013\u2014")
        if sc.int_ext is not None and (not loc or loc.upper() in TIMES_OF_DAY):
            yield finding(rule, "Scene heading names no location.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Name the place between the prefix and the time marker.")


@detector("overlong_heading")
def overlong_heading(script: Script, rule: Rule):
    limit = int(rule.params.get("max_chars", 60))
    for sc in script.scenes:
        if len(sc.heading) > limit:
            yield finding(rule, f"Scene heading runs {len(sc.heading)} characters (max {limit}).",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Move the description into the action line beneath it.")


@detector("heading_separator")
def heading_separator(script: Script, rule: Rule):
    for sc in script.scenes:
        up = sc.heading.upper().rstrip()
        if "\u2013" in up or "\u2014" in up:
            yield finding(rule, "Scene heading uses a long dash instead of a spaced hyphen.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Use ' - '.")
            continue
        for tod in _TOD_SORTED:
            if up.endswith(tod):
                prefix = up[: -len(tod)]
                if prefix and not prefix.endswith(" - ") and re.search(r"[-,]\s*$", prefix):
                    yield finding(rule, "Time marker is not separated by a spaced hyphen.",
                                  line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                                  suggestion=f"'... - {tod}'")
                break


@detector("duplicate_consecutive_heading")
def duplicate_consecutive_heading(script: Script, rule: Rule):
    for prev, cur in zip(script.scenes, script.scenes[1:]):
        if " ".join(prev.heading.upper().split()) == " ".join(cur.heading.upper().split()):
            yield finding(rule, "This heading repeats the one immediately before it.",
                          line_no=cur.line_no, scene_index=cur.index, evidence=cur.heading,
                          suggestion="Merge the two scenes, or differentiate the headings.")


# ------------------------------------------------------------ dialogue blocks

@detector("orphan_cue")
def orphan_cue(script: Script, rule: Rule):
    for i, el in enumerate(script.elements):
        if el.type != ElementType.CHARACTER:
            continue
        nxt = script.elements[i + 1] if i + 1 < len(script.elements) else None
        if nxt is None or nxt.type not in (ElementType.DIALOGUE, ElementType.PARENTHETICAL):
            yield finding(rule, f"Character cue '{el.text}' has no dialogue under it.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text)


@detector("long_dialogue_block")
def long_dialogue_block(script: Script, rule: Rule):
    limit = int(rule.params.get("max_lines", 6))
    for block in dialogue_blocks(script):
        cue = block[0]
        body = [e for e in block[1:] if e.type == ElementType.DIALOGUE]
        if len(body) > limit:
            yield finding(rule, f"{cue.text} speaks {len(body)} unbroken lines (max {limit}).",
                          line_no=cue.line_no, scene_index=cue.scene_index,
                          evidence=f"{cue.text}: {body[0].text[:60]}",
                          suggestion="Break it with a beat, an interruption, or action.")


@detector("long_parenthetical")
def long_parenthetical(script: Script, rule: Rule):
    limit = int(rule.params.get("max_words", 5))
    for el in script.elements:
        if el.type != ElementType.PARENTHETICAL:
            continue
        words = el.text.strip("()").split()
        if len(words) > limit:
            yield finding(rule, f"Parenthetical runs {len(words)} words (max {limit}).",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Anything this long is action; give it its own line.")


@detector("trailing_parenthetical")
def trailing_parenthetical(script: Script, rule: Rule):
    # A wide parenthetical wraps over several printed lines and arrives here as
    # several elements. Only the last one has to be followed by speech.
    position = {id(el): i for i, el in enumerate(script.elements)}
    for block in _paragraphs(script, (ElementType.PARENTHETICAL,)):
        last = block[-1]
        i = position[id(last)]
        nxt = script.elements[i + 1] if i + 1 < len(script.elements) else None
        if nxt is None or nxt.type != ElementType.DIALOGUE:
            yield finding(rule, "Parenthetical has no dialogue after it to modify.",
                          line_no=block[0].line_no, scene_index=block[0].scene_index,
                          evidence=block[0].text,
                          suggestion="Move it above the line it qualifies, or make it action.")


@detector("consecutive_same_cue")
def consecutive_same_cue(script: Script, rule: Rule):
    position = {id(el): i for i, el in enumerate(script.elements)}
    blocks = dialogue_blocks(script)
    for prev, cur in zip(blocks, blocks[1:]):
        prev_cue, cur_cue = prev[0], cur[0]
        # Adjacent blocks only: any action between them makes a repeat cue correct.
        contiguous = position[id(cur_cue)] == position[id(prev[-1])] + 1
        if contiguous and prev_cue.text == cur_cue.text and not cur_cue.dual:
            yield finding(rule, f"'{cur_cue.text}' is cued twice in a row with nothing between.",
                          line_no=cur_cue.line_no, scene_index=cur_cue.scene_index,
                          evidence=f"{cur_cue.text} repeat cue at scene {cur_cue.scene_index}",
                          suggestion="Merge into one speech, or put a beat of action between them.")


@detector("cue_with_description")
def cue_with_description(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.CHARACTER and re.search(r"[,;]|\s+-\s+", el.text):
            yield finding(rule, f"Character cue '{el.text}' carries a description.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Cue the name alone; describe the role in the action line.")


@detector("nonstandard_extension")
def nonstandard_extension(script: Script, rule: Rule):
    for el in script.elements:
        if el.type != ElementType.CHARACTER:
            continue
        for ext in (e.strip() for e in el.extension.split(",") if e.strip()):
            if _norm_ext(ext) not in CANONICAL_EXTENSIONS:
                yield finding(rule, f"'({ext})' is not a standard character extension.",
                              line_no=el.line_no, scene_index=el.scene_index,
                              evidence=f"{el.text} ({ext})",
                              suggestion="Use (V.O.), (O.S.), (O.C.), or (CONT'D).")
        if "(" in el.text:  # a paren the extension parser did not recognise
            yield finding(rule, f"Cue '{el.text}' carries an unrecognised parenthetical.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Extensions are (V.O.), (O.S.), (O.C.), (CONT'D). "
                                     "Direction goes under the cue, not in it.")


@detector("orphan_dual_dialogue")
def orphan_dual_dialogue(script: Script, rule: Rule):
    for i, el in enumerate(script.elements):
        if el.type != ElementType.CHARACTER or not el.dual:
            continue
        prev = script.elements[i - 1] if i else None
        if prev is None or prev.type not in (ElementType.DIALOGUE, ElementType.PARENTHETICAL):
            yield finding(rule, f"'{el.text}' is marked as simultaneous but nothing precedes it.",
                          line_no=el.line_no, scene_index=el.scene_index,
                          evidence=f"{el.text} dual marker",
                          suggestion="Dual dialogue needs a speech directly above it.")


@detector("probable_lowercase_cue")
def probable_lowercase_cue(script: Script, rule: Rule):
    known = set(script.character_registry())
    if not known:
        return
    lines = {el.line_no for el in script.elements}
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        text = el.text.strip()
        if (text.upper() in known and text != text.upper()
                and len(text.split()) <= 4 and not re.search(r"[.!?,:;]$", text)
                and el.line_no + 1 in lines):
            yield finding(rule, f"'{text}' looks like a character cue that lost its capitals.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=text,
                          suggestion=f"Capitalise it as '{text.upper()}', or these lines never "
                                     f"reach the character registry.")


# ------------------------------------------------------------ document hygiene

@detector("empty_scene")
def empty_scene(script: Script, rule: Rule):
    for sc in script.scenes:
        body = [el for el in sc.elements if el.type != ElementType.SCENE_HEADING]
        if not body:
            yield finding(rule, "Scene heading with nothing under it.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Write the scene or delete the heading.")


@detector("pagination_artifacts")
def pagination_artifacts(script: Script, rule: Rule):
    for i, line in enumerate(script.raw_text.splitlines(), start=1):
        if line.strip() and PAGINATION_ARTIFACTS.match(line):
            yield finding(rule, f"Pagination artifact '{line.strip()}' left in the text.",
                          line_no=i, evidence=line.strip(),
                          suggestion="Delete it; the software repaginates on its own.")


@detector("whitespace_artifacts")
def whitespace_artifacts(script: Script, rule: Rule):
    seen: set[str] = set()
    for i, line in enumerate(script.raw_text.splitlines(), start=1):
        for ch, label in EXOTIC_WHITESPACE.items():
            if ch in line and label not in seen:
                seen.add(label)
                yield finding(rule, f"Source contains a {label} character.",
                              line_no=i, evidence=f"whitespace {label}",
                              suggestion="Layout comes from margins, not embedded whitespace.")


@detector("smart_typography")
def smart_typography(script: Script, rule: Rule):
    seen: set[str] = set()
    for i, line in enumerate(script.raw_text.splitlines(), start=1):
        for ch, plain in SMART_TYPOGRAPHY.items():
            if ch in line and ch not in seen:
                seen.add(ch)
                yield finding(rule, f"Source contains '{ch}' where '{plain}' travels safely.",
                              line_no=i, evidence=f"typography {ch}",
                              suggestion=f"Replace '{ch}' with '{plain}'.")


@detector("unbalanced_delimiters")
def unbalanced_delimiters(script: Script, rule: Rule):
    """Bracket balance over a whole scene, not over one paragraph.

    A wide parenthetical wraps, and its second half lands in a different
    element on a non-adjacent line: '(as he starts to head back' then, after a
    gap, 'toward his desk--) Too many students'. Any grouping that depends on
    element type or line adjacency splits that pair and reports two defects
    where there are none, and on a sweep of real drafts that was over a
    thousand false reports.

    A scene is the coarsest unit that is still actionable and the only one
    robust to every wrap, so balance is counted across the scene and reported
    once. A bracket that opens in one scene and closes in the next is a defect
    either way.
    """
    for scene in script.scenes:
        body = _written_body(scene)
        if not body:
            continue
        text = " ".join(el.text for el in body)
        for opener, closer in (("(", ")"), ("[", "]")):
            n_open, n_close = text.count(opener), text.count(closer)
            if n_open != n_close:
                stray = "unclosed" if n_open > n_close else "unopened"
                yield finding(rule, f"Scene {scene.index + 1} has {abs(n_open - n_close)} "
                                    f"{stray} '{opener}{closer}'.",
                              line_no=scene.line_no, scene_index=scene.index,
                              evidence=f"unbalanced {opener}{closer} in scene {scene.index + 1}",
                              suggestion="Close the bracket, or delete the stray one.")
                break


@detector("title_page_incomplete")
def title_page_incomplete(script: Script, rule: Rule):
    if script.estimated_pages < float(rule.params.get("min_pages", 5)):
        return
    groups = {
        "title": {"title"},
        "author": {"author", "authors", "credit", "written by"},
        "contact": {"contact"},
    }
    have = set(script.title_page)
    missing = [name for name in rule.params.get("required", list(groups))
               if not groups.get(name, {name}) & have]
    if missing:
        yield finding(rule, f"Title page is missing: {', '.join(missing)}.",
                      line_no=1, evidence="title page incomplete",
                      suggestion="Add Title:, Credit:/Written by:, and Contact: lines at the top.")


@detector("missing_fade_in")
def missing_fade_in(script: Script, rule: Rule):
    if script.estimated_pages < float(rule.params.get("min_pages", 5)):
        return
    body = [el for el in script.elements if el.type != ElementType.TITLE_PAGE]
    if not body:
        return
    first = body[0]
    if first.type != ElementType.TRANSITION or not first.text.upper().startswith("FADE IN"):
        yield finding(rule, "Script does not open with FADE IN: or an equivalent marker.",
                      line_no=first.line_no, evidence="missing opening marker",
                      suggestion="Open with 'FADE IN:' above the first scene heading.")


@detector("nonstandard_transition")
def nonstandard_transition(script: Script, rule: Rule):
    for el in script.elements:
        if el.type != ElementType.TRANSITION:
            continue
        if el.text.upper().rstrip() not in CANONICAL_TRANSITIONS:
            yield finding(rule, f"'{el.text}' is not a standard transition.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Use CUT TO:, DISSOLVE TO:, SMASH CUT TO:, MATCH CUT TO:, "
                                     "or FADE OUT.")


# ---------------------------------------------------------------- action lines

@detector("long_action_block")
def long_action_block(script: Script, rule: Rule):
    limit = int(rule.params.get("max_lines", 4))
    # One paragraph, not every action line between two speeches. Three separate
    # two-line beats are not a wall of text, and counting across the blank lines
    # between them reported one on every busy scene.
    for block in _paragraphs(script, (ElementType.ACTION,)):
        if len(block) > limit:
            yield finding(rule, f"Action block runs {len(block)} lines (max {limit}).",
                          line_no=block[0].line_no, scene_index=block[0].scene_index,
                          evidence=block[0].text[:80],
                          suggestion="Break at each new visual beat.")


@detector("camera_direction")
def camera_direction(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.ACTION and (m := CAMERA_TERMS.search(el.text.upper())):
            yield finding(rule, f"Camera direction '{m.group(0)}' in a spec script.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Describe the image instead of the shot.")


@detector("reader_address")
def reader_address(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.ACTION and (m := READER_ADDRESS.search(el.text)):
            yield finding(rule, f"Action line addresses the reader ('{m.group(0)}').",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="Describe the frame directly; drop the narrator.")


@detector("emphasis_markup")
def emphasis_markup(script: Script, rule: Rule):
    limit = int(rule.params.get("max_count", 10))
    hits = [el for el in script.elements
            if el.type == ElementType.ACTION and EMPHASIS_MARKUP.search(el.text)]
    if len(hits) > limit:
        yield finding(rule, f"{len(hits)} action lines carry bold/italic/underline markup "
                            f"(max {limit}).",
                      line_no=hits[0].line_no, evidence="emphasis markup overuse",
                      suggestion="Capitals and sentence structure survive every conversion; "
                                 "markup does not.")
