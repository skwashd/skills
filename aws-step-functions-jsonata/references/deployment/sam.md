# Deploying with SAM

Emitter: `scripts/deploy/emit_sam.py`

```
python scripts/deploy/emit_sam.py \
  --asl workflow.asl.json \
  --name MyStateMachine \
  --type STANDARD \
  --outdir sam/
```

Produces `sam/template.yaml` and a copy of the ASL file.

## What the scaffold sets up

- `AWS::Serverless::StateMachine` with `DefinitionUri` pointing at the local ASL file.
- `DefinitionSubstitutions` block with one entry per `${Placeholder}` discovered in the ASL, each referencing a CloudFormation `Parameter`.
- `AWS::Logs::LogGroup` at `/aws/vendedlogs/states/<n>` with 14-day retention.
- Inline IAM `Policies` statements inferred from Task `Resource` ARNs.
- Logging + tracing enabled.

## Deployment command

```
cd sam/
sam build
sam deploy --guided
```

**Do not use `aws cloudformation deploy` directly.** SAM's `DefinitionUri` only resolves local paths during `sam package` / `sam deploy`. Plain `aws cloudformation deploy` will see an unresolvable path and fail.

## Gotchas

**`DefinitionSubstitutions` values are string-only.** Substituting a numeric field (like `TimeoutSeconds: ${Timeout}`) breaks SAM schema validation (roadmap issue #591). If you need numeric substitution, either inline the definition with `Definition:` + `Fn::Sub` or hard-code the number in the ASL.

**`Events:` in SAM wire invokers (EventBridge/Schedule/API GW).** They do not modify the state machine's execution role — that's `Policies:`.

**SAM policy templates** are a faster path than inline statements when your integrations are common: `LambdaInvokePolicy`, `DynamoDBWritePolicy`, `StepFunctionsExecutionPolicy`, etc. Swap in as appropriate; full list at https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-templates.html.

**SAM has its own state-machine DSL** (`Definition:` inline in YAML). This emitter deliberately doesn't use it — the ASL file is the source of truth, validated by the skill's validator.

## Invoking via EventBridge / Schedule / API Gateway

Add to `Properties:` on the state machine:

```yaml
Events:
  OnSchedule:
    Type: Schedule
    Properties:
      Schedule: rate(1 hour)
      Input: '{"trigger":"scheduled"}'
```

SAM generates the EventBridge rule and IAM wiring automatically.
