"""Score your own traces with a judge, using Inspect AI.

It reads my_traces.jsonl, shows each answer to the judge in judge.txt, and scores the verdict.

Run: uv run inspect eval my_task.py --model mockllm/model --log-dir logs
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset, Sample
from inspect_ai.scorer import CORRECT, INCORRECT, Score, accuracy, scorer
from inspect_ai.solver import generate, system_message

HERE = Path(__file__).parent


def to_sample(record: dict) -> Sample:
    """One trace becomes one sample: the judge reads the question and the answer."""
    text = f"Question: {record['input']}\n\nAnswer: {record['output']}"
    return Sample(input=text, id=record["id"])


@scorer(metrics=[accuracy()])
def verdict_scorer():
    async def score(state, target):
        first_line = state.output.completion.strip().lower().split("\n")[0]
        passed = first_line.startswith("pass")
        return Score(value=CORRECT if passed else INCORRECT, answer=first_line)

    return score


@task
def my_traces():
    judge_prompt = (HERE / "judge.txt").read_text()
    return Task(
        dataset=json_dataset(str(HERE / "my_traces.jsonl"), sample_fields=to_sample),
        solver=[system_message(judge_prompt), generate()],
        scorer=verdict_scorer(),
    )
