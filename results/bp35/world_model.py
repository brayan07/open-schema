"""bp35 world model.

GEOMETRY
  The world is a grid of 6x6-pixel tiles, 7 columns wide (C2..C8; C0,C1,C9,C10
  are permanent void).  Tile (R,C)'s inner 5x5 is world rows 6R+1..6R+5, cols
  6C+1..6C+5; the rows/cols that are multiples of 6 are separators.  The camera
  scrolls VERTICALLY only and always draws the player's tile at a fixed view
  row that depends on the gravity direction:
      gravity UP  (default): the player's tile inner starts at view row 37
      gravity DOWN (flipped): ...................................at view row 27
  Cols are never scrolled.  Frame row 63 is a per-level action counter
  (leftmost n pixels colour 15).

TILE KINDS
  'a' MASS   colour 10 -- the medium the player swims in
  '.' VOID   colour 5 with a colour-3 dot texture at (r%6,c%6) in
             {(1,2),(4,1),(5,4)} -- blocks
  'B' BOX    rounded 5x5 of colour 14, colour-3 corners -- blocks
  'C' CYAN   same shape, colour 12 -- blocks
  'A' AZURE  same shape, colour 8  -- blocks; clicking one FLIPS GRAVITY
  A separator pixel is colour 10 iff every tile it touches is MASS, else 5.

SPRITES  (live in a tile's inner cols dc1..dc3, drawn over the terrain)
  player  colour 9 body + colour 11 nose on the facing side (4 rows)
  target  colour 7 diamond (3 rows)   -- entering its tile completes the level
  killer  colour 15 block over an 11/0/11 foot (5 rows) -- entering kills
  xmark   colour 12 X (no halo)       -- residue of a dissolved cyan block
  Every sprite except the X punches its shape DILATED by 1 pixel to plain 5,
  which is why a sprite one tile off-screen still marks the frame's edge row.

DYNAMICS
  3 = step left, 4 = step right (into a MASS tile only; blocked = stay, but the
      facing still flips).  7 behaves like 4 wherever it has been tried.
  6 = click ANY tile on screen (range is unlimited, diagonals included):
      BOX -> MASS; CYAN -> MASS + an X decal; an X decal -> back to CYAN;
      AZURE -> gravity flips and the block is consumed (becomes plain MASS),
      so each azure block is a one-shot switch.  Any other click is a no-op.
  0 = RESET: restart the level (restores blocks, zeroes the counter).  The
      harness never model-checks a RESET.
  After EVERY action the player is carried along the gravity direction while
  the next tile that way is MASS.  Being carried into a killer is fatal, and
  buoyancy is automatic, so never open a channel that leads into one.
"""

BG, DOT, MASS, BOX, CNT = 5, 3, 10, 14, 15
CYAN, AZURE = 12, 8
TERRAIN = {BG, DOT, MASS, BOX}
BLOCKS = {'B': BOX, 'C': CYAN, 'A': AZURE}
COLS = range(0, 11)     # C0..C10; levels differ in how many they use
SLOTS = range(-1, 13)       # view tile slots that can touch the frame
CURRENT_LEVEL = 0           # the harness overwrites this module global

GOAL, HAZARD = 7, 15
HALOED = {7, 9, 15}         # sprites that punch a halo; the X decal does not


def _top(grav):
    """view row at which the player's tile inner starts"""
    return 27 if grav > 0 else 37


def _ey(y, grav):
    """y re-based so that the usual 6k+1 tile phase applies"""
    return y + 37 - _top(grav)


def _rows(slot, grav):
    """the 5 view rows of the inner of the tile in this slot"""
    base = _top(grav) + 6 * (slot - 6)
    return [base + d for d in range(5)]


# --------------------------------------------------------------- geometry ---
def _dilate(sprite):
    return {(dr + i, dc + j) for dr, dc in sprite
            for i in (-1, 0, 1) for j in (-1, 0, 1)}


def _draw(g, slot, C, sprite, grav):
    r0, c0 = _rows(slot, grav)[0], 6 * C + 1
    cells = (_dilate(sprite) if set(sprite.values()) & HALOED else set())
    for dr, dc in cells:
        if 0 <= r0 + dr < 63 and 0 <= c0 + dc < 64:
            g[r0 + dr][c0 + dc] = BG
    for (dr, dc), v in sprite.items():
        if 0 <= r0 + dr < 63 and 0 <= c0 + dc < 64:
            g[r0 + dr][c0 + dc] = v


# ---------------------------------------------------------------- reading ---
def _sprites(grid, grav):
    """{(slot, col): {(dr,dc): colour}} for every non-terrain sprite"""
    out = {}
    for r in range(63):
        ey = _ey(r, grav)
        if ey % 6 == 0:
            continue
        for c in range(64):
            if c % 6 == 0:
                continue
            if grid[r][c] not in TERRAIN:
                out.setdefault((ey // 6, c // 6), {})[(ey % 6 - 1, c % 6 - 1)] = grid[r][c]
    return out


def find_glyph(grid):
    """(slot, col, facing, gravity) or None on a death frame.

    Gravity is read off the camera: the player's sprite starts at view row 37
    when gravity pulls up and at 27 when it has been flipped.
    """
    ps = [(r, c) for r in range(63) for c in range(64) if grid[r][c] == 9]
    if not ps:
        return None
    top = min(r for r, _ in ps)
    grav = 1 if top == 27 else -1
    minc = min(c for r, c in ps if r == top + 1)
    C = (minc - 2) // 6
    nose = [c for r, c in ps if False]
    bs = [c for r in range(63) for c in range(64)
          if grid[r][c] == 11 and 6 * C + 1 <= c <= 6 * C + 5
          and top <= r <= top + 3]
    facing = 1 if max(bs) == 6 * C + 4 else -1
    return 6, C, facing, grav


def counter(grid):
    return sum(1 for v in grid[63] if v == CNT)


def _kind(grid, slot, C, grav):
    vals = set()
    for r in _rows(slot, grav):
        if 0 <= r < 63:
            for c in range(6 * C + 1, min(6 * C + 6, 64)):
                vals.add(grid[r][c])
    if not vals:
        return None
    if BOX in vals:
        return 'B'
    if CYAN in vals and not vals - {CYAN, DOT, BG}:
        return 'C'
    if AZURE in vals and not vals - {AZURE, DOT, BG}:
        return 'A'
    if vals <= {MASS} or (vals - TERRAIN):
        return 'a'
    return '.'


def _infer_offset(state, grid, grav):
    """recover abs_row = slot + offset by matching visible tiles to the map"""
    obs = {}
    for slot in range(0, 11):
        for c in COLS:
            k = _kind(grid, slot, c, grav)
            if k:
                obs[(slot, c)] = k
    best = None
    for o in range(-40, 41):
        hits = 0
        for (slot, c), k in obs.items():
            want = state['map'].get((slot + o, c))
            if want is None:
                continue
            # blocks may have been dissolved, and a dissolved cyan tile may
            # have been toggled back, so both directions are tolerated
            if want == k or (want in BLOCKS and k == 'a') or (
                    want == 'a' and k in ('C', 'A')):
                hits += 1
            else:
                hits = -1
                break
        if hits < 0:
            continue
        key = (hits, -abs(o - state.get('off', 0)))
        if best is None or key > best[0]:
            best = (key, o)
    return best[1] if best else state.get('off', 0)


def _learn(state, grid, off, grav):
    for slot in SLOTS:
        for c in COLS:
            k = _kind(grid, slot, c, grav)
            if k:
                state['map'][(slot + off, c)] = k
    for (slot, C), spr in _sprites(grid, grav).items():
        # a whole cyan/azure BLOCK is terrain, not a sprite; only record
        # sprites that sit on top of mass (player, target, killer, X decal).
        # Only learn from tiles that are FULLY on screen -- a clipped sprite
        # would otherwise overwrite a complete one with a truncated copy.
        rows = _rows(slot, grav)
        if (9 not in spr.values() and _kind(grid, slot, C, grav) == 'a'
                and rows[0] >= 0 and rows[-1] <= 62 and 6 * C + 5 < 64):
            state['objects'][(slot + off, C)] = spr


# ---------------------------------------------------------------- drawing ---
def _render(state, n):
    m, grav = state['map'], state['grav']
    off = state['row'] - 6
    g = [[BG] * 64 for _ in range(63)] + [[0] * 64]

    def tile(slot, c):
        return m.get((slot + off, c), '.')

    for r in range(63):
        ey = _ey(r, grav)
        for c in range(64):
            rs, cs = ey % 6 == 0, c % 6 == 0
            if not rs and not cs:
                k = tile(ey // 6, c // 6)
                if k == 'a':
                    g[r][c] = MASS
                elif k in BLOCKS:
                    dr, dc = ey % 6 - 1, c % 6 - 1
                    g[r][c] = DOT if (dr in (0, 4) and dc in (0, 4)) else BLOCKS[k]
                else:
                    g[r][c] = DOT if (ey % 6, c % 6) in ((1, 2), (4, 1), (5, 4)) else BG
            else:
                if rs and cs:
                    ns = [(ey // 6 - 1, c // 6 - 1), (ey // 6 - 1, c // 6),
                          (ey // 6, c // 6 - 1), (ey // 6, c // 6)]
                elif rs:
                    ns = [(ey // 6 - 1, c // 6), (ey // 6, c // 6)]
                else:
                    ns = [(ey // 6, c // 6 - 1), (ey // 6, c // 6)]
                g[r][c] = MASS if all(tile(*t) == 'a' for t in ns) else BG

    for (ar, ac), spr in state['objects'].items():
        if -1 <= ar - off <= 12:
            _draw(g, ar - off, ac, spr, grav)
    _draw(g, 6, state['col'], _player(state['facing']), grav)
    for i in range(min(n, 64)):
        g[63][i] = CNT
    return g


def _player(facing):
    s = {(0, 2): 9, (1, 1): 9, (1, 2): 9, (1, 3): 11,
         (2, 1): 9, (2, 2): 9, (2, 3): 11, (3, 2): 9}
    return s if facing > 0 else {(dr, 4 - dc): v for (dr, dc), v in s.items()}


# ------------------------------------------------------------------ model ---
def init_state(entry_grid):
    level = CURRENT_LEVEL or 0
    m = {(r, i): k          # map strings are indexed from column 0
         for r, row in LEVEL_MAPS.get(level, {}).items()
         for i, k in enumerate(row) if k != '?'}
    objs = {rc: SPRITES[name]
            for rc, name in LEVEL_OBJECTS.get(level, {}).items()}
    st = {'map': m, 'objects': objs, 'level': level, 'grav': -1,
          'row': 6, 'col': 3, 'facing': 1, 'off': 0, 'dissolved': []}
    who = find_glyph(entry_grid)
    _, C, f, grav = who if who else (6, 3, 1, -1)
    st['grav'], st['col'], st['facing'] = grav, C, f
    st['row'] = 6 + _infer_offset(st, entry_grid, grav)
    st['pristine'] = dict(m)
    # Only a mid-run frame carries my edits; the level's own entry frame is
    # pristine (that is what the backtest replays from).
    entry = LEVEL_ENTRY_ROWS.get(level)
    at_entry = entry is not None and all(
        ''.join('%x' % v for v in entry_grid[r]) == entry[r] for r in range(64))
    if not at_entry:
        st['map'].update(LEVEL_EDITS.get(level, {}))
    _learn(st, entry_grid, st['row'] - 6, grav)
    st['start'] = LEVEL_STARTS.get(level, (st['row'], C, f))
    st['start_map'] = dict(st['map'])
    # pristine was copied before LEVEL_EDITS were applied, so it is what a
    # RESET restores (st['map'] IS m, so m itself carries the edits by now)
    st['start_map'].update(st['pristine'])
    st['start_objects'] = dict(st['objects'])
    if not who:                    # death frame: no player to locate
        st['row'], st['col'], st['facing'] = st['start']
    return st


def _settle(st):
    """carry the player along gravity; returns every tile visited on the way"""
    path = [(st['row'], st['col'])]
    while st['map'].get((st['row'] + st['grav'], st['col'])) == 'a':
        st['row'] += st['grav']
        path.append((st['row'], st['col']))
    return path


def predict(state, grid, action, x=None, y=None):
    st = dict(state)                       # must stay functional for bfs
    st['map'] = dict(state['map'])
    st['objects'] = dict(state['objects'])
    st['dissolved'] = list(state['dissolved'])

    who = find_glyph(grid)
    if who:
        _, C, f, grav = who
        st['grav'], st['col'], st['facing'] = grav, C, f
        st['off'] = _infer_offset(st, grid, grav)
        st['row'] = 6 + st['off']
        _learn(st, grid, st['off'], grav)

    n = counter(grid) + 1
    info = {}
    path = [(st['row'], st['col'])]
    if action == 0:
        st['row'], st['col'], st['facing'] = st['start']
        st['grav'] = -1
        st['map'] = dict(st['start_map'])
        st['objects'] = dict(st['start_objects'])
        st['dissolved'] = []
    elif action in (3, 4, 7):
        d = -1 if action == 3 else 1
        if st['map'].get((st['row'], st['col'] + d)) == 'a':
            st['col'] += d
        st['facing'] = d
        path = _settle(st)
    elif action == 6 and x is not None:
        t = (st['row'] + _ey(y, st['grav']) // 6 - 6, x // 6)
        k = st['map'].get(t)
        if k in ('B', 'C'):
            st['map'][t] = 'a'
            st['dissolved'].append(list(t))
            st['objects'].pop(t, None)
            if k == 'C':
                st['objects'][t] = SPRITES['xmark']
        elif k == 'A':
            st['grav'] = -st['grav']     # single use: the block is consumed
            st['map'][t] = 'a'
            st['dissolved'].append(list(t))
            st['objects'].pop(t, None)
        elif k == 'a' and CYAN in st['objects'].get(t, {}).values():
            st['map'][t] = 'C'
            del st['objects'][t]
        path = _settle(st)

    # collisions are checked along the whole travel path, not just where we
    # stop: level 3's target sits mid-shaft with solid mass on both sides, so
    # it can only ever be crossed, never landed on.
    for cell in path:
        colours = set(st['objects'].get(cell, {}).values())
        if HAZARD in colours:
            return None, {'dead': True}, st
        if GOAL in colours:
            info['level_up'] = True
            break
    if info.get('level_up'):
        nxt = LEVEL_ENTRY_ROWS.get(st['level'] + 1)
        if nxt is not None:
            return [[int(ch, 16) for ch in row] for row in nxt], info, st
    return _render(st, n), info, st


LEVEL_ENTRY_ROWS = {}
# Tiles I have edited with clicks since the last RESET, per level.  init_state
# only ever sees one frame, so edits that have scrolled off-screen would
# otherwise be forgotten; LEVEL_MAPS stays pristine so RESET can restore it.
LEVEL_EDITS = {
    5: {(5, 6): 'a'},
    4: {(6, 8): 'a', (10, 6): 'a', (15, 8): 'a', (23, 8): 'a',
        (15, 3): 'C', (15, 4): 'C', (3, 9): 'a', (3, 8): 'a', (3, 7): 'a'},
}

LEVEL_MAPS = {
    5: {-10: '????...aa??', -9: '....aaaaa..', -8: '....a......',
        -7: '....aaaaa..', -6: '..aaaaaaa..', -5: '..aaaaaaa..', -4: '..aaaaCaa..',
        -3: '..aaaaaaa..', -2: '..aaaaaaa..', -1: '......a....', 0: '......a....', 1: '..aaaaaaa..',
        2: '..aaaaa.a..', 3: '..aaa...a..', 4: '..aaaaaaa..',
        5: '......A....', 6: '..aaaaaaa..', 7: '..aaaaaaa..',
        8: '..aaaaaaa..', 9: '..aaaaaaa..', 10: '........a..',
        11: '........a..', 12: '........a..', 13: '.aaa.aaaa..',
        14: '.aaaAaaaa..', 15: '...........', 16: '...........',
        17: '...........', 18: '...........', 19: '...........'},
    0: {-11: '.........', -10: '..aaaaaaa', -9: '..aaaaaaa', -8: '.....BBB.',
        -7: '..aaaaaaa', -6: '..aaaaaaa', -5: '..aaBBBaa', -4: '..aaaaaaa',
        -3: '..aaaaaaa', -2: '..BBB....', -1: '..BBBaaaa',
        0: '..BBBaaaa', 1: '.....aaaa', 2: '.....BBBB', 3: '..aaaaaaa',
        4: '..aaaaaaa', 5: '.......a.', 6: '..aaaaaaa', 7: '..aaaaaaa',
        8: '..aaaaaaa', 9: '..aaaaaaa', 10: '..aaaaaaa'},
    4: {0: '...........', 1: '....aaaaaa.', 2: '....aaaBBB.', 3: '....aaaBBB.',
        4: '.........a.', 5: '.........a.', 6: '..aaaaaaAa.', 7: '..aaaaaa...',
        8: '..aaaaaa...', 9: '......aa...', 10: '......BB...',
        11: '..aaaaaa...', 12: '..a...aaaa.', 13: '..a...aaaa.',
        14: '..aaa.BBaa.', 15: '..aaa...BB.', 16: '..aaaaaaaa.',
        17: '..aaaaaaaa.', 18: '...aaaaa...', 19: '...aa......',
        20: '...BB......', 21: '...aa......', 22: '...aa......',
        23: '........A..'},
    3: {-1: '.....A...', 0: '.........', 1: '..aaaaaaa', 2: '..aaaaaaa', 3: '........a',
        4: '.......aa', 5: '......aaa', 6: '..aaaaaaa', 7: '..aaaaaaa',
        8: '..aaaaaaa', 9: '..BB.....', 10: '..aaaaaaa', 11: '..aaaBBBB',
        12: '..aaaaaaa', 13: '..aaaa.aa', 14: '.......aa', 15: '...A.A.BB',
        16: '.......BB', 17: '..aaaaaaa', 18: '..aaaaaaa', 19: '..aaaaaaa',
        20: '..aaaaaaa', 21: '..aaaaaaa', 22: '.........', 23: '....A....',
        24: '.........', 25: '.........', 26: '.........'},
    2: {-21: '.........', -20: '.........', -19: '.........',
        -18: '..aaaaaaa', -17: '..aaaaaaa', -16: '..CCCCCCC',
        -15: '..aaaCaaa', -14: '..aaaCaaa', -13: '..aa.....',
        -12: '..aaaaa..', -11: '..aaaaa..', -10: '..CCaaa..', -9: '..aaaaaaa', -8: '..aaaaaaa', -7: '.......aa',
        -6: '.....aaaa', -5: '.....aaaa', -4: '...aaCCaa', -3: '..aaaaaaa', -2: '..a....aa',
        -1: '..aaaaaaa', 0: '..aaaaaaa', 1: '..aaaa...', 2: '..aaaaaaa',
        3: '..aaaaaaa', 4: '..aaaaaaa', 5: '......BBB', 6: '..aaaCaaa',
        7: '..aaaCaaa', 8: '..aaaaaaa', 9: '..aaaaaaa', 10: '..aaaaaaa'},
    1: {-26: '.........', -25: '.........', -24: '..aaaaaaa', -23: '..aaaaaaa',
        -22: '..BBBBBBB', -21: '..aaaaaBB', -20: '.....aaaa', -19: '..aaaaaaa', -18: '..aaaaaaa', -17: '...B....B',
        -16: '...B....B', -15: '...BBBBBB', -14: '...B.....',
        -13: '..aaaaaaa', -12: '..aaaaaaa', -11: '..BBB....', -10: '..aaaaaaa',
        -9: '..aaaaaaa', -8: '.....B...', -7: '.....B...', -6: '..aaaaaaa', -5: '..aaaaaaa',
        -4: '..aaaaaaa', -3: '..B...BBB', -2: '..BBBBaaa',
        -1: '..BBBBaaa', 0: '......aaa', 1: '..aaa.aaa', 2: '..aaa.aaa', 3: '..aaa.aaa',
        4: '..BBBBBBB', 5: '..BBBBBBB', 6: '..aaaaaaa', 7: '..aaaaaaa',
        8: '..aaaaaaa', 9: '..aaaaaaa', 10: '..aaaaaaa'},
}

LEVEL_OBJECTS = {0: {(-10, 3): 'target'},
                 1: {(-6, 6): 'killer', (-6, 7): 'killer',
                     (-6, 8): 'killer', (-10, 8): 'killer',
                     # a killer wall at abs -13 with a single gap at col 3
                     (-13, 2): 'killer', (-13, 4): 'killer',
                     (-13, 5): 'killer', (-13, 6): 'killer',
                     (-13, 7): 'killer', (-13, 8): 'killer',
                     (-19, 2): 'killer', (-19, 3): 'killer',
                     (-19, 4): 'killer', (-24, 6): 'killer',
                     (-24, 7): 'killer', (-24, 8): 'killer',
                     (-24, 5): 'target'},
                 2: {(-1, 3): 'killer', (-1, 4): 'killer',
                     (-1, 5): 'killer', (-1, 6): 'killer',
                     (-6, 5): 'killer', (-6, 6): 'killer',
                     (-5, 5): 'xmark', (-5, 6): 'xmark',
                     (-10, 4): 'xmark', (-10, 5): 'xmark',
                     (-10, 6): 'xmark', (-12, 4): 'killer',
                     (-12, 5): 'killer', (-12, 6): 'killer',
                     (-15, 7): 'target',
                     (-18, 2): 'killer', (-18, 3): 'killer',
                     (-18, 4): 'killer', (-18, 5): 'killer',
                     (-18, 6): 'killer', (-18, 7): 'killer',
                     (-18, 8): 'killer'},
                 5: {(14, 2): 'target', (-7, 5): 'killer', (-7, 6): 'killer',
                     (-7, 7): 'killer', (-7, 8): 'killer', (-4, 2): 'xmark', (-4, 3): 'xmark',
                     (-4, 4): 'xmark', (-4, 5): 'xmark', (-4, 7): 'xmark',
                     (-4, 8): 'xmark', (-2, 2): 'killer_up', (-2, 3): 'killer_up',
                     (-2, 4): 'killer_up', (-2, 5): 'killer_up', (1, 2): 'killer', (1, 3): 'killer', (1, 4): 'killer',
                     (3, 2): 'xmark', (3, 3): 'xmark', (3, 4): 'xmark',
                     (8, 6): 'xmark', (8, 7): 'xmark',
                     (9, 2): 'killer_up', (9, 3): 'killer_up',
                     (9, 4): 'killer_up', (9, 5): 'killer_up',
                     (9, 6): 'killer_up', (9, 7): 'killer_up'},
                 4: {(1, 5): 'target', (1, 7): 'killer', (1, 8): 'killer',
                     (1, 9): 'killer', (8, 2): 'killer_up',
                     (8, 3): 'killer_up', (8, 4): 'killer_up',
                     (8, 5): 'killer_up',
                     (12, 8): 'killer', (12, 9): 'killer',
                     (14, 3): 'killer', (14, 4): 'killer',
                     (15, 3): 'xmark', (15, 4): 'xmark',
                     (22, 3): 'killer_up', (22, 4): 'killer_up'},
                 3: {(6, 2): 'killer', (6, 3): 'killer',
                     (17, 2): 'killer', (17, 3): 'killer',
                     (17, 5): 'killer', (17, 6): 'killer',
                     (19, 4): 'target'}}
LEVEL_OBJECTS[3][(23, 4)] = 'azure-marker-placeholder'
del LEVEL_OBJECTS[3][(23, 4)]


SPRITES = {
    'target': {(0, 2): 7, (1, 1): 7, (1, 2): 7, (1, 3): 7, (2, 2): 7},
    # colour-12 X decal: drawn straight onto the mass, with NO halo punch
    'xmark': {(1, 1): 12, (1, 3): 12, (2, 2): 12, (3, 1): 12, (3, 3): 12},
    # 3x4 block of 15s over a 11/0/11 foot: touching it kills the player
    # same killer hanging the other way up (its 11/0/11 foot on top)
    'killer_up': {(0, 1): 11, (0, 2): 0, (0, 3): 11,
                  (1, 1): 15, (1, 2): 15, (1, 3): 15,
                  (2, 1): 15, (2, 2): 15, (2, 3): 15,
                  (3, 1): 15, (3, 2): 15, (3, 3): 15,
                  (4, 1): 15, (4, 2): 15, (4, 3): 15},
    'killer': {(0, 1): 15, (0, 2): 15, (0, 3): 15, (1, 1): 15, (1, 2): 15,
               (1, 3): 15, (2, 1): 15, (2, 2): 15, (2, 3): 15, (3, 1): 15,
               (3, 2): 15, (3, 3): 15, (4, 1): 11, (4, 2): 0, (4, 3): 11},
}

LEVEL_STARTS = {0: (6, 3, 1), 1: (6, 3, 1), 2: (6, 3, 1), 3: (6, 4, 1), 4: (6, 3, 1), 5: (6, 3, 1)}

# --------------------------------------------------------- observed data ---
LEVEL_ENTRY_ROWS[1] = [
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5535555535555535555535555535555535555aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555355555355555355555355555aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355555355555355555355555355aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '55355555355555fff5a5fff5a5fff55535555aaaaaaaaaaaaaaaaa5535555535',
    '55555555555555fff5a5fff5a5fff55555555aaaaaaaaaaaaaaaaa5555555555',
    '55555555555555fff5a5fff5a5fff55555555aaaaaaaaaaaaaaaaa5555555555',
    '53555553555555fff5a5fff5a5fff55355555aaaaaaaaaaaaaaaaa5355555355',
    '55553555553555b0b5a5b0b5a5b0b55555355aaaaaaaaaaaaaaaaa5555355555',
    '555555555555555555a55555a555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaa5535555aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaa5355555aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaa5555355aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaa5535555aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaa5355555aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaa5555355aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '55355555355553eee353eee353eee353eee353eee353eee353eee35535555535',
    '5555555555555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5555555555',
    '5555555555555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5555555555',
    '5355555355555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5355555355',
    '55553555553553eee353eee353eee353eee353eee353eee353eee35555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '55355555355553eee353eee353eee353eee353eee353eee353eee35535555535',
    '5555555555555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5555555555',
    '5555555555555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5555555555',
    '5355555355555eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5eeeee5355555355',
    '55553555553553eee353eee353eee353eee353eee353eee353eee35555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaa555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '0000000000000000000000000000000000000000000000000000000000000000',
]
LEVEL_ENTRY_ROWS[2] = [
    '5555555555555aaaaaa55555a55555a55555a55555aaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaa5555555555555555555555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaa5535555535555535555535555535',
    '5555555555555aaaaaaacacaaacacaaacaca5555555555555555555555555555',
    '5555555555555aaaaaaaacaaaaacaaaaacaa5555555555555555555555555555',
    '5355555355555aaaaaaacacaaacacaaacaca5355555355555355555355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaa5555355555355555355555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaa5555555555555555555555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '55355555355555355555355555355555355553eee353eee353eee35535555535',
    '5555555555555555555555555555555555555eeeee5eeeee5eeeee5555555555',
    '5555555555555555555555555555555555555eeeee5eeeee5eeeee5555555555',
    '5355555355555355555355555355555355555eeeee5eeeee5eeeee5355555355',
    '55553555553555553555553555553555553553eee353eee353eee35555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555aaaaaa55955aaaaaa53ccc35aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaa599b5aaaaaa5ccccc5aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaa599b5aaaaaa5ccccc5aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaa55955aaaaaa5ccccc5aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaa555aaaaaaa53ccc35aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaa53ccc35aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaa5ccccc5aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaa5ccccc5aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaa5ccccc5aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaa53ccc35aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555aaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '0000000000000000000000000000000000000000000000000000000000000000',
]
LEVEL_ENTRY_ROWS[3] = [
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555535555535555535555535555535555535555535555535555535',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5355555355555355555355555355555355555355555355555355555355555355',
    '5555355555355555355555355555355555355555355555355555355555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '5535555535555535555535555535555535555535555535555aaaaa5535555535',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '5355555355555355555355555355555355555355555355555aaaaa5355555355',
    '5555355555355555355555355555355555355555355555355aaaaa5555355555',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '5535555535555535555535555535555535555535555aaaaaaaaaaa5535555535',
    '5555555555555555555555555555555555555555555aaaaaaaaaaa5555555555',
    '5555555555555555555555555555555555555555555aaaaaaaaaaa5555555555',
    '5355555355555355555355555355555355555355555aaaaaaaaaaa5355555355',
    '5555355555355555355555355555355555355555355aaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555aaaaaaaaaaa5555555555',
    '5535555535555535555535555535555535555aaaaaaaaaaaaaaaaa5535555535',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '5355555355555355555355555355555355555aaaaaaaaaaaaaaaaa5355555355',
    '5555355555355555355555355555355555355aaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555aaaaaaaaaaaaaaaaa5555555555',
    '55355555355555fff5a5fff5a55955aaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '55555555555555fff5a5fff5a599b5aaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '55555555555555fff5a5fff5a599b5aaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '53555553555555fff5a5fff5a55955aaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '55553555553555b0b5a5b0b5aa555aaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '555555555555555555a55555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '55355555355553eee353eee35535555535555535555535555535555535555535',
    '5555555555555eeeee5eeeee5555555555555555555555555555555555555555',
    '5555555555555eeeee5eeeee5555555555555555555555555555555555555555',
    '5355555355555eeeee5eeeee5355555355555355555355555355555355555355',
    '55553555553553eee353eee35555355555355555355555355555355555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '0000000000000000000000000000000000000000000000000000000000000000',
]
LEVEL_ENTRY_ROWS[4] = [
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555535555535555535555535555535555535555535555535555535',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5355555355555355555355555355555355555355555355555355555355555355',
    '5555355555355555355555355555355555355555355555355555355555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555535555535555aaaaaa55755aaaaaaa5fff5a5fff5a5fff55535',
    '5555555555555555555555555aaaaaa57775aaaaaaa5fff5a5fff5a5fff55555',
    '5555555555555555555555555aaaaaa55755aaaaaaa5fff5a5fff5a5fff55555',
    '5355555355555355555355555aaaaaaa555aaaaaaaa5fff5a5fff5a5fff55355',
    '5555355555355555355555355aaaaaaaaaaaaaaaaaa5b0b5a5b0b5a5b0b55555',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5555555555555555555555',
    '5535555535555535555535555aaaaaaaaaaaaaaaaa53eee353eee353eee35535',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5555',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5555',
    '5355555355555355555355555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5355',
    '5555355555355555355555355aaaaaaaaaaaaaaaaa53eee353eee353eee35555',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5555555555555555555555',
    '5535555535555535555535555aaaaaaaaaaaaaaaaa53eee353eee353eee35535',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5555',
    '5555555555555555555555555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5555',
    '5355555355555355555355555aaaaaaaaaaaaaaaaa5eeeee5eeeee5eeeee5355',
    '5555355555355555355555355aaaaaaaaaaaaaaaaa53eee353eee353eee35555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555535555535555535555535555535555535555535555aaaaa5535',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5355555355555355555355555355555355555355555355555355555aaaaa5355',
    '5555355555355555355555355555355555355555355555355555355aaaaa5555',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5535555535555535555535555535555535555535555535555535555aaaaa5535',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5355555355555355555355555355555355555355555355555355555aaaaa5355',
    '5555355555355555355555355555355555355555355555355555355aaaaa5555',
    '5555555555555555555555555555555555555555555555555555555aaaaa5555',
    '5535555535555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaa5388835aaaaa5535',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaa5888885aaaaa5555',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaa5888885aaaaa5555',
    '5355555355555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaa5888885aaaaa5355',
    '5555355555355aaaaaaa555aaaaaaaaaaaaaaaaaaaaaaaaa5388835aaaaa5555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555355555',
    '555555555555555555a55555a55555a55555aaaaaaaaaaaa5555555555555555',
    '55355555355555b0b5a5b0b5a5b0b5a5b0b5aaaaaaaaaaaa5535555535555535',
    '55555555555555fff5a5fff5a5fff5a5fff5aaaaaaaaaaaa5555555555555555',
    '55555555555555fff5a5fff5a5fff5a5fff5aaaaaaaaaaaa5555555555555555',
    '53555553555555fff5a5fff5a5fff5a5fff5aaaaaaaaaaaa5355555355555355',
    '55553555553555fff5a5fff5a5fff5a5fff5aaaaaaaaaaaa5555355555355555',
    '5555555555555555555555555555555555555aaaaaaaaaaa5555555555555555',
    '5535555535555535555535555535555535555aaaaaaaaaaa5535555535555535',
    '5555555555555555555555555555555555555aaaaaaaaaaa5555555555555555',
    '5555555555555555555555555555555555555aaaaaaaaaaa5555555555555555',
    '5355555355555355555355555355555355555aaaaaaaaaaa5355555355555355',
    '5555355555355555355555355555355555355aaaaaaaaaaa5555355555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '55355555355555355555355555355555355553eee353eee35535555535555535',
    '5555555555555555555555555555555555555eeeee5eeeee5555555555555555',
    '0000000000000000000000000000000000000000000000000000000000000000',
]
LEVEL_ENTRY_ROWS[5] = [
    '5555555555555555555555555555555555555aaaaa5555555555555555555555',
    '5535555535555535555535555535555535555aaaaa5535555535555535555535',
    '5555555555555555555555555555555555555aaaaa5555555555555555555555',
    '5555555555555555555555555555555555555aaaaa5555555555555555555555',
    '5355555355555355555355555355555355555aaaaa5355555355555355555355',
    '5555355555355555355555355555355555355aaaaa5555355555355555355555',
    '5555555555555555555555555555555555555aaaaa5555555555555555555555',
    '55355555355555fff5a5fff5a5fff5aaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '55555555555555fff5a5fff5a5fff5aaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '55555555555555fff5a5fff5a5fff5aaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '53555553555555fff5a5fff5a5fff5aaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '55553555553555b0b5a5b0b5a5b0b5aaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '555555555555555555a55555a55555aaaaaaaaaaaa5555555aaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555aaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555aaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555aaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555aaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355aaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555555555555555aaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaa5535555535555535555aaaaa5535555535',
    '5555555555555acacaaacacaaacaca5555555555555555555aaaaa5555555555',
    '5555555555555aacaaaaacaaaaacaa5555555555555555555aaaaa5555555555',
    '5355555355555acacaaacacaaacaca5355555355555355555aaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaa5555355555355555355aaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaa5555555555555555555aaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555535555535555535555535555388835535555535555535555535',
    '5555555555555555555555555555555555555888885555555555555555555555',
    '5555555555555555555555555555555555555888885555555555555555555555',
    '5355555355555355555355555355555355555888885355555355555355555355',
    '5555355555355555355555355555355555355388835555355555355555355555',
    '5555555555555555555555555555555555555555555555555555555555555555',
    '5535555535555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaa599b5aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaa55955aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaa555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555555555',
    '5535555535555aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5535555535',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaacacaaacacaaaaaaa5555555555',
    '5555555555555aaaaaaaaaaaaaaaaaaaaaaaaaacaaaaacaaaaaaaa5555555555',
    '5355555355555aaaaaaaaaaaaaaaaaaaaaaaaacacaaacacaaaaaaa5355555355',
    '5555355555355aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5555355555',
    '555555555555555555a55555a55555a55555a55555a55555aaaaaa5555555555',
    '55355555355555b0b5a5b0b5a5b0b5a5b0b5a5b0b5a5b0b5aaaaaa5535555535',
    '55555555555555fff5a5fff5a5fff5a5fff5a5fff5a5fff5aaaaaa5555555555',
    '55555555555555fff5a5fff5a5fff5a5fff5a5fff5a5fff5aaaaaa5555555555',
    '53555553555555fff5a5fff5a5fff5a5fff5a5fff5a5fff5aaaaaa5355555355',
    '55553555553555fff5a5fff5a5fff5a5fff5a5fff5a5fff5aaaaaa5555355555',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '5535555535555535555535555535555535555535555535555aaaaa5535555535',
    '5555555555555555555555555555555555555555555555555aaaaa5555555555',
    '0000000000000000000000000000000000000000000000000000000000000000',
]
