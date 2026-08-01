"""Behaviour tests. Run: PYTHONPATH=src pytest -q

Structure mirrors the project's core claim — that a linter's accuracy can be
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
from dataclasses import replace
from pathlib import Path

import pytest

from sluglint.diff import diff_drafts, diff_findings
from sluglint.lint import registered_keys, run_rules, unimplemented
from sluglint.models import ElementType, Finding, Severity
from sluglint.parser import normalize_character, parse_file, parse_text, split_scene_number
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

def test_rulebook_is_101_rules():
    assert len(BOOK.rules) == 101


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
    ("F027", "INT. BAR - DAY\n\nHe says “no” and leaves.\n", {}),
    ("F028", "INT. BAR - DAY\n\nHe opens the door (and stops.\n", {}),
    ("F029", "INT. BAR - DAY\n\nHe drinks.\n", {"min_pages": 0}),
    ("F030", "INT. BAR - DAY\n\nHe drinks.\n", {"min_pages": 0}),
    ("F031", "INT. BAR - DAY\n\nHe drinks.\n\nSLOWLY FADE INTO:\n\nEXT. STREET - DAY\n\nRain.\n", {}),
    # --- tier 1: metrics and style
    ("F004", "INT. BAR - DAY\n\none\ntwo\nthree\nfour\nfive\n", {}),
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
     "EXT. RIVER - DAY\n\nRAJU (30s) rows.\n\nRAJU\nHi.\n\nరాజు\nHi again.\n", {}),
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
