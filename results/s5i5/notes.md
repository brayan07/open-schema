# s5i5 — mechanics learned, and why level 2 beat me

Result: levels 0 and 1 completed (27 and 41 actions).  Level 2 reached and
heavily explored but not completed.  `world_model.py` reproduces every
recorded transition except the two level-boundary frames (which no model can
predict) — modulo the parsing limitation noted at the end.

## Controls

* Only action 6 (click) is ever legal; RESET (action 0) works even though it
  is not listed, and restarts the current level.
* Row 63 is a cosmetic meter: after n actions of a level it shows
  round_half_up(64*n/BUDGET) cells of colour 4.  BUDGET = 50 / 150 / 200 for
  levels 0 / 1 / 2.  (It is too coarse to read the action count back out of,
  hence `N_OFFSET` in the model.)
* Each controllable colour has one control box at the bottom: a 2-border
  panel showing a shape, a 3-coloured axis, and the shape's mirror image.
  ANY pixel of the box counts:
  - far side of the axis  -> GROW that object by one 3x3 block at its
    leading edge (head, if any, moves to the new block's centre);
  - near side of the axis -> RETRACT the last block again (head moves back).
    Retracting an object that is already one block is a no-op.
  - the axis column itself, and everything outside boxes (objects, tail
    lines, diamonds, empty cells) is inert — but still costs an action.

## Objects

* An object is a solid rectangle of one colour plus a 3-cell tail line of
  colour 3 on one edge; it grows AWAY from its tail.  Some carry a head cell
  (colour 13).
* Lineless shapes are scenery.  Colour 15 never moves.  Other scenery (e.g.
  colour 1 bars) can be shoved and dragged, but never passes a shove on.
* A target diamond is 4 cells of colour 13 around an empty centre; it is
  painted on top of whatever passes under it and never moves.  A level ends
  when EVERY diamond centre holds a head (level 0 only advanced when the
  second head arrived).

## Shoving (hard-won)

Growing into occupied cells shoves what is there by 3 in the same direction:

* the shoved object drags along everything touching it PERPENDICULAR to the
  push, transitively;
* an object dragged that way may in turn shove what is in front of it, but
  the DIRECTLY shoved object may not — its landing spot must be empty
  (level 1 #44 chained a->b->e fine; level 2 #84/#85 both failed exactly
  because the directly shoved bar had something in front of it);
* scenery is dragged like anything else but never passes a drag on;
* retracting pulls scenery that leans on the retreating face back with it,
  and if that scenery has nowhere to go the whole retraction is refused;
* any blocked participant (grid edge, colour 15, a stuck neighbour) makes
  the entire click a no-op that still costs an action.

## Level 2 diagnosis

Board: heads on 7 (grows down, col 49) and a (grows right, row 28); helpers
8 (up), 9 (left), c (left), e (up); scenery bar A + bar B (colour 1) and a
fixed colour-15 block at cols45-47 rows27-29 sitting exactly between the two
target diamonds (43,28) and (49,28).

Both heads have to thread past long bars:

* a's row band is crossed by the 8-pillar and bar B.  The pillar can be
  retracted out of the band — but every retraction pulls bar A down with it,
  and bar A ends up exactly in the vacated band (bar A always sits directly
  on the pillar's top).  Blocking bar A's descent instead makes the
  retraction itself illegal.  bar B can be lifted clear (e pushes c, which
  drags bar B), which I did.
* 7's column is crossed by c, which can be retracted clear (4 retractions),
  after which 7 drops straight onto (49,28) in 4 growths — I verified this
  sub-plan in search and it is only ~8 moves.

So the level hinges on getting bar A out of the 8-pillar's column while the
pillar retracts.  Nothing I found can move a colour-1 bar horizontally
except a growth in its own row band, and no grower can reach bar A's rows.
That is where I stopped.

## Caveat for whoever continues

`world_model.parse` reads objects out of the grid, so two same-coloured
scenery bars that come to touch merge into one object and the model's
predictions drift from the game (this started happening in level 2 once bar
A and bar B met).  A model that keeps object identity in its state across a
whole level — instead of re-parsing every frame — would fix that, and is
probably a prerequisite for the later levels.
