# sb26 — SOLVED (WIN, 8/8 levels, 128 actions)

level_actions = [13, 15, 15, 15, 17, 19, 17, 17]

## Action semantics (all confirmed by a 128/128 green backtest)
- 6 = click.
  - click a palette item (bottom strip): SELECT it (drawn with a 0 ring). FREE.
  - click a 2x2 slot marker (colour 2) inside a panel: PLACE the selected item
    there. Slot rect grows by 1 on each side into a 4x4; a solid item paints
    solid, a hollow "door" item paints only its outline. The palette item
    shrinks to a 2x2 colour-2 marker. Selection clears. Costs 1 bar tick.
- 7 = UNDO the last placement. FREE.
- 5 = SUBMIT. Costs 1 tick. Advances the level iff the arrangement is right.
- Row 53 is a per-level budget bar (2 -> 3 from the right), 64 ticks. Never
  came close: the hardest level used 10.

## The game
A LISP-ish "expand the nested list" puzzle.
- Top strip = the required flat colour SEQUENCE (level 7 uses two rows = 12).
- Middle = panels. Each panel has evenly spaced positions; a position is
  either an empty 2x2 slot, a pre-filled 4x4 colour block, or a hollow
  4x4 DOOR whose colour names another panel (matched by that panel's border
  colour; level 1 also drew a literal pipe from door to panel).
- Bottom palette = the exact multiset of items to place (solid colours plus
  hollow doors). #palette items == #empty slots, always.
- Goal: fill every slot so that flattening the root panel (the one with the
  8 border) left-to-right, splicing each door's panel in place, reproduces
  the top sequence. Then press 5.

Level progression: 0 flat list; 1 one nested panel (with pipe); 2 two doors;
3 the door itself must be placed from the palette; 4 the same panel used by
two doors (repeated subsequence); 5 three sibling panels; 6 depth-3 nesting
(palindrome); 7 MUTUAL RECURSION — root=(8,b,c,door9), panel9=(9,e,f,door8),
whose unrolling is the period-6 sequence shown twice.

## Files
- world_model.py — stateful (undo stack); ENTRY_GRIDS memoises each observed
  level-entry grid so level-up steps predict the next grid.
- mkentries.py regenerates ENTRY_GRIDS; g.py dumps row-runs of the current
  grid; sim.py dry-runs plan.json through the model.
