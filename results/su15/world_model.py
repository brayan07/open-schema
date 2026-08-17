"""su15 world model.

Mechanics inferred from play:

* Rows 0-9 are an inert display band (clicks there change nothing, not even
  the meter).  Rows 10-62 are the playfield.  Row 63 is a black(0) meter that
  loses 2 cells from the right on EVERY playfield click.
* The playfield holds square monochrome "pieces".  Piece of side n has a
  colour taken from a sequence shown in the top-left legend panel
  (side 1 -> 10, 2 -> 6, 3 -> 15, 4 -> 11, ...).
* A piece's ANCHOR is topleft + (n//2, n//2).
* Clicking cell P=(y,x) inside the playfield teleports every piece whose
  anchor is within reach (Chebyshev <= 7 and radius <= ~8.5) of P so that its anchor lands on P.
  If two pieces of the same side n end up there they merge into one piece of
  side n+1 (next colour in the sequence), anchored at P.
* The maroon(9) disc is the goal.  Delivering a piece whose side equals the
  side of the piece displayed in the top band, anchored on the disc centre,
  completes the level.
"""

BAND_ROWS = 10          # rows 0..9 inert band
METER_ROW = 63
BG = 5
DISC = 9
SEQ_DEFAULT = [10, 6, 15, 11, 7, 8, 2, 1, 14, 12]

HAZARD = 7              # a shape that chases the nearest piece, <=4 per axis
HAZ_SPEED = 4
KNOCK = 10              # cells a shrunken piece is thrown on contact


# the hazard sprite, a 4x5 diamond outline
HAZ_SHAPE = [(0, 2), (1, 1), (1, 3), (2, 0), (2, 4), (3, 1), (3, 2), (3, 3)]

# rank (legend position, 1-based) -> drawn side length
SIDE_OF_RANK = [1, 1, 2, 3, 4, 5, 7, 10, 14]


def _side_of_rank(r):
    return SIDE_OF_RANK[r] if r < len(SIDE_OF_RANK) else 0


def _rank_of_side(side):
    for i in range(1, len(SIDE_OF_RANK)):
        if SIDE_OF_RANK[i] == side:
            return i
    return 0


def _hazard(grid):
    return [(r, c) for r in range(BAND_ROWS, METER_ROW)
            for c in range(64) if grid[r][c] == HAZARD]


def _hazard_shapes(grid, colours):
    """Full sprites, recovered even where a piece is drawn over part of one."""
    seen = set(_hazard(grid))
    todo = set(seen)
    out = []
    while todo:
        best = None
        for (r, c) in sorted(todo):
            for (dr, dc) in HAZ_SHAPE:
                r0, c0 = r - dr, c - dc
                cells = [(r0 + a, c0 + b) for (a, b) in HAZ_SHAPE]
                ok = True
                for (rr, cc) in cells:
                    if not (BAND_ROWS <= rr < METER_ROW and 0 <= cc < 64):
                        ok = False
                    elif (rr, cc) not in seen and grid[rr][cc] == BG:
                        ok = False
                if not ok:
                    continue
                n = sum(1 for x in cells if x in todo)
                if best is None or n > best[0]:
                    best = (n, cells)
        if best is None:
            break
        for x in best[1]:
            todo.discard(x)
        out.append(best[1])
    return out


# Cells eaten off row 63 after k playfield clicks, per level.
def _gone(level, k):
    if level == 2:
        return (4 * k + 4) // 3
    if level in (3, 7):
        return (4 * k) // 3
    return 2 * k


# A click gathers a piece iff the click cell is within radius 8 of the
# piece's NEAREST cell (squared edge distance <= 64).  One uniform radius
# fits every observed move (max edge^2 = 61) and non-move (min edge^2 = 65).
REACH2 = 64


def _copy(g):
    return [row[:] for row in g]


def _legend_seq(entry):
    """Colours of the 2x2 swatches in the top-left panel, left to right."""
    seen = []
    for c in range(0, 64):
        for r in (1, 2):
            v = entry[r][c]
            if v not in (4, BG) and v not in seen:
                seen.append(v)
    return seen if len(seen) >= 2 else list(SEQ_DEFAULT)


def _seq(entry):
    """Piece colours, in side order.  Only the legend counts: other colours
    in the playfield (e.g. the level-3 triangle) are scenery, not pieces."""
    s = _legend_seq(entry)
    if len(s) < 2:
        return list(SEQ_DEFAULT)
    return s


def _components(cells):
    """Split a cell set into 4-connected components."""
    todo = set(cells)
    out = []
    while todo:
        seed = sorted(todo)[0]
        comp = [seed]
        todo.discard(seed)
        i = 0
        while i < len(comp):
            r, c = comp[i]
            i += 1
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if n in todo:
                    todo.discard(n)
                    comp.append(n)
        out.append(comp)
    return out


def _components8(cells):
    """8-connected components (the hazard sprite is a diagonal outline)."""
    todo = set(cells)
    out = []
    while todo:
        seed = sorted(todo)[0]
        comp = [seed]
        todo.discard(seed)
        i = 0
        while i < len(comp):
            r, c = comp[i]
            i += 1
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in todo:
                        todo.discard(n)
                        comp.append(n)
        out.append(comp)
    return out


def _band_targets(entry):
    """Sides of the goal pieces: filled squares of a legend colour drawn in
    the band right of the panel (icons like the hazard sprite are outlines
    in non-legend colours, so they are skipped)."""
    colours = set(_seq(entry))
    cells = [(r, c) for r in range(0, BAND_ROWS) for c in range(24, 64)
             if entry[r][c] in colours]
    sides = []
    for comp in _components(cells):
        rs = [p[0] for p in comp]
        cs = [p[1] for p in comp]
        h = max(rs) - min(rs) + 1
        w = max(cs) - min(cs) + 1
        if h == w and len(comp) == h * w:
            sides.append(h)
    return sorted(sides)


def _disc_centres(entry):
    cells = [(r, c) for r in range(BAND_ROWS, METER_ROW)
             for c in range(64) if entry[r][c] == DISC]
    out = []
    for comp in _components(cells):
        rs = [p[0] for p in comp]
        cs = [p[1] for p in comp]
        out.append(((min(rs) + max(rs)) // 2, (min(cs) + max(cs)) // 2))
    return out


def _pieces(grid, colours):
    """Square pieces in the playfield -> list of (side, colour, r0, c0)."""
    out = []
    seen = set()
    for r in range(BAND_ROWS, METER_ROW):
        for c in range(64):
            v = grid[r][c]
            if v not in colours or (r, c) in seen:
                continue
            # flood a rectangle of this colour
            r1 = r
            while r1 + 1 < METER_ROW and grid[r1 + 1][c] == v:
                r1 += 1
            c1 = c
            while c1 + 1 < 64 and grid[r][c1 + 1] == v:
                c1 += 1
            for rr in range(r, r1 + 1):
                for cc in range(c, c1 + 1):
                    seen.add((rr, cc))
            out.append((r1 - r + 1, v, r, c))
    return out


def _anchor(p):
    side, _col, r0, c0 = p
    return (r0 + side // 2, c0 + side // 2)


def _edge2(piece, y, x):
    """squared distance from (y,x) to the nearest cell of the piece"""
    side, _col, r0, c0 = piece
    dr = 0
    if y < r0:
        dr = r0 - y
    elif y > r0 + side - 1:
        dr = y - (r0 + side - 1)
    dc = 0
    if x < c0:
        dc = c0 - x
    elif x > c0 + side - 1:
        dc = x - (c0 + side - 1)
    return dr * dr + dc * dc


def _in_reach(piece, y, x):
    return _edge2(piece, y, x) <= REACH2


def _background(entry, colours):
    """Entry grid with pieces and one-shot hint markers stripped out."""
    bg = _copy(entry)
    for (r, c) in _hazard(entry):
        bg[r][c] = BG
    for side, _col, r0, c0 in _pieces(entry, colours):
        for r in range(r0, r0 + side):
            for c in range(c0, c0 + side):
                bg[r][c] = BG
    return bg


def _plus(entry):
    """The one-shot black hint marker: (cells, centre) or (None, None)."""
    cells = [(r, c) for r in range(BAND_ROWS, METER_ROW)
             for c in range(64) if entry[r][c] == 0]
    if not cells:
        return None, None
    st = set(cells)
    centre = None
    for (r, c) in cells:
        nb = sum(1 for (dr, dc) in ((1, 0), (-1, 0), (0, 1), (0, -1))
                 if (r + dr, c + dc) in st)
        if nb == 4:
            centre = (r, c)
    return cells, centre


# ---------------------------------------------------------------- contract

def init_state(entry_grid, level=None):
    colours = _seq(entry_grid)
    cells, centre = _plus(entry_grid)
    return {
        "seq": colours,
        "plus": cells,
        "plus_centre": centre,
        "bg": _background(entry_grid, set(colours)),
        "targets": _band_targets(entry_grid),
        "discs": _disc_centres(entry_grid),
    }


def predict(state, grid, action, x=None, y=None, level=None, entry_grid=None):
    if state is None or (entry_grid is not None
                         and state.get("bg") is None):
        state = init_state(entry_grid, level)
    flags = {"level_up": False, "dead": False, "win": False}
    colours = set(state["seq"])

    if action != 6 or x is None or y is None:
        return _copy(grid), flags, state
    if y < BAND_ROWS or y >= METER_ROW:
        return _copy(grid), flags, state

    out = _copy(state["bg"])
    # Row 63 is a budget bar that shrinks from the right.  Every playfield
    # click costs 2 cells, except that from level 2 on a click that actually
    # fuses two pieces costs only 1.  (Levels 0-1 charged 2 for everything.)
    pieces = _pieces(grid, colours)
    movers = [p for p in pieces if _in_reach(p, y, x)]
    stay = [p for p in pieces if p not in movers]

    # A click is only accepted if the pieces it gathers can fuse into a
    # single piece: one piece, or exactly two of equal side.  A mixed-size
    # (or ambiguous) gather is rejected outright and nothing moves.
    sides = sorted(p[0] for p in movers)
    if len(sides) == 2 and sides[0] == sides[1]:
        sides = [_side_of_rank(_rank_of_side(sides[0]) + 1)]
        movers_merge = True
    else:
        movers_merge = False
    if len(sides) > 2 or (len(sides) == 2 and sides[0] != sides[1]):
        lv = CURRENT_LEVEL if level is None else level
        have = sum(1 for c in range(64) if grid[METER_ROW][c] == 0)
        k = 0
        for j in range(0, 400):
            if 64 - _gone(lv, j) == have:
                k = j
                break
        left = 64 - _gone(lv, k + 1)
        out[METER_ROW] = [0] * max(0, left) + [BG] * (64 - max(0, left))
        for side, col, r0, c0 in pieces:
            for r in range(r0, r0 + side):
                for c in range(c0, c0 + side):
                    out[r][c] = col
        return out, flags, state

    merged = list(sides)
    landed = []
    for side in merged:
        rank = _rank_of_side(side)
        col = state["seq"][rank - 1] if 0 < rank <= len(state["seq"]) else 0
        landed.append((side, col, y - side // 2, x - side // 2))

    # the hint marker is consumed the moment a piece lands on it
    if state.get("plus_centre") is not None:
        for side, _col, r0, c0 in landed:
            if (r0 + side // 2, c0 + side // 2) == state["plus_centre"]:
                for (r, c) in state["plus"]:
                    state["bg"][r][c] = (3 if (r, c) == state["plus_centre"]
                                         else BG)
                    out[r][c] = state["bg"][r][c]
                state["plus"] = None
                state["plus_centre"] = None
                break

    newhaz = []
    hazdir = {}
    for haz in _hazard_shapes(grid, colours):
        hr = (min(p[0] for p in haz) + max(p[0] for p in haz) + 1) // 2
        hc = (min(p[1] for p in haz) + max(p[1] for p in haz) + 1) // 2
        best = None
        for side, _c, r0, c0 in stay + landed:
            pr = r0 + side // 2
            pc = c0 + side // 2
            d = (pr - hr) ** 2 + (pc - hc) ** 2
            if best is None or d < best[0]:
                best = (d, pr, pc)
        dr = dc = 0
        if best is not None:
            dr = max(-HAZ_SPEED, min(HAZ_SPEED, best[1] - hr))
            dc = max(-HAZ_SPEED, min(HAZ_SPEED, best[2] - hc))
        d = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
        for (r, c) in haz:
            nr, nc = r + dr, c + dc
            if BAND_ROWS <= nr < METER_ROW and 0 <= nc < 64:
                newhaz.append((nr, nc))
                hazdir[(nr, nc)] = d
    hset = set(newhaz)
    for (r, c) in newhaz:
        out[r][c] = HAZARD
    # A hazard landing on a piece SHRINKS it one size and knocks it 10 cells
    # along the hazard's direction of travel (clamped to the playfield).
    # Side 1 is destroyed outright.
    survivors = list(landed)          # a piece that moved this click is immune
    for pc in stay:
        side, _c, r0, c0 = pc
        hit = None
        for r in range(r0, r0 + side):
            for c in range(c0, c0 + side):
                if (r, c) in hset:
                    hit = hazdir[(r, c)]
        if hit is None:
            survivors.append(pc)
            continue
        ns = _side_of_rank(_rank_of_side(side) - 1)
        if ns == 0:
            continue
        nr = r0 + (KNOCK * hit[0])
        nc = c0 + (KNOCK * hit[1])
        nr = max(BAND_ROWS, min(METER_ROW - ns, nr))
        nc = max(0, min(64 - ns, nc))
        nrk = _rank_of_side(ns)
        col = state["seq"][nrk - 1] if 0 < nrk <= len(state["seq"]) else 0
        survivors.append((ns, col, nr, nc))

    for side, col, r0, c0 in survivors:
        for r in range(r0, r0 + side):
            for c in range(c0, c0 + side):
                if 0 <= r < 64 and 0 <= c < 64:
                    out[r][c] = col

    lv = CURRENT_LEVEL if level is None else level
    have = sum(1 for c in range(64) if grid[METER_ROW][c] == 0)
    k = 0
    for j in range(0, 400):
        if 64 - _gone(lv, j) == have:
            k = j
            break
    left = 64 - _gone(lv, k + 1)
    if left < 0:
        left = 0
    out[METER_ROW] = [0] * left + [BG] * (64 - left)

    # a level is done when every goal piece in the band sits on a disc
    on_disc = sorted(side for side, _c, r0, c0 in survivors
                     if (r0 + side // 2, c0 + side // 2) in state["discs"])
    if on_disc and on_disc == state["targets"]:
        flags["level_up"] = True
    return out, flags, state
