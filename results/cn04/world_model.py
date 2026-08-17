"""World model for cn04.

Frame: 64x64 px = 20x20 blocks of 3x3 at pixel offset (2,2); everything
outside is background.  Pixel row 0, cols 16..47, is a progress bar with
round(32*n/BUDGET[level]) cells filled, n = actions taken this level.

A level holds several rigid SHAPES: a body plus colour-8 "tips".  Exactly one
shape is selected; 1/2/3/4 move it a block, 5 rotates it 90 CW about its
bbox top-left, 6 clicks (selects the shape under the cursor, or deselects it
if it was already selected).  Shapes never collide - they may overlap freely.  Two tips on the same block are JOINED and drawn colour 3; joins
are not rigid.  The level is cleared once every tip is joined.

Rendering differs per level:
  MODE 'all'  (levels 0,1): every shape is drawn in its own colour with its
      tips visible; the selected one is drawn in colour 0 instead.
  MODE 'one'  (level 2): only the selected shape is drawn in its own colour
      with tips; the others are drawn flat in colour 4, tips hidden.

State is rebuilt by replaying LEVEL_ACTIONS from the level entry, which is
exact - a mid-level frame reveals neither the action counter nor hidden tips.
"""

OFF = 2
N = 20
BARX = 16
BARW = 32
DEAD = 0x4          # flat colour of an unselected shape in MODE 'one'

BUDGET = {0: 74, 1: 100, 2: 128, 3: 128, 4: 150}   # bracketed to (149.3, 153.6] by ticks at n=3,8,12
MODE = {0: 'all', 1: 'all', 2: 'one', 3: 'one', 4: 'one'}

# actions taken so far in the current level (regenerated from the run log)
LEVEL_ACTIONS = [
    (6, 51, 18),
    (6, 9, 39),
    (6, 51, 54),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (6, 27, 18),
    (4, None, None),
    (6, 48, 12),
    (2, None, None),
    (2, None, None),
    (2, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (3, None, None),
    (5, None, None),
    (5, None, None),
    (5, None, None),
    (6, 6, 39),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (1, None, None),
    (4, None, None),
    (4, None, None),
    (4, None, None),
    (4, None, None),
    (4, None, None),
    (6, 27, 27),
    (5, None, None),
    (3, None, None),
    (6, 30, 24),
]

LEVEL_ENTRY = {
    0: [
        "aaaaaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
        "aaa00000aaaaaaaaaaaa",
        "aaa0aaa0aaaaaaaaaaaa",
        "aaa00a00aaaaaaaaaaaa",
        "aaaa0a0aaaaaaaaaaaaa",
        "aaaa0a0aaaaaaaaaaaaa",
        "aaaa8a8aaaaaaaaaaaaa",
        "aaaaaaaaaaaaaeeeaaaa",
        "aaaaaaaaaaaaaeaeaaaa",
        "aaaaaaaaaaaa8eaeaaaa",
        "aaaaaaaaaaaaaeaeaaaa",
        "aaaaaaaaaaaa8eaeaaaa",
        "aaaaaaaaaaaaaeaeaaaa",
        "aaaaaaaaaaaaaeeeaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
        "aaaaaaaaaaaaaaaaaaaa",
    ],
    1: [
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "ccc000cccccccccccccc",
        "ccc0c0cccccccc8ecccc",
        "ccc0c0cccccccccecccc",
        "ccc0c8ccccccccce8ccc",
        "ccc0cccccccccccecccc",
        "ccc08cccccccccce8ccc",
        "cccccccccccc8ccecccc",
        "cccccccccccceeeecccc",
        "cccccccbbbcccccccccc",
        "ccccc8cbcb8ccccccccc",
        "cccccbbbcbcccccccccc",
        "cccc8bcccbcccccccccc",
        "cccccbbbcbcccccccccc",
        "cccccccbbbcccccc8c8c",
        "cccccccc8ccccccc9c9c",
        "cccccccccccccccc999c",
        "cccccccccccccccccccc",
    ],
    2: [
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "ccccccccccccccc4cccc",
        "ccccee8ccc444444cccc",
        "cccceccccccccccccccc",
        "cceeeccccccccccccccc",
        "cceccccccccccccccccc",
        "cceeeccccccccccccccc",
        "cccceccccc4ccccccccc",
        "ccccee8cc444cccccccc",
        "ccccccccc4c4cccccccc",
        "ccccccccc4c4cccccccc",
        "ccccccccc4c4444ccccc",
        "ccccccccc4cccc44cccc",
        "ccccccccc444444ccccc",
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
        "cccccccccccccccccccc",
    ],
    3: [
        "99999999999999999999",
        "99999999999999999999",
        "99999999999999999999",
        "99aaaaaa999999999999",
        "99a9999a999999999999",
        "99a9aa9a999999999999",
        "99a9a99a999449449999",
        "99a9aaaa999949499999",
        "99a9a998999949499999",
        "99a99999999944499999",
        "99899999999999999999",
        "99999999999999999999",
        "99999999999999999999",
        "99999999999999444499",
        "99999999999999949499",
        "99999444999999949499",
        "99999999999999949499",
        "99999999999999949499",
        "99999999999999444499",
        "99999999999999999999",
    ],
    4: [
        "ffffffffffffffffffff",
        "fffffffffffffffff4ff",
        "fffffffffffffff4f4ff",
        "fffffffffffffff4f4ff",
        "ffffffffb8fffff4f4ff",
        "fffffff8bffffff444ff",
        "ffffffffbb8fffffffff",
        "ffffffff0fffffffffff",
        "ffffffffffffffffffff",
        "ffffffffffffffffffff",
        "ffffffffffffffffffff",
        "ffffffffffffffffffff",
        "f444ffffffffffffffff",
        "f4ffffffffffffffffff",
        "f444ffffffffffffffff",
        "f4fffffffffffff4ffff",
        "f444fffffffffff4f4ff",
        "fffffffffffffff444ff",
        "ffffffffffffffffffff",
        "ffffffffffffffffffff",
    ],
}

# MODE 'one' levels hide the unselected shapes' tips, so their shapes are
# written out explicitly (tips learnt by clicking each shape once).
HIDDEN_SHAPES = {2: [
    (0xe, [(4, 4), (5, 4), (4, 5), (2, 6), (3, 6), (4, 6), (2, 7), (2, 8),
           (3, 8), (4, 8), (4, 9), (4, 10), (5, 10)], [(6, 4), (6, 10)]),
    (0xb, [(11, 4), (12, 4), (13, 4), (14, 4), (15, 4)], [(10, 4), (15, 3)]),
    (0xf, [(9, 10), (10, 10), (11, 10), (9, 11), (11, 11), (9, 12), (11, 12),
           (9, 13), (11, 13), (12, 13), (13, 13), (14, 13), (9, 14), (14, 14),
           (9, 15), (10, 15), (11, 15), (12, 15), (13, 15), (14, 15)],
     [(10, 9), (15, 14)]),
], 3: [
    (0xa, [(2,3),(3,3),(4,3),(5,3),(6,3),(7,3),(2,4),(7,4),(2,5),(4,5),(5,5),
           (7,5),(2,6),(4,6),(7,6),(2,7),(4,7),(5,7),(6,7),(7,7),(2,8),(4,8),
           (2,9)], [(7, 8), (2, 10)]),
    (0xe, [(12,6),(14,6),(12,7),(14,7),(12,8),(14,8),(12,9),(13,9),(14,9)],
     [(11, 6), (15, 6)]),
    (0xb, [(6, 15)], [(5, 15), (7, 15)]),
    (0xc, [(15,13),(16,13),(17,13),(15,14),(17,14),(15,15),(17,15),(15,16),
           (17,16),(15,17),(17,17),(15,18),(16,18),(17,18)],
     [(14, 13), (14, 18)]),
], 4: [
    # b's fourth tip is drawn 0, not 8 (see ZERO_TIPS)
    (0xb, [(8,4),(8,5),(8,6),(9,6)], [(9,4),(7,5),(10,6),(8,7)]),
    (0xa, [(17,2),(15,3),(17,3),(15,4),(17,4),(15,5),(16,5),(17,5)],
     [(17,1),(15,2)]),
    (0xe, [(1,12),(2,12),(1,13),(1,14),(2,14),(1,15),(1,16),(2,16)],
     [(3,12),(3,14),(3,16)]),
    (0xc, [(15,16),(15,17),(16,17),(17,17)], [(15,15),(17,16)]),
]}

# tips drawn in colour 0 instead of 8, as (level, shape index, tip index)
ZERO_TIPS = {(4, 0, 3)}

SELECTED_INTRINSIC = 0xf     # colour a level-0/1 shape reverts to when it
                             # stops being the selected (colour-0) one


def _level():
    try:
        return CURRENT_LEVEL
    except NameError:
        return 0


def _barfill(n):
    b = BUDGET.get(_level(), 100)
    return min(BARW, (64 * n + b) // (2 * b))       # round(32n/b)


def to_blocks(grid):
    return [[grid[OFF + 3 * by][OFF + 3 * bx] for bx in range(N)]
            for by in range(N)]


def render(blocks, bgcol, filled):
    g = [[bgcol] * 64 for _ in range(64)]
    for by in range(N):
        for bx in range(N):
            v = blocks[by][bx]
            for dy in range(3):
                for dx in range(3):
                    g[OFF + 3 * by + dy][OFF + 3 * bx + dx] = v
    for i in range(BARW):
        g[0][BARX + i] = 0x0 if i < filled else 0x4
    return g


def _bgcol(blocks):
    counts = {}
    for row in blocks:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _canon(level):
    """(bgcol, shapes, selected index) at the level entry"""
    blocks = [[int(c, 16) for c in r] for r in LEVEL_ENTRY[level]]
    bgcol = _bgcol(blocks)
    if level in HIDDEN_SHAPES:
        shapes = []
        for i, (c, b, t) in enumerate(HIDDEN_SHAPES[level]):
            zero = set(t[j] for j in range(len(t))
                       if (level, i, j) in ZERO_TIPS)
            shapes.append({'col': c, 'body': set(b), 'tips': set(t),
                           'zero': zero})
        return bgcol, shapes, 0
    bodies = {}
    for by in range(N):
        for bx in range(N):
            v = blocks[by][bx]
            if v == bgcol or v == 0x8:
                continue
            key = SELECTED_INTRINSIC if v == 0x0 else v
            if key not in bodies:
                bodies[key] = set()
            bodies[key].add((bx, by))
    shapes, sel = [], 0
    for col in sorted(bodies):
        body = bodies[col]
        tips = set()
        for by in range(N):
            for bx in range(N):
                if blocks[by][bx] != 0x8:
                    continue
                for nb in ((bx + 1, by), (bx - 1, by), (bx, by + 1),
                           (bx, by - 1)):
                    if nb in body:
                        tips.add((bx, by))
        if col == SELECTED_INTRINSIC:
            sel = len(shapes)
        shapes.append({'col': col, 'body': body, 'tips': tips, 'zero': set()})
    return bgcol, shapes, sel


MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}


def _step(shapes, sel, action, x, y):
    """pure geometry: returns (shapes, sel) after one action"""
    shapes = [{'col': s['col'], 'body': set(s['body']), 'tips': set(s['tips']),
               'zero': set(s.get('zero') or ())} for s in shapes]
    if action == 6 and x is not None:
        bx, by = (x - OFF) // 3, (y - OFF) // 3
        here = [i for i, s in enumerate(shapes)
                if (bx, by) in s['body'] or (bx, by) in s['tips']]
        if here:
            # where shapes overlap the click picks one that is not already
            # selected; clicking the sole shape under the cursor deselects it
            other = [i for i in here if i != sel]
            sel = other[-1] if other else None
        return shapes, sel
    if sel is None or (action not in MOVES and action != 5):
        return shapes, sel
    cur = shapes[sel]
    if action in MOVES:
        dx, dy = MOVES[action]
        body = set((p[0] + dx, p[1] + dy) for p in cur['body'])
        tips = set((p[0] + dx, p[1] + dy) for p in cur['tips'])
        zero = set((p[0] + dx, p[1] + dy) for p in cur['zero'])
    else:
        allc = cur['body'] | cur['tips']
        x0 = min(p[0] for p in allc)
        y0 = min(p[1] for p in allc)
        h = max(p[1] for p in allc) - y0 + 1
        body = set((x0 + h - 1 - (p[1] - y0), y0 + (p[0] - x0))
                   for p in cur['body'])
        tips = set((x0 + h - 1 - (p[1] - y0), y0 + (p[0] - x0))
                   for p in cur['tips'])
        zero = set((x0 + h - 1 - (p[1] - y0), y0 + (p[0] - x0))
                   for p in cur['zero'])
    # shapes do not collide at all - they may overlap freely (seen in L4);
    # only the grid boundary stops a move
    if all(0 <= p[0] < N and 0 <= p[1] < N for p in body | tips):
        shapes[sel] = {'col': cur['col'], 'body': body, 'tips': tips,
                       'zero': zero}
    return shapes, sel


def _draw(shapes, sel, bgcol, mode):
    blocks = [[bgcol] * N for _ in range(N)]
    tipcount = {}       # only colour-8 tips join; colour-0 tips never do
    for s in shapes:
        for p in s['tips']:
            if p not in s.get('zero', ()):
                tipcount[p] = tipcount.get(p, 0) + 1
    order = [i for i in range(len(shapes)) if i != sel]
    if sel is not None:
        order.append(sel)
    for i in order:
        s = shapes[i]
        if mode == 'one' and i != sel:
            for p in s['body'] | s['tips']:
                blocks[p[1]][p[0]] = DEAD
            continue
        col = 0x0 if (mode == 'all' and i == sel) else s['col']
        for p in s['body']:
            blocks[p[1]][p[0]] = col
        for p in s['tips']:
            if tipcount.get(p, 0) > 1:
                blocks[p[1]][p[0]] = 0x3
            else:
                blocks[p[1]][p[0]] = 0x0 if p in s.get('zero', ()) else 0x8
    return blocks


def _solved(shapes):
    """cleared when every colour-8 tip sits on another shape's colour-8 tip"""
    for i, s in enumerate(shapes):
        mine = set(s['tips']) - set(s.get('zero') or ())
        others = set()
        for j, o in enumerate(shapes):
            if j != i:
                others |= set(o['tips']) - set(o.get('zero') or ())
        if not mine or not mine <= others:
            return False
    return True


def init_state(entry_grid, level=None):
    lvl = _level()
    bgcol, shapes, sel = _canon(lvl)
    blocks = to_blocks(entry_grid)
    entry = [[int(ch, 16) for ch in r] for r in LEVEL_ENTRY[lvl]]
    n = 0
    if blocks != entry:
        for a, x, y in LEVEL_ACTIONS:
            shapes, sel = _step(shapes, sel, a, x, y)
            n += 1
    return {'n': n, 'bg': bgcol, 'shapes': shapes, 'sel': sel}


def predict(state, grid, action, x=None, y=None):
    lvl = _level()
    n = state['n'] + 1
    shapes, sel = _step(state['shapes'], state['sel'], action, x, y)
    solved = _solved(shapes)
    flags = {'level_up': solved, 'dead': False, 'win': False}
    nxt = {'n': n, 'bg': state['bg'], 'shapes': shapes, 'sel': sel}
    if solved:
        nx = LEVEL_ENTRY.get(lvl + 1)
        if nx is None:
            return grid, flags, nxt
        blocks = [[int(c, 16) for c in r] for r in nx]
        return render(blocks, _bgcol(blocks), 0), flags, nxt
    out = render(_draw(shapes, sel, state['bg'], MODE.get(lvl, 'all')),
                 state['bg'], _barfill(n))
    return out, flags, nxt
