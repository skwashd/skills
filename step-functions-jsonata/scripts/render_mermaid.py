#!/usr/bin/env python3
"""
Render a JSONata-mode ASL state machine as a Mermaid state diagram.

Mermaid is chosen because it renders inline in GitHub, many IDEs, and most
markdown previewers, which makes diagrams trivially reviewable. The output
is text; pipe it into a file or paste it into a markdown block.

Usage:
    python scripts/render_mermaid.py workflow.asl.json > workflow.mmd
    python scripts/render_mermaid.py workflow.asl.json --direction LR
"""
from __future__ import annotations

import argparse
import json
import re
import sys


_ID_SAFE = re.compile(r"[^A-Za-z0-9_]")


def _sid(name: str) -> str:
    return _ID_SAFE.sub("_", name)


def _label(state: dict, name: str) -> str:
    t = state.get("Type", "Unknown")
    # Compact label showing state type and, for Task, a short Resource tag.
    if t == "Task":
        r = state.get("Resource", "")
        short = r.split(":")[-1] if r else ""
        return f"{name}<br/><small>Task · {short}</small>"
    return f"{name}<br/><small>{t}</small>"


def _emit_branch(
    machine: dict, out: list[str], prefix: str, indent: int = 1
) -> None:
    pad = "    " * indent
    states = machine.get("States") or {}
    start = machine.get("StartAt")

    # Declare states with labels
    for name, state in states.items():
        if not isinstance(state, dict):
            continue
        node_id = _sid(f"{prefix}{name}")
        label = _label(state, name)
        t = state.get("Type")
        if t in ("Succeed", "Fail"):
            out.append(f'{pad}{node_id}(("{label}"))')
        elif t == "Choice":
            out.append(f'{pad}{node_id}{{"{label}"}}')
        else:
            out.append(f'{pad}{node_id}["{label}"]')

    # StartAt edge
    if isinstance(start, str) and start in states:
        out.append(f"{pad}START_{prefix or 'top'}([Start]) --> {_sid(prefix + start)}")

    # Transition edges
    for name, state in states.items():
        if not isinstance(state, dict):
            continue
        src = _sid(f"{prefix}{name}")
        t = state.get("Type")
        if t == "Choice":
            for i, rule in enumerate(state.get("Choices") or []):
                if isinstance(rule, dict) and "Next" in rule:
                    out.append(f"{pad}{src} -->|Choice {i}| {_sid(prefix + rule['Next'])}")
            if "Default" in state:
                out.append(f"{pad}{src} -.->|Default| {_sid(prefix + state['Default'])}")
        else:
            if "Next" in state:
                out.append(f"{pad}{src} --> {_sid(prefix + state['Next'])}")
            if state.get("End") is True:
                out.append(f"{pad}{src} --> END_{prefix or 'top'}([End])")

        for i, catch in enumerate(state.get("Catch") or []):
            if isinstance(catch, dict) and "Next" in catch:
                errs = ",".join(catch.get("ErrorEquals") or [])
                out.append(f"{pad}{src} -.->|Catch: {errs}| {_sid(prefix + catch['Next'])}")

    # Recurse into Parallel branches and Map ItemProcessor
    for name, state in states.items():
        if not isinstance(state, dict):
            continue
        if state.get("Type") == "Parallel":
            for bi, branch in enumerate(state.get("Branches") or []):
                sub_prefix = f"{prefix}{name}_B{bi}_"
                out.append(f"{pad}subgraph {_sid(prefix + name)}_branch_{bi}[\"{name} / branch {bi}\"]")
                _emit_branch(branch, out, sub_prefix, indent + 1)
                out.append(f"{pad}end")
        if state.get("Type") == "Map":
            processor = state.get("ItemProcessor")
            if isinstance(processor, dict):
                sub_prefix = f"{prefix}{name}_I_"
                out.append(f"{pad}subgraph {_sid(prefix + name)}_iter[\"{name} / iteration\"]")
                _emit_branch(processor, out, sub_prefix, indent + 1)
                out.append(f"{pad}end")


def render(machine: dict, direction: str = "TB") -> str:
    out: list[str] = [f"flowchart {direction}"]
    _emit_branch(machine, out, prefix="")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Render a JSONata-mode ASL file as Mermaid.")
    ap.add_argument("path", help="path to ASL JSON file")
    ap.add_argument("--direction", default="TB", choices=["TB", "BT", "LR", "RL"],
                    help="Mermaid flowchart direction (default: TB)")
    args = ap.parse_args(argv)
    with open(args.path) as f:
        doc = json.load(f)
    sys.stdout.write(render(doc, direction=args.direction))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
