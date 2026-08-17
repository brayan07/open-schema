# World model for ka59 (levels 0-2).
#
# LATTICE   3x3-px cells with a per-level offset: cell(r,c) covers px rows
#   OY+3r..OY+3r+2, cols OX+3c..OX+3c+2.  OY/OX = (min piece px row/col) % 3.
#
# TILES     1 floor, 15 wall, 2 void.  A cell is floor iff no px in it is 15/2.
#
# PIECES    Two renderings:
#   * bordered (levels 0,1): an h x w cell rect painted 14, with a central
#     h x w px "core" carrying the colour.
#   * solid (levels 2-4): the piece's cells painted with an arbitrary fill
#     pattern (level 4 has two-tone 12/13 blocks); the pattern travels with it.
#   Colour 0 = the piece you control, 5 = never controlled, 4 = deselected.
#   Solid colour-11 pieces can only ever be LAUNCHED -- clicks on them do nothing.
#   A controlled bordered piece "opens": the border line facing an
#   orthogonally adjacent piece is drawn 0 instead of 14.
#
# GAUGES    Level 4 adds two-tone blocks (colours 12 "full" / 13 "empty").
#   Each is a cyclic counter that advances one px per MOVE action (clicks do
#   not tick them) and wraps.
#   Colour 12 piles up against one edge; the boundary travels away from that
#   edge, and THAT is the block's shove direction when the counter wraps.
#
# RINGS     a 1-px outline drawn one px outside a piece-shaped cell area.
#   The level advances when every piece sits exactly inside a ring.
#
# ACTIONS   1/2/3/4 = up/down/left/right move the controlled piece one cell.
#   Moving into another piece LAUNCHES it 5 cells that way, straight through
#   walls; if that lands illegally it keeps flying (6,7,...) to the first legal
#   spot, and only if none exists does it fall back to 4,3,2,1.  Pusher stays.  6 = click a piece to control it
#   (the old one turns 4).
#
# BAR       row 63 is a progress meter: rightmost K px are 0 with
#   K = round(64 * n / BUDGET[level]), n = actions taken this level (moves and
#   clicks count the same).  Budgets fitted from play: 100, 128, 100.
#   TRUE_N is kept by hand because `commit` re-inits from the live frame.

FLOOR, WALL, VOID, BORDER = 1, 15, 2, 14
BG = (FLOOR, WALL, VOID)   # never part of a piece; 4 IS a valid core colour
DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
BUDGET = {0: 100, 1: 128, 2: 100, 3: 128, 4: 100, 5: 150, 6: 200}
DEFAULT_BUDGET = 100
TRUE_N = 69
CURRENT_LEVEL = 0
def dirn_hint(r0, c0):
    """A gauge that reads all-13 is at 0 and its direction cannot be seen.
    Hints gathered from play, per level."""
    if CURRENT_LEVEL in (5, 6):
        return (-1, 0) if r0 >= 12 else (1, 0)
    if CURRENT_LEVEL == 4:
        return (0, -1) if r0 == 9 else (1, 0)
    return (1, 0)


# ---------------------------------------------------------------- lattice --
def offsets(grid):
    """Lattice phase, read off the pieces: piece px (anything that is not
    floor/wall/void/ring) always start exactly on a cell boundary.  The floor
    outline is NOT reliable for this (level 3's room edge is ragged)."""
    ys, xs = [], []
    for y in range(63):
        row = grid[y]
        for x in range(64):
            if row[x] not in (FLOOR, WALL, VOID, 4):
                ys.append(y)
                xs.append(x)
    return (min(ys) % 3, min(xs) % 3) if ys else (0, 0)


def make_geo(grid):
    oy, ox = offsets(grid)
    return {"oy": oy, "ox": ox, "nr": (63 - oy) // 3, "nc": (64 - ox) // 3}


def px(geo, r, c):
    return geo["oy"] + 3 * r, geo["ox"] + 3 * c


def cell_px_set(geo, cells):
    out = set()
    for (r, c) in cells:
        y0, x0 = px(geo, r, c)
        for y in range(y0, y0 + 3):
            for x in range(x0, x0 + 3):
                out.add((y, x))
    return out


def is_floor(grid, geo, r, c):
    if not (0 <= r < geo["nr"] and 0 <= c < geo["nc"]):
        return False
    y0, x0 = px(geo, r, c)
    for y in range(y0, y0 + 3):
        for x in range(x0, x0 + 3):
            if y > 62 or x > 63 or grid[y][x] in (WALL, VOID):
                return False
    return True


# ----------------------------------------------------------------- pieces --
def _cell_is_bordered(grid, geo, r, c):
    y0, x0 = px(geo, r, c)
    if y0 + 2 > 62 or x0 + 2 > 63:
        return False
    saw = False
    for y in range(y0, y0 + 3):
        for x in range(x0, x0 + 3):
            v = grid[y][x]
            if v == BORDER:
                saw = True
            elif v in BG:
                return False
    return saw


def _rect_ok(grid, geo, r, c, h, w):
    y0, x0 = px(geo, r, c)
    y1, x1 = y0 + 3 * h - 1, x0 + 3 * w - 1
    cy0, cy1, cx0, cx1 = y0 + h, y0 + 2 * h - 1, x0 + w, x0 + 2 * w - 1
    col = grid[cy0][cx0]
    if col in BG or col == BORDER:
        return None
    for y in range(cy0, cy1 + 1):
        for x in range(cx0, cx1 + 1):
            if grid[y][x] != col:
                return None
    for y in range(y0 + 1, y1):
        for x in range(x0 + 1, x1):
            if cy0 <= y <= cy1 and cx0 <= x <= cx1:
                continue
            if grid[y][x] != BORDER:
                return None
    return col


def find_pieces(grid, geo):
    pieces = []
    cells = set()
    for r in range(geo["nr"]):
        for c in range(geo["nc"]):
            if _cell_is_bordered(grid, geo, r, c):
                cells.add((r, c))
    while cells:
        r, c = min(cells)
        done = False
        for h in (1, 2, 3):
            for w in (1, 2, 3):
                rect = {(r + i, c + j) for i in range(h) for j in range(w)}
                if not rect <= cells:
                    continue
                col = _rect_ok(grid, geo, r, c, h, w)
                if col is None:
                    continue
                pieces.append({"cells": rect, "colour": col, "solid": False})
                cells -= rect
                done = True
                break
            if done:
                break
        if not done:
            cells.discard((r, c))

    used = set()
    for p in pieces:
        used |= p["cells"]
    rest = set()
    kls = {}
    for r in range(geo["nr"]):
        for c in range(geo["nc"]):
            if (r, c) in used:
                continue
            y0, x0 = px(geo, r, c)
            if y0 + 2 > 62 or x0 + 2 > 63:
                continue
            good = True
            for y in range(y0, y0 + 3):
                for x in range(x0, x0 + 3):
                    v = grid[y][x]
                    if v in BG or v == BORDER or v == 4:
                        good = False
            if good:
                vals = set()
                for y in range(y0, y0 + 3):
                    for x in range(x0, x0 + 3):
                        vals.add(grid[y][x])
                klass = "gauge" if vals <= {12, 13} else min(vals)
                rest.add((r, c))
                kls[(r, c)] = klass
    while rest:
        seed = min(rest)
        blob, stack = set(), [seed]
        rest.discard(seed)
        while stack:
            cur = stack.pop()
            blob.add(cur)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (cur[0] + d[0], cur[1] + d[1])
                if nb in rest and kls[nb] == kls[seed]:
                    rest.discard(nb)
                    stack.append(nb)
        r0 = min(b[0] for b in blob)
        c0 = min(b[1] for b in blob)
        y0, x0 = px(geo, r0, c0)
        pat = {}
        for (y, x) in cell_px_set(geo, blob):
            pat[(y - y0, x - x0)] = grid[y][x]
        cols = set(pat.values())
        piece = {"cells": blob, "colour": min(cols), "solid": True, "pat": pat}
        if cols <= {12, 13}:
            hh = (max(b[0] for b in blob) - r0 + 1) * 3
            ww = (max(b[1] for b in blob) - c0 + 1) * 3
            rowu = True
            colu = True
            for dy in range(hh):
                for dx in range(ww):
                    if pat[(dy, dx)] != pat[(dy, 0)]:
                        rowu = False
                    if pat[(dy, dx)] != pat[(0, dx)]:
                        colu = False
            mono = len(cols) == 1
            if mono:
                dirn = dirn_hint(r0, c0)
            elif rowu:
                dirn = (1, 0) if pat[(0, 0)] == 12 else (-1, 0)
            else:
                dirn = (0, -1) if pat[(0, ww - 1)] == 12 else (0, 1)
            piece["dirn"] = dirn
            piece["cap"] = hh if dirn[0] else ww
            if dirn == (1, 0):
                piece["gauge"] = sum(1 for dy in range(hh) if pat[(dy, 0)] == 12)
            elif dirn == (-1, 0):
                piece["gauge"] = sum(1 for dy in range(hh)
                                     if pat[(hh - 1 - dy, 0)] == 12)
            elif dirn == (0, -1):
                piece["gauge"] = sum(1 for dx in range(ww)
                                     if pat[(0, ww - 1 - dx)] == 12)
            else:
                piece["gauge"] = sum(1 for dx in range(ww) if pat[(0, dx)] == 12)
        pieces.append(piece)
    return pieces


# ------------------------------------------------------------------ rings --
def _outline(geo, cells):
    body = cell_px_set(geo, cells)
    out = set()
    for (y, x) in body:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                p = (y + dy, x + dx)
                if p not in body:
                    out.add(p)
    return out


def find_rings(grid, geo, pieces):
    covered = set()
    for p in pieces:
        covered |= cell_px_set(geo, p["cells"])
    shapes = []
    for p in pieces:
        r0 = min(c[0] for c in p["cells"])
        c0 = min(c[1] for c in p["cells"])
        sh = frozenset((r - r0, c - c0) for (r, c) in p["cells"])
        if sh not in shapes:
            shapes.append(sh)
    found = []
    for sh in shapes:
        hh = max(r for (r, _) in sh) + 1
        ww = max(c for (_, c) in sh) + 1
        for r in range(geo["nr"] - hh + 1):
            for c in range(geo["nc"] - ww + 1):
                cells = frozenset((r + i, c + j) for (i, j) in sh)
                o = _outline(geo, cells)
                bad = False
                hit = 0
                for (y, x) in o:
                    if not (0 <= y <= 62 and 0 <= x <= 63):
                        bad = True
                        break
                    if grid[y][x] == 4:
                        hit += 1
                    elif (y, x) not in covered:
                        bad = True
                        break
                if not bad and hit >= len(o) * 0.6:
                    found.append(cells)
    keep = []
    for a in found:
        inner = False
        for b in found:
            if a != b and a < b:
                inner = True
        if not inner:
            keep.append(a)
    return keep


# -------------------------------------------------------------------- bar --
def bar_k(n, level):
    b = BUDGET.get(level, DEFAULT_BUDGET)
    return min(64, (128 * n + b) // (2 * b))


def init_state(entry_grid, level=None):
    lvl = CURRENT_LEVEL
    k0 = sum(1 for v in entry_grid[63] if v == 0)
    if bar_k(TRUE_N, lvl) == k0:
        return {"n": TRUE_N}
    n = 0
    while bar_k(n, lvl) < k0 and n < 900:
        n += 1
    return {"n": n}


# ----------------------------------------------------------------- render --
def render(grid, geo, pieces, rings, k):
    g = [row[:] for row in grid]
    for r in range(geo["nr"]):
        for c in range(geo["nc"]):
            if is_floor(grid, geo, r, c):
                y0, x0 = px(geo, r, c)
                for y in range(y0, y0 + 3):
                    for x in range(x0, x0 + 3):
                        g[y][x] = FLOOR
    for cells in rings:
        for (y, x) in _outline(geo, cells):
            if 0 <= y <= 62 and 0 <= x <= 63:
                g[y][x] = 4
    for p in pieces:
        if p["solid"]:
            r0 = min(b[0] for b in p["cells"])
            c0 = min(b[1] for b in p["cells"])
            y0, x0 = px(geo, r0, c0)
            if p.get("gauge") is not None:
                hh = (max(b[0] for b in p["cells"]) - r0 + 1) * 3
                ww = (max(b[1] for b in p["cells"]) - c0 + 1) * 3
                gv = p["gauge"]
                for dy in range(hh):
                    for dx in range(ww):
                        dn = p["dirn"]
                        if dn == (1, 0):
                            v = 12 if dy < gv else 13
                        elif dn == (-1, 0):
                            v = 12 if dy >= hh - gv else 13
                        elif dn == (0, -1):
                            v = 12 if dx >= ww - gv else 13
                        else:
                            v = 12 if dx < gv else 13
                        g[y0 + dy][x0 + dx] = v
                continue
            pat = p.get("pat")
            if pat:
                for (dy, dx) in pat:
                    g[y0 + dy][x0 + dx] = pat[(dy, dx)]
            else:
                for (y, x) in cell_px_set(geo, p["cells"]):
                    g[y][x] = p["colour"]
        else:
            rs = [c[0] for c in p["cells"]]
            cs = [c[1] for c in p["cells"]]
            h, w = max(rs) - min(rs) + 1, max(cs) - min(cs) + 1
            y0, x0 = px(geo, min(rs), min(cs))
            for y in range(y0, y0 + 3 * h):
                for x in range(x0, x0 + 3 * w):
                    g[y][x] = BORDER
            for y in range(y0 + h, y0 + 2 * h):
                for x in range(x0 + w, x0 + 2 * w):
                    g[y][x] = p["colour"]
    ctrl = None
    for p in pieces:
        if p["colour"] == 0:
            ctrl = p
    if ctrl is not None and not ctrl["solid"]:
        rs = [c[0] for c in ctrl["cells"]]
        cs = [c[1] for c in ctrl["cells"]]
        y0, x0 = px(geo, min(rs), min(cs))
        y1 = y0 + 3 * (max(rs) - min(rs) + 1) - 1
        x1 = x0 + 3 * (max(cs) - min(cs) + 1) - 1
        for p in pieces:
            if p is ctrl:
                continue
            for d in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                touch = False
                for (r, c) in ctrl["cells"]:
                    if (r + d[0], c + d[1]) in p["cells"]:
                        touch = True
                if not touch:
                    continue
                if d == (0, 1):
                    for y in range(y0, y1 + 1):
                        g[y][x1] = 0
                elif d == (0, -1):
                    for y in range(y0, y1 + 1):
                        g[y][x0] = 0
                elif d == (1, 0):
                    for x in range(x0, x1 + 1):
                        g[y1][x] = 0
                else:
                    for x in range(x0, x1 + 1):
                        g[y0][x] = 0
    for i in range(64):
        g[63][i] = 0 if i >= 64 - k else 4
    return g


# ------------------------------------------------------------------ rules --
def _pulse(grid, geo, pieces, ticking):
    """Advance every gauge one px; a gauge that wraps makes its block shove
    a piece lying within 2*len cells ahead of its leading edge (along the
    direction its fill grows) get teleported so its near edge sits at
    edge + 2*len, flying further if that is blocked.  The player's own move
    resolves BEFORE this."""
    shoved = set()
    if not ticking:
        return shoved
    for p in pieces:
        if p.get("gauge") is None:
            continue
        p["gauge"] = (p["gauge"] + 1) % p["cap"]
        if p["gauge"] != 0:
            continue
        rs = [b[0] for b in p["cells"]]
        cs = [b[1] for b in p["cells"]]
        d = p["dirn"]
        if d[0] == 1:
            dist, edge = max(rs) - min(rs) + 1, max(rs)
        elif d[0] == -1:
            dist, edge = max(rs) - min(rs) + 1, min(rs)
        elif d[1] == -1:
            dist, edge = max(cs) - min(cs) + 1, min(cs)
        else:
            dist, edge = max(cs) - min(cs) + 1, max(cs)
        for i in range(len(pieces)):
            q = pieces[i]
            if q is p:
                continue
            if d[0]:
                if not (set(b[1] for b in q["cells"]) & set(cs)):
                    continue
                rows_in = [b[0] for b in q["cells"] if b[1] in cs]
                if d[0] == 1:
                    qe = min(b[0] for b in q["cells"])
                    if not [r for r in rows_in if edge < r <= edge + 2 * dist]:
                        continue
                else:
                    qe = max(b[0] for b in q["cells"])
                    if not [r for r in rows_in if edge - 2 * dist <= r < edge]:
                        continue
            else:
                if not (set(b[0] for b in q["cells"]) & set(rs)):
                    continue
                cols_in = [b[1] for b in q["cells"] if b[0] in rs]
                if d[1] == -1:
                    qe = max(b[1] for b in q["cells"])
                    if not [c for c in cols_in if edge - 2 * dist <= c < edge]:
                        continue
                else:
                    qe = min(b[1] for b in q["cells"])
                    if not [c for c in cols_in if edge < c <= edge + 2 * dist]:
                        continue
            sgn = d[0] + d[1]
            want = (edge + 2 * dist * sgn - qe) * sgn
            want = want if want >= 1 else 1
            for k in list(range(want, 26)) + list(range(want - 1, 0, -1)):
                nc = {(r + k * d[0], c + k * d[1]) for (r, c) in q["cells"]}
                ok = True
                for (r, c) in nc:
                    if not is_floor(grid, geo, r, c):
                        ok = False
                for o in pieces:
                    if o is not q and (o["cells"] & nc):
                        ok = False
                if ok:
                    q["cells"] = nc
                    shoved.add(i)
                    break
    return shoved


def predict(state, grid, action, x=None, y=None, level=None):
    geo = make_geo(grid)
    pieces = []
    for p in find_pieces(grid, geo):
        q = {"cells": set(p["cells"]), "colour": p["colour"],
             "solid": p["solid"], "pat": p.get("pat")}
        for key in ("gauge", "cap", "dirn"):
            if key in p:
                q[key] = p[key]
        pieces.append(q)
    rings = find_rings(grid, geo, pieces)
    ctrl = None
    for p in pieces:
        if p["colour"] == 0:
            ctrl = p

    if action in DIRS and ctrl is not None:
        dr, dc = DIRS[action]
        tgt = {(r + dr, c + dc) for (r, c) in ctrl["cells"]}
        hit = None
        for p in pieces:
            if p is not ctrl and (p["cells"] & tgt):
                hit = p
        if hit is not None:
            # thrown 5 cells (straight through walls); if that lands illegally
            # it keeps flying (6,7,...) to the first legal spot, and only if
            # none exists does it fall back to 4,3,2,1.
            for k in list(range(5, 26)) + [4, 3, 2, 1]:
                nc = {(r + k * dr, c + k * dc) for (r, c) in hit["cells"]}
                ok = True
                for (r, c) in nc:
                    if not is_floor(grid, geo, r, c):
                        ok = False
                for p in pieces:
                    if p is not hit and (p["cells"] & nc):
                        ok = False
                if ok:
                    hit["cells"] = nc
                    break
        else:
            ok = True
            for (r, c) in tgt:
                if not is_floor(grid, geo, r, c):
                    ok = False
            if ok:
                ctrl["cells"] = tgt
    elif action == 6 and ctrl is not None and y is not None:
        cell = ((y - geo["oy"]) // 3, (x - geo["ox"]) // 3)
        for p in pieces:
            # solid pieces cannot be taken control of -- clicking one is a
            # no-op (verified on level 2); only bordered pieces swap.
            if p is not ctrl and cell in p["cells"] and not p["solid"]:
                ctrl["colour"] = 4
                p["colour"] = 0

    _pulse(grid, geo, pieces, action in DIRS)

    n = state["n"] + 1
    # the level advances when every ring is exactly filled by a piece
    # (level 4's gauge blocks have no ring and do not need one).
    cellsets = [p["cells"] for p in pieces]
    done = len(rings) > 0
    for r in rings:
        if set(r) not in cellsets:
            done = False
    g = render(grid, geo, pieces, rings, bar_k(n, CURRENT_LEVEL))
    return g, {"level_up": done}, {"n": n}
