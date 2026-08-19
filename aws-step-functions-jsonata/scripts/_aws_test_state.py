"""
Thin wrapper around `aws stepfunctions test-state`.

We test states one at a time. For states that require mocks (Map, Parallel,
Activity, .sync, .sync:2, .waitForTaskToken), we emit a minimal success mock
based on the Resource pattern so the state can exercise its I/O transforms.

This is a sanity-check layer, not a substitute for real integration tests.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class TestStateResult:
    state_name: str
    ok: bool
    status: str = ""
    error: str = ""
    next_state: str = ""
    inspection: dict = field(default_factory=dict)


def _needs_mock(state: dict) -> bool:
    t = state.get("Type")
    if t in ("Map", "Parallel"):
        return True
    if t == "Task":
        r = state.get("Resource", "")
        if ":activity:" in r:
            return True
        if ".sync" in r or r.endswith(":2") or ".waitForTaskToken" in r:
            return True
    return False


def _default_mock(state: dict) -> dict:
    """Emit a minimal STRICT mock that returns an empty result object."""
    return {
        "result": {},
        "fieldValidationMode": "NONE",
    }


def run_one(
    state_machine_definition_str: str,
    state_name: str,
    state_body: dict,
    role_arn: str | None,
    sample_input: dict | None,
    timeout_s: float = 30.0,
) -> TestStateResult:
    cli = shutil.which("aws")
    if cli is None:
        return TestStateResult(state_name=state_name, ok=False,
                               error="aws CLI not found on PATH")

    args = [
        cli, "stepfunctions", "test-state",
        "--definition", state_machine_definition_str,
        "--state-name", state_name,
        "--inspection-level", "DEBUG",
        "--output", "json",
    ]
    if sample_input is not None:
        args.extend(["--input", json.dumps(sample_input)])

    if _needs_mock(state_body):
        args.extend(["--mock", json.dumps(_default_mock(state_body))])
    else:
        if role_arn is None:
            return TestStateResult(state_name=state_name, ok=False,
                                   error="role-arn required for non-mocked test-state")
        args.extend(["--role-arn", role_arn])

    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return TestStateResult(state_name=state_name, ok=False,
                               error="aws test-state timed out")

    stdout = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        return TestStateResult(state_name=state_name, ok=False,
                               error=f"cli rc={proc.returncode}: {stderr or stdout}")

    try:
        response = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as e:
        return TestStateResult(state_name=state_name, ok=False,
                               error=f"could not parse aws response: {e}")

    status = response.get("status", "")
    ok = status == "SUCCEEDED"
    err = response.get("error", "") or ""
    cause = response.get("cause", "") or ""
    return TestStateResult(
        state_name=state_name,
        ok=ok,
        status=status,
        error=f"{err} {cause}".strip(),
        next_state=response.get("nextState", ""),
        inspection=response.get("inspectionData", {}) or {},
    )


def run_all(
    definition_str: str,
    states: dict,
    role_arn: str | None,
    sample_input: dict | None = None,
) -> list[TestStateResult]:
    results: list[TestStateResult] = []
    for name, body in states.items():
        if not isinstance(body, dict):
            continue
        results.append(run_one(definition_str, name, body, role_arn, sample_input))
    return results
