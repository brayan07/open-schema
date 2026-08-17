# cn04 — what the game is, and where I stalled

Levels 0-3 cleared (16, 39, 25, 33 actions). Level 4 not solved after 49
actions; see "Level 4" below for why I believe my reading of it is incomplete.
`world_model.py` backtests green on all 161 recorded transitions.

## Mechanics (all confirmed by a green backtest)

- The 64x64 frame is a 20x20 grid of 3x3 blocks at pixel offset (2,2).
  Pixel row 0, cols 16..47, is a progress bar: `round(32*n/BUDGET[level])`
  cells filled, n = actions since the level started (reset by RESET too).
  BUDGET = 74, 100, 128, 128, 150 for levels 0..4 (each pinned or bracketed
  by the observations of that level). It is cosmetic — nothing happened as
  it filled.
- A level contains several rigid SHAPES: a body plus colour-8 TIPS.
- Exactly one shape is selected. 1=up 2=down 3=left 4=right move it one
  block; 5 rotates it 90 deg CW about its bbox top-left; 6 clicks at a pixel
  and selects the shape under the cursor (clicking the selected shape
  deselects it; where shapes overlap, a click prefers an unselected one).
- Shapes never collide — they pass through each other freely. Only the grid
  boundary stops a move.
- Two tips on the same block are JOINED and drawn colour 3. Joins are not
  rigid: moving one shape away breaks the join, and joined shapes do not
  move together.
- LEVEL CLEARED when every tip of every shape is joined (levels 0-3).
- Rendering, per level:
  - levels 0,1 "all": every shape in its own colour with tips visible; the
    selected one is drawn in colour 0 instead.
  - levels 2,3,4 "one": only the selected shape shows its colour and tips;
    every other shape is drawn flat in colour 4 with its tips hidden. So a
    level starts as reconnaissance: click each blob once to learn its tips.
  - the selected shape is drawn on top of the others.

## Level 4 — the open problem

Four shapes (tips learnt by clicking each once):
  b  body (8,4),(8,5),(8,6),(9,6)   tips (9,4),(7,5),(10,6)  + a cell (8,7)
                                    drawn in colour 0, not 8
  a  8-cell U at (15..17, 2..5)     tips (17,1),(15,2)
  e  8-cell comb at (1..2, 12..16)  tips (3,12),(3,14),(3,16)
  c  4-cell L at (15..17, 16..17)   tips (15,15),(17,16)

That is 10 colour-8 tips plus one colour-0 tip. Exhaustive search (all 4^4
rotations x all pairings, ignoring collisions, allowing disconnected
assemblies, allowing 3-way and hub joins) says:

- the 10 colour-8 tips can NEVER all be joined — zero consistent placements;
- if the colour-0 tip is treated as joinable, 52 assemblies exist, each
  leaving exactly one of e's three tips free.

Tested in game:
- a colour-8 tip placed exactly on the colour-0 tip does NOT join (renders 8
  or 0, never 3) — tried in both directions (moving onto it, and moving it
  onto a stationary tip);
- an assembly with 4 real joins in which all four shapes are connected and
  every shape has a joined tip does NOT clear the level;
- adding the colour-0-on-tip contact (the "5th join") does not clear it
  either.

### What the colour-0 cell actually is (found at the very end)

It is a GROWTH HEAD, not a tip. Clicking it *while its own shape is
selected* extends the shape: the head cell becomes body, a new tip appears
beside it, and the head advances one block. Two clicks on b's head gave:

  click 1: body +(9,7), new tip (8,7) (which immediately joined e's tip
           there, so it renders 3), head moves to (9,8)
  click 2: body +(9,8),(10,8),(11,8),(12,8), new tip (13,8),
           head moves to (9,9)

So level 4's tip count is not fixed - b can be grown until the tips pair up,
which dissolves the parity contradiction above (10 colour-8 tips can never
all be joined, but a grown b has more). The growth pattern is not yet
characterised: segment 1 added one body block, segment 2 added four, so the
new geometry has to be read off the frame after each click.

This is where the run stopped. `world_model.py` reproduces everything except
the two growth clicks (transitions #162, #163) - it has no growth rule yet.
The remaining work on level 4 is: grow b, read the resulting shape, then run
the same tip-pairing search over the grown shape.
