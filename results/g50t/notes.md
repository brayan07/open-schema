# Notes

## Universal mechanics (confirmed on level 0, carried into level 1)
- Cell grid, pitch 6. cell(i,j) box = rows R0+6i..R0+6i+6, cols C0+6j..C0+6j+6.
  OPEN (walkable) cell = the full 7x7 is colour 5. A cell the rope merely
  passes through is a 3-wide corridor => NOT walkable.
- 1=up 2=down 3=left 4=right, one cell. Move off the cell grid = rejected
  outright (not counted, not recorded). Blocked move = counted.
- 5 = RESTART: the attempt just played becomes a GHOST that respawns at the
  spawn cell and replays its recorded actions, one per counted action of mine.
  Order inside a step: player moves first, then each ghost in slot order.
  Legend rows 1-3 (3x3 swatches at cols 1+4k) = attempt slots: level 0 had 2,
  level 1 has 3 => TWO ghosts available. Row 5 marks the active slot.
- Rope (8): line along cell centres from an anchor cell (3x3 knob) to the
  block cell (5x5 sprite, far edge dotted). While ANY ring stands on the
  anchor the block is pulled ONE cell towards the anchor; it snaps back the
  instant the anchor is vacated. A block plugs its cell.
- row 63 = budget bar: 64 - ceil(m/2) pixels of 9; m resets each level.

## RESULT: WIN — all 7 levels, 415 actions total
Per level: L0 48, L1 31, L2 73, L3 32, L4 116, L5 71, L6 43.
L2/L4/L5 were expensive because each introduced a mechanic that had to be
paid for in real actions (colour-11 toggle, the gate PULSE rule, and the
colour-14 patroller's true nature).

## Confirmed rules (all levels)
- The world only TICKS when the player actually moves. A move blocked by a
  wall/block still costs an action and budget, but ghosts do not step and it
  is NOT recorded into the attempt's replay script. Off-grid moves are
  rejected outright (no transition at all).
- Rings do NOT collide: player and ghosts pass through and may share a cell.
- Budget bar (level >= 1): 64 - floor(m/2) pixels of 9. Level 0 used ceil.
- Colour 8 rope = SPRING: block pulled one cell while a ring stands on the
  anchor, snaps back when vacated.
- Colour 11 rope = TOGGLE: block flips home <-> pulled every time a ring
  steps ONTO the anchor; it stays put when the anchor is vacated.
- Colour 15 = gate SYSTEM: two 7x7 gate outlines plus a 3x3 KNOB, linked by a
  line (a level can hold several independent systems).
  The knob is a PULSE: on the tick a ring steps ONTO the knob, every ring
  standing on a gate cell is thrown to the paired gate. A ring already parked
  on the knob does nothing; standing on a gate with no pulse does nothing.
  The line is not walkable. (Player moves first, so entering a gate on the
  same tick a ghost enters the knob works.)
- Colour 14 = a PATROLLER ring: one step per world tick on its own heading,
  independent of my direction. Blocked -> tries 90 CCW, then 90 CW, then
  reverses, and keeps that heading. It trips toggles it steps onto, and a
  spring block snapping back onto it DESTROYS it (park spring ghosts early so
  they never vacate).
- A cell is walkable iff its whole 7x7 box is non-zero; rope/gate lines run
  through 3-wide corridors that are NOT walkable.

## Workflow
- /tmp/mkcp.py rebuilds G_CHECKPOINTS by replaying history through the model
  (run it before every commit: commit's init_state starts from "now").
- /tmp/newlevel.py embeds a new level's entry grid and prints its map.
- world_model.py: level 0 is bespoke; level 1+ is a generic engine that parses
  the entry grid. Anything it cannot explain yet is frozen into a static
  "overlay" so the render stays pixel-exact.

## Level 6 (the finish)
10x10 (R0=C0=1 - the maze overlaps the legend rows, so the lattice must be
anchored on the player ring, never on a bounding box). Two gate systems:
(2,2)<->(4,2) with knob (4,0), and (6,8)<->(8,8) with knob (0,8).
Chain: ghost1 flips the toggle at (6,3) so the patroller can climb column 0;
it then stands on gate (4,2) as the patroller reaches knob (4,0) and is thrown
to (2,2), parking on spring anchor (0,2) to open (0,5); ghost2 runs the top
corridor to knob (0,8) on tick 14; I stand on gate (6,8) that same tick and am
thrown to (8,8), three steps from the goal.
