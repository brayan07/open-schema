"""World model for ar25.

Board: 64x64. Rows/cols 0..62 = a 21x21 grid of 3x3 CELLS. Row 63 is a static bar
of 5; col 63 is a move counter (b, filling top-down with 5, one per action taken,
reset each level); (63,63) stays b. Background 9.

Objects (cell-aligned):
  - PLAYERS: hollow shapes of colour 5 (one or more connected components).
  - AXIS: a full row or full column of colour-a cells; the line of reflection.
  - MIRRORS: every player reflected about the axis, drawn SOLID 4. Not
    independently controllable; clipped per-cell to the board.
  - TARGET: static solid b cells.
Goal: every target cell is covered by a player cell or a mirror cell.

Rendering order: axis, target, mirrors, players. A mirror cell on a target cell
shows the target colour in its centre pixel.

Actions: 1=up 2=down 3=left 4=right (one cell), 5=cycle the active object,
6=click, 7=? (untested). The ACTIVE object has 0 in each of its cell centres;
inactive objects show 9. If the axis is immovable it is drawn fully solid and the
(single) player is permanently active.
"""

BG = 9
N = 21
LAST = 62
PLAYER_C, MIRROR_C, AXIS_C, TARGET_C, HOLE = 5, 4, 10, 11, 0

DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}

# The action-5 selection cycle visits objects in a fixed order that is NOT
# derivable from one frame: level 2 cycles its players largest-first, level 5
# smallest-first. Objects are indexed players-first (sorted largest first) then
# axes (horizontal before vertical). Where the default order is wrong, the
# observed order is recorded here, keyed by
#   (n_players, n_axes, tuple(sorted player sizes, descending)).
CYCLE_ORDER = {
    (2, 2, (8, 5)): [1, 0, 2, 3],    # level 5: the 5-cell piece precedes the 8-cell one
    (2, 2, (14, 9)): [1, 0, 2, 3],   # level 6: the 9-cell piece precedes the 14-cell one
}


def _cycle(state, active):
    n = len(state["players"])
    nobj = n + len(state["axes"])
    key = (n, len(state["axes"]),
           tuple(sorted((len(p) for p in state["players"]), reverse=True)))
    order = CYCLE_ORDER.get(key, list(range(nobj)))
    return order[(order.index(active) + 1) % len(order)]


def _components(cells):
    """Connected components of a set of cells, using 8-CONNECTIVITY: level 5's
    four small shapes are only diagonally adjacent yet move as a single rigid
    object, so diagonal touching binds cells into one piece."""
    remaining = set(cells)
    out = []
    while remaining:
        seed = sorted(remaining)[0]
        stack, comp = [seed], set()
        remaining.discard(seed)
        while stack:
            cr, cc = stack.pop()
            comp.add((cr, cc))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nb = (cr + dr, cc + dc)
                if nb in remaining:
                    remaining.discard(nb)
                    stack.append(nb)
        out.append(comp)
    # Stable object order for the action-5 cycle. Sorting by size (largest
    # first) reproduces every observed toggle; plain position order does not,
    # since the shapes overtake each other as they move.
    out.sort(key=lambda comp: (-len(comp), sorted(comp)[0]))
    return out


def _scan(grid):
    """Read the board. Cells are classified by their CORNER pixel (the centre
    pixel carries mode/match markers and is not a reliable colour)."""
    pcells, target, acells = set(), set(), set()
    for cr in range(N):
        for cc in range(N):
            v = grid[3 * cr][3 * cc]
            if v == PLAYER_C:
                pcells.add((cr, cc))
            elif v == TARGET_C:
                target.add((cr, cc))
            elif v == AXIS_C:
                acells.add((cr, cc))
            # A target cell hidden under a player or a mirror keeps the b match
            # marker in its centre, so recover it from there.
            if grid[3 * cr + 1][3 * cc + 1] == TARGET_C:
                target.add((cr, cc))

    # An axis is a full cell-line; parts of it may be hidden under a target or a
    # player, so require only that no cell of the line is bare background.
    axes = []          # (is_horizontal, index)
    for k in range(N):
        row = [(k, j) for j in range(N)]
        col = [(j, k) for j in range(N)]
        for horiz, line in ((True, row), (False, col)):
            na = sum(1 for x in line if x in acells)
            bare = sum(1 for x in line
                       if x not in acells and x not in target and x not in pcells
                       and grid[3 * x[0]][3 * x[1]] != MIRROR_C)
            if na >= 8 and bare == 0:
                axes.append((horiz, k))
    # Cycle order of the action-5 selection: players first (largest shape
    # first), then horizontal axes, then vertical ones.
    axes.sort(key=lambda ax: (not ax[0], ax[1]))

    # An immovable axis is drawn fully solid (level 0). A movable one carries a
    # mode marker in each cell centre: 0 when it is the active object, 9 when not.
    def line_cells(ax):
        horiz, k = ax
        return [(k, j) if horiz else (j, k) for j in range(N)]

    shared = set()
    for i, ax in enumerate(axes):
        for j, bx in enumerate(axes):
            if i < j:
                shared |= set(line_cells(ax)) & set(line_cells(bx))

    movable = False
    for ax in axes:
        for (r, c) in line_cells(ax):
            if grid[3 * r + 1][3 * c + 1] in (HOLE, BG):
                movable = True
    players = _components(pcells)
    active = None
    if movable:
        # An axis is active iff one of its own bare cells (no player/target on
        # it, not shared with another axis) is holed. Check axes first: an active
        # axis also holes player cells it crosses, which would otherwise look
        # like an active player.
        for ai, ax in enumerate(axes):
            for (r, c) in line_cells(ax):
                if (r, c) not in pcells and (r, c) not in target \
                        and (r, c) not in shared \
                        and grid[3 * r + 1][3 * c + 1] == HOLE:
                    active = len(players) + ai
        if active is None:
            found = False
            for i, comp in enumerate(players):
                for (cr, cc) in comp:
                    if grid[3 * cr + 1][3 * cc + 1] == HOLE:
                        active, found = i, True
                        break
            if not found and active is None:
                # Nobody shows a hole: the active player must be one parked
                # entirely on target cells, whose holes are hidden by the
                # match markers. Pick such a player.
                for i, comp in enumerate(players):
                    if all(cell in target for cell in comp):
                        active = i
                        break
    if active is None:
        active = len(players)
    return players, target, axes, movable, active


def init_state(entry_grid):
    players, target, axes, movable, active = _scan(entry_grid)
    used = [entry_grid[i][63] for i in range(LAST + 1) if entry_grid[i][63] != TARGET_C]
    return {"players": [frozenset(p) for p in players], "target": target,
            "axes": axes, "movable": movable, "active": active, "used": used}


def _images(state, comp):
    """Every non-identity reflection of comp in the group generated by the axes
    (one axis -> 1 image; two perpendicular axes -> 3, including the 180-degree
    rotation about their crossing)."""
    imgs = [set(comp)]
    for (horiz, a) in state["axes"]:
        more = []
        for img in imgs:
            if horiz:
                more.append({(2 * a - cr, cc) for (cr, cc) in img})
            else:
                more.append({(cr, 2 * a - cc) for (cr, cc) in img})
        imgs = imgs + more
    return imgs[1:]


def _axis_cells(state, ai):
    horiz, k = state["axes"][ai]
    return [(k, j) if horiz else (j, k) for j in range(N)]


def _fill(g, cr, cc, colour):
    for r in range(3 * cr, 3 * cr + 3):
        for c in range(3 * cc, 3 * cc + 3):
            g[r][c] = colour


def _render(state):
    g = [[BG] * 64 for _ in range(64)]
    for c in range(64):
        g[63][c] = PLAYER_C
    for r in range(LAST + 1):
        g[r][63] = TARGET_C
    g[63][63] = TARGET_C
    for i, colour in enumerate(state["used"][:LAST + 1]):
        g[i][63] = colour

    nplayers = len(state["players"])
    axis_cells, shared, own = [], set(), []
    for ai in range(len(state["axes"])):
        cells = set(_axis_cells(state, ai))
        for prev in axis_cells:
            shared |= cells & prev
        axis_cells.append(cells)
    all_axis = set()
    for cells in axis_cells:
        all_axis |= cells
    for cells in axis_cells:
        own.append(cells)

    for (cr, cc) in all_axis:
        _fill(g, cr, cc, AXIS_C)
        if state["movable"]:
            g[3 * cr + 1][3 * cc + 1] = BG

    for (cr, cc) in state["target"]:
        _fill(g, cr, cc, TARGET_C)

    covered = set()
    mirror_cells = set()
    for comp in state["players"]:
        for img in _images(state, comp):
            for (cr, cc) in img:
                if 0 <= cr < N and 0 <= cc < N:
                    covered.add((cr, cc))
                    mirror_cells.add((cr, cc))
                    _fill(g, cr, cc, MIRROR_C)
                    if (cr, cc) in state["target"]:
                        g[3 * cr + 1][3 * cc + 1] = TARGET_C

    active = state["active"]
    active_axis_cells = set()
    if state["movable"] and active >= nplayers:
        active_axis_cells = own[active - nplayers]

    for i, comp in enumerate(state["players"]):
        live = (not state["movable"]) or active == i
        for (cr, cc) in comp:
            covered.add((cr, cc))
            _fill(g, cr, cc, PLAYER_C)
            # A cell is a ring; its centre shows the marker layer beneath.
            if (cr, cc) in state["target"]:
                g[3 * cr + 1][3 * cc + 1] = TARGET_C   # match marker wins
            else:
                g[3 * cr + 1][3 * cc + 1] = HOLE if live else BG

    # The active axis stamps its hole into every cell it runs through -- over
    # bare board, over players and over mirrors alike -- but never over a target.
    for (cr, cc) in active_axis_cells:
        if (cr, cc) not in state["target"]:
            g[3 * cr + 1][3 * cc + 1] = HOLE

    return g, covered


def predict(state, grid, action, x=None, y=None):
    s = dict(state)
    n = len(state["players"])
    naxes = len(state["axes"])
    # Counter colour: one pixel per action; 5 while the (only) axis is vertical,
    # c otherwise. Fits every action of levels 0-3.
    horiz_any = any(h for (h, _) in state["axes"])
    s["used"] = state["used"] + [12 if horiz_any else PLAYER_C]

    if action == 5 and state["movable"]:
        s["active"] = _cycle(state, state["active"])
    elif action in DIRS:
        dr, dc = DIRS[action]
        act = state["active"] if state["movable"] else 0
        if act < n:
            moved = {(cr + dr, cc + dc) for (cr, cc) in state["players"][act]}
            # Players may overlap each other: level 3 cannot be solved otherwise
            # (a 7-cell and a 6-cell shape must cover a 12-cell target).
            if all(0 <= a < N and 0 <= b < N for (a, b) in moved):
                s["players"] = list(state["players"])
                s["players"][act] = frozenset(moved)
        else:
            horiz, k = state["axes"][act - n]
            delta = dr if horiz else dc
            if delta and 0 <= k + delta < N:
                s["axes"] = list(state["axes"])
                s["axes"][act - n] = (horiz, k + delta)

    g, covered = _render(s)
    info = {"level_up": True} if s["target"] <= covered else {}
    return g, info, s
