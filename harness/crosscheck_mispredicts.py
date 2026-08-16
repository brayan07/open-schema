#!/usr/bin/env python3
"""Where does the released-model backtest residue come from?

For each released trajectory, replay its best world model over its own
recorded history (as validate_traces does) and classify every non-green
transition: does it coincide with a step where the ORIGINAL harness also
recorded a model_mispredicted event? Their own reds explain our reds to
the extent the two sets overlap; the remainder bounds genuine contract
mismatch between our sandbox and theirs.

    python3 crosscheck_mispredicts.py --root ../data/schema-traces
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agi3lib.backtest import run_backtest  # noqa: E402
from agi3lib.events import transitions_from_events  # noqa: E402
from agi3lib.model import ModelError, WorldModel  # noqa: E402

DATASETS = ("gpt_5_6_sol", "claude_fable_opus")


def read_events(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def best_model(d, transitions):
    candidates = sorted(set(d.glob("world_model*.py")) | set(d.glob("wm*.py")))
    best = None
    for path in candidates:
        try:
            model = WorldModel(str(path))
        except ModelError:
            continue
        checked, mismatches, _, _ = run_backtest(model, transitions)
        errors = sum(1 for m in mismatches if m.kind == "error")
        green = checked - (len(mismatches) - errors)
        pct = green / checked if checked else 0.0
        if best is None or pct > best[0]:
            best = (pct, mismatches, checked)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()

    tot_red = tot_overlap = tot_checked = 0
    rows = []
    for ds in DATASETS:
        for d in sorted((args.root / ds).iterdir()):
            ev_path = d / "events.jsonl"
            if not ev_path.is_file():
                continue
            events = read_events(ev_path)
            transitions = transitions_from_events(events)
            recorded = {e.get("step_index")
                        for e in events if e.get("kind") == "model_mispredicted"}
            got = best_model(d, transitions)
            if got is None:
                rows.append((d.name, "no runnable model", None))
                continue
            pct, mismatches, checked = got
            reds = {m.transition.index for m in mismatches}
            overlap = reds & recorded
            unexplained = reds - recorded
            tot_red += len(reds)
            tot_overlap += len(overlap)
            tot_checked += checked
            rows.append((d.name,
                         f"{len(reds)} red; {len(overlap)} coincide with "
                         f"their recorded mispredicts; "
                         f"{len(unexplained)} unexplained "
                         f"({100 * (1 - len(unexplained) / checked):.1f}% "
                         "contract-fidelity floor)",
                         sorted(unexplained)[:10]))

    for name, msg, extra in rows:
        print(f"{name}: {msg}")
        if extra:
            print(f"    unexplained indices (first 10): {extra}")
    if tot_checked:
        print(f"\nTOTAL: {tot_red} red transitions; {tot_overlap} "
              f"({100 * tot_overlap / max(tot_red, 1):.1f}%) coincide with "
              "the original harness's own recorded mispredictions.")
        print(f"Unexplained residue: {tot_red - tot_overlap} of "
              f"{tot_checked} checked transitions "
              f"({100 * (tot_red - tot_overlap) / tot_checked:.2f}%) — the "
              "upper bound on genuine contract mismatch.")


if __name__ == "__main__":
    main()
