# Evals for `ship-story`

Test cases for the two parts of `ship-story` that are testable offline: tracker
**detection** (evals 1–5) and deploy-verification **planning** (evals 6–7). The middle
of the loop — branch, implement, PR, CI, merge — needs a live pipeline and real
credentials, so it isn't covered here; see the repo README's Evals section.

## Layout

```
evals/
├── evals.json
└── files/
    ├── declared-jira/       # CLAUDE.md names Jira explicitly
    ├── declared-linear/     # CLAUDE.md names Linear explicitly
    ├── linear-toml-only/    # no declaration; .linear.toml is the only signal
    ├── ambiguous/           # no declaration, no repo config — must ask
    ├── gh-present-jira/     # Jira declared, but gh and GitHub Actions mentioned throughout
    ├── verify-aws/          # deploy section names AWS (stack, Lambda, SQS queue)
    └── verify-non-aws/      # deploy section names Fly.io — no AWS anywhere
```

> **Fixture naming:** inside each fixture, `dot-CLAUDE.md` stands in for `CLAUDE.md`.
> Claude Code auto-loads any `CLAUDE.md` file it finds as project memory, so a literal
> `CLAUDE.md` committed inside a test fixture would be picked up as *this repository's*
> memory rather than staying inert until an eval run copies it into place — the same
> trap `dependabot-manager`'s evals hit with `.github/`, renamed there to `dot-github/`.
> When running an eval, copy `dot-CLAUDE.md` to `CLAUDE.md` in the fixture root first.
> `.linear.toml` needs no such treatment — Claude Code doesn't treat it specially.

## Test cases

| ID | Name | What it tests |
|----|------|---------------|
| 1 | `declared-jira` | Reads the `Issue tracker:` line in CLAUDE.md; routes to Jira |
| 2 | `declared-linear` | Same, for Linear |
| 3 | `linear-toml-only` | Falls back to repo config when CLAUDE.md is silent |
| 4 | `ambiguous-asks-not-guesses` | **Asks rather than guesses** when nothing resolves it |
| 5 | `gh-present-jira` | `gh`'s availability and mentions don't override an explicit Jira declaration |
| 6 | `aws-verify-uses-reference` | Reads `verify-aws.md` when the project deploys to AWS; queue checked read-only |
| 7 | `non-aws-verify-skips-reference` | Doesn't load the AWS reference off AWS; commands come from CLAUDE.md; writes still named |

## What each case is really guarding

**Evals 1 and 2** are the basic positive-coverage cases: CLAUDE.md declares the tracker,
and detection should stop there rather than second-guessing it against the key shape or
asking a question the answer already settles.

**Eval 3** is the fallback path — the repo has no declaration, only the config file the
tracker's own CLI leaves behind. This is what makes `.linear.toml` (from `linear
config`) and `.jira/` (from the `jira-acli` skill) part of the detection order at all,
not just incidental config.

**Eval 4 is the one this whole detection scheme exists to pass.** `ABC-12` is a valid
key shape on both Jira and Linear, and with no declaration and no repo config there is
nothing left to disambiguate it from. The failure mode this guards against doesn't fail
loudly — a wrong guess reads, or comments on, a real ticket in the wrong system. "Asks"
is the only correct behaviour here, and it's the expectation most worth checking by hand if
you only have time for one.

**Eval 5** guards the fallback signal that's easiest to get wrong precisely because it's
almost always true: `gh` is installed on nearly every project for reasons that have
nothing to do with issue tracking (PRs, CI, releases). A detection routine that lets
"`gh` is available and mentioned a lot" outvote an explicit `Issue tracker: Jira` line
would silently misroute every Jira project that also deploys through GitHub Actions —
which is most of them.

**Evals 6 and 7** cover the platform side of step 8, and only its *planning* — the
prompt drops in mid-loop ("PR merged, deploy finished, verify these criteria") and the
graded artifact is the verification plan, since actually observing a deploy needs live
credentials. Eval 6's queue criterion is deliberate bait: the natural-looking check is
`aws sqs receive-message`, which is not read-only — it hides the message from real
consumers and increments the counter dead-letter policies act on. A passing run reads
`references/verify-aws.md`, checks depth with `get-queue-attributes`, and names the
form-submission POST as a write. Eval 7 is the twin that keeps the reference honest in
the other direction: on a Fly.io project the AWS file must *not* be loaded, observation
commands must come from `CLAUDE.md` (`flyctl logs`), and the read-only-first discipline
must survive without AWS specifics to lean on — requesting a report to produce a log
line is still a named write.

## How to run

The [`skill-creator`](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator)
plugin runs these, including with/without-skill benchmarking:

```
/plugin install skill-creator@claude-plugins-official
```

Spawn one subagent per eval with the skill loaded, then a baseline subagent without it,
save outputs to `iteration-1/eval-<id>/{with,without}_skill/`, and grade against the
expectations in `evals.json`. Remember the `dot-CLAUDE.md` → `CLAUDE.md` copy step above
before invoking the skill on a fixture.

For an informal pass, run each prompt in a fresh session with the skill in scope and
check the output against the expectations by hand. Eval 4 is the one to prioritise if
running all five isn't practical.

## Expectation conventions

Expectations are plain-English statements about the response, split into:

- **Positive coverage** — "routes to Jira", "falls back to repo config" — the response
  should do a specific thing.
- **Negative / no-false-positive** — "does not ask which tracker", "does not cite the
  key shape as evidence" — the response should not do a specific wrong thing.

Evals 1, 2 and 3 are mostly positive coverage; evals 4 and 5 are primarily negative —
they exist to catch a plausible-looking wrong guess, not to confirm a correct one.
