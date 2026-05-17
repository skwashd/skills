# Evals for `terraform-review`

Test cases for the `terraform-review` skill. Each eval is a realistic user prompt paired with input `.tf` files (where applicable) and assertions describing what a good response should contain.

## Layout

```
evals/
├── evals.json
└── inputs/
    ├── dirty-module/           # Multi-file Lambda module with many anti-patterns
    ├── clean-module/           # Well-written S3 module — used to test for false positives
    └── architectural-issues/   # Style is clean, design is wrong (vpc_id var, inline SG rules, SSH from 0.0.0.0/0)
```

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `dirty-lambda-module-review` | Coverage across many rule categories; severity grouping; tflint rule citations |
| 2 | `clean-module-no-false-positives` | Skill does not fabricate issues on already-good code |
| 3 | `greenfield-lambda-module` | Proactive application of guidance when writing from scratch |
| 4 | `architectural-issues-not-just-style` | Catches structural and security issues, not just cosmetic ones |

## How to run

In Claude Code (per skill-creator standards) you'd spawn one subagent per eval with the skill loaded, then a baseline subagent without, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the assertions in `evals.json`. See `/mnt/skills/examples/skill-creator/SKILL.md` for the full loop.

For an informal pass without subagents, just run each prompt in a fresh chat with the skill in scope and compare the output against the assertions by hand.

## Assertion conventions

Assertions are plain-English statements about the response. They split into:

- **Positive coverage** — "flags X" — the response should call out a specific issue.
- **Negative / no-false-positive** — "does NOT flag Y" — the response should leave clean things alone.
- **Format** — "groups by severity", "cites tflint rule names" — about the shape of the response.

Most assertions in the dirty-module case (eval 1) are positive coverage; the clean-module case (eval 2) is mostly negatives. The greenfield case (eval 3) checks generated code against the skill's guidance directly.
