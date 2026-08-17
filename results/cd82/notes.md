# cd82 — WIN, 6/6 levels, 217 actions [134, 7, 22, 18, 16, 20]

## The game
Paint the 10x10 CANVAS (rows34-43, cols27-36) to match the TARGET panel
(rows3-12, cols3-12). An exact match triggers LEVEL_UP automatically.
Canvas starts all 0.  Write (k,j) = (r-34, c-27).

Palette: swatch boxes in rows2-6 (colour-4 borders, 3x3 interior rows3-5).
Click inside a box to select that colour; a colour-0 marker in row 7 sits
under the selected box.  Level 2+ interiors: cols 22-24, 28-30, 34-36,
40-42, 46-48, 52-54, 58-60 = colours 0 f c b e 8 9  ->  click
x = 23,29,35,41,47,53,59 at y=4.

## The bucket
A bucket ORBITS the canvas at 8 clock positions, mouth always facing it.
a1/a2/a3/a4 move it toward screen UP/DOWN/LEFT/RIGHT; each position has
exactly 2 valid keys and the other 2 are silent no-ops:
    12:00 a3->10:30  a4->1:30     6:00  a4->4:30  a3->7:30
    10:30 a2->9:00   a4->12:00    4:30  a1->3:00  a3->6:00
    9:00  a2->7:30   a1->10:30    3:00  a1->1:30  a2->4:30
    7:30  a4->6:00   a1->9:00     1:30  a3->12:00 a2->3:00

a5 = POUR: paints exactly HALF the canvas — the half-plane through the
canvas centre whose normal points at the bucket:
    12:00 k<=4    10:30 k+j<=9   9:00 j<=4   7:30 k>=j
    6:00  k>=5    4:30  k+j>=9   3:00 j>=5   1:30 j>=k
Overwrite semantics: last pour wins; re-pouring the colour already there
is a no-op.

## The flask (level 2+)
A narrower vessel rides on the far side of the bucket.  Clicking its NECK —
the 2 fixed colour-0 cells in its throat — pours ITS contents as a solid
block of (flask width) x (volume/width), laid against the canvas edge
nearest the bucket and centred.  4x3 = 12 units in levels 2-5.  Clicking
the flask body does nothing.  Neck at 12:00 = (x31,y19); at 9:00 = (x12,y38).

## Budget
Row 63 is the per-level action bar: after N actions exactly
floor((64N+48)/100) cells are 5, so N=100 => GAME_OVER.  RESET (action 0)
restarts the level with a fresh budget; the bar also resets on level_up.

## Method
Read the target as a stack of half-planes and order them so the LAST pour
covering each cell carries the right colour; add flask blocks last.
e.g. level 5 = black@4:30, e@3:00, 8@10:30, then f-band@12:00, b-block@9:00.

## Cost of the run
Level 0 took 134 actions because the orbit was hidden: a3/a4 appear to clamp
at +-45 deg, and the extra positions only open up when you press the key
matching the bucket's actual screen displacement (from 10:30 the next step
is DOWN, not LEFT).  Once that was found, levels 1-5 cost 7-22 actions each.

## world_model.py
Exact and backtest-green over the level-0 layout (bucket render, pour
half-planes, palette marker, budget bar, death at 100 actions).  It raises
ModelError on later levels — different palette, 8 orbit positions, flask —
so those commits ran unchecked and were verified by dumping the canvas.
