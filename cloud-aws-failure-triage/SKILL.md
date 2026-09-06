---
name: aws-failure-triage
description: Evidence-first debugging of AWS deploy and runtime failures — CloudFormation/CDK deploy errors (CREATE_FAILED, DELETE_FAILED, rollbacks, "no changes"), IAM AccessDenied / "not authorized to perform" errors, EventBridge events that never arrive, and Lambda Runtime.ImportModuleError. Use this whenever the user pastes an AWS error message, says a deployment failed, says a Step Function or Lambda never fired, reports an AccessDenied or 403 from any AWS service, or asks to fix an IAM policy — even if they only paste the raw error with no question.
allowed-tools: Read Glob Grep Edit Write Bash(aws *)
license: MIT
compatibility: >
  Needs the AWS CLI with read access to the affected account for evidence
  gathering. Works without credentials by handing the user the exact read-only
  commands to run and waiting for their output.
metadata:
  author: skwashd
  version: "1.0.0"
---

# AWS Failure Triage

Debug AWS failures from evidence, not guesses. The errors this skill covers arrive as pasted messages with most of the diagnosis already encoded in them — the job is to read them precisely, gather the one or two missing facts with read-only calls, and fix the actual cause.

## The Discipline

These rules exist because the most expensive AWS debugging sessions are guess-and-redeploy loops — each iteration costs a deploy cycle, and speculative fixes pile up as noise that must later be reverted.

1. **Read the pasted error completely before forming a theory.** AWS errors name the principal, action, resource, and stack event that failed. Extract those facts verbatim first.
2. **Gather evidence with read-only calls before changing anything.** `describe-*`, `list-*`, `get-*` calls are free and safe. If you don't have credentials, output the exact commands for the user to run and wait for the output — don't fill the gap with assumptions.
3. **Keep a hypothesis log across attempts.** After any failed fix, write down: what was tried, what the error said before and after, what that rules out. Never re-try a variation of a ruled-out fix. After two failed attempts, stop and re-plan from the accumulated evidence.
4. **Verify at the error surface.** The fix is confirmed when the deploy succeeds / the event arrives / the request is authorized — not when the code compiles or unit tests pass. Use the cheapest real probe available (`aws stepfunctions list-executions`, `nslookup`, `curl`, a re-run of the failed operation).
5. **Protect stateful resources.** Never propose deleting a stack, table, bucket, database, or user pool as a debugging step. When stack surgery is needed, plan it around retained resources (see the CloudFormation reference).

## Route to the Right Playbook

Classify the error and read the matching reference before acting:

| Error looks like | Read |
|---|---|
| `CREATE_FAILED`, `DELETE_FAILED`, `UPDATE_ROLLBACK_*`, "Unable to fetch parameters", "No changes to deploy", `Runtime.ImportModuleError`, cdk synth/deploy errors | `references/cloudformation-cdk.md` |
| `is not authorized to perform: <action> on resource: <arn>`, `AccessDenied`, `403`, policy-validator findings (parliament, Access Analyzer) | `references/iam-access-denied.md` |
| An event was published but the rule/target/Step Function "never fired", input transformer errors, cross-bus routing | `references/eventbridge.md` |

Failures in more than one category chain in a fixed order: fix authorization before routing, routing before target behaviour.

If the failure surfaced inside a CI/CD pipeline step rather than from a local deploy, the pipeline mechanics belong to the `ci-failure-triage` skill — use this skill for the AWS half of the diagnosis.

## Fixing Style

- Fix the infrastructure code (Terraform/CDK), not the console. A console hotfix disappears on the next deploy and creates drift; if an emergency console change is made, mirror it into code in the same session.
- Least privilege always: an AccessDenied is never fixed with `"Action": "*"` or `"Resource": "*"`. Add the specific action against the specific resource format that action requires.
- When a policy validator flags a finding, the fix is to tighten the policy. A finding may only be suppressed with a written justification of why it is a false positive in this context — never to make the check pass.

## Reporting

State: the root cause in one sentence, the evidence that proves it, the change made, and how the fix was verified. If the fix is unverified (no credentials, waiting on the user to redeploy), say so explicitly and list what to check after the deploy.
