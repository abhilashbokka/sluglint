"""Tier 1, second pass: how the prose inside the elements is written.

`tier1_format.py` checks that an element is the right SHAPE. This module checks
what is written inside it: capitals used as volume, digits left in speech,
delivery notes doing the work of action, hygiene that survives a PDF round trip
and hygiene that does not.

Same contract as the rest of tier 1. Every handler answers a question with one
right answer, reads its thresholds from `rule.params`, and is narrowed wherever
a naive version would over-fire. The narrowing is the interesting part and is
commented at each rule, because a rule that reports a real defect nine times
out of ten is worse than no rule at all: the tenth report is what teaches a
writer to ignore the other nine.
"""
from __future__ import annotations

import re

from ..models import ElementType, Script
from ..parser import HEADING_RE
from ..rulebook import Rule
from .registry import detector, finding
from .tier1_format import _written_body, dialogue_blocks

# Capitalised words that open a legitimate all-caps line. A montage header, a
# title card, and a shot label are all written in capitals on purpose.
CAPS_HEADERS = re.compile(
    r"^(MONTAGE|SERIES OF SHOTS|END (OF )?MONTAGE|INTERCUT|END (OF )?INTERCUT|"
    r"SUPER|SUPERIMPOSE|TITLE|TITLES|CHYRON|SUBTITLE|INSERT|FLASHBACK|"
    r"END (OF )?FLASHBACK|BACK TO|PRESENT DAY|ANGLE|POV|CLOSE|WIDE|INT|EXT|"
    r"FADE|CUT|DISSOLVE|SMASH|MATCH|THE END|ACT|COLD OPEN|TEASER|TAG|INTERVAL|SONG)\b")

# Colons that legitimately open a line. Everything else in that shape is a
# speaker attribution copied out of a play or a transcript.
LABEL_PREFIX = re.compile(
    r"^(SUPER|SUPERIMPOSE|TITLE|TITLES|CHYRON|SUBTITLE|INSERT|NOTE|SFX|SOUND|MUSIC|"
    r"MONTAGE|SERIES OF SHOTS|INTERCUT|FADE IN|FADE OUT|CUT TO|BACK TO|ANGLE ON|"
    r"CLOSE ON|POV|V\.?O\.?|TRANSLATION|SUBTITLES?|LEGEND|CAPTION|CARD|INTERTITLE|"
    r"INT|EXT|TRIM|OMIT|OMITTED|CONTINUED|REVISED|INSERT CARD)\b", re.IGNORECASE)
SPEAKER_STYLE = re.compile(r"^([A-Z][A-Z0-9 .'\u2019\-]{1,28}):\s+(\S.*)$")

# Verbs that describe business rather than delivery. A parenthetical holding one
# of these is an action line that lost its own line.
STAGE_VERBS = re.compile(
    r"\b(crosses|walks|sits|stands|exits|enters|turns|picks up|puts down|hands|"
    r"opens|closes|pulls|pushes|reaches|grabs|drops|leans|kneels|rises|steps|"
    r"points|nods|shrugs|smiles at|looks at|glances at|moves to|goes to)\b",
    re.IGNORECASE)
BEAT_PARENTHETICAL = re.compile(r"^\(\s*(a\s+)?(beat|pause|long pause|short pause|"
                                r"another beat|silence)\s*\.?\s*\)$", re.IGNORECASE)

# 'had had' and 'that that' are grammatical; a doubled word is otherwise a typo.
LEGITIMATE_DOUBLES = {"had", "that", "very", "no", "yes", "ha", "ho", "so", "long",
                      "far", "well", "come", "now", "there", "bye", "hey", "ok", "okay"}
DOUBLED_WORD = re.compile(r"\b([A-Za-z]{2,})\s+\1\b", re.IGNORECASE)

# A digit run that is genuinely read as a number when spoken. Years, clock
# times, and anything glued to a letter (B12, 4K) are excluded, because those
# are read as themselves.
SPOKEN_NUMERAL = re.compile(r"(?<![\w:/.-])(\d{1,3})(?![\w:/.-])")
YEAR = re.compile(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)")

SOUND_TAG = re.compile(r"\b(SFX|SOUND FX|SOUND EFFECT)\s*:", re.IGNORECASE)
CARD_WORD = re.compile(r"^(SUPER|SUPERIMPOSE|TITLE|CHYRON|SUBTITLE)\b(?!\s*:)", re.IGNORECASE)
MONTAGE_HEAD = re.compile(r"\b(MONTAGE|SERIES OF SHOTS)\b")
ENDING_MARKER = re.compile(r"\b(FADE OUT|FADE TO BLACK|CUT TO BLACK|THE END|END OF (FILM|"
                           r"SCRIPT|EPISODE)|IRIS OUT)\b", re.IGNORECASE)
INT_EXT_STYLE = re.compile(r"^(INT|EXT|EST|I/E|E/I)(\.?)", re.IGNORECASE)
SPACE_BEFORE_PUNCT = re.compile(r"\s+[,.;:!?](?:\s|$)")
NO_SPACE_AFTER_COMMA = re.compile(r",[A-Za-z]")

# What sits immediately before a word decides whether it is a name or a noun.
# 'the boss' is a job; 'BOSS' on its own is the person cued as BOSS.
ARTICLE_BEFORE = re.compile(r"\b(the|a|an|his|her|their|its|my|your|our|every|"
                            r"some|this|that)\s+$", re.IGNORECASE)
POSSESSIVE_BEFORE = re.compile(r"\b(HIS|HER|THEIR|ITS|MY|YOUR|OUR)\s+$")
CURLY_OPEN, CURLY_CLOSE = "\u201c", "\u201d"


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


# ------------------------------------------------------------------- dialogue

@detector("dialogue_in_caps")
def dialogue_in_caps(script: Script, rule: Rule):
    """A habit, measured as a rate.

    Written per line this was the fourth largest source of findings on a sweep
    of 49 real drafts, and it was mostly right about the letter of the rule and
    wrong about the draft. Plenty of produced screenplays set shouted lines in
    capitals as house style; a feature animation in the corpus did it 180
    times on purpose. One line of feedback about the habit is useful. A hundred
    and eighty reports of it is a reason to stop reading the tool.
    """
    limit = int(rule.params.get("min_words", 3))
    max_per_page = float(rule.params.get("max_per_page", 0.5))
    floor = int(rule.params.get("min_count", 5))
    hits = [el for el in script.elements
            if el.type == ElementType.DIALOGUE and _has_letters(el.text)
            # A one-word shout is a choice; a whole line in capitals is a volume
            # knob the page does not have, and it survives no format conversion.
            and el.text == el.text.upper() and len(el.text.split()) >= limit]
    pages = script.estimated_pages or 1.0
    if len(hits) >= floor and len(hits) / pages > max_per_page:
        who = ", ".join(sorted({el.character for el in hits if el.character})[:4])
        yield finding(rule, f"{len(hits)} speeches are set entirely in capitals, "
                            f"{len(hits) / pages:.2f} per page (max {max_per_page}).",
                      line_no=hits[0].line_no, scene_index=hits[0].scene_index,
                      evidence="dialogue in capitals",
                      suggestion=f"Write the lines normally; the actor decides the volume. "
                                 f"Most of these are {who}." if who else
                                 "Write the lines normally; the actor decides the volume.")


@detector("numerals_in_dialogue")
def numerals_in_dialogue(script: Script, rule: Rule):
    """A document-scale habit, deliberately not a report per numeral.

    A script about a baseball season has numbers in it, and reporting ninety of
    them buries the ninety-first thing the writer actually needs to see. The
    rule that survives contact with a real draft is a density: this many per
    page is a habit worth one line of feedback.
    """
    max_per_page = float(rule.params.get("max_per_page", 0.5))
    floor = int(rule.params.get("min_count", 5))
    hits = []
    for el in script.elements:
        if el.type != ElementType.DIALOGUE:
            continue
        # A year, a clock time, and anything glued to a letter are read aloud as
        # themselves. What has to be spelled out is a bare quantity.
        if SPOKEN_NUMERAL.search(YEAR.sub(" ", el.text)):
            hits.append(el)
    pages = script.estimated_pages or 1.0
    if len(hits) >= floor and len(hits) / pages > max_per_page:
        yield finding(rule, f"{len(hits)} speeches contain a bare numeral, "
                            f"{len(hits) / pages:.2f} per page (max {max_per_page}).",
                      line_no=hits[0].line_no, scene_index=hits[0].scene_index,
                      evidence="numerals in dialogue",
                      suggestion="Spell them out; an actor reads the page as it is written. "
                                 "Years, clock times, and codes are already exempt.")


@detector("stage_direction_parenthetical")
def stage_direction_parenthetical(script: Script, rule: Rule):
    for el in script.elements:
        if el.type != ElementType.PARENTHETICAL:
            continue
        if m := STAGE_VERBS.search(el.text):
            yield finding(rule, f"Parenthetical stages an action ('{m.group(0)}').",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="A parenthetical is how a line is said. Movement is action; "
                                     "give it its own line.")


@detector("beat_overuse")
def beat_overuse(script: Script, rule: Rule):
    max_per_page = float(rule.params.get("max_per_page", 0.5))
    floor = int(rule.params.get("min_count", 5))
    hits = [el for el in script.elements
            if el.type == ElementType.PARENTHETICAL and BEAT_PARENTHETICAL.match(el.text.strip())]
    pages = script.estimated_pages or 1.0
    if len(hits) >= floor and len(hits) / pages > max_per_page:
        yield finding(rule, f"{len(hits)} (beat) or (pause) parentheticals, "
                            f"{len(hits) / pages:.2f} per page (max {max_per_page}).",
                      line_no=hits[0].line_no, evidence="beat parenthetical overuse",
                      suggestion="A beat that matters belongs in the action. Most of these are "
                                 "punctuation the dialogue can carry on its own.")


@detector("missing_contd")
def missing_contd(script: Script, rule: Rule):
    """Resumed speeches missing (CONT'D), but only where the script is of two minds.

    A draft that never writes (CONT'D) anywhere has made a choice, and plenty of
    working writers make it because the software puts it back on the next
    repagination. What is a genuine defect is a script that marks some
    resumptions and not others, because then the reader cannot tell an
    unmarked one from a new thought. So the rule fires on the inconsistency,
    once, rather than on every occurrence of a convention the draft has
    already declined.
    """
    position = {id(el): i for i, el in enumerate(script.elements)}
    blocks = dialogue_blocks(script)
    marked, unmarked = 0, []
    for prev, cur in zip(blocks, blocks[1:]):
        prev_cue, cur_cue = prev[0], cur[0]
        if prev_cue.text != cur_cue.text or cur_cue.scene_index != prev_cue.scene_index:
            continue
        between = script.elements[position[id(prev[-1])] + 1:position[id(cur_cue)]]
        # Only action between them. Another speaker in between resets the
        # convention, and nothing in between is F016's problem, not this one.
        if not between or any(el.type != ElementType.ACTION for el in between):
            continue
        if "CONT" in cur_cue.extension.upper().replace("'", "").replace("\u2019", ""):
            marked += 1
        else:
            unmarked.append(cur_cue)
    if marked and unmarked:
        names = ", ".join(sorted({el.text for el in unmarked})[:4])
        yield finding(rule, f"{marked} resumed speeches are marked (CONT'D) and "
                            f"{len(unmarked)} are not ({names}).",
                      line_no=unmarked[0].line_no, scene_index=unmarked[0].scene_index,
                      evidence="inconsistent (CONT'D) marking",
                      suggestion="Mark all of them or none. Mixed, a reader cannot tell a "
                                 "resumed speech from a new one.")


@detector("double_parenthetical")
def double_parenthetical(script: Script, rule: Rule):
    for prev, cur in zip(script.elements, script.elements[1:]):
        # A wide parenthetical wraps across lines and arrives as two elements,
        # so adjacency alone proves nothing. What separates the two cases is
        # whether the first one closed itself: a wrapped one has not.
        first = prev.text.strip()
        closed = first.endswith(")") and first.count("(") == first.count(")")
        if (prev.type == cur.type == ElementType.PARENTHETICAL and closed):
            yield finding(rule, "Two parentheticals with no dialogue between them.",
                          line_no=cur.line_no, scene_index=cur.scene_index, evidence=cur.text,
                          suggestion="Keep one, and move the rest into the line or the action.")


@detector("cue_extension_spacing")
def cue_extension_spacing(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.CHARACTER and re.search(r"[A-Z]\(", el.raw.strip()):
            yield finding(rule, f"Cue '{el.raw.strip()}' has no space before its extension.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.raw.strip(),
                          suggestion=f"Write '{el.text} ({el.extension or 'V.O.'})'.")


@detector("overlong_cue")
def overlong_cue(script: Script, rule: Rule):
    limit = int(rule.params.get("max_words", 5))
    for el in script.elements:
        if el.type == ElementType.CHARACTER and len(el.text.split()) > limit:
            yield finding(rule, f"Character cue runs {len(el.text.split())} words (max {limit}).",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text,
                          suggestion="This reads as an action line in capitals. A cue is a name.")


# --------------------------------------------------------------------- action

@detector("first_appearance_not_capitalised")
def first_appearance_not_capitalised(script: Script, rule: Rule):
    """A character's first appearance in description is set in capitals.

    Reported once for the document. A draft either follows this convention or
    it does not, and a writer who does not needs one line telling them, not
    thirty. Role cues are the trap: 'the boss' and 'the announcer' are the
    common noun rather than the character, so an occurrence sitting behind an
    article is skipped.
    """
    min_lines = int(rule.params.get("min_lines", 2))
    floor = int(rule.params.get("min_count", 2))
    counts = script.dialogue_counts()
    # Only real speaking parts, so a one-line role named in passing is not held
    # to a convention meant to flag the reader's eye to a new person.
    names = [n for n in script.character_registry() if counts.get(n, 0) >= min_lines]
    lowercase: list[str] = []
    for name in sorted(names):
        if len(name) < 4:
            continue
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        for el in script.elements:
            if el.type != ElementType.ACTION or not (m := pattern.search(el.text)):
                continue
            if ARTICLE_BEFORE.search(el.text[:m.start()]):
                continue        # 'the boss' is the noun, not the character
            if m.group(0) != m.group(0).upper():
                lowercase.append(name)
            break
    if len(lowercase) >= floor:
        listed = ", ".join(lowercase[:5]) + (", ..." if len(lowercase) > 5 else "")
        first = lowercase[0]
        yield finding(rule, f"{len(lowercase)} characters are not capitalised where they first "
                            f"appear in description ({listed}).",
                      evidence="first appearances not capitalised",
                      suggestion=f"Capitals on the first appearance only ('{first}', then "
                                 f"'{first.title()}' after) are the page's only signal that a "
                                 f"reader is meeting somebody new.")


@detector("unbalanced_quotes")
def unbalanced_quotes(script: Script, rule: Rule):
    """An odd number of quotation marks in one scene.

    The sibling of F018, and counted over the same unit for the same reason: a
    quoted span that wraps across a line lands in two elements, and anything
    narrower than a scene reports the wrap rather than the defect.
    """
    for scene in script.scenes:
        body = _written_body(scene)
        if not body:
            continue
        text = " ".join(el.text for el in body)
        straight = text.count('"')
        # Curly quotes are directional, so they are checked as a matched pair
        # rather than by parity.
        curly = text.count(CURLY_OPEN) - text.count(CURLY_CLOSE)
        if straight % 2 or curly:
            yield finding(rule, f"Scene {scene.index + 1} has an unbalanced quotation mark.",
                          line_no=scene.line_no, scene_index=scene.index,
                          evidence=f"unbalanced quote in scene {scene.index + 1}",
                          suggestion="Close the quote, or delete the stray mark.")


@detector("title_card_format")
def title_card_format(script: Script, rule: Rule):
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        if m := CARD_WORD.match(el.text.strip()):
            yield finding(rule, f"'{m.group(1)}' card written without a colon.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:70],
                          suggestion=f"Write it as '{m.group(1).upper()}: ...' so it reads as a "
                                     f"card rather than as description.")


@detector("montage_without_items")
def montage_without_items(script: Script, rule: Rule):
    min_items = int(rule.params.get("min_items", 2))
    for i, el in enumerate(script.elements):
        if el.type != ElementType.ACTION or not MONTAGE_HEAD.search(el.text.upper()):
            continue
        if re.search(r"\bEND\b", el.text.upper()):
            continue
        items = 0
        for nxt in script.elements[i + 1:]:
            if nxt.type in (ElementType.SCENE_HEADING, ElementType.TRANSITION):
                break
            if nxt.type == ElementType.ACTION and nxt.text.strip():
                if MONTAGE_HEAD.search(nxt.text.upper()):
                    break
                items += 1
        if items < min_items:
            yield finding(rule, f"Montage header with {items} beat(s) under it (min {min_items}).",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:70],
                          suggestion="List the shots the montage is made of, or write it as an "
                                     "ordinary scene.")


@detector("pov_without_owner")
def pov_without_owner(script: Script, rule: Rule):
    registry = set(script.character_registry())
    for el in script.elements:
        if el.type not in (ElementType.ACTION, ElementType.SCENE_HEADING):
            continue
        up = el.text.upper()
        m = re.search(r"\bP\.?O\.?V\.?\b", up)
        if not m:
            continue
        if any(re.search(rf"\b{re.escape(n)}\b", up) for n in registry):
            continue
        # 'HIS POV', 'HER POV': a possessive names the owner without naming them.
        if POSSESSIVE_BEFORE.search(up[:m.start()]):
            continue
        yield finding(rule, "POV with nobody named to own it.",
                      line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:70],
                      suggestion="Name whose point of view it is, or describe what is in frame.")


@detector("sound_cue_tag")
def sound_cue_tag(script: Script, rule: Rule):
    for el in script.elements:
        if el.type == ElementType.ACTION and (m := SOUND_TAG.search(el.text)):
            yield finding(rule, f"Sound written as a '{m.group(1).upper()}:' tag.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:70],
                          suggestion="Write the sound into the action in capitals. The tag is a "
                                     "post-production label, not a screenplay element.")


@detector("playscript_speaker_style")
def playscript_speaker_style(script: Script, rule: Rule):
    """NAME: line, the way a play or a transcript writes it.

    The shape is common in production furniture too ("TRIM:", "OMIT:"), so a
    label only counts as a speaker when it is a name the script cues properly
    somewhere else, or when it carries the same speech shape more than once.
    A one-off caps word before a colon is almost never a lost cue.
    """
    registry = set(script.character_registry())
    labels: dict[str, int] = {}
    for el in script.elements:
        text = el.text.strip()
        if (el.type == ElementType.ACTION and (hit := SPEAKER_STYLE.match(text))
                and not LABEL_PREFIX.match(text)):
            labels[hit.group(1)] = labels.get(hit.group(1), 0) + 1
    owners = {name for name, n in labels.items() if name in registry or n > 1}
    for el in script.elements:
        if el.type != ElementType.ACTION:
            continue
        m = SPEAKER_STYLE.match(el.text.strip())
        if m and not LABEL_PREFIX.match(el.text.strip()) and m.group(1) in owners:
            yield finding(rule, f"'{m.group(1)}:' attributes a line the way a play does.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=el.text[:70],
                          suggestion=f"Cue the speaker on its own line:\n{m.group(1)}\n"
                                     f"{m.group(2)[:40]}")


@detector("repeated_word")
def repeated_word(script: Script, rule: Rule):
    # Dialogue is exempt on purpose. "Sorry sorry" and "cha cha" are how
    # people speak, and reduplication is ordinary grammar in Telugu, Hindi,
    # and Tamil. Description is written prose, where a doubled word is a typo.
    checked = (ElementType.ACTION, ElementType.SCENE_HEADING)
    for el in script.elements:
        if el.type not in checked:
            continue
        for m in DOUBLED_WORD.finditer(el.text):
            if m.group(1).lower() in LEGITIMATE_DOUBLES:
                continue
            yield finding(rule, f"'{m.group(1)}' is written twice in a row.",
                          line_no=el.line_no, scene_index=el.scene_index, evidence=m.group(0),
                          suggestion=f"Delete the second '{m.group(1)}'.")


# ------------------------------------------------------------------ structure

@detector("consecutive_transitions")
def consecutive_transitions(script: Script, rule: Rule):
    for prev, cur in zip(script.elements, script.elements[1:]):
        if prev.type == cur.type == ElementType.TRANSITION:
            yield finding(rule, f"'{prev.text}' is followed straight by '{cur.text}'.",
                          line_no=cur.line_no, scene_index=cur.scene_index,
                          evidence=f"{prev.text} | {cur.text}",
                          suggestion="One cut, one transition. Keep whichever is true.")


@detector("no_ending_marker")
def no_ending_marker(script: Script, rule: Rule):
    if script.estimated_pages < float(rule.params.get("min_pages", 5)):
        return
    body = [el for el in script.elements
            if el.type != ElementType.TITLE_PAGE and el.text.strip()]
    if not body:
        return
    tail = " ".join(el.text for el in body[-3:])
    if not ENDING_MARKER.search(tail):
        yield finding(rule, "Script does not close on an ending marker.",
                      line_no=body[-1].line_no, evidence="missing ending marker",
                      suggestion="Close with 'FADE OUT.' or 'THE END' so the last page is "
                                 "unambiguously the last page.")


# -------------------------------------------------------------------- headings

@detector("heading_trailing_punctuation")
def heading_trailing_punctuation(script: Script, rule: Rule):
    for sc in script.scenes:
        head = sc.heading.rstrip()
        if head and head[-1] in ".,:;" and sc.int_ext is not None and len(head.split()) > 2:
            yield finding(rule, f"Scene heading ends in '{head[-1]}'.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion=f"'{head.rstrip('.,:; ')}'")


@detector("slash_in_heading")
def slash_in_heading(script: Script, rule: Rule):
    for sc in script.scenes:
        loc = sc.location or ""
        if "/" in loc:
            yield finding(rule, f"Location '{loc.strip()}' joins two places with a slash.",
                          line_no=sc.line_no, scene_index=sc.index, evidence=sc.heading,
                          suggestion="Sub-locations are separated by a spaced hyphen: "
                                     "'INT. HOUSE - KITCHEN - DAY'.")


@detector("int_ext_punctuation_drift")
def int_ext_punctuation_drift(script: Script, rule: Rule):
    styles: dict[bool, list] = {True: [], False: []}
    for sc in script.scenes:
        text = HEADING_RE.match(sc.heading.strip())
        if not text:
            continue
        if m := INT_EXT_STYLE.match(sc.heading.strip()):
            styles[bool(m.group(2))].append(sc)
    dotted, bare = styles[True], styles[False]
    if dotted and bare:
        minority = bare if len(bare) <= len(dotted) else dotted
        yield finding(rule, f"{len(dotted)} headings use 'INT.' and {len(bare)} use 'INT'.",
                      line_no=minority[0].line_no, scene_index=minority[0].index,
                      evidence="INT/EXT punctuation drift",
                      suggestion="Pick one and use it everywhere; breakdown software keys on it.")


# -------------------------------------------------------------------- hygiene

@detector("blank_line_run")
def blank_line_run(script: Script, rule: Rule):
    limit = int(rule.params.get("max_blank", 2))
    lines = script.raw_text.splitlines()
    run = start = 0
    worst = 0
    where = 1
    for i, line in enumerate(lines, start=1):
        if line.strip():
            run = 0
            continue
        start = i if run == 0 else start
        run += 1
        if run > worst:
            worst, where = run, start
    if worst > limit:
        yield finding(rule, f"A run of {worst} blank lines (max {limit}).",
                      line_no=where, evidence="blank line run",
                      suggestion="One blank line separates elements. More is spacing the "
                                 "software adds and removes on its own.")


@detector("mixed_line_endings")
def mixed_line_endings(script: Script, rule: Rule):
    text = script.raw_text
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf and lf:
        yield finding(rule, f"File mixes {crlf} CRLF and {lf} LF line endings.",
                      line_no=1, evidence="mixed line endings",
                      suggestion="Normalise to one; a mixed file breaks diffs and some readers "
                                 "render the stray endings as blank lines.")


@detector("punctuation_spacing")
def punctuation_spacing(script: Script, rule: Rule):
    floor = int(rule.params.get("min_count", 3))
    hits = []
    for el in script.elements:
        if el.type in (ElementType.TITLE_PAGE, ElementType.SECTION):
            continue
        if SPACE_BEFORE_PUNCT.search(el.text) or NO_SPACE_AFTER_COMMA.search(el.text):
            hits.append(el)
    if len(hits) >= floor:
        yield finding(rule, f"{len(hits)} lines have a space before punctuation or none after "
                            f"a comma.",
                      line_no=hits[0].line_no, scene_index=hits[0].scene_index,
                      evidence="punctuation spacing",
                      suggestion="Usually a PDF or OCR round trip. A search for ' ,' and ' .' "
                                 "clears most of it.")
