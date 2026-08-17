# open-schema — an open replication of the Schema ARC-AGI-3 harness

**Status: work in progress, shared openly.** Single-run results for the
full 25-game public set are being collected now; this repo updates as
they land.

[Schema](https://schema-harness.github.io/) reported 95.35% (GPT-5.6 Sol)
and 98.98% (Claude Opus 4.8 + Fable 5) RHAE on the ARC-AGI-3 public set,
but released only 50 gameplay trajectories and a scoring utility — no
harness. This project:

1. **Reconstructs the harness from its own traces** — the world-model
   contract, the sandbox's exact injection surface (`np`,
   `CURRENT_LEVEL`, `ENTRY_GRID`), model re-initialisation at level
   entry, the event schema, and the tool surface — and validates the
   reconstruction against all 50 released trajectories.
2. **Reports what Schema did not**: *single-run, no-fallback* numbers,
   from sealed agents (no game source, no web, no prior notes), with
   audited transcripts and event logs scoreable by Schema's own
   released scorer.

## Results so far (sealed, single-run, no fallback — Claude Opus)

| game | levels | actions (vs human) | RHAE | wall-clock | audit |
|---|---|---|---|---|---|
| sb26 | 8/8 WIN | 128 (213) | **100.00%** | 0.23 h | clean |
| ls20 | 7/7 WIN | 497 (776) | **100.00%** | 1.75 h | clean |
| ft09 | 6/6 WIN | 75 (208) | **100.00%** | 0.9 h | clean; 1 logged infra rerun |
| ar25 | 8/8 WIN | 265 (748) | **100.00%** | 0.55 h | clean |
| tr87 | 6/6 WIN | 407 (414) | **83.89%** | 1.03 h | clean |
| tn36 | 1/7 STOPPED | 2988 (210) | **0.00%** | 1.13 h | clean |
| tu93 | 9/9 WIN | 204 (462) | **100.00%** | 1.24 h | clean |
| lp85 | 8/8 WIN | 105 (388) | **100.00%** | 1.2 h | clean; interrupted+resumed (logged) |
| r11l | 6/6 WIN | 79 (233) | **100.00%** | 1.44 h | clean; interrupted+resumed (logged) |
| cd82 | 6/6 WIN | 217 (171) | **100.00%** | 2.42 h | 1 hit, reviewed benign (guard blocked; see audit-note) |
| g50t | 7/7 WIN | 415 (879) | **94.45%** | 1.9 h | clean; interrupted+resumed (logged) |
| m0r0 | 6/6 WIN | 226 (1107) | **100.00%** | 1.2 h | clean |
| sp80 | 4/6 STOPPED | 435 (518) | **31.41%** | 2.4 h | clean; honest stall, model green, goal semantics unsolved |
| cn04 | 4/6 STOPPED | 164 (789) | **47.62%** | 2.46 h | clean; premature stop with budget+hypothesis in hand |
| vc33 | 7/7 WIN | 195 (447) | **100.00%** | 1.06 h | clean |
| *remaining 10* | *in progress* | | | | |

**Running mean over 15 completed games: 84.29%** (ten 100s, 94.45, 83.89, 47.62, 31.41, 0).

Reference: Schema's best-of-two per-game results for these games:
sb26 98.63%, ls20 100%, ft09 100%, ar25 100%, tr87 100%. The single-run
protocol reports the first attempt as it happened — tr87's 83.89% (a slow
level 3) is the kind of variance best-of-two hides.

**Contamination caveat, stated up front:** the 25 public games and
Schema's traces have been public for months and may be inside the
evaluated models' training windows. Sealing controls what an agent
*reads* during a run, not what its weights *remember* — a caveat that
applies equally to Schema's self-reported numbers, and the reason the
semi-private set exists. We report public-set numbers with that limit
explicit.

## Validation of the reconstruction

- Our event accounting + RHAE implementation reproduce all **50/50**
  rows of the released `evaluation_results.csv` manifests exactly.
- **47/50** released world models load and run **unmodified** in our
  sandbox (mean 94.4% green over their own recorded histories; the 3
  non-runners are artifacts of the release itself). See
  `harness/validate_traces.py` and `harness/crosscheck_mispredicts.py`
  for the residue analysis.
- Recovered semantics the Schema article never states are documented in
  `paper/DRAFT.md` §3.

## Run it

The harness is a plain CLI (stdlib Python; the official
[arc-agi](https://github.com/arcprize/arc-agi) engine runs games
locally). Any agent that can run shell commands and edit files can play
— Claude Code, Codex, a human:

```bash
python3 harness/arc3.py --workdir run init --env toolkit --game ls20 --agent me
python3 harness/arc3.py --workdir run observe
# write run/world_model.py, then:
python3 harness/arc3.py --workdir run backtest
python3 harness/arc3.py --workdir run commit --actions '[{"action":1}]' --reason probe
python3 harness/arc3.py --workdir run timeline   # self-contained run inspector
```

Sealed evaluation runs (the protocol behind the table above) are
scaffolded by `harness/make_eval_run.py` and audited by
`harness/audit_eval_run.py`.

## License & attribution

MIT — use it for anything. If this work is useful to you, please credit
it: cite via `CITATION.cff` (GitHub's "cite this repository" button), or
link back here. Schema's own trajectories remain under their release's
terms and are not redistributed here.
