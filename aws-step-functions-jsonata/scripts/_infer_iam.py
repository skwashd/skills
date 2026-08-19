"""
Infer an execution-role IAM policy from the Task Resource ARNs used in an ASL
document.

This is best-effort guidance, not a complete policy generator. It covers the
most common service integrations and falls through to a generic stub for
unknown ARN patterns. The output is always a `PolicyDocument`-shaped dict
suitable for an inline IAM policy attached to the state machine's role.

Always review the emitted policy before deploying. Common reasons to adjust:
  - You want to scope resources to specific ARNs rather than "*"
  - You are using resource-based policies (e.g. SQS queue policies) instead
  - You have encryption keys (KMS) not listed here
  - You are using Lambda aliases/versions and want stricter scoping
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any


# -- Mapping table ---------------------------------------------------------

# Each entry is (regex on Resource, list of IAM actions required for execution role).
# Patterns are evaluated in order; first match wins.
_RULES: list[tuple[re.Pattern[str], list[str], str]] = [
    # Lambda invoke (sync/async/callback all use the same action)
    (re.compile(r"^arn:aws[a-z\-]*:states:::lambda:invoke(\.waitForTaskToken)?$"),
     ["lambda:InvokeFunction"], "lambda"),

    # Nested state machines
    (re.compile(r"^arn:aws[a-z\-]*:states:::states:startExecution\.sync(:2)?$"),
     ["states:StartExecution", "states:DescribeExecution", "states:StopExecution",
      "events:PutTargets", "events:PutRule", "events:DescribeRule"], "nested-sync"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::states:startExecution(\.waitForTaskToken)?$"),
     ["states:StartExecution"], "nested"),

    # DynamoDB optimized
    (re.compile(r"^arn:aws[a-z\-]*:states:::dynamodb:getItem$"),
     ["dynamodb:GetItem"], "ddb"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::dynamodb:putItem$"),
     ["dynamodb:PutItem"], "ddb"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::dynamodb:updateItem$"),
     ["dynamodb:UpdateItem"], "ddb"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::dynamodb:deleteItem$"),
     ["dynamodb:DeleteItem"], "ddb"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::aws-sdk:dynamodb:query$"),
     ["dynamodb:Query"], "ddb"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::aws-sdk:dynamodb:scan$"),
     ["dynamodb:Scan"], "ddb"),

    # SNS / SQS
    (re.compile(r"^arn:aws[a-z\-]*:states:::sns:publish(\.waitForTaskToken)?$"),
     ["sns:Publish"], "sns"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::sqs:sendMessage(\.waitForTaskToken)?$"),
     ["sqs:SendMessage"], "sqs"),

    # EventBridge
    (re.compile(r"^arn:aws[a-z\-]*:states:::events:putEvents(\.waitForTaskToken)?$"),
     ["events:PutEvents"], "events"),

    # ECS
    (re.compile(r"^arn:aws[a-z\-]*:states:::ecs:runTask\.sync$"),
     ["ecs:RunTask", "ecs:StopTask", "ecs:DescribeTasks", "iam:PassRole",
      "events:PutTargets", "events:PutRule", "events:DescribeRule"], "ecs-sync"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::ecs:runTask(\.waitForTaskToken)?$"),
     ["ecs:RunTask", "iam:PassRole"], "ecs"),

    # Batch
    (re.compile(r"^arn:aws[a-z\-]*:states:::batch:submitJob\.sync(:2)?$"),
     ["batch:SubmitJob", "batch:DescribeJobs", "batch:TerminateJob",
      "events:PutTargets", "events:PutRule", "events:DescribeRule"], "batch-sync"),

    # Glue
    (re.compile(r"^arn:aws[a-z\-]*:states:::glue:startJobRun\.sync$"),
     ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"],
     "glue-sync"),
    (re.compile(r"^arn:aws[a-z\-]*:states:::glue:startJobRun(\.waitForTaskToken)?$"),
     ["glue:StartJobRun"], "glue"),

    # SageMaker (training/processing are the most common)
    (re.compile(r"^arn:aws[a-z\-]*:states:::sagemaker:createTrainingJob\.sync$"),
     ["sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob",
      "sagemaker:StopTrainingJob", "iam:PassRole",
      "events:PutTargets", "events:PutRule", "events:DescribeRule"], "sm-sync"),

    # Athena
    (re.compile(r"^arn:aws[a-z\-]*:states:::athena:startQueryExecution\.sync$"),
     ["athena:StartQueryExecution", "athena:GetQueryExecution",
      "athena:GetQueryResults", "athena:StopQueryExecution"], "athena-sync"),

    # API Gateway
    (re.compile(r"^arn:aws[a-z\-]*:states:::apigateway:invoke(\.waitForTaskToken)?$"),
     ["execute-api:Invoke"], "apigateway"),

    # HTTP Tasks (EventBridge Connections)
    (re.compile(r"^arn:aws[a-z\-]*:states:::http:invoke$"),
     ["events:RetrieveConnectionCredentials",
      "secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"], "http"),

    # Generic AWS SDK integration: arn:aws:states:::aws-sdk:SVC:ACTION
    (re.compile(r"^arn:aws[a-z\-]*:states:::aws-sdk:([a-z0-9\-]+):([a-zA-Z0-9]+)(\.waitForTaskToken)?$"),
     ["__DYNAMIC_AWS_SDK__"], "aws-sdk"),
]


def _infer_for_resource(resource: str) -> list[str]:
    for pattern, actions, _tag in _RULES:
        m = pattern.match(resource)
        if not m:
            continue
        if actions == ["__DYNAMIC_AWS_SDK__"]:
            service = m.group(1)
            action = m.group(2)
            # camelCase → PascalCase (common IAM convention, good enough as a guess)
            pascal = action[:1].upper() + action[1:]
            return [f"{service}:{pascal}"]
        return list(actions)
    return []


# -- Document walking ------------------------------------------------------


def _collect_tasks(machine: dict, out: list[tuple[str, str]]) -> None:
    """Collect (state_path, Resource) pairs for every Task in this machine."""
    states = machine.get("States") or {}
    for name, state in states.items():
        if not isinstance(state, dict):
            continue
        if state.get("Type") == "Task":
            resource = state.get("Resource")
            if isinstance(resource, str):
                out.append((name, resource))
        elif state.get("Type") == "Parallel":
            for i, branch in enumerate(state.get("Branches") or []):
                _collect_tasks(branch, out)
        elif state.get("Type") == "Map":
            processor = state.get("ItemProcessor") or {}
            _collect_tasks(processor, out)
            # Map may also have ResultWriter / ItemReader S3 resources
            reader = state.get("ItemReader") or {}
            if isinstance(reader.get("Resource"), str):
                out.append((f"{name}.ItemReader", reader["Resource"]))
            writer = state.get("ResultWriter") or {}
            if isinstance(writer.get("Resource"), str):
                out.append((f"{name}.ResultWriter", writer["Resource"]))


def infer_policy(doc: dict, include_logging: bool = True,
                 include_xray: bool = True) -> dict:
    """
    Return a PolicyDocument dict. `include_logging` adds the CloudWatch Logs
    actions needed when the state machine has a LoggingConfiguration;
    `include_xray` adds X-Ray actions needed when tracing is enabled.

    Each Task's inferred actions are grouped into its own Statement with a
    Sid derived from the state name, making the resulting policy easier to
    read and scope.
    """
    statements: list[dict] = []
    tasks: list[tuple[str, str]] = []
    _collect_tasks(doc, tasks)

    # Deduplicate by (state_name, resource) to preserve state-level grouping
    # while collapsing repeated resource patterns.
    seen: set[tuple[str, str]] = set()
    for name, resource in tasks:
        if (name, resource) in seen:
            continue
        seen.add((name, resource))
        actions = _infer_for_resource(resource)
        if not actions:
            statements.append({
                "Sid": f"UnknownResource{_sid_safe(name)}",
                "Effect": "Allow",
                "Action": ["# UNKNOWN — add manually"],
                "Resource": "*",
                "Comment": f"Could not infer IAM actions for Resource: {resource}",
            })
            continue
        statements.append({
            "Sid": f"{_sid_safe(name)}",
            "Effect": "Allow",
            "Action": actions,
            "Resource": "*",
        })

    if include_logging:
        statements.append({
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogDelivery",
                "logs:GetLogDelivery",
                "logs:UpdateLogDelivery",
                "logs:DeleteLogDelivery",
                "logs:ListLogDeliveries",
                "logs:PutResourcePolicy",
                "logs:DescribeResourcePolicies",
                "logs:DescribeLogGroups",
                "logs:PutLogEvents",
            ],
            "Resource": "*",
        })

    if include_xray:
        statements.append({
            "Sid": "XRay",
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets",
            ],
            "Resource": "*",
        })

    return {"Version": "2012-10-17", "Statement": statements}


_SID_SAFE = re.compile(r"[^A-Za-z0-9]")


def _sid_safe(s: str) -> str:
    return _SID_SAFE.sub("", s) or "Unnamed"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: _infer_iam.py <path-to-asl.json>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1]) as f:
        doc = json.load(f)
    print(json.dumps(infer_policy(doc), indent=2))
