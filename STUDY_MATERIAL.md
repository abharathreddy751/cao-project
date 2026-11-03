# Study Material: What Is Going On In This Project

Date: 2026-10-24. Written in plain words. Short sentences. Numbers come from files in this project.

---

## 1. The Project In One Page

**Problem.** A computer has many workers. Some workers are fast. Some are slow. Some are a GPU. A job has many small tasks. Some tasks wait for other tasks.

**Question.** Who should run each task? If we know how long each task takes, can we choose better workers and finish the job sooner?

**Our idea.** Predict the time of each task. Use the prediction to choose the worker.

**Answer so far.**
- On the Montage job: no. A simple rule "use only the fast cores" is as good or better.
- On our new image job (Study 2): yes against fixed rules. We are 27.6% faster than "fast cores only". But a simple greedy rule (give each task to the first free worker) is just as good. So prediction does not add extra gain.

Both answers are honest results. A "no" is also a result.

---

## 2. Words You Need

| Word | Meaning |
|---|---|
| Task | One small piece of work |
| DAG | A set of tasks with arrows. An arrow means "this task must finish first" |
| Worker | A process that runs tasks. We pin each worker to one CPU core |
| P core | Fast CPU core |
| E core | Slow CPU core. There are more of them |
| GPU | Graphics card. Very fast for some tasks. One GPU worker in our setup |
| Pool | A group of workers of one kind: P, E, G (GPU), R (remote) |
| Makespan | Total time from first task start to last task end. Smaller is better |
| Scheduler or policy | The rule that picks a worker for each task |
| Static rule | A fixed rule. It does not look at what is busy now |
| Dynamic rule | A rule that looks at which workers are free now |
| Predictor or estimator | A small model that guesses a task time |
| EFT | Earliest Finish Time. Pick the worker where the task finishes first, using predicted times |
| HEFT, PEFT | Famous static plans made before the run starts |
| B0 to B5 | Our simple rules without prediction. B4 is "first free worker" |
| Early binding | Put a task in a worker's queue now, even if the worker is busy |
| Late binding | Give a task only to a free worker |
| Baseline | The rule we compare against |
| Block | One round where every rule runs once. Order is random |
| Pre-registration | We write the plan and the claims before we run. It stops us from changing the story later |
| Hash (SHA-256) | A fingerprint of a file. Same file gives same fingerprint |
| Montage | A real astronomy program that joins sky photos into one big picture |

---

## 3. What We Changed From The Start

### Part 1: First build (about 2 to 4 October 2026, old laptop with 2 P and 8 E cores)

1. **Phase 0.** Find which cores are fast and slow. We used a Windows function for this. We measured that P cores are faster than E cores.
2. **Phase 1.** Build the core: a coordinator, worker processes pinned to cores, an event log.
3. **Phase 2.** Add simple rules B0 to B5. Add a measured time table (the "static profile").
4. **Phase 3.** Add a ladder of predictors: a constant, a table, a formula, a moving average, a small learned model (ridge), and an oracle for offline checks.
5. **Phase 4.** Add EFT. Measure how often the choice was wrong (regret).
6. **Phase 5.** Add a pretend remote worker. A program on the same laptop, with a delay added to act like a network.
7. **Phase 6.** Build a big dataset from the logs (145,378 task rows). Run a large test matrix.
8. **Demo.** An image job with 68 tasks and a web dashboard.

### Part 2: The audit and the backup (10 October)

We read the code and found seven defects. Two examples:
- A model was used with a different time table than the one it was trained on.
- Only two rules checked which worker may run a task. The documents said all rules did.

We made a backup, a Git baseline, and a list of fingerprints for 12,627 data files.

### Part 3: Redesign (11 to 14 October, new laptop: i5-13500HX, RTX 3050 GPU)

1. **Fixed the defects.** The model now refuses a wrong time table.
2. **Real job.** We built Montage on Windows. It needed many patches. We froze one job: 59 tasks.
3. **New runtime parts.** Tasks can now be outside programs. Every rule checks which worker may run a task. Pools can have any name. A GPU worker was added.
4. **More rules.** HEFT, PEFT, EFT with a rank order, and a control rule B0 early.
5. **More predictors.** CatBoost and a small neural network (MLP).
6. **Strict experiments.** A design file, random order inside each block, paired comparison, confidence intervals, and a fingerprint of every output.
7. **Stage 1.** Three Montage runs gave the same output. We also tested the GPU on image stages.
8. **Stage 2.** 14 rules, 3 blocks, 42 runs. All outputs equal.
9. **Stage 3.** Dataset and predictor tests. The simplest predictor won the selection rule.
10. **Stage 4 (pilot) and Stage 5 (confirmatory).** 143 pilot runs and 408 confirmatory runs. Result: no prediction rule beat the simple rule.
11. **Slow runs explained.** 14 runs were slow. The Windows log shows the laptop was on battery then.

### Part 4: Study 2 (24 October, new files only)

1. Saved a rollback point: tag `baseline-null-result`. New code is on branch `study2/affinity`.
2. Built a new job: 64 independent image chains. The speeds of each stage were measured, not guessed.
3. Found and fixed three problems:
   - The old GPU adapter rebuilt all workers between runs. This made timings jump.
   - The old EFT spent time on logging. It cost 3% of the time.
   - A late-binding EFT was 50% slower. We kept it as a failed idea.
4. Wrote the claims first, then ran 441 runs. All were verified.

---

## 4. Tech Stack And Why

| Tool | Why we use it |
|---|---|
| Python 3.11 | One language for all code. Easy to read |
| NumPy | Fast arrays. Image stages and the ridge model use it |
| Pillow | Image blur in the image job |
| psutil | Pin a worker to a core. Kill stuck programs. Read memory |
| PyYAML | Read the Montage workflow file |
| CatBoost | A tree model. One of the "smart" predictors |
| PyTorch with CUDA | Runs image stages on the GPU. Also trains the small neural network |
| Astropy | Compares astronomy picture files |
| Montage (C programs) | The real science job |
| Windows CPU-set function | The only reliable way to tell P cores from E cores on Windows |
| Multiple processes | Each worker is its own process. Python threads would not give clean timing |
| JSON lines files | The event log. One line per event. Easy to read later |
| SHA-256 fingerprints | Prove that outputs and logs did not change |
| TCP socket and a delay shim | The pretend remote worker |
| Simple web server (Python standard) | The dashboard. No extra install |
| Git | History and rollback. No online copy yet |
| pytest | 403 tests. 402 pass |
| mypy | Type check. No issues in 83 files |

No database is used. All data is files on disk.

---

## 5. Current Workflow

```
Design file (rules, seed, blocks)
   -> Session runner (checks memory, writes machine info)
   -> For each block, for each rule in random order:
        Adapter builds the job and the rule
        Coordinator gives tasks to workers (P, E, GPU, remote)
        Every event goes to the log
        Output is checked against a reference (fingerprint or tolerance)
        A run record is written
   -> Analysis reads only the raw logs
        paired change versus a reference rule
        confidence interval, test, multiple-test fix (Holm)
   -> Tables, figures, report
```

Rules of the workflow:
- Nothing is overwritten. Failed runs are kept and marked.
- The plan is committed before the first run.
- Different machines or different code are never mixed in one analysis.
- The laptop must be on mains power and have free memory.

How to run the main parts:
- Tests: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`
- Study 2 session: `scripts/run_experiment.py` with `--adapter caosched.study2.adapter:factory`
- Analysis: `scripts/analyze_experiment.py --reference <rule>`
- Dashboard: `python -m caosched.dashboard --open`

---

## 6. Current Numbers (Benchmarks)

### Montage job (stage 5, 108 runs, 6 P workers and 7 E workers)

| Rule | Time versus "P cores only" (285 s) |
|---|---|
| EFT with table predictor | 1.6% slower |
| HEFT | 1.5% slower |
| PEFT | 1.7% slower |
| Greedy B4 | 47.9% slower |
| B0 early (same places, early binding) | 1.7% slower |

Task speeds: the main task (`mProject`) takes 112 s on a P core and 401 s on an E core. That is 3.6 times slower.

### Montage with only 2 P workers (48 runs)

| Rule | Versus B4 |
|---|---|
| P cores only | 42.5% slower |
| EFT with table predictor | about equal (-0.13%) |
| EFT with CatBoost | 15.7% slower |

### Predictor accuracy (held-out instance, mean error in seconds)

| Predictor | Error | Time per guess |
|---|---|---|
| Table (E1) | 3.26 | 1 microsecond |
| Ridge | 1.36 | 6 microseconds |
| Neural network | 2.98 | 22 microseconds |
| CatBoost | 2.32 | about 0.5 millisecond |

Better accuracy did not give a better schedule.

### GPU test on Montage-like image job (stage 5)
The job takes about 7 seconds. Most of the time is CPU work. The GPU saves about 2%.

### Pretend remote worker
Greedy B4 with the remote worker was 30.7% slower on a slow link. EFT put 0 tasks on the remote worker.

### Study 2 (new job, 48 blocks, 432 runs)

| Rule | Mean time | Versus our EFT |
|---|---|---|
| P cores only | 2.454 s | 38% slower |
| Fixed map (GPU for edges and features) | 2.804 s | 58% slower |
| HEFT | 1.984 s | 11.6% slower |
| Shortest queue (B3) | 2.009 s | 13% slower |
| Greedy B4 | 1.773 s | about the same |
| EFT (no extra logging) | 1.778 s | reference |
| EFT with old logging | 1.824 s | 2.6% slower |
| EFT without the GPU | 1.864 s | 4.9% slower |

Time spent in the scheduler per run: B4 0.015 s, our EFT 0.056 s.

### Quality checks
- 441 of 441 Study 2 runs were verified.
- 408 of 408 stage 5 runs were verified.
- Tests: 402 pass, 1 fails. The failing test stops itself when free memory is below 2 GB. It passes alone.

---

## 7. Drawbacks To Fix

**Science**
1. Prediction does not beat the greedy rule B4. We need a job where "first free worker" is a bad choice.
2. Montage has one huge task type. It leaves no room for a better rule.
3. All results come from one laptop.
4. The remote worker is pretend. No real network.
5. The GPU gain is small, because CPU stages dominate.
6. Predictors learned from few rows (2,706) and one sky area.

**Engineering**
7. No online copy of the Git repository. The project and its backup sit on one disk.
8. The data folder is large (about 41 GB with the environment). Most of it is scratch folders that can be rebuilt.
9. Many old documents say old things. The new documents are right: `FINAL_REPORT.md`, `RESEARCH_STATUS.md`, `STUDY2_REPORT.md`.
10. Some code still assumes pool names P and E.
11. Montage was built by hand with patches. There is no build script.
12. The machine has little free memory. This breaks one test and can disturb timing.
13. No automatic checks (CI).
14. A stuck program that starts a child of a child may survive a kill.

**Paper work**
15. No project licence file.
16. Some papers could not be read in full (paywall).

---

## 8. Action Plan: How We Overcome The Drawbacks

Status on 2026-10-24: **none of these actions is done yet.** Each action says who does it. "You" means you must act (account, money, decision, physical work). "Me" means I can do it in this project. "Both" means we share it.

### 8.1 Actions by drawback

| # | Drawback | Action to take | Who | Needs your OK? | Result we expect |
|---|---|---|---|---|---|
| 7 | No online copy of Git | Make a private repository on GitHub or GitLab. Push the branches `baseline-null-result`, `study2/affinity` and `redesign/montage`. Push code and small evidence only, never the big data | You: create account and login. Me: commands and push | Yes (push leaves the laptop) | Code is safe if the disk dies |
| 8 | Data folder is big (about 41 GB) | Make a list of scratch `work/` folders (about 31 GB). Copy verified evidence to Google Drive (you have 5 TB). Delete `work/` only after you say yes. Keep the fingerprint files | Me: list and check. You: say yes to delete | Yes (delete is permanent) | Laptop disk free again, evidence kept |
| 13 | No automatic checks | After step 7, add a GitHub Actions file. It runs tests and mypy on a Windows machine on every push. Torch CUDA is not on PyPI, so the check uses the CPU install | Me: write the file. You: enable it on GitHub | No | Every change is tested automatically |
| 12 | Little free memory (about 1 to 2.6 GB during runs) | Before runs: close the WSL VM (about 1.5 GB), browser, video player. Lower worker count if needed. Or add RAM | You: close apps, decide on RAM upgrade. Me: write the check and the notes | Only for RAM purchase | Stable timing, fewer failed runs |
| 9 | Old documents say old things | Make one index file `docs/INDEX.md` with two lists: "current" and "historical". Do not edit the old files | Me | No | One clear entry point for reviewers |
| 14 | Stuck child programs survive a kill | Use a Windows Job Object in a new helper file. Add a test with a child that starts a grandchild, then check nothing is left running. Keep the old code path until the test passes | Me | Yes (new branch, then merge) | Clean stop of every program |
| 1 | Prediction does not beat greedy rule B4 | Build a workload where "first free worker" is wrong: uneven task sizes and few fast workers. Run the speed check first. Write the rules before the run. Win is not guaranteed | Me (design, run, analysis). You: say go for the long run | Yes (new pre-registration) | A clear answer on whether prediction can win |
| 5 | GPU gain is small | Keep the GPU stages and sizes that win (edges 6 to 14 times faster). Use larger tiles if the test shows gain. Accept that CPU stages still dominate | Me | No | Bigger GPU share, if the workload allows |
| 6 | Few rows to train predictors | Use the Study 2 logs as extra training rows. Download more Montage instances only if the result needs them (hours of download) | Me. You: say if download is OK | Yes (download) | More data for predictors |
| 2 | One huge Montage task | No fix. Montage stays as the old baseline. Study 2 is the new test | None | No | Honest statement in the report |
| 3 | Only one machine | Use the Raspberry Pi (section 10), or a second computer such as a friend's PC | You: buy or lend hardware. Me: setup plan | Yes (hardware) | Results from a second machine |
| 4 | Remote worker is pretend | Run the real remote node on the Raspberry Pi over a cable | Both (section 10) | Yes (network use) | Real network results |
| 15 | No licence file | Choose a licence (for example MIT or Apache 2.0). Add a `LICENSE` file. Keep the satellite image data out of any public repo (its terms say ask the holder first) | You: decide. Me: add the file | Yes (decision) | Clear reuse rules |
| 16 | Some papers are behind paywalls | Get the full text from your university library. Put it in the list of sources | You: library access. Me: update the source list | Yes (access) | Full citations |
| 10 | Code still assumes pool names P and E | Refactor on a new branch with tests. Do this after the research results, so the results do not change under us | Me | Yes (branch and merge) | Any pool name works |
| 11 | Montage build is by hand | Write a build script that applies the patches. Check the result against `bin_win64_sha256.txt`. Do not change the Montage results | Me | No | Rebuild possible |

### 8.2 Order of work

1. **Protect the work:** drawbacks 7, 8, 13 (private Git copy, data backup, automatic checks).
2. **Make the laptop stable:** drawbacks 12, 9, 14 (memory, index, stuck processes).
3. **Finish the science:** drawbacks 1, 5, 6 (new workload, GPU stages, training rows).
4. **Get hardware:** drawbacks 3 and 4 (Raspberry Pi, then the real remote runs).
5. **Paper and licence:** drawbacks 15 and 16.
6. **Clean the code:** drawbacks 10 and 11, last, so nothing changes under the results.

### 8.3 Your part, in short

- Create the GitHub or GitLab account and say yes before any push.
- Say yes before any delete.
- Choose the licence.
- Get paper access from the library.
- Decide on RAM and the Raspberry Pi purchase.

### 8.4 My part, in short

- Write the code, tests and index file.
- Run the checks and report the exact output.
- Write the new pre-registrations before each new run.
- Keep every old result and every old file unchanged (new files only).

---

## 9. Before The Raspberry Pi: Do You Need To Learn?

**Short answer.** I can write almost all the code. You must do the physical parts. You need a few basic skills.

### What I can do
- Write and change the code (adapter, node setup, profile steps).
- Write the tests and the experiment plan.
- Write the analysis.
- Give you exact commands to copy and paste.

### What I cannot do
- Touch the Pi. I have no access to it. You run the commands and paste the output back to me.
- Plug cables, install the operating system, check heat.

### What you should learn (small and simple)
1. **Connect to the Pi from your laptop** with SSH. One command.
2. **Basic Linux commands:** `cd`, `ls`, `python3`, `pip`, `nano`.
3. **IP address and network:** a cable is better than Wi-Fi for tests. Know the Pi's IP.
4. **Python virtual environment:** a clean folder of Python packages.
5. **What changes on a Pi:** it is ARM (not Intel). It has 4 slow cores. It has no GPU like ours. It gets hot and slows itself. Its clock is not the same as the laptop clock.

One evening of practice is enough. I can write a short guide for each.

---

## 10. How To Add The Raspberry Pi (Theory)

### What the project already has
- A **remote node** program. It runs tasks that it gets over the network. Command: `python -m caosched.remote.node --host 0.0.0.0 --port 5555`.
- A **proxy** on the laptop. It looks like a normal worker to the coordinator. It sends the work over TCP.
- A **password check** (shared token). It is required when the node listens on the network.
- The idea of a **named pool**, for example `R_PI`.
- Support for a **different clock**. We use durations, not clock times, for the transfer time.
- Today the node only ran on the same laptop with a delay added. It has never run on another machine.

### Steps

1. **Prepare the Pi.** Install a 64-bit OS. Connect it by cable to the same network. Install Python 3.11 or newer, NumPy, Pillow, psutil. Copy the `caosched` code.
2. **Start the node on the Pi** with a long secret token (at least 32 characters). The laptop needs the same token.
3. **Connect from the laptop.** Add a remote slot: host = Pi IP, port = 5555, pool = `R_PI`, no pretend delay (the real network is the delay), different clock = yes.
4. **Measure the Pi.** Run each image stage on the Pi alone. This gives the time table for the pool `R_PI`.
5. **Measure the link.** Send data of many sizes. Fit one line: time = fixed cost + cost per byte. EFT uses this line for the transfer time.
6. **Check outputs.** The Pi may round numbers a little differently. The check must allow tiny differences. We already have a "numeric" check for this.
7. **Write the plan first.** A new pre-registration: rules, blocks, claims. Label the results "real network".
8. **Run and analyse** in the same way as before: random order, paired change, confidence intervals.

### What the Pi can run
Today the remote node can run the image stages and the test kernels. It cannot run Montage programs. Montage tasks need input and output files, so we would have to ship files and build Montage for ARM. This is big work. Start with the image job.

### What to expect
- The link has a real cost. Transfer-aware rules like EFT should now matter more.
- A Pi is much slower than our P cores. EFT may still put few tasks on it.
- Wi-Fi and heat add noise. Use a cable and a fan or a heat sink. Record the Pi temperature.
- Keep the old results as "emulation". Do not mix them with Pi results.

### Order of work
1. Learn SSH and Linux basics (you).
2. Prepare the Pi and run the node by hand (you, with my commands).
3. One test task from the laptop to the Pi (me and you).
4. Measure Pi speed and link (me and you).
5. Write the pre-registration (me).
6. Run the sessions (laptop, unattended).
7. Analyse and report (me).

---

## 11. Where To Read More

| Need | File |
|---|---|
| Newest result | `docs/research_redesign/STUDY2_REPORT.md` |
| Study 2 rules and results | `docs/research_redesign/EVALUATION_PROTOCOL_study2.md` |
| Montage results | `docs/research_redesign/FINAL_REPORT.md` |
| Full audit of the code | `PROJECT_MASTER_DOCUMENTATION.md` |
| Remote device notes | `docs/REMOTE_DEVICES.md` |
| How to reproduce | `docs/research_redesign/REPRODUCE.md` |
| Go back to the old state | `git checkout baseline-null-result` |

---

## 12. Update (24 October): The Oracle Check

We asked: is there room for a better predictor on our new job? We ran the scheduler with perfect task times (an "oracle"). It is a ceiling, not a real rule.

- With perfect times the scheduler is only about 2% faster than the simple greedy rule B4. It is no faster than our real predictor.
- Workers are busy 92 to 95% of the time. There is no spare capacity to win.
- Our earlier guess of "40% room" was wrong. It used solo task times. Tasks run slower when all workers run together.
- First oracle run was flawed: the table lookup was too slow (1.3 s of a 1.7 s run). We fixed it and kept both results.

**What it means.** On this job, prediction cannot beat greedy, even with perfect predictions. We need a job where greedy is wrong: very uneven task sizes, a long critical path, or idle workers. For every new job, run the oracle first. Build real predictors only if the oracle is at least 5% faster than the best simple rule.

This changes the action plan: drawback 1 now has a clear test (the oracle gate) before any new predictor work.

---

## 13. Update (24 October, evening): The Project Works On The Right Job

We built a job where runtime depends on a hidden number (how many times the denoise step repeats). Same image size for all chains, so a size table cannot see it.

Result of the final test (216 runs, new chain orders, all outputs verified, claims written before the run):

| Compared with | Our learned predictor is |
|---|---|
| Greedy rule B4 | 13.8% faster |
| "Fast cores only" | 22.5% faster |
| Table predictor (cannot see the number) | 36.8% faster |
| Hand rule "sort by the number" | about 6% slower |

What it tells us:
- **Prediction helps when it knows something the other rules do not.** This is the original idea of the project. It is now shown on real runs.
- **A wrong prediction is worse than none.** The table predictor was 36% slower than plain greedy.
- **A person who knows the key number can still win.** The learned predictor replaces that knowledge, with a small cost.
- **Ordering the big tasks first adds 8.6%** on top of the predictor.

This changes the drawback list: drawback 1 ("prediction does not beat greedy") is now answered. It beats greedy and static rules when runtime depends on a parameter. It does not beat a hand rule that uses the same parameter.

What is still open: a second machine, the Raspberry Pi, a real network, and a model with more than one feature.

---

## 14. Update (25 October): The Permanent Fix

**The problem we found.** Our predictor was good, but the scheduler used it badly. It queued tasks behind busy workers. A hand rule that just sorts by the hidden number was 6% faster.

**The fix, in simple words.**
1. Use predictions to decide the **order** (longest chain first).
2. Give each task to the **idle** worker that is predicted fastest. Never queue.
3. One **generic model** finds by itself which task numbers matter. No code names them.
4. **Retrain with one command** when the machine changes (for example a Raspberry Pi).
5. **Guards** stop old mistakes from coming back: a decision-time test, a "too much time deciding" check, a charger check, and a claims file that must match the stored numbers.

**Results (fresh tests each time, all outputs verified):**
- 6 fast + 7 slow cores: 20% faster than blind greedy, 22% faster than "fast cores only", 43% faster than the table predictor. About 1.6% behind the hand rule.
- 2 fast + 7 slow cores (model retrained by one command): 21% faster than greedy, 45% faster than "fast cores only", 37% faster than the table predictor. Level with the hand rule.
- Job with nothing hidden: level with greedy. So it does no harm.

**What it means.** The project's idea is now shown and implemented. Prediction beats blind and static scheduling where a table cannot see the cost. It matches a hand rule that is told the key number. It does not beat that rule.

**Raspberry Pi.** The retrain command is ready for it. When the Pi is working, run it once on the Pi and the model learns the Pi's speeds. No retraining by hand.
