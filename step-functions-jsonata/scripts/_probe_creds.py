"""
Probe for AWS credentials without failing noisily when none are present.

The probe is designed to:
  - Return quickly (<5s) when AWS is unreachable or creds are misconfigured
  - Never raise — always return a (bool, reason) pair
  - Work without boto3 being installed (boto3 is optional)
"""
from __future__ import annotations

import os
import shutil
import subprocess


_ENV_MARKERS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_PROFILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
)
_CRED_FILES = ("~/.aws/credentials", "~/.aws/config")


def probe(timeout_s: float = 5.0) -> tuple[bool, str]:
    """
    Return (ok, reason).

    `ok` is True only when both the local configuration suggests credentials
    exist AND an actual STS GetCallerIdentity call succeeds. Otherwise returns
    a short machine-readable reason code.
    """
    # Step 1: cheap local check — is anything configured at all?
    has_env = any(os.environ.get(k) for k in _ENV_MARKERS)
    has_file = any(os.path.exists(os.path.expanduser(p)) for p in _CRED_FILES)
    if not (has_env or has_file):
        return False, "no_credentials_configured"

    # Step 2: actually call STS.
    # Prefer boto3 when installed (fast, structured errors).
    # Fall back to the AWS CLI if available.
    boto_result = _probe_with_boto3(timeout_s)
    if boto_result is not None:
        return boto_result
    cli_result = _probe_with_cli(timeout_s)
    if cli_result is not None:
        return cli_result
    return False, "no_probe_mechanism_available"


def _probe_with_boto3(timeout_s: float) -> tuple[bool, str] | None:
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
        from botocore.exceptions import (  # type: ignore
            NoCredentialsError, PartialCredentialsError, ClientError,
            EndpointConnectionError, ProfileNotFound,
        )
    except ImportError:
        return None

    cfg = Config(connect_timeout=timeout_s, read_timeout=timeout_s,
                 retries={"max_attempts": 1})
    try:
        boto3.client("sts", config=cfg).get_caller_identity()
        return True, "ok"
    except (NoCredentialsError, PartialCredentialsError, ProfileNotFound):
        return False, "credentials_missing_or_partial"
    except EndpointConnectionError:
        return False, "network_unreachable"
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        rejected = {"ExpiredToken", "InvalidClientTokenId",
                    "SignatureDoesNotMatch", "AccessDenied"}
        if code in rejected:
            return False, f"credentials_rejected:{code}"
        return False, f"client_error:{code}"
    except Exception as e:  # noqa: BLE001
        return False, f"unexpected:{type(e).__name__}"


def _probe_with_cli(timeout_s: float) -> tuple[bool, str] | None:
    cli = shutil.which("aws")
    if cli is None:
        return None
    try:
        result = subprocess.run(
            [cli, "sts", "get-caller-identity", "--output", "text"],
            capture_output=True, timeout=timeout_s + 2,
        )
    except subprocess.TimeoutExpired:
        return False, "network_unreachable"
    except OSError as e:
        return False, f"cli_exec_error:{e}"
    if result.returncode == 0:
        return True, "ok"
    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
    if "Unable to locate credentials" in stderr:
        return False, "credentials_missing_or_partial"
    if "ExpiredToken" in stderr or "InvalidClientTokenId" in stderr:
        return False, "credentials_rejected"
    if "Could not connect" in stderr or "EndpointConnectionError" in stderr:
        return False, "network_unreachable"
    return False, "cli_error"


if __name__ == "__main__":
    ok, reason = probe()
    print(f"credentials: {'OK' if ok else 'absent/invalid'} ({reason})")
