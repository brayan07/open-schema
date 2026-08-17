# ka59 — SOLVED (WIN, 340 actions over 7 levels)

27 / 47 / 34 / 40 / 20 / 59 / 113 actions for levels 0..6.

## The game
Everything lives on a 3x3-px cell lattice whose phase varies per level
(read it off the piece pixels, NOT the floor outline — level 3's room edge
is ragged).  colour 1 floor, 15 wall, 2 void, 4 rings.

PIECES
- bordered: an h x w cell rect painted 14 with a central h x w px core.
  Core 0 = the piece you control, 5 = never controlled, 4 = deselected.
  Only these can be taken control of (action 6 = click on one).
- solid: cells painted a flat colour (11) or a two-tone 12/13 gauge block.
  These can never be controlled — only thrown or shoved.

GOAL: every ring exactly filled by a piece (gauge blocks need no ring).

THROW: moving the controlled piece into another piece throws that piece 5
cells that way, straight through walls.  If the 5-cell spot is illegal it
keeps flying (6,7,...) to the first legal one, and only if none exists does
it fall back to 4,3,2,1.  The thrower does not move.  This is the only way
across walls, and rings are placed at multiples of 5 (or at back-off spots).

GAUGE BLOCKS (levels 4-6): colour 12 piles up against one edge, one px per
MOVE (clicks do not tick them).  The fill boundary travels away from that
edge = the block's shove direction.  When the gauge wraps, any piece lying
within 2*len cells ahead of the block's leading edge (and overlapping its
perpendicular span) is teleported so its near edge sits at edge + 2*len,
flying further if blocked.  The player's own move resolves BEFORE the shove.
Shoves cross walls, so they are the level-5/6 lifts between regions.

BAR (row 63): rightmost round(64*n/BUDGET) px are 0, n = actions this level.
Budgets: 100, 128, 100, 128, 100, 150, 200.  Purely cosmetic, but it must be
predicted or commits get voided — keep TRUE_N in world_model.py current.
