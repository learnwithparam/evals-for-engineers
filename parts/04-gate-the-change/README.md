# Gate the change

## The problem

A gate is a check that decides if a release may ship. Someone wants to move the abstractor to a cheaper model. Its average field accuracy drops by only 1.3 points, so a gate on the average lets it through. But it gets the rent wrong on 9 more amended leases. Those are the leases owners complain about.

For example, here are two gates on the same release. The average gate prints `Average gate on cheaper-model: PASS (field accuracy drops 1.3 points; the limit is 2.0)`. The gate you build prints `Gate on cheaper-model: BLOCKED`, with the reason `rent newly wrong on 9 amended leases (critical)`. One of those leases is L040. There, the cheaper model misses Amendment No. 1 in every trial.

## Why it matters

A trial is one run of a case. Anthropic's engineering team shows why one passing trial proves little: "If your agent has a 75% per-trial success rate and you run 3 trials, the probability of passing all three is (0.75)³ ≈ 42%". The source is [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), from Anthropic.

So a good gate follows four rules:

- It runs each case more than once.
- It decides on a share of trials that you set in advance.
- It never lets an average hide a critical failure.
- It blocks when a result is missing. This is called failing closed.

```mermaid
flowchart LR
  R[release candidate] --> T[3 trials per case]
  T --> F[field checks from Check with code]
  T --> J[judge from Judge what code cannot]
  F & J --> G{any critical case newly wrong, or a result missing?}
  G -- yes --> B[exit 1: blocked, with reasons]
  G -- no --> S[exit 0: ship]
```

## Steps

| Step                 | Minutes | You produce                                                      | The check reads                                                                      |
| -------------------- | ------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `gate-the-release`   | 25      | a `gate` command: exit 0 to ship, 1 to block, with a JSON report | exit codes on the four releases in `world/data/releases`, and on an injected timeout |
| `repeat-the-trials`  | 15      | pass@3 and pass^3 per case in the gate report                    | the numbers recomputed; the flaky case does not block `clause-ids-in-answer`         |
| `run-the-gate-in-ci` | 15      | `evals.yml`: a CI workflow that runs the gate on pull requests   | the workflow file linted: trigger, gate command, judge role, timeout                 |

## Walkthrough

TODO(part session): one command per step, each followed by its Expect: line.

## What you can show

You can show two lines side by side. The average gate passes `cheaper-model`. Your gate blocks it, with the reason "rent newly wrong on 9 amended leases".
