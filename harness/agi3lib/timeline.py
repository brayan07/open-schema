"""Build the self-contained timeline.html inspector for a run.

Everything comes from two sources of truth: events.jsonl (frames, actions,
plans, tool calls, mispredictions) and the workdir's git history (the world
model's code and notes.md at every point in time). The generator also
*re-simulates* the past: for each committed plan and each BFS rollout it
loads the model version that was current at that moment and replays the
plan inside it (ghost trajectories), and for each model snapshot it runs a
full backtest against the recorded history (version-vs-reality verdicts).
The output is one HTML file with all of it embedded — no server, no
network.
"""

import ast
import difflib
import json
import os
import re
import subprocess
import tempfile

from . import render
from .backtest import run_backtest
from .events import EventLog, transitions_from_events
from .model import ModelError, WorldModel

MAX_FILE_BYTES = 300_000
MAX_GHOST_STEPS = 96
SNAP_LABEL = re.compile(r"@ t=(\d+)")
BFS_PLAN = re.compile(r"^Plan \(-> commit\): (\[.*\])", re.M)


def _hexgrid(grid):
    return ["".join(render.HEX[v] for v in row) for row in grid]


def _git(workdir, *argv):
    return subprocess.run(["git", *argv], cwd=workdir,
                          capture_output=True, text=True)


def _snapshots(workdir):
    """Workdir git history -> (embed list, resolved-content list).

    The embed list dedupes unchanged files (None = same as previous); the
    resolved list carries full content per snapshot for re-simulation.
    """
    if not os.path.isdir(os.path.join(workdir, ".git")):
        return [], []
    log = _git(workdir, "log", "--reverse", "--format=%H\t%s")
    if log.returncode != 0:
        return [], []
    snaps, resolved = [], []
    prev_files = {}
    for line in log.stdout.splitlines():
        sha, _, label = line.partition("\t")
        m = SNAP_LABEL.search(label)
        t = int(m.group(1)) if m else 0
        names = _git(workdir, "ls-tree", "-r", "--name-only",
                     sha).stdout.split()
        files, diffs = {}, {}
        for name in names:
            if not name.endswith((".py", ".md")) or name == ".gitignore":
                continue
            content = _git(workdir, "show", f"{sha}:{name}").stdout
            if len(content) > MAX_FILE_BYTES:
                content = content[:MAX_FILE_BYTES] + "\n... [truncated]"
            if prev_files.get(name) == content:
                files[name] = None  # unchanged; viewer walks back
            else:
                files[name] = content
                if name in prev_files:
                    diffs[name] = "".join(difflib.unified_diff(
                        prev_files[name].splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"{name}@prev", tofile=f"{name}@t{t}"))
            prev_files[name] = content
        snaps.append({"sha": sha[:10], "label": label, "t": t,
                      "files": files, "diffs": diffs})
        resolved.append(dict(prev_files))
    return snaps, resolved


def _model_source(resolved_files):
    """Pick the model file the run would have used from a snapshot."""
    candidates = sorted(n for n in resolved_files
                        if re.fullmatch(r"world_model.*\.py", n))
    if not candidates:
        return None
    if "world_model.py" in candidates:
        return resolved_files["world_model.py"]
    return resolved_files[candidates[-1]]


class _ModelCache:
    """Load each distinct model source once, into a temp file + sandbox."""

    def __init__(self):
        self._by_src = {}

    def get(self, source):
        if source is None:
            return None, "no world_model*.py at this time"
        if source not in self._by_src:
            with tempfile.NamedTemporaryFile(
                    "w", suffix=".py", delete=False) as fh:
                fh.write(source)
            try:
                self._by_src[source] = (WorldModel(fh.name), None)
            except ModelError as exc:
                self._by_src[source] = (None, str(exc))
            finally:
                os.unlink(fh.name)
        return self._by_src[source]


def _snap_before(snaps, resolved, at_step):
    """The latest snapshot taken at or before env step at_step."""
    best = None
    for i, s in enumerate(snaps):
        if s["t"] <= at_step:
            best = i
    return resolved[best] if best is not None else None


def _norm_plan(plan):
    """Plan entries ([a,x,y] lists or {'action':..} dicts) -> [a,x,y]."""
    out = []
    for step in plan:
        if isinstance(step, list):
            a, x, y = (step + [None, None])[:3]
        else:
            a, x, y = step.get("action"), step.get("x"), step.get("y")
        out.append([a, x, y])
    return out


def _simulate(model, start_grid, level, plan):
    """Roll a plan forward inside the model; returns (hex frames, error)."""
    try:
        state = model.init_state(start_grid, level=level)
    except ModelError as exc:
        return [], str(exc)
    frames, grid, err = [], start_grid, None
    for a, x, y in plan[:MAX_GHOST_STEPS]:
        if a in (None, 0):
            break
        try:
            g2, flags, state = model.predict(state, grid, a, x, y,
                                             level=level)
        except ModelError as exc:
            err = str(exc)
            break
        if g2 is None:
            break
        frames.append(_hexgrid(g2))
        grid = g2
        if flags["level_up"] or flags["win"] or flags["dead"]:
            break  # the model can't see past a level boundary
    return frames, err


def _ghosts(turns, tools, frames_int, levels, snaps, resolved, cache):
    """Re-simulate committed plans and BFS rollouts under the model version
    that was current when they were made."""
    out = []
    for tn in turns:
        s = tn["at_step"]
        if s >= len(frames_int):
            continue
        plan = _norm_plan(tn["plan"])
        files = _snap_before(snaps, resolved, s)
        model, err = cache.get(_model_source(files) if files else None)
        if model is None:
            out.append({"kind": "commit", "turn": tn["turn"], "at_step": s,
                        "plan": plan, "frames": [], "error": err})
            continue
        frames, sim_err = _simulate(model, frames_int[s], levels[s], plan)
        out.append({"kind": "commit", "turn": tn["turn"], "at_step": s,
                    "plan": plan, "frames": frames, "error": sim_err})
    for tool in tools:
        if tool["name"] != "bfs" or not tool.get("output"):
            continue
        m = BFS_PLAN.search(tool["output"])
        if not m:
            continue
        try:
            plan = _norm_plan(ast.literal_eval(m.group(1)))
        except (ValueError, SyntaxError):
            continue
        s = tool["at_step"]
        if s >= len(frames_int):
            continue
        files = _snap_before(snaps, resolved, s)
        model, err = cache.get(_model_source(files) if files else None)
        if model is None:
            continue
        frames, sim_err = _simulate(model, frames_int[s], levels[s], plan)
        tool["ghost"] = len(out)
        out.append({"kind": "bfs", "turn": tool["turn"], "at_step": s,
                    "plan": plan, "frames": frames, "error": sim_err})
    return out


def _verdicts(transitions, resolved, cache):
    """Per-snapshot backtest of the FULL history: how much of reality does
    each model version explain? marks[i] in g(reen)/r(ed)/e(rror)/s(kip)."""
    out = []
    for i, files in enumerate(resolved):
        model, err = cache.get(_model_source(files))
        if model is None:
            out.append({"snap": i, "marks": "", "note": err})
            continue
        _, mismatches, _, _ = run_backtest(model, transitions)
        bad = {}
        for m in mismatches:
            bad[m.transition.index] = "e" if m.kind == "error" else "r"
        marks = []
        for t in transitions:
            if t.action == 0 or t.before is None:
                marks.append("s")
            else:
                marks.append(bad.get(t.index, "g"))
        green = marks.count("g")
        checkable = green + marks.count("r") + marks.count("e")
        out.append({"snap": i, "marks": "".join(marks),
                    "note": f"{green}/{checkable} green"})
    return out


def build_data(workdir, fast=False):
    events = EventLog(os.path.join(workdir, "events.jsonl")).read()
    try:
        with open(os.path.join(workdir, "run.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        cfg = {}

    meta = {"game": cfg.get("game_id") or cfg.get("env", "?"),
            "env": cfg.get("env"), "agent": cfg.get("agent"),
            "state": "?", "win_levels": 0, "initial_level": 0}
    initial = None
    initial_level = 0
    steps, turns, mispredicts = [], [], {}
    tools, open_tools = [], {}
    frames_int, levels = [], []  # levels[i] = level of frame i
    for ev in events:
        kind = ev.get("kind")
        if kind == "run_started":
            meta["agent"] = ev.get("model", meta["agent"])
        elif kind == "turn_started":
            if initial is None and ev.get("grid"):
                initial = _hexgrid(ev["grid"])
                initial_level = ev.get("level", 0)
                meta["initial_level"] = initial_level
                meta["win_levels"] = ev.get("win_levels", 0)
                frames_int.append(ev["grid"])
                levels.append(initial_level)
        elif kind == "action_taken":
            steps.append({
                "i": ev["step_index"], "turn": ev.get("turn", 0),
                "action": ev["action"], "x": ev.get("x"), "y": ev.get("y"),
                "state": ev.get("state"), "level": ev.get("level", 0),
                "level_up": bool(ev.get("level_up")),
                "dead": bool(ev.get("dead")), "win": bool(ev.get("win")),
                "grid": _hexgrid(ev["grid"]),
            })
            frames_int.append(ev["grid"])
            levels.append(ev.get("level", 0))
            meta["state"] = ev.get("state", meta["state"])
            meta["level"] = ev.get("level", 0)
        elif kind == "turn_committed":
            turns.append({"turn": ev.get("turn", 0), "seq": ev.get("seq"),
                          "plan": ev.get("plan", []),
                          "reason": ev.get("reason", ""),
                          "at_step": len(steps)})
        elif kind == "model_mispredicted":
            mispredicts[ev.get("step_index")] = {
                "surprise": ev.get("surprise", ""),
                "predicted": (_hexgrid(ev["predicted"])
                              if ev.get("predicted") else None)}
        elif kind == "tool_started":
            open_tools[ev.get("call_id")] = {
                "turn": ev.get("turn", 0), "seq": ev.get("seq"),
                "name": ev.get("name"), "args": ev.get("args", {}),
                "at_step": len(steps), "output": None, "is_error": False,
                "ghost": None}
            tools.append(open_tools[ev.get("call_id")])
        elif kind == "tool_finished":
            t = open_tools.get(ev.get("call_id"))
            if t is not None:
                t["output"] = ev.get("output", "")
                t["is_error"] = bool(ev.get("is_error"))
        elif kind == "run_finished":
            meta["state"] = ev.get("state", meta["state"])
            meta["level"] = ev.get("levels", meta.get("level", 0))

    snaps, resolved = _snapshots(workdir)
    ghosts, verdicts = [], []
    if not fast and frames_int:
        cache = _ModelCache()
        ghosts = _ghosts(turns, tools, frames_int, levels, snaps, resolved,
                         cache)
        verdicts = _verdicts(transitions_from_events(events), resolved,
                             cache)

    return {"meta": meta, "initial": initial, "steps": steps,
            "turns": turns,
            "mispredicts": {str(k): v for k, v in mispredicts.items()},
            "tools": tools, "snapshots": snaps, "ghosts": ghosts,
            "verdicts": verdicts}


def write_html(workdir, out_path, fast=False):
    template = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "timeline_template.html")
    with open(template, encoding="utf-8") as fh:
        html = fh.read()
    payload = json.dumps(build_data(workdir, fast=fast),
                         separators=(",", ":"))
    html = html.replace("/*__DATA__*/null", payload)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
