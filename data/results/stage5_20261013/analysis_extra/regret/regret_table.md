# One-step hindsight placement regret (evidence: real; derived from event logs)

Regret = (finish of the chosen worker) - (finish of the best worker), both with the E5 replay-oracle kernel time and the actual worker backlog at binding time (analysis/decisions.py). Myopic, kernel-only; workers whose pool has no oracle observation are left out of the minimum. B0/B4 log no candidate costs but regret needs none.

## main

| policy | runs | decisions | mean regret s | total regret s | total per run s | share positive | mProject mean s | mProject share positive | costs logged |
|---|---|---|---|---|---|---|---|---|---|
| B0_P_only | 4 | 236 | 0.000 | 0.0 | 0.0 | 0.017 | 0.000 | 0.000 | 0.00 |
| B4_greedy_eligible | 4 | 236 | 6.850 | 1616.5 | 404.1 | 0.153 | 44.751 | 0.333 | 0.00 |
| EFT_CatBoost | 4 | 236 | 0.117 | 27.6 | 6.9 | 0.208 | 0.645 | 0.306 | 1.00 |
| EFT_E1 | 4 | 236 | 0.312 | 73.7 | 18.4 | 0.326 | 0.651 | 0.306 | 1.00 |
| EFT_E1_rank | 4 | 236 | 0.346 | 81.6 | 20.4 | 0.318 | 0.667 | 0.250 | 1.00 |
| EFT_E1_rc | 4 | 236 | 0.336 | 79.4 | 19.8 | 0.322 | 0.698 | 0.278 | 1.00 |
| EFT_E3 | 4 | 236 | 0.219 | 51.7 | 12.9 | 0.275 | 0.693 | 0.278 | 1.00 |
| EFT_E4 | 4 | 236 | 0.193 | 45.6 | 11.4 | 0.237 | 0.753 | 0.278 | 1.00 |
| EFT_MLP | 4 | 236 | 0.251 | 59.2 | 14.8 | 0.386 | 0.771 | 0.306 | 1.00 |
| HEFT_E1 | 4 | 236 | 0.362 | 85.5 | 21.4 | 0.386 | 0.690 | 0.306 | 0.00 |
| PEFT_E1 | 4 | 236 | 0.331 | 78.2 | 19.6 | 0.369 | 0.626 | 0.250 | 0.00 |

## regime_R

| policy | runs | decisions | mean regret s | total regret s | total per run s | share positive | mProject mean s | mProject share positive | costs logged |
|---|---|---|---|---|---|---|---|---|---|
| B0_P_only | 3 | 177 | 0.000 | 0.0 | 0.0 | 0.034 | 0.000 | 0.000 | 0.00 |
| B4_greedy_eligible | 3 | 177 | 17.136 | 3033.1 | 1011.0 | 0.452 | 111.493 | 0.778 | 0.00 |
| EFT_CatBoost | 3 | 177 | 2.538 | 449.2 | 149.7 | 0.249 | 13.920 | 0.444 | 1.00 |
| EFT_E1 | 3 | 177 | 0.134 | 23.8 | 7.9 | 0.237 | 0.346 | 0.185 | 1.00 |
| HEFT_E1 | 3 | 177 | 8.767 | 1551.8 | 517.3 | 0.548 | 55.876 | 0.556 | 0.00 |

## regime_R: mProject decisions where EFT_CatBoost and EFT_E1 chose different pools (6 pairs)

| block | task | CatBoost pool | E1 pool | CatBoost pred exec s | CatBoost actual s | E1 actual s | CatBoost regret s | E1 regret s | best pool (CatBoost view) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | ID0000007 | P | E | 94.4 | 114.5 | 399.3 | 61.3 | 0.0 | E |
| 0 | ID0000008 | P | E | 94.4 | 113.0 | 395.4 | 58.3 | 0.0 | E |
| 1 | ID0000007 | P | E | 94.4 | 115.3 | 399.2 | 60.7 | 0.0 | E |
| 1 | ID0000008 | P | E | 94.4 | 113.1 | 395.5 | 57.5 | 0.0 | E |
| 2 | ID0000007 | P | E | 94.4 | 115.7 | 399.2 | 61.7 | 0.0 | E |
| 2 | ID0000008 | P | E | 94.4 | 113.5 | 395.4 | 57.9 | 0.0 | E |
