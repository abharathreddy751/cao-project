# Amendment F1: end-to-end timing convention (final study, written 2026-11-01, before any final run)

## Problem found in the audit

`RunSummary.makespan_seconds` is "first dispatch to last completion" (`core/coordinator.py`, `_summary`). Everything a policy does in `scheduler.on_run_start` happens before the first task is dispatched and is outside that number:

* HEFT and PEFT compute their whole plan there (`StaticPlanScheduler.on_run_start`);
* `RankEftScheduler.on_run_start` computes the upward rank PRED uses (`PredictedRankGreedy`, `PredictedRankGreedyE2E`);
* B4 and B4_param_first do almost nothing there.

`scheduling_time_seconds` counts only `order_ready` and `select_worker`. So the one-off planning cost of a static scheduler, and the rank cost of PRED, were in neither total. A comparison of a static plan against a dynamic policy by `makespan_seconds` favours whichever policy front-loads its work.

## New convention (additive; nothing old is changed)

`Coordinator.run` now records, for every scheduler, with one boundary:

| field (`RunSummary`, `run_finished` event, adapter `extra`) | meaning |
|---|---|
| `init_seconds` (`init_s`) | start of `run()` to just before `on_run_start`: eligibility resolution and the `run_started` / `worker_ready` log entries. The same for every policy. |
| `policy_setup_seconds` (`policy_setup_s`) | duration of `scheduler.on_run_start`: static plan, upward rank, cost validation. |
| `scheduling_time_seconds` (`decision_time_total_s`) | unchanged: `order_ready` plus `select_worker`, summed over the run. |
| `makespan_seconds` | unchanged: first dispatch to last completion. |
| `end_to_end_makespan_seconds` (`makespan_e2e_s` in the analysis) | start of `run()` to last completion. Contains `init_seconds`, `policy_setup_seconds` and execution. |
| `total_wall_time_seconds` | unchanged: sum of timed kernels. |

The boundary is the same clock (`util.clock.now`) and the same place for every scheduler. Building the DAG, the sequential reference run and the output verification are outside it for every scheduler.

## What does not change

* Old logs have none of the new fields. The analysis refuses to guess: with `--primary-metric makespan_e2e_s` a run without the field is excluded with the reason "no makespan_e2e_s ... logged before amendment F1".
* `analyze` default is still `makespan_s`; `primary_metric` is an explicit option and is written to `analysis.json` when it is not the default.
* No earlier result is re-labelled. Statements about earlier sessions keep their original convention.
* The final study reports both numbers for every comparison: the primary `makespan_e2e_s` and the old `makespan_s`, plus `init_s`, `policy_setup_s` and the scheduling time as separate columns.

## Tests

`tests/test_final_timing.py`: a scheduler with a 0.30 s `on_run_start` shows `policy_setup_seconds` of at least 0.30 s, an old-convention makespan below 0.25 s and an end-to-end makespan above both; `init + setup + execution` accounts for the end-to-end time within the gap before the first dispatch; the fields are in the `run_finished` event; HEFT's plan time is recorded; older logs map to `None`; an excluded run names the missing metric. `tests/test_final_region.py` checks that a fixed set-up cost shrinks a relative gain when the new metric is used.
