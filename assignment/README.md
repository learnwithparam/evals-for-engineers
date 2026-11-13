# Assignment: port your gate to Inspect AI

This is optional in the live session. It is expected as homework.

## The task

You built a release gate by hand. Now redo its dataset, call and grader with Inspect AI, an open-source eval runner. Edit `assignment/task.py` so it has one `@task` with a dataset of the 50 gate leases, a solver and a scorer. The scorer must be the course grader, `fernhill.evals.fields`, limited to the critical fields. Write `assignment/CHOICE.md` with the runner-up, promptfoo, and when you would choose it.

For example, run the finished version from `parts/07-score-the-answers-with-inspect-ai/01-port-the-gate/solution`. Without a key, the solver replays the saved answers of the cheaper model.

## Run the check

```bash
uv run checks/assignment.py
```

Expect: three `PASS` lines, and `assignment/result.json` with one `pass` or `fail` per line and the Inspect AI version found. On the untouched starter you see `FAIL` lines.

## Done when

- `inspect-ai` resolves to 0.3.289.
- An eval log in `assignment/logs` has one score per dataset row.
- The failing rows match the hand-built gate.

## Rubric (a person reads it)

- The scorer is the course grader, not a new one.
- `CHOICE.md` names promptfoo and says when to choose it.
- The solver can call a real model when you pass `replayed=False`.

## Submit

Push a branch named `assignment` and send its URL. The grader reruns the same check script.
