"""World model for ft09.

General picture (holds for levels 0, 1 and 2):

* The board is made of 6x6 CELLS on an 8-pixel lattice (2px gutters).
  Cells may form one lattice (levels 1, 2) or several separate panels
  (level 0, where one panel is additionally wrapped in a thick frame).
  The occupied lattice positions need not fill the bounding rectangle
  (level 2 is a cross).
* Every level has a two-colour PALETTE; a plain cell always shows one of
  the two, and a click flips it to the other one.  The palette is the set
  of plain-cell colours plus the set of mini centre colours
  (level 0: {9,8}, level 1: {9,12}, level 2: {8,12}).
* A few lattice positions hold a MINI: a 3x3 picture drawn at 2x2 pixels
  which specifies the colours of its own 3x3 neighbourhood of cells.
  Sub-pixel 0 means "that neighbour must show THIS MINI'S CENTRE colour",
  sub-pixel 2 means "must show the other palette colour".  Different
  minis on the same board can have different centre colours (level 2);
  where two minis overlap their demands always agree.
* The level is cleared once every mini's neighbourhood matches its spec.
* Row 63 is an action bar: two more pixels flip 12 -> 11 (from the right)
  per action; it resets at each new level.

Level-entry grids cannot be derived, so the ones already seen are
memorised at the bottom of this file and replayed on a predicted level-up.
"""

CELL = 6
STRIDE = 8
BAR_ROW = 63
BAR_FULL, BAR_USED = 12, 11
# The bar is an action budget: px = round(64 * actions / BUDGET[level]).
# Levels 0-1 drew exactly 2 px per action (budget 32) and levels 2-3 drew
# 1,1,2,3,3,4,5,5,... (budget 96) — so the budget triples every two levels,
# and level 4's first two actions drew 0 then 1 px, i.e. a budget
# in (128, 256] — 192 taken as the next doubling.
BAR_BUDGET = {0: 32, 1: 32, 2: 96, 3: 96, 4: 192, 5: 192}
BAR_OBS = {0: [2, 4, 6], 1: [2, 4, 6, 8, 10, 12], 2: [1, 1, 2, 3, 3, 4, 5, 5, 6, 7, 7, 8, 9], 3: [1, 1, 2, 3, 3, 4, 5, 5, 6, 7, 7, 8, 9, 9, 10], 4: [0, 1, 2, 2, 2, 3, 4, 4, 4, 5, 6, 6, 6, 7, 8, 8, 8, 9, 10, 10]}           # level -> px after 1,2,3,... actions (measured)
BAR_SEED = {5: 0}      # level -> actions already taken (rewritten by mkentry.py)
SPEC_SAME, SPEC_OTHER, SPEC_ABSENT = 0, 2, 3
SPEC_SYMBOLS = (SPEC_SAME, SPEC_OTHER, SPEC_ABSENT)

CURRENT_LEVEL = 0          # injected by the harness before every call

def _entry_grid(level):
    rows = LEVEL_ENTRY_HEX.get(str(level))
    if rows is None:
        return None
    return [[int(ch, 16) for ch in row] for row in rows]


# ---------------------------------------------------------------- board


def _uniform_cells(grid):
    """Every isolated 6x6 block of a single non-background colour."""
    bg = grid[0][0]
    out = {}
    for r in range(64 - CELL + 1):
        for c in range(64 - CELL + 1):
            v = grid[r][c]
            if v == bg:
                continue
            if any(grid[r + a][c + b] != v
                   for a in range(CELL) for b in range(CELL)):
                continue
            # must be a maximal run in both axes
            if r and grid[r - 1][c] == v:
                continue
            if r + CELL < 64 and grid[r + CELL][c] == v:
                continue
            if c and grid[r][c - 1] == v:
                continue
            if c + CELL < 64 and grid[r][c + CELL] == v:
                continue
            out[(r, c)] = v
    return out


def _tile_blocks(grid):
    """Non-uniform 6x6 blocks that sit alone in the background: minis and
    overlay tiles.  Level 5 has no uniform cell at all, so the lattice has
    to be seeded from these as well."""
    bg = grid[0][0]
    out = set()
    for r in range(64 - CELL + 1):
        for c in range(64 - CELL + 1):
            if r and grid[r - 1][c] != bg:
                continue
            if c and grid[r][c - 1] != bg:
                continue
            if r + CELL < 64 and grid[r + CELL][c] != bg:
                continue
            if c + CELL < 64 and grid[r][c + CELL] != bg:
                continue
            if any(grid[r + a][c + b] == bg
                   for a in range(CELL) for b in range(CELL)):
                continue
            if _is_mini(grid, r, c) is not None:
                out.add((r, c))
    return out


def _groups(cells):
    """Union cells that are exactly one lattice step apart."""
    parent = {k: k for k in cells}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for (r, c) in cells:
        for nb in ((r + STRIDE, c), (r, c + STRIDE)):
            if nb in cells:
                ra, rb = find((r, c)), find(nb)
                if ra != rb:
                    parent[ra] = rb
    out = {}
    for k in cells:
        out.setdefault(find(k), []).append(k)
    return list(out.values())


def _is_mini(grid, r, c):
    """A 6x6 block of nine uniform 2x2 sub-blocks, not uniform overall."""
    vals = []
    for i in range(3):
        for j in range(3):
            v = grid[r + 2 * i][c + 2 * j]
            for a in range(2):
                for b in range(2):
                    if grid[r + 2 * i + a][c + 2 * j + b] != v:
                        return None
            vals.append(v)
    if len(set(vals)) == 1:
        return None
    return [vals[0:3], vals[3:6], vals[6:9]]


def board(grid):
    """Panels: (plain-cell positions, mini positions) on each lattice.

    Each panel is (cells, minis) where cells maps (i, j) -> (row_px, col_px)
    for the plain cells and minis maps (i, j) -> (3x3 spec, (row_px, col_px)).
    Lattice positions with nothing on them are simply absent.
    """
    uniform = _uniform_cells(grid)
    lc, ln = legend_box(grid)
    seeds = dict.fromkeys(uniform, True)
    for rc in _tile_blocks(grid):
        if rc not in seeds and not (lc is not None and rc[0] < 4 * ln
                                    and rc[1] + CELL > lc):
            seeds[rc] = False
    panels = []
    for grp in _groups(seeds):
        rows = sorted({r for r, _ in grp})
        cols = sorted({c for _, c in grp})
        cells, minis, checkers = {}, {}, {}
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                if (r, c) in uniform:
                    cells[(i, j)] = (r, c)
                    continue
                if lc is not None and r < 4 * ln and c + CELL > lc:
                    continue          # the colour strip, not a board cell
                m = _is_mini(grid, r, c)
                if m is None:
                    continue
                outer = [m[a][b] for a in range(3) for b in range(3)
                         if (a, b) != (1, 1)]
                if all(v in SPEC_SYMBOLS for v in outer):
                    minis[(i, j)] = (m, (r, c))
                else:
                    # An overlay tile: a cell whose block carries a few
                    # pixels in a foreign colour.  Those pixels are a
                    # pictogram of the neighbours a click drags along —
                    # all four orthogonals on level 4, only north on
                    # level 5.
                    cells[(i, j)] = (r, c)
                    flat = [m[a][b] for a in range(3) for b in range(3)]
                    own = max(set(flat), key=flat.count)
                    checkers[(i, j)] = tuple(
                        (a - 1, b - 1) for a in range(3) for b in range(3)
                        if (a, b) != (1, 1) and m[a][b] != own)
        panels.append((cells, minis, checkers))
    return panels


def legend_box(grid):
    """(col, n_swatches) of the colour strip that hangs from row 0 in the
    top-right corner: 4x4 swatches stacked downwards.  Level 0 has none.
    It sits at column 60 on levels 1-3 but at column 54 on level 4, so it
    is located rather than assumed."""
    bg = grid[0][0]
    right = None
    for c in range(63, -1, -1):
        if grid[0][c] != bg:
            right = c
            break
    if right is None:
        return None, 0
    col = right
    while col > 0 and grid[0][col - 1] != bg:
        col -= 1
    n = 0
    for r in range(0, 64, 4):
        v = grid[r][col]
        if v == bg or any(grid[r + a][col + b] != v
                          for a in range(4) for b in range(4)):
            break
        n += 1
    return col, n


def legend(grid):
    """The level's colours, in the order a click cycles through them."""
    col, n = legend_box(grid)
    return [] if not n else [grid[4 * k][col] for k in range(n)]


def palette(grid, panels):
    """The level's colour cycle, in click order."""
    strip = legend(grid)
    if strip:
        return strip
    cols = set()
    for cells, minis, _ in panels:
        for (r, c) in cells.values():
            cols.add(grid[r][c])
        for m, _ in minis.values():
            cols.add(m[1][1])
    return sorted(cols)


def _next_colour(cycle, colour):
    if colour in cycle:
        return cycle[(cycle.index(colour) + 1) % len(cycle)]
    return colour


def allowed(grid, panels):
    """{(row_px, col_px): set of colours the cell may show}.

    A mini sub-pixel of 0 pins its neighbour to the mini's centre colour;
    a sub-pixel of 2 only forbids that colour.  Where two minis overlap,
    the two "not mine" bans can leave exactly one colour — that is how the
    third colour of level 3 gets used.
    """
    cycle = palette(grid, panels)
    out = {}
    for cells, minis, _ in panels:
        for (i, j), (m, _) in minis.items():
            same = m[1][1]
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    pos = cells.get((i + di, j + dj))
                    if pos is None:
                        continue
                    spec = m[di + 1][dj + 1]
                    if spec == SPEC_SAME:
                        ok = {same}
                    elif spec == SPEC_OTHER:
                        ok = set(cycle) - {same}
                    else:
                        continue      # 3 = "no cell there"; anything else
                                      # (the 6/14 checkerboards) says nothing
                    out[pos] = out.get(pos, set(cycle)) & ok
    return out


def target(grid, panels=None):
    """{(row_px, col_px): wanted colour} — the cheapest legal colour, which
    is the earliest one in cycle order (the level's background comes first)."""
    panels = panels if panels is not None else board(grid)
    cycle = palette(grid, panels)
    want = {}
    for pos, ok in allowed(grid, panels).items():
        for v in cycle:
            if v in ok:
                want[pos] = v
                break
    return want


def solved(grid, panels=None):
    panels = panels if panels is not None else board(grid)
    return all(grid[r][c] in ok
               for (r, c), ok in allowed(grid, panels).items())


def _apply(state, cells, checkers, cycle, ij):
    """Click cell ij in a lightweight {(i,j): colour} board state."""
    todo = [ij] + [(ij[0] + di, ij[1] + dj)
                   for di, dj in checkers.get(ij, ())]
    for k in todo:
        if k in state:
            state[k] = _next_colour(cycle, state[k])


def _settle_order(cells, checkers):
    """An order in which each cell can be settled for good: a cell is
    settled only after everything whose click would disturb it.  Level 5's
    tiles only reach north, so that is a strict order (bottom row first);
    level 4's four-way tiles make cycles, and there the overlay tiles are
    simply fired first and the plain cells repaired afterwards."""
    disturbs = {ij: set() for ij in cells}      # ij -> cells it knocks about
    for ij in cells:
        for di, dj in checkers.get(ij, ()):
            nb = (ij[0] + di, ij[1] + dj)
            if nb in cells:
                disturbs[ij].add(nb)
    order, done = [], set()
    pending = sorted(cells)
    while pending:
        free = [ij for ij in pending
                if all(v in done or v == ij
                       for v in _disturbed_by(disturbs, ij, pending))]
        if not free:                            # cyclic: fall back
            return ([ij for ij in pending if ij in checkers]
                    + [ij for ij in pending if ij not in checkers])
        for ij in free:
            order.append(ij)
            done.add(ij)
        pending = [ij for ij in pending if ij not in done]
    return order


def _disturbed_by(disturbs, ij, pending):
    """The still-unsettled cells whose click would move ij."""
    return [v for v in pending if ij in disturbs[v]]


def plan(grid):
    """Clicks (x, y) that bring every constrained cell to its target.

    Checkerboard tiles go first: they are the only way to change themselves
    and they drag their four neighbours along, so the plain cells are fixed
    afterwards, once the collateral damage is known."""
    panels = board(grid)
    cycle = palette(grid, panels)
    want = target(grid, panels)
    out = []
    for cells, _, checkers in panels:
        state = {ij: grid[r][c] for ij, (r, c) in cells.items()}
        wanted = {ij: want[cells[ij]] for ij in cells if cells[ij] in want}
        for ij in _settle_order(cells, checkers):
            if ij not in wanted:
                continue
            while state[ij] != wanted[ij]:
                _apply(state, cells, checkers, cycle, ij)
                r, c = cells[ij]
                out.append((c + 2, r + 2))
    return out


def todo(grid):
    return plan(grid)


# ---------------------------------------------------------------- rules


def bar_used(grid):
    return sum(1 for v in grid[BAR_ROW] if v == BAR_USED)


def _fit_bar(obs):
    """The bar's per-action increments repeat with a short period: 2 on
    levels 0-1, (1,0,1) on levels 2-3, (0,1,1,0) on level 4.  Find the
    shortest period that explains the measured prefix and extend with it."""
    deltas = [obs[0]] + [obs[k] - obs[k - 1] for k in range(1, len(obs))]
    for period in range(1, len(deltas) + 1):
        if all(deltas[k] == deltas[k - period]
               for k in range(period, len(deltas))):
            if len(deltas) < 2 * period:
                continue        # not yet seen twice: do not trust it
            def f(a, d=deltas[:period], p=period):
                return sum(d[k % p] for k in range(a))
            return f
    return None


def _bar_px(level, actions):
    """Pixels eaten after `actions` actions on this level.

    Levels 0-1 ate 2 px per action and levels 2-3 followed round(2a/3), but
    level 4 starts 0,1,2 — which no round(a*rate) can produce.  So the
    measured prefix (BAR_OBS, refreshed by mkentry.py) is used where it
    reaches, and beyond it the last observed increment is repeated."""
    if actions <= 0:
        return 0
    obs = BAR_OBS.get(level)
    if obs:
        if actions <= len(obs):
            return obs[actions - 1]
        fit = _fit_bar(obs)
        if fit:
            return min(64, fit(actions))
        return obs[-1]      # no formula fits level 4 (0,1,2,2,2): freeze
    b = BAR_BUDGET.get(level, 96)
    return min(64, (2 * 64 * actions + b) // (2 * b))


def _actions_from_bar(level, grid):
    """Action count to resume from: exact at a level entry (empty bar),
    otherwise the count recorded for the live frame — the rounded bar is
    not invertible on its own."""
    px = bar_used(grid)
    if px == 0:
        return 0
    if level in BAR_SEED:
        return BAR_SEED[level]
    a = 0
    while _bar_px(level, a) < px:
        a += 1
    return a


def _tick_bar(grid, level, actions):
    px = _bar_px(level, actions)
    out = [row[:] for row in grid]
    for c in range(64 - px, 64):
        out[BAR_ROW][c] = BAR_USED
    return out


def _hit(panels, x, y):
    """Which plain cell (top-left pixel) does the click land on?"""
    if x is None or y is None:
        return None
    for cells, _, checkers in panels:
        for (i, j), (r, c) in cells.items():
            if r <= y < r + CELL and c <= x < c + CELL:
                hits = [(r, c)]
                for di, dj in checkers.get((i, j), ()):
                    nb = cells.get((i + di, j + dj))
                    if nb is not None:
                        hits.append(nb)
                return hits
    return None


def init_state(entry_grid, level=None, **kw):
    lvl = level if level is not None else CURRENT_LEVEL
    return {"actions": _actions_from_bar(lvl, entry_grid)}


def predict(state, grid, action, x=None, y=None, level=None, **kw):
    flags = {"level_up": False, "dead": False, "win": False}
    if action != 6:
        return grid, flags, state
    panels = board(grid)
    lvl = level if level is not None else CURRENT_LEVEL
    state = {"actions": state.get("actions", 0) + 1}
    out = _tick_bar(grid, lvl, state["actions"])
    hit = _hit(panels, x, y)
    if hit is not None:
        cycle = palette(grid, panels)
        for (r, c) in hit:
            old = grid[r][c]
            new = _next_colour(cycle, old)
            for a in range(CELL):       # a checkerboard keeps its overlay
                for b in range(CELL):
                    if grid[r + a][c + b] == old:
                        out[r + a][c + b] = new
    if solved(out, panels):
        flags["level_up"] = True
        # the harness calls predict() positionally; the level arrives as the
        # injected CURRENT_LEVEL global instead
        nxt = _entry_grid(lvl + 1)
        if nxt is not None:
            out = nxt
    return out, flags, state


# ------------------------------------------------- memorised level entries
# rewritten by mkentry.py; grids seen so far, one hex char per pixel
LEVEL_ENTRY_HEX = {
    '1': [
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944002222449999994444444444444444444444',
        '4444444444444444444499999944002222449999994444444444444444444444',
        '444444444444444444449999994400cc00449999994444444444444444444444',
        '444444444444444444449999994400cc00449999994444444444444444444444',
        '4444444444444444444499999944002200449999994444444444444444444444',
        '4444444444444444444499999944002200449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944002200449999994444444444444444444444',
        '4444444444444444444499999944002200449999994444444444444444444444',
        '444444444444444444449999994422cc22449999994444444444444444444444',
        '444444444444444444449999994422cc22449999994444444444444444444444',
        '4444444444444444444499999944000022449999994444444444444444444444',
        '4444444444444444444499999944000022449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    ],
    '2': [
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '444444444444444444448888884488888844888888444444444444444444cccc',
        '444444444444444444448888884488888844888888444444444444444444cccc',
        '444444444444444444448888884488888844888888444444444444444444cccc',
        '444444444444444444448888884488888844888888444444444444444444cccc',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444488888844000000448888884444444444444444444444',
        '4444444444444444444488888844000000448888884444444444444444444444',
        '444444444444444444448888884400cc22448888884444444444444444444444',
        '444444444444444444448888884400cc22448888884444444444444444444444',
        '4444444444444444444488888844220022448888884444444444444444444444',
        '4444444444444444444488888844220022448888884444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444448888884422002244888888442200004488888844444444444444',
        '4444444444448888884422002244888888442200004488888844444444444444',
        '4444444444448888884422880044888888440088224488888844444444444444',
        '4444444444448888884422880044888888440088224488888844444444444444',
        '4444444444448888884400002244888888442200224488888844444444444444',
        '4444444444448888884400002244888888442200224488888844444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444448888884488888844888888448888884488888844444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444488888844220022448888884444444444444444444444',
        '4444444444444444444488888844220022448888884444444444444444444444',
        '444444444444444444448888884400cc22448888884444444444444444444444',
        '444444444444444444448888884400cc22448888884444444444444444444444',
        '4444444444444444444488888844000000448888884444444444444444444444',
        '4444444444444444444488888844000000448888884444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444488888844888888448888884444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    ],
    '3': [
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444449999',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '4444444444444444444444444444444444444444444444444444444444448888',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '444444444444444444444444444444444444444444444444444444444444cccc',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444449999994422002244999999442200224499999944444444444444',
        '4444444444449999994422002244999999442200224499999944444444444444',
        '4444444444449999994422cc2244999999442299224499999944444444444444',
        '4444444444449999994422cc2244999999442299224499999944444444444444',
        '4444444444449999994422002244999999442222004499999944444444444444',
        '4444444444449999994422002244999999442222004499999944444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444449999994499999944999999449999994499999944444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944002222449999994444444444444444444444',
        '4444444444444444444499999944002222449999994444444444444444444444',
        '444444444444444444449999994422cc22449999994444444444444444444444',
        '444444444444444444449999994422cc22449999994444444444444444444444',
        '4444444444444444444499999944000000449999994444444444444444444444',
        '4444444444444444444499999944000000449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444499999944999999449999994444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    ],
    '4': [
        '444444444444444444444444444444444444444444444444444444eeee444444',
        '444444444444444444444444444444444444444444444444444444eeee444444',
        '444444444444444444444444444444444444444444444444444444eeee444444',
        '444444444444444444444444444444444444444444444444444444eeee444444',
        '4444444444444433333344eeeeee44eeeeee444444444444444444ffff444444',
        '4444444444444433333344eeeeee44eeeeee444444444444444444ffff444444',
        '4444444444444433ee0044eeeeee44eeeeee444444444444444444ffff444444',
        '4444444444444433ee0044eeeeee44eeeeee444444444444444444ffff444444',
        '4444444444444433002244eeeeee44eeeeee4444444444444444444444444444',
        '4444444444444433002244eeeeee44eeeeee4444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '44444444444444eeeeee44ee66ee44eeeeee4400333344444444444444444444',
        '44444444444444eeeeee44ee66ee44eeeeee4400333344444444444444444444',
        '44444444444444eeeeee4466ee6644eeeeee4422ff3344444444444444444444',
        '44444444444444eeeeee4466ee6644eeeeee4422ff3344444444444444444444',
        '44444444444444eeeeee44ee66ee44eeeeee4400220044444444444444444444',
        '44444444444444eeeeee44ee66ee44eeeeee4400220044444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee44eeeeee4444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '44444433220044eeeeee44ee66ee44eeeeee4422002244eeeeee442200334444',
        '44444433220044eeeeee44ee66ee44eeeeee4422002244eeeeee442200334444',
        '44444433ff2244eeeeee4466ee6644eeeeee4400ee0044eeeeee4400ee334444',
        '44444433ff2244eeeeee4466ee6644eeeeee4400ee0044eeeeee4400ee334444',
        '44444433220044eeeeee44ee66ee44eeeeee4422002244eeeeee442200334444',
        '44444433220044eeeeee44ee66ee44eeeeee4422002244eeeeee442200334444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '444444eeeeee44eeeeee4400220044eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee4400220044eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee4422ee2244eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee4422ee2244eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee4400330044eeeeee44eeeeee44eeeeee44eeeeee4444',
        '444444eeeeee44eeeeee4400330044eeeeee44eeeeee44eeeeee44eeeeee4444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '44444444444444eeeeee4422332244eeeeee44ee66ee44eeeeee444444444444',
        '44444444444444eeeeee4422332244eeeeee44ee66ee44eeeeee444444444444',
        '44444444444444eeeeee4400ee0044eeeeee4466ee6644eeeeee444444444444',
        '44444444444444eeeeee4400ee0044eeeeee4466ee6644eeeeee444444444444',
        '44444444444444eeeeee4422002244eeeeee44ee66ee44eeeeee444444444444',
        '44444444444444eeeeee4422002244eeeeee44ee66ee44eeeeee444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee44220033444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee44220033444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee4400ee33444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee4400ee33444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee44333333444444444444',
        '44444444444444eeeeee44eeeeee44eeeeee44eeeeee44333333444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    ],
    '5': [
        '444444444444444444444444444444444444444444444444444444444444bbbb',
        '444444444444444444444444444444444444444444444444444444444444bbbb',
        '444444444444444444444444444444444444444444444444444444444444bbbb',
        '444444444444444444444444444444444444444444444444444444444444bbbb',
        '444444444444444444444444444444444444444444444444444444444444eeee',
        '444444444444444444444444444444444444444444444444444444444444eeee',
        '4444bb66bb44333333444444444444444444444444444444444444444444eeee',
        '4444bb66bb44333333444444444444444444444444444444444444444444eeee',
        '4444bbbbbb4422ee334444444444444444444444444444444444444444444444',
        '4444bbbbbb4422ee334444444444444444444444444444444444444444444444',
        '4444bbbbbb440000224444444444444444444444444444444444444444444444',
        '4444bbbbbb440000224444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44444444444444',
        '4444bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44444444444444',
        '4444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44444444444444',
        '4444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44444444444444',
        '4444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44444444444444',
        '4444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '444444444444bb66bb44bb66bb44bb66bb4422002244bb66bb44444444444444',
        '444444444444bb66bb44bb66bb44bb66bb4422002244bb66bb44444444444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb4400ee0044bbbbbb44444444444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb4400ee0044bbbbbb44444444444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb4400002244bbbbbb44444444444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb4400002244bbbbbb44444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '444444444444bb66bb4422000044bb66bb44bb66bb44bb66bb44444444444444',
        '444444444444bb66bb4422000044bb66bb44bb66bb44bb66bb44444444444444',
        '444444444444bbbbbb4400ee0044bbbbbb44bbbbbb44bbbbbb44444444444444',
        '444444444444bbbbbb4400ee0044bbbbbb44bbbbbb44bbbbbb44444444444444',
        '444444444444bbbbbb4422002244bbbbbb44bbbbbb44bbbbbb44444444444444',
        '444444444444bbbbbb4422002244bbbbbb44bbbbbb44bbbbbb44444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '444444444444bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44bb66bb444444',
        '444444444444bb66bb44bb66bb44bb66bb44bb66bb44bb66bb44bb66bb444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb444444',
        '444444444444bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb44bbbbbb444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444422000044bb66bb444444',
        '4444444444444444444444444444444444444444444422000044bb66bb444444',
        '4444444444444444444444444444444444444444444433ee2244bbbbbb444444',
        '4444444444444444444444444444444444444444444433ee2244bbbbbb444444',
        '4444444444444444444444444444444444444444444433333344bbbbbb444444',
        '4444444444444444444444444444444444444444444433333344bbbbbb444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        '4444444444444444444444444444444444444444444444444444444444444444',
        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    ],
}
