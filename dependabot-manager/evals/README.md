# Evals for `dependabot-manager`

Test cases for the `dependabot-manager` skill. Each eval is a realistic user prompt paired with input files (where applicable) and expectations describing what a good response should contain.

## Layout

```
evals/
├── evals.json
└── files/
    ├── polyglot-repo/      # npm + uv + docker + terraform + actions, and nothing else
    ├── drifted-config/     # existing config with every rule violated at least once
    └── compliant-config/   # already-good config with a stricter-than-required cooldown
```

> **Fixture naming:** inside each fixture, `dot-github/` stands in for `.github/`. Storing a real
> `.github/` directory inside test fixtures causes trouble — tooling picks the files up as if they
> were this repo's own workflow and Dependabot config, and some editors and sync tools refuse to
> write them. When running an eval, treat `dot-github/workflows/ci.yml` as
> `.github/workflows/ci.yml`; the skill's detection logic keys off that path, so the mapping
> matters for eval 1's `Detects github-actions` expectation.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `greenfield-detection` | Ecosystem detection from manifests; **emits only what's in use** |
| 2 | `update-drifted-config` | Fixing violations; removing `reviewers`; preserving user additions |
| 3 | `compliant-config-no-false-positives` | Doesn't lower a stricter cooldown or strip user config |
| 4 | `new-ecosystem-lookup` | Reference table currency (`deno`, `sbt`) |
| 5 | `cooldown-rationale` | Explains the daily + cooldown interaction correctly |

## What each case is really guarding

**Eval 1** is the regression test for the biggest behaviour change in v2 of this skill. Earlier versions emitted an entry for every ecosystem GitHub supports, commenting out the unused ones — roughly 300 lines of mostly-dead YAML in every repo. The expectation `Does NOT emit unused ecosystems` fails the old behaviour deliberately.

**Eval 2** is the only case where the skill *deletes* something the user wrote. `reviewers` was removed by GitHub in August 2025, so preserving it — which the general "preserve user config" rule would otherwise imply — leaves dead configuration behind. The eval checks both that it goes and that the user is told why.

**Eval 3** guards the opposite failure: a skill that normalises everything to its stated minimum. `default-days: 3` is a floor. A config at 7 days is better than the house standard and must survive contact with the skill unchanged.

**Eval 4** has no input files by design — it tests only whether the ecosystem reference table is current. `deno`, `nix` and `sbt` were all added to Dependabot in the first half of 2026. If this eval starts failing, the table has gone stale again.

**Eval 5** tests reasoning rather than output. The daily-schedule rule looks wrong to anyone who assumes a cooldown batches updates, and the skill needs to be able to defend it.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the expectations in `evals.json`.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

## Expectation conventions

Expectations are plain-English statements about the response. They split into:

- **Positive coverage** — "detects X", "removes Y" — the response should do a specific thing.
- **Negative / no-false-positive** — "does NOT lower the 7-day cooldown" — the response should leave correct things alone.
- **Format** — "valid YAML", "summarises every change" — about the shape of the response.

Evals 1 and 2 are mostly positive coverage; eval 3 is entirely negative.
