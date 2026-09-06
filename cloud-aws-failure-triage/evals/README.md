# Evals for `aws-failure-triage`

Test cases for the `aws-failure-triage` skill. Each eval is a realistic user prompt — usually a pasted AWS error — paired with input files (where applicable) and expectations describing what a good response should contain. All three run offline: no AWS credentials are needed, and the evidence-gathering expectations are about which commands the response *proposes*.

## Layout

```
evals/
├── evals.json
└── files/
    ├── ssm-access-denied/  # Terraform IAM role missing an SSM action, two-ARN-form trap
    └── event-mismatch/     # EventBridge rule pattern that doesn't match the captured event
```

`files` entries in `evals.json` name whole fixture directories, relative to the skill root. Eval 2 has no files — the pasted error is the entire input. Account IDs in the fixtures are the AWS documentation placeholder `123456789012`.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `ssm-access-denied-minimal-fix` | Least-privilege fix; the SSM two-ARN-form requirement |
| 2 | `cert-in-use-evidence-before-action` | Read-only evidence first; stateful resources protected |
| 3 | `eventbridge-pattern-mismatch` | Both pattern mismatches found; fix in code; offline verification |

## What each case is really guarding

**Eval 1** is least privilege under time pressure. The error names the exact action and resource, and the tempting fix is a wildcard. The pass requires the specific action against *both* SSM resource forms (the bare path and the `/*` wildcard) — granting only one still yields AccessDenied, which is the trap the skill's IAM reference documents — with everything else in the policy untouched.

**Eval 2** is the discipline test: no fixture, no credentials, a stuck `DELETE_FAILED`, and a user worried about their Cognito user pool. The pass is a plan that leads with read-only commands (`acm describe-certificate --query 'Certificate.InUseBy'`), protects the user pool with a retain policy before any further destructive step, and never proposes force-deleting the stack. This is the eval most worth reading by hand — the ordering of the plan is the point.

**Eval 3** hides two mismatches in one rule: a `detail-type` case difference and a `resource_type`/`resourceType` key difference. Finding only the obvious one is the expected failure mode. The fix must land in the Terraform/producer code, not the console, and the response should reach for `aws events test-event-pattern` — verification that works with no live bus.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the expectations in `evals.json`. Copy each fixture directory into a scratch working directory first so runs don't modify the fixtures.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the expectations by hand.

## Expectation conventions

Expectations are plain-English statements about the response. They split into:

- **Positive coverage** — "identifies the detail-type mismatch", "grants both resource forms" — the response should find or fix a specific thing.
- **Negative / no-false-positive** — "no statement uses `*`", "no step proposes deleting the stack" — the response should refuse the tempting shortcut.
- **Process** — "provides the read-only command before proposing any change" — about the order of operations, which for this skill is most of the value.

Eval 2 is almost entirely process expectations by design.
