# tn36 — final analysis (level 0 solved, level 1 not)

Result: 1 / 7 levels, 2988 actions. Level 0 cost 1632 actions (nearly all of it
spent discovering the mechanic); level 1 was not cracked.

## Mechanics established (with evidence)

- Only action 6 (click) does anything. Actions 1–5 are accepted but are complete
  no-ops (they do not even tick the level timer). Action 0 (RESET) is legal only
  after death.
- Every level = a **board** (checkerboard of 4x4 cells, colours 4/5) holding a
  b-coloured **piece** and a matching **socket**, plus a **control panel** of
  toggles, plus a round **lamp** wired to the panel.
- The piece's 4x4 cell is a full square minus 2 cells on one edge; the socket's
  cavity has a matching 2-cell bump. **The notch faces the direction of travel.**
  L0: notch down, piece (r1,c4) -> cavity (r6,c4), 5 cells down.
  L1: notch up,   piece (r5,c3) -> cavity (r1,c3), 4 cells up.
- Panel toggles: each unit is a CAP (3x1 horizontal bar) plus a STEM (1x3
  vertical bar); each is an independent 2-state toggle, blue(1)=on, grey(5)=off.
  L0: 1 group x 5 units (10 toggles).  L1: 3 groups x 4 units (24 toggles).
  Units per group = (board width + 1) / 2 in both levels.
- Row 1 is a 61-cell timer; one cell turns green per action; at 61 the level is
  GAME_OVER/DEAD. RESET restores the timer, the panel and the board exactly
  (fully deterministic), and does not itself consume timer ticks.
- **Nothing on screen ever changes except the timer and the toggles you click.**
  Verified over ~3000 actions: the board, piece, socket, lamp and side displays
  never changed once. There is no feedback of any kind, so search is blind.

## Level 0 solution (found)

Set all 10 toggles to grey (off), then click the lamp centre. The lamp is a
submit button: clicking it at 15+ other panel states, and clicking the piece /
socket / every board cell at the all-off state, all did nothing.
Cost me 1632 actions because it required a state x click-target cross product
sweep after all 1024 panel states and ~300 click positions had each been swept
alone without effect.

## Level 1 (unsolved) — what it looks like and what was ruled out

Screen is split. Right half = the live machine: board (7x7 cells, cols 33–60,
rows 4–31), panel rows 32–50 (cap rows y=33/39/45, stem rows y=36/42/48, unit
columns x=39/44/49/54), lamp centre (46,58). Left half is **not clickable**: a
green board showing an example piece at cell (r3,c5) with its notch on the LEFT,
a red copy of the panel, and two 7x7 minimap boxes at the bottom.
  - Box A (cols 8–14, rows 55–61) = minimap of the example board: socket blob at
    rows 2–4 / cols 0–1, dots at (r3,c3) and (r3,c5) = midpoint and piece.
  - Box B (cols 18–24, rows 55–61) = minimap of MY board: socket blob rows 0–1 /
    cols 2–4, dots at (r3,c3) and (r5,c3).
  So the example is the same puzzle rotated: travel 4 cells LEFT instead of UP.
- Red (example) panel = group-1 caps all grey, all other 18 toggles blue.
  Right panel starts with exactly two greys: (G2 stem, unit0) and (G3 cap, unit0).
- Tried and failed, each submitted with a lamp click:
  * copying the red example panel exactly;
  * all 64 "every row uniformly on/off" states (includes all-off, all-on, and
    every single-row-off which is the direct analogue of the example);
  * example pattern + the two initial greys preserved (6);
  * whole unit-columns grey: stems only, caps only, all six rows (12);
  * vertical runs of 4 consecutive rows in one unit column (12);
  * every contiguous run inside a single row, lengths 1–3 (54);
  * 165 of the 256 states of group 1 alone (Gray sweep) — budget ran out here;
  * alternative submit targets (both minimap boxes, piece, cavity, green board,
    wire) at four different panel states.

## Best remaining hypothesis

The panel is a picture to be drawn in grey: the example draws a horizontal line
of 4 caps for a 4-cell horizontal journey. The obvious dual — a vertical line of
4 — cannot be drawn in a 3-group panel, and every "line-like" variant above
failed, so the encoding must involve the group index and the two initial greys in
a way I could not pin down. With no feedback signal anywhere, the only reliable
route left is exhausting group 1 (91 states remain) and then groups 2 and 3.
