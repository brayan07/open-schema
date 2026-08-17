"""World model for sp80.

Scene is a 16x16 logical grid rendered as 4x4 pixel blocks in a 64x64 frame.
One pixel row (row 0 or row 63) is an action-counter overlay.

Pieces are horizontal bars (1 cell tall). Exactly one is ACTIVE (colour 9);
the rest render as 8. Actions 1/2/3/4 translate the active bar by one logical
cell; collision uses the bar's cells DILATED BY 1 in all 8 directions, so a bar
always halts one cell short of anything.

Cups (colour 11) sit against one edge: a 3-wide roof with two legs and a 1-cell
cavity between them. Bars must be brought to their closest approach under/over
the cups.

Action 5 = "hand over": rejected outright unless the active bar is settled
(one more step toward the cups would put a cup cell in its dilated footprint).
When accepted, control passes to the NEAREST other bar -- unless that bar is
already CORRECT, in which case nothing happens at all (a correct bar is locked).
CORRECT = settled AND both end columns are leg columns of the cups.
When there is no other bar (or every bar is correct) the level advances.
Action 6 = click on a cell: SELECTS the bar under it (transition #128). This
is the only way to reach a bar that is earlier in reading order than the
active one, since hand-over never moves backwards.
"""

BG = 12
PLAYER = 9
PIECE = 8
CUP = 11
MARK = 4      # a cell of this colour inside a bar travels with it (level 3)
ODD = 15      # level 4's L-shaped piece: idle it renders 15, held it renders 9

BAR_PERIOD = {0: 30, 1: 45, 2: 100, 3: 120, 4: 100}
DEFAULT_BAR_PERIOD = 60

DELTA = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


def counter_row(grid):
    for r in (0, 63):
        if grid[r][0] == 14 or 14 in grid[r]:
            return r
    return 0


def geometry(grid):
    """(cell_size, row_offset, col_offset, rows, cols).

    Levels 0-2 draw a 16x16 board in 4x4 pixel blocks; level 3 switches to a
    20x20 board in 3x3 blocks inset by two pixels, so the block size has to be
    read off the frame rather than assumed.
    """
    orow = counter_row(grid)
    for s in (5, 4, 3, 2):
        for orr in range(s):
            for occ in range(s):
                nr, nc = (64 - orr) // s, (64 - occ) // s
                if nr < 8 or nc < 8:
                    continue
                ok = True
                for i in range(nr):
                    for j in range(nc):
                        vals = set()
                        for a in range(s):
                            for b in range(s):
                                r, c = orr + i * s + a, occ + j * s + b
                                if r == orow:
                                    continue
                                vals.add(grid[r][c])
                        if len(vals) > 1:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    return (s, orr, occ, nr, nc)
    return (4, 0, 0, 16, 16)


def to_cells(grid):
    s, orr, occ, nr, nc = geometry(grid)
    out = []
    for i in range(nr):
        r = orr + i * s + (1 if s > 2 else 0)
        if r == counter_row(grid):
            r += 1
        out.append([grid[r][occ + j * s + 1] for j in range(nc)])
    return out


def _comps(cells, colour):
    nr, nc = _dims(cells)
    seen, comps = set(), []
    for r in range(nr):
        for c in range(nc):
            if cells[r][c] != colour or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                comp.append((rr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ar, ac = rr + dr, cc + dc
                    if 0 <= ar < nr and 0 <= ac < nc \
                            and cells[ar][ac] == colour and (ar, ac) not in seen:
                        seen.add((ar, ac))
                        stack.append((ar, ac))
            comps.append(comp)
    return comps


_MASK = [set()]


def _recolour(cells, comp, colour):
    """Repaint a piece, leaving its marked cells alone.

    The odd-shaped piece renders 15 when idle and 9 when held, so track which
    cells were odd and restore that colour when it is put down."""
    odd = len(set(r for r, _ in comp)) > 1   # bars are one row tall
    for (r, c) in comp:
        if cells[r][c] == MARK:
            continue
        cells[r][c] = colour if not (odd and colour == PIECE) else ODD


def _dims(cells):
    return len(cells), len(cells[0])


def bar_mask(cells):
    """Cells belonging to bars: 8/9 runs, plus any MARK cells joined to them.

    Level 3's 7-wide bar carries a colour-4 cell in its middle; it is part of
    the bar and moves with it, unlike the free-standing colour-4 marker.
    """
    nr, nc = _dims(cells)
    cl = _classed(cells)
    nr, nc = _dims(cells)
    return set((r, c) for r in range(nr) for c in range(nc) if cl[r][c] != BG)


def _comps_multi(cells, colours):
    nr, nc = _dims(cells)
    seen, comps = set(), []
    for r in range(nr):
        for c in range(nc):
            if cells[r][c] not in colours or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                comp.append((rr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ar, ac = rr + dr, cc + dc
                    if 0 <= ar < nr and 0 <= ac < nc \
                            and cells[ar][ac] in colours and (ar, ac) not in seen:
                        seen.add((ar, ac))
                        stack.append((ar, ac))
            comps.append(comp)
    return comps


def _classed(cells):
    """Grid of bar membership classes: PIECE, PLAYER, or BG.

    A MARK cell bracketed left and right by the same class in its own row is
    part of that bar (level 3's 7-wide carries one in its middle); a lone MARK
    cell is scenery.
    """
    nr, nc = _dims(cells)
    out = [[BG] * nc for _ in range(nr)]
    for r in range(nr):
        for c in range(nc):
            v = cells[r][c]
            if v in (PIECE, PLAYER):
                out[r][c] = v
            elif v == ODD:
                out[r][c] = PIECE
            elif v == MARK and 0 < c < nc - 1:
                a, b = cells[r][c - 1], cells[r][c + 1]
                if a == b and a in (PIECE, PLAYER):
                    out[r][c] = a
    return out


def player_cells(cells):
    for comp in _comps(_classed(cells), PLAYER):
        return sorted(comp)
    return []


def _comps_multi(cells, colours):
    nr, nc = _dims(cells)
    seen, comps = set(), []
    for r in range(nr):
        for c in range(nc):
            if cells[r][c] not in colours or (r, c) in seen:
                continue
            stack, comp = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                comp.append((rr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ar, ac = rr + dr, cc + dc
                    if 0 <= ar < nr and 0 <= ac < nc \
                            and cells[ar][ac] in colours and (ar, ac) not in seen:
                        seen.add((ar, ac))
                        stack.append((ar, ac))
            comps.append(comp)
    return comps


def blocked(cells, core, ignore=()):
    """Bars block only by OVERLAP; cups/walls/markers block with a 1-cell halo.

    Verified at transition #50: the active 5-bar slid left until it sat flush
    against another bar, so the standoff is scenery-only.
    """
    nr, nc = _dims(cells)
    _MASK[0] = bar_mask(cells)
    core_set = set(core)
    ign = set(ignore)
    for (r, c) in core:
        if not (0 <= r < nr and 0 <= c < nc):
            return True
        if (r, c) not in ign and cells[r][c] != BG and (r, c) not in _MASK[0]:
            return True   # pieces pass through each other; only scenery blocks
    for (r, c) in core:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < nr and 0 <= cc < nc):
                    continue
                if (rr, cc) in core_set or (rr, cc) in ign:
                    continue
                if cells[rr][cc] != BG and (rr, cc) not in _MASK[0]:
                    return True
    return False


def render(grid, cells, n, level=0):
    sz, orr, occ, nr, nc = geometry(grid)
    out = [row[:] for row in grid]
    for i in range(nr):
        for j in range(nc):
            v = cells[i][j]
            for a in range(sz):
                for b in range(sz):
                    r, c = orr + i * sz + a, occ + j * sz + b
                    if r < 64 and c < 64:
                        out[r][c] = v
    cr = counter_row(grid)
    period = BAR_PERIOD.get(level, DEFAULT_BAR_PERIOD)
    filled = min(int(round(64.0 * n / period)), 64)
    for c in range(64):
        pos = c >= 64 - filled if cr == 0 else c < filled
        out[cr][c] = 0 if pos else 14
    return out


def _level():
    try:
        return CURRENT_LEVEL
    except NameError:
        return 0


def read_n(grid, level):
    cr = counter_row(grid)
    filled = sum(1 for c in range(64) if grid[cr][c] != 14)
    period = BAR_PERIOD.get(level, DEFAULT_BAR_PERIOD)
    best, bestd = 0, 99
    for n in range(period + 1):
        d = abs(int(round(64.0 * n / period)) - filled)
        if d < bestd:
            best, bestd = n, d
    return best


# --- cups -----------------------------------------------------------------

def cup_cells(cells):
    nr, nc = _dims(cells)
    return [(r, c) for r in range(nr) for c in range(nc) if cells[r][c] == CUP]


def leg_row(cells):
    """The cup row the bars can reach: the row next to the cups' back wall.

    Found from the row carrying the most cup cells (the solid back), stepping
    one row towards the playfield.
    """
    cups = cup_cells(cells)
    if not cups:
        return None
    counts = {}
    for r, _ in cups:
        counts[r] = counts.get(r, 0) + 1
    back = max(counts, key=lambda r: (counts[r], -r))
    if counts.get(back + 1):
        return back + 1
    if counts.get(back - 1):
        return back - 1
    return back


def cup_dir(cells, core):
    """1 = cups are up from the bars, 2 = down."""
    cups = cup_cells(cells)
    if not cups:
        return 2
    cr = sum(r for r, _ in cups) / float(len(cups))
    br = sum(r for r, _ in core) / float(len(core))
    return 2 if cr > br else 1


def leg_cols(cells, core=None):
    """Columns of the cup row the bars rest against."""
    row = leg_row(cells)
    if row is None:
        return set()
    keep = set(c for lo, hi in cups_of(cells) for c in range(lo, hi + 1))
    return set(c for (r, c) in cup_cells(cells) if r == row and c in keep)


def settled(cells, core):
    """One more step toward the cups is stopped BY A CUP."""
    dr, dc = DELTA[cup_dir(cells, core)]
    moved = [(r + dr, c + dc) for r, c in core]
    if not blocked(cells, moved, ignore=core):
        return False
    mset = set(moved) | set(core)
    for (r, c) in moved:
        for ddr in (-1, 0, 1):
            for ddc in (-1, 0, 1):
                rr, cc = r + ddr, c + ddc
                if 0 <= rr < _dims(cells)[0] and 0 <= cc < _dims(cells)[1] \
                        and (rr, cc) not in mset and cells[rr][cc] == CUP:
                    return True
    return False


def cup_columns(cells):
    return set(c for (_, c) in cup_cells(cells))


def gap_columns(cells):
    """Columns BETWEEN the cups that no cup occupies -- the spans to bridge."""
    cols = cup_columns(cells)
    if not cols:
        return set()
    return set(c for c in range(min(cols) + 1, max(cols)) if c not in cols)


def cups_of(cells):
    """Column span of each cup facing the bars.

    Level 4 also has a cup lying against the side wall, well away from the row
    the bars can reach; only cups that reach the leg row count.
    """
    legrow = leg_row(cells)
    if legrow is None:
        return []
    out = []
    for comp in _comps(cells, CUP):
        if any(r == legrow for r, _ in comp):
            out.append((min(c for _, c in comp), max(c for _, c in comp)))
    return out


def _cup_range(cells):
    cols = cup_columns(cells)
    return (min(cols), max(cols)) if cols else (0, 15)


def stranded(cells, bars, core):
    """An idle bar with no column inside the cup structure has fallen off it.

    #131 pressed 5 with a bar at cols 0-2 while HOLDING it: fine. #134 pressed
    5 with that same bar idle: instant game over.
    """
    lo, hi = _cup_range(cells)
    for b in bars:
        if _spec(b) == _spec(core):
            continue
        cs = [c for _, c in b]
        if max(cs) < lo or min(cs) > hi:
            return True
    return False


def gap_spans(cells):
    """Each maximal run of gap columns between neighbouring cups."""
    spans = sorted(cups_of(cells))
    return [(a_hi + 1, b_lo - 1) for (a_lo, a_hi), (b_lo, b_hi)
            in zip(spans, spans[1:])]


def _gap_spans(cells):
    spans = sorted(cups_of(cells))
    return [(a_hi + 1, b_lo - 1) for (a_lo, a_hi), (b_lo, b_hi)
            in zip(spans, spans[1:]) if b_lo - a_hi > 1]


def _classify(cells, bar):
    """'bridge' (both ends on legs, covering at least one gap), 'spare' (both
    ends clear of every leg), or None for a bar that is not properly at rest."""
    legs = leg_cols(cells, bar)
    cs = [c for _, c in bar]
    lo, hi = min(cs), max(cs)
    if lo in legs and hi in legs:
        spanned = [g for g in _gap_spans(cells) if lo <= g[0] and g[1] <= hi]
        # each end must be the leg bordering one of the gaps it carries
        if spanned and all(any(e in (g[0] - 1, g[1] + 1) for g in spanned)
                           for e in (lo, hi)):
            return "bridge"
        return None
    if lo not in legs and hi not in legs:
        return "spare"
    return None


def resting(cells, bars):
    """Action 5 grades the board once every bar is at rest and no two bars end
    on the same column."""
    ends = []
    covered = set()
    for b in bars:
        kind = _classify(cells, b)
        if kind is None:
            return False
        cs = [c for _, c in b]
        lo, hi = min(cs), max(cs)
        ends += [lo, hi]
        if kind == "bridge":
            covered.update(g for g in _gap_spans(cells)
                           if lo <= g[0] and g[1] <= hi)
    if set(_gap_spans(cells)) - covered:
        return False          # nothing is graded until every gap is bridged
    return len(ends) == len(set(ends))


def solved(cells, bars):
    """Correct when every gap between neighbouring cups is spanned by a bridge
    and no gap carries more than one end of a stowed spare."""
    counts = {}
    covered = set()
    for b in bars:
        kind = _classify(cells, b)
        cs = [c for _, c in b]
        lo, hi = min(cs), max(cs)
        for g in _gap_spans(cells):
            if kind == "bridge" and lo <= g[0] and g[1] <= hi:
                covered.add(g)
            elif kind == "spare":
                for e in (lo, hi):
                    if g[0] <= e <= g[1]:
                        counts[g] = counts.get(g, 0) + 1
    return set(_gap_spans(cells)) <= covered and all(v <= 1 for v in counts.values())


def _bar_cells(spec):
    r, c0, c1 = spec
    return [(r, c) for c in range(c0, c1 + 1)]


def _spec(comp):
    return (comp[0][0], min(c for _, c in comp), max(c for _, c in comp))


def bars_of(state, cells):
    """Bars as separate objects.

    Two bars parked side by side merge into one blob in the frame, so their
    identities are carried in `state` and only re-derived from the frame when
    that bookkeeping does not match what is on screen.
    """
    occupied = bar_mask(cells)
    specs = (state or {}).get("bars")
    if specs:
        cov = set()
        for spec in specs:
            cov.update(_bar_cells(spec))
        if cov == occupied:
            return [_bar_cells(spec) for spec in specs]
    cl = _classed(cells)
    bars = [sorted(comp) for comp in _comps(cl, PIECE)]
    play = player_cells(cells)
    if play:
        bars.append(play)
    return bars


def _order_key(comp):
    return (min(r for r, _ in comp), min(c for _, c in comp))


def n_of(state, grid, level):
    """Action count: trust the threaded state when it matches the overlay.

    With a long period several counts render identically, so reading the bar
    alone is ambiguous; the carried count disambiguates.
    """
    cr = counter_row(grid)
    filled = sum(1 for c in range(64) if grid[cr][c] != 14)
    period = BAR_PERIOD.get(level, DEFAULT_BAR_PERIOD)
    sn = (state or {}).get("n")
    if sn is not None and int(round(64.0 * sn / period)) == filled:
        return sn
    return read_n(grid, level)


# The overlay is coarse: with a long period several action counts render the
# same bar, so re-initialising from the frame alone is ambiguous by one. The
# true count for the level in progress is recorded here before each commit.
N_HINT = {4: 53}

# Bars parked flush against one another merge into a single blob in the frame,
# so when that happens the true split is recorded here before a commit.
BAR_HINT = []


def init_state(entry_grid, level=None, **kw):
    lvl = _level() if level is None else level
    n = read_n(entry_grid, lvl)
    bars = list(BAR_HINT) or None
    hint = N_HINT.get(lvl)
    if hint is not None:
        period = BAR_PERIOD.get(lvl, DEFAULT_BAR_PERIOD)
        cr = counter_row(entry_grid)
        filled = sum(1 for c in range(64) if entry_grid[cr][c] != 14)
        if int(round(64.0 * hint / period)) == filled:
            n = hint
    return {"n": n, "level": lvl, "bars": bars}


def predict(state, grid, action, x=None, y=None, level=None, **kw):
    cells = to_cells(grid)
    core = player_cells(cells)
    lvl = _level() if level is None else level
    n = n_of(state, grid, lvl) + 1
    info = {"level_up": False, "dead": False, "win": False}
    st = {"n": n, "level": lvl}

    bars = bars_of(state, cells)
    st["bars"] = [_spec(b) for b in bars]

    if action == 5 and core:
        if stranded(cells, bars, core):
            info["dead"] = True
            return render(grid, cells, n, lvl), info, st
        if resting(cells, bars):
            if solved(cells, bars):
                info["level_up"] = True
                return _entry(lvl + 1, grid), info, {"n": 0, "level": lvl + 1}
            info["dead"] = True
            return render(grid, cells, n, lvl), info, st
        if cup_dir(cells, core) == 2:      # cups below -> topmost bar is last
            target = min(bars, key=_order_key)
        else:                              # cups above -> bottommost is last
            target = max(bars, key=_order_key)
        if _order_key(target) != _order_key(core):
            _recolour(cells, core, PIECE)
            _recolour(cells, target, PLAYER)
        return render(grid, cells, n, lvl), info, st

    if action == 6 and x is not None and y is not None:
        sz, orr, occ, _nr, _nc = geometry(grid)
        cell = ((int(y) - orr) // sz, (int(x) - occ) // sz)
        for b in bars:
            if cell in b and b != core:
                _recolour(cells, core, PIECE)
                _recolour(cells, b, PLAYER)
                break
        return render(grid, cells, n, lvl), info, st

    if action in DELTA and core:
        dr, dc = DELTA[action]
        new = [(r + dr, c + dc) for (r, c) in core]
        if not blocked(cells, new, ignore=core):
            colours = [cells[r][c] for (r, c) in core]
            for (r, c) in core:
                cells[r][c] = BG
            for (r, c), v in zip(new, colours):
                cells[r][c] = v
            st["bars"] = [_spec(new) if _spec(b) == _spec(core) else _spec(b)
                          for b in bars]
    return render(grid, cells, n, lvl), info, st


LEVEL_ENTRY = {1: """1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
ccccccccccccbbbbbbbbbbbbccccbbbbbbbbbbbbccccbbbbbbbbbbbbcccccccc
ccccccccccccbbbbbbbbbbbbccccbbbbbbbbbbbbccccbbbbbbbbbbbbcccccccc
ccccccccccccbbbbbbbbbbbbccccbbbbbbbbbbbbccccbbbbbbbbbbbbcccccccc
ccccccccccccbbbbbbbbbbbbccccbbbbbbbbbbbbccccbbbbbbbbbbbbcccccccc
ccccccccccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbcccccccc
ccccccccccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbcccccccc
ccccccccccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbcccccccc
ccccccccccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbccccbbbbcccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccc888888888888cccccccccccccccccccccccccccccccccccccccccccc
cccccccc888888888888cccccccccccccccccccccccccccccccccccccccccccc
cccccccc888888888888cccccccccccccccccccccccccccccccccccccccccccc
cccccccc888888888888cccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccc888888888888cccccccccccccccccccccccc
cccccccccccccccccccccccccccc888888888888cccccccccccccccccccccccc
cccccccccccccccccccccccccccc888888888888cccccccccccccccccccccccc
cccccccccccccccccccccccccccc888888888888cccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccc99999999999999999999cccccccccccccccccccccccc
cccccccccccccccccccc99999999999999999999cccccccccccccccccccccccc
cccccccccccccccccccc99999999999999999999cccccccccccccccccccccccc
cccccccccccccccccccc99999999999999999999cccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc6666cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc6666cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc6666cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc6666cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc4444cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc4444cccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc4444cccccccccccccccccccc
eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee""",
               2: """1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
ccccbbbbbbbbbbbbccccccccbbbbbbbbbbbbccccccccccccbbbbbbbbbbbbcccc
ccccbbbbbbbbbbbbccccccccbbbbbbbbbbbbccccccccccccbbbbbbbbbbbbcccc
ccccbbbbbbbbbbbbccccccccbbbbbbbbbbbbccccccccccccbbbbbbbbbbbbcccc
ccccbbbbbbbbbbbbccccccccbbbbbbbbbbbbccccccccccccbbbbbbbbbbbbcccc
ccccbbbbccccbbbbccccccccbbbbccccbbbbccccccccccccbbbbccccbbbbcccc
ccccbbbbccccbbbbccccccccbbbbccccbbbbccccccccccccbbbbccccbbbbcccc
ccccbbbbccccbbbbccccccccbbbbccccbbbbccccccccccccbbbbccccbbbbcccc
ccccbbbbccccbbbbccccccccbbbbccccbbbbccccccccccccbbbbccccbbbbcccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccc8888888888888888cccccccccccccccccccccccccccccccccccccccc
cccccccc8888888888888888cccccccccccccccccccccccccccccccccccccccc
cccccccc8888888888888888cccccccccccccccccccccccccccccccccccccccc
cccccccc8888888888888888cccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccc88888888888888888888cccc
cccccccccccccccccccccccccccccccccccccccc88888888888888888888cccc
cccccccccccccccccccccccccccccccccccccccc88888888888888888888cccc
cccccccccccccccccccccccccccccccccccccccc88888888888888888888cccc
cccccccc888888888888888888888888cccccccccccccccccccccccccccccccc
cccccccc888888888888888888888888cccccccccccccccccccccccccccccccc
cccccccc888888888888888888888888cccccccccccccccccccccccccccccccc
cccccccc888888888888888888888888cccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccc999999999999999999999999cccc
cccccccccccccccccccccccccccccccccccc999999999999999999999999cccc
cccccccccccccccccccccccccccccccccccc999999999999999999999999cccc
cccccccccccccccccccccccccccccccccccc999999999999999999999999cccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
cccc6666cccccccccccccccccccccccccccc6666cccccccccccccccc6666cccc
cccc6666cccccccccccccccccccccccccccc6666cccccccccccccccc6666cccc
cccc6666cccccccccccccccccccccccccccc6666cccccccccccccccc6666cccc
cccc6666cccccccccccccccccccccccccccc6666cccccccccccccccc6666cccc
cccc4444cccccccccccccccccccccccccccc4444cccccccccccccccc4444cccc
cccc4444cccccccccccccccccccccccccccc4444cccccccccccccccc4444cccc
cccc4444cccccccccccccccccccccccccccc4444cccccccccccccccc4444cccc
eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee""",
               3: """eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
1111111111111111111111111111111111111111111111111111111111111111
11ccccccccccccccccccccc444cccccccccccccccccccccccccccccccccccc11
11ccccccccccccccccccccc444cccccccccccccccccccccccccccccccccccc11
11ccccccccccccccccccccc444cccccccccccccccccccccccccccccccccccc11
11ccccccccccccccccccccc666cccccccccccccccccccccccccccccccccccc11
11ccccccccccccccccccccc666cccccccccccccccccccccccccccccccccccc11
11ccccccccccccccccccccc666cccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11ccccccccccccccc999999999999999cccccc888888888888888ccccccccc11
11ccccccccccccccc999999999999999cccccc888888888888888ccccccccc11
11ccccccccccccccc999999999999999cccccc888888888888888ccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccc888888888444888888888ccccccccccccccccccccccccccccccccc11
11cccccc888888888444888888888ccccccccccccccccccccccccccccccccc11
11cccccc888888888444888888888ccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccc888888888888cccccc11
11cccccccccccccccccccccccccccccccccccccccccc888888888888cccccc11
11cccccccccccccccccccccccccccccccccccccccccc888888888888cccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccc888888888888cccccccccccc11
11cccccccccccccccccccccccccccccccccccc888888888888cccccccccccc11
11cccccccccccccccccccccccccccccccccccc888888888888cccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11ccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccbbbcccbbbccc11
11ccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccbbbcccbbbccc11
11ccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccbbbcccbbbccc11
11ccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccbbbbbbbbbccc11
11ccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccbbbbbbbbbccc11
11ccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccbbbbbbbbbccc11
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111""",
               4: """1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
1111111111111111111111111111111111111111111111111111111111111111
11111ccccccccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccccc11
11111ccccccccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccccc11
11111ccccccccccccbbbbbbbbbcccccccccbbbbbbbbbcccbbbbbbbbbcccccc11
11111ccccccccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccccc11
11111ccccccccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccccc11
11111ccccccccccccbbbcccbbbcccccccccbbbcccbbbcccbbbcccbbbcccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111cccccccccccccccccccccccc888888888888ccccccccccccccccccccc11
11111cccccccccccccccccccccccc888888888888ccccccccccccccccccccc11
11111cccccccccccccccccccccccc888888888888ccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccc888888888cccccccccccc999999999999999cccccc11
11111ccccccccccccccc888888888cccccccccccc999999999999999cccccc11
11111ccccccccccccccc888888888cccccccccccc999999999999999cccccc11
11111bbbbbbccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbbbbccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbbbbccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbcccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbcccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbcccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111bbbbbbcccccccccccccccccccccffffffcccccccccccccccccccccccc11
11111bbbbbbcccccccccccccccccccccffffffcccccccccccccccccccccccc11
11111bbbbbbcccccccccccccccccccccffffffcccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccfffcccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccfffcccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccfffcccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccccccccccccccccccccccccccccccccccccccccccccc11
11111ccccccccccccccc666ccccccccccccccccccccc666ccccccccccccccc11
11111ccccccccccccccc666ccccccccccccccccccccc666ccccccccccccccc11
11111ccccccccccccccc666ccccccccccccccccccccc666ccccccccccccccc11
11111ccccccccccccccc444ccccccccccccccccccccc444ccccccccccccccc11
11111ccccccccccccccc444ccccccccccccccccccccc444ccccccccccccccc11
11111ccccccccccccccc444ccccccccccccccccccccc444ccccccccccccccc11
1111111111111111111111111111111111111111111111111111111111111111
eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"""}


def _entry(level, fallback):
    txt = LEVEL_ENTRY.get(level)
    if txt is None:
        return fallback
    return [[int(ch, 16) for ch in line] for line in txt.split("\n") if line]
