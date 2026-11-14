"""Score your own traces with a judge, using Inspect AI.

It reads my_traces.jsonl, shows each answer to the judge in judge.txt, and scores the verdict.

Run: uv run inspect eval my_task.py --model mockllm/model --log-dir logs
"""

from inspect_ai import Task, task


@task
def my_traces():
    # TODO: load my_traces.jsonl with json_dataset, turn each trace into a Sample,
    # read judge.txt into a system_message, call generate(), and write a scorer
    # that gives CORRECT when the first line of the reply starts with pass.
    return Task()
