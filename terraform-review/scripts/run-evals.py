#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "anthropic==0.102.0",
# ]
# ///
"""Run terraform-review skill evals against the Anthropic API.

Loads evals.json, runs each eval with SKILL.md as the system prompt, then
asks a grading model to score each expectation against the response. Writes
responses, grades, and a summary to a timestamped output directory.

Suggested placement: scripts/run_evals.py at the same level as evals/.

Usage with uv (recommended — handles dependencies automatically):
  export ANTHROPIC_API_KEY=...
  uv run scripts/run_evals.py --skill SKILL.md --evals evals/evals.json

Or, since the shebang invokes uv, execute directly:
  ./scripts/run_evals.py --skill SKILL.md --evals evals/evals.json

Or with plain python (requires `pip install anthropic` first):
  python scripts/run_evals.py --skill SKILL.md --evals evals/evals.json

Flags:
  --skill PATH           Path to SKILL.md (required)
  --evals PATH           Path to evals.json (required)
  --output-dir DIR       Where to save results (default: eval-runs)
  --model NAME           Model used to run evals (default: claude-sonnet-4-6)
  --grader-model NAME    Model used to grade (default: claude-sonnet-4-6)
  --eval-ids 1,3         Only run these eval IDs (default: all)
  --threshold 0.80       Minimum pass rate before exit 1 (default: 0.80)
  --workers N            Parallel eval runs (default: 4)
  --no-grade             Skip grading; just save responses

Exit codes:
  0   All evals scored at or above --threshold
  1   Some evals scored below --threshold, or no grades were produced
  2   Configuration error (missing key, bad paths, etc.)
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# anthropic is imported lazily inside main() so `--help` works without the SDK installed


# ---------------------------------------------------------------------------
# Eval execution
# ---------------------------------------------------------------------------

def build_user_message(eval_def: dict, skill_dir: Path) -> str:
    """Assemble the prompt plus inline file contents into one user message.

    `files` entries are relative to the skill root (the official skill-creator
    schema), and may name a directory, in which case every file under it is
    inlined. Fixture names using the `dot-` convention (dot-github,
    dot-CLAUDE.md) are presented under their real names.
    """
    parts = [eval_def["prompt"]]

    for rel_path in eval_def.get("files", []):
        target = skill_dir / rel_path
        if not target.exists():
            raise FileNotFoundError(f"Eval input missing: {target}")
        paths = sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else [target]
        for file_path in paths:
            shown = str(file_path.relative_to(skill_dir))
            shown = shown.replace("dot-github", ".github").replace("dot-CLAUDE.md", "CLAUDE.md")
            parts.append(f"\n\n### `{shown}`\n```\n{file_path.read_text()}\n```")

    return "".join(parts)


def run_eval(client, eval_def: dict, skill_dir: Path, skill_content: str, model: str) -> dict:
    """Send one eval to the API and return the response text + token counts."""
    user_message = build_user_message(eval_def, skill_dir)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=skill_content,
        messages=[{"role": "user", "content": user_message}],
    )

    text = "\n".join(b.text for b in response.content if hasattr(b, "text"))

    return {
        "id": eval_def["id"],
        "name": eval_def["name"],
        "response": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

GRADING_PROMPT = """You are grading a Claude response against a list of expectations.

For each expectation, output a JSON object with these keys:
  - "text": the expectation string verbatim
  - "verdict": one of "PASS", "FAIL", "PARTIAL"
  - "reason": a one-sentence justification

Return a JSON array of these objects and nothing else. No prose, no markdown
fences, no preamble. Be strict: PASS only if the response clearly satisfies
the expectation; PARTIAL if it gestures at the right idea but misses detail;
FAIL otherwise.

EXPECTATIONS:
{expectations_json}

RESPONSE TO GRADE:
{response}
"""


def grade_response(client, eval_def: dict, response_text: str, model: str) -> dict:
    """Have the grader model judge the response against the eval's expectations."""
    prompt = GRADING_PROMPT.format(
        expectations_json=json.dumps(eval_def["expectations"], indent=2),
        response=response_text,
    )

    completion = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "\n".join(b.text for b in completion.content if hasattr(b, "text")).strip()

    # Defensive: strip markdown fences if the grader added them despite instructions
    text = re.sub(r"^```(?:json)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)

    try:
        grades = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"error": f"could not parse grader output: {exc}", "raw": text}

    if not isinstance(grades, list):
        return {"error": "grader did not return a JSON array", "raw": text}

    return {"grades": grades}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def score_grades(grades: list[dict]) -> tuple[int, int, int, float]:
    """Return (passes, partials, fails, score) where partial = 0.5."""
    passes = sum(1 for g in grades if g.get("verdict") == "PASS")
    partials = sum(1 for g in grades if g.get("verdict") == "PARTIAL")
    fails = sum(1 for g in grades if g.get("verdict") == "FAIL")
    score = passes + 0.5 * partials
    return passes, partials, fails, score


def write_summary_md(path: Path, summary: dict) -> None:
    """Human-readable summary, in addition to the JSON one."""
    lines = [
        f"# Eval run summary",
        "",
        f"- **Run timestamp:** {summary['timestamp']}",
        f"- **Eval model:** `{summary['model']}`",
        f"- **Grader model:** `{summary['grader_model']}`",
        f"- **Overall score:** {summary['overall_score']:.1%} ({summary['overall_points']:.1f} / {summary['overall_total']})",
        "",
        "| ID | Name | Pass | Partial | Fail | Total | Score |",
        "|---:|------|----:|--------:|----:|------:|------:|",
    ]
    for e in summary["evals"]:
        total = e["passes"] + e["partials"] + e["fails"]
        score = (e["passes"] + 0.5 * e["partials"]) / total if total else 0.0
        lines.append(
            f"| {e['id']} | {e['name']} | {e['passes']} | {e['partials']} | "
            f"{e['fails']} | {total} | {score:.1%} |"
        )
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run terraform-review skill evals against the Anthropic API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skill", type=Path, required=True, help="Path to SKILL.md")
    parser.add_argument("--evals", type=Path, required=True, help="Path to evals.json")
    parser.add_argument("--output-dir", type=Path, default=Path("eval-runs"))
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Model for running evals")
    parser.add_argument("--grader-model", default="claude-sonnet-4-6", help="Model for grading")
    parser.add_argument("--eval-ids", help="Comma-separated eval IDs to run (default: all)")
    parser.add_argument("--threshold", type=float, default=0.80, help="Min pass rate before exit 1")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--no-grade", action="store_true", help="Skip grading; just save responses")
    args = parser.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.stderr.write(
            "error: anthropic SDK not installed.\n"
            "  Recommended: run with `uv run` (handles dependencies automatically).\n"
            "  Or install manually: `pip install anthropic`.\n"
        )
        return 2

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write("error: ANTHROPIC_API_KEY env var not set\n")
        return 2

    for p in (args.skill, args.evals):
        if not p.exists():
            sys.stderr.write(f"error: not found: {p}\n")
            return 2

    skill_content = args.skill.read_text()
    evals_data = json.loads(args.evals.read_text())
    # evals.json lives at <skill>/evals/evals.json; `files` paths are relative
    # to the skill root, per the skill-creator schema.
    skill_dir = args.evals.parent.parent

    evals_to_run = evals_data["evals"]
    if args.eval_ids:
        wanted = {int(x) for x in args.eval_ids.split(",")}
        evals_to_run = [e for e in evals_to_run if e["id"] in wanted]
        if not evals_to_run:
            sys.stderr.write(f"error: no evals match --eval-ids={args.eval_ids}\n")
            return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic()

    print(f"Running {len(evals_to_run)} eval(s)")
    print(f"  Eval model:    {args.model}")
    print(f"  Grader model:  {args.grader_model}")
    print(f"  Output dir:    {run_dir}\n")

    # --- Run evals in parallel ---------------------------------------------
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_eval, client, e, skill_dir, skill_content, args.model): e
            for e in evals_to_run
        }
        for fut in as_completed(futures):
            eval_def = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:
                print(f"  ✗ eval {eval_def['id']} ({eval_def['name']}) — ERROR: {exc}")
                continue
            response_path = run_dir / f"eval-{result['id']}-{result['name']}-response.md"
            response_path.write_text(result["response"])
            print(
                f"  ✓ eval {result['id']:>2} ({result['name']}): "
                f"{result['output_tokens']} output tokens"
            )
            results.append(result)

    if args.no_grade:
        print("\nSkipping grading (--no-grade). Responses saved.")
        return 0

    # --- Grade --------------------------------------------------------------
    print(f"\nGrading {len(results)} response(s)...")
    summary_evals = []
    overall_points = 0.0
    overall_total = 0

    for result in sorted(results, key=lambda r: r["id"]):
        eval_def = next(e for e in evals_to_run if e["id"] == result["id"])
        try:
            grading = grade_response(client, eval_def, result["response"], args.grader_model)
        except Exception as exc:
            print(f"  ! eval {result['id']} — grader call failed: {exc}")
            continue

        if "error" in grading:
            print(f"  ! eval {result['id']} — {grading['error']}")
            (run_dir / f"eval-{result['id']}-{result['name']}-grader-raw.txt").write_text(grading["raw"])
            continue

        grades = grading["grades"]
        passes, partials, fails, score = score_grades(grades)
        total = passes + partials + fails

        (run_dir / f"eval-{result['id']}-{result['name']}-grades.json").write_text(
            json.dumps(grades, indent=2)
        )

        rate = score / total if total else 0.0
        print(
            f"  eval {result['id']:>2} ({result['name']}): "
            f"{passes}P {partials}~ {fails}F / {total} ({rate:.1%})"
        )

        summary_evals.append({
            "id": result["id"],
            "name": result["name"],
            "passes": passes,
            "partials": partials,
            "fails": fails,
        })
        overall_points += score
        overall_total += total

    # --- Summary -----------------------------------------------------------
    if overall_total == 0:
        print("\nNo grades produced.")
        return 1

    overall = overall_points / overall_total
    print(f"\nOverall: {overall_points:.1f} / {overall_total} ({overall:.1%})")
    print(f"Threshold: {args.threshold:.0%}")

    summary = {
        "timestamp": timestamp,
        "model": args.model,
        "grader_model": args.grader_model,
        "evals": summary_evals,
        "overall_score": overall,
        "overall_points": overall_points,
        "overall_total": overall_total,
        "threshold": args.threshold,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    write_summary_md(run_dir / "summary.md", summary)

    if overall < args.threshold:
        print("❌ Below threshold.")
        return 1
    print("✅ At or above threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
