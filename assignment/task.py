"""Port your release gate to Inspect AI: a dataset, a solver and a scorer.

Fill in the three functions, then run:
  uv run inspect eval assignment/task.py --model mockllm/model --log-dir assignment/logs
"""

from inspect_ai import Task, task


@task
def abstract_gate():
    return Task()
