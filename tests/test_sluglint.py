"""Behaviour tests. Run: PYTHONPATH=src pytest -q

Structure mirrors the project's core claim, that a linter's accuracy can be
measured:

  * `test_every_rule_fires` is a POSITIVE case per deterministic rule: a
    minimal snippet that must produce exactly that rule id. If a rule ships
    in the rulebook and cannot be made to fire, it is decoration.
  * `test_clean_script_stays_clean` is the NEGATIVE case, and it is the one
    that matters. Precision over recall: a linter that cries wolf gets
    uninstalled.
  * The fixture tests assert against drafts with KNOWN injected defects.

Together these are the seed of the fault-injection eval harness in the
roadmap (mutate a clean script -> labelled corpus -> per-rule precision).
"""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from sluglint.diff import diff_drafts, diff_findings
from sluglint.lint import registered_keys, run_rules, unimplemented
from sluglint.models import ElementType, Finding, Severity
from sluglint.parser import (
    normalize_character,
    parse_file,
    parse_heading,
    parse_text,
    split_scene_number,
)
from sluglint.report import render_console, to_json
from sluglint.rulebook import load_rulebook, load_rules, rules_by_tier

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
V1 = EXAMPLES / "the_last_train.fountain"
V2 = EXAMPLES / "the_last_train_v2.fountain"
CLEAN = EXAMPLES / "clean_pages.fountain"
PILOT = EXAMPLES / "night_shift_pilot.fountain"
SHOOTING = EXAMPLES / "switching_yard_production.fountain"
REGIONAL = EXAMPLES / "nadi_regional.fountain"

BOOK = load_rulebook()
RULES = load_rules()

# F008/F043 are whole-document length rules; every short fixture is outside the
# band by construction, so the precision gate excludes them explicitly rather
# than pretending they do not fire.
DOCUMENT_SCALE = {"F008", "F043"}


def lint(script, profile=None):
    rules = BOOK.for_profile(profile)
    return (run_rules(script, rules_by_tier(rules, 1))
            + run_rules(script, rules_by_tier(rules, 2)))


def ids(findings):
    return {f.rule_id for f in findings}


def fire(rule_id: str, text: str, **params):
    """Run ONE rule over a snippet, optionally retuning its params.

    Overriding params in the test rather than in code is the point: rules are
    data, so a document-scale threshold (min_pages) can be dialled down to
    exercise the same handler on four lines.
    """
    rule = next(r for r in BOOK.rules if r.id == rule_id)
    if params:
        rule = replace(rule, params={**rule.params, **params})
    return run_rules(parse_text(text), [rule])


# ============================================================ parser

def test_parser_structure():
    s = parse_file(V1)
    assert s.title == "The Last Train"
    assert len(s.scenes) == 7
    assert s.scenes[0].int_ext == "INT"
    assert s.scenes[0].time_of_day == "NIGHT"
    assert "JOHN" in s.character_registry()


def test_character_normalization():
    assert normalize_character("JOHN (V.O.) (CONT'D)") == "JOHN"
    assert normalize_character("MEERA ^") == "MEERA"


def test_sound_line_is_not_a_cue():
    s = parse_text("INT. ROOM - DAY\n\nBANG!\nThe door flies open.\n")
    assert all(el.type != ElementType.CHARACTER for el in s.elements)


def test_dialogue_ownership():
    s = parse_file(V1)
    lines = [el for el in s.elements
             if el.type == ElementType.DIALOGUE and el.character == "MEERA"]
    assert len(lines) >= 3


def test_scene_numbers_are_parsed_not_swallowed():
    assert split_scene_number("14 INT. BAR - NIGHT 14") == ("INT. BAR - NIGHT", "14")
    assert split_scene_number("INT. STAGE 2 - DAY") == ("INT. STAGE 2 - DAY", None)
    s = parse_file(SHOOTING)
    assert [sc.number for sc in s.scenes][:3] == ["1", "2", "3"]
    assert s.scenes[0].int_ext == "INT"  # the number did not break heading parsing


def test_act_markers_become_sections():
    s = parse_file(PILOT)
    sections = [el.text for el in s.elements if el.type == ElementType.SECTION]
    assert "COLD OPEN" in sections and "ACT ONE" in sections
    assert s.scenes[0].act == "COLD OPEN"


def test_extensions_and_dual_marker_are_kept():
    s = parse_text("INT. ROOM - DAY\n\nJOHN (V.O.)\nHello.\n\nMAYA ^\nHi.\n")
    cues = [el for el in s.elements if el.type == ElementType.CHARACTER]
    assert cues[0].text == "JOHN" and "V.O." in cues[0].extension
    assert cues[1].dual is True


def test_title_page_is_captured():
    s = parse_file(CLEAN)
    assert s.title_page["title"] == "Clean Pages"
    assert "contact" in s.title_page


def test_parser_is_forgiving_about_garbage():
    """A parse failure would hide the very defects we exist to report."""
    s = parse_text("!!!\n\n\tint bar\n\n((((\n\nJOHN\n")
    assert s.total_lines == 7


# ============================================================ rulebook

def test_rulebook_rule_count():
    assert len(BOOK.rules) == 150


def test_rule_ids_and_detect_keys_are_unique():
    rule_ids = [r.id for r in BOOK.rules]
    assert len(rule_ids) == len(set(rule_ids))
    keys = [r.detect for r in BOOK.rules if r.tier in (1, 2)]
    assert len(keys) == len(set(keys))


def test_every_rule_is_wellformed():
    for r in BOOK.rules:
        assert r.principle and r.source, r.id
        assert r.severity in {"error", "warning", "suggestion"}, r.id
        assert r.tier in (1, 2, 3), r.id
        assert (r.detect != "") == (r.tier in (1, 2)), r.id


def test_no_rule_is_decoration():
    """Every deterministic rule resolves to a handler, and vice versa."""
    assert unimplemented(BOOK.rules) == []
    assert registered_keys() == {r.detect for r in BOOK.rules if r.tier in (1, 2)}


@pytest.mark.parametrize("profile", ["us-spec-feature", "tv-pilot",
                                     "shooting-script", "indian-regional"])
def test_profiles_resolve(profile):
    rules = BOOK.for_profile(profile)
    assert rules and unimplemented(rules) == []
    assert all(r.applies_to(profile) for r in rules)


def test_profile_scoping_is_real():
    spec = {r.id for r in BOOK.for_profile("us-spec-feature")}
    shooting = {r.id for r in BOOK.for_profile("shooting-script")}
    assert "F009" in spec and "F009" not in shooting     # numbers = amateur tell
    assert "F039" in shooting and "F039" not in spec     # numbers = mandatory
    assert "F041" in {r.id for r in BOOK.for_profile("tv-pilot")}


def test_unknown_profile_is_rejected():
    with pytest.raises(KeyError):
        BOOK.for_profile("bollywood-musical")


# ============================================================ precision gate

def test_clean_script_stays_clean():
    findings = [f for f in lint(parse_file(CLEAN)) if f.rule_id not in DOCUMENT_SCALE]
    assert findings == [], [f"{f.rule_id} {f.message}" for f in findings]


@pytest.mark.parametrize("profile", ["us-spec-feature", "tv-pilot",
                                     "shooting-script", "indian-regional"])
def test_clean_script_stays_clean_in_every_profile(profile):
    # F039/F041/F045 demand production furniture a spec draft has no reason to carry.
    allowed = DOCUMENT_SCALE | {"F039", "F041", "F045"}
    findings = [f for f in lint(parse_file(CLEAN), profile) if f.rule_id not in allowed]
    assert findings == [], [f"{f.rule_id} {f.message}" for f in findings]


def test_ordinary_prose_does_not_trip_the_fuzzy_matchers():
    """The tier-2 matchers key on capitalised words; plain scenes must survive."""
    text = ("INT. KITCHEN - DAY\n\nANA (30s) chops onions. Steam fogs the window.\n\n"
            "ANA\nDinner in ten.\n\nOnions hit the pan.\n\nANA\nMaybe twenty.\n")
    assert run_rules(parse_text(text), rules_by_tier(RULES, 2)) == []


# ============================================================ per-rule firing

SNIPPETS = [
    # --- tier 1: headings
    ("F001", "INT. BAR - DAY\n\nHe drinks.\nint. cellar - day\nHe descends.\n", {}),
    ("F002", "INT. BAR\n\nA man drinks.\n", {}),
    ("F010", "int. bar - day\n\nA man drinks.\n", {}),
    ("F011", "INT. BAR - LATE AFTERNOON\n\nA man drinks.\n", {}),
    ("F012", "INT. - DAY\n\nA man drinks.\n", {}),
    ("F013", "INT. THE LONGEST ROOM IN THE ENTIRE BUILDING ON THE FAR SIDE - DAY\n\nHe waits.\n", {}),
    ("F014", "INT. BAR -NIGHT\n\nA man drinks.\n", {}),
    ("F015", "INT. BAR - DAY\n\nHe drinks.\n\nINT. BAR - DAY\n\nHe leaves.\n", {}),
    # --- tier 1: dialogue blocks
    ("F003", "INT. BAR - DAY\n\nJOHN\nCUT TO:\n\nEXT. STREET - DAY\n\nCars pass.\n", {}),
    ("F016", "INT. BAR - DAY\n\nJOHN\none\ntwo\nthree\nfour\nfive\nsix\nseven\n", {}),
    ("F017", "INT. BAR - DAY\n\nJOHN\n(with the weary air of a beaten man)\nFine.\n", {}),
    ("F018", "INT. BAR - DAY\n\nJOHN\nHello.\n(beat)\n\nHe leaves.\n", {}),
    ("F019", "INT. BAR - DAY\n\nJOHN\nHello.\n\nJOHN\nAgain.\n", {}),
    ("F020", "INT. BAR - DAY\n\nJOHN, THE BARBER\nHello.\n", {}),
    ("F021", "INT. BAR - DAY\n\nMAYA (VOICE OVER)\nHello.\n", {}),
    ("F022", "INT. BAR - DAY\n\nJOHN ^\nHello.\n", {}),
    ("F023", "INT. BAR - DAY\n\nJOHN stands.\n\nJOHN\nHello.\n\nJohn\nWhat now.\n", {}),
    # --- tier 1: document hygiene
    ("F024", "INT. BAR - DAY\n\nEXT. STREET - DAY\n\nCars pass.\n", {}),
    ("F025", "INT. BAR - DAY\n\nHe drinks.\n\n(MORE)\n\nCONTINUED:\n", {}),
    ("F026", "INT. BAR - DAY\n\n\tHe drinks slowly.\n", {}),
    ("F027", "INT. BAR - DAY\n\nHe says \u201cno\u201d and leaves.\n", {}),
    ("F028", "INT. BAR - DAY\n\nHe opens the door (and stops.\n", {}),
    ("F029", "INT. BAR - DAY\n\nHe drinks.\n", {"min_pages": 0}),
    ("F030", "INT. BAR - DAY\n\nHe drinks.\n", {"min_pages": 0}),
    ("F031", "INT. BAR - DAY\n\nHe drinks.\n\nSLOWLY FADE INTO:\n\nEXT. STREET - DAY\n\nRain.\n", {}),
    # --- tier 1: metrics and style
    ("F004", "INT. BAR - DAY\n\n" + "\n".join(f"line {i}" for i in range(9)) + "\n", {}),
    ("F005", "INT. BAR - DAY\n\nANGLE ON the glass.\n", {}),
    ("F006", ("INT. A - DAY\n\nx\n\nCUT TO:\n\nINT. B - DAY\n\ny\n\nCUT TO:\n\n"
              "INT. C - DAY\n\nz\n\nCUT TO:\n\nINT. D - DAY\n\nw\n"), {}),
    ("F007", "INT. BAR - DAY\n\n" + "".join(f"JOHN\n(beat)\nline {i}\n\n" for i in range(10)), {}),
    ("F008", "INT. BAR - DAY\n\nHe drinks.\n", {}),
    ("F009", "1 INT. BAR - DAY 1\n\nHe drinks.\n", {}),
    ("F032", "INT. BAR - DAY\n\nHE SLAMS THE GLASS DOWN HARD.\n",
     {"min_action_lines": 0, "max_ratio": 0.1}),
    ("F033", "INT. BAR - DAY\n\nHe drinks!\nHe shouts!\nHe leaves!\nHe returns!\n",
     {"min_pages": 0, "max_per_page": 0.1}),
    ("F034", "INT. BAR - DAY\n\nJOHN\nI don't...\n", {"min_lines": 0, "max_ratio": 0.1}),
    ("F035", "INT. BAR - DAY\n\nWe see the door swing open.\n", {}),
    ("F036", "INT. BAR - DAY\n\nHe drinks.\n\nJOHN\nNo.\n", {"min_lines": 0, "max_ratio": 0.1}),
    ("F037", "INT. BAR - DAY\n\nHe drinks.\nHe waits.\nHe leaves.\n",
     {"min_pages": 0, "max_per_page": 0.5}),
    ("F038", "INT. BAR - DAY\n\nHe drinks *slowly*.\n", {"max_count": 0}),
    # --- tier 2: character identity
    ("C001", "INT. BAR - DAY\n\nJOHN and JON argue.\n\nJOHN\nNo.\n\nJON\nYes.\n", {}),
    ("C002", ("INT. A - DAY\n\nBEA (30s) waits.\n\nBEA\n1.\n\nINT. B - DAY\n\nBEA\n2.\n\n"
              "INT. C - DAY\n\nBEA\n3.\n\nINT. D - DAY\n\nx\n\nINT. E - DAY\n\ny\n\n"
              "INT. F - DAY\n\nz\n\nINT. G - DAY\n\nw\n"), {}),
    ("C003", "INT. BAR - DAY\n\nThe room is empty.\n\nSTRANGER\nHello?\n", {}),
    ("C004", ("EXT. YARD - DAY\n\nx\n\nEXT. YARD - NIGHT\n\ny\n\nEXT. YARD - DAY\n\nz\n"), {}),
    ("C006", "INT. BAR - DAY\n\nA WAITER (20s) passes.\n\nWAITER\nEvening.\n", {}),
    ("C007", ("INT. BAR - DAY\n\nMAYA (30s) sits.\n\nMAYA\nHi.\n\n"
              "INT. HALL - DAY\n\nMAYA (30s) waits.\n\nMAYA\nStill here.\n"), {}),
    ("C008", "INT. BAR - DAY\n\nMAYA (30s) sits. GUS (60s) mops.\n\nMAYA\nHi.\n", {}),
    ("C012", "INT. BAR - DAY\n\nMEERA (30s) waits. Meerah checks her watch.\n\nMEERA\nHi.\n", {}),
    ("C013", ("INT. BAR - DAY\n\nMAYA (30s) sits.\n\nMAYA\nHi.\n\n"
              "INT. HALL - DAY\n\nMAYA (40s) waits.\n\nMAYA\nStill.\n"), {}),
    ("C017", "INT. BAR - DAY\n\nA radio crackles.\n\nHOST (V.O.)\nGood evening.\n", {}),
    ("C018", "INT. BAR - DAY\n\nJOHN (40s) drinks.\n\nJOHN\nHere.\n\nJOHN (O.S.)\nAnd there.\n", {}),
    # --- tier 2: place and time
    ("C005", "INT. TRAIN YARD - DAY\n\nx\n\nINT. TRAIN YARDS - NIGHT\n\ny\n", {}),
    ("C009", "INT. GARAGE - DAY\n\nx\n\nEXT. GARAGE - NIGHT\n\ny\n", {}),
    ("C010", "INT. BAR - DAY\n\nx\n\nINT. LIGHTHOUSE - CONTINUOUS\n\ny\n", {}),
    ("C011", "INT. BAR - DAY\n\nx\n\nINT. BAR - CONTINUOUS\n\ny\n", {}),
    ("C019", "INT. RIVERA APT - DAY\n\nx\n\nINT. RIVERA APARTMENT - NIGHT\n\ny\n", {}),
    # --- tier 2: structural continuity
    ("C014", "INT. BAR - DAY\n\nBEGIN FLASHBACK\n\nA child runs.\n", {}),
    ("C015", "INT. BAR - DAY\n\nMONTAGE\n\nA child runs.\n", {}),
    ("C016", "INT. BAR - DAY\n\nINTERCUT\n\nA phone rings.\n", {}),
    ("C026", "INT. BAR - DAY\n\nHe pockets the REVOLVER and walks out.\n", {}),
    # --- tier 2: production metrics
    ("C020", "INT. BAR - DAY\n\nANA (30s) and BEN (30s) talk.\n\nANA\nHi.\n\nBEN\nHi.\n",
     {"min_pages": 0, "max_speaking_per_page": 0.1}),
    ("C021", "INT. BAR - DAY\n\nx\n\nINT. HALL - DAY\n\ny\n", {"min_pages": 0, "max_per_page": 0.1}),
    ("C022", "INT. BAR - NIGHT\n\nx\n\nINT. HALL - NIGHT\n\ny\n",
     {"min_scenes": 0, "max_ratio": 0.1}),
    ("C023", "INT. BAR - DAY\n\nHe drinks and drinks and drinks.\n", {"max_pages": 0.01}),
    ("C024", ("INT. A - DAY\n\nANA (30s) talks.\n\n" + "ANA\nline.\n\n" * 8
              + "".join(f"INT. {c} - DAY\n\nBEN (30s) waits.\n\nBEN\nline.\n\n"
                        for c in "BCDEFGH")), {}),
    ("C025", ("INT. A - DAY\n\nANA (30s), BEN (30s), CIA (30s), DOV (30s).\n\n"
              + "ANA\nline.\n\n" * 20
              + "BEN\nline.\n\nCIA\nline.\n\nDOV\nline.\n\n" * 7), {}),
    # --- tier 1/2: production load
    ("F047", "".join(f"INT. SET{c} - DAY\n\nx\n\n" for c in "ABCD"), {"min_scenes": 3}),
    ("F048", "INT. BAR - DAY\n\nJOHN\nOne.\nTwo.\nThree.\n", {"min_lines": 2}),
    ("C028", "".join(f"INT. SET{c} - DAY\n\nx\n\n" for c in "ABCD"), {"min_scenes": 3}),
    ("C029", ("INT. HALL - DAY\n\n" + "line\n" * 40
              + "\nINT. A - DAY\n\nx\n\nINT. B - DAY\n\ny\n"), {"min_locations": 3}),
    ("C030", "INT. BAR - DAY\n\nSTRANGER (40s) sits.\n\nSTRANGER\nOne.\nTwo.\n",
     {"min_lines": 2}),

    # --- tier 1: prose inside the elements
    ("F049", "INT. BAR - DAY\n\nJOHN\nGET OUT OF HERE NOW.\n\nMARY\nI SAID GET OUT.\n",
     {"min_count": 2, "max_per_page": 0.0}),
    ("F050", "INT. BAR - DAY\n\nJOHN\nI need 4 of them.\n\nMARY\nTake 12 instead.\n",
     {"min_count": 2, "max_per_page": 0.0}),
    ("F051", "INT. BAR - DAY\n\nJOHN\n(crosses to the door)\nLater.\n", {}),
    ("F052", "INT. BAR - DAY\n\nJOHN\n(beat)\nOne.\n\nMARY\n(a beat)\nTwo.\n",
     {"min_count": 2, "max_per_page": 0.0}),
    ("F053", "INT. BAR - DAY\n\nJOHN\nOne.\n\nHe drinks.\n\nJOHN (CONT'D)\nTwo.\n\n"
              "MARY\nThree.\n\nShe stands.\n\nMARY\nFour.\n", {}),
    ("F054", "INT. BAR - DAY\n\nSarah pours. Daniel waits.\n\nSARAH\nOne.\nTwo.\n\n"
              "DANIEL\nThree.\nFour.\n", {}),
    ("F055", 'INT. BAR - DAY\n\nHe reads the sign: "CLOSED FOR THE SEASON.\n', {}),
    ("F056", "INT. BAR - DAY\n\nHe drinks and leaves.\n", {"min_pages": 0}),
    ("F057", "INT. BAR - DAY\n\nHe drinks.\n\nCUT TO:\n\nDISSOLVE TO:\n\n"
              "INT. HALL - DAY\n\nx\n", {}),
    ("F058", "INT. BAR - DAY\n\nSUPER SIX MONTHS LATER\n", {}),
    ("F059", "INT. BAR - DAY\n\nA MONTAGE of the trip home.\n\nINT. HALL - DAY\n\nHe waits.\n",
     {}),
    ("F060", "INT. BAR - DAY\n\nHe drinks.\n\n\n\n\nHe leaves.\n", {}),
    ("F061", "INT. BAR - DAY\r\n\r\nHe drinks.\n", {}),
    ("F062", "INT. BAR - DAY.\n\nHe drinks.\n", {}),
    ("F063", "INT. HOUSE/KITCHEN - DAY\n\nHe cooks.\n", {}),
    ("F064", "INT. BAR - DAY\n\nJOHN AND MARY AND THE DOG\nHello.\n", {}),
    ("F065", "INT. BAR - DAY\n\nJOHN\n(angry)\n(quietly)\nFine.\n", {}),
    ("F066", "INT. BAR - DAY\n\nPOV of the street below.\n", {}),
    ("F067", "INT. BAR - DAY\n\nSFX: a door slams somewhere upstairs.\n", {}),
    ("F068", "INT. A - DAY\n\nx\n\nINT B - DAY\n\ny\n", {}),
    ("F069", "INT. BAR - DAY\n\nJOHN(V.O.)\nHello.\n", {}),
    ("F070", "INT. BAR - DAY\n\nHe drinks , slowly .\n", {"min_count": 1}),
    ("F071", "INT. BAR - DAY\n\nHe ran ran for the door.\n", {}),
    ("F072", "INT. BAR - DAY\n\nRAVI: Where were you?\n\nRAVI: Answer me.\n", {}),

    # --- tier 2: the cast as a graph, and reference decay
    ("C031", "INT. BAR - DAY\n\nCHITRA'S FATHER\nOne.\n\nCHITRA\u2019S FATHER\nTwo.\n", {}),
    ("C032", "INT. A - DAY\n\nJOHN\nHi.\n\nMARY\nHi.\n\nINT. B - DAY\n\nSOLO\nOne.\nTwo.\n",
     {}),
    ("C033", "INT. A - DAY\n\nJOHN\n1.\n\nMARY\n2.\n\nINT. B - DAY\n\nANA\n3.\n\n"
              "BEN\n4.\n\nCAL\n5.\n", {}),
    ("C034", "INT. HALL - DAY\n\nx\n\n" * 3
             + "".join(f"INT. SET{c} - DAY\n\ny\n\n" for c in "DEFGHI"), {}),
    ("C035", "INT. A - DAY\n\nThe LOCKET glints.\n\nINT. B - DAY\n\nHe holds the LOCKET.\n\n"
              "INT. C - DAY\n\nThe LOCKET again.\n\n"
             + "".join(f"INT. S{c} - DAY\n\nz\n\n" for c in "DEFGHIJK"), {}),
    ("C036", "INT. BAR - DAY\n\n"
             + "\n\n".join(f"{n}\nHi." for n in ["ANA", "BEN", "CAL", "DEV", "EVE"]) + "\n", {}),
    ("C037", "INT. BAR - DAY\n\nWAITER\nOne.\nTwo.\n", {"min_lines": 2}),
    ("C038", "".join(f"INT. S{i} - DAY\n\nP{i}\nHi.\n\n" for i in range(24)),
     {"min_scenes": 4, "max_cast": 1, "opening_share": 0.5}),
    ("C040", "INT. BAR - DAY\n\nJOHN\nOne.\nTwo.\nThree.\n", {"min_lines": 2}),
]


@pytest.mark.parametrize("rule_id,text,params", SNIPPETS, ids=[s[0] for s in SNIPPETS])
def test_every_rule_fires(rule_id, text, params):
    hits = fire(rule_id, text, **params)
    assert hits, f"{rule_id} did not fire on its own positive fixture"
    assert all(f.rule_id == rule_id for f in hits)
    assert all(f.message for f in hits)


PROFILE_SNIPPETS = [
    ("F039", "shooting-script", "INT. BAR - DAY\n\nHe drinks.\n", {}),
    ("F040", "shooting-script",
     "1 INT. A - DAY 1\n\nx\n\n5 INT. B - DAY 5\n\ny\n\n4 INT. C - DAY 4\n\nz\n", {}),
    ("F041", "tv-pilot", "INT. BAR - DAY\n\nHe drinks.\n", {}),
    ("F042", "tv-pilot",
     "ACT ONE\n\nINT. A - DAY\n\nx\n\nACT TWO\n\nINT. B - DAY\n\na\nb\nc\nd\ne\nf\ng\nh\n", {}),
    ("F043", "tv-pilot", "INT. BAR - DAY\n\nHe drinks.\n", {}),
    ("F044", "indian-regional", "EXT. RIVER - DAY\n\nA song sequence carries them downriver.\n", {}),
    ("F045", "indian-regional", "EXT. RIVER - DAY\n\nHe rows.\n", {}),
    ("F046", "indian-regional",
     "EXT. RIVER - DAY\n\nRAJU (30s) rows.\n\nRAJU\nHi.\n\n\u0c30\u0c3e\u0c1c\u0c41\nHi again.\n", {}),
    ("C039", "us-spec-feature",
     "".join(f"INT. S{i} - DAY\n\nJOHN\nHi.\n\n" for i in range(8))
     + "INT. LAST - DAY\n\nLATECOMER\nOne.\nTwo.\n", {"min_lines": 2}),
    ("C027", "tv-pilot",
     ("".join(f"INT. {c} - DAY\n\nx\n\n" for c in "ABCDE")
      + "INT. F - DAY\n\nNURSE (30s) arrives.\n\nNURSE\n1.\n\n"
      + "INT. G - DAY\n\nNURSE\n2.\n\nINT. H - DAY\n\nNURSE\n3.\n"), {}),
]


@pytest.mark.parametrize("rule_id,profile,text,params", PROFILE_SNIPPETS,
                         ids=[s[0] for s in PROFILE_SNIPPETS])
def test_profile_rules_fire(rule_id, profile, text, params):
    assert rule_id in {r.id for r in BOOK.for_profile(profile)}
    hits = fire(rule_id, text, **params)
    assert hits, f"{rule_id} did not fire on its own positive fixture"


def test_snippet_coverage_is_complete():
    """Every deterministic rule in the book has a positive fixture above."""
    covered = {s[0] for s in SNIPPETS} | {s[0] for s in PROFILE_SNIPPETS}
    expected = {r.id for r in BOOK.rules if r.tier in (1, 2)}
    assert expected - covered == set(), f"no positive fixture for {sorted(expected - covered)}"


# ============================================================ fixtures

def test_tier1_detects_injected_format_defects():
    found = ids(lint(parse_file(V1)))
    for expected in ("F002", "F004", "F005", "F006"):
        assert expected in found, f"{expected} should fire on draft 1"


def test_tier2_detects_injected_consistency_defects():
    found = ids(lint(parse_file(V1)))
    for expected in ("C001", "C002", "C004", "C005"):
        assert expected in found, f"{expected} should fire on draft 1"


def test_name_drift_is_an_error():
    drift = [f for f in lint(parse_file(V1)) if f.rule_id == "C001"]
    assert drift and drift[0].severity == Severity.ERROR
    assert "JON" in drift[0].evidence and "JOHN" in drift[0].evidence


def test_shooting_fixture_reports_numbering_defects():
    found = ids(lint(parse_file(SHOOTING), "shooting-script"))
    assert "F039" in found      # one scene left unnumbered
    assert "F040" in found      # 5 before 4
    assert "F025" in found      # (MORE) / CONTINUED: survived the conversion


def test_pilot_fixture_reports_structure_defects():
    found = ids(lint(parse_file(PILOT), "tv-pilot"))
    assert "F042" in found      # act lengths out of balance
    assert "F043" in found      # short of either pilot band
    assert "F041" not in found  # act markers ARE present


def test_regional_fixture_reports_regional_defects():
    found = ids(lint(parse_file(REGIONAL), "indian-regional"))
    assert "F044" in found      # song sequence buried in action
    assert "F045" in found      # no INTERVAL marker
    assert "F046" in found      # cues in two writing systems


def test_profile_changes_the_verdict():
    """The same draft, linted two ways, must disagree about scene numbers."""
    script = parse_file(SHOOTING)
    assert "F009" in ids(lint(script, "us-spec-feature"))    # numbers are a tell
    assert "F009" not in ids(lint(script, "shooting-script"))


# ============================================================ diff

def test_diff_resolved_and_new():
    f_old = [Finding("C001", "drift", Severity.ERROR, "m", evidence="JOHN | JON"),
             Finding("F002", "tod", Severity.WARNING, "m", evidence="INT. SHACK")]
    f_new = [Finding("F002", "tod", Severity.WARNING, "m", evidence="INT. SHACK"),
             Finding("F005", "camera", Severity.SUGGESTION, "m", evidence="CLOSE ON x")]
    d = diff_findings(f_old, f_new)
    assert ids(d.resolved) == {"C001"}
    assert ids(d.introduced) == {"F005"}
    assert ids(d.persisting) == {"F002"}


def test_fingerprint_survives_line_moves():
    a = Finding("F005", "camera", Severity.SUGGESTION, "m", line_no=10, evidence="ANGLE ON board")
    b = Finding("F005", "camera", Severity.SUGGESTION, "m", line_no=99, evidence="ANGLE ON board")
    assert a.fingerprint == b.fingerprint


def test_metric_findings_keep_a_stable_fingerprint():
    """Counts belong in `message`, never `evidence`, or every re-lint churns."""
    small = fire("F033", "INT. BAR - DAY\n\nHe shouts!\nHe waits.\nHe leaves.\n",
                 min_pages=0, max_per_page=0.1)
    big = fire("F033", "INT. BAR - DAY\n\nHe shouts!\nHe roars!\nHe howls!\n",
               min_pages=0, max_per_page=0.1)
    assert small[0].fingerprint == big[0].fingerprint
    assert small[0].message != big[0].message


def test_draft_diff_on_fixtures():
    s1, s2 = parse_file(V1), parse_file(V2)
    d = diff_drafts(s1, s2, lint(s1), lint(s2))
    resolved = ids(d.findings.resolved)
    assert "C001" in resolved            # JON -> JOHN fixed in v2
    assert "C004" in resolved            # day/night whiplash fixed
    assert "F005" in ids(d.findings.introduced)                     # v2 adds CLOSE ON
    assert any(f.rule_id == "C002" for f in d.findings.persisting)  # MEERA still vanishes


# ============================================================ report / CLI

def test_json_report_is_machine_readable():
    import json
    script = parse_file(V1)
    payload = json.loads(to_json(script, lint(script), profile="us-spec-feature"))
    assert payload["profile"] == "us-spec-feature"
    assert payload["summary"]["error"] >= 1
    assert {"rule_id", "severity", "fingerprint"} <= set(payload["findings"][0])


def test_console_report_names_the_profile():
    script = parse_file(V1)
    out = render_console(script, lint(script), [], profile="us-spec-feature")
    assert "Sluglint" in out and "profile: us-spec-feature" in out


def test_cli_lint_exits_nonzero_on_errors():
    from sluglint.cli import main
    assert main(["lint", str(V1)]) == 1          # V1 has a name-drift error
    assert main(["lint", str(CLEAN)]) == 0       # clean draft, warnings only
    assert main(["rules", "--check"]) == 0


# ============================================================ real-script parsing
# Every case below came from running the linter over produced screenplays and
# finding that the engine, not the script, was wrong.

def test_contd_with_a_typographic_apostrophe_is_still_an_extension():
    """Final Draft writes CONT’D. Left unstripped it forks the character."""
    script = parse_text("INT. BAR - DAY\n\nCHITRA\nOne.\n\nCHITRA (CONT’D)\nTwo.\n")
    assert set(script.character_registry()) == {"CHITRA"}


def test_combined_prefix_parses_in_either_order():
    _, location, tod = parse_heading("EXT./INT. HILL HOUSE - NIGHT")
    assert location == "HILL HOUSE" and tod == "NIGHT"


def test_forced_action_marker_beats_the_cue_shape():
    script = parse_text("INT. HOUSE - DAY\n\n!THE KITCHEN\n\nFlour everywhere.\n")
    assert not script.character_registry()
    assert script.elements[1].text == "THE KITCHEN"


def test_wrapped_parenthetical_stays_one_parenthetical():
    script = parse_text("INT. YARD - DAY\n\nWIDOW\n(getting on a cart\noutside)\nChalo.\n")
    kinds = [el.type for el in script.elements[1:]]
    assert kinds == [ElementType.CHARACTER, ElementType.PARENTHETICAL,
                     ElementType.PARENTHETICAL, ElementType.DIALOGUE]
    assert not [f for f in lint(script) if f.rule_id == "F028"]


def test_relatives_of_different_people_are_not_name_drift():
    """'BRIDE'S FATHER' and 'RICHA'S FATHER' are 87% alike and two actors."""
    script = parse_text("INT. HALL - DAY\n\nBRIDE'S FATHER\nOne.\n\nRICHA'S FATHER\nTwo.\n")
    assert not [f for f in lint(script) if f.rule_id == "C001"]


def test_one_character_spelled_two_ways_is_still_name_drift():
    script = parse_text("INT. HALL - DAY\n\nRICHA'S FATHER\nOne.\n\nRICHAS FATHER\nTwo.\n")
    assert [f for f in lint(script) if f.rule_id == "C001"]


def test_wall_of_text_counts_one_paragraph_not_a_whole_scene():
    """Separate beats are never a wall however many there are; one long one is.

    The threshold is 7 because 18,299 action paragraphs in produced
    screenplays put four lines at the 95th percentile: normal, not defective.
    """
    beats = "INT. BAR - DAY\n\n" + "\n\n".join("a\nb" for _ in range(6)) + "\n"
    wall = "INT. BAR - DAY\n\n" + "\n".join("line " + str(i) for i in range(9)) + "\n"
    assert not [f for f in lint(parse_text(beats)) if f.rule_id == "F004"]
    assert [f for f in lint(parse_text(wall)) if f.rule_id == "F004"]


# ============================================================ PDF ingestion
# pdfplumber is imported lazily, so the geometry can be tested without it.

def _row(text, x0, top, page=1, width=None):
    from sluglint.ingest.pdf import Line
    return Line(text, x0, x0 + (width if width is not None else len(text) * 6), top, page)


def test_geometry_classifies_by_indent_not_by_shape():
    from sluglint.ingest.pdf import _classify
    rows = {
        "heading": _row("INT. CAR - DAY", 108, 100),
        "action": _row("He waits.", 108, 120),
        "character": _row("PRASHANT", 252, 140),
        "parenthetical": _row("(beat)", 180, 160),
        "dialogue": _row("Ikkada right ah?", 180, 180),
    }
    for expected, row in rows.items():
        assert _classify(row, 108.0, 792.0, 540.0) == expected


def test_a_speaker_written_as_a_parenthetical_is_read_as_the_speaker():
    """At cue depth, '(VOICE ON THE PHONE)' is who is talking."""
    from sluglint.ingest.pdf import _classify
    assert _classify(_row("(VOICE ON THE PHONE)", 252, 140), 108.0, 792.0, 540.0) == "character"


def test_page_furniture_is_dropped():
    from sluglint.ingest.pdf import _classify
    assert _classify(_row("42.", 500, 30), 108.0, 792.0, 540.0) == "drop"
    assert _classify(_row("(MORE)", 180, 700), 108.0, 792.0, 540.0) == "drop"


def test_action_margin_is_the_leftmost_column_not_the_commonest():
    """Dialogue outnumbers action in plenty of scripts; the margin is still action's."""
    from sluglint.ingest.pdf import _action_margin
    rows = [_row("x", 108, i) for i in range(10)] + [_row("y", 180, i) for i in range(30)]
    assert _action_margin(rows) == 108.0


def test_legacy_indic_font_output_is_flagged_as_unreadable():
    from sluglint.ingest.pdf import text_confidence
    good = [_row("The WIDOW walks up to the room with an axe in one hand", 96, i)
            for i in range(20)]
    mojibake = [_row("lhfu;j jSfxax ^j.kNksM+nkl L;keynkl BIik yxk yks", 96, i)
                for i in range(20)]
    assert text_confidence(good) > 0.95
    assert text_confidence(mojibake) < 0.5


def test_split_speech_is_rejoined_across_a_page_break():
    from sluglint.ingest.pdf import _emit
    typed = [("character", _row("VIVEK", 252, 100, page=1)),
             ("dialogue", _row("Aagu.", 180, 120, page=1)),
             ("character", _row("VIVEK (CONT’D)", 252, 100, page=2)),
             ("dialogue", _row("Thini po.", 180, 120, page=2))]
    out, rejoined = _emit(typed)
    assert rejoined == 1
    assert out.count("VIVEK") == 1


def test_numbered_extras_are_not_name_drift():
    """'SENIOR 1' and 'SENIOR 2' are two actors, not one misspelled."""
    script = parse_text("INT. YARD - DAY\n\nSENIOR 1\nOne.\n\nSENIOR 2\nTwo.\n\nSENIOR\nThree.\n")
    assert not [f for f in lint(script) if f.rule_id == "C001"]


def test_a_capitalised_sound_is_not_an_unpaid_prop():
    action = ("INT. HOUSE - NIGHT\n\nHe yanks the chain and a MOAN comes from "
              "under the roots.\n")
    prop = "INT. HOUSE - NIGHT\n\nShe puts a LOCKET on the table and leaves.\n"
    assert not [f for f in lint(parse_text(action)) if f.rule_id == "C026"]
    assert [f for f in lint(parse_text(prop)) if f.rule_id == "C026"]


# ============================================================ Indic script names
# An abugida does not compare like an alphabet, and a code-mixed draft cues the
# same person in two writing systems.

TELUGU_KRISHNA = "కృష్ణ"        # KRISHNA, correctly spelled
TELUGU_KRISHNA_TYPO = "కృష్న"   # the same name, one wrong letter
TELUGU_RAJU = "రాజు"                 # RAJU, short final vowel
TELUGU_RAJU_LONG = "రాజూ"            # RAJU, long final vowel
DEVANAGARI_VINAYAK = "विनायक"

pytest.importorskip("indic_transliteration")


def test_fold_maps_a_name_to_one_comparison_key():
    from sluglint.indic import fold
    assert fold(TELUGU_KRISHNA) == "krishna" == fold("KRISHNA")
    assert fold(TELUGU_RAJU) == "raju" == fold(TELUGU_RAJU_LONG)
    assert fold(DEVANAGARI_VINAYAK) == "vinayak" == fold("VINAYAK")


def test_latin_text_is_not_disturbed_by_the_fold():
    from sluglint.indic import comparable
    assert comparable("CHITRA", "CHITRA'S AUNT") is None
    assert comparable("KARTHIK HOUSE", "KARTHIK'S HOUSE") is None


def test_vowel_length_typo_in_telugu_is_below_threshold_without_the_fold():
    """The regression this module exists for: 0.75 raw, so C001 missed it."""
    from difflib import SequenceMatcher

    from sluglint.lint.tier2_consistency import similar
    raw = SequenceMatcher(None, TELUGU_RAJU, TELUGU_RAJU_LONG).ratio()
    assert raw < 0.80
    assert similar(TELUGU_RAJU, TELUGU_RAJU_LONG) == 1.0


def test_the_same_character_cued_in_two_writing_systems_is_one_person():
    script = parse_text(
        f"INT. ROOM - DAY\n\n{TELUGU_KRISHNA} waits.\n\n{TELUGU_KRISHNA}\nOne.\n\n"
        f"INT. ROOM - NIGHT\n\nKRISHNA waits.\n\nKRISHNA\nTwo.\n")
    drift = [f for f in lint(script, "indian-regional") if f.rule_id == "C001"]
    assert drift, "a Telugu cue and its Latin spelling are one contract"
    assert "1.00" in drift[0].message


def test_two_different_telugu_names_are_left_alone():
    script = parse_text(
        f"INT. ROOM - DAY\n\n{TELUGU_KRISHNA} and {TELUGU_RAJU} argue.\n\n"
        f"{TELUGU_KRISHNA}\nOne.\n\n{TELUGU_RAJU}\nTwo.\n")
    assert not [f for f in lint(script, "indian-regional") if f.rule_id == "C001"]


def test_a_speech_line_starting_with_a_dot_is_not_a_forced_heading():
    script = parse_text("INT. BAR - DAY\n\nRAJU\nNenu vasthanu\n. Suddenga cheppanu\n")
    assert len(script.scenes) == 1
    assert not [f for f in lint(script) if f.rule_id == "F001"]


def test_a_forced_heading_still_works_after_a_blank_line():
    script = parse_text("INT. BAR - DAY\n\nHe drinks.\n\n.THE ROOFTOP\n\nRain.\n")
    assert [sc.heading for sc in script.scenes] == ["INT. BAR - DAY", "THE ROOFTOP"]


def test_two_places_sharing_a_long_suffix_are_not_one_set():
    script = parse_text(
        "INT. CHITRA'S HOUSE - THE NEXT DAY\n\nx\n\n"
        "EXT. CHITRA'S OFFICE - THE NEXT DAY\n\ny\n")
    assert not [f for f in lint(script) if f.rule_id == "C005"]


def test_one_place_spelled_two_ways_is_still_location_drift():
    script = parse_text("INT. FOOD TRUCK - DAY\n\nx\n\nINT. FOODTRUCK - NIGHT\n\ny\n")
    assert [f for f in lint(script) if f.rule_id == "C005"]


# ============================================================ metrics
# The stats layer reports numbers unconditionally. It must never carry a
# verdict, and every number has to be arithmetic a reader can redo by hand.

# Page count had no test, which is how it stayed a third low for so long: the
# parser drops blank lines, and the old estimate divided what was left by 55 as
# though they were still there. Measured against seven produced screenplays
# whose real page count is known, a page carries about 36.5 lines of text.

def test_printed_lines_wraps_to_the_column_it_prints_in():
    from sluglint.models import printed_lines
    assert printed_lines("", "action") == 0
    assert printed_lines("   ", "action") == 0
    assert printed_lines("short line", "action") == 1
    # Action runs the full six-inch measure, 60 characters.
    assert printed_lines("x" * 60, "action") == 1
    assert printed_lines("x" * 61, "action") == 2
    assert printed_lines("x" * 180, "action") == 3
    # Dialogue sits in a narrower column, so the same words take more lines.
    assert printed_lines("x" * 60, "dialogue") == 2
    assert printed_lines("x" * 60, "parenthetical") == 3


def test_a_real_page_count_wins_over_the_estimate():
    from sluglint.metrics import analyse
    script = parse_file(V1)
    loose = script.estimated_pages
    assert loose > 0
    script.page_count = 118
    assert script.estimated_pages == 118.0
    # The scenes still hold the estimate until they are told about the count.
    assert abs(sum(sc.estimated_pages for sc in script.scenes) - 118.0) > 0.5
    # Reconciling stretches them onto it, so every layer that reads a scene's
    # length reads the same number: the linter, the metrics, the dashboard.
    script.reconcile_pages()
    assert abs(sum(sc.estimated_pages for sc in script.scenes) - 118.0) < 0.5
    m = analyse(script)
    assert m.pages == 118.0
    assert abs(sum(sc.pages for sc in m.scenes) - 118.0) < 0.5


def test_scene_pages_sum_to_the_document_without_a_real_count():
    from sluglint.metrics import analyse
    m = analyse(parse_file(V1))
    assert abs(sum(sc.pages for sc in m.scenes) - m.pages) < 0.5


def test_a_scene_number_does_not_make_a_heading_overlong():
    """F013 measures the slugline, not the numbering a production added.

    A shooting script prints its scene number at both margins, which adds about
    ten characters to every heading. Measuring the raw string flagged 52% of
    numbered headings across 1,082 produced screenplays against 0.8% of
    unnumbered ones: identical writing, judged differently because somebody
    locked the script."""
    slug = "INT. THE UPSTAIRS APARTMENT KITCHEN - VERY EARLY MORNING"
    assert len(slug) <= 60
    plain = parse_text(f"{slug}\n\nShe fills the kettle.\n")
    assert not [f for f in lint(plain) if f.rule_id == "F013"]

    script = parse_text(f"148A {slug} 148A\n\nShe fills the kettle.\n")
    assert script.scenes[0].number == "148A"
    assert len(script.scenes[0].heading) > 60          # as printed, it is over
    assert not [f for f in lint(script) if f.rule_id == "F013"]


def test_a_wrapped_source_is_not_wrapped_twice():
    """A crawled text dump and a PDF row are already one printed line each.
    Re-wrapping those at a narrower standard column counts every line twice,
    which put a ScriptBase script at 188 pages instead of 138."""
    from sluglint.models import already_wrapped, printed_lines
    body = "\n\n".join("The room is quiet and nobody moves an inch at all here."
                       for _ in range(60))
    wrapped_src = parse_text(f"INT. ROOM - DAY\n\n{body}\n")
    assert already_wrapped(wrapped_src.elements) is True
    # 56 characters is under the 60-character action column either way, but a
    # source at 67 would double without the check.
    long_body = "\n\n".join("x" * 67 for _ in range(60))
    src = parse_text(f"INT. ROOM - DAY\n\n{long_body}\n")
    assert already_wrapped(src.elements) is True
    assert printed_lines("x" * 67, "action", True) == 1
    assert printed_lines("x" * 67, "action", False) == 2

    # A paragraph source is mostly short with a long tail, and must be wrapped.
    paras = "\n\n".join("word " * (16 if i % 5 else 90) for i in range(50))
    loose = parse_text(f"INT. ROOM - DAY\n\n{paras}\n")
    assert already_wrapped(loose.elements) is False
    # And the fixtures, which are the real thing rather than a construction.
    assert already_wrapped(parse_file(CLEAN).elements) is False


def test_every_scene_measures_pages_the_way_the_document_does():
    """One wrap decision per document, stamped onto every scene.

    `already_wrapped` needs forty action lines to tell a wrapped source from a
    paragraph source, and a single scene almost never has forty. Asking each
    scene for itself made scenes in a wrapped script measure up to 30% long,
    made two scenes in one document disagree, and skewed every rule that reads
    a scene's length (C023, C029, F047). The document decides once."""
    body = "\n\n".join("The room is quiet and nobody moves an inch at all here."
                       for _ in range(20))
    src = parse_text("".join(f"INT. ROOM {i} - DAY\n\n{body}\n\n" for i in range(4)))
    assert src.prewrapped is True
    assert all(sc.prewrapped is True for sc in src.scenes)
    # Scenes sum to the document, up to per-scene rounding.
    assert sum(sc.estimated_pages for sc in src.scenes) == pytest.approx(
        src.estimated_pages, abs=0.5)


def test_a_paragraph_on_one_source_line_still_costs_several_pages_lines():
    """Fountain holds a whole paragraph on one line; a PDF row is already one
    printed line. Both have to count the same way or the two inputs disagree."""
    from sluglint.models import printed_lines
    long_para = "The room is " + "very " * 60 + "quiet."      # 318 characters
    a = parse_text(f"INT. ROOM - DAY\n\n{long_para}\n")
    b = parse_text("INT. ROOM - DAY\n\nThe room is quiet.\n")
    assert printed_lines(long_para, "action") == 6
    def lines(sc):
        return sum(printed_lines(e.text, e.type) for e in sc.elements)
    assert lines(a) == 7 and lines(b) == 2
    assert a.estimated_pages > b.estimated_pages

def test_metrics_count_what_is_on_the_page():
    from sluglint.metrics import analyse
    m = analyse(parse_file(V1))
    assert m.scene_count == 7
    assert m.speaking_cast == len(parse_file(V1).character_registry())
    assert m.pages > 0 and m.runtime_minutes == m.pages
    assert sum(c.dialogue_lines for c in m.characters) == m.dialogue_lines


def test_character_presence_and_share_are_consistent():
    from sluglint.metrics import analyse
    m = analyse(parse_file(V1))
    assert m.characters == sorted(m.characters, key=lambda c: (-c.dialogue_lines, c.name))
    assert abs(sum(c.speaking_share for c in m.characters) - 1.0) < 0.01
    for c in m.characters:
        assert c.first_scene <= c.last_scene
        assert c.shoot_days_hint == len(c.scenes)


def test_eighths_render_the_way_a_strip_board_does():
    from sluglint.metrics import _fmt_eighths
    assert _fmt_eighths(0.625) == "5/8"
    assert _fmt_eighths(2.25) == "2 2/8"
    assert _fmt_eighths(3.0) == "3"


def test_company_moves_count_location_changes_in_scene_order():
    from sluglint.metrics import analyse
    same = analyse(parse_text("INT. BAR - DAY\n\nx\n\nINT. BAR - NIGHT\n\ny\n"))
    moved = analyse(parse_text("INT. BAR - DAY\n\nx\n\nINT. HALL - DAY\n\ny\n"))
    assert same.company_moves == 0 and moved.company_moves == 1


def test_day_and_night_pages_split_the_document():
    from sluglint.metrics import analyse
    m = analyse(parse_text("INT. BAR - DAY\n\nx\n\nINT. HALL - NIGHT\n\ny\nz\n"))
    assert m.day_pages > 0 and m.night_pages > 0
    assert 0.0 < m.night_share < 1.0


def test_genre_scoring_is_a_count_of_bands_not_a_verdict():
    from sluglint.metrics import analyse, score_genres
    m = analyse(parse_file(V1))
    matches = score_genres(m.signals, BOOK.genres)
    assert matches and all(0 <= g.matched <= g.total for g in matches)
    assert matches == sorted(matches, key=lambda g: (-g.score, -g.matched, g.name))
    # Every band that decided the score has to be inspectable.
    for g in matches:
        assert len(g.checks) == g.total
        assert all(c.verdict in {"within", "below", "above"} for c in g.checks)


def test_comparables_report_which_side_of_the_band_a_number_falls():
    from sluglint.metrics import analyse, compare
    m = analyse(parse_file(V1))
    checks = {c.signal: c for c in compare(m, BOOK.comparables["us-spec-feature"])}
    assert "pages" in checks
    # The fixture is a few pages long, far under a feature band.
    assert checks["pages"].verdict == "below" and not checks["pages"].inside


def test_stats_json_is_machine_readable():
    import json

    from sluglint.metrics import analyse, compare, score_genres
    from sluglint.report import stats_to_json
    m = analyse(parse_file(V1))
    payload = json.loads(stats_to_json(m, score_genres(m.signals, BOOK.genres),
                                       compare(m, BOOK.comparables["us-spec-feature"]),
                                       profile="us-spec-feature"))
    assert payload["profile"] == "us-spec-feature"
    assert payload["metrics"]["scene_count"] == 7
    assert {"key", "matched", "total", "checks"} <= set(payload["genres"][0])


def test_stats_command_prints_no_findings():
    from sluglint.cli import main
    assert main(["stats", str(V1)]) == 0


def test_dashboard_is_self_contained_and_leaks_no_script_text():
    """The dashboard is the artifact most likely to get shared."""
    from sluglint import dashboard
    from sluglint.metrics import analyse, compare, score_genres
    script = parse_file(V1)
    m = analyse(script)
    page = dashboard.render(m, score_genres(m.signals, BOOK.genres),
                            compare(m, BOOK.comparables["us-spec-feature"]),
                            profile="us-spec-feature")
    assert "<script" not in page.lower()          # no JS, so nothing to fetch
    assert "http://" not in page and "https://" not in page
    assert "prefers-color-scheme" in page and 'data-theme="dark"' in page
    # Dialogue must never reach the page; names and counts are the whole payload.
    spoken = {el.text for el in script.elements if el.type == ElementType.DIALOGUE}
    assert not [line for line in spoken if len(line) > 12 and line in page]
    assert "PRASHANT" not in page  # not in this fixture; guards the assertion above


def test_dashboard_survives_a_script_with_nothing_in_it():
    from sluglint import dashboard
    from sluglint.metrics import analyse
    page = dashboard.render(analyse(parse_text("")), [], [], profile="us-spec-feature")
    assert "Untitled script" in page


# ============================================================ character attributes

def test_age_is_read_as_the_band_the_script_wrote():
    from sluglint.characters import parse_age
    assert parse_age("30s")[1:] == (30, 39)
    assert parse_age("early 40s")[1:] == (40, 43)
    assert parse_age("mid-20s")[1:] == (24, 26)
    assert parse_age("late fifties")[1:] == (56, 59)
    assert parse_age("34")[1:] == (34, 34)
    assert parse_age("28-35")[1:] == (28, 35)
    assert parse_age("a mechanic") == ("", None, None)


def test_nothing_about_a_character_is_inferred_from_their_name():
    """The one boundary that matters here: names carry no facts."""
    from sluglint.characters import profiles
    text = ("INT. ROOM - DAY\n\nPRIYA sits. SANJAY stands.\n\n"
            "PRIYA\nOne.\n\nSANJAY\nTwo.\n")
    got = profiles(parse_text(text))
    assert got["PRIYA"].pronoun == "unspecified"
    assert got["SANJAY"].pronoun == "unspecified"
    assert got["PRIYA"].age_band == ""


def test_a_pronoun_is_only_read_from_unambiguous_sentences():
    from sluglint.characters import profiles
    lines = "\n\n".join(f"NADIA locks the door. She checks the street. Line {i}."
                        for i in range(6))
    text = f"INT. FLAT - NIGHT\n\n{lines}\n\nNADIA\nHome.\n"
    assert profiles(parse_text(text))["NADIA"].pronoun == "she"
    # Two people in one sentence: the pronoun could belong to either.
    crowded = ("INT. FLAT - NIGHT\n\nNADIA blocks his path with a mop.\n\n"
               "NADIA\nHome.\n\nOSCAR\nMove.\n")
    assert profiles(parse_text(crowded))["NADIA"].pronoun == "unspecified"


def test_role_and_age_come_out_of_the_same_parenthetical():
    from sluglint.characters import profiles
    text = "INT. SHOP - DAY\n\nRAJU (early 40s, a mechanic) wipes his hands.\n\nRAJU\nHi.\n"
    got = profiles(parse_text(text))["RAJU"]
    assert got.age_band == "40-43" and "mechanic" in got.role


# ============================================================ character network

NETWORK_TEXT = (
    "INT. A - DAY\n\nANA\n1.\n\nBEN\n2.\n\n"
    "INT. B - DAY\n\nBEN\n3.\n\nCAL\n4.\n\n"
    "INT. C - DAY\n\nDEV\n5.\n\nEVE\n6.\n"
)


def test_two_people_in_a_scene_are_one_edge():
    from sluglint import network
    g = network.build(parse_text(NETWORK_TEXT))
    pairs = {(e.a, e.b) for e in g.edges}
    assert pairs == {("ANA", "BEN"), ("BEN", "CAL"), ("DEV", "EVE")}


def test_a_cast_that_never_meets_is_two_components():
    from sluglint import network
    g = network.build(parse_text(NETWORK_TEXT))
    assert sorted(len(c) for c in g.components) == [2, 3]


def test_the_only_link_between_two_groups_is_a_cut_vertex():
    from sluglint import network
    g = network.build(parse_text(NETWORK_TEXT))
    # BEN alone joins ANA to CAL. DEV and EVE hold each other up and neither is
    # load bearing, which is the distinction the check exists to make.
    assert g.cut_vertices == ["BEN"]


def test_a_solo_speaker_is_isolated_rather_than_a_cut_vertex():
    from sluglint import network
    g = network.build(parse_text("INT. A - DAY\n\nANA\n1.\n\nINT. B - DAY\n\nBEN\n2.\n"))
    assert g.isolated == ["ANA", "BEN"] and g.cut_vertices == []


# ============================================================ per-character timeline

def test_a_character_timeline_collapses_consecutive_scenes():
    from sluglint.metrics import analyse
    text = "".join(f"INT. S{i} - DAY\n\nANA\nHi.\n\n" if i in (0, 1, 2, 5)
                   else f"INT. S{i} - DAY\n\nBEN\nHi.\n\n" for i in range(7))
    ana = next(c for c in analyse(parse_text(text)).characters if c.name == "ANA")
    assert ana.timeline == "1-3, 6"
    assert ana.page_first < ana.page_last


def test_scene_page_positions_run_end_to_end():
    from sluglint.metrics import analyse
    m = analyse(parse_file(V1))
    assert m.scenes[0].page_start == 0.0
    for prev, cur in zip(m.scenes, m.scenes[1:]):
        assert cur.page_start == prev.page_end
    assert abs(m.scenes[-1].page_end - m.pages) < 0.1


def test_a_character_cued_without_an_extension_is_not_voice_only():
    from sluglint.metrics import analyse
    m = analyse(parse_text("INT. A - DAY\n\nANA\nHi.\n\nBEN (V.O.)\nHello.\n"))
    by_name = {c.name: c for c in m.characters}
    assert not by_name["ANA"].voice_only and by_name["BEN"].voice_only


# ============================================================ project config

def test_config_disables_regrades_and_retunes(tmp_path):
    from sluglint import config
    (tmp_path / ".sluglint.yaml").write_text(
        "profile: tv-pilot\ndisable: [F013]\nseverity: {F062: error}\n"
        "params: {F002: {min_pages: 3}}\nmin_severity: warning\n", encoding="utf-8")
    cfg = config.discover(tmp_path)
    assert cfg.profile == "tv-pilot"
    book = cfg.apply(BOOK)
    ids = {r.id for r in book.rules}
    assert "F013" not in ids and "F062" in ids
    assert next(r for r in book.rules if r.id == "F062").severity == "error"
    assert next(r for r in book.rules if r.id == "F002").params["min_pages"] == 3
    kept = cfg.filter([Finding("X", "x", Severity.SUGGESTION, "m"),
                       Finding("Y", "y", Severity.ERROR, "m")])
    assert [f.rule_id for f in kept] == ["Y"]


def test_config_only_list_is_an_allow_list(tmp_path):
    from sluglint import config
    (tmp_path / ".sluglint.yaml").write_text("only: [F001, C031]\n", encoding="utf-8")
    book = config.discover(tmp_path).apply(BOOK)
    assert {r.id for r in book.rules} == {"F001", "C031"}


def test_config_rejects_a_key_it_does_not_understand(tmp_path):
    from sluglint import config
    (tmp_path / ".sluglint.yaml").write_text("disabled: [F001]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config keys"):
        config.discover(tmp_path)


def test_no_config_anywhere_is_not_an_error(tmp_path):
    from sluglint import config
    assert config.discover(tmp_path).is_empty or config.discover(tmp_path).path is not None


def test_a_house_rulebook_extends_the_shipped_one(tmp_path):
    """The point of `extends`: eleven lines, not a 1500-line fork."""
    from sluglint.rulebook import load_rulebook
    (tmp_path / "house.yaml").write_text(
        "extends: default\nrules:\n"
        "  - id: F013\n    severity: error\n"
        "  - id: H001\n    name: House rule\n    tier: 1\n    category: format\n"
        "    severity: warning\n    detect: slugline_prefix\n"
        "    principle: A house convention.\n    source: HouseStyle\n", encoding="utf-8")
    book = load_rulebook(tmp_path / "house.yaml")
    by_id = {r.id: r for r in book.rules}
    assert len(book.rules) == len(BOOK.rules) + 1
    assert by_id["F013"].severity == "error"        # patched in place
    assert by_id["F013"].principle                  # and kept everything else
    assert by_id["H001"].name == "House rule"       # and added a new one
    assert book.profiles and book.genres            # inherited wholesale


# ============================================================ generated summaries

def test_the_logline_surface_never_produces_findings():
    """Model output is fenced out of the linter by construction.

    Not a stylistic preference. A Finding is a claim that something on the page
    is wrong, and every one of them has to be checkable against the page. This
    module cannot make that promise, so it is not allowed to make Findings.
    """
    import sluglint.logline as mod
    assert "Finding" not in dir(mod) and "detector" not in dir(mod)
    assert not any(mod.__name__ in str(v) for v in registered_keys())
    summary = mod.Summary(title="T", model="m", script_hash="h", synopsis="s")
    assert summary.generated and "language model" in summary.to_dict()["disclaimer"]


def test_the_logline_cache_is_keyed_on_the_script_and_the_model(tmp_path, monkeypatch):
    from sluglint import logline
    monkeypatch.setattr(logline, "CACHE_DIR", tmp_path)
    one, two = parse_text("INT. A - DAY\n\nx\n"), parse_text("INT. B - DAY\n\ny\n")
    assert logline.cache_path(one, "m", 3) != logline.cache_path(two, "m", 3)
    assert logline.cache_path(one, "m", 3) != logline.cache_path(one, "m", 5)
    assert logline.load_cached(one, "m", 3) is None


def test_logline_reports_a_missing_key_instead_of_crashing(monkeypatch):
    from sluglint import logline
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(logline, "load_cached", lambda *a, **k: None)
    summary, notices = logline.generate(parse_file(V1))
    assert summary is None and any("ANTHROPIC_API_KEY" in n for n in notices)


# ============================================================ tier 3 plumbing

def test_tier3_reports_a_missing_key_for_whichever_provider_is_configured(monkeypatch):
    from sluglint.lint import tier3_llm
    rules = [r for r in load_rulebook().rules if r.tier == 3][:2]
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SLUGLINT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SLUGLINT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    findings, notices = tier3_llm.run(parse_file(V1), rules)
    assert findings == [] and any("ANTHROPIC_API_KEY" in n for n in notices)

    # Pointed at an OpenAI-compatible endpoint, it asks for that key instead.
    monkeypatch.setenv("SLUGLINT_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    findings, notices = tier3_llm.run(parse_file(V1), rules)
    assert findings == [] and any("SLUGLINT_LLM_API_KEY" in n for n in notices)


def test_tier3_filters_are_counted_so_their_drop_rate_is_measurable(monkeypatch):
    """Each judged item is attributed to exactly one filter, so the columns sum.

    The filters are the part of tier 3 worth defending and there was no number
    behind them until this existed."""
    from sluglint.lint import tier3_llm
    rules = [r for r in load_rulebook().rules if r.tier == 3][:1]
    rule_id = rules[0].id
    # One chunk, so every proposal meets the same window and each rejection is
    # attributable to one filter without arithmetic.
    script = parse_text("INT. BAR - NIGHT\n\nA man waits by the window.\n")
    assert len(list(tier3_llm._chunks(script))) == 1
    quotable = "A man waits by the window."

    proposals = [
        {"rule_id": "NOPE", "scene_index": 0, "evidence": "", "message": "m",
         "suggestion": "s", "confidence": 0.9},                    # unknown rule
        {"rule_id": rule_id, "scene_index": 9999, "evidence": "", "message": "m",
         "suggestion": "s", "confidence": 0.9},                    # out of window
        {"rule_id": rule_id, "scene_index": 0, "evidence": "", "message": "m",
         "suggestion": "s", "confidence": 0.1},                    # low confidence
        {"rule_id": rule_id, "scene_index": 0, "evidence": "never in the script",
         "message": "m", "suggestion": "s", "confidence": 0.9},    # not quotable
        {"rule_id": rule_id, "scene_index": 0, "evidence": quotable,
         "message": "m", "suggestion": "s", "confidence": 0.9},    # survives
    ]
    monkeypatch.setenv("SLUGLINT_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("SLUGLINT_LLM_API_KEY", "test")
    monkeypatch.setattr(tier3_llm, "_openai_compatible",
                        lambda *a, **k: json.dumps({"findings": proposals}))

    stats = tier3_llm.FilterStats()
    findings, notices = tier3_llm.run(script, rules, stats=stats)

    assert stats.calls == 1 and stats.failed_calls == 0
    assert stats.proposed == 5
    assert stats.accepted == len(findings) == 1
    assert stats.dropped_unknown_rule == 1
    assert stats.dropped_out_of_window == 1
    assert stats.dropped_low_confidence == 1
    assert stats.dropped_unquotable == 1
    # The columns account for every proposal, which is what makes the drop
    # rate a measurement rather than an impression.
    assert (stats.dropped_unknown_rule + stats.dropped_out_of_window
            + stats.dropped_low_confidence + stats.dropped_unquotable
            + stats.accepted) == stats.proposed
    assert any("dropped" in n for n in notices)


def test_a_dead_provider_leaves_tiers_1_and_2_usable(monkeypatch):
    from sluglint.lint import tier3_llm
    rules = [r for r in load_rulebook().rules if r.tier == 3][:1]
    monkeypatch.setenv("SLUGLINT_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("SLUGLINT_LLM_API_KEY", "test")

    def boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(tier3_llm, "_openai_compatible", boom)
    findings, notices = tier3_llm.run(parse_file(V1), rules)
    assert findings == []
    assert any("no route to host" in n for n in notices)


def test_the_throttle_paces_calls_to_a_requests_per_minute_budget():
    from sluglint.lint import tier3_llm
    assert tier3_llm._Throttle(0).gap == 0.0          # unset is a no-op
    assert tier3_llm._Throttle(30).gap == pytest.approx(2.0)


# ============================================================ the network on the page

def test_the_network_graph_reaches_the_dashboard():
    from sluglint import dashboard
    from sluglint.metrics import analyse
    m = analyse(parse_text(NETWORK_TEXT))
    page = dashboard.render(m, [], [], profile="us-spec-feature")
    assert "Who plays against whom" in page
    assert "<svg" in page and "<script" not in page.lower()
    # The graph seats characters deterministically, so two runs are comparable.
    assert page == dashboard.render(analyse(parse_text(NETWORK_TEXT)), [], [],
                                    profile="us-spec-feature")


def test_the_cast_table_says_what_the_page_does_not_know():
    from sluglint import dashboard
    from sluglint.metrics import analyse
    page = dashboard.render(analyse(parse_text(NETWORK_TEXT)), [], [],
                            profile="us-spec-feature")
    assert "never guessed from a name" in page
