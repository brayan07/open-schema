# Notes — r11l SOLVED (WIN, 6/6 levels, 79 actions: 9,12,13,14,16,15)

## The game
Only action 6 (click x,y). Column x=0 is an action gauge (a + a//8 cells
filled after `a` actions in the level). Terrain: 5 = floor, 2 and 10 are
blocked; terrain never changes, so the blocked-cell set identifies the level.

### Objects
- ENDPOINT node: filled L1<=2 diamond, centre = group colour, ring 0 when
  SELECTED / 3 when not. Exactly one node in the frame is selected.
- ANCHOR: 5x5-minus-corners blob drawn at the FLOORED CENTROID of its
  group's endpoints, plus blue(1) segments anchor -> each endpoint.
- Both the anchor and its target are painted from a PIE: a fixed angular
  colour partition of the 21/12 cells (clockwise from north, ties at
  0/90/180/270 taking the outer cell first). Level 0-2 pies are one colour.
- TARGET ring: the L1==4 ring minus its 4 axis cells, painted with the same
  pie. It turns colour 0 once its group is parked on it. A ring cell painted
  in a terrain colour (10) belongs to the MAP, so segments draw over it.
- PICK-UP (levels 4-5): a loose blob whose pie is only partly filled
  (0 = empty). An anchor whose blob OVERLAPS one absorbs its colours and the
  pick-up vanishes. Decoy rings exist that no pick-up set can complete.

### Rules
- Click inside a node's 5x5 BOX (Chebyshev <= 2, not the drawn diamond) ->
  select it. Click elsewhere -> move the selected node there.
- A move is REJECTED (the action is still spent) unless the whole node
  diamond lands on floor AND the resulting anchor blob lies on floor or on
  marker cells. Segments are unconstrained — they may cross anything.
- Segment raster: step along the major axis, off-axis coord = origin +
  round(delta) with ties rounded AWAY FROM ZERO.
- Draw order: terrain, segments, rings, pick-ups, nodes (ascending group
  colour), anchors last.
- LEVEL CLEARS when every group is parked on a ring whose pie its own pie
  reproduces.
- Groups are NOT identified by colour: levels 4-5 have two groups sharing
  colour 4, separated by which anchor blob sits on their centroid.

### Cost model
Moving j endpoints costs j moves + (j-1) selects, +1 more if the first one
moved is not the already-selected node. Levels 0-3 needed no staging hops.

## What cost extra actions
- 1 wasted click in level 2: a move destination fell inside another node's
  select box and became a select (the box is square, the sprite is a
  diamond).
- 2 probe actions in level 4 to discover the pick-up mechanic.
- The level-5 route detoured for a pick-up that overlap already absorbed.
