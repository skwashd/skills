# EventBridge Routing Playbook

For "the event was published but nothing happened". The failure is somewhere on a fixed path — walk it in order and confirm each hop with evidence rather than intuition.

## The Path

```
producer → bus (PutEvents) → rule (pattern match) → [cross-bus target → rule on second bus] → target (SFn/Lambda/queue) → input transformer → consumer
```

## Step 1: Did the Event Reach the Bus?

- Producer-side confirmation: `PutEvents` returns per-entry failures — check the producer's logs for `FailedEntryCount`.
- Cheapest bus-side proof: temporarily add a catch-all debug rule (pattern `{"account":["<account-id>"]}`) targeting a CloudWatch log group, publish, read the log. This captures the event **exactly as the bus sees it** — which is the ground truth for step 2.

## Step 2: Does the Rule Pattern Actually Match the Event?

This is the most common failure. Compare the captured event JSON against the rule pattern field by field:

- **Every field in the pattern is ANDed**; every value list is ORed. A single extra constrained field silently kills the match.
- **Case matters.** `detail-type: ["Bucket Created"]` does not match `bucket created`.
- **Pattern values must be arrays.** `"detail-type": "X"` instead of `["X"]` is invalid/non-matching.
- **Nesting must mirror the event exactly** — matching `detail.status` requires `{"detail": {"status": [...]}}`.
- **`source` and `detail-type` drift** between producer and rule is the classic bug: the producer emits `myapp.provisioner` while the rule matches `myapp-provisioner`.

Test offline without deploying:

```bash
aws events test-event-pattern --event-pattern file://pattern.json --event file://event.json
```

Where rules live in IaC (rules.json files, Terraform), fix the source file, not the console.

## Step 3: Cross-Bus Routing

Bus-to-bus forwarding needs three things, and each missing one fails silently:

1. A rule on the source bus whose **target is the destination bus ARN**.
2. An IAM **role on that target** allowing `events:PutEvents` to the destination bus (targets to another bus don't use resource policies alone).
3. The destination bus **resource policy** allowing the source account/rule if crossing accounts.

Then the destination bus needs its own rule — matching on it repeats Step 2 there. Remember the envelope: a forwarded event keeps its original `source`/`detail-type` — rules on the second bus match the original fields, not anything about the forwarding.

## Step 4: Did the Target Get Invoked, and Did It Fail?

The rule matching is not the same as the target succeeding:

- `aws cloudwatch get-metric-statistics` (or the console) for the rule's `Invocations` and `FailedInvocations` metrics: invocations>0 with failures>0 means routing works and the target/permissions/transformer is broken.
- Check the rule target's **DLQ** if configured — failed events with error codes land there.
- Target permission failures (EventBridge not allowed to `states:StartExecution` / `lambda:InvokeFunction`) show as FailedInvocations. See the IAM playbook.

## Step 5: Input Transformers

A transformer that produces output the target rejects fails at invocation, after a successful match:

- Every `<placeholder>` in the template must exist in `InputPathsMap`, and every referenced path must exist in the actual event — a missing path yields literal `<placeholder>` text or invalid JSON.
- The output must be the exact shape the target expects (Step Functions input schema, Lambda event contract). Validate by taking the captured event from Step 1, applying the transform by hand, and checking the result against what the target's first state/handler reads.
- Quoting: `"<field>"` produces a JSON string; bare `<field>` splices raw JSON. Mixing these up produces double-quoted strings or broken JSON.

## Verify

Publish one real event end-to-end and confirm the terminal effect (execution started, log line written). Then remove any debug rules you added — a leftover catch-all rule logging every event is cost and noise.
