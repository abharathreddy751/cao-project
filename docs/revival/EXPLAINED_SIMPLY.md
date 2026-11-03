# The project in simple English (for a student or a reviewer)

**The problem.** A computer has fast workers (P cores, a GPU) and slow workers (E cores). A job is a set of small tasks, some waiting for others. The question is who runs which task, and in what order, so the whole job finishes sooner.

**The three kinds of scheduler we compare.**
1. *Static*: always use the fast workers only. Simple, but the slow workers sit unused.
2. *Blind greedy (B4)*: when a worker is free, give it the next waiting task. Nobody is ever left idle. This is surprisingly hard to beat.
3. *Prediction-aware*: guess how long each task will take on each worker, and (a) start the long chains first, (b) give a free worker the task it is best at.

**What we found, in order.**
- Prediction-aware scheduling beats static and naive rules clearly (17% to 45% faster), especially when a task's cost is hidden in a setting (for example how many times a filter is repeated) that a simple table cannot see.
- Against blind greedy it is only better when ordering matters a lot. When the machine is full, there is usually only one free worker at a time, so there is no choice to make, only an order.

**The new idea we tested.** Besides *what the task is*, look at *what the machine is doing right now*: if one core is shared with another program, it is slower; do not give it the big task. We built it (a small, fast "state reader", a cost split into compute, setup and transfer, and a safe fallback to blind greedy) and tested it.

**How we tested fairly.** Before building any predictor we asked: what is the best an all-knowing helper could do on this workload, obeying the same rules? We built that helper (it knows the exact task times and exactly when each core is shared). If even it cannot beat blind greedy by 5%, there is nothing for a predictor to win, and we stop.

**The answer.** The all-knowing helper was *not* faster than blind greedy (1.2% slower, within noise). So on this workload there is nothing to win, and we did not run the big study. We did not change the workload to force a better answer.

**What we also learned the hard way.** The first version of the new scheduler made things 2% slower on a plain workload where it should do no harm. Measuring showed why: it spent about 100 microseconds reading the machine state after *every* finished task, and the coordinator that does this is a single slow core. After making it read the state only when there is a real choice, the harm disappeared (all within +-2%). The bad first run is kept in the record.

**What this means.** The idea "predict, then schedule" is real against static scheduling. The idea "also watch the machine's live state" did not pay off on the workload built for it. The honest next step is a workload where free workers outnumber waiting tasks (that is where a choice exists), plus GPU and remote-network experiments that need hardware or a driver package we have not installed.
