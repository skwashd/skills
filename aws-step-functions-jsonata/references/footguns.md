# Footguns

Concrete failure modes, grouped. Each includes the trigger, the symptom, and the fix.

## JSONata expression syntax

**Forgetting the `{% %}` wrapper.** `"id": "$states.input.id"` is a literal string `"$states.input.id"`, not an evaluated expression. Symptom: the downstream service gets the literal text. Fix: always wrap dynamic values in `{% … %}` with no surrounding whitespace.

**Using JSONPath `$.foo` inside a JSONata expression.** AWS rejects bare `$` as the top of the expression. Fix: `$states.input.foo`.

**Using `$$` for execution context.** Forbidden. Fix: `$states.context` (e.g. `$states.context.Execution.Name`).

**Using the `.$` field-name suffix.** The `"field.$": "$.value"` convention is JSONPath only. Fix: drop the `.$` suffix, wrap the value in `{% %}`.

**Using `$eval(...)`.** Blocked by Step Functions for security. Fix: `$parse(jsonString)` for JSON, or precompute the value.

**Using JSONata 2.1 syntax (`?:`, `??`).** `jsonata-python` and `jsonata-js` accept these; Step Functions runs 2.0.6 and rejects them. The skill's L2 check will pass but AWS validation (L3) will fail. Fix: use ternary `cond ? a : b` and explicit null checks.

## `$states.*` scope errors

**Referencing `$states.result` in `Arguments` or `ItemSelector`.** These fields run *before* the task returns; the result doesn't exist yet. Fix: read `$states.input` instead, or move the transformation into `Output`.

**Referencing `$states.errorOutput` outside `Catch[]`.** Only available in `Catch[].Output` and `Catch[].Assign`. Fix: if you want to preserve the error for later, stash it inside `Catch[].Output` using `$merge`.

**Expecting `Assign` on this state to be visible in this state's `Output`.** They run in parallel. Fix: either duplicate the expression, or move the computation into `Assign` alone and use `$myVar` from the next state.

**Shadowing an outer variable from inside Parallel/Map.** Inner scopes can read outer variables but cannot write to the same name. Fix: use a different name inside the branch/iteration.

**Referring to outer variables from inside a Distributed Map.** Forbidden entirely — each iteration is a separate execution. Fix: pass the needed values through `ItemSelector` or `ItemBatcher.BatchInput`.

## Graph topology

**Choice state with no `Default`.** Unmatched input raises `States.NoChoiceMatched` at runtime. Fix: always include `Default`, even if it routes to a `Fail` state.

**`Next` pointing to a state not in this `States` map.** The validator catches this. Fix: check spelling, or realize you intended to route into a Parallel/Map sub-state-machine (which isn't allowed — branches are closed scopes).

**`StartAt` not in `States`.** Same category; validator catches it.

**Cycle with no exit.** Wait states can legitimately cycle, but an infinite loop with no termination raises `States.ExecutionLimitExceeded`. Fix: include a Choice state that breaks the cycle.

**No terminal reachable.** Every reachable state must eventually hit `End: true`, `Succeed`, or `Fail`. Validator warns.

## Timeouts

**`TimeoutSeconds` not set.** Default is 99,999,999 seconds (≈3 years). A hung integration will hang the execution for the lifetime of the workflow type (1 year for Standard, 5 min for Express). Fix: always set an explicit timeout aligned with the integration's SLA plus margin.

**`HeartbeatSeconds ≥ TimeoutSeconds`.** Heartbeat errors never fire because the timeout expires first. Fix: make `HeartbeatSeconds` strictly less than `TimeoutSeconds`, typically less than half.

**Express execution > 5 minutes.** Express workflows are capped at 5 minutes wall-clock. A Wait state alone can push you over. Fix: use Standard.

**HTTP Task > 60 seconds.** The HTTP integration has a hard 60-second cap regardless of `TimeoutSeconds`. Fix: use a Lambda as a shim for longer HTTP calls.

## Retry / Catch

**`States.ALL` as the only retrier.** Masks bugs by retrying JSONata errors, permission errors, and uncatchable errors. Fix: list the specific transient errors you want to retry; include `States.QueryEvaluationError` with `MaxAttempts: 0` to fail fast on expression bugs.

**`States.ALL` not last.** It shadows subsequent entries. Fix: make it the final entry if present at all.

**`BackoffRate` below 1.0.** Invalid — AWS rejects. Fix: use 1.0 for constant delay, or > 1.0 for exponential.

**No `JitterStrategy: "FULL"`.** Without jitter, retry storms synchronize. Fix: always include `"JitterStrategy": "FULL"` on any retrier that will run multiple times.

**Common error handler pattern.** All Tasks `Catch` → one `HandleError` state. Breaks redrive-from-failed-state, turns failed executions into Succeeded, hides failure location. Fix: per-Task handlers for named recoverable errors; let unknown errors fail the execution. See `error-handling.md`.

## Map state

**Inline Map `MaxConcurrency > 40`.** Service limit. Fix: use Distributed Map (set `ProcessorConfig.Mode: "DISTRIBUTED"`).

**Distributed Map with no `MaxConcurrency`.** Defaults to 10,000 concurrent children — can overwhelm downstream. Fix: set it explicitly, typically 50–500 depending on downstream capacity.

**Distributed Map in Express parent.** Not supported. Fix: parent must be Standard.

**Inline Map with `ItemReader` / `ItemBatcher` / `ResultWriter`.** Those are Distributed-only. Fix: either switch to Distributed mode, or move the I/O into Tasks.

**Using `Iterator` instead of `ItemProcessor`.** `Iterator` is deprecated. Fix: rename to `ItemProcessor`; the skill's schema rejects `Iterator`.

**`ItemsPath`.** Deprecated JSONPath field. Fix: `Items` with a JSONata expression like `{% $states.input.records %}`.

## Express-specific

**Standard-style "fail loud" in Express.** Express has no execution history; unknown failures leave no diagnostic trail. Fix: use the express-defensive pattern (`States.ALL` catcher per Task with structured failure output to SNS/EventBridge/Logs).

**Non-idempotent Tasks in Express.** At-least-once delivery can duplicate. Fix: make every Task idempotent — use `ConditionExpression` on DDB writes, deduplication IDs on queue sends, etc.

**Express workflow bigger than ~10 states.** You lose visibility into where failures occur. Fix: split — Standard parent + Express children via `states:startExecution.sync:2`.

## Distributed Map

**Distributed Map + `ResultWriter` + JSONata, without `Arguments`.** Known CDK bug (aws-cdk#33396); the console auto-injects `Arguments` but CDK doesn't. Fix: include `ItemReader.Arguments` and `ResultWriter.Arguments` explicitly (even if empty objects).

**`ItemBatcher.MaxInputBytesPerBatch > 256 KiB.** Batches get rejected. Fix: cap it lower and shard.

**Distributed Map without self-execution IAM.** Parent state machine needs `states:StartExecution`, `states:DescribeExecution`, `states:StopExecution`, `states:RedriveExecution` *on its own ARN*. Fix: include these in the execution role policy.

**Distributed Map label > 40 chars or non-ASCII.** Fix: restrict to `[A-Za-z0-9_-]{1,40}`.

## Payload and variable limits

**Task payload > 256 KiB.** Raises `States.DataLimitExceeded` — uncatchable. Fix: store large data in S3 and pass references.

**Variable > 256 KiB, or total variables > 10 MiB.** Fix: same as above — externalize.

**Execution history > 25,000 entries** (Standard). Fix: Distributed Map moves iteration history to children; use it.

## IaC gotchas

**Terraform `log_destination` without trailing `:*`.** Fix: `"${aws_cloudwatch_log_group.sfn.arn}:*"`.

**Terraform or CFN state machine `type` change.** Immutable — requires replacement (new ARN). Fix: plan for replacement, or create a new resource and migrate traffic.

**SAM `DefinitionUri` with `aws cloudformation deploy`.** Doesn't resolve local paths. Fix: use `sam package && sam deploy`.

**CDK `DefinitionBody.fromFile()` with auto-grant expectations.** CDK can't infer permissions from an externally-authored ASL. Fix: grant explicitly, or use `CfnStateMachine` with `DefinitionSubstitutions`.

**CloudFormation template > 51,200 bytes inline.** Fix: use `DefinitionS3Location` — the emitter does this automatically at 40 KB.

**Log group name outside `/aws/vendedlogs/states/*`.** Hits the 5,120-character resource-policy cap on CloudWatch Logs per log group. Fix: use `/aws/vendedlogs/states/*`.

**Missing `iam:PassRole`.** For `.sync` integrations that assume a service role (ECS, Batch, SageMaker), the state machine's execution role needs `iam:PassRole`. Fix: included by the skill's IAM inference, but scope it to the target role ARN rather than `*` when deploying.
