"""World model for lf52 -- PEG SOLITAIRE on 4x4 cells (pitch 6) plus a CART.

Cells
  empty            : 4x4 all 1
  peg              : 12-px circle of 14 on 1 (corners 1)
  jump landing mark: 8-px circle outline of 2 on 1
  selected peg     : ring of 3 in the gap around the cell + the cell's corners
Row 0 is an action counter: pixel k = 1 once k+1 actions have been taken.

Clicks (confirmed): click a peg with >=1 legal jump -> select + mark landings;
click a marked landing -> jump; anything else -> no-op.

The CART (level 1+) is the 6x6 box of 11 framing a 4x4 interior of 12 that
rides the drawn pipe. Actions 1/2/3/4 = up/down/left/right move it one lattice
step (6px) along the pipe; it is a normal cell for jumps whenever it is docked
6px from a board cell, so it ferries a peg between boards. Arrow moves clear
any selection.

Win: level_up when a single peg is left. Reaching a position with >1 peg and
no legal jump freezes the board (pegs turn 2) and shows a restart icon.
"""

CIRCLE = [(0, 1), (0, 2),
          (1, 0), (1, 1), (1, 2), (1, 3),
          (2, 0), (2, 1), (2, 2), (2, 3),
          (3, 1), (3, 2)]
OUTLINE = [(0, 1), (0, 2), (1, 0), (1, 3), (2, 0), (2, 3), (3, 1), (3, 2)]

PEG, MARK, EMPTY, SEL = 14, 2, 1, 3
OBJ, OBJ2 = 15, 7   # level 3+: a jumpable object standing on a cell
CART_FRAME, CART_FILL, BG, PIPE, SHADOW = 11, 12, 10, 5, 9
PITCH = 6

# per level: cart track nodes (interior top-left) and the pipe lanes it rides
TRACK = {
    1: [(15, 49), (15, 55), (21, 55), (27, 55), (33, 55),
        (33, 49), (33, 43), (33, 37), (33, 31), (33, 25), (33, 19), (33, 13),
        (39, 13), (45, 13), (51, 13), (51, 19), (51, 25), (51, 31), (51, 37)],
    # level 2: two carts, moved in LOCKSTEP by one arrow
    3: [(24, 48), (24, 54), (24, 60), (24, 66), (24, 72),
        (48, 54), (48, 60), (48, 66), (48, 72), (48, 78),
        (54, 54), (60, 54)],
    2: [(12, 36), (12, 42), (12, 48), (12, 54),
        (48, 30), (48, 36), (48, 42), (42, 42), (36, 42),
        (36, 48), (36, 54), (42, 54), (48, 54), (48, 60)],
}
# inclusive (y0, y1, x0, x1) rectangles of 2px-wide pipe
LANES = {
    1: [(16, 17, 48, 57), (16, 35, 56, 57), (34, 35, 14, 57),
        (34, 53, 14, 15), (52, 53, 14, 41)],
    3: [(25, 26, 47, 76), (49, 50, 55, 82), (49, 63, 55, 56)],
    2: [(13, 14, 35, 58), (49, 50, 29, 44), (37, 50, 43, 44),
        (37, 38, 43, 56), (37, 50, 55, 56), (49, 50, 55, 63)],
}
DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}

# Levels whose world is wider than the 64x64 frame: the camera pans (in steps
# of 8px) to follow the peg-carrying cart, so the frame shows only part of the
# board and neither the freeze test nor cart-track lookups can be evaluated
# from one frame. Those levels are planned with an offline world-map solver.
CAMERA_LEVELS = {2, 3}

# `commit` injects ENTRY_GRID = the frame at COMMIT START, so when a cart is
# docked there the scenery it hides is unknown. These 9x9 patches record the
# true scenery under each dock, read off the level's real entry frame.
DOCK_BG = {
    2: {
        (12, 36): ["059aaaaaa", "059aaaaaa", "059aaaaaa", "055555555",
                   "055555555", "059aaaaaa", "059aaaaaa", "559aaaaaa",
                   "999aaaaaa"],
        (12, 54): ["aaaaaa555", "aaaaaa500", "aaaaaa501", "55555550e",
                   "55555550e", "aaaaaa501", "aaaaaa500", "aaaaaa555",
                   "aaaaaaa99"],
        (48, 30): ["55aaaaaaa", "059aaaaaa", "059aaaaaa", "055555555",
                   "055555555", "059aaaaaa", "059aaaaaa", "559aaaaaa",
                   "999aaaaaa"],
    },
}

# The restart icon drawn at the bottom-left when the board freezes; '.' keeps
# the background. Top-left corner is (ICON_Y, ICON_X); clicking it restarts.
ICON_Y, ICON_X = 51, 2
ICON = [
    ".55555555..",
    "55ffffff55.",
    "5ffffffff59",
    "5ff5555ff59",
    "5ff5005ff59",
    "5ff5005ff59",
    "5ff5555ff59",
    "5ffffffff59",
    "55ffffff559",
    ".555ff55599",
    "...5ff5999.",
    "...5ff59...",
    "...5ff59...",
]


def _runs(vals):
    out = []
    for v in sorted(vals):
        if out and v == out[-1][-1] + 1:
            out[-1].append(v)
        else:
            out.append([v])
    return out


def _carts(grid):
    """Interior top-left of every cart. A selected peg inside a cart repaints
    part of its 11-frame with the 3 highlight, so components are grown over
    {11, 3} and kept only if they contain at least one frame pixel (a selected
    ordinary cell gives a pure-3 ring, which is not a cart)."""
    seen = set()
    out = []
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            if grid[y][x] in (CART_FRAME, SEL) and (y, x) not in seen:
                stack = [(y, x)]
                cur = []
                while stack:
                    a, b = stack.pop()
                    if (a, b) in seen or not (0 <= a < len(grid) and
                                              0 <= b < len(grid[0])):
                        continue
                    if grid[a][b] not in (CART_FRAME, SEL):
                        continue
                    seen.add((a, b))
                    cur.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        stack.append((a + da, b + db))
                if any(grid[a][b] == CART_FRAME for a, b in cur):
                    out.append((min(p[0] for p in cur) + 1,
                                min(p[1] for p in cur) + 1))
    return sorted(out)


def _cart(grid):
    c = _carts(grid)
    return c[0] if c else None


def _off(carts):
    """Camera pan (multiple of 8) inferred by matching carts to the track."""
    track = TRACK.get(CURRENT_LEVEL, [])
    if not track:
        return 0
    for o in range(0, 65):
        ok = True
        for c in carts:
            if (c[0], c[1] + o) not in track:
                ok = False
        if ok:
            return o
    return 0


def _lane(y, x):
    for y0, y1, x0, x1 in LANES.get(CURRENT_LEVEL, []):
        if y0 <= y <= y1 and x0 <= x <= x1:
            return True
    return False


def _kind(grid, by, bx):
    vals = [grid[by + dy][bx + dx] for dy in range(4) for dx in range(4)]
    if PEG in vals:
        return 'peg'
    if MARK in vals:
        return 'mark'
    return 'empty'


def _cells(grid, carts):
    """dict (by,bx) -> kind, for board cells plus every cart."""
    xs, ys = set(), set()
    for y in range(1, len(grid)):
        for x in range(len(grid[y])):
            if grid[y][x] in (EMPTY, MARK, PEG):
                inside = False
                for c in carts:
                    if c[0] <= y < c[0] + 4 and c[1] <= x < c[1] + 4:
                        inside = True
                if inside:
                    continue          # cart contents are not board lattice
                xs.add(x)
                ys.add(y)
    cells = {}
    for by in [r[0] for r in _runs(ys)]:
        for bx in [c[0] for c in _runs(xs)]:
            if by + 4 > len(grid) or bx + 4 > len(grid[0]):
                continue
            vals = [grid[by + dy][bx + dx]
                    for dy in range(4) for dx in range(4)]
            if any(v in (EMPTY, MARK, PEG, SEL) for v in vals):
                cells[(by, bx)] = _kind(grid, by, bx)
    for c in carts:
        cells[c] = _kind(grid, c[0], c[1])
    # level 3+: objects of colour 15 stand on a cell, drawn one row higher;
    # they behave as pegs for jumping.
    seen = set()
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            if grid[y][x] == OBJ and (y, x) not in seen:
                stack = [(y, x)]
                cur = []
                while stack:
                    a, b = stack.pop()
                    if (a, b) in seen or not (0 <= a < len(grid) and
                                              0 <= b < len(grid[0])):
                        continue
                    if grid[a][b] not in (OBJ, OBJ2):
                        continue
                    seen.add((a, b))
                    cur.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        stack.append((a + da, b + db))
                oy = min(p[0] for p in cur)
                ox = min(p[1] for p in cur)
                cells[(oy + 1, ox)] = 'obj'
    return cells


def _jumps(cells, cell):
    out = []
    by, bx = cell
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        mid = (by + PITCH * dy, bx + PITCH * dx)
        dst = (by + 2 * PITCH * dy, bx + 2 * PITCH * dx)
        if cells.get(mid) in ('peg', 'obj') and \
                cells.get(dst) in ('empty', 'mark'):
            out.append((dst, mid))
    return out


def _paint(grid, by, bx, kind, cart=None):
    base = CART_FILL if cart == (by, bx) else EMPTY
    for dy in range(4):
        for dx in range(4):
            grid[by + dy][bx + dx] = base
    if kind == 'peg':
        for dy, dx in CIRCLE:
            grid[by + dy][bx + dx] = PEG
    elif kind == 'mark':
        for dy, dx in OUTLINE:
            grid[by + dy][bx + dx] = MARK


def _ring(grid, by, bx, on, cart=None):
    fill = CART_FILL if cart == (by, bx) else EMPTY
    off = CART_FRAME if cart == (by, bx) else 0
    for dx in range(4):
        grid[by - 1][bx + dx] = SEL if on else off
        grid[by + 4][bx + dx] = SEL if on else off
    for dy in range(4):
        grid[by + dy][bx - 1] = SEL if on else off
        grid[by + dy][bx + 4] = SEL if on else off
    for dy, dx in ((0, 0), (0, 3), (3, 0), (3, 3)):
        grid[by + dy][bx + dx] = SEL if on else fill


def _selected(grid, cells):
    for (by, bx) in cells:
        if grid[by][bx] == SEL and grid[by - 1][bx] == SEL:
            return (by, bx)
    return None


def _clear(grid, cells, sel, carts):
    on = None
    for c in (carts or []):
        if c == sel:
            on = c
    if sel is not None:
        _ring(grid, sel[0], sel[1], False, on)
        _paint(grid, sel[0], sel[1], 'peg', on)
    for (by, bx), kind in cells.items():
        if kind == 'mark':
            here = None
            for c in (carts or []):
                if c == (by, bx):
                    here = c
            _paint(grid, by, bx, 'empty', here)


def _bg(y, x):
    """The static scenery under a cart: the entry grid, except where the entry
    grid itself held a cart (bare pipe/background, or a recorded dock patch)."""
    for e0 in _carts(ENTRY_GRID):
        if e0[0] - 2 <= y <= e0[0] + 6 and e0[1] - 2 <= x <= e0[1] + 6:
            patch = DOCK_BG.get(CURRENT_LEVEL, {}).get(e0)
            if patch:
                return int(patch[y - e0[0] + 2][x - e0[1] + 2], 16)
            return PIPE if _lane(y, x) else BG
    return ENTRY_GRID[y][x]


def _draw_cart(grid, by, bx, kind):
    # Where the cart docks it is clipped by the board: nothing is drawn over
    # board interior, and its shadow only falls on plain background.
    def body(y, x, v):
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return
        if _bg(y, x) not in (0, EMPTY, MARK, PEG):
            grid[y][x] = v

    def shade(y, x):
        if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
            return
        if _bg(y, x) in (BG, SHADOW):
            grid[y][x] = SHADOW

    for y in range(by - 2, by + 6):                     # 8x8 grey border
        for x in range(bx - 2, bx + 6):
            if y in (by - 2, by + 5) or x in (bx - 2, bx + 5):
                body(y, x, PIPE)
    for y in range(by - 1, by + 5):                     # 6x6 frame
        for x in range(bx - 1, bx + 5):
            if y in (by - 1, by + 4) or x in (bx - 1, bx + 4):
                body(y, x, CART_FRAME)
    for dy in range(4):                                 # interior (clipped)
        for dx in range(4):
            if 0 <= by + dy < len(grid) and 0 <= bx + dx < len(grid[0]):
                grid[by + dy][bx + dx] = CART_FILL
    if kind == 'peg':
        for dy, dx in CIRCLE:
            if 0 <= bx + dx < len(grid[0]):
                grid[by + dy][bx + dx] = PEG
    elif kind == 'mark':
        for dy, dx in OUTLINE:
            if 0 <= bx + dx < len(grid[0]):
                grid[by + dy][bx + dx] = MARK
    for y in range(by - 1, by + 6):                     # drop shadow
        shade(y, bx + 6)
    for x in range(bx - 1, bx + 7):
        shade(by + 6, x)


def _erase_cart(grid, by, bx):
    """Restore what the cart covers: the entry grid, or bare pipe/background
    where the entry grid had a cart itself."""
    e0s = _carts(ENTRY_GRID)
    for y in range(by - 2, by + 7):
        for x in range(bx - 2, bx + 7):
            if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
                continue
            v = _bg(y, x)
            if v not in (EMPTY, MARK, PEG):
                grid[y][x] = v


def _dead(cells, carts):
    """No jump is available for any single-cart repositioning on the track."""
    board = dict(cells)
    carried = {}
    for c in (carts or []):
        carried[c] = board.pop(c, 'empty')
    trials = [dict(board)]
    for c in (carts or []):
        base = dict(board)
        for o in (carts or []):
            if o != c:
                base[o] = carried[o]
        for t in TRACK.get(CURRENT_LEVEL, []):
            trial = dict(base)
            trial[t] = carried[c]
            trials.append(trial)
    for trial in trials:
        for c, k in trial.items():
            if k == 'peg' and _jumps(trial, c):
                return False
    return True


def _frozen(grid):
    """A frozen board shows the restart icon."""
    return grid[ICON_Y + 4][ICON_X] == PIPE and grid[ICON_Y + 4][ICON_X + 3] == PIPE


def _freeze(grid, cells):
    for (by, bx), kind in cells.items():
        if kind == 'peg':
            for dy, dx in CIRCLE:
                grid[by + dy][bx + dx] = MARK
    for dy, row in enumerate(ICON):
        for dx, ch in enumerate(row):
            if ch != '.':
                grid[ICON_Y + dy][ICON_X + dx] = int(ch, 16)


def step(grid, action, x=None, y=None):
    g = [list(row) for row in grid]
    n = sum(1 for v in g[0] if v)
    if n < len(g[0]):
        g[0][n] = 1
    info = {}

    if _frozen(grid):
        # only the restart icon responds
        if (action == 6 and x is not None and
                ICON_X <= x < ICON_X + len(ICON[0]) and
                ICON_Y <= y < ICON_Y + len(ICON)):
            g = [list(row) for row in ENTRY_GRID]
            for k in range(n + 1):
                g[0][k] = 1
        return g, info

    carts = _carts(grid)
    cells = _cells(grid, carts)
    sel = _selected(grid, cells)

    if action in DIRS:
        dy, dx = DIRS[action]
        track = TRACK.get(CURRENT_LEVEL, [])
        off = _off(carts)
        moving = []
        for c in carts:
            dst = (c[0] + PITCH * dy, c[1] + PITCH * dx)
            if (dst[0], dst[1] + off) in track:
                moving.append((c, dst))
        if not moving:
            return g, info
        _clear(g, cells, sel, carts)
        for c, _d in moving:
            _erase_cart(g, c[0], c[1])
        for c, dst in moving:
            _draw_cart(g, dst[0], dst[1], cells.get(c, 'empty'))
        for c in carts:
            stays = True
            for m in moving:
                if m[0] == c:
                    stays = False
            if stays:
                _draw_cart(g, c[0], c[1], cells.get(c, 'empty'))
        return g, info

    if action != 6 or x is None or y is None:
        return g, info

    def dud():
        gg = [list(row) for row in g]
        _clear(gg, cells, sel, carts)
        return gg, info

    hit = None
    for (by, bx) in cells:
        if by <= y < by + 4 and bx <= x < bx + 4:
            hit = (by, bx)
    if hit is None:
        return dud()

    kind = cells[hit]
    if kind == 'obj':
        return dud()
    if kind == 'peg':
        if hit == sel:
            return g, info
        jumps = _jumps(cells, hit)
        if not jumps:
            return dud()
        _clear(g, cells, sel, carts)
        _ring(g, hit[0], hit[1], True, hit if hit in carts else None)
        for dst, _m in jumps:
            _paint(g, dst[0], dst[1], 'mark',
                   dst if dst in carts else None)
        return g, info

    if kind == 'mark' and sel is not None:
        mid = None
        for dst, m in _jumps(cells, sel):
            if dst == hit:
                mid = m
        if mid is None:
            return dud()
        _clear(g, cells, sel, carts)
        _paint(g, sel[0], sel[1], 'empty', sel if sel in carts else None)
        if cells.get(mid) == 'peg':      # objects are pivots: never consumed
            _paint(g, mid[0], mid[1], 'empty', mid if mid in carts else None)
        _paint(g, hit[0], hit[1], 'peg', hit if hit in carts else None)
        after = dict(cells)
        after[sel] = 'empty'
        if cells.get(mid) == 'peg':
            after[mid] = 'empty'
        after[hit] = 'peg'
        pegs = sum(1 for k in after.values() if k == 'peg')
        if pegs <= 1:
            info['level_up'] = True
        elif CURRENT_LEVEL not in CAMERA_LEVELS and _dead(after, carts):
            _freeze(g, after)
        return g, info

    return dud()
