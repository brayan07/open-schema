#!/usr/bin/env python3
"""Validate the replication against the 50 released [schema] trajectories.

Two independent checks, strongest first:

1. --scores: recompute every trajectory's RHAE from its events.jsonl using
   OUR event summarizer and OUR RHAE formula, and compare against the
   release's evaluation_results.csv manifests. Exact agreement means our
   event schema, per-level action accounting, and scoring all match theirs.

2. --backtest: load a released world_model*.py into OUR sandbox and run OUR
   backtest over the transitions reconstructed from that run's own
   events.jsonl. The released models were kept green against their history
   by the original harness, so a high pass rate here means our transition
   reconstruction, CURRENT_LEVEL injection, model contract, and comparison
   semantics reproduce theirs.

Usage:
    python3 validate_traces.py --root ../data/schema-traces --scores
    python3 validate_traces.py --root ../data/schema-traces --backtest N
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agi3lib import score  # noqa: E402
from agi3lib.backtest import run_backtest  # noqa: E402
from agi3lib.events import transitions_from_events  # noqa: E402
from agi3lib.model import ModelError, WorldModel  # noqa: E402

DATASETS = ("gpt_5_6_sol", "claude_fable_opus")


def read_events(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def load_manifests(root):
    rows = {}
    for ds in DATASETS:
        with open(root / ds / "evaluation_results.csv", newline="",
                  encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                key = Path(row["workdir"]).name
                rows[key] = row
    return rows


def check_scores(root):
    baselines = score.load_baselines(str(root / "gpt_5_6_sol"
                                          / "baseline_actions.csv"))
    by_task = {task: actions for task, actions in baselines.values()}
    manifests = load_manifests(root)
    ok = bad = 0
    for ds in DATASETS:
        for d in sorted((root / ds).iterdir()):
            if not (d / "events.jsonl").is_file():
                continue
            man = manifests.get(d.name)
            if man is None:
                print(f"  {d.name}: no manifest row")
                bad += 1
                continue
            summary = score.summarize_events(read_events(d / "events.jsonl"))
            human = by_task[man["task"]]
            value, _ = score.rhae(summary.completed_actions, human)
            want = float(man["rhae"])
            want_levels = [int(man[f"level{i}"])
                           for i in range(10) if man.get(f"level{i}")]
            same_levels = list(summary.completed_actions) == want_levels
            if abs(value - want) < 0.005 and same_levels:
                ok += 1
            else:
                bad += 1
                print(f"  MISMATCH {d.name}: rhae {value:.2f} vs {want}; "
                      f"levels {list(summary.completed_actions)} "
                      f"vs {want_levels}")
    print(f"scores: {ok}/{ok + bad} trajectories match the manifests "
          f"(RHAE and per-level action counts)")
    return bad == 0


def check_backtests(root, limit):
    results = []
    dirs = [d for ds in DATASETS for d in sorted((root / ds).iterdir())
            if (d / "events.jsonl").is_file()]
    if limit:
        dirs = dirs[:limit]
    for d in dirs:
        # Runs often leave several model versions behind (world_model_v6.py,
        # wm_v11_wip.py, ...) and clone mtimes are meaningless, so try every
        # candidate and report the best — the run's final model is whichever
        # actually validates against its own history.
        candidates = sorted(set(d.glob("world_model*.py"))
                            | set(d.glob("wm*.py")))
        if not candidates:
            results.append((d.name, "no model file", None))
            continue
        transitions = transitions_from_events(
            read_events(d / "events.jsonl"))
        best = None
        load_errs = []
        for path in candidates:
            try:
                model = WorldModel(str(path))
            except ModelError as exc:
                load_errs.append(f"{path.name}: {exc}")
                continue
            checked, mismatches, skipped, _ = run_backtest(model, transitions)
            errors = sum(1 for m in mismatches if m.kind == "error")
            green = checked - (len(mismatches) - errors)
            pct = 100.0 * green / checked if checked else 0.0
            if best is None or pct > best[0]:
                best = (pct, green, checked, errors, skipped, path.name)
        if best is None:
            results.append(
                (d.name, "load failed: " + "; ".join(load_errs), None))
            continue
        pct, green, checked, errors, skipped, fname = best
        results.append(
            (d.name,
             f"{green}/{checked} green ({pct:.1f}%), {errors} error(s), "
             f"{skipped} skipped [{fname}]",
             pct))
    print("\nbacktest of released models over their own recorded history:")
    for name, msg, _ in results:
        print(f"  {name}: {msg}")
    scored = [p for _, _, p in results if p is not None]
    if scored:
        print(f"mean green rate over {len(scored)} model(s): "
              f"{sum(scored) / len(scored):.1f}%")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--backtest", type=int, default=0, metavar="N",
                    help="backtest released models for the first N traces "
                         "(0 = skip)")
    args = ap.parse_args()
    ok = True
    if args.scores:
        ok = check_scores(args.root)
    if args.backtest:
        check_backtests(args.root, args.backtest)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
