# sp80 — mechanics learned (levels 0-3 cleared, stalled on level 4)

## Rendering
- Board size and cell size VARY per level: levels 0-2 are 16x16 in 4x4 pixel
  blocks; levels 3-4 are 20x20 in 3x3 blocks inset 2px. `geometry()` reads it
  off the frame — never assume.
- One pixel row (0 or 63) is an action counter that fills with colour 0 over
  14 as `round(64*n/PERIOD)`. PERIOD per level: 30, 45, 100, 120, ~97.
  It is coarse, so several counts render alike (hence `N_HINT`).
- The whole board rotates between levels; cups may hang from the top, stand on
  the bottom, or (level 4) sit against a side wall.
- Colours: c/12 bg, 1 wall, b/11 cup, 8 idle piece, 9 held piece,
  4 = a mark inside a piece (moves with it) or a free-standing level marker,
  6 = the other half of that marker, f/15 = level 4's L-shaped piece when idle.

## Actions
1/2/3/4 move the held piece one cell; 6 = click a cell to pick up the piece
under it; 5 = hand over / grade; 0 = reset (works, not listed).

## Movement
- Pieces do NOT collide with each other at all — they slide over one another
  (level 4 #335). Only scenery (cups, walls, free markers) blocks, and it
  blocks with a 1-CELL HALO, so a piece halts one cell short of any scenery.
  That is why the resting row is two cells from the cup mouth.

## Cups
- A cup is a 3-wide U/∏: a solid back plus two LEGS on the row facing the
  playfield, with a 1-cell cavity between them. `leg_row` = the row next to the
  row carrying the most cup cells. GAPS are the runs of columns between
  neighbouring cups.

## Action 5
- If the board is not gradeable, control passes to the piece FARTHEST from the
  cups (so the direction flips with the board's rotation); if the held piece is
  already that one, nothing happens.
- The board is GRADED as soon as every piece is at rest and no two pieces end
  on the same column. Correct -> level up, incorrect -> GAME OVER.
- AT REST means either
    BRIDGE: both ends on legs, covering at least one whole gap, and each end is
            the leg bordering one of the gaps it covers (a bridge may span
            several gaps at once — level 3's 7-wide covered two);
    SPARE:  both ends on columns that are not legs (gap, cavity or off-board).
- CORRECT means every gap carries a bridge and no gap holds more than one
  spare end.
- Extra death: pressing 5 while an IDLE piece sits entirely outside the cups'
  column range (it has slid off the structure) is fatal, even mid-hand-over.

## Levels
- L0: 1 bar, 2 cups. Bridge -> clear.  L1/L2/L3: bridges + stowed spares.
- L3 also had a piece with a colour-4 mark in its middle; the mark just rides
  along (it does not have to line up with the level marker — the clear had it
  at column 13 while the marker was at column 7).

## Level 4 — unsolved, and why
Cups (5-7), (11-13), (15-17) on the ceiling; gaps 8-10 and 14. Pieces: 5-wide,
3-wide, 4-wide, plus an L-shaped piece (cells (r,c),(r,c+1),(r+1,c+1)).
There is ALSO a cup lying against the left wall (rows 11-13, col 1-2, mouth
facing right) that nothing has satisfied.
Tried and rejected (all with the two bridges correctly at 7-11 and 13-15):
- 4-wide stowed at 9-12, L at cols 3-4  -> GRADED and fatal.
- 4-wide stowed at 9-12, L docked level with the side cup's mouth at its
  closest approach (12,4-5)+(13,5) -> action 5 is a dead no-op: not graded and
  no hand-over, which suggests the L is not yet "at rest" and the game will not
  even look at the board.
- 4-wide docked end-on into the side cup (12,4-7) -> also never graded (its
  right end lands on leg 7, so it is not a legal spare).
Open question: what counts as "at rest" for the L piece, and what the sideways
cup wants. Everything else about the level matches the model above.
