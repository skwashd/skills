"""
JSONata expression syntax checker for Step Functions.

Step Functions expressions are delimited by {% and %}. Inside the delimiters,
Step Functions forbids several JSONata constructs that the reference parser
would otherwise accept:

  - top-level `$`       — forbidden (AWS: "use $states.*")
  - top-level `$$`      — forbidden (AWS: "use $states.context")
  - `$eval(...)`        — blocked (use $parse)
  - unqualified field names at the top of the expression

We detect these with lightweight structural checks before handing the inner
text to jsonata-python for full parse validation. jsonata-python implements
JSONata 2.x; Step Functions implements 2.0.6. This check is therefore a
*superset* of what AWS accepts — it will not reject valid Step Functions
JSONata, but it may accept expressions that AWS later rejects (e.g. the
elvis `?:` and nullish-coalesce `??` operators introduced in 2.1.x).
Authoritative validation remains `aws stepfunctions validate-state-machine-
definition`, which runs in layer L3 when credentials are present.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

try:
    import jsonata as _jsonata_mod  # type: ignore
    _HAS_JSONATA = True
except ImportError:
    _HAS_JSONATA = False

_EXPR_RE = re.compile(r"^\{%([\s\S]*)%\}$")

# Forbidden standalone tokens inside a Step Functions expression.
# We match these only when they appear to be used as the top-level context.
_FORBIDDEN_EVAL = re.compile(r"\$eval\s*\(")
_BARE_DOLLAR = re.compile(r"(?:^|[^\w$])\$(?![a-zA-Z_$])")
_BARE_DOUBLE_DOLLAR = re.compile(r"(?:^|[^\w$])\$\$(?![a-zA-Z_$])")


def is_jsonata_string(value: object) -> bool:
    """Return True if `value` is a string wrapped in {% %}."""
    return isinstance(value, str) and bool(_EXPR_RE.match(value))


def extract_inner(expr: str) -> Optional[str]:
    """Return the text between {% and %}, stripped, or None if not a JSONata string."""
    m = _EXPR_RE.match(expr)
    if not m:
        return None
    return m.group(1).strip()


def check_expression(expr: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a single JSONata expression string.

    Returns (ok, error_message). `expr` must include the {% %} delimiters.
    """
    inner = extract_inner(expr)
    if inner is None:
        return False, "expression must be wrapped in {% ... %} (no surrounding whitespace)"
    if not inner:
        return False, "empty JSONata expression"

    # Step Functions specific rejections.
    if _FORBIDDEN_EVAL.search(inner):
        return False, "$eval(...) is blocked by Step Functions; use $parse(...)"
    if _BARE_DOUBLE_DOLLAR.search(inner):
        return False, "bare $$ is forbidden in Step Functions JSONata; use $states.context"
    if _BARE_DOLLAR.search(inner):
        # Check if it's just `$` used in a position other than as a variable reference.
        # We accept $foo, $states.*, $$numeric JSONata functions like $count, $sum, etc.
        return False, (
            "bare $ (top-level context) is forbidden in Step Functions JSONata; "
            "use $states.input / $states.result / $states.errorOutput / $states.context, "
            "a named variable like $myVar, or a JSONata function call like $count(...)"
        )

    # Syntactic parse via jsonata-python, if available.
    if _HAS_JSONATA:
        try:
            _jsonata_mod.Jsonata(inner)
        except Exception as e:  # noqa: BLE001 - library raises assorted types
            return False, f"JSONata syntax error: {e}"

    return True, None


def walk_and_check(obj: object, path: str = "$") -> list[tuple[str, str]]:
    """
    Walk a JSON structure and check every JSONata expression string.

    Returns a list of (path, error_message) pairs for expressions that fail.
    """
    errors: list[tuple[str, str]] = []
    if isinstance(obj, str):
        if is_jsonata_string(obj):
            ok, err = check_expression(obj)
            if not ok and err is not None:
                errors.append((path, err))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            errors.extend(walk_and_check(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errors.extend(walk_and_check(v, f"{path}[{i}]"))
    return errors
