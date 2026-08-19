#!/usr/bin/env python3
"""
Emit a raw CloudFormation template that deploys a Step Functions state machine.

For portability and smaller workflows, we inline the ASL in DefinitionString
with Fn::Sub handling placeholder substitution. For larger workflows (>51,200
template bytes), the emitter falls back to DefinitionS3Location — you will
need to upload the ASL file to S3 separately.

Usage:
    python scripts/deploy/emit_cloudformation.py \
        --asl path/to/workflow.asl.json \
        --name my-state-machine \
        --type STANDARD \
        --outdir cfn/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))

import _infer_iam  # noqa: E402


_INLINE_SOFT_LIMIT = 40_000  # CFN cap is 51,200; leave headroom


def _find_placeholders(asl_text: str) -> list[str]:
    pat = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    return sorted(set(pat.findall(asl_text)))


def _build_template(name: str, asl_text: str, sfn_type: str,
                    placeholders: list[str], policy: dict,
                    use_s3: bool) -> dict:
    parameters = {p: {"Type": "String",
                      "Description": f"Value for ${{{p}}} in the state machine definition"}
                  for p in placeholders}
    if use_s3:
        parameters["DefinitionBucket"] = {"Type": "String"}
        parameters["DefinitionKey"] = {"Type": "String"}

    log_group = {
        "Type": "AWS::Logs::LogGroup",
        "Properties": {
            "LogGroupName": {"Fn::Sub": "/aws/vendedlogs/states/${AWS::StackName}"},
            "RetentionInDays": 14,
        },
    }

    role = {
        "Type": "AWS::IAM::Role",
        "Properties": {
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "states.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }],
            },
            "Policies": [{
                "PolicyName": "inline",
                "PolicyDocument": policy,
            }],
        },
    }

    state_machine_props: dict = {
        "StateMachineName": name,
        "StateMachineType": sfn_type,
        "RoleArn": {"Fn::GetAtt": ["StateMachineRole", "Arn"]},
        "LoggingConfiguration": {
            "Level": "ALL",
            "IncludeExecutionData": True,
            "Destinations": [{
                "CloudWatchLogsLogGroup": {
                    "LogGroupArn": {"Fn::GetAtt": ["StateMachineLogGroup", "Arn"]}
                }
            }],
        },
        "TracingConfiguration": {"Enabled": True},
        "DefinitionSubstitutions": {p: {"Ref": p} for p in placeholders},
    }
    if use_s3:
        state_machine_props["DefinitionS3Location"] = {
            "Bucket": {"Ref": "DefinitionBucket"},
            "Key": {"Ref": "DefinitionKey"},
        }
    else:
        # Inline as a JSON string; CloudFormation will apply Substitutions.
        state_machine_props["DefinitionString"] = asl_text

    state_machine = {
        "Type": "AWS::StepFunctions::StateMachine",
        "DependsOn": "StateMachineRole",
        "Properties": state_machine_props,
    }

    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"{name} state machine (JSONata)",
        "Parameters": parameters,
        "Resources": {
            "StateMachineLogGroup": log_group,
            "StateMachineRole": role,
            "StateMachine": state_machine,
        },
        "Outputs": {
            "StateMachineArn": {"Value": {"Ref": "StateMachine"}}
        },
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asl", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--type", default="STANDARD", choices=["STANDARD", "EXPRESS"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--force-s3", action="store_true",
                    help="always use DefinitionS3Location (default: auto by size)")
    args = ap.parse_args(argv)

    with open(args.asl) as f:
        asl_text = f.read()
    json.loads(asl_text)  # sanity check

    os.makedirs(args.outdir, exist_ok=True)
    asl_basename = os.path.basename(args.asl)
    with open(os.path.join(args.outdir, asl_basename), "w") as f:
        f.write(asl_text)

    placeholders = _find_placeholders(asl_text)
    use_s3 = args.force_s3 or len(asl_text) > _INLINE_SOFT_LIMIT

    policy = _infer_iam.infer_policy(json.loads(asl_text))
    # Strip comment entries for CFN
    for stmt in policy.get("Statement", []):
        stmt.pop("Comment", None)
        stmt["Action"] = [a for a in stmt["Action"] if not a.startswith("#")]

    template = _build_template(args.name, asl_text, args.type, placeholders, policy, use_s3)

    out_path = os.path.join(args.outdir, "template.json")
    with open(out_path, "w") as f:
        json.dump(template, f, indent=2)

    print(f"wrote {out_path} ({'S3-referenced' if use_s3 else 'inline'} ASL)")
    if use_s3:
        print("upload the ASL to S3, then pass --parameter-overrides DefinitionBucket=... "
              "DefinitionKey=... to deploy")
    else:
        print("deploy with: aws cloudformation deploy --template-file template.json "
              "--stack-name ... --capabilities CAPABILITY_IAM --parameter-overrides ...")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
