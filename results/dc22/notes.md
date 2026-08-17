# dc22 — notes

Levels 0-3 solved (29 / 45 / 50 / 66 actions). Level 4: STUCK — analysis below.

## Screen
- LEFT panel = maze (bg 4). RIGHT panel = widgets (bg 5), separated by a dashed
  colour-0 column pair. Row 63 is a tick meter: ceil(ticks/div) lit pixels,
  div per level (L0 2, L1-3 3, L4 12).
- Ticks: 1 per action (2 per action on L4), +1 extra for a click that flips a
  body, and a big penalty (~20 on L3, ~30 on L4) for a *refused* click.
  Ticks are cosmetic — they do not gate anything — but the world model has to
  reproduce them, so `TICKS_NOW` is recalibrated by hand after each commit.

## Confirmed mechanics
- Player = 2x2 block of colour 14, moves 2px per step; 1=up 2=down 3=left
  4=right. A move is legal iff ALL FOUR destination pixels are non-background.
  Blocked moves still cost an action.
- Goal = colour 11 marker; stepping onto it completes the level.
- Everything non-background is walkable (rooms 2, pipes 8/9/d/7/f, black 0,
  corridor cells 1/12, ...). A "ghost" (checkerboard: colour only where (r+c)
  is odd) is NOT walkable because half its pixels are background.
- Clicks only work on the RIGHT panel; clicking the maze never does anything.
- Widget types seen:
  * standard button (7x3 over 13x2 glyph, drawn in the body colour) — flips
    that body between two configurations (a 90-degree arm rotation about a
    pivot, or which of several gate zones is solid).
  * portal pair — two rooms each holding a 2x2 6/7 marker; clicking the 6
    button swaps the markers AND carries the player if it stands on one.
  * b-shaped widget (4x3 over 7x4) — slides colour-1 blocks one cell along a
    rail; top segment and bottom segment move opposite ways; at the end of the
    rail the block turns colour 12 and the next click wraps it back.
  * 6x6 colour-2 pad — adds/removes 2 corridor cells; corridor cells fill from
    both ends inwards, gap drawn colour 5, a full corridor drawn colour 12.
    It ping-pongs between empty and full.
  * four 4x4 blocks (a,9,a,9) — up/down/left/right nudges for a sprite.
- IN-MAZE SWITCH ROOM: a room carrying a small copy of the button glyph in
  colour C. WALKING INTO it consumes the glyph and UNLOCKS body C's button in
  the right panel (clicking the glyph from afar does nothing).
- A click that would strand the player (move a block/gate out from under it)
  is REFUSED: nothing changes and the tick meter jumps by the penalty. So the
  player can never ride a body; instead it walks along a sliding block, one
  step per slide (that was the trick in level 3).

## Level 4 — where I got stuck
Left panel rows 0-62, cols 0-37. Widgets: b (block slider), 2 (corridor),
a/9/a/9 (arrow nudges), 8 (9x3, inert => LOCKED), 9 (gate), 6 (portal).

Map (rows, cols):
  A  6-9,22-25 room w/ portal marker      CC 10-21,20-25 colour-c corridor
  SW 18-21,10-13 room w/ colour-f switch glyph  (unlocks the f button)
  B  20-23,26-29 room                     C  30-33,26-29 room  <- PLAYER
  D  34-37,30-33 room                     9-gate zones 34-37,26-29 / 38-41,10-13
  E  34-37,10-13 room w/ portal marker    F  42-45,10-13 room
  CORR5 44-45,14-29 (8 corridor cells)    f zones 46-53,26-29 / 50-53,14-23
  G  50-53,10-13 room w/ GOAL             1-block 54-55, rail cols 14..29
  BLACK 14-17,3-19 + 18-25,3-6 + 26-29,3-18, walkable, with an 8-coloured
  arrow sprite sliding on it (its 1x2-cell middle is the only part a 2x2
  player fits in). The sprite is confined: its middle must stay over black.

Verified reachability: the player's component is exactly {C, 9-gate, D} — 12
cells — and EVERY frontier cell is full background (the ghost cells have 2
background pixels, so they are walls). No available body can reach that
frontier: the gate only has those two zones, the corridor is fixed at rows
44-45, the block rail is rows 54-55, the portal markers are in A and E, and
the arrow is locked to the black track. Clicking the gate while standing on
it is refused, so the gate is not a transport either.

Two links are missing for the level to be solvable:
  1. the player's pocket has no exit;
  2. BLACK+SW is only adjacent to CC through the "notch" at cols 20-21,
     rows 14-17, whose pixels (14,21) and (17,21) are background, so a 2x2
     player cannot pass (both candidate cells have exactly one background
     pixel).
Both would be explained if either (a) a move is legal with one background
pixel in the destination, or (b) an as-yet-locked body (the 8 widget is drawn
incomplete, i.e. locked; the f body has no button at all) owns extra zones —
e.g. an f zone at rows 22-29, cols 26-29 would join B to C. (I checked the
arrow: driving it to (12,18) would have completed the notch, but that
position is refused — its middle would leave the black track, so the arrow
tops out at (12,14), leaving both notch cells at exactly one background
pixel.) Both unlock switches (SW for f, presumably the arrow itself for 8)
sit inside BLACK, which the player cannot reach, so I could not bootstrap
either one. Note also that f has one SOLID zone despite having no button,
which does not match level 2, where a locked body had all zones ghosted —
so the f body may have a control I never found.

Probes already spent and negative: every right-panel widget and every one of
its sub-cells; clicking the maze (goal marker, player, rooms, black, notch,
switch glyph, arrow); standing on the gate and clicking 9/6; driving the
arrow over its whole track; filling/emptying the corridor; running the block
rail end to end and wrapping it.

## Model
`run/world_model.py` reproduces the maze mechanics of every recorded
transition. The only residual mismatches are (a) the four level-boundary
frames, whose after-grid is the next level's entry frame and is therefore
unpredictable, and (b) single-pixel row-63 (tick meter) drift on level 4:
the tick cost of a click that hits nothing / is refused is not a single
constant there, and no (div, move, click, refused) tuple fits all 64 level-4
transitions. Every mismatch outside those two categories was chased down and
fixed, so the *maze* dynamics in the model are fully validated.
