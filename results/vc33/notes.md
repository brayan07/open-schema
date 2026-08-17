# vc33 — WON (7/7 levels, 195 actions: 8, 8, 24, 42, 44, 20, 49)

## The game
The playfield is cut by WALLS (colour 5, `thick` px thick) into rectangular
ROOMS.  Every room's OPEN area (0) grows from one fixed side of the room (the
same side for all rooms in a level); `h` is its depth in px.  Levels 0-4 are
one row/column of rooms, levels 5-6 are 2-D room layouts.  Raw row 0 is a
cosmetic per-level action meter, `round_half_up(rate*k)` px wide, rate = 64/B
with B = 50, 50, 75, 50, 200, 50, 200 for levels 0..6.

`thick` = wall thickness = 9-button size = CLICK STEP; `au = ceil(thick/2)`
is the glyph unit (arrow 3*au long, knob au, fat gate mark 4*au).

## Rules (all confirmed by backtest over the whole run)
- 9 BUTTON: sits at the anchor-most end of the boundary a room shares with one
  neighbour, on that room's side. Clicking it moves `thick` px from that
  neighbour into this room. No-op if the donor would go below 0 or the
  receiver past its CAP (the shortest wall bounding it).
- ARROW: rides a room's edge, centred across the room. Its colour names its
  target KNOB (an au-long mark inside some wall).
- FAT MARK (4*au long, colour 1): a GATE. It LIGHTS (colour 12, plus a 1-px
  open channel 2 px either side of the wall, spanning the mark inset by au)
  exactly when BOTH rooms it separates have their edge on the mark's first
  pixel. CLICKING A LIT GATE walks the arrow across that wall; if both rooms
  hold arrows, the two swap.
- LEVEL COMPLETE when every arrow sits in a room bordering the wall that holds
  its same-coloured knob, with the room's edge exactly on the knob.

So each level is a flow problem (heights are conserved, moved in `thick`-px
units between neighbouring rooms) plus a routing problem (walk each arrow to
a room adjacent to its knob, paying the gate alignment costs on the way).

## Models
world_model.py  levels 0-4 (general 1-D stripe parser)
world_model2.py level 5, world_model3.py level 6 (topology tables + the same
mechanics; the harness uses the newest world_model*.py, so scope backtests
with `--level N`).
