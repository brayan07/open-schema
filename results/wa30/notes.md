# wa30 — final analysis

Result: GAME_OVER at level 4/9, 4 levels finished, 357 actions
(level_actions = [29, 50, 74, 79], then 125 spent on level 4 before the
budget ran out).

## Mechanics (all confirmed by a green backtest on levels 0,1,2,4)

Board = 16x16 cells of 4x4 px.

- Player sprite: 4x4 block of colour e with one edge line of colour 0 that
  marks the facing. Actions 1/2/3/4 = up/down/left/right one cell.
  A blocked move still turns the player (a turn costs a real action).
- Action 5 = grab / release. It only grabs the box in the cell the player
  FACES. A grabbed box keeps its offset from the player and travels with
  it; while carrying, the facing stays locked toward the box.
- Box sprite BBBB|B99B|B99B|BBBB. Border: 4 idle, 3 = faced by the player,
  0 = held by the player, 5 = held by a rival.
- Containers = 9-border / 2-fill rectangles. Carriers may WALK on container
  cells; the player may not. A carried box may be released into one.
- Strip cells (mottled '2122|1222|2221|2212') are walls that neither the
  player nor a rival can enter, but a box CAN be parked on one. That is how
  a box is handed from one sealed region of the board to another (level 2:
  a wall across the board; level 3: the player is sealed in a room).
- Colour-c cells are rival carriers with the same abilities. They walk to
  the nearest box (BFS distance) that is not already stored, spend one step
  grabbing it, carry it to the nearest empty container cell by BFS, and
  spend one step releasing it. They leave alone any box the player is
  standing within 2 cells of, and they freeze completely while the player
  faces the box they hold — the player can then steal it with action 5.
- A level ends when EVERY box sits released in a container cell.
- Bottom pixel row (y=63): px = round(64 * actions / BUDGET[level]) filling
  from the right. Budgets measured: L0 200, L1 70, L2 100, L3 100, L4 125.

## What killed the run

The bar is a HARD per-level action budget: filling it ends the game.
I treated it as a cosmetic counter to be reproduced for the backtest and
never as a constraint, so I never checked remaining budget before
committing. Level 4 needed ~30 more actions than I had left, and roughly
that many had already been wasted on:
  - 7 actions pushing a box into a rival that was parked in the tunnel
    (the model let a carried box pass through a rival — fixed afterwards);
  - a delivery routed to a container cell that a rival filled first, which
    forced a 12-action detour to the next free slot.

The right play would have been to re-plan every trip against the *live*
board and to keep a running "actions left = BUDGET - used" check, dropping
any plan that does not fit.

## Tooling (outside run/)
v.py compact frame/diff viewer; solve.py Dijkstra tour planner
(box -> container assignment and trip order); prep.py syncs N_OVERRIDE and
refits BUDGET from history; drive.py commits a plan, re-committing the
remainder past rival-only mispredictions and aborting if my own position
derails.
