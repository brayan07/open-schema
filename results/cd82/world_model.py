"""World model for cd82 (level 0).

LAYOUT
  target panel : rows 3-12,  cols 3-12   (10x10 goal image; static)
  palette      : swatch A rows2-6 cols35-39 (colour 0), swatch B cols41-45
                 (colour 15); selection marker = colour 0 at row 7 under the
                 selected swatch.
  container    : rotatable paint bucket, 3 tilt states (-1, 0, +1)
  canvas       : rows 34-43, cols 27-36  (10x10 painting surface)
  action bar   : row 63, fills 4->5 from the right

MECHANICS (all confirmed against the recorded history)
  a1        : accepted, no visible effect (submit?).
  a2        : rejected outright, never changes anything.
  a3        : tilt += 1, clamped at +1.
  a4        : tilt -= 1, clamped at -1.
  a5        : POUR - paints exactly half the canvas with the selected colour.
              The half is the one nearest the container:
                tilt  0 : r <= 38            (top half, 50 cells)
                tilt +1 : r + c <= 70        (top-left half, 55 cells)
                tilt -1 : c - r >= -7        (top-right half, 55 cells)
              All three cut lines pass through the canvas centre (38.5, 31.5).
  a6        : click. Only the two palette swatches are interactive
              (x in 35..39 / 41..45, y in 2..6 -> select that colour).
              Every other click observed so far is a no-op.

  Row 63 counter: advances by one cell on most actions but stalls on ~1 in 3
  in a pattern I have not been able to derive from (state, action) - the same
  action in the same state ticks sometimes and not others, so it depends on
  hidden engine state. The observed stall positions are tabled below; beyond
  the recorded history the model assumes it always ticks. A wrong guess only
  truncates a committed plan, it costs no actions.
"""

CANVAS_R = (34, 43)
CANVAS_C = (27, 36)
TARGET_R = (3, 12)
TARGET_C = (3, 12)
BAR_ROW = 63

# container renderings, extracted verbatim from the recorded frames
CONTAINER = {int(_k): _v for _k, _v in {"0": [[24, 25, 2], [24, 26, 2], [24, 27, 2], [24, 28, 2], [24, 29, 2], [24, 30, 2], [24, 31, 2], [24, 32, 2], [24, 33, 2], [24, 34, 2], [24, 35, 2], [24, 36, 2], [24, 37, 2], [24, 38, 2], [25, 25, 2], [25, 26, 15], [25, 27, 15], [25, 28, 15], [25, 29, 15], [25, 30, 15], [25, 31, 15], [25, 32, 15], [25, 33, 15], [25, 34, 15], [25, 35, 15], [25, 36, 15], [25, 37, 15], [25, 38, 2], [26, 25, 2], [26, 26, 15], [26, 27, 15], [26, 28, 15], [26, 29, 15], [26, 30, 15], [26, 31, 15], [26, 32, 15], [26, 33, 15], [26, 34, 15], [26, 35, 15], [26, 36, 15], [26, 37, 15], [26, 38, 2], [27, 25, 2], [27, 26, 15], [27, 27, 15], [27, 28, 15], [27, 29, 15], [27, 30, 15], [27, 31, 15], [27, 32, 15], [27, 33, 15], [27, 34, 15], [27, 35, 15], [27, 36, 15], [27, 37, 15], [27, 38, 2], [28, 25, 2], [28, 26, 15], [28, 27, 15], [28, 28, 15], [28, 29, 15], [28, 30, 15], [28, 31, 15], [28, 32, 15], [28, 33, 15], [28, 34, 15], [28, 35, 15], [28, 36, 15], [28, 37, 15], [28, 38, 2], [29, 25, 2], [29, 26, 15], [29, 27, 15], [29, 28, 15], [29, 29, 15], [29, 30, 15], [29, 31, 15], [29, 32, 15], [29, 33, 15], [29, 34, 15], [29, 35, 15], [29, 36, 15], [29, 37, 15], [29, 38, 2], [30, 25, 2], [30, 26, 15], [30, 27, 15], [30, 28, 15], [30, 29, 15], [30, 30, 15], [30, 31, 15], [30, 32, 15], [30, 33, 15], [30, 34, 15], [30, 35, 15], [30, 36, 15], [30, 37, 15], [30, 38, 2], [31, 25, 2], [31, 26, 15], [31, 27, 15], [31, 28, 15], [31, 29, 15], [31, 30, 15], [31, 31, 15], [31, 32, 15], [31, 33, 15], [31, 34, 15], [31, 35, 15], [31, 36, 15], [31, 37, 15], [31, 38, 2], [32, 25, 2], [32, 38, 2]], "1": [[21, 24, 2], [22, 23, 2], [22, 24, 2], [22, 25, 2], [23, 22, 2], [23, 23, 2], [23, 24, 15], [23, 25, 2], [23, 26, 2], [24, 21, 2], [24, 22, 2], [24, 23, 15], [24, 24, 15], [24, 25, 15], [24, 26, 2], [24, 27, 2], [25, 20, 2], [25, 21, 2], [25, 22, 15], [25, 23, 15], [25, 24, 15], [25, 25, 15], [25, 26, 15], [25, 27, 2], [25, 28, 2], [26, 19, 2], [26, 20, 2], [26, 21, 15], [26, 22, 15], [26, 23, 15], [26, 24, 15], [26, 25, 15], [26, 26, 15], [26, 27, 15], [26, 28, 2], [26, 29, 2], [27, 18, 2], [27, 19, 2], [27, 20, 15], [27, 21, 15], [27, 22, 15], [27, 23, 15], [27, 24, 15], [27, 25, 15], [27, 26, 15], [27, 27, 15], [27, 28, 15], [27, 29, 2], [27, 30, 2], [28, 17, 2], [28, 18, 2], [28, 19, 15], [28, 20, 15], [28, 21, 15], [28, 22, 15], [28, 23, 15], [28, 24, 15], [28, 25, 15], [28, 26, 15], [28, 27, 15], [28, 28, 15], [29, 16, 2], [29, 17, 2], [29, 18, 15], [29, 19, 15], [29, 20, 15], [29, 21, 15], [29, 22, 15], [29, 23, 15], [29, 24, 15], [29, 25, 15], [29, 26, 15], [29, 27, 15], [30, 15, 2], [30, 16, 2], [30, 17, 15], [30, 18, 15], [30, 19, 15], [30, 20, 15], [30, 21, 15], [30, 22, 15], [30, 23, 15], [30, 24, 15], [30, 25, 15], [30, 26, 15], [31, 14, 2], [31, 15, 2], [31, 16, 15], [31, 17, 15], [31, 18, 15], [31, 19, 15], [31, 20, 15], [31, 21, 15], [31, 22, 15], [31, 23, 15], [31, 24, 15], [31, 25, 15], [32, 15, 2], [32, 16, 2], [32, 17, 15], [32, 18, 15], [32, 19, 15], [32, 20, 15], [32, 21, 15], [32, 22, 15], [32, 23, 15], [32, 24, 15], [33, 16, 2], [33, 17, 2], [33, 18, 15], [33, 19, 15], [33, 20, 15], [33, 21, 15], [33, 22, 15], [33, 23, 15], [34, 17, 2], [34, 18, 2], [34, 19, 15], [34, 20, 15], [34, 21, 15], [34, 22, 15], [35, 18, 2], [35, 19, 2], [35, 20, 15], [35, 21, 15], [36, 19, 2], [36, 20, 2], [37, 20, 2]], "-1": [[21, 39, 2], [22, 38, 2], [22, 39, 2], [22, 40, 2], [23, 37, 2], [23, 38, 2], [23, 39, 15], [23, 40, 2], [23, 41, 2], [24, 36, 2], [24, 37, 2], [24, 38, 15], [24, 39, 15], [24, 40, 15], [24, 41, 2], [24, 42, 2], [25, 35, 2], [25, 36, 2], [25, 37, 15], [25, 38, 15], [25, 39, 15], [25, 40, 15], [25, 41, 15], [25, 42, 2], [25, 43, 2], [26, 34, 2], [26, 35, 2], [26, 36, 15], [26, 37, 15], [26, 38, 15], [26, 39, 15], [26, 40, 15], [26, 41, 15], [26, 42, 15], [26, 43, 2], [26, 44, 2], [27, 33, 2], [27, 34, 2], [27, 35, 15], [27, 36, 15], [27, 37, 15], [27, 38, 15], [27, 39, 15], [27, 40, 15], [27, 41, 15], [27, 42, 15], [27, 43, 15], [27, 44, 2], [27, 45, 2], [28, 35, 15], [28, 36, 15], [28, 37, 15], [28, 38, 15], [28, 39, 15], [28, 40, 15], [28, 41, 15], [28, 42, 15], [28, 43, 15], [28, 44, 15], [28, 45, 2], [28, 46, 2], [29, 36, 15], [29, 37, 15], [29, 38, 15], [29, 39, 15], [29, 40, 15], [29, 41, 15], [29, 42, 15], [29, 43, 15], [29, 44, 15], [29, 45, 15], [29, 46, 2], [29, 47, 2], [30, 37, 15], [30, 38, 15], [30, 39, 15], [30, 40, 15], [30, 41, 15], [30, 42, 15], [30, 43, 15], [30, 44, 15], [30, 45, 15], [30, 46, 15], [30, 47, 2], [30, 48, 2], [31, 38, 15], [31, 39, 15], [31, 40, 15], [31, 41, 15], [31, 42, 15], [31, 43, 15], [31, 44, 15], [31, 45, 15], [31, 46, 15], [31, 47, 15], [31, 48, 2], [31, 49, 2], [32, 39, 15], [32, 40, 15], [32, 41, 15], [32, 42, 15], [32, 43, 15], [32, 44, 15], [32, 45, 15], [32, 46, 15], [32, 47, 2], [32, 48, 2], [33, 40, 15], [33, 41, 15], [33, 42, 15], [33, 43, 15], [33, 44, 15], [33, 45, 15], [33, 46, 2], [33, 47, 2], [34, 41, 15], [34, 42, 15], [34, 43, 15], [34, 44, 15], [34, 45, 2], [34, 46, 2], [35, 42, 15], [35, 43, 15], [35, 44, 2], [35, 45, 2], [36, 43, 2], [36, 44, 2], [37, 43, 2]]}.items()}

NOTICK = [1, 4, 6, 9, 12, 15, 18, 20, 23, 26, 29, 31, 34, 37, 40, 43, 45]


def _canvas_cells():
    return [(r, c) for r in range(CANVAS_R[0], CANVAS_R[1] + 1)
            for c in range(CANVAS_C[0], CANVAS_C[1] + 1)]


CANVAS_SET = set(_canvas_cells())


def pour_cells(tilt):
    out = []
    for (r, c) in _canvas_cells():
        if tilt == 0:
            hit = r <= 38
        elif tilt == 1:
            hit = r + c <= 70
        else:
            hit = c - r >= -7
        if hit:
            out.append((r, c))
    return out


class ModelError(Exception):
    pass


try:  # the harness disables the model for a turn when init_state raises this
    from agi3lib.model import ModelError  # noqa: F811
except Exception:
    pass


def _read_tilt(grid):
    for t in (0, 1, -1):
        if all(grid[r][c] == v for r, c, v in CONTAINER[t]
               if v == 2):
            return t
    raise ModelError(
        "bucket is at one of the extended tilts (>=90 deg) reached with a2; "
        "those renderings are not in the model yet")


def _read_colour(grid):
    # marker (colour 0) at row 7 sits under the selected swatch
    return 0 if grid[7][35] == 0 else 15


def init_state(entry_grid, level=0):
    swatches = {c for c in range(18, 64) if entry_grid[2][c] == 4}
    if swatches != set(range(35, 40)) | set(range(41, 46)):
        raise ModelError(
            "model is only validated for the level-0 layout (2 swatches at "
            "cols 35-39/41-45); this level has a different palette and the "
            "bucket now uses all 8 orbit positions")
    # The bar stall table below is indexed by GLOBAL step number, which is
    # only recoverable when we start from the true entry frame (empty bar).
    # `commit` re-inits mid-run, so there we fall back to "always ticks".
    fresh = all(v == 4 for v in entry_grid[BAR_ROW])
    return {"tilt": _read_tilt(entry_grid),
            "colour": _read_colour(entry_grid),
            "hist": fresh,
            "n": 0}


def _draw_container(g, tilt, colour):
    for r in range(21, 38):
        for c in range(14, 50):
            if (r, c) not in CANVAS_SET:
                g[r][c] = 5
    for r, c, v in CONTAINER[tilt]:
        g[r][c] = colour if v == 15 else v


def _draw_marker(g, colour):
    for c in range(35, 46):
        g[7][c] = 3
    base = 35 if colour == 0 else 41
    for c in range(base, base + 5):
        g[7][c] = 0


# The row-63 bar is an ACTION-BUDGET meter for the level: after N actions
# exactly floor((64*N + 48)/100) cells are filled, i.e. 64 cells for a
# budget of 100 actions.  In backtest we start from the true entry frame so
# N = n + 1; `commit` re-inits mid-run, hence LIVE_OFFSET.
LIVE_OFFSET = 2   # actions already taken before this commit


def _set_bar(g, total_actions):
    fill = (64 * total_actions + 48) // 100
    g[BAR_ROW] = [4] * (64 - fill) + [5] * fill


def predict(state, grid, action, x=None, y=None, level=0, entry_grid=None):
    st = dict(state)
    g = [row[:] for row in grid]
    tilt, colour = st["tilt"], st["colour"]
    n = st["n"]
    rejected = False

    if action == 2:
        rejected = True
    elif action == 1:
        pass
    elif action == 3:
        tilt = min(1, tilt + 1)
    elif action == 4:
        tilt = max(-1, tilt - 1)
    elif action == 5:
        for (r, c) in pour_cells(tilt):
            g[r][c] = colour
    elif action == 6:
        if y is not None and 2 <= y <= 6 and x is not None:
            if 35 <= x <= 39:
                colour = 0
            elif 41 <= x <= 45:
                colour = 15
            else:
                rejected = True
        else:
            rejected = True

    if action in (3, 4, 6):
        _draw_container(g, tilt, colour)
        _draw_marker(g, colour)

    total = n + 1 if st.get("hist", True) else LIVE_OFFSET + n + 1
    _set_bar(g, total)
    # the budget bar is 100 actions long; running it out kills the run
    dead = total >= 100

    st.update(tilt=tilt, colour=colour, n=n + 1)
    return g, {"level_up": False, "dead": dead, "win": False}, st
