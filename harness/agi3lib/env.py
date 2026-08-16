"""Environments: the live ARC-AGI-3 API, a recorded-trace replay, and a toy game.

All three expose the same two calls:

    reset() -> Frame
    act(action, x=None, y=None) -> Frame

and are resumable across CLI invocations via ``state_dict()`` /
``from_state()``, because every ``arc3.py`` command is a separate process.

Action numbering follows the ARC-AGI-3 wire format: 0 RESET, 1..5 simple
actions, 6 click (x, y in 0..63), 7 undo.
"""

import json
import urllib.request

RESET = 0


class Frame:
    """What the environment returns after RESET or an action."""

    def __init__(self, grid, state, level, win_levels, legal, frames=None):
        self.grid = grid  # last grid of the frame list
        self.frames = frames if frames is not None else [grid]
        self.state = state  # NOT_STARTED | NOT_FINISHED | WIN | GAME_OVER
        self.level = level  # levels completed so far
        self.win_levels = win_levels
        self.legal = legal  # available action ids


class ApiEnv:
    """The live ARC-AGI-3 API.

    Endpoint shapes follow docs.arcprize.org as captured in
    arc/notes/arc-agi-3.md. Untested against the live service (no key in this
    environment yet); verify the routes before the first paid run.
    """

    def __init__(self, game_id, api_key, base_url="https://three.arcprize.org",
                 card_id=None, guid=None):
        self.game_id = game_id
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.card_id = card_id
        self.guid = guid

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"X-API-Key": self.api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    def open_scorecard(self, tags=()):
        out = self._post("/api/scorecard/open", {"tags": list(tags)})
        self.card_id = out["card_id"]
        return self.card_id

    def close_scorecard(self):
        if self.card_id:
            return self._post("/api/scorecard/close", {"card_id": self.card_id})

    def _frame(self, out):
        self.guid = out.get("guid", self.guid)
        frames = out.get("frame") or []
        grid = frames[-1] if frames else None
        return Frame(
            grid=grid,
            state=out.get("state", "NOT_FINISHED"),
            level=out.get("levels_completed", 0),
            win_levels=out.get("win_levels", 0),
            legal=out.get("available_actions", []),
            frames=frames,
        )

    def reset(self):
        payload = {"game_id": self.game_id}
        if self.card_id:
            payload["card_id"] = self.card_id
        if self.guid:
            payload["guid"] = self.guid
        return self._frame(self._post("/api/cmd/RESET", payload))

    def act(self, action, x=None, y=None):
        if action == RESET:
            return self.reset()
        payload = {"game_id": self.game_id, "guid": self.guid}
        if self.card_id:
            payload["card_id"] = self.card_id
        if action == 6:
            payload["x"] = x
            payload["y"] = y
        return self._frame(self._post(f"/api/cmd/ACTION{action}", payload))

    def list_games(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/games",
            headers={"X-API-Key": self.api_key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())

    def state_dict(self):
        return {"card_id": self.card_id, "guid": self.guid}

    def from_state(self, st):
        self.card_id = st.get("card_id")
        self.guid = st.get("guid")


class ReplayEnv:
    """Replays a recorded events.jsonl as if it were the live game.

    Only the recorded action sequence is legal: asking for anything else
    raises, because a log is not a simulator. Used to rebuild timelines from
    the released traces and to drive the loop machinery over ground truth.
    """

    def __init__(self, events_path, cursor=0):
        self.events_path = str(events_path)
        self.cursor = cursor
        self._initial = None  # Frame before any action
        self._steps = []  # action_taken events in order
        self._load()

    def _load(self):
        win_levels = 0
        with open(self.events_path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                ev = json.loads(line)
                kind = ev.get("kind")
                if kind == "turn_started" and self._initial is None:
                    win_levels = ev.get("win_levels", 0)
                    self._initial = Frame(
                        grid=ev["grid"], state=ev.get("state", "NOT_FINISHED"),
                        level=ev.get("level", 0), win_levels=win_levels,
                        legal=ev.get("legal", []),
                    )
                elif kind == "action_taken":
                    self._steps.append(ev)
        self.win_levels = win_levels

    def reset(self):
        if self.cursor == 0:
            return self._initial
        # A mid-run RESET is a recorded step like any other.
        return self.act(RESET)

    def expected_action(self):
        """What the log says happens next, or None at end of trace."""
        if self.cursor >= len(self._steps):
            return None
        ev = self._steps[self.cursor]
        return (ev["action"], ev.get("x"), ev.get("y"))

    def act(self, action, x=None, y=None):
        exp = self.expected_action()
        if exp is None:
            raise IndexError("replay exhausted: no more recorded actions")
        if (action, x, y) != exp:
            raise ValueError(
                f"replay divergence at step {self.cursor}: "
                f"recorded {exp}, requested {(action, x, y)}"
            )
        ev = self._steps[self.cursor]
        self.cursor += 1
        return Frame(
            grid=ev["grid"], state=ev.get("state", "NOT_FINISHED"),
            level=ev.get("level", 0), win_levels=self.win_levels,
            legal=[1, 2, 3, 4, 5, 6, 7],
        )

    def state_dict(self):
        return {"events_path": self.events_path, "cursor": self.cursor}

    def from_state(self, st):
        self.cursor = st.get("cursor", 0)


# --- Toy game -----------------------------------------------------------------
# A deterministic 64x64 three-level game for exercising the whole loop offline:
# move with 1..4, pick up a key to open the door, avoid the void, reach the
# goal. Small enough that a correct world model fits in a page, rich enough to
# produce level_up / dead / win flags and click no-ops.

FLOOR, WALL, DOOR, GOAL, KEY, AVATAR, VOID = 0, 4, 6, 7, 8, 9, 10
TOY_WIN_LEVELS = 3

# (avatar r, c), (goal r, c), walls, door cell or None, key cell or None, voids
TOY_LEVELS = [
    ((5, 5), (20, 20), [], None, None, []),
    ((5, 5), (20, 40), [(r, 30) for r in range(0, 64) if r != 12],
     (12, 30), (18, 10), []),
    ((5, 5), (40, 40), [], None, None, [(30, c) for c in range(0, 60)]),
]


class ToyEnv:
    def __init__(self):
        self.level = 0
        self.pos = TOY_LEVELS[0][0]
        self.have_key = False
        self.state = "NOT_STARTED"
        self.win_levels = TOY_WIN_LEVELS

    def _spec(self):
        return TOY_LEVELS[min(self.level, TOY_WIN_LEVELS - 1)]

    def _grid(self):
        _, goal, walls, door, key, voids = self._spec()
        g = [[FLOOR] * 64 for _ in range(64)]
        for c in range(64):
            g[0][c] = g[63][c] = WALL
        for r in range(64):
            g[r][0] = g[r][63] = WALL
        for r, c in walls:
            g[r][c] = WALL
        for r, c in voids:
            g[r][c] = VOID
        if door and not self.have_key:
            g[door[0]][door[1]] = DOOR
        if key and not self.have_key:
            g[key[0]][key[1]] = KEY
        g[goal[0]][goal[1]] = GOAL
        r, c = self.pos
        g[r][c] = AVATAR
        return g

    def _frame(self):
        return Frame(self._grid(), self.state, self.level, self.win_levels,
                     [1, 2, 3, 4, 6] if self.state == "NOT_FINISHED" else [0])

    def reset(self):
        # Matches the real games' observed semantics: RESET restarts the
        # CURRENT level (recovery after GAME_OVER, or a voluntary retry);
        # only a fresh game or a finished one restarts from level 0.
        if self.state in ("NOT_STARTED", "WIN"):
            self.level = 0
        self.have_key = False
        self.pos = self._spec()[0]
        self.state = "NOT_FINISHED"
        return self._frame()

    def act(self, action, x=None, y=None):
        if action == RESET:
            return self.reset()
        if self.state != "NOT_FINISHED":
            raise ValueError(f"game is {self.state}; only RESET is legal")
        _, goal, walls, door, key, voids = self._spec()
        dr = {1: -1, 2: 1}.get(action, 0)
        dc = {3: -1, 4: 1}.get(action, 0)
        if dr or dc:
            r, c = self.pos[0] + dr, self.pos[1] + dc
            cell_is_wall = ((r, c) in set(walls) or r in (0, 63) or c in (0, 63)
                            or ((r, c) == door and not self.have_key))
            if not cell_is_wall:
                self.pos = (r, c)
                if (r, c) == key and not self.have_key:
                    self.have_key = True
                if (r, c) in set(voids):
                    self.state = "GAME_OVER"
                elif (r, c) == goal:
                    self.level += 1
                    if self.level >= self.win_levels:
                        self.state = "WIN"
                    else:
                        self.have_key = False
                        self.pos = self._spec()[0]
        # action 6 (click) and 5/7 are deliberate no-ops in the toy game
        return self._frame()

    def state_dict(self):
        return {"level": self.level, "pos": list(self.pos),
                "have_key": self.have_key, "state": self.state}

    def from_state(self, st):
        self.level = st["level"]
        self.pos = (st["pos"][0], st["pos"][1])
        self.have_key = st["have_key"]
        self.state = st["state"]


class ToolkitEnv:
    """The official arc-agi toolkit engine (github.com/arcprize/arc-agi).

    Games are downloaded once (NORMAL mode needs ARC_API_KEY for the fetch)
    and then run locally at engine speed. Because every arc3 CLI command is
    a separate process and the engine holds game state in memory, resuming
    works by deterministic replay: reset, then re-apply the recorded action
    history (seeded engine, ~2000 FPS, so this costs milliseconds).
    """

    def __init__(self, game, environments_dir, history=None):
        from arc_agi import Arcade, OperationMode  # deferred: optional dep

        self.game = game
        mode = OperationMode.NORMAL
        self.arc = Arcade(operation_mode=mode,
                          environments_dir=environments_dir)
        self._env = self.arc.make(game)
        if self._env is None:
            raise RuntimeError(
                f"arc-agi could not make game {game!r} "
                f"(check the name and ARC_API_KEY for first download)")
        self.history = list(history or [])
        self.steps = 0  # recorded actions applied to the live engine

    def _frame(self, raw):
        if raw is None:
            raise RuntimeError("engine returned no frame")
        frames = raw.frame or []
        if not frames:
            raise RuntimeError("engine returned an empty frame list")
        grid = frames[-1]
        state = getattr(raw.state, "value", raw.state)
        return Frame(
            grid=[[int(v) for v in row] for row in grid],
            state=str(state),
            level=raw.levels_completed,
            win_levels=raw.win_levels,
            legal=[getattr(a, "value", int(a)) for a in raw.available_actions],
            frames=frames,
        )

    def _step(self, action, x=None, y=None):
        from arcengine.enums import GameAction

        if action == RESET:
            return self._env.reset()
        # GameAction members are (id, action_class) tuples with a customised
        # .value returning the id, so construct via a value map, not the enum.
        by_id = {a.value: a for a in GameAction}
        data = {"x": x, "y": y} if action == 6 else None
        return self._env.step(by_id[action], data)

    def reset(self):
        frame = self._frame(self._env.reset())
        self.steps = 0
        return frame

    def act(self, action, x=None, y=None):
        frame = self._frame(self._step(action, x, y))
        self.steps += 1
        return frame

    def state_dict(self):
        return {"steps": self.steps}

    def from_state(self, st):
        wanted = st.get("steps", 0)
        if wanted == 0:
            return
        if wanted > len(self.history):
            raise RuntimeError(
                f"cannot restore: engine state is {wanted} steps in but only "
                f"{len(self.history)} recorded actions are available")
        self._env.reset()
        for action, x, y in self.history[:wanted]:
            self._step(action, x, y)
        self.steps = wanted


def make_env(run_cfg, env_state=None, history=None):
    """Build the environment named by run.json, restored to saved state."""
    kind = run_cfg.get("env", "toy")
    if kind == "toy":
        env = ToyEnv()
    elif kind == "replay":
        env = ReplayEnv(run_cfg["trace_events"])
    elif kind == "toolkit":
        env = ToolkitEnv(run_cfg["game_id"],
                         run_cfg.get("environments_dir",
                                     "arc/data/agi3-environments"),
                         history=history)
    elif kind == "api":
        import os
        key = os.environ.get("ARC_API_KEY", "")
        if not key:
            raise RuntimeError("ARC_API_KEY is not set; cannot use the live API")
        env = ApiEnv(run_cfg["game_id"], key,
                     base_url=run_cfg.get("base_url",
                                          "https://three.arcprize.org"))
    else:
        raise ValueError(f"unknown env kind {kind!r}")
    if env_state:
        env.from_state(env_state)
    return env
