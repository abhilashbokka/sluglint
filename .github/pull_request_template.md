<!-- Sluglint PR template. Delete sections that don't apply. -->

## What this changes

<!-- One or two sentences. -->

## Rulebook changes

- [ ] No rules added, removed, or retuned
- [ ] Rules added/changed — every one below is filled in:

| Rule id | Tier | Severity | New / changed | Profiles |
|---|---|---|---|---|
|  |  |  |  |  |

For each **new** rule:

- [ ] `principle:` is an original formulation — **no text reproduced from a screenwriting book**
- [ ] `source:` attributes where the underlying convention is taught
- [ ] Tier 1/2 only: a `detect:` key with a registered handler (`sluglint rules --check` passes)
- [ ] Tier 1/2 only: a positive fixture in `SNIPPETS` / `PROFILE_SNIPPETS` so the rule provably fires
- [ ] Tier 3 only: at least one few-shot `bad`/`good` pair
- [ ] `examples/clean_pages.fountain` still produces zero errors and zero warnings

## Checks

- [ ] `pytest -q` green
- [ ] `ruff check .` and `pylint src/sluglint` clean
- [ ] README badges still truthful (rule count, test count)
- [ ] No API keys, tokens, or personal data added anywhere — including fixtures

## Scope boundary

Sluglint checks the screenplay **as a document**: formatting, internal
consistency, and craft rules about how scenes and lines are written. It does
not evaluate plot logic, premise, theme, or whether the story is good.

- [ ] This change stays inside that boundary
