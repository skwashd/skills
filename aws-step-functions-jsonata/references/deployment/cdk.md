# Deploying with CDK

Emitter: `scripts/deploy/emit_cdk.py`

```
python scripts/deploy/emit_cdk.py \
  --asl workflow.asl.json \
  --name MyStateMachine \
  --type STANDARD \
  --outdir cdk/lib/
```

Produces `cdk/lib/<classname>.ts` and a copy of the ASL file. TypeScript CDK v2 (`aws-cdk-lib`).

## Why the L1 `CfnStateMachine` rather than L2 `StateMachine`

The high-level `sfn.StateMachine` + `sfn.DefinitionBody.fromFile()` discards the ability to substitute placeholders at deploy time (it uploads the file verbatim as an S3 asset). The L1 `CfnStateMachine` accepts `definitionSubstitutions` the same way CloudFormation does.

If you'd rather author the state machine with the CDK chainable DSL (`sfn.Chain.start(...)`), this skill isn't the right tool — the whole point is that the ASL file is the source of truth and the validator's focus.

## What the scaffold sets up

- `iam.Role` for the state machine with `states.amazonaws.com` trust.
- Inline policy statements via `role.addToPolicy(...)`, one per inferred group.
- `logs.LogGroup` at `/aws/vendedlogs/states/<n>` with 2-week retention.
- `sfn.CfnStateMachine` reading the ASL via `fs.readFileSync`, with `definitionSubstitutions` mapped from `props`.
- Logging `ALL` + include-execution-data + tracing enabled.
- `CfnOutput` for the state machine ARN.

## Integrating into your CDK app

Add to `bin/app.ts`:

```typescript
import { MyStateMachineStack } from '../lib/mystatemachinestack';

new MyStateMachineStack(app, 'MyStateMachine', {
  processingLambdaArn: processingFn.functionArn,
  ordersTable: ordersTable.tableName,
  // ... one prop per ${Placeholder}
});
```

## Gotchas

**CDK cannot infer permissions from an externally-authored ASL.** Grants that the L2 `StateMachine` construct adds automatically (e.g. `lambda.grantInvoke(machine)`) don't happen here. The emitted scaffold adds them based on our own ARN parsing — review the inline policy statements before deploying.

**`fromFile` uploads as an S3 asset, bypassing the 1 MB CloudFormation limit.** With `CfnStateMachine.definitionString`, the ASL is inlined into the template, which has the 1 MB CFN limit. For large workflows, switch the emitter to use `DefinitionBody.fromFile` + no substitutions, or upload the ASL to S3 manually and use `DefinitionS3Location`.

**L1 constructs expect property names in camelCase.** The scaffold has them right (`stateMachineType`, `tracingConfiguration`, etc.); don't "correct" them.

**CDK JSONata Distributed Map + `ResultWriter` without `Arguments`.** Known aws-cdk#33396 bug — the console auto-adds `Arguments`, CDK doesn't. Include `Arguments` (even an empty object `{}`) on your Distributed Map's `ResultWriter` in the ASL.

## Running it

```
cd cdk/
npm install
npx cdk synth
npx cdk deploy
```
