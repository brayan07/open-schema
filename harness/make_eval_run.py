#!/usr/bin/env python3
"""Scaffold a sealed evaluation run: a clean directory where an agent can
play one ARC-AGI-3 game with no access to game source, notes, traces, or
the web.

    python3 make_eval_run.py --game ft09 --dest ~/arc3-eval/ft09

Creates:
  <dest>/arc3.py + agi3lib/      the harness tooling (copied, self-contained)
  <dest>/.venv                   own env with arc-agi + numpy (via uv)
  <dest>/.env                    ARC_API_KEY (for the one-time game download)
  <dest>/CLAUDE.md               the complete procedure + hard rules
  <dest>/.claude/settings.json   permission DENY rules: repo, game source, web
  <dest>/.claude/hooks/guard.py  blocks Bash commands referencing sealed paths
  <dest>/run/                    the game workdir (events.jsonl lands here)

Then launch the agent from <dest> (e.g. `claude` there, prompt: "Play the
game per CLAUDE.md"), and afterwards run audit_eval_run.py on the session
transcript. Enforcement is layered, not absolute — the audit is part of
the protocol, and the transcript ships with the result.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

CLAUDE_MD = """\
# Your task: play one ARC-AGI-3 game, single run, as well as you can

You are being evaluated on RHAE: finishing every level in as few actions
as possible (quadratic penalty for excess actions). The game has NO
instructions — you must discover the mechanics by acting.

## Hard rules (violations void the run; your transcript is audited)

- NEVER read anything under `environments/` — that is the game's source
  code. The entire point is to learn the game by playing it.
- NEVER use the web, and never read files outside this directory.
- Single run: no restarting the evaluation to try again with what you
  learned. (In-game RESET is a normal action and is fine.)

## The method

Work from this directory. The game workdir is `run/`.

    A() { .venv/bin/python arc3.py --workdir run "$@"; }

1. `A observe` — current frame (64x64, colours 0-15 as hex), legal
   actions, your notes.
2. Maintain `run/notes.md` (shown on every observe; keep it pruned) and
   `run/world_model.py`, a program that predicts the next frame:

       def init_state(entry_grid): return state
       def predict(state, grid, action, x=None, y=None):
           return next_grid, info, next_state   # info: level_up/dead/win
       # or stateless: def step(grid, action, x=None, y=None):
       #                   return next_grid, info

3. `A backtest` — your model vs EVERY recorded transition. Do not plan
   until green. A mismatch names the counterexample transition; inspect
   with `A history --indices <i> --detail full`.
4. `A bfs --target advance [--clicks "x,y;x,y"]` — plan inside the model;
   costs no real actions.
5. `A commit --actions '[{"action":1},...]' --reason "..."` — execute.
   One misprediction voids the rest of the plan and hands you the
   counterexample: go back to 2 with new evidence.
6. When several rules fit the history, choose the ACTION on which they
   disagree and take it — the best experiment per action spent.
7. Repeat until WIN. If truly stuck, write your best analysis into
   `run/notes.md` and stop; an honest stall is a valid result.

Efficiency matters: think long, act little. Blocked probes still count
as actions. Prefer general mechanisms over special cases carried by one
observation.

## Start

    .venv/bin/python arc3.py --workdir run init --env toolkit \\
        --game {game} --agent {agent} --environments-dir environments
    A observe
"""

GUARD = """\
#!/usr/bin/env python3
# PreToolUse hook: block Bash commands that reach into sealed paths.
import json
import sys

data = json.load(sys.stdin)
cmd = (data.get("tool_input") or {}).get("command", "")
SEALED = ["environments/", "exocortex", "schema-traces", "arc-agi-3-schema",
          "curl ", "wget ", "http://", "https://"]
hits = [s for s in SEALED if s in cmd]
if hits:
    print(f"BLOCKED: command references sealed path/tool: {hits}. "
          "The game source, the repo, and the web are off-limits — "
          "learn the game by playing it.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
"""


def settings(dest):
    env_dir = os.path.join(dest, "environments")
    return {
        "permissions": {
            # allow the working tools so a headless run never stalls on a
            # prompt; deny rules below take precedence, so the seal holds
            "allow": ["Bash", "Read", "Edit", "Write", "Glob", "Grep"],
            "deny": [
                f"Read({env_dir}/**)",
                "Read(**/environments/**)",
                f"Read({os.path.expanduser('~/exocortex')}/**)",
                "WebFetch",
                "WebSearch",
            ],
        },
        "hooks": {
            "PreToolUse": [{
                "matcher": "Bash",
                "hooks": [{"type": "command",
                           "command": os.path.join(dest, ".claude", "hooks",
                                                   "guard.py")}],
            }],
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, help="4-char game id, e.g. ft09")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--agent", default="eval-agent")
    args = ap.parse_args()
    dest = os.path.abspath(os.path.expanduser(args.dest))
    os.makedirs(dest, exist_ok=True)

    # tooling (copied so nothing references the repo at runtime)
    shutil.copy(os.path.join(HERE, "arc3.py"), dest)
    shutil.copytree(os.path.join(HERE, "agi3lib"),
                    os.path.join(dest, "agi3lib"), dirs_exist_ok=True)
    os.makedirs(os.path.join(dest, "run"), exist_ok=True)

    # the agent's brief
    with open(os.path.join(dest, "CLAUDE.md"), "w", encoding="utf-8") as fh:
        fh.write(CLAUDE_MD.replace("{game}", args.game)
                 .replace("{agent}", args.agent))

    # sealed-path enforcement
    hooks_dir = os.path.join(dest, ".claude", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    guard = os.path.join(hooks_dir, "guard.py")
    with open(guard, "w", encoding="utf-8") as fh:
        fh.write(GUARD)
    os.chmod(guard, os.stat(guard).st_mode | stat.S_IEXEC)
    with open(os.path.join(dest, ".claude", "settings.json"), "w",
              encoding="utf-8") as fh:
        json.dump(settings(dest), fh, indent=1)

    # API key for the one-time game download
    key = os.environ.get("ARC_API_KEY", "")
    if not key:
        try:
            with open(os.path.expanduser("~/exocortex/.env"),
                      encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("ARC_API_KEY="):
                        key = line.split("=", 1)[1].strip()
        except OSError:
            pass
    with open(os.path.join(dest, ".env"), "w", encoding="utf-8") as fh:
        fh.write(f"ARC_API_KEY={key}\n")

    # self-contained venv (no reference to the repo's environment)
    subprocess.run(["uv", "venv", ".venv"], cwd=dest, check=True)
    subprocess.run(["uv", "pip", "install", "--python", ".venv/bin/python",
                    "arc-agi>=0.9.1", "numpy"], cwd=dest, check=True)

    print(f"eval run scaffolded: {dest}")
    print(f"launch:  cd {dest} && claude "
          f"'Play the game exactly per CLAUDE.md.'")
    print("audit:   python3 arc/agi3/audit_eval_run.py --dest", dest)


if __name__ == "__main__":
    main()
