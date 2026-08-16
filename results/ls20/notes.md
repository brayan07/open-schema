# ls20 — WIN, 7/7 levels, 497 actions
level_actions = [19, 45, 41, 49, 52, 94, 197]

## The game
Carry a 3x3 "key" (shown bottom-left) to a lock box and step into its centre.
The key must match the lock's 3x3 pattern in BOTH shape and colour.

## Geometry / actions
- 5x5 pixel cells at x=4+5c, y=5r (c 0..11, r 0..12). 1=up 2=down 3=left 4=right.
- Colour 4 (wall) is the only blocker. Player sprite = 2 rows of 12 over 3 of 9.

## Tiles (all walkable; effect fires on entering the cell)
- lock box: 9x9 colour-3 outline round a 7x7 colour-5 interior, centred on one
  cell, holding the 3x3 lock pattern. Entering the centre with a matching key
  dissolves the box; a level may stack two and only the dead-end one (fewest
  open neighbours) ends the level. Entering with a mismatched key is refused,
  and the refusal costs no bar.
- rotator `.0./100/.1.`: rotates the key 90 degrees CLOCKWISE.
- reshaper `X../.XX/.X.` (colour 0 only): replaces the key's shape,
  orientation-preserving. Shapes run in a 6-cycle:
    D=X.X/XX./.XX -> E=XXX/.X./.X. -> F=XXX/X.X/X.X -> G=.X./X.X/XX.
    -> H=XX./.XX/.X. -> I=X.X/X../XXX -> D          (also A=.X./XX./.XX -> rot180(I))
  rot180 of that cycle is a second, disjoint cycle, so crossing between the two
  requires the rotator. The underlying rule was never identified — the model
  just uses the transitions observed (LEARNED_SHAPES).
- recolour pinwheel: key colour advances 9 -> 14 -> 8 -> 12 -> 9.
- ring (colour-11 outline): refills the bar; one use per level attempt.
- launcher: a colour-1 stripe painted on a wall face; entering the cell beside
  it glides the player away from that face over plain floor, stopping on the
  first cell that is not plain floor. One action for the whole glide.
- In levels 4, 5 and 6 some tiles patrol a fixed beat, one cell per action.

## Bar and lives
- Bar x13..54 (42 px) at y61-62; pixels per action are per-level [1,2,2,1,2,1,2].
- Emptying it spends one of the three colour-8 tokens at x56-63 and RESTARTS the
  level: player back to the entry, key back to its start, every ring restored.
  Two of the three tokens were spent (both on level 6).

## Level 6
Played in the dark: only a disc of radius^2 399 around (sprite x0+1.5, y0+1.5)
is drawn, everything else painted colour 5; the HUD (key glyph x3-8 y55-60, bar
x13-63 y61-62) is drawn over the fog. The world model therefore stores the union
of everything ever lit as that level's background.

## Known gap
No triangle-wave fit reproduced every sighting of level 6's patrolling rotator
(column 10, rows 1..6), so the model mispredicts frames where its marker is
visible and the backtest is not green over those. It was worked around by
reading the marker off the live frame and stepping onto the cell it was about to
enter, which landed both required rotations first try.
