"""Publish provisioning request events to the provisioner bus."""

import json

import boto3

_events = boto3.client("events")


def request_bucket(name: str, owner: str) -> None:
    """Ask the provisioner to create an S3 bucket."""
    _events.put_events(
        Entries=[
            {
                "EventBusName": "sandy-provisioner",
                "Source": "sandy.manager",
                "DetailType": "Bucket Create Requested",
                "Detail": json.dumps(
                    {
                        "resourceType": "s3_bucket",
                        "name": name,
                        "owner": owner,
                    }
                ),
            }
        ]
    )
