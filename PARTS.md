# Parts

Every part of the course, its steps, minutes, and what each step's check reads. A part session starts here.
The orientation and Find the failures are built. The rest are skeletons: a README with the problem, a
cited reason, a diagram and the step table, and no step folders yet.

| Part folder                                  | Steps (minutes)                                                                                                                      | Total | State    |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----- | -------- |
| `00-orientation`                             | `meet-fernhill` (15)                                                                                                                 | 15    | built    |
| `parts/01-find-the-failures`                 | `sample-the-traces` (10), `mark-the-traces` (15), `note-the-failures` (20), `name-the-failure-modes` (20), `count-the-failures` (10) | 75    | built    |
| `parts/02-check-with-code`                   | `build-the-golden-set` (15), `write-field-checks` (20), `check-the-ledger` (15)                                                      | 50    | skeleton |
| `parts/03-judge-what-code-cannot`            | `label-the-answers` (25), `write-the-judge` (20), `align-the-judge` (25), `test-the-judge` (10), `correct-the-pass-rate` (10)        | 90    | skeleton |
| `parts/04-gate-the-change`                   | `gate-the-release` (25), `repeat-the-trials` (15), `run-the-gate-in-ci` (15)                                                         | 55    | skeleton |
| `parts/05-watch-production`                  | `sample-production-traces` (15), `report-the-batch-rate` (15), `feed-failures-back` (10)                                             | 40    | skeleton |
| `parts/06-evaluate-retrieval-and-agent`      | `measure-retrieval-recall` (20), `judge-the-abstentions` (20), `grade-the-agent-outcome` (20), `map-agent-failures` (20)             | 80    | skeleton |
| `parts/07-score-the-answers-with-inspect-ai` | `port-the-gate` (30)                                                                                                                 | 30    | built    |

Total: 405 minutes. `schedules.toml` maps these onto one-day, four-evenings and six-weeks.

## What each step's check reads

| Step                       | The check reads                                                            | Passes on                                                                                                                     |
| -------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `meet-fernhill`            | `report.txt` from `uv run fernhill report`                                 | the live report, all five lines, gate BLOCKED, world fingerprint matches                                                      |
| `sample-the-traces`        | three runs of the learner's `sample.py` (seeds 7, 7, 8)                    | 40 real ids, at least 8 amended and 3 commercial, same seed same sample                                                       |
| `mark-the-traces`          | `marks.csv`, planted faults 1 to 3, Dana's labels                          | every trace marked, planted faults marked fail, 32 of 40 agree with Dana                                                      |
| `note-the-failures`        | `notes.csv`, `marks.csv`, planted faults                                   | a note of 5 or more words per fail, no fix words, planted notes name the field                                                |
| `name-the-failure-modes`   | `failure_modes.yaml`, `labels.csv`, notes and marks                        | 4 to 8 specific modes, one-sentence definitions, consistent labels, one amendment mode                                        |
| `count-the-failures`       | `rates.json`, recomputed from `labels.csv`                                 | counts and rates match, top mode right, rent modes go to a code check                                                         |
| `build-the-golden-set`     | `golden.jsonl` against `world/data/keys.jsonl` and `splits.json`           | 40 leases, 10 or more amended, 3 or more commercial, no gate lease, `critical_fields` holds rent and renewal notice days      |
| `write-field-checks`       | the learner's checks run over a hidden table of known pairs, three runs    | zero wrong verdicts on money and dates; prose rent steps expanded; live accuracy within 0.5 points of `fernhill.evals.fields` |
| `check-the-ledger`         | the learner's ledger check output                                          | finds every fault 4 and 6 lease in `planted_faults.jsonl`, no alarm on clean leases                                           |
| `label-the-answers`        | the learner's 30 labels                                                    | 30 labels with critiques; kappa with Dana is reported, any value passes                                                       |
| `write-the-judge`          | the `judge` command on the train split, three runs in replay               | contract met, pass or fail only, no dev or test text in the prompt                                                            |
| `align-the-judge`          | the learner's judge outputs on dev                                         | TPR and TNR at least 0.80, computed by the check, change log names a disagreement                                             |
| `test-the-judge`           | one judge run on test, keyed by prompt hash                                | TPR and TNR at least 0.80; a second run on the same hash is refused                                                           |
| `correct-the-pass-rate`    | `grounded_rate.json`                                                       | corrected rate within 0.01 of the formula, interval holds the estimate                                                        |
| `gate-the-release`         | the `gate` command's exit code and report on each release                  | 1 on `cheaper-model` (reason names rent), 1 on `shorter-prompt`, 0 on `clause-ids-in-answer`, 1 on an injected timeout        |
| `repeat-the-trials`        | the gate report's per-case trials                                          | pass@3 and pass^3 recomputed; `flaky_gate_lease` in `splits.json` does not block                                              |
| `run-the-gate-in-ci`       | the learner's `evals.yml`                                                  | runs on pull requests, calls the gate, names the judge role not a model id, has a timeout                                     |
| `sample-production-traces` | the `monitor` command on the production traces, three runs in replay       | at least 30 per batch, across buildings, the aligned judge                                                                    |
| `report-the-batch-rate`    | `batches.csv`                                                              | corrected rates right per batch; alert on batch 5 only                                                                        |
| `feed-failures-back`       | new cases in the golden set                                                | 3 or more tagged `source: production`, valid, and the gate fails `live` on them                                               |
| `measure-retrieval-recall` | the `retrieve` command on `questions.jsonl`                                | metrics recomputed; one setting reaches recall@5 of 0.85                                                                      |
| `judge-the-abstentions`    | the abstention judge on its own labelled split                             | TPR and TNR at least 0.80; every fault 5 answer caught                                                                        |
| `grade-the-agent-outcome`  | the learner's grader on fresh database copies, 20 tasks by 3 replay trials | grades match `fernhill.evals.agent_grade`; the posted charge is caught                                                        |
| `map-agent-failures`       | `transitions.csv` from `world/data/traces/agent.jsonl`                     | counts sum to the failed traces; the top cell matches                                                                         |

## What the world gives a part session

- `uv run world generate` rebuilds all of `world/data` and `world/replay` from `world/fernhill/generate.py`. The output is committed; run it only when you change the generator, then `uv run python -m fernhill.fixtures` from `world/` to rebuild the Find the failures files.
- Planted faults, numbered as in the research brief, are in `world/data/planted_faults.jsonl`: 1 amended rent missed, 2 prose rent step dropped, 3 "not less than N days" (abstractor and lease desk), 4 pet fee charged where pets are banned, 5 lease desk answers an unanswerable question, 6 rent step never charged in the ledger and a charge posted by the agent without approval, 7 the `cheaper-model` release.
- Labels: `labels/abstractor.csv` (Dana, per trace and mode), `labels/grounded.csv` (120 labels, 60 pass and 60 fail, split train 20, dev 50, test 50), `labels/lease_desk_truth.jsonl` and `labels/production_truth.jsonl` (the truth for every run, including abstention).
- `splits.json`: `golden` (40 leases), `gate` (50 leases), `review`, the demo lease and the flaky gate lease.
- The finished system in `world/fernhill/evals/` is the reference answer for Parts 2 to 6: `fields.py`, `stats.py`, `judge.py`, `gate.py`, `agent_grade.py`. Checks may call it to compute expected numbers.
- `checks/lib/world.ts` reads all of this; `checks/lib/run.ts` runs learner work with `LLM_PROVIDER=replay` and has `threeRuns()`.

## Notes for part sessions

- **Replay and the learner's own judge.** Replay answers only prompts the finished system sends. A learner's own judge prompt needs a live key, or the step ships recorded replies for its sample answer. Checks run sample answers in replay; decide in the Judge what code cannot session how a learner without a key passes `write-the-judge` and `align-the-judge` (for example, a judge contract that reads verdicts from a file the learner's command wrote during a live run).
- **CI file location.** `run-the-gate-in-ci` must keep the learner's workflow as `evals.yml` in the step's `problem/` folder. Nothing in this repo is written under `.github/`.
- **Case study numbers.** Only Anthropic's engineering post and the Langfuse guide could be read from this build's network, so the skeletons cite those. The brief's other cases (Thomson Reuters, Shopify, Harvey, Uber, GOV.UK, Khan Academy, DoorDash, Zillow) are marked "(search)" and may reach a learner file only after a session reads the company's own page and cites it.
- **Time words.** Use "batch", never a day or week number, in Watch production.
