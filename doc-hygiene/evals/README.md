# Evals for `doc-hygiene`

Test cases for the `doc-hygiene` skill. Each eval is a realistic user prompt paired with a small fixture project and expectations describing what a good response should contain. All three run offline.

## Layout

```
evals/
├── evals.json
└── files/
    ├── duplicated-docs/    # CLAUDE.md restating the README, plus a terraform-docs block
    ├── undocumented-cli/   # code gained a flag and an env var the README doesn't mention
    └── new-project/        # a small CLI with no docs at all
```

> **Fixture naming:** `dot-CLAUDE.md` stands in for `CLAUDE.md`. A real `CLAUDE.md` inside a
> fixture gets picked up as agent context for this repo itself. When running an eval, treat
> `dot-CLAUDE.md` as `CLAUDE.md`; the prompts refer to the real name.

`files` entries in `evals.json` name whole fixture directories, relative to the skill root.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `dedupe-claude-md-against-readme` | Deduplication direction: agent doc references, README stays canonical |
| 2 | `drift-check-after-code-change` | The drift check finds what changed and answers explicitly |
| 3 | `create-docs-with-clean-split` | Creating both docs with the split right and no slop |

## What each case is really guarding

**Eval 1** is the taxonomy applied under pressure: the duplicated content must leave CLAUDE.md (not the README), the agent-only Conventions section must survive, and the generated terraform-docs region must come through byte-identical — the eval's sharpest expectation, because "cleaning up" a generated block is exactly the mistake the skill exists to prevent.

**Eval 2** tests the drift check as a question, not an instruction. The right response identifies both undocumented additions (`--dry-run`, `SITECHECK_TOKEN`), fixes the README, and states explicitly what was updated — silence, or a silent edit, is a failure. It also checks nothing gets invented: no CLAUDE.md appears for what is human-facing usage documentation.

**Eval 3** is the from-scratch case, and most of its expectations are negative: no banned trope vocabulary, no exclamation marks, no contribution-guide boilerplate, no claims about behaviour the code doesn't implement. Accuracy expectations (the `--check` exit-code behaviour, the required tag keys) keep the docs honest against the code.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the expectations in `evals.json`. Copy each fixture directory into a scratch working directory first (restoring `CLAUDE.md` from `dot-CLAUDE.md`) so runs don't modify the fixtures.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

## Expectation conventions

Expectations are plain-English statements about the response. They split into:

- **Positive coverage** — "identifies that `--dry-run` is missing" — the response should find or produce a specific thing.
- **Negative / no-false-positive** — "no banned trope vocabulary", "the generated region is byte-identical" — the response should leave the right things alone.
- **Format** — "headings use Title Case", "states which files were updated" — about the shape of the output.

Eval 3 is mostly negative by design: the skill's value in greenfield writing is what it keeps out.
