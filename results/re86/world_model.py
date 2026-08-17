"""World model for re86.

Scene (constant within a level):
  * background 5; row 63 is a bar of f whose lit cells =
    round(64 * actions_used_this_level / 100)  -- i.e. a 100-action budget
    per level (verified on every action of levels 0-1);
  * static 3x3 'tokens': 4-border, centre pixel = a shape colour;
  * one or more movable 'shapes'. A shape is a rigid set of cells around a
    centre. Seen so far: plus(L) (centre included), X(L) (centre excluded,
    level 1) and X(L) with centre included (level 2), diamond outline(R),
    horizontal line(L). Several shapes may share one colour (level 2).

Actions: 1=up 2=down 3=left 4=right translate the ACTIVE shape by 3 cells;
5 cycles which shape is active. The active shape's centre pixel renders 0.

Goal (confirmed levels 0-1): every token is covered by a shape of its own
colour -- the shape passes through the token's 3x3 box.
"""

BG = 5
BAR_ROW = 63
H, W = 63, 64
DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
STEP = 3
NONSHAPE = {BG, 4, 0, 15}
BUDGETS = {0: 100, 1: 100, 2: 200, 3: 200, 4: 250, 5: 200, 6: 300}   # actions per level; bar = round(64n/B)
DEFAULT_BUDGET = 200
# Auto-detected levels: shapes are ordered by this list -- it fixes both the
# draw order (later = on top) and the action-5 cycle order.
DRAW_ORDER = [0xc, 0xd, 0x9, 0xb]
CURRENT_LEVEL = 0   # injected by the harness before every call
RESUME_N = 87        # actions used so far on the live level, when known


def budget(level):
    return BUDGETS.get(level, DEFAULT_BUDGET)


def bar_cells(n, level):
    B = budget(level)
    return (2 * W * n + B) // (2 * B)


def _n_from_bar(cells, level):
    if RESUME_N is not None and bar_cells(RESUME_N, level) == cells:
        return RESUME_N
    if cells == 0:
        return 0
    n = 0
    while bar_cells(n, level) < cells:
        n += 1
    return n


# --- shape geometry -------------------------------------------------------

def offsets(kind, R):
    if kind == "plus":
        return {(d, 0) for d in range(-R, R + 1)} | \
               {(0, d) for d in range(-R, R + 1)}
    if kind == "X":                       # centre NOT part of the figure
        return {(d, d) for d in range(-R, R + 1) if d} | \
               {(d, -d) for d in range(-R, R + 1) if d}
    if kind == "Xc":                      # centre included
        return {(d, d) for d in range(-R, R + 1)} | \
               {(d, -d) for d in range(-R, R + 1)}
    if kind == "diamond":                 # outline only
        return {(dr, dc) for dr in range(-R, R + 1)
                for dc in (R - abs(dr), abs(dr) - R)}
    if kind == "hline":
        return {(0, d) for d in range(-R, R + 1)}
    if kind == "vline":
        return {(d, 0) for d in range(-R, R + 1)}
    if kind == "rect":                    # square outline, half-size R
        return {(dr, dc) for dr in range(-R, R + 1) for dc in range(-R, R + 1)
                if max(abs(dr), abs(dc)) == R}
    raise ValueError(kind)


# Shapes that auto-fitting cannot recover (several per colour, odd kinds,
# or shapes whose colour changes).  level -> [(kind, R, entry centre), ...]
LEVEL_SHAPES = {
    2: [("hline", 21, (45, 30)),
        ("Xc", 11, (48, 18)),
        ("diamond", 12, (48, 45))],
    3: [("plus", 13, (36, 54)),
        ("Xc", 10, (21, 24))],
    5: [("rect", 9, (48, 15)),
        ("plus", 12, (15, 48))],
    4: [("plus", 14, (33, 54)),
        ("Xc", 11, (42, 24)),
        ("diamond", 9, (18, 30))],
}
# Palette boxes are static; recorded per level so a shape parked on top of
# one does not hide it. level -> [(colour, top row, left col), ...]
LEVEL_SWATCHES = {
    3: [(0xa, 4, 4), (0xc, 4, 28), (0xd, 4, 52),
        (0xb, 54, 4), (0x6, 54, 28), (0xe, 54, 52)],
    4: [(0xb, 3, 3), (0xa, 3, 54), (0xe, 27, 3), (0x9, 52, 3), (0x8, 52, 54)],
}
# Tokens whose centre pixel is hidden under a shape cannot be read from the
# grid, so levels where that happens get an explicit list.
LEVEL_TOKENS = {
    6: [(8, (9, 9)), (8, (15, 3)), (8, (15, 36)), (9, (18, 57)),
        (9, (24, 39)), (8, (27, 9)), (0xb, (30, 45)), (0xb, (48, 39)),
        (0xb, (48, 51))],
    4: [(9, (6, 21)), (9, (6, 39)), (8, (27, 51)), (8, (33, 57)),
        (8, (36, 42)), (8, (42, 54)), (9, (45, 33)), (9, (51, 24)),
        (9, (51, 45)), (9, (60, 33))],
}
# Level 5: shapes are made of independent straight SEGMENTS. A move
# translates each segment unless its destination overlaps the blocker blob,
# in which case that segment stays put (confirmed for the 9-cross; the
# b-rectangle instead reshapes, so its route must avoid the blob).
# level -> [(colour, anchor, [(orient, fixed, start, length), ...]), ...]
LEVEL_SEGMENTS = {
    5: [(0xb, (41, 23), [("h", 27, 18, 10), ("h", 54, 18, 10),
                         ("v", 18, 27, 28), ("v", 27, 27, 28)]),
        (9, (15, 24), [("h", 15, 12, 25), ("v", 27, 3, 25)])],
    6: [(9, (21, 48), [("h", 18, 39, 19), ("h", 24, 39, 19),
                        ("v", 39, 18, 7), ("v", 57, 18, 7)]),
        (7, (45, 42), [("h", 42, 24, 37), ("v", 30, 36, 19)]),
        (0xb, (39, 45), [("h", 48, 36, 19), ("v", 45, 30, 19)])],
}
# 5x5 palette boxes on level 6 (top-left corners), colour -> corner
LEVEL_SW5 = {
    6: [(9, 2, 15), (0xb, 2, 25), (8, 2, 35), (0xe, 2, 45), (6, 2, 55)],
}
DRAW_SEQ = {5: [1, 0], 6: [0, 1, 2]}    # render order (later on top) for segment levels
BLOCKER = {5: {(r, c) for r in range(28, 36) for c in range(28, 36)},
           6: {(r, c) for r in range(28, 36) for c in range(28, 36)}}


def seg_cells(seg):
    o, f, s0, n = seg
    if o == "h":
        return {(f, s0 + i) for i in range(n)}
    return {(s0 + i, f) for i in range(n)}


def seg_move(seg, dr, dc):
    o, f, s0, n = seg
    return (o, f + (dr if o == "h" else dc), s0 + (dc if o == "h" else dr), n)


# Static decorations that are neither tokens nor shapes.
LEVEL_STATIC = {
    6: [(1, [(r, c) for r in range(28, 36) for c in range(28, 36)
             if abs(r * 2 - 63) + abs(c * 2 - 63) > 7])],
    5: [(1, [(r, c) for r in range(28, 36) for c in range(28, 36)
             if abs(r * 2 - 63) + abs(c * 2 - 63) > 7])],
}
SWATCH_BORDER = 2   # 6x6 palette boxes: ring of 2 around a 4x4 colour patch


def find_swatches(grid):
    """[(colour, r0, c0)] for each 6x6 palette box (top-left corner r0,c0)."""
    out = []
    for r in range(H - 5):
        for c in range(W - 5):
            ring = [grid[r][c + k] for k in range(6)] + \
                   [grid[r + 5][c + k] for k in range(6)] + \
                   [grid[r + k][c] for k in range(1, 5)] + \
                   [grid[r + k][c + 5] for k in range(1, 5)]
            if any(v != SWATCH_BORDER for v in ring):
                continue
            inner = {grid[r + a][c + b] for a in range(1, 5) for b in range(1, 5)}
            if len(inner) == 1:
                out.append((inner.pop(), r, c))
    return out


def swatch_cells(sw):
    _, r0, c0 = sw
    return {(r0 + a, c0 + b) for a in range(6) for b in range(6)}


def cells_at(offs, center):
    r0, c0 = center
    return [(r0 + dr, c0 + dc) for dr, dc in offs
            if 0 <= r0 + dr < H and 0 <= c0 + dc < W]


def fit_shape(cells):
    """Infer (kind, centre, R) from the visible cells of one colour."""
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    d1 = [r - c for r, c in cells]
    d2 = [r + c for r, c in cells]
    cr = max(set(rows), key=rows.count)
    cc = max(set(cols), key=cols.count)
    if all(r == cr or c == cc for r, c in cells):
        R = max(max(abs(r - cr) for r, _ in cells),
                max(abs(c - cc) for _, c in cells))
        return "plus", (cr, cc), R
    k1 = max(set(d1), key=d1.count)
    k2 = max(set(d2), key=d2.count)
    if (k1 + k2) % 2 == 0 and all(r - c == k1 or r + c == k2 for r, c in cells):
        center = ((k1 + k2) // 2, (k2 - k1) // 2)
        R = max(abs(r - center[0]) for r, _ in cells)
        return "X", center, R
    s = (max(d2) + min(d2)) // 2
    t = (max(d1) + min(d1)) // 2
    center = ((s + t) // 2, (s - t) // 2)
    R = (max(d2) - min(d2)) // 2
    if all(abs(r - center[0]) + abs(c - center[1]) == R for r, c in cells):
        return "diamond", center, R
    raise ValueError("unrecognised shape: %r" % (sorted(cells)[:8],))


# --- parsing --------------------------------------------------------------

def _colors(grid):
    seen = set()
    for r in range(H):
        seen.update(grid[r])
    return sorted(seen - NONSHAPE)


def _has_neighbour(grid, p, col):
    r, c = p
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if (dr, dc) == (0, 0):
                continue
            a, b = r + dr, c + dc
            if 0 <= a < H and 0 <= b < W and grid[a][b] == col:
                return True
    return False


def _locate(grid, offs, anchor, wild=()):
    """[(centre, colour)] where the shape sits on one uniform shape colour.

    Cells in `wild` (claimed by a shape drawn on top) are ignored.
    """
    out = []
    for r in range(anchor[0] % 3, H, 3):
        for c in range(anchor[1] % 3, W, 3):
            pts = [p for p in cells_at(offs, (r, c)) if p not in wild]
            if len(pts) * 2 < len(offs):
                continue
            vals = {grid[a][b] for a, b in pts} - {0}
            if len(vals) == 1:
                v = vals.pop()
                if v not in NONSHAPE:
                    out.append(((r, c), v))
    return out


def _find_tokens(grid, shapes):
    occ = set()
    for sh in shapes:
        occ.update(cells_at(sh["offsets"], sh["center"]))
    out = []
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            nb = [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                  if (dr, dc) != (0, 0)]
            if not all(grid[a][b] == 4 or (a, b) in occ for a, b in nb):
                continue
            if sum(1 for a, b in nb if grid[a][b] == 4) < 5:
                continue
            v = grid[r][c]
            if v not in NONSHAPE:
                out.append((v, (r, c)))
    return out


def init_state(entry_grid, level=None):
    if level is None:
        level = CURRENT_LEVEL
    zeros = [(r, c) for r in range(H) for c in range(W) if entry_grid[r][c] == 0]
    shapes = []
    if level in LEVEL_SEGMENTS:
        return _init_segments(entry_grid, level)
    swatches = LEVEL_SWATCHES.get(level) or find_swatches(entry_grid)
    swcells = set()
    for sw in swatches:
        swcells |= swatch_cells(sw)
    if level in LEVEL_SHAPES:
        wild = set()
        for kind, R, anchor in reversed(LEVEL_SHAPES[level]):   # top-most first
            offs = offsets(kind, R)
            spots = _locate(entry_grid, offs, anchor, wild)
            spots.sort(key=lambda p: abs(p[0][0] - anchor[0])
                       + abs(p[0][1] - anchor[1]))
            (ctr, col) = spots[0]
            shapes.append({"color": col, "center": ctr, "offsets": offs})
            wild |= set(cells_at(offs, ctr))
        shapes.reverse()
    else:
        cols = [c for c in _colors(entry_grid) if c != SWATCH_BORDER]
        cols.sort(key=lambda c: DRAW_ORDER.index(c) if c in DRAW_ORDER else 99)
        for col in cols:
            pts = [(r, c) for r in range(H) for c in range(W)
                   if entry_grid[r][c] == col and (r, c) not in swcells]
            keep = [p for p in pts if _has_neighbour(entry_grid, p, col)]
            kind, center, R = fit_shape(keep or pts)
            shapes.append({"color": col, "center": center,
                           "offsets": offsets(kind, R)})
    tokens = LEVEL_TOKENS.get(level) or _find_tokens(entry_grid, shapes)
    active = 0
    if zeros:
        for i, sh in enumerate(shapes):
            if sh["center"] == zeros[0]:
                active = i
    return {"shapes": shapes, "tokens": tokens, "active": active,
            "swatches": swatches, "static": LEVEL_STATIC.get(level, []),
            "level": level,
            "n": _n_from_bar(sum(1 for v in entry_grid[BAR_ROW] if v == 1), level)}


def _init_segments(grid, level):
    """State for a level whose shapes are independent segments.

    The segment table is anchored to the level's entry layout; the live
    positions are recovered by matching each shape's colour cells.
    """
    shapes = []
    for col, anchor, segs in LEVEL_SEGMENTS[level]:
        shapes.append({"color": col, "anchor": anchor, "segs": list(segs)})
    tokens = LEVEL_TOKENS.get(level) or _find_tokens(grid, [])
    sw5 = LEVEL_SW5.get(level, [])
    zeros = [(r, c) for r in range(H) for c in range(W) if grid[r][c] == 0]
    active = 0
    for i, sh in enumerate(shapes):
        if zeros and anchor_of(sh) == zeros[0]:
            active = i
    return {"segments": True, "shapes": shapes, "tokens": tokens,
            "active": active, "static": LEVEL_STATIC.get(level, []),
            "sw5": sw5, "swatches": [], "level": level,
            "n": _n_from_bar(sum(1 for v in grid[BAR_ROW] if v == 1), level)}


def sw5_cells(sw, inner=False):
    _, r0, c0 = sw
    a, b = (1, 4) if inner else (0, 5)
    return {(r0 + i, c0 + j) for i in range(a, b) for j in range(a, b)}


def anchor_of(sh):
    """The 0 marker sits at (centre row of a vertical bar, centre col of a
    horizontal bar) -- it does not follow a bar that got blocked."""
    r = c = None
    for (o, f, s0, n) in sh["segs"]:
        if o == "v" and r is None:
            r = s0 + (n - 1) // 2
        if o == "h" and c is None:
            c = s0 + (n - 1) // 2
    if r is None or c is None:
        return sh.get("anchor", (0, 0))
    return (r, c)


def render_segments(state):
    g = [[BG] * W for _ in range(H)]
    for sw in state.get("sw5", ()):
        col, r0, c0 = sw
        for (r, c) in sw5_cells(sw):
            g[r][c] = SWATCH_BORDER
        for (r, c) in sw5_cells(sw, True):
            g[r][c] = col
    for col, pts in state.get("static", ()):
        for (r, c) in pts:
            g[r][c] = col
    for col, (r, c) in state["tokens"]:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if 0 <= r + dr < H and 0 <= c + dc < W:
                    g[r + dr][c + dc] = 4
        g[r][c] = col
    for i in DRAW_SEQ.get(state.get("level"), range(len(state["shapes"]))):
        sh = state["shapes"][i]
        for seg in sh["segs"]:
            for (r, c) in seg_cells(seg):
                if 0 <= r < H and 0 <= c < W:
                    g[r][c] = sh["color"]
        if i == state["active"]:
            r0, c0 = anchor_of(sh)
            if 0 <= r0 < H and 0 <= c0 < W:
                g[r0][c0] = 0
    bar = [15] * W
    for i in range(bar_cells(state["n"], state.get("level", 0))):
        bar[W - 1 - i] = 1
    g.append(bar)
    return g


def covered_segments(state):
    reach = {}
    for sh in state["shapes"]:
        for seg in sh["segs"]:
            reach.setdefault(sh["color"], set()).update(seg_cells(seg))
    for col, (r, c) in state["tokens"]:
        cells = reach.get(col, ())
        if not any((r + a, c + b) in cells
                   for a in (-1, 0, 1) for b in (-1, 0, 1)):
            return False
    return True


def predict_segments(state, action, level):
    s = {"segments": True,
         "shapes": [{"color": sh["color"], "anchor": sh["anchor"],
                     "segs": list(sh["segs"])} for sh in state["shapes"]],
         "tokens": list(state["tokens"]), "active": state["active"],
         "static": state.get("static", []), "swatches": [],
         "sw5": state.get("sw5", []),
         "level": level, "n": state["n"]}
    info = {}
    if action in DIRS or action == 5:
        s["n"] += 1
    if action == 5:
        s["active"] = (s["active"] + 1) % len(s["shapes"])
    elif action in DIRS:
        dr, dc = DIRS[action]
        dr, dc = dr * STEP, dc * STEP
        sh = s["shapes"][s["active"]]
        block = BLOCKER.get(level, set())
        new = []
        for seg in sh["segs"]:
            moved = seg_move(seg, dr, dc)
            new.append(seg if seg_cells(moved) & block else moved)
        if len(new) == 2:
            a_, b_ = seg_cells(new[0]), seg_cells(new[1])
            if not (a_ & b_):        # a cross may not be torn apart
                return render_segments(state), info, state
        sh["segs"] = new
        pts = set()
        for seg in new:
            pts |= seg_cells(seg)
        hit = [sw for sw in s.get("sw5", ()) if pts & sw5_cells(sw)]
        if hit:
            hit.sort(key=lambda sw: (sw[1], sw[2]))
            sh["color"] = hit[0][0]
        if covered_segments(s):
            info["level_up"] = True
    return render_segments(s), info, s


# --- rendering ------------------------------------------------------------

def render(state):
    g = [[BG] * W for _ in range(H)]
    for (col, r0, c0) in state.get("swatches", ()):
        for a in range(6):
            for b in range(6):
                g[r0 + a][c0 + b] = SWATCH_BORDER
        for a in range(1, 5):
            for b in range(1, 5):
                g[r0 + a][c0 + b] = col
    for col, pts in state.get("static", ()):
        for (r, c) in pts:
            g[r][c] = col
    for col, (r, c) in state["tokens"]:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                g[r + dr][c + dc] = 4
        g[r][c] = col
    for i, sh in enumerate(state["shapes"]):
        for (r, c) in cells_at(sh["offsets"], sh["center"]):
            g[r][c] = sh["color"]
        if i == state["active"]:
            r0, c0 = sh["center"]
            if 0 <= r0 < H and 0 <= c0 < W:
                g[r0][c0] = 0
    bar = [15] * W
    for i in range(bar_cells(state["n"], state.get("level", 0))):
        bar[W - 1 - i] = 1
    g.append(bar)
    return g


def covered(state):
    reach = {}
    for sh in state["shapes"]:
        reach.setdefault(sh["color"], set()).update(
            cells_at(sh["offsets"], sh["center"]))
    for col, (r, c) in state["tokens"]:
        cells = reach.get(col, ())
        if not any((r + a, c + b) in cells
                   for a in (-1, 0, 1) for b in (-1, 0, 1)):
            return False
    return True


def predict(state, grid, action, x=None, y=None, level=None, entry_grid=None):
    if state.get("segments"):
        return predict_segments(state, action,
                                CURRENT_LEVEL if level is None else level)
    s = {"shapes": [dict(sh) for sh in state["shapes"]],
         "tokens": list(state["tokens"]),
         "swatches": list(state.get("swatches", ())),
         "static": state.get("static", []),
         "active": state["active"], "n": state["n"],
         "level": state.get("level", CURRENT_LEVEL)}
    info = {}
    if action in DIRS or action == 5:
        s["n"] += 1
    if action == 5:
        s["active"] = (s["active"] + 1) % len(s["shapes"])
    elif action in DIRS:
        dr, dc = DIRS[action]
        sh = s["shapes"][s["active"]]
        r0, c0 = sh["center"]
        sh["center"] = (r0 + dr * STEP, c0 + dc * STEP)
        # walking a palette swatch repaints the shape in that colour
        pts = set(cells_at(sh["offsets"], sh["center"]))
        hit = [sw for sw in s["swatches"] if pts & swatch_cells(sw)]
        if hit:   # ties resolved in reading order (level 4, transition 151)
            hit.sort(key=lambda sw: (sw[1], sw[2]))
            sh["color"] = hit[0][0]
        if covered(s):
            info["level_up"] = True
    return render(s), info, s
