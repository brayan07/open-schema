# re86 — WIN (8/8 levels, 580 actions)

## Rules of the game (all confirmed by play)
- Actions 1/2/3/4 move the ACTIVE shape up/down/left/right by exactly 3
  cells; 5 cycles the active shape. Action 6 (click) is never legal.
- Scene: background 5; static 3x3 TOKENS (4-border, centre = a colour);
  one or more rigid SHAPES built from straight bars (plus, X with or
  without its centre, diamond outline, rectangle outline, line...).
- GOAL: every token is covered (its 3x3 box touched) by a shape of its own
  colour. Several shapes may share a colour.
- The active shape's 0 marker sits at (centre of a vertical bar, centre of
  a horizontal bar) and does not follow a bar that was blocked. The marker
  must stay on the grid: a move that would push it off is a no-op.
- PALETTE boxes (6x6 with a 2-ring from level 3, 5x5 later): moving any
  cell of a shape into the box repaints the shape in that colour; if two
  boxes are touched at once the topmost-leftmost wins.
- BLOCKER blobs (colour 1, square with a diamond hole): a bar whose
  destination overlaps a blob does not move while the other bars do —
  that is how a cross's bars are slid apart. A rectangle instead MORPHS:
  the blocked leading edge stays, the trailing edge comes in (that
  dimension −3) and the perpendicular dimension grows +3, keeping the
  perimeter constant; the growth goes to the min side when the growing
  dimension is odd, else to the max side.
- A cross whose two bars would stop crossing refuses to move at all.
- Row 63 bar: lit cells = round(64 * actions_this_level / BUDGET), with
  BUDGET 100,100,200,200,250,200,300,(300?) per level. Informational.

## Cost
level 0: 21 actions, 1: 35, 2: 47, 3: 46, 4: 65, 5: 52, 6: 115, 7: 199.
