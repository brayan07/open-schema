# tu93 — WIN, 9/9 levels, 204 actions
level_actions = [18, 15, 19, 17, 35, 34, 14, 23, 29]

## The game
A node/edge maze walked one node per action; reach the goal node.
Frame 64x64, bg=5. The maze is the bounding box of non-5 pixels above row 63,
in 3px cells, forming an odd x odd "coarse" grid: (even,even) = node,
exactly-one-odd = edge (2 passable, 5 wall).  Node values: 0 plain, 14 goal.
Actors sit on nodes as a filled block plus ONE marker pixel on the side they
face (player marker 4; actor markers 15, ambusher 11 once it has lunged).
Row 63 is a bar filling from the right: zeros = round(64*moves/BUDGET), with a
per-level BUDGET: 50, 50, 35, 20, 50, 60, 30, 50, ~50.

Actions 1=up 2=down 3=left 4=right, 0=RESET (restarts the level, keeps level
progress).  A blocked move still burns a move and advances nothing.

## Actors
- ambusher (8): stands still; the instant the player steps into the ONE node it
  faces, it lunges onto that node and kills.  Harmless from any other side.
- walker (12): steps one node along its facing every player move, reversing at
  the end of its corridor.  Kills by stepping onto the player.
- hunter (13): dormant until the player steps anywhere along the line it faces.
  That turn it only wakes (marker 15 -> 11); afterwards it chases the player's
  WAKE -- it heads for where the player stood two moves ago and then walks the
  player's exact route at that lag.  Kills on contact.  Because the maze is
  bipartite it stays pinned two nodes back and can never be caught, so levels
  with a hunter are solved by lapping a cycle to put it behind you.
- Stepping onto an actor destroys it.  Every kill I made was a SIDE entry;
  entry from directly behind stayed untested and the model treats it as fatal.
- Walkers pass straight through ambushers, harming neither.  Stacked actors
  draw only one block: the walker covers the ambusher unless the two face along
  the same axis; among stacked walkers the last in (row asc, col desc) wins.

## Model
run/world_model.py is stateful (init_state/predict) because the frame cannot
show stacked actors: it replays walkers from each level's embedded entry frame
and phase-matches them against the frame (blocked moves desync the bar from the
walker clock).  run/embed_entries.py re-embeds those frames as literals -- the
model sandbox has no file, json or builtins access.

## Tools
run/layout.py  coarse dump of the current frame + actor markers
run/budget.py N  feasible BUDGET values for level N from the recorded bars
run/simplan.py L '[acts]'  dry-run a plan, showing kills and actor positions
run/plan.py L DEPTH NODES [target] [nokill]  planner keyed on model state
  rather than rendered frames (arc3 bfs splits states on the facing marker and
  the progress bar, which made levels 7-8 intractable)
