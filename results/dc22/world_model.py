"""World model for dc22.

Screen: a LEFT maze panel (bg 4) and a RIGHT button panel (bg 5), separated by
a dashed column pair; row 63 is a tick meter (one lit px per two ticks).

The player is a 2x2 block of colour 14 and walks 2px at a time over any
non-background pixel of the left panel (actions 1/2/3/4 = up/down/left/right).
Colour 11 is the goal.

The maze is built from static rooms (colour 2) plus "bodies": an arm assembly
that has exactly two configurations.  A body is flipped either by clicking its
button in the right panel (the button is drawn in the body's own colour) or by
walking into an in-maze switch room, which consumes the room's glyph and
UNLOCKS that body's button in the right panel.  A body configuration that is present-but-inactive is drawn as
a checkerboard ghost (colour only where (r+c) is odd) and is not walkable.

Every action costs 1 tick; a click that flips a body costs 2.  The meter
lights ceil(ticks/div) pixels, with a per-level div (2 on level 0, 3 on 1).
"""

# Tick count of the CURRENT live frame.  The meter only shows ceil(ticks/2) so
# the parity cannot be read back from the grid; kept by hand.
TICKS_NOW = 145

BG_L, BG_R = 4, 5
PLAYER, GOAL = 14, 11
TICK_COLOR = 3

# --- level 3 ------------------------------------------------------------
# Two corridors share a pool of 8 bridge cells; each click of the 2 widget
# moves two of them from the lower corridor to the upper one.  Bridge cells
# fill a corridor from both ends inwards; the gap is drawn in colour 5 and a
# completely bridged corridor is drawn in colour 12 instead of 1.
CORRIDORS = [(20, 8), (40, 16)]  # (top row, left col) of an 8-cell corridor


def _corridor_states():
    states = []
    for j in range(5):
        k = [2 * j, 8 - 2 * j]
        rects = []
        for (row, col), kk in zip(CORRIDORS, k):
            col_full = 12 if kk == 8 else 1
            for i in range(8):
                bridged = i < kk // 2 or i >= 8 - kk // 2
                rects.append((row, col + 2 * i, row + 1, col + 2 * i + 1,
                              col_full if bridged else 5, "solid"))
        states.append(rects)
    return states


def _block_states():
    states = []
    for q1 in range(4, 10):
        col = 12 if q1 == 9 else 1
        states.append([(28, 2 * q1, 29, 2 * q1 + 5, col, "solid"),
                       (38, 2 * q1 - 4, 39, 2 * q1 + 1, col, "solid")])
    return states


# --- level 4 ------------------------------------------------------------
# A left-pointing arrow sprite (colour 8) slides over a black backdrop; four
# small blocks in the right panel move it up / down / left / right.
ARROW = [(0, 3, 7), (1, 3, 3), (1, 7, 7), (2, 1, 4), (3, 0, 3),
         (4, 0, 3), (5, 1, 4), (6, 3, 3), (6, 7, 7), (7, 3, 7)]
BLACK_RECTS = [(14, 3, 17, 19), (18, 3, 25, 6), (26, 3, 29, 18)]


def _arrow_cells(r0, c0):
    out = []
    for dr, a, b in ARROW:
        for c in range(c0 + a, c0 + b + 1):
            out.append((r0 + dr, c))
    return out


def _l4_corridor():
    states = []
    for j in range(5):
        k = 2 * j
        rects = []
        for i in range(8):
            bridged = i < k // 2 or i >= 8 - k // 2
            col = (12 if k == 8 else 1) if bridged else 5
            rects.append((44, 14 + 2 * i, 45, 15 + 2 * i, col, "solid"))
        states.append(rects)
    return states


def _l4_block():
    return [[(54, 2 * q, 55, 2 * q + 5, 1, "solid")] for q in range(7, 15)]


def _find_arrow(g):
    for r in range(0, 56):
        for c in range(0, 34):
            if all(g[y][x] == 8 for y, x in _arrow_cells(r, c)):
                return r, c
    return None


def _backdrop(r, c):
    for (r0, c0, r1, c1) in BLACK_RECTS:
        if r0 <= r <= r1 and c0 <= c <= c1:
            return 0
    return BG_L


def _core_in_black(r0, c0):
    for r in (r0 + 2, r0 + 5):
        for c in (c0 + 2, c0 + 3):
            if _backdrop(r, c) != 0:
                return False
    return True


def _move_arrow(g, pos, d, st):
    r0, c0 = pos
    nr, nc = r0 + d[0], c0 + d[1]
    if not _core_in_black(nr, nc):
        return False
    old = set(_arrow_cells(r0, c0))
    new = _arrow_cells(nr, nc)
    for (r, c) in new:
        if not (0 <= r <= 62 and 0 <= c <= 37):
            return False
        if (r, c) not in old and g[r][c] not in (BG_L, 0):
            return False
    for (r, c) in old:
        g[r][c] = _backdrop(r, c)
    for (r, c) in new:
        g[r][c] = 8
    return True


# rect = (r0, c0, r1, c1, colour, style) with style "solid" | "ghost"
LEVELS = {
    0: {
        "left": (10, 53, 0, 31),
        "right": (10, 53, 34, 63),
        "bodies": {
            8: [[(30, 12, 33, 17, 8, "solid")],
                [(24, 18, 29, 21, 8, "solid")]],
            9: [[(20, 18, 23, 21, 9, "solid"), (34, 8, 37, 11, 9, "ghost")],
                [(20, 18, 23, 21, 9, "ghost"), (34, 8, 37, 11, 9, "solid")]],
        },
        "switches": [],
        "div": 2,
    },
    1: {
        "left": (8, 55, 0, 37),
        "right": (8, 55, 40, 63),
        "bodies": {
            6: [[(40, 8, 43, 15, 7, "solid"), (40, 20, 43, 27, 7, "solid")],
                [(32, 16, 39, 19, 7, "solid"), (44, 16, 51, 19, 7, "solid")]],
            9: [[(28, 8, 31, 11, 9, "solid"), (32, 4, 39, 7, 9, "ghost")],
                [(28, 8, 31, 11, 9, "ghost"), (32, 4, 39, 7, 9, "solid")]],
            8: [[(24, 12, 27, 19, 8, "solid"), (24, 24, 27, 31, 8, "solid")],
                [(16, 20, 23, 23, 8, "solid"), (28, 20, 35, 23, 8, "solid")]],
        },
        # walking into a switch room consumes its glyph and UNLOCKS that
        # body's button in the right panel
        # (r0, c0, r1, c1, body, glyph_pixels, button_rects)
        "switches": [(52, 16, 55, 19, 8,
                      [(53, 17), (53, 18), (54, 16), (54, 17), (54, 18),
                       (54, 19)],
                      [(29, 49, 31, 55), (32, 46, 33, 58)])],
        "div": 3,
    },
    2: {
        "left": (8, 55, 0, 37),
        "right": (8, 55, 40, 63),
        "div": 3,
        "bodies": {
            8: [[(24, 12, 27, 19, 8, "solid"), (24, 24, 27, 31, 8, "solid")],
                [(16, 20, 23, 23, 8, "solid"), (28, 20, 35, 23, 8, "solid")]],
            # one 9 gate is solid while the other three are ghosts, and the
            # button swaps the roles
            9: [[(24, 8, 27, 11, 9, "solid"), (16, 24, 19, 27, 9, "ghost"),
                 (20, 4, 23, 7, 9, "ghost"), (40, 12, 43, 15, 9, "ghost")],
                [(24, 8, 27, 11, 9, "ghost"), (16, 24, 19, 27, 9, "solid"),
                 (20, 4, 23, 7, 9, "solid"), (40, 12, 43, 15, 9, "solid")]],
            15: [[(32, 16, 39, 19, 15, "ghost"),
                  (32, 24, 35, 33, 15, "ghost")],
                 [(32, 16, 39, 19, 15, "solid"),
                  (32, 24, 35, 33, 15, "solid")]],
        },
        # bodies drawn as bare pixels (the 6/7 markers in the two portal rooms)
        # the two 2x2 markers are a portal pair: flipping body 6 swaps their
        # contents, carrying the player across
        "portals": {6: [(16, 6), (46, 12)]},
        "glyph_bodies": {
            6: [[(16, 6, 7), (16, 7, 6), (17, 6, 6), (17, 7, 7),
                 (46, 12, 6), (46, 13, 7), (47, 12, 7), (47, 13, 6)],
                [(16, 6, 6), (16, 7, 7), (17, 6, 7), (17, 7, 6),
                 (46, 12, 7), (46, 13, 6), (47, 12, 6), (47, 13, 7)]],
        },
        "switches": [(40, 16, 43, 19, 15,
                      [(42, 17), (42, 18), (43, 16), (43, 17), (43, 18),
                       (43, 19)],
                      [(43, 48, 45, 54), (46, 45, 47, 57)])],
    },
    3: {
        "left": (8, 55, 0, 37),
        "right": (8, 55, 40, 63),
        "div": 3,
        "bodies": {
            2: _corridor_states(),
            11: _block_states(),
        },
        # the corridor widget ping-pongs along its range; the block widget wraps
        "oscillate": [2],
        "dir0": {2: -1},
        "portals": {6: [(24, 4), (32, 18)]},
        "glyph_bodies": {
            6: [[(24, 4, 6), (24, 5, 7), (25, 4, 7), (25, 5, 6),
                 (32, 18, 7), (32, 19, 6), (33, 18, 6), (33, 19, 7)],
                [(24, 4, 7), (24, 5, 6), (25, 4, 6), (25, 5, 7),
                 (32, 18, 6), (32, 19, 7), (33, 18, 7), (33, 19, 6)]],
        },
        "switches": [],
    },
    4: {
        "left": (0, 62, 0, 37),
        "right": (0, 62, 40, 63),
        "div": 12,
        "penalty": 30,
        "cost_move": 2,
        "bodies": {
            9: [[(34, 26, 37, 29, 9, "ghost"), (38, 10, 41, 13, 9, "solid")],
                [(34, 26, 37, 29, 9, "solid"), (38, 10, 41, 13, 9, "ghost")]],
            2: _l4_corridor(),
            11: _l4_block(),
        },
        "oscillate": [2],
        "portals": {6: [(6, 24), (34, 10)]},
        "glyph_bodies": {
            6: [[(6, 24, 7), (6, 25, 6), (7, 24, 6), (7, 25, 7),
                 (34, 10, 6), (34, 11, 7), (35, 10, 7), (35, 11, 6)],
                [(6, 24, 6), (6, 25, 7), (7, 24, 7), (7, 25, 6),
                 (34, 10, 7), (34, 11, 6), (35, 10, 6), (35, 11, 7)]],
        },
        "switches": [],
        # (r0, c0, r1, c1, dr, dc) right-panel blocks that nudge the arrow
        "sprite_buttons": [(28, 43, 31, 46, 0, -4), (28, 48, 31, 51, -4, 0),
                           (28, 53, 31, 56, 0, 4), (28, 58, 31, 61, 4, 0)],
    },
}

DELTA = {1: (-2, 0), 2: (2, 0), 3: (0, -2), 4: (0, 2)}

def _cfg(level):
    return LEVELS.get(level if level in LEVELS else 0)


def _copy(g):
    return [row[:] for row in g]


def _find_player(g, left):
    r0, r1, c0, c1 = left
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if g[r][c] == PLAYER:
                return r, c
    return None


def _body_state(g, states):
    """Which of the two configurations is currently drawn."""
    for i, rects in enumerate(states):
        ok = True
        for (r0, c0, r1, c1, col, style) in rects:
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    want = col if (style == "solid" or (r + c) % 2) else BG_L
                    if g[r][c] not in (want, PLAYER):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            return i
    return 0


def _draw_body(g, states, idx, st=None):
    for rects in states:
        for (r0, c0, r1, c1, col, style) in rects:
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if g[r][c] != PLAYER:
                        g[r][c] = BG_L
    for (r0, c0, r1, c1, col, style) in states[idx]:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                want = col if (style == "solid" or (r + c) % 2) else BG_L
                if g[r][c] == PLAYER:
                    # the ground under the player was repainted too
                    if st is not None:
                        p = _find_player(g, (0, 63, 0, 63))
                        if p is not None:
                            st["patch"][r - p[0]][c - p[1]] = want
                    continue
                g[r][c] = want


def _next_index(cfg, body, i, n, st):
    if body not in cfg.get("oscillate", []):
        return (i + 1) % n
    d = (st or {}).get("dir", {}).get(body, 1)
    if i == 0:
        d = 1
    elif i == n - 1:
        d = -1
    if st is not None:
        st.setdefault("dir", {})[body] = d
    return i + d


def _on_rects(p, rects):
    for (r0, c0, r1, c1, col, style) in rects:
        if style != "solid":
            continue
        if r0 <= p[0] and p[0] + 1 <= r1 and c0 <= p[1] and p[1] + 1 <= c1:
            return True
    return False


def _flip(g, cfg, body, st=None):
    gb = cfg.get("glyph_bodies", {})
    if body in gb:
        states = gb[body]
        cur = 0 if all(g[r][c] in (v, PLAYER) for r, c, v in states[0]) else 1
        for r, c, v in states[1 - cur]:
            g[r][c] = v
        ports = cfg.get("portals", {}).get(body)
        if ports and st is not None:
            p = _find_player(g, cfg["left"])
            here = None
            for i, (pr, pc) in enumerate(ports):
                if p is None and st.get("pos") == (pr, pc):
                    here = i
            if p is None:
                # the player was standing on a marker: it has just been
                # overwritten, so relocate it to the partner marker
                here = st.get("portal_idx")
                if here is not None:
                    dr, dc = ports[1 - here]
                    st["patch"] = [[g[dr][dc], g[dr][dc + 1]],
                                   [g[dr + 1][dc], g[dr + 1][dc + 1]]]
                    for i in range(2):
                        for j in range(2):
                            g[dr + i][dc + j] = PLAYER
        return
    states = cfg["bodies"][body]
    i = _body_state(g, states)
    j = _next_index(cfg, body, i, len(states), st)
    _draw_body(g, states, j, st)


def _in_rect(r, c, rect):
    return rect[0] <= r <= rect[2] and rect[1] <= c <= rect[3]


def _paint_ticks(g, ticks, div):
    lit = -(-ticks // div)
    for c in range(64):
        g[63][c] = TICK_COLOR if c < lit else 0


def _level(default=0):
    # the harness injects CURRENT_LEVEL into this module's globals
    try:
        return CURRENT_LEVEL
    except NameError:
        return default


def init_state(entry_grid, level=None):
    level = _level() if level is None else level
    cfg = _cfg(level)
    div = cfg.get("div", 2)
    lit = sum(1 for v in entry_grid[63] if v != 0)
    if lit == 0:
        ticks = 0
    elif -(-TICKS_NOW // div) == lit:
        ticks = TICKS_NOW
    else:
        ticks = div * lit
    p = _find_player(entry_grid, cfg["left"])
    patch = [[2, 2], [2, 2]]
    if p:
        counts = {}
        for r in range(p[0] - 1, p[0] + 3):
            for c in range(p[1] - 1, p[1] + 3):
                if p[0] <= r <= p[0] + 1 and p[1] <= c <= p[1] + 1:
                    continue
                if not _in_rect(r, c, (cfg["left"][0], cfg["left"][2],
                                       cfg["left"][1], cfg["left"][3])):
                    continue
                v = entry_grid[r][c]
                if v not in (BG_L, PLAYER):
                    counts[v] = counts.get(v, 0) + 1
        if counts:
            best = max(counts.values())
            v = 2 if counts.get(2) == best else max(
                counts, key=lambda k: counts[k])
            patch = [[v, v], [v, v]]
        # standing on a portal marker: recover the marker's own colours
        for body, ports in cfg.get("portals", {}).items():
            if p not in ports:
                continue
            here = ports.index(p)
            other = ports[1 - here]
            states = cfg["glyph_bodies"][body]
            idx = 0
            for i, pix in enumerate(states):
                if all(entry_grid[r][c] == v for r, c, v in pix
                       if (r, c) not in [(other[0] + a, other[1] + b)
                                         for a in (0, 1) for b in (0, 1)]
                       and (r, c) not in [(p[0] + a, p[1] + b)
                                          for a in (0, 1) for b in (0, 1)]):
                    idx = i
            mine = {(r, c): v for r, c, v in states[idx]}
            patch = [[mine.get((p[0] + i, p[1] + j), 2) for j in (0, 1)]
                     for i in (0, 1)]
        # standing on a body: the ground is that body's own colour
        for body, states in cfg.get("bodies", {}).items():
            idx = _body_state(entry_grid, states)
            for (r0, c0, r1, c1, col, style) in states[idx]:
                if (r0 <= p[0] and p[0] + 1 <= r1
                        and c0 <= p[1] and p[1] + 1 <= c1):
                    patch = [[col, col], [col, col]]
    return {"level": level, "ticks": ticks, "patch": patch,
            "dir": dict(cfg.get("dir0", {}))}


def predict(state, grid, action, x=None, y=None, level=0, entry_grid=None):
    st = dict(state)
    st["patch"] = [row[:] for row in state["patch"]]
    st["dir"] = dict(state.get("dir", {}))
    cfg = _cfg(state.get("level", _level()))
    lr0, lr1, lc0, lc1 = cfg["left"]
    rr0, rr1, rc0, rc1 = cfg["right"]
    g = _copy(grid)
    info = {"level_up": False, "dead": False, "win": False}
    # every action costs 1 tick (2 on level 4); a click that flips a body costs 2
    cost = cfg.get("cost_move", 1) if action in DELTA else 1

    if action in DELTA:
        p = _find_player(g, cfg["left"])
        if p is not None:
            pr, pc = p
            dr, dc = DELTA[action]
            nr, nc = pr + dr, pc + dc
            cells = [(nr + i, nc + j) for i in range(2) for j in range(2)]
            ok = all(lr0 <= r <= lr1 and lc0 <= c <= lc1
                     and g[r][c] != BG_L for r, c in cells)
            if ok:
                dest = [[g[nr][nc], g[nr][nc + 1]],
                        [g[nr + 1][nc], g[nr + 1][nc + 1]]]
                for i in range(2):
                    for j in range(2):
                        g[pr + i][pc + j] = st["patch"][i][j]
                for r, c in cells:
                    g[r][c] = PLAYER
                st["patch"] = dest
                if any(v == GOAL for row in dest for v in row):
                    info["level_up"] = True
                for sw in cfg["switches"]:
                    sr0, sc0, sr1, sc1, body, glyph, btn = sw
                    inside_new = sr0 <= nr <= sr1 and sc0 <= nc <= sc1
                    inside_old = sr0 <= pr <= sr1 and sc0 <= pc <= sc1
                    if not (inside_new and not inside_old):
                        continue
                    if all(g[r][c] != body for r, c in glyph
                           if not (nr <= r <= nr + 1 and nc <= c <= nc + 1)):
                        continue  # already used
                    for r, c in glyph:
                        if g[r][c] != PLAYER:
                            g[r][c] = 2
                        st["patch"] = [[2 if v == body else v for v in row]
                                       for row in st["patch"]]
                    for (br0, bc0, br1, bc1) in btn:
                        for r in range(br0, br1 + 1):
                            for c in range(bc0, bc1 + 1):
                                g[r][c] = body
    elif action == 6 and x is not None and y is not None:
        for (br0, bc0, br1, bc1, dr, dc) in cfg.get("sprite_buttons", []):
            if br0 <= y <= br1 and bc0 <= x <= bc1:
                pos = _find_arrow(g)
                if pos is not None and _move_arrow(g, pos, (dr, dc), st):
                    cost = 2
                st["ticks"] += cost
                _paint_ticks(g, st["ticks"], cfg.get("div", 2))
                return g, info, st
        if (rr0 <= y <= rr1 and rc0 <= x <= rc1
                and (grid[y][x] in cfg["bodies"]
                     or grid[y][x] in cfg.get("glyph_bodies", {}))):
            cost = 2
            for r in range(rr0, rr1 + 1):
                for c in range(rc0, rc1 + 1):
                    if g[r][c] == 0:
                        g[r][c] = BG_R
            b = grid[y][x]
            pl = _find_player(grid, cfg["left"])
            if b in cfg.get("bodies", {}) and pl is not None:
                states = cfg["bodies"][b]
                i = _body_state(grid, states)
                j = _next_index(cfg, b, i, len(states), dict(st))
                if _on_rects(pl, states[i]) and not _on_rects(pl, states[j]):
                    # the move would strand the player: refused, big penalty
                    st["ticks"] += cfg.get("penalty", 20)
                    _paint_ticks(g, st["ticks"], cfg.get("div", 2))
                    return g, info, st
            st["portal_idx"] = None
            for i, pp in enumerate(cfg.get("portals", {}).get(b, [])):
                if pl == pp:
                    st["portal_idx"] = i
            _flip(g, cfg, b, st)

    st["ticks"] += cost
    _paint_ticks(g, st["ticks"], cfg.get("div", 2))
    return g, info, st
