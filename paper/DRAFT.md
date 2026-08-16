# Reconstructing Schema: an open replication of the ARC-AGI-3
# world-model harness, with single-run no-fallback results

**DRAFT — work in progress.** Sections marked TODO await the full
25-game sweep.

## Abstract (draft)

Schema reported near-ceiling scores on the ARC-AGI-3 public set (95.35%
GPT-5.6 Sol; 98.98% Claude Opus 4.8 + Fable 5) using an unreleased
harness in which an agent maintains an executable world model, keeps it
consistent with all observed transitions, plans inside it, and treats
any misprediction as grounds to void its plan. The release comprised 50
gameplay trajectories and a scorer; the harness itself, and any
single-run (non best-of-two) figure, were not published. We reconstruct
the harness from the traces themselves, validate the reconstruction
against all 50 trajectories (exact reproduction of every released score;
47/50 released world models execute unmodified in our sandbox), and
report single-run, no-fallback results for the Schema method on the
public set, produced by sealed agents whose transcripts are audited for
information leakage and published — a contamination-control protocol not
previously reported on this benchmark (concurrently, Tycho
[arXiv:2607.28287] reports open-source public-set saturation with a
different method; see §6). On the games evaluated so far, a single sealed
run with a current frontier model matches or exceeds Schema's best-of-two
figures at 2.5–3.5× less wall-clock. All code, event logs, and world
models are released under MIT.

## 1. Background and motivation

[TODO: ARC-AGI-3 description — RHAE, no-instructions games; Schema's
published claims and disclosed protocol; the three published criticisms:
best-of-two fallback with selection on score, public-set-only, and
self-reporting; the absent harness; no replication attempts to date.]

## 2. Reconstructing the harness from its traces

The 50 released trajectories are richer than the accompanying article:
each contains a streamed `events.jsonl` (10 event kinds, every tool
call), sanitized agent-session transcripts, model snapshots, and working
notes. From these we recovered:

- **The loop**: observe → deliberate (edit a world-model program;
  backtest it against every recorded transition; search for plans inside
  it) → execute (each real transition checked against the model's
  prediction; ONE mismatch voids the remaining plan) → append-only record.
- **The world-model contract** (verbatim across both model families):
  `init_state(entry_grid)` and
  `predict(state, grid, action, x, y) -> (next_grid, info, next_state)`
  with `level_up/dead/win` flags — plus a second, stateless form
  `step(grid, action, x, y) -> (grid, info)` used by three runs.
- **The sandbox's complete injection surface**, by static analysis of
  all 50 model files (no other undefined names occur): `np`,
  `CURRENT_LEVEL`, `ENTRY_GRID`. Negative space too: `next()` is absent
  from the sandbox builtins (one trace records replacing it after a
  NameError).
- **State lifecycle**: model state is re-initialised at every level
  entry. This is nowhere in the article; we recovered it by measurement
  (threading state across levels backtests at 8–92% green on the traces'
  own histories; re-initialising scores ~99%).
- **The harness-agnosticism of the original**: the released sessions are
  Claude Code transcripts on the Claude side and `codex exec` sessions
  on the GPT side — Schema drove commodity coding agents with four
  bespoke tools and a turn prompt. Our reformulation of the tool surface
  as a CLI (playable by any agent, or a human) is therefore fidelity,
  not liberty.

## 3. Validating the reconstruction

Three independent checks:

1. **Scoring**: our event accounting and RHAE implementation reproduce
   all 50 rows of the released evaluation manifests exactly (per-level
   action counts; RHAE to 2 d.p.).
2. **Contract**: 47/50 released world models load and execute
   unmodified in our sandbox, averaging 94.4% green over their own
   recorded histories (GPT family 93–99%). The three non-runners are
   release artifacts (two files broken by a redaction line; one
   trajectory shipped no model file).
3. **Residue attribution**: of 21,378 transitions checked across the 47
   runnable models, 1,014 are red in our replay; 557 (54.9%) coincide
   exactly with steps where the original harness itself recorded a
   `model_mispredicted` event. The unexplained residue is 457
   transitions (**2.14%**) — a loose upper bound on genuine contract
   mismatch, as it still contains final-model-vs-early-history cases
   (transitions that passed under earlier model versions, so no
   contemporaneous mispredict was recorded, but that the final released
   file no longer reproduces). Contract fidelity is therefore bounded
   below by 97.9%, with the true figure likely higher.

The sensitivity of check (2) is itself evidence: each recovered semantic
moved the number in large steps (no `np` → 0%; no `ENTRY_GRID` → all
calls error; no per-level re-init → 8–92%; full contract → ~99% on the
same traces).

## 4. The sealed single-run protocol

Where Schema's headline figure permits a second model's run to replace a
first-run score below 80, we report **one run per game, first attempt,
no fallback**, under seals that control what the agent can read:

- A fresh directory per game containing only the CLI and a procedure
  document; permission deny-rules and a command guard block the
  downloaded game source, this project's own repository, and all web
  access. The game runs on the official `arc-agi` engine.
- Every run's transcript is swept mechanically for sealed-path reads and
  web use; the audit verdict ships with the event log.
- Pre-declared rerun policy: infrastructure failures (e.g. a permission
  misconfiguration that prevents any action being taken) are rerun and
  logged; agent stalls, deaths, and losses stand as-is. [One such infra
  rerun has occurred to date: ft09, 0 actions taken, settings
  misconfiguration, logged in results/ft09/rerun.log.]

**What sealing cannot do**: the public games and Schema's traces have
been on the open internet for months; nothing rules them out of the
evaluated models' training data. This limit applies equally to Schema's
own numbers, and to every public-set ARC figure; the semi-private set
exists for exactly this reason, and we would welcome an
ARC-Prize-verified run.

## 5. Results

Sealed, single-run, Claude Opus, text-only observation (as in the
original — no vision):

| game | outcome | actions (human) | RHAE | wall-clock | Schema best-of-2 |
|---|---|---|---|---|---|
| sb26 | WIN 8/8 | 128 (213) | **100.00%** | 0.23 h | 98.63% / 127 act |
| ls20 | WIN 7/7 | 497 (776) | **100.00%** | 1.75 h | 100% / 533 act |
| ... | TODO: remaining 23 games | | | | |

Observations from the completed runs:

- **Time is deliberation.** 93% of ls20's wall-clock is agent thinking;
  all 322 harness calls together account for 7%. The hardest level (a
  fog-of-war finale requiring the agent to build map memory and render
  from remembered state) consumed 43% of the run.
- **The verification discipline, not the search, is load-bearing.** The
  sb26 agent never invoked the planner; ls20 used it once. Plans were
  formed in-context and kept honest by backtest-greenness and
  mispredict-voiding. (Schema's agents averaged ~9 planner calls/game.)
- **Mispredictions cluster at level boundaries** when the model is good:
  all 9 of sb26's mispredicts, and 98 of ls20's 237, were level-entry
  frames, which are unknowable in advance. [TODO: exact ls20 boundary
  count; distribution figure.]

## 6. Related work

**Executable World Models for ARC-AGI-3** (Rodionov, SingularityNET;
arXiv:2605.05138, May 6 2026) predates Schema by two months and states
the same core loop: an executable Python world model, a verifier
requiring the model to reproduce all recorded observations, plan
execution with per-step prediction checking that halts on divergence,
and an explicit refactoring pressure toward shared abstractions. With
GPT-5.4/Codex it reports a mean 32.58% RHAE over the 25 public games —
under an honest protocol this work follows: single recorded runs, no
best-of-N, interruptions reported as-is. The method family's trajectory
is itself informative: from 32.6% (May, GPT-5.4) to ~99% (July, Schema,
Opus 4.8 + Fable 5, best-of-two) to 100% (late July, Tycho, Opus 5,
single-run) — the public set moved from "method demonstrated" to
saturated within one frontier-model generation, which sharpens both the
harness-vs-model attribution question and the need for the semi-private
set.

**Tycho** (arXiv:2607.28287, July 30 2026; open source) formalizes
ARC-AGI-3 games as rendered deterministic Moore machines and reports —
in one matched public-set run per orchestration policy — Opus 4.8 at
88.49 mean RHAE, and GPT-5.6 Sol and Opus 5 at **100.00 RHAE across all
183 levels**. Tycho therefore holds the first published open-source
saturation of the public set, predating this work's sweep. Our
contribution is orthogonal: Tycho is its own method; we reconstruct and
validate *Schema's specific unreleased system* from its traces, and add
the sealed/audited protocol that neither Schema nor Tycho report
(Tycho's abstract makes no contamination-control claims). Our per-game
numbers double as the first Schema-method single-run figures.

[TODO also: Duck Harness (Tufa Labs, Milestone 1 winner, open source);
Prime Agent (Prime Intellect, MIT — no published ARC-AGI-3 score;
third-party claims of 95.5% appear unsourced); Arcgentica; Executable
World Models for ARC-AGI-3 (arXiv:2605.05138); Graph-Based Exploration
(arXiv:2512.24156). Schema's harness remains unreleased: an open request
on their trace repository (HF discussion #1, ~3 weeks old) has no author
response, and their site states no release plans.]

## 7. Reproducing

[TODO: exact commands; hardware/model versions; costs. All event logs
and world models in results/; timelines regenerable via
`arc3.py timeline`.]

## Acknowledgements

Schema's authors, for releasing trajectories detailed enough to
reconstruct their system — a form of openness this work depends on and
tries to extend. The ARC Prize Foundation for ARC-AGI-3 and the arc-agi
engine.
