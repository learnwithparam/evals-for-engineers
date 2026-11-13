# Repeat the trials

## The problem

A trial is one run of a case. A model can answer differently each time, so one trial proves little. Each release holds 3 trials of every case. Your gate reads only trial 1.

For example, look at lease L001 in the release `clause-ids-in-answer`. The rent is right in trial 1, wrong in trial 2, and right in trial 3. Live gets it right in all three. One wrong trial in three is noise. A gate that wants every trial right blocks this harmless change.

Anthropic puts numbers on this: "If your agent has a 75% per-trial success rate and you run 3 trials, the probability of passing all three is (0.75)³ ≈ 42%" ([Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), Anthropic).

```mermaid
flowchart LR
  C[one case: L001 rent] --> T1[trial 1: right]
  C --> T2[trial 2: wrong]
  C --> T3[trial 3: right]
  T1 & T2 & T3 --> P[p = 2 / 3]
  P --> A[pass@3 = 0.963]
  P --> H[pass^3 = 0.296]
  P --> S{right in at least 2 of 3?}
  S -- yes --> OK[the case passes]
```

## Your challenge

Change `gate.py` so every case uses all 3 trials. A case is one critical field on one lease, or one unanswerable question.

For each case, report:

- `case`: the lease id or the question id, and `field`: the field name, or `abstains`.
- `trials`: a list of 3 `true` or `false` values, in trial order.
- `pass_at_3`: the chance that at least one of 3 trials is right, `1 - (1 - p) ** 3`. Here `p` is right trials / 3.
- `pass_hat_3`: the chance that all 3 trials are right, `p ** 3`.
- `passed`: `true` when the case is right in at least 2 of its 3 trials.

Block on cases that pass on live and fail on the release. A case with fewer than 3 trials blocks.

```bash
uv run python gate.py --release clause-ids-in-answer
```

Expect: `"verdict": "ship"`, and the L001 rent case lists the trials `true`, `false`, `true` with `"pass_hat_3": 0.2963`.

## Done when

- Every gate lease and critical field has a case with 3 trials, read in trial order.
- `pass_at_3`, `pass_hat_3` and `passed` match the trials.
- `clause-ids-in-answer` ships, and `cheaper-model` is still blocked.
- A case with a lost trial blocks the release.

```bash
bun run verify repeat-the-trials
```

Expect: `Done. All 8 rules pass.` and a `Progress:` line.

## If you get stuck

| What you see                                                    | Fix                                                                                        |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `FAIL the flaky lease L001 does not block clause-ids-in-answer` | Your gate wants all 3 trials right. Decide on the share: 2 of 3 right passes.              |
| `FAIL the trials are read from the release, in trial order`     | Sort the rows by `trial` before you score them, so trial 1 comes first.                    |
| `FAIL pass@3 and pass^3 match the trials of every case`         | Divide right trials by 3 first. Then `1 - (1 - p) ** 3` is pass@3, and `p ** 3` is pass^3. |

The sample answer is in `../solution/gate.py`. Open it after you have tried.

## Words you will use

- **Trial**: one run of one case.
- **pass@3**: the chance that at least one of 3 trials is right.
- **pass^3**: the chance that all 3 trials are right. It falls fast: 75% per trial gives about 42%.
- **Flaky case**: a case that is right in some trials and wrong in others.
