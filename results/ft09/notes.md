# ft09 — WIN, 6/6 levels, 75 actions [4, 7, 14, 16, 21, 13]

## The game (fully worked out; see world_model.py)
Boards are 6x6 CELLS on an 8px lattice (2px gutters); occupied positions
need not fill the rectangle. Some lattice positions hold a MINI — a 3x3
picture at 2x2px whose centre is a real colour and whose outer sub-pixels
are symbols:
  0 = this neighbour must show the mini's centre colour
  2 = must show anything BUT that colour
  3 = there is no cell at that position (edge, gap, or another mini)
Overlapping minis intersect their demands; on level 3 two "not mine" bans
left exactly one colour, which is how the third colour got used. Cells
that stay ambiguous take the earliest colour in cycle order.

A click cycles a cell through the level's colours in the order of the
4x4 swatch strip hanging from row 0 in the top-right (absent on level 0).
Levels used: {9,8} / [9,12] / [8,12] / [9,8,12] / [14,15] / [11,14].

Some cells wear an OVERLAY: a few pixels of a foreign colour (6) inside
the block. Those pixels are a pictogram of the neighbours a click drags
along with the cell — all four orthogonals on level 4, north only on
level 5. Otherwise a click moves that cell alone.

A level clears the moment every mini's neighbourhood satisfies it.

## Row 63
A per-level action bar (12 -> 11 from the right, reset each level). Its
increments repeat with a short period — 2 on levels 0-1, (1,0,1) on 2-3,
(0,1,1,0) on 4 — but the period only becomes measurable after several
actions, so the first actions of a fresh level mispredict. Purely
cosmetic: it never gated anything.

## Cost note
Level 4 cost 21 instead of ~12: the nine plainly-forced cells were
clicked before the lights-out tiles were understood, and firing those
tiles afterwards knocked seven settled cells off target.
