#!/usr/bin/env python3
"""
Validate an AWS Step Functions ASL document in JSONata mode.

Runs four layers, in order:

  L1  JSON Schema (JSONata-only, Draft 2020-12)
  L2  Graph + JSONata syntax + $states scope + IAM inference
  L3  `aws stepfunctions validate-state-machine-definition`   (needs creds)
  L4  `aws stepfunctions test-state`, per state, with mocks    (opt-in, needs creds)

Exit codes:
  0  clean (L1+L2 passed; L3/L4 either passed or were skipped with a banner)
  1  errors (at least one ERROR-severity issue in L1/L2/L3)
  2  warnings only (L1+L2 clean, warnings present)
  3  clean locally but dynamic layers were skipped because of missing creds

Usage:
  python scripts/validate.py workflow.asl.json
  python scripts/validate.py workflow.asl.json --target-type EXPRESS
  python scripts/validate.py workflow.asl.json --test-states --role-arn arn:aws:iam::...:role/...
  python scripts/validate.py workflow.asl.json --json         # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

# Make scripts/ importable regardless of where we're invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _graph_analyze  # noqa: E402
import _infer_iam      # noqa: E402
import _jsonata_syntax as _jsyntax  # noqa: E402
import _probe_creds    # noqa: E402


try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:
    print("ERROR: jsonschema is required. Install with: pip install jsonschema",
          file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Pretty output
# ---------------------------------------------------------------------------

# Do not emit ANSI colors when stdout is not a TTY.
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def _c(code: str, s: str) -> str:
    if not _USE_COLOR:
        return s
    return f"\033[{code}m{s}\033[0m"


_SEV_LABEL = {
    "error":   _c("31;1", "ERROR"),    # red bold
    "warning": _c("33;1", "WARN "),    # yellow bold
    "info":    _c("36",   "INFO "),    # cyan
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@dataclass
class ValidateReport:
    issues: list[_graph_analyze.Issue] = field(default_factory=list)
    schema_errors: list[dict] = field(default_factory=list)
    jsonata_errors: list[tuple[str, str]] = field(default_factory=list)
    aws_validate_diagnostics: list[dict] = field(default_factory=list)
    aws_validate_unavailable_reason: str = ""
    test_state_results: list[dict] = field(default_factory=list)
    creds_reason: str = ""
    creds_ok: bool = False
    dynamic_skipped: bool = False
    iam_policy: dict = field(default_factory=dict)


def _load_schema() -> dict:
    schema_path = os.path.join(_HERE, "..", "schemas", "asl-jsonata.schema.json")
    with open(schema_path) as f:
        return json.load(f)


_JSONPATH_LEGACY_FIELDS = {
    "InputPath", "OutputPath", "Parameters", "ResultSelector", "ResultPath",
    "Result", "ItemsPath", "MaxConcurrencyPath", "MaxItemsPath",
    "MaxItemsPerBatchPath", "MaxInputBytesPerBatchPath",
    "ToleratedFailureCountPath", "ToleratedFailurePercentagePath",
    "TimeoutSecondsPath", "HeartbeatSecondsPath",
    "SecondsPath", "TimestampPath", "ErrorPath", "CausePath", "Iterator",
}
_JSONPATH_CHOICE_OPERATORS = {
    "Variable", "And", "Or", "Not",
    "StringEquals", "StringEqualsPath", "StringLessThan", "StringLessThanPath",
    "StringGreaterThan", "StringGreaterThanPath", "StringLessThanEquals",
    "StringLessThanEqualsPath", "StringGreaterThanEquals", "StringMatches",
    "NumericEquals", "NumericEqualsPath", "NumericLessThan",
    "NumericLessThanPath", "NumericGreaterThan", "NumericGreaterThanPath",
    "NumericLessThanEquals", "NumericGreaterThanEquals",
    "BooleanEquals", "BooleanEqualsPath",
    "TimestampEquals", "TimestampEqualsPath", "TimestampLessThan",
    "TimestampLessThanPath", "TimestampGreaterThan",
    "TimestampGreaterThanPath", "TimestampLessThanEquals",
    "TimestampGreaterThanEquals",
    "IsPresent", "IsNull", "IsNumeric", "IsString", "IsBoolean", "IsTimestamp",
}


def _explain_schema_error(err, instance) -> str:
    """Turn a jsonschema error into a short, human-friendly message."""
    # Primary intervention: detect JSONPath-era fields in state objects and
    # name them explicitly rather than dumping the whole state body.
    if isinstance(instance, dict):
        found_legacy = [k for k in instance if k in _JSONPATH_LEGACY_FIELDS]
        if found_legacy:
            return (f"JSONPath-era field(s) forbidden in JSONata mode: "
                    f"{', '.join(found_legacy)}")
        if instance.get("Type") == "Choice":
            legacy_choice = [
                k for rule in (instance.get("Choices") or []) if isinstance(rule, dict)
                for k in rule if k in _JSONPATH_CHOICE_OPERATORS
            ]
            if legacy_choice:
                uniq = sorted(set(legacy_choice))
                return (f"Choice rule uses JSONPath operator(s) {', '.join(uniq)}; "
                        "in JSONata mode, Choice rules have only Condition and Next "
                        "(plus optional Output/Assign/Comment)")
    return err.message


def run_layer_1(doc: dict) -> list[dict]:
    """JSON Schema validation. Returns a list of error dicts with path + message."""
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(doc):
        # Build JSON Pointer-ish path
        path = "$"
        for part in err.absolute_path:
            if isinstance(part, int):
                path += f"[{part}]"
            else:
                path += f".{part}"
        errors.append({
            "path": path,
            "message": _explain_schema_error(err, err.instance),
            "validator": err.validator,
        })
    return errors


def run_layer_2(doc: dict, target_type: str) -> tuple[
    _graph_analyze.AnalysisResult, list[tuple[str, str]]
]:
    """Graph analysis + per-expression JSONata syntax check."""
    analysis = _graph_analyze.analyze(doc, target_type=target_type)
    jsonata_errors = _jsyntax.walk_and_check(doc)
    return analysis, jsonata_errors


def run_layer_3(definition_str: str, target_type: str) -> Any:
    """AWS official validator. Returns AwsValidateResult."""
    import _aws_validate
    return _aws_validate.run_from_string(definition_str, target_type) \
        if hasattr(_aws_validate, "run_from_string") else None


def _aws_validate_from_path(path: str, target_type: str):
    import _aws_validate
    return _aws_validate.run(path, target_type)


def run_layer_4(definition_str: str, doc: dict, role_arn: str | None) -> list[dict]:
    import _aws_test_state
    results = _aws_test_state.run_all(
        definition_str, doc.get("States") or {}, role_arn
    )
    return [
        {
            "state_name": r.state_name, "ok": r.ok, "status": r.status,
            "error": r.error, "next_state": r.next_state,
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_banner(text: str) -> None:
    line = "─" * min(len(text), 78)
    print(line)
    print(text)
    print(line)


def _print_human(report: ValidateReport, show_iam: bool) -> None:
    _print_banner("Layer 1 — JSON Schema")
    if not report.schema_errors:
        print(_c("32", "  ✓ schema clean"))
    else:
        for e in report.schema_errors:
            print(f"  {_SEV_LABEL['error']} {e['path']}: {e['message']}")

    _print_banner("Layer 2 — Graph & JSONata")
    for e_path, e_msg in report.jsonata_errors:
        print(f"  {_SEV_LABEL['error']} {e_path}: {e_msg}")
    for issue in report.issues:
        print(f"  {_SEV_LABEL[issue.severity]} [{issue.code}] {issue.path}: {issue.message}")
    if not report.issues and not report.jsonata_errors:
        print(_c("32", "  ✓ graph clean"))

    _print_banner("Layer 3 — aws validate-state-machine-definition")
    if report.aws_validate_unavailable_reason:
        print(_c("33", f"  ⚠ skipped: {report.aws_validate_unavailable_reason}"))
    elif not report.aws_validate_diagnostics:
        print(_c("32", "  ✓ AWS validation clean"))
    else:
        for d in report.aws_validate_diagnostics:
            sev = d.get("severity", "ERROR").lower()
            label = _SEV_LABEL.get(
                "error" if sev.startswith("error") else "warning", sev.upper()
            )
            print(f"  {label} [{d.get('code','')}] {d.get('location','')}: {d.get('message','')}")

    if report.test_state_results:
        _print_banner("Layer 4 — test-state (per state)")
        for r in report.test_state_results:
            icon = _c("32", "✓") if r["ok"] else _c("31", "✗")
            line = f"  {icon} {r['state_name']} status={r['status']}"
            if r.get("next_state"):
                line += f" → {r['next_state']}"
            if r.get("error"):
                line += f"  {r['error']}"
            print(line)

    if report.creds_reason and not report.creds_ok:
        _print_banner("Credentials")
        print(_c("33", f"  ⚠ AWS creds unavailable ({report.creds_reason}); "
                        "L3/L4 were skipped"))

    if show_iam and report.iam_policy:
        _print_banner("Proposed IAM execution-role policy (review before deploying)")
        print(json.dumps(report.iam_policy, indent=2))


def _print_json(report: ValidateReport) -> None:
    print(json.dumps({
        "schema_errors": report.schema_errors,
        "jsonata_errors": [{"path": p, "message": m} for p, m in report.jsonata_errors],
        "issues": [
            {"severity": i.severity, "code": i.code, "path": i.path, "message": i.message}
            for i in report.issues
        ],
        "aws_validate": {
            "diagnostics": report.aws_validate_diagnostics,
            "skipped_reason": report.aws_validate_unavailable_reason,
        },
        "test_state_results": report.test_state_results,
        "credentials": {"ok": report.creds_ok, "reason": report.creds_reason},
        "iam_policy": report.iam_policy,
    }, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Validate a JSONata-mode Step Functions ASL file.")
    ap.add_argument("path", help="path to the ASL JSON file")
    ap.add_argument("--target-type", choices=["STANDARD", "EXPRESS"], default="STANDARD")
    ap.add_argument("--test-states", action="store_true",
                    help="also run `aws stepfunctions test-state` per state (requires creds)")
    ap.add_argument("--role-arn",
                    help="execution-role ARN for non-mocked test-state calls")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of human output")
    ap.add_argument("--show-iam", action="store_true",
                    help="print proposed IAM execution-role policy")
    ap.add_argument("--no-aws", action="store_true",
                    help="skip L3/L4 even if creds are present")
    args = ap.parse_args(argv)

    try:
        with open(args.path) as f:
            raw = f.read()
            doc = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read or parse {args.path}: {e}", file=sys.stderr)
        return 1

    report = ValidateReport()

    # L1
    report.schema_errors = run_layer_1(doc)

    # L2
    analysis, jsonata_errors = run_layer_2(doc, args.target_type)
    report.issues = analysis.issues
    report.jsonata_errors = jsonata_errors

    # IAM preview
    try:
        report.iam_policy = _infer_iam.infer_policy(doc)
    except Exception as e:  # noqa: BLE001
        report.iam_policy = {"error": str(e)}

    # L3 / L4 gate
    if not args.no_aws:
        ok, reason = _probe_creds.probe()
        report.creds_ok, report.creds_reason = ok, reason
        if ok:
            res = _aws_validate_from_path(args.path, args.target_type)
            if res.result == "UNAVAILABLE":
                report.aws_validate_unavailable_reason = res.error
            else:
                report.aws_validate_diagnostics = res.diagnostics
            if args.test_states:
                report.test_state_results = run_layer_4(raw, doc, args.role_arn)
        else:
            report.aws_validate_unavailable_reason = f"no credentials: {reason}"
            report.dynamic_skipped = True
    else:
        report.aws_validate_unavailable_reason = "--no-aws specified"
        report.dynamic_skipped = True

    # Emit
    if args.json:
        _print_json(report)
    else:
        _print_human(report, show_iam=args.show_iam)

    # Exit code
    has_l1 = bool(report.schema_errors)
    has_l2_err = any(i.severity == "error" for i in report.issues) or bool(report.jsonata_errors)
    has_l3_err = any(
        (d.get("severity", "ERROR")).upper().startswith("ERROR")
        for d in report.aws_validate_diagnostics
    )
    has_l4_err = any(not r["ok"] for r in report.test_state_results)
    if has_l1 or has_l2_err or has_l3_err or has_l4_err:
        return 1
    has_warnings = any(i.severity == "warning" for i in report.issues) or any(
        (d.get("severity", "")).upper() == "WARNING"
        for d in report.aws_validate_diagnostics
    )
    if has_warnings:
        return 2
    if report.dynamic_skipped:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
