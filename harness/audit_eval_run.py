#!/usr/bin/env python3
"""Audit a sealed evaluation run's transcript for leakage.

    python3 audit_eval_run.py --dest ~/arc3-eval/ft09

Finds the Claude Code session transcript(s) for the eval directory and
scans every tool call for reads of sealed material: the downloaded game
source (environments/), the exocortex repo (notes, traces, prior runs),
and web access. Prints a verdict and every hit with context. The
transcript is part of the published result either way — this script just
makes the check mechanical.
"""

import argparse
import glob
import json
import os
import sys

SEALED_SUBSTRINGS = [
    "environments/", "exocortex", "schema-traces", "arc-agi-3-schema",
]
WEB_TOOLS = {"WebFetch", "WebSearch"}
READ_TOOLS = {"Read", "Grep", "Glob", "Bash", "Agent", "Task"}


def transcript_paths(dest):
    munged = os.path.abspath(os.path.expanduser(dest)).replace("/", "-")
    pattern = os.path.expanduser(f"~/.claude/projects/{munged}/*.jsonl")
    return sorted(glob.glob(pattern))


def tool_uses(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block.get("name", ""), block.get("input", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--transcript", default=None,
                    help="explicit transcript path (else auto-discover)")
    args = ap.parse_args()

    paths = ([args.transcript] if args.transcript
             else transcript_paths(args.dest))
    if not paths:
        sys.exit(f"no transcripts found for {args.dest} under "
                 "~/.claude/projects/ — pass --transcript")

    hits = []
    calls = 0
    for path in paths:
        for name, tool_input in tool_uses(path):
            calls += 1
            if name in WEB_TOOLS:
                hits.append((path, name, "web tool used",
                             json.dumps(tool_input)[:200]))
                continue
            if name not in READ_TOOLS:
                continue
            blob = json.dumps(tool_input)
            for s in SEALED_SUBSTRINGS:
                if s in blob:
                    hits.append((path, name, f"references {s!r}",
                                 blob[:200]))
                    break

    print(f"audited {calls} tool call(s) across {len(paths)} transcript(s)")
    if not hits:
        print("VERDICT: CLEAN — no sealed-path reads, no web access")
        sys.exit(0)
    print(f"VERDICT: {len(hits)} HIT(S) — review each before trusting "
          "the run:")
    for path, name, why, ctx in hits:
        print(f"\n  {name}: {why}\n    {ctx}\n    in {os.path.basename(path)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
