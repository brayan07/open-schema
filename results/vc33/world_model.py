"""World model for vc33 -- orientation-agnostic.

Raw row 0 is a per-level action meter (7 background, fills with 4 from the
right; width after k actions on the level = k + (k+2)//4).

The playfield is the bounding box of all structural pixels (values 0/3/5/9).
It is cut into STRIPES perpendicular to one axis: alternating PANEL and
BAND(5).  All panels are anchored to the same side of the box; a panel is
OPEN(0) for the first h pixels measured from that anchor, solid 3 beyond.

Let `unit` = half the band thickness (2 px in levels 0-1, 1 px in level 2).
Inside a panel stripe, at distance d from the anchor:
    d < h                    -> OPEN
    d < 2*unit, some stripes -> a 9 button (2x2 units) pinned at the anchor
    d in [h, h+unit)         -> arrow pointer (knob colour), 3 units wide
    d in [h+unit, h+2*unit)  -> arrow body (4)
    d in [h+2u, h+3u)        -> arrow tip (4), middle unit only
Clicking a 9 button moves 2*unit px from the panel on the other side of the
band that button touches into the button's own panel.

Each arrow's colour matches a knob (non-5 pixel) sitting inside some band at
distance d_knob.  The level is complete once every arrow panel has
h == d_knob of its colour.
"""

BG, OPEN, BAND, NINE, METER, LIT = 3, 0, 5, 9, 4, 12
STRUCT = (0, 3, 5, 9)


# ---------------------------------------------------------------- meter ---
# extra-pixel period per level (None = a plain 1 px per action)
CURRENT_LEVEL = 0   # injected by the harness before every call

# Meter fill rate (pixels per action) per level, as a fraction num/den.
# meter(k) = round-half-up(num/den * k).  Levels 0-1: 5/4 (1,3,4,5,6,8,9...).
# Level 2: measured 1,2,3,3,4,5,6,7,8,9,9,10,... -> exactly 6/7.
RATE = {0: (32, 25), 1: (32, 25), 2: (6, 7), 3: (32, 25), 4: (8, 25)}


BOUNDS = {}   # levels whose rate is still being calibrated


def _meter_for(k, level, bounds=None):
    if level in RATE:
        num, den = RATE[level]
        return (2 * num * k + den) // (2 * den)
    lo, hi = bounds if bounds else BOUNDS.get(level, (0.0, 3.0))
    return int((lo + hi) / 2.0 * k + 0.5)


def _actions_taken(meter, level):
    """Fallback when the state carries no counter: the largest k matching."""
    best = 0
    for k in range(0, 400):
        if _meter_for(k, level) == meter:
            best = k
        if _meter_for(k, level) > meter:
            break
    return best


def _narrow(bounds, k, meter):
    """Each observed (k, meter) pins the rate to [(m-.5)/k, (m+.5)/k)."""
    if k <= 0:
        return bounds
    lo, hi = bounds
    lo = max(lo, (meter - 0.5) / float(k))
    hi = min(hi, (meter + 0.5) / float(k))
    if lo >= hi:
        lo, hi = (meter - 0.5) / float(k), (meter + 0.5) / float(k)
    return (lo, hi)


# ---------------------------------------------------------------- parse ---
class Scene(object):
    pass


def _bbox(grid):
    r0, r1, c0, c1 = 64, -1, 64, -1
    for r in range(1, 64):
        for c in range(64):
            if grid[r][c] in STRUCT:
                if r < r0:
                    r0 = r
                if r > r1:
                    r1 = r
                if c < c0:
                    c0 = c
                if c > c1:
                    c1 = c
    return r0, r1, c0, c1


def parse(grid):
    s = Scene()
    r0, r1, c0, c1 = _bbox(grid)
    rows5 = 0
    cols5 = 0
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if grid[r][c] == BAND:
                rows5 += 1
                break
    for c in range(c0, c1 + 1):
        for r in range(r0, r1 + 1):
            if grid[r][c] == BAND:
                cols5 += 1
                break
    s.axis = "h" if rows5 <= cols5 else "v"
    if s.axis == "h":
        s.u0, s.u1, s.dlo, s.dhi = r0, r1, c0, c1
    else:
        s.u0, s.u1, s.dlo, s.dhi = c0, c1, r0, r1
    s.dmax = s.dhi - s.dlo

    # which stripes are bands?
    isband = {}
    for u in range(s.u0, s.u1 + 1):
        hit = False
        for p in range(s.dlo, s.dhi + 1):
            if _raw(s, grid, u, p - s.dlo, True) == BAND:
                hit = True
                break
        isband[u] = hit

    # anchor: bands touch one end of the perpendicular range
    s.lo = True
    for u in range(s.u0, s.u1 + 1):
        if isband[u]:
            if _get(grid, s, u, s.dlo, True) == BAND:
                s.lo = True
            else:
                s.lo = False
            break

    # stripe groups
    s.stripes = []
    u = s.u0
    while u <= s.u1:
        v = u
        while v <= s.u1 and isband[v] == isband[u]:
            v += 1
        s.stripes.append([isband[u], u, v])
        u = v
    # band thickness == click step == 9-button size; the arrow glyph is
    # drawn at half that (rounded up)
    s.thick = 2
    for st in s.stripes:
        if st[0]:
            s.thick = st[2] - st[1]
            break
    s.step = s.thick
    s.au = (s.thick + 1) // 2

    s.panels = []
    s.bands = []
    for i, (band, a, b) in enumerate(s.stripes):
        if band:
            knobs = {}
            marks = []
            u = a
            d = 0
            while d <= s.dmax:
                v = _at(grid, s, a, d)
                if v != BAND and v != BG:
                    d2 = d
                    while d2 + 1 <= s.dmax and _at(grid, s, a, d2 + 1) == v:
                        d2 += 1
                    tv = v
                    if v == LIT:
                        tv = MARK_ORIG.get((i, d), LIT)
                    marks.append({"v": tv, "d0": d, "d1": d2})
                    if v not in knobs or d < knobs[v]:
                        knobs[v] = d
                    d = d2 + 1
                else:
                    d += 1
            kv, kd = (None, None)
            for v in knobs:
                if kd is None or knobs[v] < kd:
                    kv, kd = v, knobs[v]
            ln = 0
            for u in range(a, b):
                d = 0
                while d <= s.dmax and _at(grid, s, u, d) != BG:
                    d += 1
                if d > ln:
                    ln = d
            s.bands.append({"i": i, "u0": a, "u1": b, "kv": kv, "kd": kd,
                            "len": ln, "marks": knobs, "mk": marks})
        else:
            h = 0
            for u in range(a, b):
                d = 0
                while d <= s.dmax and _at(grid, s, u, d) == OPEN:
                    d += 1
                if d > h:
                    h = d
            p = {"i": i, "u0": a, "u1": b, "h": h,
                 "nine": [], "arrow": [], "tip": [], "ptr": None}
            for u in range(a, b):
                if _at(grid, s, u, 0) == NINE:
                    p["nine"].append(u)
                if h <= s.dmax and _at(grid, s, u, h) not in (BG, NINE, OPEN):
                    p["arrow"].append(u)
                    p["ptr"] = _at(grid, s, u, h)
                if h + 2 * s.au <= s.dmax and \
                        _at(grid, s, u, h + 2 * s.au) not in (BG, NINE, OPEN):
                    p["tip"].append(u)
            s.panels.append(p)
    return s


def _coord(s, u, d):
    p = s.dlo + d if s.lo else s.dhi - d
    return (u, p) if s.axis == "h" else (p, u)


def _at(grid, s, u, d):
    r, c = _coord(s, u, d)
    return grid[r][c]


def _get(grid, s, u, p, absolute):
    return grid[u][p] if s.axis == "h" else grid[p][u]


def _raw(s, grid, u, d, absolute):
    p = s.dlo + d
    return grid[u][p] if s.axis == "h" else grid[p][u]


# --------------------------------------------------------------- render ---
def render(s, grid, meter):
    g = [row[:] for row in grid]
    g[0] = [METER if c >= 64 - meter else 7 for c in range(64)]
    au = s.au
    for p in s.panels:
        h = p["h"]
        for u in range(p["u0"], p["u1"]):
            for d in range(s.dmax + 1):
                v = BG
                if d < h:
                    v = OPEN
                if d < s.thick and u in p["nine"]:
                    v = NINE
                if u in p["arrow"] and h <= d < h + 2 * au:
                    v = p["ptr"] if d < h + au else METER
                if u in p["tip"] and h + 2 * au <= d < h + 3 * au:
                    v = METER
                r, c = _coord(s, u, d)
                g[r][c] = v
    for b in s.bands:
        for m in b["mk"]:
            on = _lit(s, b, m)
            for u in range(b["u0"], b["u1"]):
                for d in range(m["d0"], m["d1"] + 1):
                    r, c = _coord(s, u, d)
                    g[r][c] = LIT if on else m["v"]
            if not on:
                continue
            for cu in (b["u0"] - 2, b["u1"] + 1):
                if s.u0 <= cu < s.u1:
                    for d in range(m["d0"] + 2, m["d1"] - 1):
                        r, c = _coord(s, cu, d)
                        g[r][c] = OPEN
    return g


def _place_arrow(s, dst, colour):
    """Clicking a lit mark walks the arrow across that band, re-centred."""
    span = 3 * s.au
    u0 = dst["u0"] + ((dst["u1"] - dst["u0"]) - span) // 2
    dst["arrow"] = [u0 + i for i in range(span)]
    dst["tip"] = [u0 + s.au + i for i in range(s.au)]
    dst["ptr"] = colour


def _clear_arrow(p):
    p["arrow"] = []
    p["tip"] = []
    p["ptr"] = None


def _lit(s, b, m):
    """A mark lights up only when BOTH adjacent panel edges sit on it."""
    n = 0
    for p in s.panels:
        if p["i"] == b["i"] - 1 or p["i"] == b["i"] + 1:
            n += 1
            if p["h"] != m["d0"]:
                return False
    return n == 2


# ---------------------------------------------------------------- model ---
def _panel_at(s, u):
    for p in s.panels:
        if p["u0"] <= u < p["u1"]:
            return p
    return None


def _cap(s, p):
    """A panel's edge slides along its bands: h cannot outrun the shorter."""
    cap = s.dmax + 1
    for b in s.bands:
        if b["i"] == p["i"] - 1 or b["i"] == p["i"] + 1:
            if b["len"] < cap:
                cap = b["len"]
    return cap


def _neighbour(s, p, u):
    rows = p["nine"]
    a = u
    while a - 1 in rows:
        a -= 1
    want = p["i"] - 1 if a == p["u0"] else p["i"] + 1
    bd = None
    for b in s.bands:
        if b["i"] == want:
            bd = b
    if bd is None:
        return None
    other = want * 2 - p["i"]
    for q in s.panels:
        if q["i"] == other:
            return q
    return None


MARK_ORIG = {(1, 9): 1, (3, 18): 1, (1, 24): 1, (3, 12): 1, (5, 27): 1}   # original colour of marks now showing as LIT
K_HINT = None   # actions already spent on this level when resuming mid-level


def init_state(entry_grid, level=0):
    m = 0
    for v in entry_grid[0]:
        if v == METER:
            m += 1
    b = BOUNDS.get(CURRENT_LEVEL, (0.0, 3.0))
    if K_HINT is not None:
        return {"k": K_HINT, "b": _narrow(b, K_HINT, m)}
    if m == 0:
        return {"k": 0, "b": b}
    k = _actions_taken(m, CURRENT_LEVEL)
    return {"k": k, "b": _narrow(b, k, m)}


def predict(state, grid, action, x=None, y=None, level=0):
    s = parse(grid)
    meter = 0
    for v in grid[0]:
        if v == METER:
            meter += 1
    if action == 6 and x is not None and grid[y][x] == LIT:
        u = y if s.axis == "h" else x
        for b in s.bands:
            if not (b["u0"] <= u < b["u1"]):
                continue
            side = []
            for q in s.panels:
                if q["i"] == b["i"] - 1 or q["i"] == b["i"] + 1:
                    side.append(q)
            if len(side) == 2:
                p0, p1 = side
                if p0["arrow"] and p1["arrow"]:
                    c0, c1 = p0["ptr"], p1["ptr"]
                    _place_arrow(s, p0, c1)
                    _place_arrow(s, p1, c0)
                elif p0["arrow"]:
                    _place_arrow(s, p1, p0["ptr"])
                    _clear_arrow(p0)
                elif p1["arrow"]:
                    _place_arrow(s, p0, p1["ptr"])
                    _clear_arrow(p1)
    if action == 6 and x is not None and grid[y][x] == NINE:
        u = y if s.axis == "h" else x
        p = _panel_at(s, u)
        if p is not None:
            q = _neighbour(s, p, u)
            if q is not None and p["h"] + s.step <= _cap(s, p) \
                    and q["h"] - s.step >= 0:
                p["h"] += s.step
                q["h"] -= s.step
    lvl = CURRENT_LEVEL
    k = 0
    bnd = BOUNDS.get(lvl, (0.0, 3.0))
    if isinstance(state, dict):
        k = state.get("k", 0)
        bnd = state.get("b", bnd)
    if lvl in RATE and _meter_for(k, lvl) != meter:
        k = _actions_taken(meter, lvl)
    bnd = _narrow(bnd, k, meter)
    out = render(s, grid, min(_meter_for(k + 1, lvl, bnd), 64))
    state = {"k": k + 1, "b": bnd}
    up = True
    any_arrow = False
    for p in s.panels:
        if p["arrow"]:
            any_arrow = True
            ok = False
            for b in s.bands:
                if b["i"] != p["i"] - 1 and b["i"] != p["i"] + 1:
                    continue
                for m in b["mk"]:
                    if m["v"] == p["ptr"] and m["d0"] == p["h"]:
                        ok = True
            if not ok:
                up = False
    return out, {"level_up": bool(any_arrow and up),
                 "dead": False, "win": False}, state
