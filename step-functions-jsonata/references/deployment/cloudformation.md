# Deploying with CloudFormation

Emitter: `scripts/deploy/emit_cloudformation.py`

```
python scripts/deploy/emit_cloudformation.py \
  --asl workflow.asl.json \
  --name my-state-machine \
  --type STANDARD \
  --outdir cfn/
```

Produces `cfn/template.json`. Use `--force-s3` if you prefer the ASL externalized to S3 regardless of size.

## Inline vs S3-referenced

The emitter chooses automatically:

- ASL ≤ 40,000 bytes: inlined as `DefinitionString` in the template (the CloudFormation template body cap is 51,200 bytes; 40,000 leaves headroom for the other resources).
- ASL > 40,000 bytes or `--force-s3`: emits `DefinitionS3Location` pointing at a bucket/key you supply at deploy time via parameters.

## What the scaffold sets up

- Template parameters: one `String` per `${Placeholder}` in the ASL; plus `DefinitionBucket` and `DefinitionKey` in S3 mode.
- `AWS::Logs::LogGroup` at `/aws/vendedlogs/states/${AWS::StackName}` with 14-day retention.
- `AWS::IAM::Role` with trust policy and inline policy (execution-role permissions inferred from Task Resource ARNs plus CloudWatch Logs and X-Ray).
- `AWS::StepFunctions::StateMachine` with `DefinitionSubstitutions`, logging, and tracing.
- `DependsOn: StateMachineRole` on the state machine so CFN creates the role first.

## Deployment command

Inline:
```
aws cloudformation deploy \
  --template-file cfn/template.json \
  --stack-name my-state-machine \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    ProcessingLambdaArn=arn:aws:lambda:... \
    OrdersTable=orders
```

S3-referenced:
```
aws s3 cp workflow.asl.json s3://my-bucket/sfn/workflow.asl.json

aws cloudformation deploy \
  --template-file cfn/template.json \
  --stack-name my-state-machine \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    DefinitionBucket=my-bucket \
    DefinitionKey=sfn/workflow.asl.json \
    ProcessingLambdaArn=arn:aws:lambda:...
```

The S3 bucket must be in the stack's region.

## Gotchas

**ASL size limits:** 51,200 bytes for inline (template body), 1,048,576 bytes for S3-referenced (Step Functions API limit).

**Placeholder substitution happens BEFORE the ASL is parsed for JSON validity.** An unquoted `${Placeholder}` in a numeric field breaks parsing; if you substitute into a number, the ASL must have `"MaxConcurrency": "${MaxConcurrency}"` — quoted — and the parameter value must be a valid integer literal. Our templates avoid this by putting all substitutions in string positions.

**`DependsOn: StateMachineRole`** is required. CloudFormation otherwise tries to create the state machine before the role is ready and fails with `AccessDenied`.

**Log-group name outside `/aws/vendedlogs/states/*`** hits the 5,120-character resource-policy cap on CloudWatch Logs. The scaffold uses `/aws/vendedlogs/states/${AWS::StackName}` which is safe.

**CFN doesn't auto-grant per-integration permissions.** All Task permissions come from the inferred inline policy. Review it before deploying.

## Running it

Same as the deployment command above. To update, re-run `aws cloudformation deploy` with the same `--stack-name`.
