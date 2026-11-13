# Sample the traces

## The problem

A trace is the record of one run of a system: what went in, what came out, and each step between. The abstractor has 300 traces. Each one wrote a lease abstract into the system of record. Dana knows of two wrong rent letters. Nobody knows how many abstracts are wrong, or in what way.

Reading all 300 traces is too slow. Reading the first 40 is worse. They come from only 18 leases, and they hold no commercial lease at all. Shop leases and amended leases are where mistakes cost most, so you need them in the set you read.

```mermaid
flowchart LR
  T[300 abstractor traces] --> A[amended leases: at least 8]
  T --> C[commercial leases: at least 3]
  T --> R[the rest at random]
  A & C & R --> S[sample.jsonl: 40 traces]
```

## Your challenge

Work in this step's `problem/` folder. From the repo root, go there first with `cd parts/01-find-the-failures/01-sample-the-traces/problem`.

Finish `sample()` in `sample.py` so it picks 40 traces for review. Pick the risky kinds first: at least 8 traces of amended leases and at least 3 of commercial leases. Then fill the rest at random. The same seed must always give the same 40, so a colleague can review the same set.

Each line of `world/data/traces/abstractor.jsonl` is one trace. You need three fields: `trace_id`, `lease_type` (`residential` or `commercial`) and `amendments` (a count).

For example, the first line of the file starts like this:

```
{"amendments": 0, "building": "Eyot House", "lease_id": "L001", "lease_type": "residential", ...
```

This trace is for a residential lease with no amendments, so it is not one of the risky kinds. Near its end, the same line holds `"trace_id": "abs-0001"`.

```bash
uv run python sample.py --seed 7
```

Expect: `Wrote 40 traces to` followed by the path of `sample.jsonl`.

With seed 7, the sample answer picks 14 traces of amended leases and 7 of commercial leases.

## Done when

- `sample.py --seed 7` writes 40 real trace ids, with no repeats.
- At least 8 come from amended leases and at least 3 from commercial leases.
- The same seed gives the same sample, and a different seed gives a different one.

```bash
bun run verify sample-the-traces
```

Expect: `Done. All 7 rules pass.` and a `Progress:` line.

## If you get stuck

| What you see                                        | Fix                                                                                                              |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `FAIL sample.py --seed 7 runs and writes 40 traces` | Run the script yourself and read the error. `NotImplementedError` means `sample()` is still the starter.         |
| `FAIL at least 3 traces of commercial leases`       | Only 10 of the 120 leases are shops. A plain random draw often misses them, so pick them as their own group.     |
| `FAIL the same seed gives the same sample`          | Make one `random.Random(seed)` and use it for every pick. `random.sample()` on its own uses a new seed each run. |

The sample answer is in `../solution/sample.py`. Open it after you have tried.

## Words you will use

- **Trace**: the record of one run of a system: what went in, what came out, and each step between.
- **Stratified sample**: a sample that takes a set number from each group first, so small groups are not missed.
- **Seed**: a number that fixes what a random generator produces, so you can repeat a run exactly.
