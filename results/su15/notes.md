# su15 — SOLVED (WIN, 9/9 levels, 216 actions)

per-level actions: [14, 16, 18, 18, 12, 9, 6, 80, 43]
Levels 0-6 were played near-optimally; levels 7-8 cost ~120 actions because
the hazard mechanics (below) had to be discovered by losing and resetting.

## Board
- rows 0-9: inert display band; clicks there do nothing at all.
  - top-LEFT panel: legend of 2x2 swatches. Swatch k = piece RANK k.
    colours 10,6,15,11,12,8 -> drawn side 1,2,3,4,5,7 (rank 6 is a 7x7!).
    A second legend row (7,14,13) is the HAZARD rank ladder.
  - right of the panel: the level's GOALS, drawn full size, plus an icon of
    the hazard rank that must exist at the end (14 = one fusion, 13 = three).
- rows 10-62: playfield. Maroon(9) 9x9 discs are the delivery slots.
- row 63: budget bar; running out = GAME_OVER (action 0 restores the level).

## Pieces
- ANCHOR = topleft + (side//2, side//2).
- A click at P gathers every piece whose NEAREST CELL is within radius 8
  (squared edge distance <= 64) and teleports it so its anchor is at P.
  One piece -> it moves. Two of equal rank -> they FUSE into rank+1 at P.
  Anything else (mixed ranks, 3+) -> the whole click is rejected.
- A move is also rejected if the destination square would overlap a hazard's
  bounding box.
- Budget bar cost per playfield click: levels 0,1,4,5,6,8 -> 2k;
  level 2 -> (4k+4)//3; levels 3,7 -> (4k)//3.

## Hazards (the key to levels 3-8)
- 8-cell diamond outline; each click every hazard steps at most 4 per axis
  (faster in later levels) toward the ANCHOR of the nearest piece, using
  ceil-rounded sprite centres.
- Landing on a piece SHRINKS it one rank and throws it 10 cells along the
  hazard's direction of travel (clamped to the playfield); rank 1 dies.
  Shrinking is the intended way to turn an oversized piece into the goal.
- A piece that MOVED on that click is IMMUNE, so a piece you click every
  turn can never be hit -- and it acts as a decoy that all hazards follow.
- Two hazards that meet FUSE into the next hazard rank (7+7 -> 14,
  14+14 -> 13). The band icon says which rank is required.
- Losing mass you cannot spare turns the goals and discs RED = unwinnable;
  action 0 resets the level.

## Winning recipe for the hazard levels
1. Build/park every goal piece except one on its disc, FAR from the hazards.
2. Keep the remaining oversized piece central and re-click it every turn:
   it is immune, it absorbs exactly the shrinks you want, and it draws all
   hazards together so they fuse.
3. When the required hazard rank exists, move the decoy onto the last disc.
