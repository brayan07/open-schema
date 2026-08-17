# bp35 — mechanics, and why level 5 defeats me

## Geometry / rendering  (fully solid; run/world_model.py backtests 184/184)
6px tile pitch. Tile (R,C) inner = rows 6R+1..6R+5, cols 6C+1..6C+5; rows/cols
that are multiples of 6 are separators (colour 10 iff every tile they touch is
mass, else 5). Up to 11 columns C0..C10 (levels use different subsets).
The camera scrolls VERTICALLY only and draws the player's tile inner starting at
view row 37 when gravity pulls UP, view row 27 when gravity pulls DOWN. Frame
row 63 is a per-level action counter (colour 15).
Tiles: 10 MASS (the medium the player swims in) | 5+colour-3 dots VOID |
       14 BOX | 12 CYAN | 8 AZURE  (all three block movement and buoyancy).
Sprites (drawn over a mass tile, punching their shape dilated by 1 to plain 5):
  9/11 player | 7 target | 15 over 11/0/11 killer (both up and down variants)
  | 12 X decal (residue of a dissolved cyan; punches nothing).
A sprite one tile off-screen still marks the frame's edge row — that is how
off-screen killer rows get detected.

## Actions  (all verified)
3 = step left, 4 = step right; only into MASS (void AND all three block types
    block the step). Blocked = stay, facing still flips. 7 behaves like 4.
0 = RESET: restarts the level, restores every block (azures included) and
    gravity=UP, zeroes the counter. Never model-checked by the harness.
6 = click any tile addressable on screen (range unlimited, diagonals fine):
      BOX -> MASS | CYAN -> MASS + X decal | X decal -> back to CYAN
      AZURE -> gravity FLIPS and the block is consumed (one-shot switch)
      mass / void / target / killer / a spent azure -> NO-OP (all tested)
    Addressable rows are player-6..player+4 (gravity UP) and
    player-5..player+6 (gravity DOWN), from y in 0..63.
After EVERY action the player is carried along gravity while the next tile that
way is MASS. Collisions are checked along the WHOLE path, so a target can be won
by merely crossing it and a killer anywhere on the path is fatal.
Re-solidifying an X decal is the only way to stop being carried into a killer.

## Result: levels 0-4 cleared in 154 actions (18, 43, 43, 19, 31)

## Level 5: I believe I am missing one rule
Map (abs rows, C0..C10; player starts abs 6 col 3, gravity UP):
   -10 .......aa..            -4 ..xxxxCxx..   (x = X decal on mass)
    -9 ....aaaaa..            -3 ..aaaaaaa..
    -8 ....a......            -2 ..aaaaaaa..   killers C2-C5
    -7 ....aaaaa..  killers    -1 ......a....
       C5-C8                    0 ......a....
    -6 ..aaaaaaa..              1 ..aaaaaaa..  killers C2,C3,C4
    -5 ..aaaaaaa..              2 ..aaaaa.a..
                                3 ..xxx...a..
     4 ..aaaaaaa..              9 ..aaaaaaa..  killers C2-C7
     5 ......A....  AZURE      10-12 ........a..
     6 ..aaaaaaa..  start     13 .aaa.aaaa..
     7 ..aaaaaaa..            14 .aaAaaaaa..  AZURE C4, TARGET C2
     8 ..aaaaaaxx.  X C6,C7   15+ all void
Exactly two azure blocks exist (verified: every tile of the level has been
observed, and cols 61-63 are void everywhere).

Why that seems impossible:
* Gravity starts UP and the player can only sit on abs 6, so the first flip
  must be the azure at (5,6) -> gravity DOWN.
* With gravity DOWN the only survivable descent is col 8 (the abs 9 killer row
  covers C2-C7), and it bottoms out at abs 14.
* The target pocket {(13,1..3),(14,1..3)} is sealed; its sole entrance is
  (14,4), the second azure.
* Entering the target needs gravity DOWN (with gravity UP you cannot stand on
  (14,1)/(14,3) — abs 13 is mass there — and abs 15 is void, so it cannot be
  crossed from below). So an ODD number of flips is required; two azures give
  an even number, and dissolving (14,4) is itself the second flip.
* An exhaustive 1.4M-state search over (row, col, gravity, every block/decal
  configuration) confirms the target is unreachable under the rules above.
  The search DOES solve it in 12 actions if clicks may address off-screen
  tiles — but clicks are demonstrably camera-relative and y is capped at 63.

Ruled out by experiment (each cost one action): blocks being walkable,
clicking the target, clicking a killer, clicking void, clicking the player's
own tile, re-solidifying a spent azure, blocks being pushable, X decals
blocking buoyancy, RESET keeping dissolved blocks. Ruled out by the recorded
history: action 7 being anything but "step right", the azure setting an
absolute gravity rather than toggling, killers being solid, the settle being
non-maximal or deferred.
