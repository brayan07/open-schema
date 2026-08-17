# m0r0 — SOLVED (WIN, 6/6 levels, 226 actions)
level_actions = [18, 23, 67, 25, 48, 45]

## The game
Each frame is a grid of SxS-pixel cells (geometry differs per level and is
auto-detected). Walls are the two background colours (px (1,0) = left half,
(1,63) = right half); floor is 5.

TWO avatars (colour 10) move on every action, MIRRORED horizontally:
  1 = up, 2 = down (both);  3 / 4 = horizontal, one avatar each way.
Which avatar takes the unmirrored sign is per-level: levels 0-3 and 5 give it
to the LEFT avatar, level 4 to the RIGHT one (world_model.HFLIP).
Each avatar is blocked independently by walls and the frame edge.
Action 5 is a no-op.

GOAL of every level: get both avatars into the SAME cell.
Because the controls are mirrored, this is only possible where the level's
layout is deliberately asymmetric — that asymmetry is the puzzle.

## Objects introduced level by level
L0/L1  plain mazes.
L1     CHECKERBOARD cells (colour 8 on 5): stepping into one RESETS the level
       (positions restored, action meter keeps running, dead flag stays False).
       Blocks a selected marker. Verified the hard way on level 3.
L2     MARKER cells (solid patch inside a floor border): impassable doors.
       Click one (action 6) to SELECT it — its patch turns 11, the avatars dim
       to colour 1 and stop responding; arrows then walk THAT marker one cell
       per action in ABSOLUTE directions (never mirrored). Click an avatar to
       select the pair again. Solution: park blocking doors in dead ends.
L4     GATES (bands of same-coloured solid cells) and SWITCHES (isolated cells
       of a gate colour). A gate is open exactly WHILE an avatar stands on a
       switch of its colour — pressure plates, not latches. Since both avatars
       move every turn, the trick is to pin one avatar against a wall/marker/
       closed gate so it holds its plate while the other crosses.
L5     All of the above at once: lethal border, two plate-gate pairs, and one
       marker sitting on the only crossing of the mirror axis.

## Action meter
The black strip eating rows 0 and 63 from the outer corners is an action
counter: after `a` actions in a level it shows (3*(a+1) - lost)//7 pixels at
each end, where `lost` absorbs a rare 1-unit hiccup. Full strip ~ 150 actions,
which is the per-level budget the designers had in mind.

## What cost extra
- 4 actions relearning the mirror convention on levels 4 and 5.
- 4 actions to a checkerboard reset on level 3 (the one real mistake).
- Level 2's 67 actions are mostly irreducible: three doors had to be walked to
  parking spots one cell per action, with a click to change selection.
