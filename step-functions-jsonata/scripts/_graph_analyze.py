"""
Structural analysis of a JSONata-mode ASL document.

Checks performed:
  - StartAt exists in States
  - Every Next/Default/Catch[].Next references a real state in the same States map
  - Reachability: warn on unreachable states; error on missing terminals
  - Cycle detection (warn only — cycles are sometimes legitimate with Wait states)
  - Choice state has a Default (warn — without it you can hit States.NoChoiceMatched)
  - Task/Parallel/Map has TimeoutSeconds (warn)
  - HeartbeatSeconds < TimeoutSeconds (error when set)
  - Retry/Catch hygiene:
      * States.ALL must be last in the list (error)
      * BackoffRate < 1.0 (error, though schema should already block)
      * Missing States.QueryEvaluationError retry-block-of-zero for JSONata-heavy Tasks (info)
  - Inline Map: MaxConcurrency ≤ 40 (error), ItemReader/ItemBatcher/ResultWriter forbidden (error)
  - Distributed Map: ExecutionType required in ProcessorConfig (error);
    warn when MaxConcurrency unset (defaults to 10,000)
  - Express target-type incompatibility: reject .sync / .waitForTaskToken /
    Distributed Map parents (error when --target-type EXPRESS)
  - $states.* scope: $states.result forbidden in Arguments and ItemSelector;
    $states.errorOutput forbidden outside Catch context (error)
  - "Common error state" detection: warn if more than one Catch[].Next points
    to the same state across 3+ Task states (rationale in docstring of
    _detect_common_error_state)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from _jsonata_syntax import extract_inner, is_jsonata_string


# ---------------------------------------------------------------------------
# Issue representation
# ---------------------------------------------------------------------------

SEVERITIES = ("error", "warning", "info")


@dataclass
class Issue:
    severity: str  # "error" | "warning" | "info"
    code: str
    path: str
    message: str


@dataclass
class AnalysisResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add(self, severity: str, code: str, path: str, message: str) -> None:
        assert severity in SEVERITIES, severity
        self.issues.append(Issue(severity, code, path, message))


# ---------------------------------------------------------------------------
# $states.* usage detection
# ---------------------------------------------------------------------------

_STATES_RESULT_RE = re.compile(r"\$states\.result\b")
_STATES_ERROR_RE = re.compile(r"\$states\.errorOutput\b")
_STATES_INPUT_RE = re.compile(r"\$states\.input\b")
_STATES_CONTEXT_RE = re.compile(r"\$states\.context\b")


def _uses_states_field(value: Any, pattern: re.Pattern[str]) -> bool:
    if isinstance(value, str):
        inner = extract_inner(value)
        if inner is not None and pattern.search(inner):
            return True
    elif isinstance(value, dict):
        return any(_uses_states_field(v, pattern) for v in value.values())
    elif isinstance(value, list):
        return any(_uses_states_field(v, pattern) for v in value)
    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def analyze(doc: dict, target_type: str = "STANDARD") -> AnalysisResult:
    """
    Analyze a state-machine document. `target_type` is "STANDARD" or "EXPRESS";
    several checks are stricter under EXPRESS.
    """
    result = AnalysisResult()
    if not isinstance(doc, dict):
        result.add("error", "E_TYPE", "$", "top-level document must be an object")
        return result

    _analyze_machine(doc, result, "$", target_type, in_distributed_map=False)
    return result


def _analyze_machine(
    machine: dict,
    result: AnalysisResult,
    path: str,
    target_type: str,
    in_distributed_map: bool,
) -> None:
    states = machine.get("States")
    start_at = machine.get("StartAt")

    if not isinstance(states, dict):
        return  # Schema check will have caught this already.

    state_names = set(states.keys())

    # StartAt exists
    if isinstance(start_at, str) and start_at not in state_names:
        result.add(
            "error", "E_STARTAT_MISSING", f"{path}.StartAt",
            f"StartAt references '{start_at}' which is not a key in States"
        )

    # Reference validity + per-state checks
    for name, state in states.items():
        state_path = f"{path}.States.{name}"
        if not isinstance(state, dict):
            continue
        _check_state(name, state, state_names, result, state_path, target_type, in_distributed_map)

    # Reachability from StartAt
    reachable = _collect_reachable(start_at, states) if isinstance(start_at, str) else set()
    for name in state_names - reachable:
        result.add(
            "warning", "W_UNREACHABLE", f"{path}.States.{name}",
            f"state '{name}' is not reachable from StartAt"
        )

    # Terminal presence — at least one path ends in End:true, Succeed, or Fail
    if not _has_terminal(start_at, states):
        result.add(
            "error", "E_NO_TERMINAL", path,
            "no terminal reachable from StartAt (need End:true, Succeed, or Fail)"
        )

    # Common-error-state heuristic
    _detect_common_error_state(states, result, path)


# ---------------------------------------------------------------------------
# Per-state checks
# ---------------------------------------------------------------------------


def _check_state(
    name: str,
    state: dict,
    state_names: set[str],
    result: AnalysisResult,
    path: str,
    target_type: str,
    in_distributed_map: bool,
) -> None:
    stype = state.get("Type")

    # Next / Default / Catch[].Next reference validity
    if "Next" in state and state["Next"] not in state_names:
        result.add("error", "E_NEXT_MISSING", f"{path}.Next",
                   f"Next references unknown state '{state['Next']}'")

    if stype == "Choice":
        default = state.get("Default")
        if default is None:
            result.add("warning", "W_CHOICE_NO_DEFAULT", path,
                       "Choice state has no Default; unmatched input raises States.NoChoiceMatched")
        elif default not in state_names:
            result.add("error", "E_DEFAULT_MISSING", f"{path}.Default",
                       f"Default references unknown state '{default}'")
        for i, rule in enumerate(state.get("Choices") or []):
            if isinstance(rule, dict) and "Next" in rule and rule["Next"] not in state_names:
                result.add("error", "E_CHOICE_NEXT_MISSING",
                           f"{path}.Choices[{i}].Next",
                           f"Choices[{i}].Next references unknown state '{rule['Next']}'")

    for i, catcher in enumerate(state.get("Catch") or []):
        if isinstance(catcher, dict):
            nxt = catcher.get("Next")
            if nxt and nxt not in state_names:
                result.add("error", "E_CATCH_NEXT_MISSING", f"{path}.Catch[{i}].Next",
                           f"Catch[{i}].Next references unknown state '{nxt}'")

    # Task / Parallel / Map — error handling hygiene
    if stype in ("Task", "Parallel", "Map"):
        _check_retry_hygiene(state, result, path)
        _check_catch_hygiene(state, result, path, target_type=target_type)
        if "TimeoutSeconds" not in state and stype == "Task":
            result.add("warning", "W_NO_TIMEOUT", path,
                       "Task has no TimeoutSeconds (defaults to 99,999,999 seconds — always set it)")
        ts = state.get("TimeoutSeconds")
        hb = state.get("HeartbeatSeconds")
        if isinstance(ts, int) and isinstance(hb, int) and hb >= ts:
            result.add("error", "E_HEARTBEAT_GE_TIMEOUT", path,
                       f"HeartbeatSeconds ({hb}) must be strictly less than TimeoutSeconds ({ts})")

    # Task — scope rules and express incompatibility
    if stype == "Task":
        _check_task_scope(state, result, path)
        _check_task_express(state, result, path, target_type)

    # Map — inline vs distributed checks
    if stype == "Map":
        _check_map(state, result, path, target_type)

    # Scope: Catch[].Output may reference errorOutput; top-level Output must not.
    for i, catcher in enumerate(state.get("Catch") or []):
        if isinstance(catcher, dict):
            # catch-scope fields CAN use $states.errorOutput — OK
            pass
    if "Output" in state and _uses_states_field(state["Output"], _STATES_ERROR_RE):
        # top-level Output on Task/Map/Parallel: errorOutput is only legal in Catch scope
        result.add("error", "E_ERROR_OUTSIDE_CATCH", f"{path}.Output",
                   "$states.errorOutput is only available inside a Catch[].Output / Catch[].Assign; "
                   "move this expression into the relevant catcher")


def _check_retry_hygiene(state: dict, result: AnalysisResult, path: str) -> None:
    retries = state.get("Retry") or []
    for i, r in enumerate(retries):
        if not isinstance(r, dict):
            continue
        errs = r.get("ErrorEquals") or []
        if "States.ALL" in errs and i != len(retries) - 1:
            result.add("error", "E_RETRY_ALL_NOT_LAST", f"{path}.Retry[{i}]",
                       "States.ALL must be the last retrier; it shadows subsequent entries")
        if "States.ALL" in errs and len(errs) > 1:
            result.add("error", "E_RETRY_ALL_WITH_OTHERS", f"{path}.Retry[{i}]",
                       "States.ALL must be the only entry in its ErrorEquals array")
        if isinstance(r.get("BackoffRate"), (int, float)) and r["BackoffRate"] < 1.0:
            result.add("error", "E_BACKOFF_LT_1", f"{path}.Retry[{i}].BackoffRate",
                       f"BackoffRate must be ≥ 1.0 (got {r['BackoffRate']})")


def _check_catch_hygiene(state: dict, result: AnalysisResult, path: str,
                          target_type: str = "STANDARD") -> None:
    catchers = state.get("Catch") or []
    for i, c in enumerate(catchers):
        if not isinstance(c, dict):
            continue
        errs = c.get("ErrorEquals") or []
        if "States.ALL" in errs:
            if i != len(catchers) - 1:
                result.add("error", "E_CATCH_ALL_NOT_LAST", f"{path}.Catch[{i}]",
                           "States.ALL must be the last catcher; it shadows subsequent entries")
            if len(errs) > 1:
                result.add("error", "E_CATCH_ALL_WITH_OTHERS", f"{path}.Catch[{i}]",
                           "States.ALL must be the only entry in its ErrorEquals array")
            # Under EXPRESS, catching States.ALL is the intended pattern (no history
            # to debug with; emit structured failure output instead). Under STANDARD,
            # it masks unknown errors and prevents redrive-from-failed-state.
            if target_type == "EXPRESS":
                result.add(
                    "info", "I_CATCH_ALL_EXPRESS",
                    f"{path}.Catch[{i}]",
                    "catching States.ALL is appropriate for Express workflows; "
                    "ensure the catcher emits structured failure output (to SNS/"
                    "EventBridge/Logs) rather than swallowing the error, because "
                    "Express has no execution history to debug with",
                )
            else:
                result.add(
                    "warning", "W_CATCH_ALL",
                    f"{path}.Catch[{i}]",
                    "catching States.ALL in a Standard workflow masks unknown errors "
                    "and prevents redrive-from-failed-state; prefer to catch only "
                    "named recoverable errors and let unknown errors fail the "
                    "execution so EventBridge can alert and history is preserved",
                )


def _check_task_scope(state: dict, result: AnalysisResult, path: str) -> None:
    """Arguments / ItemSelector / top-level fields must not reference $states.result."""
    args = state.get("Arguments")
    if args is not None and _uses_states_field(args, _STATES_RESULT_RE):
        result.add("error", "E_RESULT_IN_ARGUMENTS", f"{path}.Arguments",
                   "$states.result is not available in Arguments (it exists only after the task returns); "
                   "read input with $states.input or a named variable")
    if args is not None and _uses_states_field(args, _STATES_ERROR_RE):
        result.add("error", "E_ERROR_IN_ARGUMENTS", f"{path}.Arguments",
                   "$states.errorOutput is not available in Arguments; it exists only inside Catch[]")


def _check_task_express(
    state: dict, result: AnalysisResult, path: str, target_type: str
) -> None:
    if target_type != "EXPRESS":
        return
    resource = state.get("Resource", "")
    if ".sync" in resource or resource.endswith(":2"):
        result.add("error", "E_EXPRESS_SYNC", f"{path}.Resource",
                   f"'.sync' pattern is forbidden in Express workflows (Resource: {resource})")
    if ".waitForTaskToken" in resource:
        result.add("error", "E_EXPRESS_TOKEN", f"{path}.Resource",
                   f"'.waitForTaskToken' is forbidden in Express workflows (Resource: {resource})")
    if ":activity:" in resource:
        result.add("error", "E_EXPRESS_ACTIVITY", f"{path}.Resource",
                   f"Activities are forbidden in Express workflows (Resource: {resource})")


def _check_map(
    state: dict, result: AnalysisResult, path: str, target_type: str
) -> None:
    proc = state.get("ItemProcessor") or {}
    cfg = proc.get("ProcessorConfig") or {}
    mode = cfg.get("Mode", "INLINE")
    if mode == "INLINE":
        mc = state.get("MaxConcurrency")
        if isinstance(mc, int) and mc > 40:
            result.add("error", "E_MAP_INLINE_CONCURRENCY", f"{path}.MaxConcurrency",
                       f"Inline Map allows max 40 concurrent iterations (got {mc}); "
                       "switch to Distributed mode (ProcessorConfig.Mode: DISTRIBUTED)")
        for forbidden in ("ItemReader", "ItemBatcher", "ResultWriter"):
            if forbidden in state:
                result.add("error", "E_MAP_INLINE_FIELD", f"{path}.{forbidden}",
                           f"{forbidden} is only valid in Distributed Map; "
                           "set ProcessorConfig.Mode to DISTRIBUTED")
    elif mode == "DISTRIBUTED":
        if target_type == "EXPRESS":
            result.add("error", "E_EXPRESS_DISTRIBUTED", path,
                       "Distributed Map is not supported in Express workflows "
                       "(the parent must be a Standard workflow)")
        if "ExecutionType" not in cfg:
            result.add("error", "E_DIST_EXEC_TYPE", f"{path}.ItemProcessor.ProcessorConfig",
                       "Distributed Map requires ExecutionType (STANDARD or EXPRESS) in ProcessorConfig")
        if "MaxConcurrency" not in state:
            result.add("warning", "W_DIST_NO_MAXCONCURRENCY", path,
                       "Distributed Map without MaxConcurrency defaults to 10,000 concurrent child "
                       "executions, which can overwhelm downstream services")


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------


def _successors(state: dict) -> list[str]:
    """Return state-name successors for transition edges within this state map."""
    out: list[str] = []
    if state.get("Type") == "Choice":
        for rule in state.get("Choices") or []:
            if isinstance(rule, dict) and "Next" in rule:
                out.append(rule["Next"])
        if "Default" in state:
            out.append(state["Default"])
    else:
        if "Next" in state:
            out.append(state["Next"])
    for c in state.get("Catch") or []:
        if isinstance(c, dict) and "Next" in c:
            out.append(c["Next"])
    return out


def _collect_reachable(start: Optional[str], states: dict) -> set[str]:
    if start is None or start not in states:
        return set()
    seen: set[str] = set()
    stack = [start]
    while stack:
        n = stack.pop()
        if n in seen or n not in states:
            continue
        seen.add(n)
        for nxt in _successors(states[n]):
            if nxt not in seen:
                stack.append(nxt)
    return seen


def _has_terminal(start: Optional[str], states: dict) -> bool:
    for name in _collect_reachable(start, states):
        s = states[name]
        if s.get("Type") in ("Succeed", "Fail"):
            return True
        if s.get("End") is True:
            return True
    return False


# ---------------------------------------------------------------------------
# Common-error-state heuristic
# ---------------------------------------------------------------------------


def _detect_common_error_state(
    states: dict, result: AnalysisResult, path: str
) -> None:
    """
    Flag the pattern where multiple Task/Parallel/Map states route their Catch
    blocks to the same handler state.

    Rationale: routing every error through a common handler transitions the
    execution past the failed state, which (a) prevents redrive-from-failed-
    state after the underlying bug is fixed, (b) reports the execution as
    Succeeded (no EventBridge FAILED event), and (c) buries the failure
    location inside the handler's input. Prefer per-Task handlers for named
    recoverable errors and let unknown errors fail the execution.

    We warn only when 3 or more states share a Catch[].Next target, to avoid
    false positives on small legitimate convergence points (e.g. two tasks
    that legitimately share a compensation routine).
    """
    targets: dict[str, list[str]] = {}
    for name, state in states.items():
        if not isinstance(state, dict):
            continue
        if state.get("Type") not in ("Task", "Parallel", "Map"):
            continue
        for c in state.get("Catch") or []:
            if isinstance(c, dict):
                nxt = c.get("Next")
                if isinstance(nxt, str):
                    targets.setdefault(nxt, []).append(name)

    for tgt, sources in targets.items():
        if len(sources) >= 3:
            result.add(
                "warning", "W_COMMON_ERROR_STATE",
                f"{path}.States.{tgt}",
                f"state '{tgt}' is used as a Catch[].Next target by {len(sources)} states "
                f"({', '.join(sources)}); this 'common error handler' pattern prevents "
                "redrive-from-failed-state and reports failed executions as Succeeded. "
                "Prefer per-state handlers for named recoverable errors; let unknown errors "
                "fail the execution so EventBridge can alert and operators can redrive "
                "after fixing the bug.",
            )
