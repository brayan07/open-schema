# lf52 — PEG SOLITAIRE with pipe CARTS, pivot objects and a panning camera

Result: levels 0, 1, 2 completed (159 actions: 11 / 47 / 55, plus 46 spent so
far on level 3). Level 3 is in progress and NOT frozen — see the end.

## Mechanics (all confirmed by experiment)

Board geometry
- Boards are rectangles (border 5, drop shadow 9, interior 0) holding 4x4
  cells on a 6px pitch. A board may be irregular (L/T/plus shaped): two
  rectangles that share interior are ONE board.
- Cell renderings: empty = 4x4 of 1; peg = 12px circle of 14 (corners 1);
  jump-landing marker = 8px circle outline of 2; selected = ring of 3 drawn in
  the gap around the cell plus the cell's own 4 corners.
- PIVOT object (level 3+): a 4x4 box of 15 with a small 7 motif, drawn ONE ROW
  HIGHER than its cell plus a grey bar below it. It can be jumped over exactly
  like a peg but is NEVER consumed and never counts as a peg, so a lone peg can
  travel freely over pivots. It cannot be selected or landed on.

Moves
- Click a peg that has >=1 legal jump -> selects it and marks every landing.
  A peg with no legal jump cannot be selected; any click that neither selects
  nor jumps just clears the current selection.
- Click a marked landing -> jump. Orthogonal, over the adjacent (pitch-6)
  occupant, into the empty cell beyond. The jumped PEG is removed; a jumped
  PIVOT stays. 2 actions per jump.
- Jumps never cross between boards, and a landing must be a real cell (an
  empty pipe/track position is NOT a landing).

Carts (the only way to move a peg between boards)
- A cart is a 6x6 frame of 11 around a 4x4 interior of 12, riding a drawn 2px
  pipe. It is a normal cell for jumping whenever it sits 6px from a board cell
  (a "dock"); it can be loaded (peg jumps into it) and unloaded (its peg jumps
  out over an adjacent occupant).
- Actions 1/2/3/4 = up/down/left/right move EVERY cart one 6px step along its
  own track simultaneously (lockstep); a cart with no track node in that
  direction stays put. That per-cart blocking is how you change their relative
  phase — dead-end branches exist precisely to park one cart.
- Arrow moves clear any selection. Action 7 (undo) does nothing. Clicks never
  move carts.
- Docking clips the drawing: the cart is not drawn over board interior, and its
  shadow only falls on plain background.
- Selecting a peg inside a cart repaints part of the 11-frame with 3, so detect
  carts as {11,3} components containing at least one 11 pixel.

Camera (level 2+)
- The world is LARGER than the 64x64 frame and the frame is a window. The
  camera follows the peg-CARRYING cart (level 2 panned in 8px steps keeping it
  at screen x=18; level 3 pans 6px per cart step and also vertically, clamped
  to the world bounds). With no loaded cart the camera does not move.
- Consequence: boards, pegs and whole pipe networks can be off-screen. Never
  conclude a level is unsolvable from one frame — load a cart, drive it around,
  and stitch a world map from the frames.

Win / lose
- level_up when ONE peg is left (levels 0-2).
- Dead end: >1 peg with no jump reachable from any cart position -> the board
  freezes, remaining pegs turn 2 and a restart icon appears at screen (51,2);
  clicking it restarts the level. Nothing else responds while frozen. The game
  does NOT block a legal-but-losing move, so verify with an offline solver.

## Method that works
1. Load a cart, drive it to pan the camera, and record each frame with its
   offset (anchor on the loaded cart's known world position, or correlate
   structural colours); stitch a world map.
2. Flood-fill the world map for boards/cells/pegs; find pivots (colour 15) and
   pipe lanes -> cart track nodes every 6px, docks where a node is 6px from a
   board cell.
3. Solve offline: DFS over (peg bitmask, cart indices) with lockstep cart moves,
   pivot jumps free, peg jumps consuming. This is what found the level-2 line.
4. Execute: clicks never pan, so a whole jump chain commits in one go; commit
   arrow moves in small chunks because a pan voids the rest of the plan (that
   costs round-trips, not game actions).

## Model caveats (run/world_model.py)
- `commit` injects ENTRY_GRID = the frame at COMMIT START, not the level entry
  grid, so the scenery a docked cart hides is unknown; DOCK_BG holds the true
  9x9 patches for level 2's docks. Backtest injects the real entry grid.
- The level_up transition always mispredicts (next level's layout) — put it last.
- For CAMERA_LEVELS = {2,3} the model cannot evaluate the freeze rule or predict
  pans from a single frame (it only sees part of the world), so those checks are
  delegated to the offline solver. Levels 0/1 backtest green apart from their
  level-up frames; the level-2/3 mismatches are exactly the camera pans.

## Level 3 state (in progress, not frozen)
World is ~124x94. Known structure (world coords):
- Board A rows 16..35, x=4..48: cells rows 18/24/30 x cols 6..42, pivots at
  (24,18),(24,30). Started with pegs (24,12),(24,42) — now EMPTY.
- Cart1 track rows 25/26: nodes (24,48..72); docks (24,48)->A(24,42) and
  (24,72)->B(24,78).
- Board B rows 22..53, x=76..114: cols 78,84,90,96,102,108 x rows 24..48;
  pivots (30,84),(30,102),(42,84),(42,102),(48,96). Started with pegs
  (24,78),(24,102) — now EMPTY.
- Cart2 track: (48,54..78) horizontal + (54,54),(60,54) dead-end branch;
  dock (48,78)->B(48,84). It now HOLDS the northern component's last peg and
  is parked at (60,54).
- Board C rows 58..65, x=28..48: one cell row (60,30/36/42) with one peg and NO
  pipe connection found — an isolated component already at 1 peg.
- Southern half (mapped from the pan with cart2 loaded; camera offy=42,
  offx=15 in that frame): board D rows 64..83 x=22..35 (cells col 24 at rows
  66/72/78, pivots col 30 at rows 66/78); board E rows 64..83 x=40..60 (pivots
  col 42 at rows 66/78, cells cols 48/54/60); board F rows 83..90 x=28..48 with
  ONE peg at (84,36); a second cart on a horizontal lane at world row 72
  (nodes x=30..60, currently at (72,36)) whose dock (72,30) serves board D's
  (72,24).

Done so far: board A's 2 pegs -> 1 peg into cart1 (using both pivots as free
hops), ferried to board B, then board B's two pegs routed down the pivot
columns and jumped into cart2. So the whole northern component is reduced to
its single peg, which is the optimum for that component.

Probed: board C's peg (60,36) has NO legal jump (clicking it does nothing), so
like board F's peg it needs a cart delivery; the row-72 cart is the only thing
that can reach board D, and cart2's vertical branch dead-ends at (60,54) with
no dock, which is why its peg is currently parked.

Remaining: reduce the southern component to one peg. Level 3 did not level_up
at "one peg per component", so either the southern component must also reach 1
(most likely) or all components must merge to a single peg via a connection I
have not yet found. The next step is to finish stitching the southern map
(drive the loaded cart2 along its branch to pan the camera), then re-run the
offline solver over the whole world.
