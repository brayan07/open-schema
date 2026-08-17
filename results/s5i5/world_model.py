"""World model for s5i5.

Mechanics
---------
Only action 6 (click) is legal.  Row 63 is a step meter: after n actions of the
current level, round_half_up(64*n/50) cells at its right end are colour 4.

The board holds *objects*: a solid rectangle of one colour plus a 3-cell line
of colour 3 glued to one edge (its tail), plus optionally a head cell of
colour 13.  An object grows AWAY from its line.  Walls (colour 15) have no
line: they can only be pushed.

One control box per colour sits at the bottom (2-border, 4-inner panel showing
a shape, an axis and its mirror).  Clicking a pixel of the object colour inside
a box grows that object by one 3x3 block at its leading edge; whatever stands
in the way is pushed 3 cells in the same direction (rigid, tail and head
included) and pushes chain.  A push that would leave the grid makes the whole
click a no-op.  The grown object's head moves to the centre of the new block.

Target diamonds (4 cells of colour 13 around an empty centre) are drawn on top
of everything and never move; the level is completed once every diamond centre
holds a head.
"""

BG = 5
BORDER = 2
INNER = 4
AXIS = 3
HEAD = 13
FIXED = 15
H = W = 64
STRUCTURAL = (BG, BORDER, INNER, AXIS, HEAD)


# per-level action budget the row-63 meter is drawn against (calibrated
# from observation: level 0 fills 64 cells over 50 actions)
BUDGET = {0: 50, 1: 150, 2: 200}
DEFAULT_BUDGET = 200


def _budget(level):
    return BUDGET.get(level if level is not None else 0, DEFAULT_BUDGET)


def _bar_after(n, level):
    b = _budget(level)
    return (2 * 64 * n + b) // (2 * b)


def _n_from_bar(grid, level):
    b = sum(1 for v in grid[63] if v == INNER)
    for n in range(0, 900):
        if _bar_after(n, level) == b:
            return n
    return 0


def _cur_level():
    # the harness injects CURRENT_LEVEL as a module global
    try:
        return int(CURRENT_LEVEL)
    except Exception:
        return 0


# the row-63 meter is coarse, so the action count cannot always be read back
# from it; N_OFFSET carries the true count of the live position.
N_OFFSET = 38


def init_state(entry_grid, level=None):
    lvl = level if level is not None else _cur_level()
    n = _n_from_bar(entry_grid, lvl)
    if n and _bar_after(N_OFFSET, lvl) == _bar_after(n, lvl):
        n = N_OFFSET
    return {"n": n, "level": lvl}


def _components(cells, diag=False):
    todo = set(cells)
    out = []
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if diag:
        steps = steps + [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    while todo:
        seed = None
        for c in todo:
            seed = c
            break
        stack = [seed]
        todo.discard(seed)
        comp = set()
        while stack:
            cx, cy = stack.pop()
            comp.add((cx, cy))
            for dx, dy in steps:
                p = (cx + dx, cy + dy)
                if p in todo:
                    todo.discard(p)
                    stack.append(p)
        out.append(comp)
    return out


def _components_through(cells, bridges):
    """4-connected components of `cells`, allowed to hop over `bridges`"""
    todo = set(cells)
    out = []
    steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while todo:
        seed = None
        for c in todo:
            seed = c
            break
        todo.discard(seed)
        comp = {seed}
        stack = [seed]
        seen_bridge = set()
        while stack:
            cx, cy = stack.pop()
            for dx, dy in steps:
                p = (cx + dx, cy + dy)
                if p in todo:
                    todo.discard(p)
                    comp.add(p)
                    stack.append(p)
                elif p in bridges and p not in seen_bridge:
                    seen_bridge.add(p)
                    stack.append(p)
        out.append(comp)
    return out


def _boxes(grid):
    cells = set()
    for y in range(H):
        for x in range(W):
            if grid[y][x] == BORDER:
                cells.add((x, y))
    out = []
    for comp in _components(cells, diag=True):
        xs = [c[0] for c in comp]
        ys = [c[1] for c in comp]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _in_boxes(x, y, boxes):
    for x0, y0, x1, y1 in boxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def parse(grid):
    boxes = _boxes(grid)

    # marks (colour 13) first: a lone cell is a head, a ring of 4 around a
    # centre is a target diamond.  They are drawn ON TOP of objects, so fill
    # them with the neighbouring object colour before looking for components.
    marks = set()
    for y in range(H - 1):
        for x in range(W):
            if grid[y][x] == HEAD and not _in_boxes(x, y, boxes):
                marks.add((x, y))
    diamonds = set()
    heads = []
    for comp in _components(marks, diag=True):
        if len(comp) == 1:
            for c in comp:
                heads.append(c)
        else:
            xs = [c[0] for c in comp]
            ys = [c[1] for c in comp]
            centre = ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
            for c in comp:
                if c == centre:
                    heads.append(c)
                else:
                    diamonds.add(c)

    filled = grid          # diamonds are drawn on top: 8-connectivity keeps
    body = set()
    for y in range(H - 1):
        for x in range(W):
            v = filled[y][x]
            if v in STRUCTURAL or _in_boxes(x, y, boxes):
                continue
            body.add((x, y))
    objs = []
    colours = set(filled[y][x] for (x, y) in body)
    for col in sorted(colours):
        same = set(c for c in body if filled[c[1]][c[0]] == col)
        # an object whose middle is covered by a diamond stays one piece:
        # connectivity may pass through the overlaid marks
        for comp in _components_through(same, marks):
            objs.append({"colour": col, "body": set(comp), "line": set(),
                         "dir": None, "head": None})

    box_colours = set()
    for x0, y0, x1, y1 in boxes:
        for cy in range(y0, y1 + 1):
            for cx in range(x0, x1 + 1):
                v = grid[cy][cx]
                if v not in STRUCTURAL:
                    box_colours.add(v)

    lines = set()
    for y in range(H - 1):
        for x in range(W):
            if grid[y][x] == AXIS and not _in_boxes(x, y, boxes):
                lines.add((x, y))
    for comp in _components(lines):
        xs = set(c[0] for c in comp)
        ys = set(c[1] for c in comp)
        if len(xs) == 1:
            probes = ((1, 0), (-1, 0))
        elif len(ys) == 1:
            probes = ((0, 1), (0, -1))
        else:
            continue
        cands = []
        for dx, dy in probes:
            for o in objs:
                for (cx, cy) in comp:
                    if (cx + dx, cy + dy) in o["body"]:
                        cands.append((o, (dx, dy)))
                        break
        owner = None
        direction = None
        for o, d in cands:
            if o["colour"] in box_colours:
                owner, direction = o, d
                break
        if owner is None and cands:
            owner, direction = cands[0]
        if owner is not None:
            owner["line"] |= comp
            owner["dir"] = direction

    # a target diamond drawn on top of an object punches holes in it: give
    # those cells back so they travel with the object
    for o in objs:
        cells = o["body"] | o["line"]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        for (mx, my) in diamonds:
            if min(xs) <= mx <= max(xs) and min(ys) <= my <= max(ys):
                o["body"].add((mx, my))

    for c in heads:
        owner = None
        for o in objs:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (c[0] + dx, c[1] + dy) in o["body"]:
                        owner = o
                        break
                if owner:
                    break
            if owner:
                break
        if owner is not None:
            owner["body"].add(c)
            owner["head"] = c
    return objs, diamonds, boxes


def diamond_centres(diamonds):
    out = set()
    for comp in _components(diamonds, diag=True):
        xs = [c[0] for c in comp]
        ys = [c[1] for c in comp]
        out.add(((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2))
    return out


def _occupied(o):
    return o["body"] | o["line"]


def _shift(o, dx, dy, k=3):
    o["body"] = set((x + dx * k, y + dy * k) for x, y in o["body"])
    o["line"] = set((x + dx * k, y + dy * k) for x, y in o["line"])
    if o["head"] is not None:
        o["head"] = (o["head"][0] + dx * k, o["head"][1] + dy * k)


def _inside(cells):
    for x, y in cells:
        if not (0 <= x < W and 0 <= y < H - 1):
            return False
    return True


def grow(target, objs):
    """Grow `target` by one 3x3 block.  Whatever occupies the new block is
    pushed 3 cells the same way, and every object touching it PERPENDICULAR
    to the push (or in front of it) is dragged along.  Walls (no tail line)
    never move; a blocked move makes the whole click a no-op."""
    if target["dir"] is None:
        return False
    dx, dy = target["dir"]
    body = _occupied(target)
    if dx:
        edge = max(x for x, y in body) if dx > 0 else min(x for x, y in body)
        lead = [(x, y) for x, y in body if x == edge]
    else:
        edge = max(y for x, y in body) if dy > 0 else min(y for x, y in body)
        lead = [(x, y) for x, y in body if y == edge]
    new_cells = set()
    for k in (1, 2, 3):
        for (cx, cy) in lead:
            new_cells.add((cx + dx * k, cy + dy * k))
    if not _inside(new_cells):
        return False

    movers = []
    for o in objs:
        if o is not target and (_occupied(o) & new_cells):
            if o["colour"] == FIXED:     # colour 15 never moves
                return False
            movers.append(o)
    if movers:
        # the directly shoved object only drags its SIDEWAYS neighbours; a
        # neighbour dragged along may in turn shove what is in front of it.
        # Walls travel but never pass the drag on.
        perp = [(0, 1), (0, -1)] if dx else [(1, 0), (-1, 0)]
        direct = list(movers)
        changed = True
        while changed:
            changed = False
            for o in objs:
                if o is target or o["colour"] == FIXED or \
                        any(o is m for m in movers):
                    continue
                occ = _occupied(o)
                for m in movers:
                    if m["dir"] is None:      # walls do not pass drag on
                        continue
                    axes = perp if any(m is d for d in direct) \
                        else perp + [(dx, dy)]
                    mo = _occupied(m)
                    hit = False
                    for ax, ay in axes:
                        for (cx, cy) in mo:
                            if (cx + ax, cy + ay) in occ:
                                hit = True
                                break
                        if hit:
                            break
                    if hit:
                        movers.append(o)
                        changed = True
                        break
                if changed:
                    break

        grown = set(body) | new_cells
        moved = []
        for m in movers:
            cells = set((x + dx * 3, y + dy * 3) for x, y in _occupied(m))
            if not _inside(cells):
                return False
            moved.append(cells)
        for idx in range(len(movers)):
            cells = moved[idx]
            for o in objs:
                if any(o is mm for mm in movers):
                    continue
                occ = grown if o is target else _occupied(o)
                if cells & occ:
                    return False

        for m in movers:
            _shift(m, dx, dy)

    target["body"] |= new_cells
    if target["head"] is not None:
        cx = sum(c[0] for c in lead) // len(lead) + dx * 2
        cy = sum(c[1] for c in lead) // len(lead) + dy * 2
        target["head"] = (cx, cy)
    return True


def shrink(target, objs=None):
    """the mirrored half of a control box retracts the object's last block
    (down to a single 3x3); whatever sits against the retreating face is
    pulled along into the freed space"""
    dx, dy = target["dir"]
    cells = _occupied(target)
    if dx:
        span = max(x for x, y in cells) - min(x for x, y in cells) + 1
    else:
        span = max(y for x, y in cells) - min(y for x, y in cells) + 1
    if span <= 3:
        return False
    if dx > 0:
        edge = max(x for x, y in cells)
        gone = set(c for c in cells if c[0] > edge - 3)
    elif dx < 0:
        edge = min(x for x, y in cells)
        gone = set(c for c in cells if c[0] < edge + 3)
    elif dy > 0:
        edge = max(y for x, y in cells)
        gone = set(c for c in cells if c[1] > edge - 3)
    else:
        edge = min(y for x, y in cells)
        gone = set(c for c in cells if c[1] < edge + 3)
    target["body"] -= gone
    target["line"] -= gone
    if target["head"] is not None:
        target["head"] = (target["head"][0] - dx * 3, target["head"][1] - dy * 3)

    if objs:
        # anything leaning on the retreating face follows it back
        face = set((cx + dx, cy + dy) for (cx, cy) in gone)
        pulled = []
        for o in objs:
            if o is target or o["colour"] == FIXED or o["dir"] is not None:
                continue          # only loose scenery follows the retreat
            if _occupied(o) & face:
                pulled.append(o)
        for o in pulled:
            cells = set((cx - dx * 3, cy - dy * 3) for cx, cy in _occupied(o))
            blocked = False
            if not _inside(cells):
                blocked = True
            for other in objs:
                if other is o or any(other is q for q in pulled):
                    continue
                if cells & _occupied(other):
                    blocked = True
            if not blocked:
                _shift(o, -dx, -dy)
    return True


def render(grid, objs, diamonds, boxes, n, level=0):
    g = [row[:] for row in grid]
    for y in range(H - 1):
        for x in range(W):
            if not _in_boxes(x, y, boxes):
                g[y][x] = BG
    for o in objs:
        for (x, y) in o["body"]:
            g[y][x] = o["colour"]
        for (x, y) in o["line"]:
            g[y][x] = AXIS
        if o["head"] is not None:
            g[o["head"][1]][o["head"][0]] = HEAD
    for (x, y) in diamonds:
        g[y][x] = HEAD
    b = _bar_after(n, level)
    for i in range(W):
        g[63][i] = INNER if i >= W - b else AXIS
    return g


def _near_half(grid, x, y, box):
    x0, y0, x1, y1 = box
    ax = [(cx, cy) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)
          if grid[cy][cx] == AXIS]
    if not ax:
        return False
    if len(set(c[0] for c in ax)) == 1:
        return x < ax[0][0]
    if len(set(c[1] for c in ax)) == 1:
        return y < ax[0][1]
    return False


def _active_half(grid, x, y, boxes):
    """only the mirror-image half of a control box (right of / below its
    3-coloured axis) actually fires; the other half is inert"""
    box = None
    for x0, y0, x1, y1 in boxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            box = (x0, y0, x1, y1)
    if box is None:
        return False
    x0, y0, x1, y1 = box
    ax = [(cx, cy) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)
          if grid[cy][cx] == AXIS]
    if not ax:
        return False
    axx = set(c[0] for c in ax)
    axy = set(c[1] for c in ax)
    if len(axx) == 1:
        return x > ax[0][0]
    if len(axy) == 1:
        return y > ax[0][1]
    return False


def predict(state, grid, action, x=None, y=None, level=None, entry_grid=None):
    n = state.get("n", 0) + 1
    lvl = level if level is not None else _cur_level()
    objs, diamonds, boxes = parse(grid)

    did = False
    if action == 6 and x is not None and 0 <= x < W and 0 <= y < H:
        # ANY pixel of a control box works, not just the coloured shapes:
        # far half of the axis = grow, near half = retract
        box = None
        for x0, y0, x1, y1 in boxes:
            if x0 <= x <= x1 and y0 <= y <= y1:
                box = (x0, y0, x1, y1)
                break
        if box is not None:
            x0, y0, x1, y1 = box
            colour = None
            for cy in range(y0, y1 + 1):
                for cx in range(x0, x1 + 1):
                    if grid[cy][cx] not in STRUCTURAL:
                        colour = grid[cy][cx]
                        break
                if colour is not None:
                    break
            half = _active_half(grid, x, y, boxes)
            near = _near_half(grid, x, y, box)
            for o in objs:
                if o["colour"] == colour and o["dir"] is not None:
                    if half:
                        did = grow(o, objs)
                    elif near:
                        did = shrink(o, objs)
                    break

    if not did:
        g = [row[:] for row in grid]
        b = _bar_after(n, lvl)
        for i in range(W):
            g[63][i] = INNER if i >= W - b else AXIS
        return g, {}, {"n": n, "level": lvl}

    g = render(grid, objs, diamonds, boxes, n, lvl)
    info = {}
    centres = diamond_centres(diamonds)
    heads = set(o["head"] for o in objs if o["head"] is not None)
    if centres and centres <= heads:
        info["level_up"] = True
    return g, info, {"n": n, "level": lvl}
