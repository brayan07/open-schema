# tr87 — WIN (6/6 levels, 407 actions: 21, 26, 28, 107, 81, 144)

## The game: a transliteration puzzle

Screen: an upper field (bg 2) holding a LEGEND, a lower field (bg 3) holding
two words, and row 63 = a per-level action bar (64 cells, colour 1 -> 4 from
the right; one cell per 2 actions on levels 0-4, per 4 actions on level 5).

A "box" is a rectangle of border colour C, height 7 and width 7*n; it holds
n 5x5 glyphs (foreground 5) at cols c0+1+7i. Colour = script.

* lower field: the upper box is the GIVEN word, the lower box is the ANSWER.
* upper field: legend rules, laid out in bands as `src box --333-- dst box`.
  A rule rewrites the src glyph string into the dst glyph string; the legend
  may be a CHAIN of scripts (level 3: a->7->b, level 5: a->7->b).

Win: translating the given word through the legend spells the answer word.

## Actions
  1 next symbol, 2 previous symbol (cyclic, 7 symbols per script)
  3 / 4 move the colour-0 bracket left / right around the ring of editable
  cells (wrapping).

Which cells are editable depends on where the bracket starts:
* bracket in the lower field  -> the answer word's slots, one glyph each
  (levels 0-3: fill in the translation).
* bracket in the upper field  -> the LEGEND boxes, ONE BOX PER RING CELL
  (levels 4-5: repair the legend). Pressing 1/2 advances *every* glyph of
  the box by one step together, so the cyclic offset between a box's glyphs
  is fixed for the whole level — a 2-glyph box can only be rotated, never
  rearranged. That is the key constraint on level 5.

## Rotation is cosmetic
Every glyph is drawn at some rotation; letter identity is its rotation
class. Each editable cell has its OWN fixed rotation which never changes,
so the legend, the words and the cells can all show the same letter turned
differently.

## Files
`world_model.py` — geometry + simulation; CYCLES/KFIX/SEEN/RATE/ENTRY are
tables re-derived from played history by `../learn.py` (a new level's frame
is unpredictable, so level-entry frames are recorded rather than predicted).
`../goal.py`, `../goal5b.py` — what each cell must end up showing;
`../plan.py` / `../drive.py` — shortest / exploring executors.

## Cost postmortem
Levels 0-2 were near-minimal. Level 3 wasted ~85 actions because the
learned alphabet was keyed by script COLOUR instead of by level (fonts are
regenerated every level), and level 4-5 wasted ~90 more before I realised
the legend ring is box-level, not glyph-level, and that a box's glyphs are
linked. Both were mechanic discoveries, not search failures.
