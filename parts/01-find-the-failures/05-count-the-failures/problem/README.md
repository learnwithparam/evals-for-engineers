# Count the failures

## The problem

Dana asked one question: how often does this happen, and what kind of mistake is it? Your labels hold the answer. But nobody can read a 40 by 6 grid in a meeting. Each mode also needs a decision. Some mistakes have one right answer, such as a rent amount. Code should catch those on every release, not a person reading.

```mermaid
flowchart LR
  L[labels.csv] --> C[count each mode]
  C --> R[rate = count / traces reviewed]
  R --> D{one right answer?}
  D -- yes --> K[code check]
  D -- no --> J[fix the prompt, judge or monitor]
```

## Your challenge

First, from the repo root: `cd parts/01-find-the-failures/05-count-the-failures/problem`.

From `labels.csv`, compute three things: the count of each failure mode, its rate, and the mode that happens most. Give each mode one decision: `fix the prompt`, `code check`, `judge` or `monitor`. A code check is a test in code that compares the output with the right answer. A judge is a model that grades the output. Write it all to `rates.json`. The starter `count.py` already reads the labels for you.

```bash
uv run python count.py
```

Expect: `Wrote rates.json` and, once you finish it, the top mode with its count.

For example, the column `amended-rent-missed` in `labels.csv` has a `1` in 4 of the 40 rows. So its count is 4 and its rate is 4 / 40 = 0.1. A rent amount has one right answer in the lease, so its decision is `code check`. In `rates.json` that mode looks like this:

```json
"amended-rent-missed": {
  "count": 4,
  "rate": 0.1,
  "decision": "code check"
}
```

When the sample answer runs, it prints `Wrote rates.json: top mode amended-rent-missed at 4 of 40 traces`.

## Done when

- `rates.json` has `n`, `top_mode` and an entry per mode with `count`, `rate` and `decision`.
- Every count and rate matches `labels.csv`.
- `top_mode` is the mode with the highest count.
- Every mode has one of the four decisions, and the rent modes are `code check`.

```bash
bun run verify count-the-failures
```

Expect: `Done. All 6 rules pass.` and a `Progress:` line.

## If you get stuck

| What you see                                                          | Fix                                                                                                                     |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `FAIL every mode has a count and a rate that match labels.csv`        | Compute the numbers with code, not by eye. The rate divides by all 40 reviewed traces, not by the failures.             |
| `FAIL rent failures, which have one right answer, go to a code check` | A rent value in the lease is either matched or not. Comparing two numbers in code is cheaper and steadier than a judge. |

## Words you will use

- **Failure rate**: the share of reviewed traces that show a failure mode.
- **Code check**: a test in code that compares an output with a known right answer.
- **Judge**: a model that grades an output on one criterion when no code check can decide it.
