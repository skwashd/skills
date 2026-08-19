# Service integrations

This is the grounding table for Task `Resource` ARNs. Copy the Doc URL into the Task's `Comment` field so the ARN is sourced rather than invented.

Three integration patterns:

| Pattern | ARN suffix | Semantics |
|---|---|---|
| Request/Response | (none) | Invoke, wait for a synchronous response, continue. |
| Run-a-Job (`.sync` / `.sync:2`) | `.sync` or `.sync:2` | Invoke, poll for job completion, continue. |
| Wait-for-Callback (`.waitForTaskToken`) | `.waitForTaskToken` | Invoke, pause until external caller calls `SendTaskSuccess`/`Failure` with the task token. |

**Express workflow constraint:** only Request/Response is supported. No `.sync`, no `.waitForTaskToken`, no Activities, and Distributed Map cannot be hosted as a parent.

## Core integrations

### Lambda

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Request/Response | `arn:aws:states:::lambda:invoke` | `lambda:InvokeFunction` |
| Wait-for-Callback | `arn:aws:states:::lambda:invoke.waitForTaskToken` | `lambda:InvokeFunction` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-lambda.html

Retryable errors to consider: `Lambda.TooManyRequestsException`, `Lambda.ServiceException`, `Lambda.AWSLambdaException`, `Lambda.SdkClientException`, `Lambda.Unknown`.

### Nested Step Functions

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Async | `arn:aws:states:::states:startExecution` | `states:StartExecution` |
| Sync | `arn:aws:states:::states:startExecution.sync` | `states:StartExecution`, `states:DescribeExecution`, `states:StopExecution`, plus `events:PutTargets`, `events:PutRule`, `events:DescribeRule` on the managed rule |
| Sync v2 | `arn:aws:states:::states:startExecution.sync:2` | same as Sync. Use when the child may return a JSON object; `.sync` stringifies the cause. |
| Wait-for-Callback | `arn:aws:states:::states:startExecution.waitForTaskToken` | `states:StartExecution` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-stepfunctions.html

Pattern: Standard parent invokes Express children via `.sync:2` for high-throughput idempotent sequences.

### DynamoDB (optimized)

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| GetItem | `arn:aws:states:::dynamodb:getItem` | `dynamodb:GetItem` |
| PutItem | `arn:aws:states:::dynamodb:putItem` | `dynamodb:PutItem` |
| UpdateItem | `arn:aws:states:::dynamodb:updateItem` | `dynamodb:UpdateItem` |
| DeleteItem | `arn:aws:states:::dynamodb:deleteItem` | `dynamodb:DeleteItem` |

For Query and Scan, use the AWS SDK integration: `arn:aws:states:::aws-sdk:dynamodb:query` / `:scan`. IAM: `dynamodb:Query` / `dynamodb:Scan`.

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-ddb.html

Retryable: `DynamoDB.ThrottlingException`, `DynamoDB.ProvisionedThroughputExceededException`.

### SNS

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Publish | `arn:aws:states:::sns:publish` | `sns:Publish` |
| Wait-for-Callback | `arn:aws:states:::sns:publish.waitForTaskToken` | `sns:Publish` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-sns.html

### SQS

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| SendMessage | `arn:aws:states:::sqs:sendMessage` | `sqs:SendMessage` |
| Wait-for-Callback | `arn:aws:states:::sqs:sendMessage.waitForTaskToken` | `sqs:SendMessage` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-sqs.html

### EventBridge

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| PutEvents | `arn:aws:states:::events:putEvents` | `events:PutEvents` |
| Wait-for-Callback | `arn:aws:states:::events:putEvents.waitForTaskToken` | `events:PutEvents` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-eventbridge.html

## Compute and data integrations

### ECS / Fargate (RunTask)

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Request/Response | `arn:aws:states:::ecs:runTask` | `ecs:RunTask`, `iam:PassRole` |
| Sync | `arn:aws:states:::ecs:runTask.sync` | `ecs:RunTask`, `ecs:StopTask`, `ecs:DescribeTasks`, `iam:PassRole`, plus events-trio |
| Wait-for-Callback | `arn:aws:states:::ecs:runTask.waitForTaskToken` | `ecs:RunTask`, `iam:PassRole` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-ecs.html

### AWS Batch

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Sync | `arn:aws:states:::batch:submitJob.sync` | `batch:SubmitJob`, `batch:DescribeJobs`, `batch:TerminateJob`, plus events-trio |
| Sync v2 | `arn:aws:states:::batch:submitJob.sync:2` | same; bypasses container-override injection |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-batch.html

### Glue

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Sync | `arn:aws:states:::glue:startJobRun.sync` | `glue:StartJobRun`, `glue:GetJobRun`, `glue:GetJobRuns`, `glue:BatchStopJobRun` |
| Async | `arn:aws:states:::glue:startJobRun` | `glue:StartJobRun` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-glue.html

### SageMaker

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Training (sync) | `arn:aws:states:::sagemaker:createTrainingJob.sync` | `sagemaker:CreateTrainingJob`, `sagemaker:DescribeTrainingJob`, `sagemaker:StopTrainingJob`, `iam:PassRole`, plus events-trio |
| Endpoint / Transform | `arn:aws:states:::sagemaker:<action>[.sync]` | per-action SageMaker permissions |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-sagemaker.html

### Athena

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Query (sync) | `arn:aws:states:::athena:startQueryExecution.sync` | `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `athena:StopQueryExecution` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-athena.html

### API Gateway

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Invoke | `arn:aws:states:::apigateway:invoke` | `execute-api:Invoke` |
| Wait-for-Callback | `arn:aws:states:::apigateway:invoke.waitForTaskToken` | `execute-api:Invoke` |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-api-gateway.html

### HTTP Task (EventBridge Connections)

| Pattern | Resource ARN | IAM actions |
|---|---|---|
| Invoke | `arn:aws:states:::http:invoke` | `events:RetrieveConnectionCredentials`, `secretsmanager:GetSecretValue`, `secretsmanager:DescribeSecret` on the connection's secret |

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/connect-third-party-apis.html

**60-second hard cap** regardless of `TimeoutSeconds`. Failure raises `States.Http.Socket`.

## Generic AWS SDK integration

For any AWS service not on the list above, use:

```
arn:aws:states:::aws-sdk:<service>:<action>
arn:aws:states:::aws-sdk:<service>:<action>.waitForTaskToken
```

The IAM action is typically `<service>:<Action>` with the first letter of `<Action>` uppercased (SDK is camelCase; IAM is PascalCase).

Examples:
- `arn:aws:states:::aws-sdk:s3:headObject` → `s3:HeadObject`
- `arn:aws:states:::aws-sdk:secretsmanager:getSecretValue` → `secretsmanager:GetSecretValue`
- `arn:aws:states:::aws-sdk:bedrock-runtime:invokeModel` → `bedrock:InvokeModel`
- `arn:aws:states:::aws-sdk:kinesis:putRecords` → `kinesis:PutRecords`

Doc: https://docs.aws.amazon.com/step-functions/latest/dg/supported-services-awssdk.html

Over 200 services are supported. When uncertain about an action name's capitalization, check the AWS CLI for the service — it uses the same camelCase as the SDK integration.

## Distributed Map ItemReader / ResultWriter

Not Task integrations but use the same ARN shape:

| Resource ARN | Purpose | IAM actions |
|---|---|---|
| `arn:aws:states:::s3:getObject` | ItemReader: CSV/JSON/JSONL/Parquet from S3 | `s3:GetObject`, `s3:ListBucket` |
| `arn:aws:states:::s3:listObjectsV2` | ItemReader: iterate object keys | `s3:ListBucket` |
| `arn:aws:states:::s3:putObject` | ResultWriter: write results back to S3 | `s3:PutObject`, `s3:AbortMultipartUpload` |

For Distributed Map execution-role permissions on the state machine itself: `states:StartExecution`, `states:DescribeExecution`, `states:StopExecution`, `states:RedriveExecution`. The `Resource` scope is the state machine's own ARN.

## When an integration isn't listed

Either it doesn't exist (check AWS docs), or it's a brand-new service that only works via the AWS SDK integration. Default to the `aws-sdk:<service>:<action>` pattern and populate the Task's `Comment` with the AWS documentation URL.
