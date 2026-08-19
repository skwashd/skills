"""
Thin wrapper around `aws stepfunctions validate-state-machine-definition`.

This is the authoritative JSONata-aware validator. We run it at severity
WARNING so informational diagnostics are surfaced. Returns a structured
result the orchestrator can fold into its issue list.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class AwsValidateResult:
    ok: bool
    result: str  # "OK" | "FAIL" | "UNAVAILABLE"
    diagnostics: list[dict] = field(default_factory=list)
    error: str = ""


def run(definition_path: str, target_type: str = "STANDARD",
        timeout_s: float = 30.0) -> AwsValidateResult:
    cli = shutil.which("aws")
    if cli is None:
        return AwsValidateResult(ok=False, result="UNAVAILABLE",
                                 error="aws CLI not found on PATH")
    try:
        with open(definition_path) as f:
            definition = f.read()
    except OSError as e:
        return AwsValidateResult(ok=False, result="UNAVAILABLE",
                                 error=f"cannot read definition file: {e}")

    try:
        proc = subprocess.run(
            [cli, "stepfunctions", "validate-state-machine-definition",
             "--definition", definition,
             "--type", target_type,
             "--severity", "WARNING",
             "--output", "json"],
            capture_output=True, timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return AwsValidateResult(ok=False, result="UNAVAILABLE",
                                 error="aws CLI call timed out")
    except OSError as e:
        return AwsValidateResult(ok=False, result="UNAVAILABLE",
                                 error=f"cli exec error: {e}")

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        return AwsValidateResult(
            ok=False, result="UNAVAILABLE",
            error=f"aws CLI failed (rc={proc.returncode}): {stderr or stdout}"
        )

    try:
        response = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as e:
        return AwsValidateResult(ok=False, result="UNAVAILABLE",
                                 error=f"could not parse aws response: {e}")

    result_code = response.get("result", "UNKNOWN")
    diagnostics = response.get("diagnostics", []) or []
    ok = result_code == "OK"
    return AwsValidateResult(ok=ok, result=result_code, diagnostics=diagnostics)
