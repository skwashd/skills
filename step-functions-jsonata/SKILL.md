---
name: aws-step-functions-jsonata
description: Author, validate, test, and deploy AWS Step Functions state machines in JSONata QueryLanguage mode. Use whenever the user asks to create, modify, review, validate, lint, test, or deploy a Step Functions workflow, state machine, or `.asl.json` file; or mentions Task/Choice/Parallel/Map/Wait/Pass/Succeed/Fail states, `Arguments`/`Output`/`Assign`, `$states.input`/`$states.result`/`$states.context`, JSONata `{% ... %}` expressions, service integrations (Lambda, DynamoDB, SNS, SQS, ECS, Glue, Bedrock, EventBridge, nested state machines), `.sync`/`.waitForTaskToken`, Express vs Standard, Distributed Map, or `stepfunctions test-state`. Also use for vaguer phrasing like "orchestrate these Lambdas", "wire this pipeline", or mentions of SAM `AWS::Serverless::StateMachine`, CDK `aws-stepfunctions`, Terraform `aws_sfn_state_machine`, CloudFormation `AWS::StepFunctions::StateMachine`. JSONata-only; never emits JSONPath (`InputPath`, `Parameters`, `ResultPath`, `.$` suffix, `$.foo`).
---

# AWS Step Functions (JSONata) Authoring Skill

This skill produces clean, modern AWS Step Functions state machines in **JSONata QueryLanguage mode**, validates them through a layered pipeline, and — on demand — emits deployment scaffolding for Terraform, SAM, CDK, CloudFormation, or the AWS CLI.

**This skill is JSONata-only.** If the user hands you an existing JSONPath state machine and asks you to work on it, your first job is to port it — see `references/jsonata-conversion.md`.

---

## The phased workflow

The phases below build on each other — the graph outline exists to be revised before ASL makes revision expensive. The one hard gate is Phase 4: don't hand over ASL the validator rejects at L1 or L2.

### Phase 1 — Capture intent

Before writing any ASL, establish:

1. **Trigger**: what kicks the workflow off? (API call, EventBridge rule, schedule, another state machine, manual)
2. **Inputs and outputs**: what shape does the input take, what does success output look like?
3. **Workflow type**: Standard or Express? Use the decision rules in "Standard vs Express" below. When unsure, ask.
4. **Error policy per external call**: for each Task, which errors are *known and recoverable* (retry or compensate) and which are *unknown* (fail loud)? This is not a detail — it drives the whole design. See "Error handling philosophy".
5. **Idempotency**: especially mandatory for Express (at-least-once delivery). For Standard with `.sync` / `.waitForTaskToken`, still preferred.

If any of these is unclear, ask the user one focused question. Do not guess your way into a 12-state machine only to discover it should have been Express.

### Phase 2 — Scaffold the graph before writing ASL

Emit a YAML outline of the state graph *first*. This is cheap, easy to revise, and prevents the most common failure mode (a Task references a `Next` state that doesn't exist or a Catch routes to a dead end). Example:

```yaml
StartAt: ValidateOrder
States:
  ValidateOrder:   { type: Task, next: ChargeCard, catch: [ValidationError -> RejectOrder] }
  ChargeCard:      { type: Task, next: FulfillOrder, catch: [CardDeclined -> RefundAndNotify] }
  FulfillOrder:    { type: Task, end: true }
  RejectOrder:     { type: Fail }
  RefundAndNotify: { type: Task, next: NotifyFailure }
  NotifyFailure:   { type: Fail }
```

Confirm the outline with the user if the workflow is non-trivial. **Checklist before proceeding:**

- Every non-terminal state has a `Next` or `End: true`.
- Every terminal is reachable from `StartAt`.
- Every Choice has a `Default`.
- Every Task has an explicit `TimeoutSeconds`.
- Every Task with recoverable failure modes has a targeted `Retry`.
- There is **no common error-handling state** that all Catch blocks funnel into (see "Error handling philosophy" below — this matters).

### Phase 3 — Fill the ASL from templates

Pick the closest template in `templates/` and adapt it. Every template already uses `"QueryLanguage": "JSONata"` and illustrates the right error-handling shape.

| Template | Use when |
|---|---|
| `standard-sequential-lambda.asl.json` | Linear pipeline of Lambda calls |
| `standard-parallel-fanout.asl.json` | Independent branches that must all complete |
| `standard-inline-map.asl.json` | Iterate over a small array (≤40 concurrency, fits in 256 KiB) |
| `standard-distributed-map-s3.asl.json` | Iterate over S3 objects or a large dataset (up to 10,000 child executions) |
| `standard-choice-router.asl.json` | Fan out based on input properties |
| `standard-saga-compensation.asl.json` | Multi-step transaction with compensating actions |
| `standard-waitfortask-callback.asl.json` | Human approval or external callback |
| `express-defensive.asl.json` | Express workflow — small, fully defensive |

For every Task `Resource` ARN, consult `references/service-integrations.md`. Do not invent ARN shapes. If the service you need is not in the allowlist, use the generic `arn:aws:states:::aws-sdk:<svc>:<action>` pattern documented at the bottom of that file — and copy the AWS documentation URL into the state's `Comment` field so the ARN is grounded in a real source.

For every JSONata expression, follow `references/jsonata-conversion.md`. Key rules — these apply to every expression you write:

- Every dynamic value wraps in `{% ... %}`. No wrapper = literal string.
- Read state input as `$states.input`, task result as `$states.result`, errors as `$states.errorOutput`, execution context as `$states.context`. **Never** use bare `$`, `$$`, or `$.foo` inside a Step Functions expression — those are JSONPath or plain JSONata idioms that AWS rejects.
- `Assign` and `Output` on the same state run in parallel. A variable assigned here is not visible to this state's `Output` — re-run the computation if needed.
- Do not use the old `.$` field-name suffix. Do not use `States.Format`, `States.Array`, etc. — they are JSONPath intrinsics. Use JSONata operators (`&` for concat, `[a,b]` for arrays, `$uuid()`, `$merge()`).

### Phase 4 — Validate (hard gate)

Run the validator. Do not hand the file to the user until layers L1 and L2 pass.

```bash
python scripts/validate.py path/to/statemachine.asl.json
```

The validator runs four layers:

| Layer | What | Offline? | Required? |
|---|---|---|---|
| L1 | JSON Schema (JSONata-only) | yes | **yes** |
| L2 | Graph + JSONata syntax + `$states` scope + IAM inference | yes | **yes** |
| L3 | `aws stepfunctions validate-state-machine-definition` | needs creds | if creds present |
| L4 | `aws stepfunctions test-state` per state (with mocks) | needs creds | opt-in with `--test-states` |

The validator probes for AWS credentials and skips L3/L4 with a clear banner if none are found. Exit codes: `0` = clean, `1` = errors, `2` = warnings-only, `3` = clean locally but dynamic layers skipped.

If the validator reports errors, fix them and re-run. Do not present the state machine as complete while L1 or L2 errors remain.

### Phase 5 — Deploy (on demand only)

Only emit deployment scaffolding when the user asks. When they do, ask which IaC tool:

| Tool | Emitter | Read before using |
|---|---|---|
| Terraform | `scripts/deploy/emit_terraform.py` | `references/deployment/terraform.md` |
| SAM | `scripts/deploy/emit_sam.py` | `references/deployment/sam.md` |
| CDK (L1 `CfnStateMachine`) | `scripts/deploy/emit_cdk.py` | `references/deployment/cdk.md` |
| CloudFormation | `scripts/deploy/emit_cloudformation.py` | `references/deployment/cloudformation.md` |
| Plain AWS CLI | `scripts/deploy/emit_cli.py` | `references/deployment/aws-cli.md` |

Each emitter takes the validated ASL path and a few config flags and writes the IaC file plus an execution-role IAM policy inferred from the Task `Resource` ARNs.

---

## Error handling philosophy

This section diverges from many tutorials and from AWS Workflow Studio defaults — where they conflict, this section wins.

### Never introduce a common error-handling state

It is tempting to route every `Catch` to a single `HandleError` state. **Do not.** When you do:

- The execution transitions past the offending state, so **redrive from the failed state is impossible**. Once the user fixes the underlying bug, they must rerun from `StartAt` rather than resuming from the point of failure.
- The diagnostic context (which state failed, its input, its error cause) gets funneled into the common handler's input and loses its anchor in the execution history.
- The execution reports as "Succeeded" (if the handler finishes) rather than "Failed", so EventBridge doesn't alert on it, and operators lose the clearest failure signal.

Handle known, recoverable errors *locally on the state that produced them*, and let unknown errors propagate to fail the execution at the exact state where they occurred.

### Retry for transient failures, Catch for branches

**Retry** is for transient, idempotent failures that might succeed on a retry with no change: throttling, service exceptions, network blips, cold-start timeouts. Use exponential backoff with full jitter:

```json
"Retry": [
  {
    "ErrorEquals": ["Lambda.TooManyRequestsException", "Lambda.ServiceException",
                    "Lambda.AWSLambdaException", "Lambda.SdkClientException"],
    "IntervalSeconds": 2, "MaxAttempts": 6, "BackoffRate": 2.0,
    "MaxDelaySeconds": 60, "JitterStrategy": "FULL"
  },
  {
    "ErrorEquals": ["States.QueryEvaluationError"],
    "MaxAttempts": 0
  }
]
```

Never catch `States.QueryEvaluationError` with retries — it is a deterministic expression bug that will fail the same way every time. Never use `BackoffRate < 1.0`. Never put `States.ALL` anywhere except as the last retrier/catcher in a list (it shadows everything after it), and usually not at all (see below).

**Catch** is for *known recoverable business outcomes* that branch the workflow — a card decline, a validation failure, a not-found, a quota exceeded. Each catcher routes to a specific state that handles that specific outcome:

```json
"Catch": [
  { "ErrorEquals": ["CardDeclined"], "Next": "NotifyCustomerDeclined",
    "Output": "{% { 'orderId': $states.input.orderId, 'reason': $states.errorOutput.Cause } %}" },
  { "ErrorEquals": ["InsufficientInventory"], "Next": "BackorderOrRefund",
    "Output": "{% $merge([$states.input, { 'error': $states.errorOutput }]) %}" }
]
```

### Do not use `States.ALL` as a catch-all

`States.ALL` turns every unknown error into a successful transition, which is the exact behavior you want to avoid. If you genuinely need to log something on unknown failure:

- **Standard workflows**: don't catch it — let it fail the execution. Configure EventBridge (`detail-type: "Step Functions Execution Status Change"`, `status: "FAILED"`) to notify; operators use the execution history to diagnose and then *redrive* from the failed state once the fix is deployed.
- **Express workflows**: see the Express section below. Because Express has no history, defensive `States.ALL` catchers are sometimes justified, but they emit structured failure output — they do not mask the failure.

### Workflow-type-specific rules

**Standard: fail spectacularly on fatal errors.**

- Catch only *named, recoverable* errors.
- Let unknown errors propagate. The execution fails at the offending state. History is preserved for 90 days via the API. EventBridge alerts on the failure. Operators fix the bug and **redrive** — resume from the failed state with fresh input — instead of re-running from scratch.
- Every Task sets `TimeoutSeconds` (the default is 99,999,999 seconds, which is effectively infinite — always set it).

**Express: small and defensive; handle everything.**

- Keep the workflow short (roughly ≤10 states). If it grows past that, consider splitting: a Standard parent that invokes Express children via `states:startExecution.sync:2`.
- Every Task is idempotent (Express has at-least-once delivery).
- Every Task has a comprehensive Retry policy.
- Unknown errors need a `States.ALL` catcher that *emits structured failure output* to a sink you can monitor — EventBridge, SNS, or the workflow's CloudWatch Logs — because there is no execution history to inspect after the fact.
- Even in Express, catchers still route to distinct handler states rather than one shared handler. The goal is visibility of *where* the error occurred, not centralization.

See `references/error-handling.md` for worked examples of both patterns and `references/express-vs-standard.md` for the full decision rubric.

---

## Standard vs Express quick rules

Use Standard unless all of the following hold for Express:

- Max duration ≤ 5 minutes.
- Request-response pattern only (no `.sync`, no `.waitForTaskToken`, no Activities).
- At-least-once delivery is acceptable (or every Task is idempotent).
- You do not need a Distributed Map (Distributed Map requires a Standard parent).
- You accept losing execution history after it leaves CloudWatch Logs retention.

Full decision rubric with cost and throughput numbers: `references/express-vs-standard.md`.

---

## What must never appear in output

This is enforced by the validator, but know it by heart. **None of these may appear in any ASL this skill produces:**

- Top-level or per-state `"QueryLanguage"` other than `"JSONata"`.
- Any of: `InputPath`, `OutputPath`, `Parameters`, `ResultSelector`, `ResultPath`, `Result` (on Pass), any field ending in `Path` (`ItemsPath`, `MaxConcurrencyPath`, `SecondsPath`, `TimestampPath`, `ErrorPath`, `CausePath`, etc.), the `.$` field-name suffix.
- Any JSONPath Choice operator: `Variable`, `And`, `Or`, `Not`, `StringEquals`, `NumericLessThan`, `IsPresent`, `StringMatches`, etc. Choice rules in JSONata use `Condition` + `Next` only.
- JSONPath intrinsic functions inside JSONata expressions: `States.Format`, `States.Array`, `States.UUID`, `States.JsonToString`, `States.StringToJson`, `States.JsonMerge`, etc. Use JSONata equivalents (see `references/jsonata-conversion.md`).
- Inside a JSONata expression: bare `$` (the top-level context — forbidden by Step Functions), `$$` (forbidden — use `$states.context`), unqualified field names (forbidden — reach through `$states.*`), `$eval(...)` (blocked — use `$parse`).
- Legacy `Iterator` on Map state. Modern Map uses `ItemProcessor`.

---

## Validation commands

```bash
# Validate a single file (default)
python scripts/validate.py workflow.asl.json

# Validate and run AWS dynamic per-state tests (opt-in; needs credentials)
python scripts/validate.py workflow.asl.json --test-states

# Validate expecting an Express target (stricter — rejects .sync, .waitForTaskToken, Distributed Map)
python scripts/validate.py workflow.asl.json --target-type EXPRESS

# Output a Mermaid diagram for review
python scripts/render_mermaid.py workflow.asl.json > workflow.mmd
```

---

## Quick footgun reminder

The full list is in `references/footguns.md`. The top offenders:

- Forgetting `{% %}` — `"id": "$states.input.id"` is a literal string, not evaluation.
- Using JSONPath `$.foo` inside a JSONata expression. It's `$states.input.foo`.
- Using `$$` for context. It's `$states.context`.
- Referencing `$states.result` in `Arguments` (runs before the task returns).
- Referencing `$states.errorOutput` outside a `Catch`.
- Assuming `Assign` on this state is visible to this state's `Output` — they run in parallel.
- Choice fallthrough without `Default` — runtime `States.NoChoiceMatched`.
- `TimeoutSeconds` unset (defaults to 99,999,999).
- `HeartbeatSeconds ≥ TimeoutSeconds` (heartbeat errors never surface).
- Inline Map `MaxConcurrency > 40` (service limit).
- Distributed Map in an Express parent (forbidden).
- `.sync` / `.waitForTaskToken` / Activities in Express (forbidden).

---

## Files in this skill

```
SKILL.md                                         (this file)
schemas/asl-jsonata.schema.json                  JSON Schema, Draft 2020-12, JSONata-only
scripts/validate.py                              Layered validator — run this before handing off
scripts/_jsonata_syntax.py                       Internal: per-expression JSONata parser
scripts/_graph_analyze.py                        Internal: reachability, refs, $states scope
scripts/_infer_iam.py                            Internal: Resource ARN → IAM policy
scripts/_probe_creds.py                          Internal: AWS credential probe
scripts/_aws_validate.py                         Internal: wraps validate-state-machine-definition
scripts/_aws_test_state.py                       Internal: wraps test-state with mocks
scripts/render_mermaid.py                        Mermaid diagram for review
scripts/deploy/emit_{terraform,sam,cdk,cloudformation,cli}.py   On-demand IaC emitters
templates/                                       Canonical starting points (read these before authoring)
references/state-types.md                        Fields per state type in JSONata mode
references/jsonata-conversion.md                 JSONPath → JSONata cheat sheet + idioms
references/service-integrations.md               ARN + IAM + doc URL allowlist
references/error-handling.md                     Retry/Catch recipes and the no-common-handler rationale
references/express-vs-standard.md                Decision rubric
references/footguns.md                           Full footgun list with fixes
references/deployment/{terraform,sam,cdk,cloudformation,aws-cli}.md   Scaffolds and gotchas
```

Read the reference file for the specific thing you are currently doing; do not read them all at once.
