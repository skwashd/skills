# Evals for `github-actions-security`

Test cases for the `github-actions-security` skill. Each eval is a realistic user prompt paired with input workflow files (where applicable) and assertions describing what a good response should contain.

## Layout

```
evals/
├── evals.json
└── inputs/
    ├── vulnerable-workflow/   # pull_request_target + fork-head checkout, and much else
    ├── stale-pins/            # correct in every respect except an out-of-date checkout pin
    └── hardened-workflow/     # compliant release pipeline — used to test for false positives
```

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `pwn-request-workflow-review` | Broad coverage; correctly ranks the pwn request as the critical finding |
| 2 | `stale-checkout-pin` | The subtle case: a *correct* pin that is nonetheless too old |
| 3 | `hardened-release-no-false-positives` | Doesn't invent findings on compliant code |
| 4 | `scaffold-zizmor-workflow` | Generated workflow matches the skill's own rules |
| 5 | `cooldown-alignment` | zizmor config path and threshold reasoning |

## What each case is really guarding

**Eval 2 is the important one.** Every other eval tests something a careful reader would catch. This one tests whether the skill knows that `actions/checkout@de0fac2e…` — a genuine, correctly-formatted, properly-commented SHA pin of a real release — is nonetheless a finding, because v6.0.2 predates the July 2026 pwn-request protections. It is the case where following the skill's own advice (pin everything) produces the vulnerability, and the skill has to be self-aware enough to say so.

**Eval 1** deliberately stacks eight or nine violations into one file. The assertion that matters most is `flags pull_request_target as critical` — a review that lists all nine findings as equals, or leads with `ubuntu-latest`, has failed at prioritisation even if coverage is complete.

**Eval 3** guards the opposite failure. `id-token: write` looks alarming to a naive reviewer; it is correct here, and flagging it as an over-broad permission is a false positive.

**Eval 4** is a regression test for a real inconsistency: the skill's text said to use a `.github/**` path trigger while its bundled example used `.github/workflows/**`. If a generated workflow comes back with the narrower filter, the example and the prose have drifted apart again.

**The `does not fabricate SHAs` assertions appear in two evals** and are hard failures rather than partial credit. A plausible-looking but invented commit hash is worse than no pin at all: it fails closed at runtime if you are lucky, and pins to an attacker-chosen commit if you are not.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it, save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the assertions in `evals.json`.

For an informal pass, run each prompt in a fresh session with the skill in scope and check the output against the assertions by hand.

## A note on eval currency

Evals 2 and 4 embed specific commit SHAs and dates. When `actions/checkout` ships its next significant security change, eval 2's fixture should be refreshed so it continues to test "the pin is real but too old" rather than drifting into "the pin is ancient and obviously wrong". The fixture is meant to be a near-miss, not a straw man.

## Assertion conventions

Assertions are plain-English statements about the response. They split into:

- **Positive coverage** — "flags X" — the response should call out a specific issue.
- **Negative / no-false-positive** — "no false flag on pinning" — the response should leave correct things alone.
- **Hard failures** — "does not fabricate SHAs" — no partial credit.
- **Prioritisation** — "flags pull_request_target as critical" — about ranking, not just coverage.
