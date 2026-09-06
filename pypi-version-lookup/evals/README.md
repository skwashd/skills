# Evals for `pypi-version-lookup`

Test cases for the `pypi-version-lookup` skill. Each eval is a realistic user prompt paired with input files (where applicable) and expectations describing what a good response should contain.

## Layout

```
evals/
└── files/
    └── pin-requirements/    # unpinned requirements.txt with comments and one range constraint
```

Most cases here need no fixtures — this skill's job is to reach out to a live API, so the interesting failures are about *how* it queries, not what it was handed.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `single-package-lookup` | Actually queries PyPI instead of answering from memory |
| 2 | `pin-a-requirements-file` | Batching, comment preservation, existing constraints |
| 3 | `pipeline-exit-status-trap` | Diagnoses the `$?`-after-pipeline bug correctly |
| 4 | `fresh-release-cooldown` | Uses `upload_time_iso_8601`, not the naive field |
| 5 | `quarantined-and-yanked` | PEP 792 project status; precise yanked semantics |

## What each case is really guarding

**Eval 1's `Actually queries PyPI` expectation is the whole reason this skill exists.** A model asked "what's the latest version of httpx" will happily produce a confident, plausible, wrong answer from training data. Everything else in the skill is downstream of establishing that this is a question you look up, not one you remember.

**Eval 3 is a self-test on the skill's own history.** The bug in the prompt is the one that shipped in v1 of this skill: `$?` after a pipeline reads jq's status, not curl's, so a 404 comes back looking like success. The `Does not just add a -n guard` expectation is there because the obvious patch — check the string is non-empty — makes the symptom go away while leaving the wrong idiom in place to be copied into the next script.

**Eval 4** targets the other v1 bug. `upload_time` and `upload_time_iso_8601` look interchangeable; only the second carries an offset. Parsing the first as local time shifts the computed age by the local UTC offset, which in Australia is enough to let a 14-hour-old release pass a 24-hour check. A response that reaches for `upload_time` has reproduced the original defect.

**Eval 5** checks currency in both directions: it should know about PEP 792 project status (new), and it should *not* reach for `.releases` (deprecated). The precise-yanked-semantics expectation allows a partial pass for a vague answer, because "it might return a yanked version" is not wrong — just much less useful than knowing it happens only when the whole project has been yanked.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the expectations in `evals.json`.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

**These evals need network access.** Evals 1, 2 and 5 make live PyPI requests, so results will vary with whatever is current — that is intentional. Grade on whether the version was looked up and reported faithfully, not on a fixed expected string.

## Expectation conventions

Expectations are plain-English statements about the response. They split into:

- **Positive coverage** — "uses `upload_time_iso_8601`" — the response should do a specific thing.
- **Hard failures** — "actually queries PyPI" — answering from memory gets no partial credit.
- **Anti-patterns** — "does not just add a -n guard", "does not recommend the deprecated releases key" — the response should avoid a specific plausible-but-wrong move.
