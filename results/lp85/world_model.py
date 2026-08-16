"""World model for lp85 — general "rotating tracks" puzzle.

Board: square tiles of side s on a lattice of pitch s+gap, laid out as one or
more closed TRACKS (a track is a cyclic sequence of tile slots: either a
straight row that wraps, or a rectangular loop).  Each track has a pair of
arrow buttons: colour 8 = "left/backwards", colour 14 = "right/forwards".
Pressing an arrow cyclically shifts that track's CONTENTS by one slot; slot
geometry never moves.  Tracks may share slots (they cross).

Colour-11 (b) tiles are the tokens.  Four colour-11 corner pips just outside a
slot mark it as a target.  Level clears when every marked slot holds a
colour-11 tile.

Column 0 is a per-level action counter that fills from the top, 5 cells/action.
"""

BG = 4          # play-area background
TOKEN = 11      # token / bracket colour
LEFT_C = 8      # left arrow colour
RIGHT_C = 14    # right arrow colour
# Column 0 is a gauge: filled = round(64 * actions_this_level / BUDGET[level]).
# BUDGET is fitted per level from observed frames (level 2 is only pinned to
# 77..85 so far; 81 is the midpoint).
BUDGET = {0: 13, 1: 64, 2: 80, 3: 150, 4: 80, 5: 80, 6: 80, 7: 80}  # level 3 pinned to (146.3, 153.6] by gauge data
# actions already spent on the current level when a plan is started mid-level
# (backtest always re-enters a level at bar 0, so it is unaffected)
A_OFFSET = 20
N = 64


def level_of(grid):
    """Level index = number of filled (colour-14) pips in the row-1 progress bar."""
    return sum(1 for x in range(N) if grid[1][x] == 14) // 4


# ---------------------------------------------------------------- components

def _components(grid):
    from collections import deque
    seen = [[False] * N for _ in range(N)]
    out = []
    for y in range(N):
        for x in range(N):
            if seen[y][x]:
                continue
            c = grid[y][x]
            q = deque([(y, x)])
            seen[y][x] = True
            cells = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < N and 0 <= nx < N and not seen[ny][nx] and grid[ny][nx] == c:
                        seen[ny][nx] = True
                        q.append((ny, nx))
            ys = [a for a, b in cells]
            xs = [b for a, b in cells]
            out.append((c, min(ys), max(ys), min(xs), max(xs), len(cells)))
    return out


# ---------------------------------------------------------------- layout

class Layout:
    pass


def analyse(grid):
    comps = _components(grid)
    squares = [c for c in comps
               if c[0] not in (BG, 3) and c[2] - c[1] == c[4] - c[3]
               and c[5] == (c[2] - c[1] + 1) ** 2 and c[5] > 1]
    if not squares:
        return None
    sizes = {}
    for c in squares:
        s = c[2] - c[1] + 1
        sizes[s] = sizes.get(s, 0) + 1
    s = max(sizes, key=lambda k: (sizes[k], k))
    tiles = {}                      # (y0,x0) -> colour
    for c in squares:
        if c[2] - c[1] + 1 == s:
            tiles[(c[1], c[3])] = c[0]
    if len(tiles) < 4:
        return None
    ys = sorted({y for y, x in tiles})
    xs = sorted({x for y, x in tiles})
    pitch = min([b - a for a, b in zip(xs, xs[1:])] +
                [b - a for a, b in zip(ys, ys[1:])])

    lay = Layout()
    lay.s = s
    lay.pitch = pitch
    lay.tiles = tiles

    # arrows: non-square blobs of colour 8 / 14 inside the play area
    def arrows(col):
        return [c for c in comps if c[0] == col and c[3] > 1 and c[5] >= 6
                and not (c[2] - c[1] == c[4] - c[3] and c[5] == (c[2] - c[1] + 1) ** 2)]
    lefts = arrows(LEFT_C)
    rights = arrows(RIGHT_C)

    lay.tracks = []                 # list of (left_btn, right_btn, [slots])
    for lb in lefts:
        rb = None
        for r in rights:
            if (r[3] > lb[4] and r[1] <= lb[2] and lb[1] <= r[2]
                    and (rb is None or r[3] < rb[3])):
                rb = r
        if rb is None:
            continue
        # the track's "contact row": the tile row nearest the arrow band
        def rowdist(y):
            if y + s - 1 >= lb[1] and y <= lb[2]:
                return 0
            return min(abs(y - lb[2]), abs(lb[1] - (y + s - 1)))
        cand = [(y, x) for (y, x) in tiles
                if lb[3] <= x and x + s - 1 <= rb[4]]
        if not cand:
            continue
        best = min(rowdist(y) for y, x in cand)
        row_tiles = sorted([(y, x) for (y, x) in cand if rowdist(y) == best])
        start = row_tiles[0]
        slots = _walk(tiles, start, pitch)
        lay.tracks.append((lb, rb, slots, _sense(slots, pitch)))

    # target slots: four matching corner pips just outside a tile mark the
    # colour that slot must end up holding
    lay.targets = []                # (slot, required colour)
    for (y, x) in tiles:
        pips = [grid[a][b] for a, b in ((y - 1, x - 1), (y - 1, x + s),
                                        (y + s, x - 1), (y + s, x + s))
                if 0 <= a < N and 0 <= b < N]
        if len(pips) == 4 and len(set(pips)) == 1 and pips[0] not in (BG, 3):
            lay.targets.append(((y, x), pips[0]))
    return lay


_STRAIGHTS = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))


def _turns(d):
    """Candidate new headings, nearest-angle first (45 deg, then 90 deg)."""
    i = _STRAIGHTS.index(d)
    return [_STRAIGHTS[(i - 1) % 8], _STRAIGHTS[(i + 1) % 8],
            _STRAIGHTS[(i - 2) % 8], _STRAIGHTS[(i + 2) % 8]]


def _walk(tiles, start, pitch):
    """Follow the corridor from `start` heading right, turning at dead ends.

    Steps may be orthogonal or diagonal (rings are drawn as octagons)."""
    order = [start]
    cur, d = start, (0, 1)
    while True:
        nxt = (cur[0] + d[0] * pitch, cur[1] + d[1] * pitch)
        if nxt not in tiles:
            nd = None
            for t in _turns(d):
                cand = (cur[0] + t[0] * pitch, cur[1] + t[1] * pitch)
                if cand in tiles and (cand == start or cand not in order):
                    nd, nxt = t, cand
                    break
            if nd is None:
                return order            # straight line -> cyclic wrap
            d = nd
        if nxt == start or nxt in order:
            return order                # closed loop
        order.append(nxt)
        cur = nxt


def _sense(slots, pitch):
    """+1 if walking `slots` forwards goes CLOCKWISE on screen, else -1.

    The right-hand arrow always turns a ring clockwise (its top row moves
    right); for an open, straight track it just shifts contents rightwards.
    """
    closed = (max(abs(slots[0][0] - slots[-1][0]),
                  abs(slots[0][1] - slots[-1][1])) <= pitch)
    if not closed:
        return +1
    top = min(y for y, x in slots)
    i = min(i for i, (y, x) in enumerate(slots) if y == top)
    return +1 if slots[(i + 1) % len(slots)][1] > slots[i][1] else -1


# ---------------------------------------------------------------- dynamics

def _copy(grid):
    return [list(r) for r in grid]


def _paint(g, slot, colour, s):
    y, x = slot
    for dy in range(s):
        for dx in range(s):
            g[y + dy][x + dx] = colour


def bar_filled(grid):
    n = 0
    for y in range(N):
        if grid[y][0] == 5:
            n += 1
        else:
            break
    return n


def set_bar(g, n):
    n = min(n, N)
    for y in range(N):
        g[y][0] = 5 if y < n else 14


def _hit(box, x, y):
    return box[1] <= y <= box[2] and box[3] <= x <= box[4]


def init_state(entry_grid, level=None):
    lvl = level_of(entry_grid) if level is None else level
    if bar_filled(entry_grid) == 0 and lvl in _ENTRY and entry_grid != _ENTRY[lvl]:
        return {'a': A_OFFSET}      # resumed mid-level, gauge still empty
    return {'a': 0 if bar_filled(entry_grid) == 0 else A_OFFSET}


def predict(state, grid, action, x=None, y=None, level=None, entry_grid=None):
    if state is None:
        state = init_state(grid, level)
    state = {'a': state['a'] + 1}
    g, info = _apply(grid, action, x, y, state['a'])
    return g, info, state



# ---------------------------------------------------------------- grid levels
# From level 3 on the board is a sparse lattice of LINES: a few full rows and a
# few full columns of slots.  All row-lines are chained into ONE cyclic track
# (row-major order: first row left->right, then next row, ...), and likewise all
# column-lines into a second cycle (column-major, top->bottom).  Each arrow
# blob points in the direction its cycle's contents move; the whole cycle
# rotates by one slot per click, so tiles hop between lines at the wrap.
# CONFIRMED on level 3 transition #32 (click on the row-15 right arrow moved
# BOTH row 15 and row 45 as a single 20-cycle).

def grid_lines(lay):
    """(H_cycle, V_cycle) or None if the layout is not a line lattice."""
    tiles = lay.tiles
    rowc, colc = {}, {}
    for (y, x) in tiles:
        rowc.setdefault(y, []).append(x)
        colc.setdefault(x, []).append(y)
    R = sorted(y for y, xs in rowc.items() if len(xs) >= 5)
    C = sorted(x for x, ys in colc.items() if len(ys) >= 5)
    if len(R) < 2 or len(C) < 2:
        return None
    if any(y not in R and x not in C for (y, x) in tiles):
        return None
    # level-1 style layouts are combs (row-lines and col-lines interleave and
    # never share a tile) and there each line is its own cycle; the chained
    # behaviour is only for a true crossing lattice.
    if not any(y in R and x in C for (y, x) in tiles):
        return None
    H = [(y, x) for y in R for x in sorted(rowc[y])]
    V = [(y, x) for x in C for y in sorted(colc[x])]
    return H, V


def _apex(cells):
    """Direction a triangular arrow blob points: 'L','R','U' or 'D'."""
    ys = [y for y, x in cells]; xs = [x for y, x in cells]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
    cl = sum(1 for y, x in cells if x == x0)
    cr = sum(1 for y, x in cells if x == x1)
    ct = sum(1 for y, x in cells if y == y0)
    cb = sum(1 for y, x in cells if y == y1)
    # a left/right arrow's bbox is taller than wide, an up/down arrow's wider
    # than tall; the apex is the side holding fewest cells.
    if y1 - y0 > x1 - x0:
        return 'L' if cl < cr else 'R'
    return 'U' if ct < cb else 'D'


def _arrow_blobs(grid):
    from collections import deque
    seen = [[False] * N for _ in range(N)]
    out = []
    for y in range(N):
        for x in range(N):
            if seen[y][x] or grid[y][x] not in (LEFT_C, RIGHT_C):
                continue
            c = grid[y][x]
            q = deque([(y, x)]); seen[y][x] = True; cells = []
            while q:
                cy, cx = q.popleft(); cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < N and 0 <= nx < N and not seen[ny][nx] and grid[ny][nx] == c:
                        seen[ny][nx] = True; q.append((ny, nx))
            if len(cells) < 6 or max(b for a, b in cells) == 0:
                continue                      # col-0 action gauge
            ys = [a for a, b in cells]; xs = [b for a, b in cells]
            if max(ys) - min(ys) == max(xs) - min(xs) and len(cells) == (max(ys) - min(ys) + 1) ** 2:
                continue                      # a square tile, not an arrow
            out.append((cells, min(ys), max(ys), min(xs), max(xs)))
    return out


def _apply_grid(grid, g, lay, cycles, x, y):
    H, V = cycles
    for cells, y0, y1, x0, x1 in _arrow_blobs(grid):
        if not (y0 <= y <= y1 and x0 <= x <= x1):
            continue
        d = _apex(cells)
        cyc, step = (H, +1 if d == 'R' else -1) if d in 'LR' else (V, +1 if d == 'D' else -1)
        vals = [grid[sy][sx] for (sy, sx) in cyc]
        k = len(cyc)
        for i, slot in enumerate(cyc):
            _paint(g, slot, vals[(i - step) % k], lay.s)
        return True
    return False


# ---------------------------------------------------------------- snake levels
# Level 4 style: every tile forms ONE simple path (a serpentine chain).  Each
# horizontal arrow pair spans a range of columns; the slots of the chain inside
# that span form a cyclic track, rotated one slot per click, contents moving
# toward the clicked arrow.

def snake_path(lay):
    tiles = list(lay.tiles)
    pitch = lay.pitch
    adj = {t: [] for t in tiles}
    for a in tiles:
        for b in tiles:
            if a < b and (abs(a[0] - b[0]) + abs(a[1] - b[1])) == pitch:
                adj[a].append(b); adj[b].append(a)
    ends = [t for t in tiles if len(adj[t]) == 1]
    if len(ends) != 2 or any(len(v) > 2 for v in adj.values()):
        return None
    path = [ends[0]]
    prev = None
    while True:
        nxt = [t for t in adj[path[-1]] if t != prev]
        if not nxt:
            break
        prev = path[-1]; path.append(nxt[0])
    return path if len(path) == len(tiles) else None


def _arrow_pairs(grid):
    """[(left_blob, right_blob)] for horizontal arrow pairs sharing a band."""
    blobs = [b for b in _arrow_blobs(grid) if _apex(b[0]) in 'LR']
    lefts = [b for b in blobs if _apex(b[0]) == 'L']
    rights = [b for b in blobs if _apex(b[0]) == 'R']
    out = []
    for lb in lefts:
        cand = [r for r in rights if r[3] > lb[4] and r[1] <= lb[2] and lb[1] <= r[2]]
        if cand:
            out.append((lb, min(cand, key=lambda r: r[3])))
    return out


def _apply_snake(grid, g, lay, path, x, y):
    """Arrow pairs own tracks on the chain.

    A pair whose band holds >=2 chain slots owns exactly that straight run
    (level 4's top row); any other pair drives the WHOLE chain.  The chain is
    oriented from its topmost-leftmost end; a left/up arrow advances contents
    by +1 along it, a right/down arrow by -1 (i.e. contents always move in the
    direction the arrow points).  CONFIRMED on level 4 tx#45 and tx#46.
    """
    pairs = _arrow_pairs(grid)
    if path[0] > path[-1]:
        path = path[::-1]
    for lb, rb in pairs:
        for blob, step in ((lb, +1), (rb, -1)):
            if not (blob[1] <= y <= blob[2] and blob[3] <= x <= blob[4]):
                continue
            band = [i for i, (sy, sx) in enumerate(path)
                    if lb[1] <= sy <= lb[2] and lb[3] <= sx and sx + lay.s - 1 <= rb[4]]
            cyc = [path[i] for i in band] if len(band) >= 2 else list(path)
            vals = [grid[sy][sx] for (sy, sx) in cyc]
            n = len(cyc)
            for i, slot in enumerate(cyc):
                _paint(g, slot, vals[(i - step) % n], lay.s)
            return True
    return False


# ---------------------------------------------------------------- flower levels
# Level 5: four "flowers" — a centre with three concentric octagonal rings of 8
# slots (pitch apart, then 2*pitch, then 3*pitch).  Each flower has two buttons
# sitting one ring further out: the one on the centre ROW pushes every ray
# radially OUTWARD (ring1->2->3->1), the one under the centre COLUMN rotates all
# rings COUNTER-CLOCKWISE by one slot.  Both confirmed on tx#56 / tx#57.
# The middle flower M shares its rings 2 and 3 with the corner slots of L/R/B,
# and its ring 1 holds the three target slots; its button is the lone up arrow.
_CCW = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
L5_FLOWERS = {'L': (15, 14), 'R': (15, 44), 'B': (45, 29), 'M': (30, 29)}
L5_BUTTONS = [                       # (y0, y1, x0, x1, flower, kind)
    (14, 17, 26, 28, 'L', 'rad'), (27, 30, 14, 16, 'L', 'rot'),
    (14, 17, 56, 58, 'R', 'rad'), (27, 30, 44, 46, 'R', 'rot'),
    (44, 47, 41, 43, 'B', 'rad'), (57, 60, 29, 31, 'B', 'rot'),
    (54, 56, 52, 55, 'M', 'rad'),
]


def flower_level(lay, grid):
    return (lay.s == 2 and lay.pitch == 3 and len(lay.tiles) == 75
            and len(_arrow_blobs(grid)) == 7)


def _apply_flower(grid, g, lay, x, y):
    p, s = lay.pitch, lay.s
    for y0, y1, x0, x1, name, kind in L5_BUTTONS:
        if not (y0 <= y <= y1 and x0 <= x <= x1):
            continue
        cy, cx = L5_FLOWERS[name]
        slot = lambda k, a: (cy + p * k * a[0], cx + p * k * a[1])
        if kind == 'rad':
            # M only owns rings 1 and 2 (its ring-3 slots belong to L/R/B), so
            # its button just swaps them -- confirmed on tx#71.
            rings = (1, 2) if name == 'M' else (1, 2, 3)
            for a in _CCW:
                vals = [grid[slot(k, a)[0]][slot(k, a)[1]] for k in rings]
                for i, k in enumerate(rings):
                    _paint(g, slot(k, a), vals[(i - 1) % len(rings)], s)
        else:
            for k in (1, 2, 3):
                vals = [grid[slot(k, a)[0]][slot(k, a)[1]] for a in _CCW]
                for i, a in enumerate(_CCW):
                    _paint(g, slot(k, a), vals[(i - 1) % len(_CCW)], s)
        return True
    return False


# ---------------------------------------------------------------- level 6
# A row of 8 slots, a 3-slot column hanging off its left end (together one bent
# chain) and a separate 2x2 ring.  The pair of arrows under the ring drives the
# ROW and the RING at the same time (confirmed tx#75: left arrow = row shifts
# left AND ring turns counter-clockwise).  The up/down arrows above/below the
# column drive the bent chain (row -> corner -> column), so they move the row
# without touching the ring.
L6_ROW = [(23, 20 + 3 * i) for i in range(8)]
L6_RING = [(35, 29), (35, 32), (38, 32), (38, 29)]          # clockwise
L6_COL = [(29, 20), (26, 20), (23, 20)]   # shares (23,20) with the row
L6_BUTTONS = [(41, 44, 28, 30, -1), (41, 44, 32, 34, +1),   # ring/row pair
              (19, 21, 19, 22, +1), (32, 34, 19, 22, -1)]   # column pair


def level6(lay):
    return lay.s == 2 and lay.pitch == 3 and sorted(lay.tiles) == sorted(
        set(L6_ROW) | set(L6_RING) | set(L6_COL))


def _spin(grid, g, cyc, d, s):
    vals = [grid[y][x] for (y, x) in cyc]
    n = len(cyc)
    for i, slot in enumerate(cyc):
        _paint(g, slot, vals[(i - d) % n], s)


def _apply_l6(grid, g, lay, x, y):
    for y0, y1, x0, x1, d in L6_BUTTONS:
        if not (y0 <= y <= y1 and x0 <= x <= x1):
            continue
        if y0 > 40:                       # under the ring: row + ring together
            _spin(grid, g, L6_ROW, d, lay.s)
            _spin(grid, g, L6_RING, d, lay.s)    # same sense as the row
        else:
            _spin(grid, g, L6_COL, d, lay.s)
        return True
    return False


# ---------------------------------------------------------------- level 7
# Three cyclic tracks, each a diagonal feeder that turns into a vertical chute
# ending on a target.  The bottom arrow pair shifts ALL THREE tracks by one
# (confirmed tx#80); each right-hand panel pair instead slides just its track's
# token one slot, swapping it with the neighbour (confirmed tx#79 for the top
# pair, which drives the col-36 track).
L7_CHAINS = [
    [(12, 3), (15, 6), (18, 9), (21, 12), (24, 15), (27, 18), (30, 21),
     (33, 24), (36, 24), (39, 24), (42, 24), (45, 24), (48, 24), (51, 24)],
    [(6, 6), (9, 9), (12, 12), (15, 15), (18, 18), (21, 21), (24, 24),
     (27, 27), (30, 30), (33, 30), (36, 30), (39, 30), (42, 30), (45, 30),
     (48, 30), (51, 30)],
    [(9, 18), (12, 21), (15, 24), (18, 27), (21, 30), (24, 33), (27, 36),
     (30, 36), (33, 36), (36, 36), (39, 36), (42, 36), (45, 36), (48, 36),
     (51, 36)],
]
# panel pairs, top to bottom, drive chains 2, 1, 0 (rightmost chute first);
# only the top pair is confirmed.
L7_PANEL = [(23, 26, 2), (28, 31, 1), (33, 36, 0)]


def level7(lay):
    return (lay.s == 2 and lay.pitch == 3 and len(lay.tiles) == 69
            and all(sl in lay.tiles for c in L7_CHAINS for sl in c))


def _apply_l7(grid, g, lay, x, y):
    if 56 <= y <= 59 and 30 <= x <= 37:                 # bottom pair
        d = +1 if x >= 34 else -1
        for c in L7_CHAINS:
            _spin(grid, g, c, d, lay.s)
        return True
    for y0, y1, k in L7_PANEL:
        if y0 <= y <= y1 and 48 <= x <= 54:
            d = +1 if x >= 51 else -1
            # each pair drives the feeder segment at the head of its chain
            # (chain 0: 7 slots, confirmed tx#93; chain 2: only its first two,
            # confirmed tx#79/#88; chain 1 assumed to be its 9-slot diagonal)
            seg = {0: 7, 1: 6, 2: 2}[k]
            _spin(grid, g, L7_CHAINS[k][:seg], d, lay.s)
            return True
    return False


def _apply(grid, action, x, y, acted):
    g = _copy(grid)
    lay = analyse(grid)
    cycles = grid_lines(lay) if lay is not None else None
    if cycles is not None and len(_arrow_blobs(grid)) < 8:
        cycles = None          # few arrows -> the old single-track layouts
    path = snake_path(lay) if (lay is not None and cycles is None) else None
    if action == 6 and lay is not None and level7(lay):
        _apply_l7(grid, g, lay, x, y)
    elif action == 6 and lay is not None and level6(lay):
        _apply_l6(grid, g, lay, x, y)
    elif action == 6 and lay is not None and flower_level(lay, grid):
        _apply_flower(grid, g, lay, x, y)
    elif action == 6 and cycles is not None:
        _apply_grid(grid, g, lay, cycles, x, y)
    elif action == 6 and path is not None and _apply_snake(grid, g, lay, path, x, y):
        pass
    elif action == 6 and lay is not None:
        for lb, rb, slots, sense in lay.tracks:
            d = 0
            if _hit(lb, x, y):
                d = -sense
            elif _hit(rb, x, y):
                d = +sense
            if d:
                vals = [grid[sy][sx] for (sy, sx) in slots]
                k = len(slots)
                new = [vals[(i - d) % k] for i in range(k)]
                for slot, c in zip(slots, new):
                    _paint(g, slot, c, lay.s)
                break
    lvl = level_of(grid)
    budget = BUDGET.get(lvl, 64)
    set_bar(g, int(N * acted / budget + 0.5))
    info = {}
    if lay is not None and lay.targets and all(
            g[ty][tx] == c for (ty, tx), c in lay.targets):
        info['level_up'] = True
        if lvl + 1 in _ENTRY:
            g = [list(r) for r in _ENTRY[lvl + 1]]
    return g, info

# ---- level entry grids (auto-generated by gen_entry.py) ----
_ENTRY_HEX = {
    1: [
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333eeee35555355553555535555355553555535555333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e3333333333444444444884444444444444444ee444444444444333333333333',
        'e3333333333444444448884aa4994ff4bb4ff4eee44444444444333333333333',
        'e3333333333444444448884aa4994ff4bb4ff4eee44444444444333333333333',
        'e3333333333444444444884444444444444444ee444444444444333333333333',
        'e3333333333444444444444ff444444444499444444444444444333333333333',
        'e3333333333444444444444ff444444444499444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e3333333333444444444444224444444444aa444444444444444333333333333',
        'e3333333333444444444444224444444444aa444444444444444333333333333',
        'e333333333344488444444444444444444b44b444444444ee444333333333333',
        'e3333333333448884114994994114aa4ff4224aa4224224eee44333333333333',
        'e3333333333448884114994994114aa4ff4224aa4224224eee44333333333333',
        'e333333333344488444444444444444444b44b444444444ee444333333333333',
        'e333333333344444444444411444444444411444444444444444333333333333',
        'e333333333344444444444411444444444411444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444411444444444422444444444444444333333333333',
        'e333333333344444444444411444444444422444444444444444333333333333',
        'e333333333344488444444444444444444b44b444444444ee444333333333333',
        'e3333333333448884114aa4994114994aa4ff4994224aa4eee44333333333333',
        'e3333333333448884114aa4994114994aa4ff4994224aa4eee44333333333333',
        'e333333333344488444444444444444444b44b444444444ee444333333333333',
        'e3333333333444444444444bb444444444411444444444444444333333333333',
        'e3333333333444444444444bb444444444411444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444422444444444499444444444444444333333333333',
        'e333333333344444444444422444444444499444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e3333333333444444444444aa4aa4ff4ff422444444444444444333333333333',
        'e3333333333444444444444aa4aa4ff4ff422444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333344444444444444444444444444444444444444444333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
    ],
    2: [
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333eeee3eeee355553555535555355553555535555333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e33333333333444444444994ff4224444aa4ff49944444444443333333333333',
        'e33333333333444444444994ff4224444aa4ff49944444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e33333333333444444994444444444994444444444bb44444443333333333333',
        'e33333333333444444994444444444994444444444bb44444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e33333333333444114444444444ff44441144444444442244443333333333333',
        'e33333333333444114444444444ff44441144444444442244443333333333333',
        'e3333333333344b44b44444444444444444444444444c44c4443333333333333',
        'e33333333333444994444444444114444ff44444444449944443333333333333',
        'e33333333333444994444444444114444ff44444444449944443333333333333',
        'e3333333333344b44b44444444444444444444444444c44c4443333333333333',
        'e33333333333444aa4444444444224444994444444444ff44443333333333333',
        'e33333333333444aa4444444444224444994444444444ff44443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e33333333333444444cc44444444442244444444441144444443333333333333',
        'e33333333333444444cc44444444442244444444441144444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e33333333333444444444114994aa4444114224aa44444444443333333333333',
        'e33333333333444444444114994aa4444114224aa44444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333334444444444488ee4444444488ee4444444444443333333333333',
        'e333333333334444444444888eee444444888eee444444444443333333333333',
        'e333333333334444444444888eee444444888eee444444444443333333333333',
        'e333333333334444444444488ee4444444488ee4444444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333334444444444444444444444444444444444444443333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
    ],
    3: [
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333eeee3eeee3eeee3555535555355553555535555333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444ee4444444444444444444444444444ee44444444444443333',
        'e3344444444444eeee44444444444444444444444444eeee4444444444443333',
        'e3344444444444eeee44444444444444444444444444eeee4444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444aa44444444444444444444444444449944444444444443333',
        'e33444444444444aa44444444444444444444444444449944444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444449944444444444444444444444444442244444444444443333',
        'e334444444444449944444444444444444444444444442244444444444443333',
        'e33444884444444444444444ee4444444444884444444444444444ee44443333',
        'e33448884114224114ff4aa4eee444444448884bb4994114224ff4eee4443333',
        'e33448884114224114ff4aa4eee444444448884bb4994114224ff4eee4443333',
        'e33444884444444444444444ee4444444444884444444444444444ee44443333',
        'e334444444444442244444444444444444444444444441144444444444443333',
        'e334444444444442244444444444444444444444444441144444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444ff4444444444444444444444444444aa44444444444443333',
        'e33444444444444ff4444444444444444444444444444aa44444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444488884444444444444444444444444488884444444444443333',
        'e334444444444488884444444444444444444444444488884444444444443333',
        'e334444444444448844444444444444444444444444448844444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444ee4444444444444444444444444444ee44444444444443333',
        'e3344444444444eeee44444444444444444444444444eeee4444444444443333',
        'e3344444444444eeee44444444444444444444444444eeee4444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444224444444444444444444444444444ff44444444444443333',
        'e33444444444444224444444444444444444444444444ff44444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444ff44444444444444444444444444442244444444444443333',
        'e33444444444444ff44444444444444444444444444442244444444444443333',
        'e33444884444444444444444ee444444444488444444b44b44c44cee44443333',
        'e33448884114994224aa4114eee444444448884994994ff4aa4114eee4443333',
        'e33448884114994224aa4114eee444444448884994994ff4aa4114eee4443333',
        'e33444884444444444444444ee444444444488444444b44b44c44cee44443333',
        'e33444444444444cc4444444444444444444444444444aa44444444444443333',
        'e33444444444444cc4444444444444444444444444444aa44444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e33444444444444aa44444444444444444444444444442244444444444443333',
        'e33444444444444aa44444444444444444444444444442244444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444488884444444444444444444444444488884444444444443333',
        'e334444444444488884444444444444444444444444488884444444444443333',
        'e334444444444448844444444444444444444444444448844444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e334444444444444444444444444444444444444444444444444444444443333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
    ],
    4: [
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444eeee4eeee4eeee4eeee45555455554555545555444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e33334444888844bb4444bb4444444444444444bb4444bb44eeee44444433333',
        'e33334444888844bb4444bb4444444444444444bb4444bb44eeee44444433333',
        'e3333448888884444aaaa44999944222244ffff4411114444eeeeee444433333',
        'e3333448888884444aaaa44999944222244ffff4411114444eeeeee444433333',
        'e3333448888884444aaaa44999944222244ffff4411114444eeeeee444433333',
        'e3333448888884444aaaa44999944222244ffff4411114444eeeeee444433333',
        'e33334444888844bb4444bb4444444444444444bb4444bb44eeee44444433333',
        'e33334444888844bb4444bb4444444444444444bb4444bb44eeee44444433333',
        'e3333444444444444ffff4444444444444444444444444444444444444433333',
        'e3333444444444444ffff4444444444444444444444444444444444444433333',
        'e3333444444444444ffff4444444444444444444444444444444444444433333',
        'e3333444444444444ffff4444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e3333444444444444bbbb4422224499994444444444444444444444444433333',
        'e3333444444444444bbbb4422224499994444444444444444444444444433333',
        'e3333444444444444bbbb4422224499994444444444444444444444444433333',
        'e3333444444444444bbbb4422224499994444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444411114444444444444444444444444433333',
        'e333344444444444444444444444411114444444444444444444444444433333',
        'e333344444444444444444444444411114444444444444444444444444433333',
        'e333344444444444444444444444411114444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444411114411114499994444444444444444444444444433333',
        'e333344444444444411114411114499994444444444444444444444444433333',
        'e333344444444444411114411114499994444444444444444444444444433333',
        'e333344444444444411114411114499994444444444444444444444444433333',
        'e3333444444888844444444444444444444eeee4444444444444444444433333',
        'e3333444444888844444444444444444444eeee4444444444444444444433333',
        'e3333444488888844aaaa44444444444444eeeeee44444444444444444433333',
        'e3333444488888844aaaa44444444444444eeeeee44444444444444444433333',
        'e3333444488888844aaaa44444444444444eeeeee44444444444444444433333',
        'e3333444488888844aaaa44444444444444eeeeee44444444444444444433333',
        'e3333444444888844444444444444444444eeee4444444444444444444433333',
        'e3333444444888844444444444444444444eeee4444444444444444444433333',
        'e3333444444444444ffff44111144aaaa4444444444444444444444444433333',
        'e3333444444444444ffff44111144aaaa4444444444444444444444444433333',
        'e3333444444444444ffff44111144aaaa4444444444444444444444444433333',
        'e3333444444444444ffff44111144aaaa4444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444499994444444444444444444444444433333',
        'e333344444444444444444444444499994444444444444444444444444433333',
        'e333344444444444444444444444499994444444444444444444444444433333',
        'e333344444444444444444444444499994444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e3333444444444444111144111144bbbb4444444444444444444444444433333',
        'e3333444444444444111144111144bbbb4444444444444444444444444433333',
        'e3333444444444444111144111144bbbb4444444444444444444444444433333',
        'e3333444444444444111144111144bbbb4444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
        'e333344444444444444444444444444444444444444444444444444444433333',
    ],
    5: [
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444eeee4eeee4eeee4eeee4eeee455554555545555444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444114444444ff4444444ff4444444444aa4444444ff444444411444444433',
        'e3444114444444ff4444444ff4444444444aa4444444ff444444411444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444aa4444224444224444444444444444224444ff444499444444444433',
        'e3444444aa4444224444224444444444444444224444ff444499444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444444114994114444444444444444444444aa4224bb444444444444433',
        'e3444444444114994114444444444444444444444aa4224bb444444444444433',
        'e3444444444444444444444444ee4444444444444444444444444444ee444433',
        'e3444ff4aa4994444994aa4ff4eee444444aa4224224444994224224eee44433',
        'e3444ff4aa4994444994aa4ff4eee444444aa4224224444994224224eee44433',
        'e3444444444444444444444444ee4444444444444444444444444444ee444433',
        'e3444444444bb4114994444444444444444444444aa4ff411444444444444433',
        'e3444444444bb4114994444444444444444444444aa4ff411444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444aa4444aa4444aa4444444444444444ff4444ff4444aa444444444433',
        'e3444444aa4444aa4444aa4444444444444444ff4444ff4444aa444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444ff4444444994444444ff4444444444ff444444422444444499444444433',
        'e3444ff4444444994444444ff4444444444ff444444422444444499444444433',
        'e344444444444444444444444b44b44b44b44444444444444444444444444433',
        'e3444444444444ee4444444444224444aa4444444444ee444444444444444433',
        'e3444444444444eee444444444224444aa4444444444eee44444444444444433',
        'e3444444444444eee44444444b44b44b44b444444444eee44444444444444433',
        'e3444444444444ee4444444444444444444444444444ee444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444b44b44444444444444444444444444444433',
        'e3444444444444444444444444444ff444444444444444444444444444444433',
        'e3444444444444444444444444444ff444444444444444444444444444444433',
        'e344444444444444444444444444b44b44444444444444444444444444444433',
        'e3444444444444444444114444444aa444444411444444444444444444444433',
        'e3444444444444444444114444444aa444444411444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444444444444444444224444994444aa444444444444444444444444433',
        'e3444444444444444444444224444994444aa444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444444444444444444444224aa411444444444444444444444444444433',
        'e3444444444444444444444444224aa411444444444444444444444444444433',
        'e3444444444444444444444444444444444444444ee444444444444444444433',
        'e3444444444444444444114994bb4444224114aa4eee44444444444444444433',
        'e3444444444444444444114994bb4444224114aa4eee44444444444444444433',
        'e3444444444444444444444444444444444444444ee444444444444444444433',
        'e3444444444444444444444444aa4aa422444444444444444444444444444433',
        'e3444444444444444444444444aa4aa422444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444444444444444444aa444422444411444444444444444444444444433',
        'e3444444444444444444444aa444422444411444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e3444444444444444444994444444ff4444444114444444444444ee444444433',
        'e3444444444444444444994444444ff444444411444444444444eeee44444433',
        'e344444444444444444444444444444444444444444444444444eeee44444433',
        'e3444444444444444444444444444ee444444444444444444444444444444433',
        'e3444444444444444444444444444eee44444444444444444444444444444433',
        'e3444444444444444444444444444eee44444444444444444444444444444433',
        'e3444444444444444444444444444ee444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
        'e344444444444444444444444444444444444444444444444444444444444433',
    ],
    6: [
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333eeee3eeee3eeee3eeee3eeee3eeee3555535555333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e3333333444444444444ee444444444444444444444444444444444433333333',
        'e333333344444444444eeee44444444444444444444444444444444433333333',
        'e333333344444444444eeee44444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444b44b44444444444433333333',
        'e3333333444444444444ff4aa4114ff4224114994bb444444444444433333333',
        'e3333333444444444444ff4aa4114ff4224114994bb444444444444433333333',
        'e333333344444444444444444444444444444444b44b44444444444433333333',
        'e333333344444444444422444444444444444444444444444444444433333333',
        'e333333344444444444422444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e3333333444444444444ff444444444444444444444444444444444433333333',
        'e3333333444444444444ff444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444888844444444444444444444444444444444433333333',
        'e333333344444444444888844444444444444444444444444444444433333333',
        'e333333344444444444488444444444b44b44444444444444444444433333333',
        'e3333333444444444444444444444114ff444444444444444444444433333333',
        'e3333333444444444444444444444114ff444444444444444444444433333333',
        'e333333344444444444444444444444b44b44444444444444444444433333333',
        'e3333333444444444444444444444994bb444444444444444444444433333333',
        'e3333333444444444444444444444994bb444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e3333333444444444444444444444884ee444444444444444444444433333333',
        'e3333333444444444444444444448884eee44444444444444444444433333333',
        'e3333333444444444444444444448884eee44444444444444444444433333333',
        'e3333333444444444444444444444884ee444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333344444444444444444444444444444444444444444444444433333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
        'e333333333333333333333333333333333333333333333333333333333333333',
    ],
    7: [
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444eeee4eeee4eeee4eeee4eeee4eeee4eeee45555444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444449944444444444444449944444444444444444444444444444444444443',
        'e444449944444444444444449944444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444114444444bb4444994444444444aa44444444444444444444444443',
        'e44444444114444444bb4444994444444444aa44444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44aa4444444994444444ff4444444114444994444ff44444444444444444443',
        'e44aa4444444994444444ff4444444114444994444ff44444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444224444444114444444224444ff4444aa44449944444444444444444443',
        'e44444224444444114444444224444ff4444aa44449944444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444994444444bb4444444224444444aa44441144444444444444444443',
        'e44444444994444444bb4444444224444444aa44441144444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444ff44444441144444442244442244449944444444444444444443',
        'e44444444444ff44444441144444442244442244449944444444444444444443',
        'e444444444444444444444444444444444444444444444444884ee4444444443',
        'e44444444444444994444444ff44444442244444442244448884eee444444443',
        'e44444444444444994444444ff44444442244444442244448884eee444444443',
        'e444444444444444444444444444444444444444444444444884ee4444444443',
        'e44444444444444444bb4444444aa4444444aa4444aa44444444444444444443',
        'e44444444444444444bb4444444aa4444444aa4444aa44444884ee4444444443',
        'e444444444444444444444444444444444444444444444448884eee444444443',
        'e44444444444444444444224444444994444aa4444ff44448884eee444444443',
        'e44444444444444444444224444444994444aa4444ff44444884ee4444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444444444444444994444ff4444ff4444aa44444884ee4444444443',
        'e44444444444444444444444994444ff4444ff4444aa44448884eee444444443',
        'e444444444444444444444444444444444444444444444448884eee444444443',
        'e44444444444444444444444aa4444aa4444ff44449944444884ee4444444443',
        'e44444444444444444444444aa4444aa4444ff44449944444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444444444444444114444aa4444aa4444ff44444444444444444443',
        'e44444444444444444444444114444aa4444aa4444ff44444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444444444444444aa4444224444ff4444aa44444444444444444443',
        'e44444444444444444444444aa4444224444ff4444aa44444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444444444444444aa4444994444ff44449944444444444444444443',
        'e44444444444444444444444aa4444994444ff44449944444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e44444444444444444444444224444224444994224ff44444444444444444443',
        'e44444444444444444444444224444224444994224ff44444444444444444443',
        'e4444444444444444444444b44b44b44b44b44b4444444444444444444444443',
        'e44444444444444444444444224444994444ff44449944444444444444444443',
        'e44444444444444444444444224444994444ff44449944444444444444444443',
        'e4444444444444444444444b44b44b44b44b44b4444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e4444444444444444444444444444448844ee444444444444444444444444443',
        'e4444444444444444444444444444488844eee44444444444444444444444443',
        'e4444444444444444444444444444488844eee44444444444444444444444443',
        'e4444444444444444444444444444448844ee444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e444444444444444444444444444444444444444444444444444444444444443',
        'e333333333333333333333333333333333333333333333333333333333333333',
    ],
}
_ENTRY = {k: [[int(c, 16) for c in row] for row in v]
          for k, v in _ENTRY_HEX.items()}
