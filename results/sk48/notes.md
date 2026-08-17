# sk48 — notes (final)

Levels 0-6 finished; level 7 not solved.  world_model.py reproduces every
recorded transition of levels 0-4 exactly (bar row 53, the cosmetic clock).

## Mechanics (all verified in play)
CARRIERS.  The PLAYER is a 6x6 box on a vertical pole at the left of the field
with a horizontal ARM (2 rows) that grows/shrinks in steps of 6.  From level 5
there is also a CRANE: a box on a horizontal rail at the top with a vertical
CABLE.  Exactly one carrier is active; action 6 (click) on the other box
switches control (its interior turns 0 and its beam takes the arm texture).
For the active carrier: 1/2 move it along its track, 4/3 grow/shrink its beam
(player: 1 up, 2 down, 4 out, 3 in; crane: 3 left, 4 right, 2 down, 1 up).

BLOCKS.  A block is HELD by a beam exactly when it lies inside the beam's span
— pure geometry, there is no per-block state.
- GROW: every block inside the new span is shoved 6 along if it can move
  (a moving block shoves whatever is in front of it); one that cannot move
  (field edge, hole, another stuck block, or the other carrier's beam) stays
  put and the beam threads through it.
- SHRINK: held blocks are dragged 6 back if they can; one that cannot stays and
  drops off the tip — that is the only way to let go of a block.
- MOVE: blocks the beam carries, and blocks it sweeps into, travel with it and
  chain-push others; the move is blocked if any of them would hit a wall/hole.
- The other carrier's beam blocks motion across it (a block cannot be pushed
  sideways onto the cable's columns, or up/down through the arm's rows).
- HOLES (colour 5 inside the field) stop beams and blocks alike.

GOAL PANEL.  One 6x6 box per carrier (icon = cable anchor colour, none = the
player's arm) followed by the wanted blocks.  Icon i is hollow when the i-th
block that carrier holds matches it (arm: ordered by distance; cable: top
down).  All hollow => level up.

## Level 7 (unsolved) — state and analysis
Field rows 8-49.  The crane's rail is only 14 wide, so its cable is stuck on
columns 31-32, i.e. block column 30.  Goal: arm = [9, e], cable = [8, c].
Blocks: 8 (33,24) and c (33,30) held by the arm at band 32; 9 (39,30);
e (45,30).

What blocks the solution: a block leaves a beam only when it cannot follow the
beam's retraction, so the arm can only shed blocks that are packed against the
LEFT WALL (columns 12, 18, ...) and the cable only blocks packed against the
CEILING.  Column 30 has no backstop for the arm, so the arm cannot put a block
down there.  Two further facts I measured:
  - the arm's grip beats the cable's push (a block held by the arm did not move
    when the cable was extended down onto it), but
  - the cable's grip does NOT beat the arm's pull (that same block was dragged
    away when the arm retracted),
so "hand the block to the crane" does not work either.
The remaining idea, untested: bring 8 and c to column 30 from ABOVE with the
cable (blocks pushed down the cable's own column stack on the 9/e already
there), which needs them first to be parked on column 30 higher up — reachable
only by the arm carrying them vertically, which is where the release problem
bites.  I could not find a legal ordering in the time available.
