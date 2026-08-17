"""World model for g50t.

Level 0 keeps the hand-written model that went backtest-green (kept verbatim
below with an L0_ prefix).  Level 1+ uses a GENERIC engine that parses the
level's entry grid into a config (open cells, goal, ropes/anchors/blocks,
spawn, number of attempt slots) and re-renders every frame from scratch.

Shared vocabulary, recovered from level 0 and confirmed on the level-1 entry
frame:
  * cell grid, pitch 6.  cell(i,j) box = rows R0+6i..R0+6i+6,
    cols C0+6j..C0+6j+6 (7x7).  An OPEN cell is a full 7x7 of colour 5;
    a cell the rope merely passes through is a 3-wide corridor and is NOT
    walkable.  Cell centre = (R0+3+6i, C0+3+6j).
  * player ring = 5x5 of 9 with the centre pixel left as floor; ghosts the
    same in colour 2.
  * rope (8): 1px line along cell centres from an anchor cell (3x3 knob) to
    the block cell (5x5 sprite whose far edge is dotted).  While ANY ring
    stands on the anchor the block is pulled one cell along the rope towards
    the anchor; it snaps back the instant the anchor is vacated.  A block
    plugs its cell, and its cell is drawn as a full open cell.
  * action 5 = RESTART: the attempt just played becomes a ghost that replays
    its recorded actions, one per counted action of mine.  The legend (rows
    1-3, 3x3 swatches at cols 1+4k) shows how many attempt slots the level
    has; level 0 had 2, level 1 has 3 (so TWO ghosts are available).
  * row 63 = budget bar, 64 - ceil(m/2) pixels of 9 then 1s.
  * ordering inside a step: the player moves first, then each ghost.
"""

N = 64
ROPE_COLOURS = (8, 11)
GATE_COLOUR = 15   # paired teleport gates
MIRROR_COLOUR = 14  # a ring that copies my move with the vertical axis flipped
# The colour-14 ring is a PATROLLER: it keeps its own heading and takes one
# step per world tick, whatever I do.  When its heading is blocked it tries
# (in order) 90 deg counter-clockwise, 90 deg clockwise, then a reversal, and
# adopts whichever direction it actually took.  A block that snaps back onto
# it pins it: it cannot move again until the block is pulled away.
CCW = {1: 3, 3: 2, 2: 4, 4: 1}
CW = {1: 4, 4: 2, 2: 3, 3: 1}
OPPOSITE = {1: 2, 2: 1, 3: 4, 4: 3}
LATCH_COLOUR = 11  # stays pulled once any ring has touched its anchor
DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


def _blank():
    return [[0] * N for _ in range(N)]


def _fill(g, r0, r1, c0, c1, v):
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if 0 <= r < N and 0 <= c < N:
                g[r][c] = v


# =====================================================================
# level 0
# =====================================================================

L0_OPEN = {
    (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
    (1, 0), (1, 2),
    (2, 0), (2, 1), (2, 2),
    (3, 0),
    (4, 0),
    (5, 0),
    (6, 0),
    (7, 0), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5),
}
L0_GOAL = (7, 5)
L0_ROWS, L0_COLS = 8, 6
L0_ROPE = [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4), (5, 4),
           (5, 3), (5, 2), (5, 1), (5, 0)]
L0_ANCHOR = L0_ROPE[0]
L0_BLOCK_HOME = len(L0_ROPE) - 1

L0_CHECKPOINT = {
    "player": (0, 0),
    "ghost": {"rec": [2, 2, 2, 2, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4],
              "idx": 0, "pos": (0, 0)},
    "rec": [],
    "m": 29,
    "attempt": 2,
}


def l0_centre(cell):
    i, j = cell
    return (10 + 6 * i, 16 + 6 * j)


def l0_fresh():
    return {"player": (0, 0), "ghost": None, "rec": [], "m": 0, "attempt": 1}


def _l0_ring(g, cell, colour):
    r, c = l0_centre(cell)
    _fill(g, r - 2, r + 2, c - 2, c + 2, colour)
    g[r][c] = 5


def _l0_line_pixels(upto):
    pts = []
    for k in range(upto):
        r0, c0 = l0_centre(L0_ROPE[k])
        r1, c1 = l0_centre(L0_ROPE[k + 1])
        dr = (r1 > r0) - (r1 < r0)
        dc = (c1 > c0) - (c1 < c0)
        r, c = r0, c0
        pts.append((r, c))
        while (r, c) != (r1, c1):
            r += dr
            c += dc
            pts.append((r, c))
    if not pts:
        pts = [l0_centre(L0_ROPE[0])]
    return pts


def l0_block_index(state):
    on = state["player"] == L0_ANCHOR
    if state["ghost"] is not None and state["ghost"]["pos"] == L0_ANCHOR:
        on = True
    return L0_BLOCK_HOME - (1 if on else 0)


def l0_render(state):
    g = _blank()
    for (i, j) in L0_OPEN:
        _fill(g, 7 + 6 * i, 13 + 6 * i, 13 + 6 * j, 19 + 6 * j, 5)
    _fill(g, 48, 56, 42, 50, 5)
    _fill(g, 49, 49, 43, 49, 9)
    _fill(g, 55, 55, 43, 49, 9)
    _fill(g, 49, 55, 49, 49, 9)
    g[52][46] = 9

    bidx = l0_block_index(state)
    line = _l0_line_pixels(bidx)
    for (r, c) in line:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < N and 0 <= cc < N and g[rr][cc] == 0:
                    g[rr][cc] = 5
    bi, bj = L0_ROPE[bidx]
    _fill(g, 7 + 6 * bi, 13 + 6 * bi, 13 + 6 * bj, 19 + 6 * bj, 5)
    for (r, c) in set(line):
        g[r][c] = 8
    ar, ac = l0_centre(L0_ANCHOR)
    _fill(g, ar - 1, ar + 1, ac - 1, ac + 1, 8)
    br, bc = l0_centre(L0_ROPE[bidx])
    _fill(g, br - 2, br + 2, bc - 2, bc + 2, 8)
    g[br - 1][bc - 2] = 5
    g[br + 1][bc - 2] = 5

    if state["ghost"] is not None:
        _l0_ring(g, state["ghost"]["pos"], 2)
    _l0_ring(g, state["player"], 9)

    if state["attempt"] == 1:
        _fill(g, 1, 3, 1, 3, 9)
        g[2][2] = 0
        _fill(g, 1, 3, 5, 7, 1)
        _fill(g, 5, 5, 1, 3, 9)
    else:
        _fill(g, 1, 3, 1, 3, 2)
        g[2][2] = 0
        _fill(g, 1, 3, 5, 7, 9)
        g[2][6] = 0
        _fill(g, 5, 5, 5, 7, 9)

    used = (state["m"] + 1) // 2
    for c in range(N):
        g[63][c] = 1 if c >= N - used else 9
    return g


def _l0_occupied(state, cell, mover):
    if cell not in L0_OPEN:
        return True
    if cell == L0_ROPE[l0_block_index(state)]:
        return True
    other = (state["ghost"]["pos"]
             if (state["ghost"] and mover != "ghost") else None)
    if mover == "ghost":
        other = state["player"]
    return other is not None and cell == other


def _l0_try_move(state, pos, action, mover):
    d = DIRS.get(action)
    if d is None:
        return pos
    tgt = (pos[0] + d[0], pos[1] + d[1])
    return pos if _l0_occupied(state, tgt, mover) else tgt


def l0_predict(state, action):
    s = {
        "player": state["player"],
        "ghost": None if state["ghost"] is None else dict(state["ghost"]),
        "rec": list(state["rec"]),
        "m": state["m"],
        "attempt": state["attempt"],
    }
    info = {}
    if action == 5:
        s["m"] += 1
        if not s["rec"]:
            return l0_render(s), info, s
        if s["attempt"] == 1:
            s["ghost"] = {"rec": list(s["rec"]), "idx": 0, "pos": (0, 0)}
            s["attempt"] = 2
        else:
            s["ghost"] = None
            s["attempt"] = 1
        s["rec"] = []
        s["player"] = (0, 0)
        return l0_render(s), info, s

    d = DIRS.get(action)
    if d is None:
        return l0_render(s), info, s
    tgt = (s["player"][0] + d[0], s["player"][1] + d[1])
    if not (0 <= tgt[0] < L0_ROWS and 0 <= tgt[1] < L0_COLS):
        return l0_render(s), info, s
    s["m"] += 1
    s["rec"].append(action)
    s["player"] = _l0_try_move(s, s["player"], action, "player")
    if s["ghost"] is not None and s["ghost"]["idx"] < len(s["ghost"]["rec"]):
        ga = s["ghost"]["rec"][s["ghost"]["idx"]]
        s["ghost"]["idx"] += 1
        s["ghost"]["pos"] = _l0_try_move(s, s["ghost"]["pos"], ga, "ghost")
    if s["player"] == L0_GOAL:
        info["level_up"] = True
    return l0_render(s), info, s


# The entry frame of level 1, observed after the level-0 win.  A model cannot
# invent the next level's layout, so the one level-up transition in the
# history is answered from this record.
L1_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0909011101110000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555500000000000000000000000555555500000555555500000000",
    "0000000555555500000000000000000000000555555500000555555500000000",
    "0000000555555500000000000000000000000555555500000555555500000000",
    "0000000555555500000000000000000000000555555500000555555500000000",
    "0000000555555500000000005555555550000555555500000555555500000000",
    "0000000555555555555555555999999950000555555500000555555500000000",
    "0000000555555585858555555555555950000555555500000555555500000000",
    "0000000555555588888555555555555950000555555500000555555500000000",
    "0000000555555588888555555555955950000555555500000555555500000000",
    "0000000555555588888555555555555950000555555500000555555500000000",
    "0000000555555588888555555555555950000555555500000555555500000000",
    "0000000555555555855555555999999950000555555555555555555500000000",
    "0000000000000005850000005555555550000555555555555599999500000000",
    "0000000000000005850000000000000000000558885555555599999500000000",
    "0000000000000005850000000000000000000558885555555599599500000000",
    "0000000000000005850000000000000000000558885555555599999500000000",
    "0000000000000005850000000000000000000555855555555599999500000000",
    "0000000000000005850000000000000000000555855555555555555500000000",
    "0000000000000005850000000000000000000005850000000555555500000000",
    "0000000000000005850000000000000000000005850000000555555500000000",
    "0000000000000005850000000000000000000005850000000555555500000000",
    "0000000000000005850000000000000000000005850000000555555500000000",
    "0000000000000005850000000000000000000005850000000555555500000000",
    "0000000555555555855555555555555500000005850000000555555500000000",
    "0000000555555555855555555555555500000005850000000555555500000000",
    "0000000555555558885555555555555500000005850000000555555500000000",
    "0000000555555558885555555555555500000005850000000555555500000000",
    "0000000555555558885555555555555500000005850000000555555500000000",
    "0000000555555555555555555555555500000005850000000555555500000000",
    "0000000555555555555555555555555500000005850000000555555500000000",
    "0000000000000000000000000555555500000005850000000555555500000000",
    "0000000000000000000000000555555500000005850000000555555500000000",
    "0000000000000000000000000555555500000005850000000555555500000000",
    "0000000000000000000000000555555500000005850000000555555500000000",
    "0000000000000000000000000555555500000005850000000555555500000000",
    "0000000555555555555555555555555555555555855555555555555500000000",
    "0000000555555555555555555555555555555588888555555555555500000000",
    "0000000555555555555555555555555555555588888555555555555500000000",
    "0000000555555555555555555555555555555588888555555555555500000000",
    "0000000555555555555555555555555555555588888555555555555500000000",
    "0000000555555555555555555555555555555585858555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "9999999999999999999999999999999999999999999999999999999999999999",
]


def _decode(hexrows):
    return [[int(ch, 16) for ch in row] for row in hexrows]


# =====================================================================
# generic engine (level 1+)
# =====================================================================

def _components(pixels):
    pixels = set(pixels)
    out = []
    while pixels:
        seed = sorted(pixels)[0]
        comp = set([seed])
        frontier = [seed]
        pixels.discard(seed)
        while frontier:
            r, c = frontier.pop()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (r + dr, c + dc)
                if p in pixels:
                    pixels.discard(p)
                    comp.add(p)
                    frontier.append(p)
        out.append(comp)
    return out


def _path_in(comp, start, goal):
    """Shortest 4-connected path inside comp from start to goal."""
    prev = {start: None}
    frontier = [start]
    while frontier:
        nxt = []
        for p in frontier:
            if p == goal:
                path = []
                q = p
                while q is not None:
                    path.append(q)
                    q = prev[q]
                path.reverse()
                return path
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (p[0] + dr, p[1] + dc)
                if q in comp and q not in prev:
                    prev[q] = p
                    nxt.append(q)
        frontier = nxt
    return []


def _parse(entry):
    # The cell lattice is anchored on the player ring (a 5x5 of 9 with a floor
    # centre): its centre sits at R0+3+6i, C0+3+6j.  Bounding boxes are
    # unreliable because some levels paint floor over the legend rows.
    pr = pc = None
    for r in range(2, N - 2):
        for c in range(2, N - 2):
            ok = True
            for dr in (-2, -1, 0, 1, 2):
                for dc in (-2, -1, 0, 1, 2):
                    want = 5 if (dr == 0 and dc == 0) else 9
                    if entry[r + dr][c + dc] != want:
                        ok = False
            if ok:
                pr, pc = r, c
    R0 = (pr - 3) % 6
    C0 = (pc - 3) % 6
    nr = (N - 2 - R0 - 6) // 6 + 1
    nc = (N - 1 - C0 - 6) // 6 + 1

    def box(cell):
        i, j = cell
        return (R0 + 6 * i, R0 + 6 * i + 6, C0 + 6 * j, C0 + 6 * j + 6)

    def ctr(cell):
        return (R0 + 3 + 6 * cell[0], C0 + 3 + 6 * cell[1])

    openc = []
    for i in range(nr):
        for j in range(nc):
            r0, r1, c0, c1 = box((i, j))
            n = 0
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if entry[r][c]:
                        n += 1
            if n == 49:
                openc.append((i, j))

    # rings (5x5 of one colour with a floor centre) and the goal room
    spawn = None
    goal = None
    goal_pixels = []
    for (i, j) in openc:
        cr, cc = ctr((i, j))
        ring = True
        for dr in (-2, -1, 0, 1, 2):
            for dc in (-2, -1, 0, 1, 2):
                want = 5 if (dr == 0 and dc == 0) else 9
                if entry[cr + dr][cc + dc] != want:
                    ring = False
        if ring:
            spawn = (i, j)
            continue
        r0, r1, c0, c1 = box((i, j))
        px = [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
              if entry[r][c] == 9]
        if len(px) >= 10:
            goal = (i, j)
            goal_pixels = px

    # the colour-14 ring: moves whenever the player does, up<->down flipped
    mirror = None
    for i in range(nr):
        for j in range(nc):
            cr, cc = ctr((i, j))
            ok = True
            for dr in (-2, -1, 0, 1, 2):
                for dc in (-2, -1, 0, 1, 2):
                    want = 5 if (dr == 0 and dc == 0) else MIRROR_COLOUR
                    if entry[cr + dr][cc + dc] != want:
                        ok = False
            if ok:
                mirror = (i, j)

    ropes = []
    rope_px = []
    for col in ROPE_COLOURS:
        rope_px += [((r, c), col) for r in range(N) for c in range(N)
                    if entry[r][c] == col]
    bycol = {}
    for (p, col) in rope_px:
        bycol.setdefault(col, []).append(p)
    comps = []
    for col in sorted(bycol):
        for comp in _components(bycol[col]):
            comps.append((comp, col))
    for comp, colour in comps:
        centres = []
        for i in range(nr):
            for j in range(nc):
                if ctr((i, j)) in comp:
                    centres.append((i, j))
        block = None
        anchor = None
        for cell in centres:
            cr, cc = ctr(cell)
            n = 0
            for dr in (-2, -1, 0, 1, 2):
                for dc in (-2, -1, 0, 1, 2):
                    if (cr + dr, cc + dc) in comp:
                        n += 1
            if n >= 20:
                block = cell
        for cell in centres:
            if cell == block:
                continue
            cr, cc = ctr(cell)
            n = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if (cr + dr, cc + dc) in comp:
                        n += 1
            if n == 9:
                anchor = cell
        if block is None or anchor is None:
            continue
        pix = _path_in(comp, ctr(anchor), ctr(block))
        cells = []
        for p in pix:
            for i in range(nr):
                for j in range(nc):
                    if ctr((i, j)) == p:
                        cells.append((i, j))
        # a dotted far edge on the block sprite (two floor pixels) is part of
        # the sprite in colour 8; the colour-11 block is drawn solid
        br, bc = ctr(block)
        dots = sum(1 for dr in (-2, -1, 0, 1, 2) for dc in (-2, -1, 0, 1, 2)
                   if (br + dr, bc + dc) not in comp) == 2
        ropes.append({"cells": cells, "anchor": anchor, "block": block,
                      "colour": colour, "dots": dots,
                      "latch": colour == LATCH_COLOUR})

    # colour-15 gate systems: each connected structure holds two 7x7 gate
    # outlines and one 3x3 knob.  Stepping onto the knob throws every ring
    # standing on that system's gates across to its partner.
    gate_px = [(r, c) for r in range(N) for c in range(N)
               if entry[r][c] == GATE_COLOUR]
    systems = []
    for comp in _components(gate_px):
        gates = []
        knob = None
        for i in range(nr):
            for j in range(nc):
                r0, r1, c0, c1 = box((i, j))
                border = [(r0, c) for c in range(c0, c1 + 1)]
                border += [(r1, c) for c in range(c0, c1 + 1)]
                border += [(r, c0) for r in range(r0, r1 + 1)]
                border += [(r, c1) for r in range(r0, r1 + 1)]
                if border and all(p in comp for p in border):
                    gates.append((i, j))
                    continue
                cr, cc = ctr((i, j))
                if all((cr + dr, cc + dc) in comp
                       for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
                    knob = (i, j)
        if len(gates) == 2:
            systems.append({"gates": (gates[0], gates[1]), "knob": knob})

    slots = 0
    while 1 + 4 * slots < 16 and entry[1][1 + 4 * slots] in (9, 2, 1):
        slots += 1

    # the budget bar spans only the columns that are 9 in the entry frame
    # (level 4 paints a floor stripe down column 63)
    barw = 0
    for c in range(N):
        if entry[N - 1][c] == 9:
            barw = c + 1

    cfg = {
        "R0": R0, "C0": C0, "nr": nr, "nc": nc,
        "open": sorted(openc), "spawn": spawn, "goal": goal,
        "goal_pixels": sorted(goal_pixels), "ropes": ropes, "slots": slots,
        "gates": systems, "barw": barw,
        "mirror0": mirror,
        "overlay": (),
    }
    # anything in the entry frame this model does not explain yet (e.g. the
    # colour-15 structures of level 3) is kept as a static overlay, so the
    # render stays exact while its mechanics are still unknown
    s0 = {"player": tuple(spawn), "ghosts": [], "rec": [], "m": 0,
          "attempt": 1, "latched": (),
          "mirror": None if mirror is None else tuple(mirror),
          "mdir": 1}
    base = g_render(cfg, s0)
    cfg["overlay"] = tuple(sorted(
        (r, c, entry[r][c]) for r in range(N) for c in range(N)
        if base[r][c] != entry[r][c]))
    return cfg


def _ctr(cfg, cell):
    return (cfg["R0"] + 3 + 6 * cell[0], cfg["C0"] + 3 + 6 * cell[1])


def _box(cfg, cell):
    i, j = cell
    return (cfg["R0"] + 6 * i, cfg["R0"] + 6 * i + 6,
            cfg["C0"] + 6 * j, cfg["C0"] + 6 * j + 6)


def _rings_on(state, cell):
    if state["player"] == cell:
        return True
    for gh in state["ghosts"]:
        if gh["pos"] == cell:
            return True
    return False


def _block_idx(cfg, state, rope, k=None):
    home = len(rope["cells"]) - 1
    if rope.get("latch"):
        # colour 11 is a TOGGLE: every time a ring steps ONTO the anchor the
        # block flips between home and pulled, and it stays where it is when
        # the anchor is vacated.  (Observed: press -> pulled, step off ->
        # still pulled, press again -> home.)
        pulled = k in state.get("latched", ())
    else:
        pulled = _rings_on(state, rope["anchor"])
    return home - 1 if pulled else home


def _block_cells(cfg, state):
    return [rope["cells"][_block_idx(cfg, state, rope, k)]
            for k, rope in enumerate(cfg["ropes"])]


def g_render(cfg, state):
    g = _blank()
    for cell in cfg["open"]:
        r0, r1, c0, c1 = _box(cfg, cell)
        _fill(g, r0, r1, c0, c1, 5)

    if cfg["goal"] is not None:
        r0, r1, c0, c1 = _box(cfg, cfg["goal"])
        _fill(g, r0 - 1, r1 + 1, c0 - 1, c1 + 1, 5)
        for (r, c) in cfg["goal_pixels"]:
            g[r][c] = 9

    for k, rope in enumerate(cfg["ropes"]):
        bidx = _block_idx(cfg, state, rope, k)
        cells = rope["cells"]
        line = []
        for k in range(bidx):
            r0, c0 = _ctr(cfg, cells[k])
            r1, c1 = _ctr(cfg, cells[k + 1])
            dr = (r1 > r0) - (r1 < r0)
            dc = (c1 > c0) - (c1 < c0)
            r, c = r0, c0
            line.append((r, c))
            while (r, c) != (r1, c1):
                r += dr
                c += dc
                line.append((r, c))
        if not line:
            line = [_ctr(cfg, cells[0])]
        for (r, c) in line:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < N and 0 <= cc < N and g[rr][cc] == 0:
                        g[rr][cc] = 5
        r0, r1, c0, c1 = _box(cfg, cells[bidx])
        _fill(g, r0, r1, c0, c1, 5)
        col = rope.get("colour", 8)
        for (r, c) in set(line):
            g[r][c] = col
        ar, ac = _ctr(cfg, rope["anchor"])
        _fill(g, ar - 1, ar + 1, ac - 1, ac + 1, col)
        br, bc = _ctr(cfg, cells[bidx])
        _fill(g, br - 2, br + 2, bc - 2, bc + 2, col)
        if not rope.get("dots", True):
            dr = dc = 0
        elif bidx > 0:
            pr, pc = cells[bidx - 1]
            dr = (pr > cells[bidx][0]) - (pr < cells[bidx][0])
            dc = (pc > cells[bidx][1]) - (pc < cells[bidx][1])
        else:
            dr = dc = 0
        fr, fc = br - 2 * dr, bc - 2 * dc
        if dr:
            g[fr][fc - 1] = 5
            g[fr][fc + 1] = 5
        elif dc:
            g[fr - 1][fc] = 5
            g[fr + 1][fc] = 5

    for (r, c, v) in cfg.get("overlay", ()):
        g[r][c] = v

    if state.get("mirror") is not None:
        r, c = _ctr(cfg, state["mirror"])
        _fill(g, r - 2, r + 2, c - 2, c + 2, MIRROR_COLOUR)
        g[r][c] = 5

    for gh in state["ghosts"]:
        r, c = _ctr(cfg, gh["pos"])
        _fill(g, r - 2, r + 2, c - 2, c + 2, 2)
        g[r][c] = 5
    r, c = _ctr(cfg, state["player"])
    _fill(g, r - 2, r + 2, c - 2, c + 2, 9)
    g[r][c] = 5

    for k in range(cfg["slots"]):
        c0 = 1 + 4 * k
        if k < state["attempt"] - 1:
            _fill(g, 1, 3, c0, c0 + 2, 2)
            g[2][c0 + 1] = 0
        elif k == state["attempt"] - 1:
            _fill(g, 1, 3, c0, c0 + 2, 9)
            g[2][c0 + 1] = 0
        else:
            _fill(g, 1, 3, c0, c0 + 2, 1)
    mc = 1 + 4 * (state["attempt"] - 1)
    _fill(g, 5, 5, mc, mc + 2, 9)

    # level 1's bar is one step behind level 0's: it is still full after the
    # first action, i.e. floor(m/2) pixels spent rather than ceil(m/2).
    used = state["m"] // 2
    for c in range(N):
        g[63][c] = 1 if c >= N - used else 9
    # level 4 paints a floor stripe down column 63 that covers the bar's last
    # pixel, so static decoration wins over the bar on that row
    for (r, c, v) in cfg.get("overlay", ()):
        if r == N - 1:
            g[r][c] = v
    return g


def _g_occupied(cfg, state, cell, mover):
    if cell not in [tuple(x) for x in cfg["open"]]:
        return True
    if cell in _block_cells(cfg, state):
        return True
    # rings do NOT block each other: player and ghosts pass through and may
    # share a cell (observed on the spawn cell of level 2)
    return False


def _g_try_move(cfg, state, pos, action, mover, blocked=None):
    d = DIRS.get(action)
    if d is None:
        return pos
    tgt = (pos[0] + d[0], pos[1] + d[1])
    if blocked is None:
        if _g_occupied(cfg, state, tgt, mover):
            return pos
    elif tgt not in [tuple(x) for x in cfg["open"]] or tgt in blocked:
        return pos
    return tgt


def _resolve_gates(cfg, s, before, after):
    """A ring standing on a gate is thrown to its partner on the tick some
    ring steps ONTO that gate system's knob (level 4: a ghost already parked
    on the knob does nothing)."""
    rings = [("player", None)] + [("ghost", k)
                                  for k in range(len(s["ghosts"]))]
    if s.get("mirror") is not None:
        rings.append(("mirror", None))
    for sysm in cfg.get("gates", ()):
        knob = sysm.get("knob")
        if knob is not None:
            pulse = False
            for idx in range(len(after)):
                if (tuple(after[idx]) == tuple(knob)
                        and tuple(before[idx]) != tuple(knob)):
                    pulse = True
            if not pulse:
                continue
        a, b = tuple(sysm["gates"][0]), tuple(sysm["gates"][1])
        link = {a: b, b: a}
        for idx, (kind, k) in enumerate(rings):
            if idx >= len(after):
                break
            pos = tuple(after[idx])
            if pos in link:
                if kind == "player":
                    s["player"] = link[pos]
                elif kind == "ghost":
                    s["ghosts"][k]["pos"] = link[pos]
                else:
                    s["mirror"] = link[pos]


def _update_latches(cfg, s, before, after):
    """before/after: ring positions this step; a toggle fires on ENTRY."""
    lat = set(s.get("latched", ()))
    for k, rope in enumerate(cfg["ropes"]):
        if not rope.get("latch"):
            continue
        a = tuple(rope["anchor"])
        for old_p, new_p in zip(before, after):
            if tuple(new_p) == a and tuple(old_p) != a:
                lat.symmetric_difference_update([k])
    s["latched"] = tuple(sorted(lat))


def g_predict(cfg, state, action):
    s = {
        "player": state["player"],
        "mirror": state.get("mirror"),
        "mdir": state.get("mdir", 1),
        "latched": tuple(state.get("latched", ())),
        "ghosts": [{"rec": list(gh["rec"]), "idx": gh["idx"],
                    "pos": gh["pos"]} for gh in state["ghosts"]],
        "rec": list(state["rec"]),
        "m": state["m"],
        "attempt": state["attempt"],
    }
    info = {}
    spawn = tuple(cfg["spawn"])

    if action == 5:
        s["m"] += 1
        if not s["rec"]:
            return g_render(cfg, s), info, s
        if s["attempt"] < cfg["slots"]:
            s["ghosts"].append({"rec": list(s["rec"]), "idx": 0,
                                "pos": spawn})
            s["attempt"] += 1
        else:
            s["ghosts"] = []
            s["attempt"] = 1
        for gh in s["ghosts"]:
            gh["idx"] = 0
            gh["pos"] = spawn
        s["rec"] = []
        s["player"] = spawn
        s["latched"] = ()
        if cfg["mirror0"] is not None:
            s["mirror"] = tuple(cfg["mirror0"])
            s["mdir"] = 1
        return g_render(cfg, s), info, s

    d = DIRS.get(action)
    if d is None:
        return g_render(cfg, s), info, s
    tgt = (s["player"][0] + d[0], s["player"][1] + d[1])
    if not (0 <= tgt[0] < cfg["nr"] and 0 <= tgt[1] < cfg["nc"]):
        return g_render(cfg, s), info, s

    s["m"] += 1
    before = ([s["player"]] + [gh["pos"] for gh in s["ghosts"]]
              + ([s["mirror"]] if s.get("mirror") is not None else []))
    s["player"] = _g_try_move(cfg, s, s["player"], action, "player")
    # only moves that actually happened go into the attempt's replay script
    if s["player"] != before[0]:
        s["rec"].append(action)
    # the world only ticks when the player actually moves: a move blocked by
    # a wall or a block still costs an action but freezes the ghosts
    moved = s["player"] != before[0]
    for k, gh in enumerate(s["ghosts"]):
        if moved and gh["idx"] < len(gh["rec"]):
            ga = gh["rec"][gh["idx"]]
            gh["idx"] += 1
            gh["pos"] = _g_try_move(cfg, s, gh["pos"], ga, k)
    if s.get("mirror") is not None and moved:
        # the patroller is resolved against the block layout as it stood
        # BEFORE this tick's moves: it walked into (0,7) on the very tick the
        # spring block snapped back there, and ended up under it
        bl_before = set(_block_cells(cfg, state))
        d = s.get("mdir", 1)
        for cand in (d, CCW[d], CW[d], OPPOSITE[d]):
            p = _g_try_move(cfg, s, s["mirror"], cand, "mirror",
                            blocked=bl_before)
            if p != s["mirror"]:
                s["mirror"] = p
                s["mdir"] = cand
                break
        # a block snapping back onto the patroller destroys it
        if tuple(s["mirror"]) in set(_block_cells(cfg, s)):
            s["mirror"] = None
    after = ([s["player"]] + [gh["pos"] for gh in s["ghosts"]]
             + ([s["mirror"]] if s.get("mirror") is not None else []))
    _update_latches(cfg, s, before, after)
    _resolve_gates(cfg, s, before, after)
    if cfg["goal"] is not None and s["player"] == tuple(cfg["goal"]):
        info["level_up"] = True
    return g_render(cfg, s), info, s


# =====================================================================
# harness entry points
# =====================================================================

# Recorded actions cannot be read off a frame; when init_state is handed a
# mid-run frame (bfs/commit start from "now") we restore this checkpoint.
# Keep it in sync with the real run.
G_CHECKPOINTS = {
    6: {'player': (4, 4), 'latched': (), 'mirror': (9, 3), 'mdir': 1, 'rec': [], 'm': 0, 'attempt': 1, 'ghosts': []},
}

# Entry grid per level: the geometry (and above all the SPAWN cell) must be
# parsed from the level's entry frame, never from a mid-run frame.
L2_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0909011101110000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000555555500000000000000000555555500000000000555555500000000",
    "0000000555555500000000000000000555555500000000000555555500000000",
    "0000000555555500000000000000000555555500000000000555555500000000",
    "0000000555555500000000000000000555555500000000000555555500000000",
    "0000000555555500005555555550000555555500000000000555555500000000",
    "0000000555555500005999999950000555555500000000000555555500000000",
    "00000005999995000059555559500005555555000000000005bbbbb500000000",
    "000000059999950000595555595000055bbb55555555555555bbbbb500000000",
    "000000059959950000595595595000055bbbbbbbbbbbbbbbbbbbbbb500000000",
    "000000059999950000595555595000055bbb55555555555555bbbbb500000000",
    "00000005999995000059555559500005555555000000000005bbbbb500000000",
    "0000000555555500005955555950000555555500000000000555555500000000",
    "0000000000000000005555555550000555555500000000000555555500000000",
    "0000000000000000000555555500000555555500000000000555555500000000",
    "0000000000000000000555555500000555555500000000000555555500000000",
    "0000000000000000000555555500000555555500000000000555555500000000",
    "0000000000000000000555555500000555555500000000000555555500000000",
    "0000000555555555555555555500000555555555555500000555555500000000",
    "0000000555555555555585858500000555555555555500000555555500000000",
    "0000000555555555555588888500000555555558885500000555555500000000",
    "0000000555555555555588888500000555555558885500000555555500000000",
    "0000000555555555555588888500000555555558885500000555555500000000",
    "0000000555555555555588888500000555555555855500000555555500000000",
    "0000000555555555555555855500000555555555855500000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555500000005850000000000000005850000000555555500000000",
    "0000000555555555555555855555555555555555855555555555555500000000",
    "0000000555555555555555855555555555555588888555555555555500000000",
    "0000000555555555555558885555555555555588888555555555555500000000",
    "0000000555555555555558885555555555555588888555555555555500000000",
    "0000000555555555555558885555555555555588888555555555555500000000",
    "0000000555555555555555555555555555555585858555555555555500000000",
    "0000000555555555555555555555555555555555555555555555555500000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "9999999999999999999999999999999999999999999999999999999999999999",
]

L3_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0909011101110000000000000000000000000000000000000000000000000000",
    "0999011101110000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0999000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000555555555555555555555555500000555555555555555555500000000",
    "0000000555555555555555555599999500000555555555555555555500000000",
    "0000000555555555555555555599999500000555555555555555555500000000",
    "0000000555555555555555555599599500000555555555555555555500000000",
    "0000000555555555555555555599999500000555555555555555555500000000",
    "0000000555555555555555555599999500000555555555555555555500000000",
    "0000000555555555555555555555555500000555555555555555555500000000",
    "0000000555555500000000000555555500000555555500000555555500000000",
    "0000000555555500000000000555555500000555555500000555555500000000",
    "0000000555555500000000000555555500000555555500000555555500000000",
    "0000000555555500000000000555555500000555555500000555555500000000",
    "0000000555555500000000000555555500000555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000555555500000000000555555555555555555500000555555500000000",
    "0000000588888500000000000000000555555500000000000555555500000000",
    "000000055888855555555555555555555888550000000000055fff5500000000",
    "000000058888888888888888888888888888550000000000055fff5500000000",
    "000000055888855555555555555555555888550000000000055fff5500000000",
    "0000000588888500000000000000000555555500000000000555f55500000000",
    "0000000555555500000000000000000555555500000000000555f55500000000",
    "0000000555555500000000000000000000000000000000000005f50000000000",
    "0000000555555500000000000000000000000000000000000005f50000000000",
    "0000000555555500000000000000000000000000000000000005f50000000000",
    "0000000555555500000000000000000000000000000000000005f50000000000",
    "0000000555555500000000005555555550000000000000000005f50000000000",
    "0000000555555555555555555fffffff50000000000000000005f50000000000",
    "0000000555555555555555555f55555f50000000000000000005f50000000000",
    "0000000555555555555555555f55555f55555555555555555555f50000000000",
    "0000000555555555555555555f55555ffffffffffffffffffffff50000000000",
    "0000000555555555555555555f55555f55555555555555555555f50000000000",
    "0000000555555555555555555f55555f50000000000000000005f50000000000",
    "0000000555555555555555555fffffff50000000000000000005f50000000000",
    "0000000000000000000000005555555550000000000000000005f50000000000",
    "0000000000000000000000000000000000000000000000000005f50000000000",
    "0000000000000000000000000000000000000000000000000005f50000000000",
    "0000000000000000000000000000000000000000000000000005f50000000000",
    "0000005555555550000000005555555550000000000000000005f50000000000",
    "0000005999999955555555555fffffff50000000000000000005f50000000000",
    "0000005955555555555555555f55555f50000000000000000005f50000000000",
    "0000005955555555555555555f55555f55555555555555555555f50000000000",
    "0000005955955555555555555f55555ffffffffffffffffffffff50000000000",
    "0000005955555555555555555f55555f55555555555555555555550000000000",
    "0000005955555555555555555f55555f50000000000000000000000000000000",
    "0000005999999955555555555fffffff50000000000000000000000000000000",
    "0000005555555550000000005555555550000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "9999999999999999999999999999999999999999999999999999999999999999",
]

L4_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0999011101110000000000000000000000000000000000000000000000000005",
    "0909011101110000000000000000000000000000000000000000000000000005",
    "0999011101110000000000000000000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0999000000000000000000000000000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0555555500000000000555555555555555555555555555555555555555555505",
    "05555555000000000005bbbbb555555555555555555555555555555555555505",
    "055bbb55555555555555bbbbb555555555555555555555555555555555555505",
    "055bbbbbbbbbbbbbbbbbbbbbb555555555555555555555555555555555555505",
    "055bbb55555555555555bbbbb555555555555555555555555555555555555505",
    "05555555000000000005bbbbb555555555555555555555555555555555555505",
    "0555555500000000000555555555555555555555555555555555555555555505",
    "0599999500000000000555555500000000000555555500000000000555555505",
    "0599999500000000000555555500000000000555555500000000000555555505",
    "0599599500000000000555555500000000000555555500000000000555555505",
    "0599999500000000000555555500000000000555555500000000000555555505",
    "0599999500000000000555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555500000000000555555505",
    "0555555555555555555555555500000000000555555555555555555555555505",
    "05555555000000000005555555000000000005bbbbb555555555555555555505",
    "055555550000000000055bbb55555555555555bbbbb55555555555555fff5505",
    "055555550000000000055bbbbbbbbbbbbbbbbbbbbbb55555555555555fff5505",
    "055555550000000000055bbb55555555555555bbbbb55555555555555fff5505",
    "05555555000000000005555555000000000005bbbbb555555555555555f55505",
    "0555555555555555555555555500000000000555555555555555555555f55505",
    "0555555555555555555555555500000000000555555500000000000005f50005",
    "0555555555555555555555555500000000000555555500000000000005f50005",
    "0555555555555555555555555500000000000555555500000000000005f50005",
    "0555555555555555555555555500000000000555555500000000000005f50005",
    "0555555555555555555555555500000000000555555555555550000005f50005",
    "0555555555555555555555555500000000000555555fffffff50000005f50005",
    "0000000000000000000555555500000000000555555f55555f50000005f50005",
    "0000000000000000000558885500000000000555555f55555f55555555f50005",
    "0000000000000000000558885500000000000555555f55555ffffffffff50005",
    "0000000000000000000558885500000000000555555f55555f55555555f50005",
    "0000005555555550000555855500000000000555555f55555f50000005f50005",
    "0000005999999950000555855500000000000555555fffffff50000005f50005",
    "0000005955555950000005850000000000000000005555555550000005f50005",
    "0000005955555950000005850000000000000000000000000000000005f50005",
    "0000005955955950000005850000000000000000000000000000000005f50005",
    "0000005955555950000005850000000000000000000000000000000005f50005",
    "0000005955555950000005850000000000000000005555555550000005f50005",
    "0000005955555950000005850000000000000555555fffffff50000005f50005",
    "0000005555555550000005850000000000000555555f55555f50000005f50005",
    "0000000555555500000005850000000000000555555f55555f55555555f50005",
    "0000000555555500000005850000000000000555555f55555ffffffffff50005",
    "0000000555555500000005850000000000000555555f55555f55555555550005",
    "0000000555555500000005850000000000000555555f55555f50000000000005",
    "0000000555555555555555855555555555555555555fffffff50000000000005",
    "0000000555555555555588888555555555555555555555555550000000000005",
    "0000000555555555555588888555555555555555555500000000000000000005",
    "0000000555555555555588888555555555555555555500000000000000000005",
    "0000000555555555555588888555555555555555555500000000000000000005",
    "0000000555555555555585858555555555555555555500000000000000000005",
    "0000000555555555555555555555555555555555555500000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "9999999999999999999999999999999999999999999999999999999999999995",
]

L5_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0999011101110000000000000000000000000000000000000000000000000005",
    "0909011101110000000000000000000000000000000000000000000000000005",
    "0999011101110000000000000000000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0999000000000000000000000000000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0555555555555555555555555555555555555555555555555555555555555505",
    "0555555555555555555555555555555585858555555585858555555555555505",
    "055bbb555555555555555bbb5555555588888555555588888555555555555505",
    "055bbb555555555555555bbb5555555588888555555588888555555555555505",
    "055bbb555555555555555bbb5555555588888555555588888555555555555505",
    "0555b55555555555555555b55555555588888555555588888555555555555505",
    "0555b55555555555555555b55555555555855555555555855555555555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b50000000005850000000005850000000555555505",
    "0005b50000000000000005b500000000058500000000058500000005eeeee505",
    "0005b50000000000000005b500000000058500000000058500000005eeeee505",
    "0005b50000000000000005b500000000058500000000058500000005ee5ee505",
    "0005b50000000000000005b500000000058500000000058500000005eeeee505",
    "0005b50000000000000005b500000000058500000000058500000005eeeee505",
    "0555b55555555555555555b55500000555855555555555855500000555555505",
    "05bbbbb5555555555555bbbbb500000555855555555555855500000000000005",
    "05bbbbb5555555555555bbbbb500000558885555555558885500000000000005",
    "05bbbbb5555555555555bbbbb500000558885555555558885500000000000005",
    "05bbbbb5555555555555bbbbb500000558885555555558885500000000000005",
    "05bbbbb5555555555555bbbbb500000555555555555555555500000000000005",
    "0555555555555555555555555500000555555555555555555555555555555505",
    "0555555500000000000555555500000000000000000555555555555599999505",
    "0555555500000000000555555500000000000000000555555555555599999505",
    "0555555500000000000555555500000000000000000555555555555599599505",
    "0555555500000000000555555500000000000000000555555555555599999505",
    "0555555500000000000555555500000000000000000555555555555599999505",
    "0555555500000555555555555555555555555555555555555555555555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000555555555555555555555555555555555555500000555555505",
    "0555555500000000000000000000000555555500000000000000000555555505",
    "0555555500000000000000000000000555555500000000000000000555555505",
    "0555555500000000000000000000000555555500000000000000000555555505",
    "0555555500000000000000000000000555555500000000000000000555555505",
    "0555555500000000000000000000000555555500005555555550000555555505",
    "0555555500000555555500000000000555555555555999999950000555555505",
    "05555555000005555555000000000005bbbbb555555555555950000555555505",
    "055555550000055bbb55555555555555bbbbb555555555555950000555555505",
    "055555550000055bbbbbbbbbbbbbbbbbbbbbb555555555955950000555555505",
    "055555550000055bbb55555555555555bbbbb555555555555950000555555505",
    "05555555000005555555000000000005bbbbb555555555555950000555555505",
    "0555555555555555555500000000000555555555555999999950000555555505",
    "0555555555555555555500000000000000000000005555555550000000000005",
    "0555555555555555555500000000000000000000000000000000000000000005",
    "0555555555555555555500000000000000000000000000000000000000000005",
    "0555555555555555555500000000000000000000000000000000000000000005",
    "0555555555555555555500000000000000000000000000000000000000000005",
    "0555555555555555555500000000000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "9999999999999999999999999999999999999999999999999999999999999995",
]

L6_ENTRY_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000005",
    "0999011101110555555500000000000555555555555555555555555500000005",
    "0909011101110555555500000000000588888555555555555555555500000005",
    "099901110111055888555555555555558888555555555555555fff5555555505",
    "000000000000055888888888888888888888855555555555555ffffffffff505",
    "099900000000055888555555555555558888555555555555555fff555555f505",
    "000000000000055555550000000000058888855555555555555555550005f505",
    "000000000000055555550000000000055555555555555555555555550005f505",
    "000000000000055555550000000000055555550000000000000000000005f505",
    "000000000000055555550000000000055555550000000000000000000005f505",
    "000000000000055555550000000000055555550000000000000000000005f505",
    "000000000000055555550000000000055555550000000000000000000005f505",
    "000000000000555555555000000000055555550000000000000000000005f505",
    "0000000000005fffffff5000055555555555555555555555555555550005f505",
    "0000000000005f55555f5000055555555555555555555555555555550005f505",
    "0005555555555f55555f5000055555555555555555555555555555550005f505",
    "0005ffffffffff55555f5000055555555555555555555555555555550005f505",
    "0005f55555555f55555f5000055555555555555555555555555555550005f505",
    "0005f50000005f55555f5000055555555555555555555555555555550005f505",
    "0005f50000005fffffff5000055555555555555555555555555555550005f505",
    "0005f5000000555555555000000000000000055555550000055555550005f505",
    "0005f5000000000000000000000000000000055555550000055555550005f505",
    "0005f5000000000000000000000000000000055555550000055555550005f505",
    "0005f5000000000000000000000000000000055555550000055555550005f505",
    "0005f5000000555555555000000000000000055555550000055555550005f505",
    "0555f55500005fffffff5555555555550000055555550000055555550005f505",
    "0555f55500005f55555f5555559999950000055555550000055555550005f505",
    "055fff5555555f55555f5555559999950000055555550000055555550005f505",
    "055fffffffffff55555f5555559959950000055555550000055555550005f505",
    "055fff5555555f55555f5555559999950000055555550000055555550005f505",
    "0555555500005f55555f5555559999950000055555550000055555550005f505",
    "0555555500005fffffff5555555555550000055555550000055555550005f505",
    "055555550000555555555000055555550000055555550000055555550005f505",
    "055555550000000000000000055555550000055555550000055555550005f505",
    "055555550000000000000000055555550000055555550000055555550005f505",
    "055555550000000000000000055555550000055555550000055555550005f505",
    "055555550000000000000000055555550000055555550000555555555005f505",
    "0555555500000000000555555555555555555555555500005fffffff5005f505",
    "05bbbbb500000000000555555555555555555555555500005f55555f5005f505",
    "05bbbbb55555555555555bbb5555555555555555555500005f55555f5555f505",
    "05bbbbbbbbbbbbbbbbbbbbbb5555555555555555555500005f55555ffffff505",
    "05bbbbb55555555555555bbb5555555555555555555500005f55555f5555f505",
    "05bbbbb500000000000555555555555555555555555500005f55555f5005f505",
    "0555555500000000000555555555555555555555555500005fffffff5005f505",
    "055555550000000000055555550000000000000000000000555555555005f505",
    "055555550000000000055555550000000000000000000000000000000005f505",
    "055555550000000000055555550000000000000000000000000000000005f505",
    "055555550000000000055555550000000000000000000000000000000005f505",
    "055555550000000000055555550000555555555000000000555555555005f505",
    "0555555500000000000555555500005999999955555555555fffffff5005f505",
    "0555555500000000000000000000005955555555555555555f55555f5005f505",
    "0555555500000000000000000000005955555555555555555f55555f5555f505",
    "0555555500000000000000000000005955955555555555555f55555ffffff505",
    "0555555500000000000000000000005955555555555555555f55555f55555505",
    "0555555500000000000000000000005955555555555555555f55555f50000005",
    "0555555555555555555555555500005999999955555555555fffffff50000005",
    "05555555555555555555eeeee500005555555550000000005555555550000005",
    "05555555555555555555eeeee500000000000000000000000000000000000005",
    "05555555555555555555ee5ee500000000000000000000000000000000000005",
    "05555555555555555555eeeee500000000000000000000000000000000000005",
    "05555555555555555555eeeee500000000000000000000000000000000000005",
    "0555555555555555555555555500000000000000000000000000000000000005",
    "0000000000000000000000000000000000000000000000000000000000000005",
    "9999999999999999999999999999999999999999999999999999999999999995",
]

LEVEL_ENTRIES = {1: L1_ENTRY_HEX, 2: L2_ENTRY_HEX, 3: L3_ENTRY_HEX, 4: L4_ENTRY_HEX, 5: L5_ENTRY_HEX, 6: L6_ENTRY_HEX}


def init_state(entry_grid):
    if CURRENT_LEVEL == 0:
        s = l0_fresh()
        if entry_grid is not None and l0_render(s) != [list(r) for r
                                                       in entry_grid]:
            c = dict(L0_CHECKPOINT)
            c["rec"] = list(c["rec"])
            if c["ghost"] is not None:
                c["ghost"] = dict(c["ghost"])
                c["ghost"]["rec"] = list(c["ghost"]["rec"])
            return c
        return s

    base = ([list(r) for r in entry_grid] if CURRENT_LEVEL not in LEVEL_ENTRIES
            else _decode(LEVEL_ENTRIES[CURRENT_LEVEL]))
    cfg = _parse(base)
    s = {"cfg": cfg, "player": tuple(cfg["spawn"]), "ghosts": [],
         "rec": [], "m": 0, "attempt": 1, "latched": (),
         "mirror": (None if cfg["mirror0"] is None
                    else tuple(cfg["mirror0"])), "mdir": 1}
    cp = G_CHECKPOINTS.get(CURRENT_LEVEL)
    if cp is not None and g_render(cfg, s) != [list(r) for r in entry_grid]:
        s["player"] = tuple(cp["player"])
        s["ghosts"] = [{"rec": list(gh["rec"]), "idx": gh["idx"],
                        "pos": tuple(gh["pos"])} for gh in cp["ghosts"]]
        s["rec"] = list(cp["rec"])
        s["m"] = cp["m"]
        s["attempt"] = cp["attempt"]
        s["latched"] = tuple(cp.get("latched", ()))
        if cp.get("mirror") is not None:
            s["mirror"] = tuple(cp["mirror"])
            s["mdir"] = cp.get("mdir", 1)
    return s


def predict(state, grid, action, x=None, y=None):
    if "cfg" not in state:
        g, info, s = l0_predict(state, action)
    else:
        cfg = state["cfg"]
        g, info, s = g_predict(cfg, state, action)
        s["cfg"] = cfg
    # a model cannot invent the next level's layout; the level-up transitions
    # already in the history are answered from the recorded entry frames
    if info.get("level_up") and (CURRENT_LEVEL + 1) in LEVEL_ENTRIES:
        g = _decode(LEVEL_ENTRIES[CURRENT_LEVEL + 1])
    return g, info, s
