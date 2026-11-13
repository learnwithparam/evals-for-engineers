"""The lease abstractor gate as an Inspect AI task: dataset, solver and scorer."""

import json

from fernhill import leases, paths
from fernhill.evals import fields
from fernhill.systems import abstractor
from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import Generate, TaskState, solver


def gate_leases() -> MemoryDataset:
    split = json.loads((paths.DATA / "splits.json").read_text())
    return MemoryDataset([Sample(id=lease_id, input=lease_id) for lease_id in split["gate"]])


@solver
def replay(release: str):
    """Answer from the saved release, one saved trial per epoch, so no key is needed."""
    saved = paths.read_jsonl(paths.RELEASES / f"{release}.jsonl")
    outputs = {
        (row["lease_id"], row["trial"]): row["output"] for row in saved if row["kind"] == "abstract"
    }

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.output.completion = json.dumps(outputs[(state.sample_id, state.epoch)])
        return state

    return solve


@solver
def abstract_lease():
    """Ask the model, with the same prompt the hand-built abstractor uses."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.messages = abstractor.messages(state.sample_id)
        return await generate(state)

    return solve


@scorer(metrics=[{"*": [mean()]}])
def critical_fields():
    """The course grader (fernhill.evals.fields), limited to the critical fields."""
    keys = leases.keys()

    async def score(state: TaskState, target: Target) -> Score:
        abstract = abstractor.parse(state.output.completion)
        fields.score(abstract, keys[state.sample_id])
        return Score(value={field: True for field in leases.CRITICAL})

    return score


@task
def abstract_gate(release: str = "cheaper-model", replayed: bool = True):
    return Task(
        dataset=gate_leases(),
        solver=replay(release) if replayed else abstract_lease(),
        scorer=critical_fields(),
        epochs=Epochs(3, "at_least_2"),
    )
