# Contributing to Sluglint

The product is `src/sluglint/rulebook.yaml`. Most contributions are rules
rather than code.

## Licence for contributions

Sluglint is under [PolyForm Noncommercial 1.0.0](LICENSE), and commercial
licences are sold separately (see [COMMERCIAL.md](COMMERCIAL.md)). By opening a
pull request you agree your contribution can be included under that licence and
under commercial licences granted by the maintainer. If that does not work for
you, open an issue and we will find another way.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev,pdf,llm,indic]"

# or the minimum, if you are only touching tiers 1 and 2:
#   pip install -e ".[dev]"      add ,pdf to read PDFs, ,llm for the tier-3 judge

pytest -q                    # 153 tests
ruff check . && pylint src/sluglint
python benchmark/run.py      # regenerates benchmark/REPORT.md
```

## Branching

`main` is protected and always releasable. `develop` is the integration branch.

```
main ──────────────●──────────────●   tagged releases
                  ╱              ╱
develop ──●──●───●──────●──●────●     integration
          ╱      ╱       ╱     ╱
  feat/rule-c028   fix/f014-dash      short-lived branches
```

Branch from `develop`, open a PR back into `develop`. Release PRs go
`develop → main`. Branch names: `feat/…`, `fix/…`, `rule/…`, `docs/…`.

## Adding a rule

**Tier 3 (LLM-judged) needs zero Python.** Add the rule to `src/sluglint/rulebook.yaml`
with a `principle`, a `source`, and one or two `examples`, the judge builds its
rubric from the YAML.

**Tier 1 and 2 need a handler.** Add a `detect:` key to the rule, then register
a generator for it:

```python
@detector("my_new_check")
def my_new_check(script: Script, rule: Rule):
    limit = int(rule.params.get("max_thing", 3))   # read thresholds from the rule
    for sc in script.scenes:
        if ...:
            yield finding(rule, f"...{limit}...", line_no=sc.line_no,
                          scene_index=sc.index, evidence=sc.heading,
                          suggestion="...")
```

Then add a positive fixture to `SNIPPETS` in `tests/test_sluglint.py`. A rule
with no fixture fails `test_snippet_coverage_is_complete`, a rule that cannot
be made to fire is decoration.

## The rules that are not negotiable

1. **Never reproduce text from screenwriting books.** `principle:` fields are
   original formulations. `source:` attributes where the idea is taught. Quoted
   book content is a copyright problem and will be rejected.
2. **Precision over recall.** A linter that cries wolf gets uninstalled. Every
   new tier-1/2 rule must leave `examples/clean_pages.fountain` at zero errors
   and zero warnings. Prefer a narrow check that anchors on a second signal (an
   age parenthetical, an article before a capitalised prop, a known cue name)
   over a broad one that flags every capitalised word.

   If your rule can be fault-injected, add a mutator to `benchmark/mutate.py`.
   That turns "I think it works" into a recall number.
3. **Rules are data.** Thresholds live in `params:`, never as constants in
   Python. Severity, name, and principle live in the YAML.
4. **Scope boundary.** Sluglint checks the screenplay as a *document*. It does
   not judge plot logic, premise, theme, or story quality. Rules that need that
   judgement do not belong here, whatever their severity.

## Fingerprint stability

`Finding.fingerprint` deliberately excludes line numbers so a note survives text
moving to another page. Script-level metric findings must use a **fixed**
evidence string, counts go in `message`, never in `evidence`, or every re-lint
looks like a brand new finding and the draft diff churns.
`test_metric_findings_keep_a_stable_fingerprint` guards this.

## Profiles

A rule with no `profiles:` key applies to every profile. A rule that lists them
applies only to those. This is how one rulebook holds both "scene numbers are an
amateur tell" (spec) and "scene numbers are mandatory" (shooting script) without
either becoming a special case in code.

## House style

- **No em dashes.** Anywhere. Use a comma, a colon, or a full stop.
- **Avoid the "X, not Y" construction.** Say what the thing is.
- **Python source stays ASCII.** Typographic characters the linter hunts for are
  written as `\uXXXX` escapes, so the rule can find them without the source
  containing them.

## Security

No API keys, tokens, or personal data in code, fixtures, or git history, ever.
Configuration is via environment variables only (`ANTHROPIC_API_KEY`,
`SLUGLINT_MODEL`).

**Never commit a third-party screenplay.** Almost none can legally be
redistributed, however public the page you found it on.
`benchmark/corpus/*.fountain` and `*.txt` are gitignored to stop it happening by
accident. The reasoning is in
[docs/public-domain-scripts.md](docs/public-domain-scripts.md).
