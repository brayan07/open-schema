"""m0r0 world model.

Confirmed mechanics
-------------------
Frame = grid of SxS-pixel cells.  Walls are the two background colours (the
colour at pixel (1,0) for the left half, (1,63) for the right).  Floor is 5.

Two avatars move together with MIRRORED horizontal controls:
    1 = up, 2 = down (both);  3 = A left / B right;  4 = A right / B left.
Each is blocked independently by walls and by the frame edge.
A level is completed when the two avatars end up in the SAME cell.

Level 2 adds MARKER cells (a 2x2 patch of colour 9 inside the cell) which
block movement, and the click action (6):
  * clicking a marker SELECTS it -- that marker's patch turns 11 and both
    avatars turn colour 1 (dimmed);
  * clicking an avatar selects the avatar pair again (avatars 10, markers 9);
  * the arrows move whatever is selected.  A selected marker walks one cell
    per action (verified: (2,1) -> (1,1) with action 1).

The black strip on rows 0/63 is an action meter: after `a` actions in the
level it shows 3*(a+1)//7 black pixels at each end.  `a` cannot be read back
exactly from the frame, so ACTIONS_HINT carries it across commit()'s re-init.

DANGER: a cell textured with colour 8 ("checkerboard") RESETS the level if an
avatar so much as tries to step into it (verified level 3: avatars and the
marker snapped back to their start cells, meter kept running, dead=False).
It merely blocks a selected marker.  The model treats it as a wall, so plans
must be checked separately to never ATTEMPT to enter one.

Open questions
--------------
* horizontal direction convention for a selected marker (MARKER_MIRRORED)
* what clicking a plain floor cell does (never done; avoided)
* level 1's 8-on-5 "checkerboard" cells (routed around; never touched)
"""

FLOOR = 5
AV_ACTIVE, AV_DIMMED = 10, 1
MARK_IDLE, MARK_SEL = 9, 11
TEX = 8

DELTA = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1), 5: (0, 0)}

# Which avatar takes the action's horizontal sign unmirrored is a per-level
# fact: levels 0-3 give it to the LEFT avatar, level 4 to the RIGHT one.
# Keyed by the level's (rows, cols, cell size).
# keyed by (rows, cols, cell size, wall colours) -- levels 1 and 5 share a
# shape, so the wall colours are part of the key.
HFLIP = {(13, 15, 4, (6, 7)): True}   # level 4 only; level 5 is NOT flipped

# Gate/switch layouts read off each level's entry frame.  Needed because a
# switch standing under an avatar, or an open gate, is invisible in a later
# frame, and commit() re-initialises state mid-level.
LAYOUT = {
    (13, 15, 4, (6, 7)): (            # level 4
        {(4, 3): 14, (4, 4): 14, (4, 5): 14, (4, 10): 15, (4, 11): 15,
         (4, 12): 15, (8, 2): 12, (8, 3): 12, (8, 4): 12, (8, 10): 15,
         (8, 11): 15, (8, 12): 15},
        {(0, 3): 15, (5, 8): 14, (5, 14): 12, (11, 3): 15}),
    (13, 13, 4, (6, 7)): (            # level 5
        {(6, 2): 14, (6, 3): 14, (6, 4): 14,
         (6, 8): 12, (6, 9): 12, (6, 10): 12},
        {(2, 3): 12, (2, 9): 14, (9, 3): 14}),
}

# actions already taken in the current level, when known (set before commit)
ACTIONS_HINT = 41
# does a selected marker use avatar A's horizontal convention (3=left)?
MARKER_MIRRORED = False


def bar_for(a, lost=0):
    """Meter reading after `a` actions.  The accumulator gains 3 per action
    and shows one pixel per 7; it very occasionally loses a unit, which
    `lost` absorbs (re-derived from the frame whenever it disagrees)."""
    return (3 * (a + 1) - lost) // 7


def lost_for(a, bar):
    """Smallest loss putting the accumulator at the top of bucket `bar`."""
    return max(0, 3 * (a + 1) - 7 * bar - 6)


def actions_for(bar):
    a = 0
    while bar_for(a) < bar:
        a += 1
    return a


def geometry(grid):
    walls = {grid[1][0], grid[1][63]}
    rs = [r for r in range(1, 63)
          if any(grid[r][c] not in walls for c in range(1, 63))]
    cs = [c for c in range(1, 63)
          if any(grid[r][c] not in walls for r in range(1, 63))]
    r0, r1, c0, c1 = rs[0], rs[-1], cs[0], cs[-1]
    size = 1
    for s in (5, 4, 3, 2):
        if (r1 - r0 + 1) % s == 0 and (c1 - c0 + 1) % s == 0:
            size = s
            break
    return r0, c0, size, (r1 - r0 + 1) // size, (c1 - c0 + 1) // size, walls


def _classify(grid, r0, c0, S, i, j, walls):
    """-> ('wall'|'avatar'|'marker'|'tex'|'floor', detail).

    Detection is by SHAPE, not colour: level 3's wall colour is 11, the same
    colour a selected marker's patch uses.  A marker is a cell whose border
    is floor and whose interior is one solid non-floor colour.
    """
    px = [[grid[r0 + S * i + a][c0 + S * j + b] for b in range(S)]
          for a in range(S)]
    vals = {v for row in px for v in row}
    if vals <= walls:
        return "wall", None
    if vals in ({AV_ACTIVE}, {AV_DIMMED}):
        return "avatar", vals.pop()
    border = {px[a][b] for a in range(S) for b in range(S)
              if a in (0, S - 1) or b in (0, S - 1)}
    inner = {px[a][b] for a in range(1, S - 1) for b in range(1, S - 1)}
    if border == {FLOOR} and len(inner) == 1 and inner != {FLOOR}:
        return "marker", inner.pop()
    if TEX in vals:
        return "tex", None
    if len(vals) == 1 and vals != {FLOOR}:
        return "solid", vals.pop()
    return "floor", None


def _scan(grid):
    r0, c0, S, R, C, walls = geometry(grid)
    wall = [[False] * C for _ in range(R)]
    avs, markers, selected, solid = [], [], None, {}
    for i in range(R):
        for j in range(C):
            kind, detail = _classify(grid, r0, c0, S, i, j, walls)
            if kind in ("wall", "tex"):
                wall[i][j] = True
            elif kind == "avatar":
                avs.append((i, j))
            elif kind == "marker":
                markers.append((i, j))
                if detail == MARK_SEL:
                    selected = (i, j)
            elif kind == "solid":
                solid[(i, j)] = detail
    # A solid-colour cell in a BAND (a same-coloured orthogonal neighbour) is
    # a closed gate; an isolated one is a switch that opens its colour's
    # gates when an avatar steps on it (level 4).
    gates, switches = {}, {}
    for (i, j), col in solid.items():
        if any(solid.get((i + di, j + dj)) == col
               for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            gates[(i, j)] = col          # closed gate (open ones read as floor)
        else:
            switches[(i, j)] = col
    known = LAYOUT.get((R, C, S, tuple(sorted(walls))))
    if known:
        merged = dict(known[0]); merged.update(gates); gates = merged
        merged = dict(known[1]); merged.update(switches); switches = merged
    return ((r0, c0, S, R, C), wall, sorted(avs, key=lambda p: p[1]),
            markers, selected, gates, switches)


def _paint(grid, geo, cell, colour):
    r0, c0, S = geo[0], geo[1], geo[2]
    for a in range(S):
        for b in range(S):
            grid[r0 + S * cell[0] + a][c0 + S * cell[1] + b] = colour


def _paint_patch(grid, geo, cell, colour):
    """Repaint the marker patch: the cell interior, i.e. all but a 1px border."""
    r0, c0, S = geo[0], geo[1], geo[2]
    for a in range(1, S - 1):
        for b in range(1, S - 1):
            grid[r0 + S * cell[0] + a][c0 + S * cell[1] + b] = colour


def init_state(entry_grid):
    geo, _, avs, _, _, gates, switches = _scan(entry_grid)
    if not avs:
        avs = [(0, 0)]
    if len(avs) == 1:
        avs = avs * 2
    bar = sum(1 for v in entry_grid[0] if v == 0)
    # 81 of 82 observed transitions fit 3*(a+1)//7 exactly; one tick was
    # skipped, so carry the discrepancy rather than re-deriving `a` from it.
    if (ACTIONS_HINT and bar > 0
            and 0 <= bar_for(ACTIONS_HINT) - bar <= 2):
        a = ACTIONS_HINT
        lost = 0 if bar_for(a) == bar else lost_for(a, bar)
    else:
        a, lost = actions_for(bar), 0
    # NB: a switch or gate under an avatar is invisible in this frame, so the
    # remembered layout can be incomplete after a mid-level re-init.
    return {"A": avs[0], "B": avs[1], "a": a, "lost": lost,
            "gates": gates, "switches": switches, "geo": geo[3:]}


def _meter(g, a, lost=0):
    for k in range(bar_for(a, lost)):
        g[0][63 - k] = 0
        g[63][k] = 0


def predict(state, grid, action, x=None, y=None):
    geo, wall, avs, markers, selected, gates, switches = _scan(grid)
    walls = {grid[1][0], grid[1][63]}
    # Open gates and occupied switches render as floor / avatar, so the layout
    # has to be remembered across turns (and across every action kind).
    if geo[3:] == state.get("geo"):
        remembered = dict(state.get("gates", {}))
        remembered.update(gates)
        gates = remembered
        remembered = dict(state.get("switches", {}))
        remembered.update(switches)
        switches = remembered
    _, _, S, R, C = geo
    r0, c0 = geo[0], geo[1]

    if len(avs) == 1:
        A = B = avs[0]
    else:
        d = lambda p, q: abs(p[0] - q[0]) + abs(p[1] - q[1])
        A, B = avs[0], avs[1]
        if d(A, state["A"]) + d(B, state["B"]) > d(B, state["A"]) + d(A, state["B"]):
            A, B = B, A

    g = [row[:] for row in grid]
    lost = state.get("lost", 0)
    a_n = state.get("a", 0)
    bar_in = sum(1 for v in grid[0] if v == 0)
    if bar_for(a_n, lost) != bar_in:
        if bar_in == 0:                     # level change
            a_n, lost = 0, 0
        else:
            lost = lost_for(a_n, bar_in)
    a_n += 1
    info = {}
    nA, nB = A, B
    new_state = {}

    if action == 6:
        cell = ((y - r0) // S, (x - c0) // S)
        if cell in markers:
            if selected:
                _paint_patch(g, geo, selected, MARK_IDLE)
            _paint_patch(g, geo, cell, MARK_SEL)
            for c in (A, B):
                _paint(g, geo, c, AV_DIMMED)
        elif cell in (A, B):
            if selected:
                _paint_patch(g, geo, selected, MARK_IDLE)
            for c in (A, B):
                _paint(g, geo, c, AV_ACTIVE)
    elif selected:
        di, dj = DELTA.get(action, (0, 0))
        if MARKER_MIRRORED and selected[1] > (C - 1) / 2:
            dj = -dj
        ni, nj = selected[0] + di, selected[1] + dj
        known_gates = gates
        opened = {switches[p] for p in (A, B) if p in switches}
        blocked_gate = (ni, nj) in known_gates and known_gates[(ni, nj)] not in opened
        if (0 <= ni < R and 0 <= nj < C and not wall[ni][nj] and not blocked_gate
                and (ni, nj) not in markers and (ni, nj) not in (A, B)):
            _paint_patch(g, geo, selected, FLOOR)
            _paint_patch(g, geo, (ni, nj), MARK_SEL)
    else:
        # Gates are PRESSURE-PLATE controlled: a colour-X gate is open exactly
        # while an avatar stands on a colour-X switch.  Open gates render as
        # floor, so remember the layout across turns.
        di, dj = DELTA.get(action, (0, 0))
        if HFLIP.get((R, C, S, tuple(sorted(walls)))):
            dj = -dj
        opened = {switches[p] for p in (A, B) if p in switches}

        def mv(p, d):
            ni, nj = p[0] + d[0], p[1] + d[1]
            if not (0 <= ni < R and 0 <= nj < C):
                return p
            if (ni, nj) in gates:
                return (ni, nj) if gates[(ni, nj)] in opened else p
            if wall[ni][nj] or (ni, nj) in markers:
                return p
            return (ni, nj)

        nA, nB = mv(A, (di, dj)), mv(B, (di, -dj))
        opened2 = {switches[p] for p in (nA, nB) if p in switches}
        for gc, col in gates.items():
            _paint(g, geo, gc, FLOOR if col in opened2 else col)
        for c in (A, B):
            if c not in gates:
                _paint(g, geo, c, switches.get(c, FLOOR))
        for c in (nA, nB):
            _paint(g, geo, c, AV_ACTIVE)
        if nA == nB:
            info["level_up"] = True

    _meter(g, a_n, lost)
    new_state.update({"A": nA, "B": nB, "a": a_n, "lost": lost,
                      "gates": gates, "switches": switches, "geo": geo[3:]})
    return g, info, new_state
