# sc25 — SOLVED (WIN, 6/6 levels, 196 actions)
level_actions = [22, 5, 34, 29, 58, 48]

## Full mechanics

**Player.** An NxN square (N=4 or 2). The half on the side it FACES is
colour 9, the other half colour a.
Actions 1/2/3/4 = up/down/left/right: turn to face that way AND move N
pixels if the whole destination square is floor (2); if blocked, it only
turns. Action 6 = click(x=col, y=row). Floor = 2; marks (b/f/4-brackets)
drawn on floor are walkable; 5 = void; c/d = locked gates (solid).

**Goal.** Overlap the DOOR (a 9-framed box with an 'a' interior) -> LEVEL_UP.

**The board** (rows47-63, cols22-38): a 3x3 grid, cell centres
x = 25/30/35, y = 50/55/60. Clicking a cell arms it (-> e); clicking an
armed cell disarms it. When the armed set equals one of the level's
COMBINATIONS, the board clears and that combination fires.

**Mini panels** (10x10 boxes with a 3 border) show the available
combinations, each drawn in the colour of what it acts on:
  - `f` = diamond (0,1),(1,0),(1,2),(2,1) -> TOGGLE player size 4x4 <-> 2x2.
    The new square grows FORWARD (facing direction) and down/right on the
    other axis; if that square isn't all floor the fire is a silent no-op.
  - `6` = middle column -> COLLECT the 6-framed key. Needs aim: the player
    must FACE the key and its perpendicular span must be contained in the
    frame's, and the straight line between must contain no void (5).
    Walls of colour 4 are transparent to the beam; c/d gates are NOT.
    Collecting a key turns every wall of that key's colour into floor.
  - `b` = (0,0),(0,1),(1,1) -> WARP to the b-pad matching the player's
    current size. No aim needed. Pads are drawn with corner marks; the
    ACTIVE destination additionally has outer diagonal marks, and which
    pad is active alternates as the level state changes.

**Meter** (cols62-63, e=left, 0=used): ~1 row per action, resets per level.
Never ran out; unclear what happens if it does.

## Lesson learned
Firing a combination with the aim/size precondition unmet is a silent
no-op that still costs an action — check facing + alignment + a void-free
line first. Most wasted actions in this run came from that (level 2).
