# lp85 — WIN (8/8 levels, 105 actions total)

Per level: L0 6, L1 8, L2 17, L3 13, L4 11, L5 20, L6 8, L7 21 (+1 winning step).

## The game
Every level is the same idea in a different skin: coloured square tiles sit in
SLOTS arranged on a lattice; arrow buttons rotate a cyclic TRACK of slots by one
slot per click. Four matching corner pips just outside a slot mark it as a
target: it must end up holding a tile of the pip colour (always colour 11 = b
except level 3, which also wanted 12 = c). Slot geometry never moves, only
contents. Tracks may share slots — that sharing is what makes the puzzles hard.

## Rules that held everywhere
- Only action 6 (click) is ever legal; clicking inside an arrow blob fires it.
- Contents move in the direction the arrow's apex points, at the arrow's own
  position. Bbox taller than wide => left/right arrow, wider than tall => up/down.
- Column 0 is a per-level action gauge: filled cells = round(64*a/BUDGET).
  Fitted budgets: L0 13, L1 64, L2 80, L3 150, L4 80, L5 80, L6 80, L7 80.
  It never affects the puzzle, but it must be predicted or a plan aborts.

## Track shapes, level by level (all encoded in world_model.py)
- L0-L2: rings / single rows, one arrow pair each (`analyse` + `_walk`).
- L3: crossing lattice — all row-lines chained into ONE 20-cycle (row-major),
  all column-lines into another; they share the four crossing slots.
- L4: one serpentine chain; the top arrows rotate only the top row, the middle
  arrows rotate the whole chain — the shared slot lets tokens hop between them.
- L5: flowers of 3 concentric 8-slot rings; per flower one button pushes every
  ray radially outward, the other rotates all rings counter-clockwise. The
  middle flower (rings 1-2 only) shares its ring 2 with the outer flowers'
  ring-3 corners, and its lone up arrow swaps rings 1 and 2 — that is the only
  way into the targets.
- L6: a row and a 2x2 ring locked to the same pair of arrows (both move
  together), plus a 3-slot column sharing one slot with the row. Row+ring are
  parity-locked, so the fix is to park a token in the column and back.
- L7: three cyclic tracks, each a diagonal feeder turning into a vertical chute
  that ends on a target. The bottom pair advances ALL three by one; each
  right-hand panel pair cycles just one track's feeder segment (lengths 7, 6, 2),
  which is how the three tracks are brought into phase.

## Method that worked
Write the model, `backtest` to green, plan with BFS over TOKEN positions only
(full-grid BFS blows up), commit the whole plan: a misprediction wastes no
action, it just names the counterexample.
