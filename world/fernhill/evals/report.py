"""The finished system, end to end.

`uv run fernhill demo` shows one lease going through all three systems.
`uv run fernhill report` prints the eval report card a learner builds over the course.
"""

import csv
import hashlib
import json

from .. import db, leases, llm, paths
from ..systems import abstractor, agent, lease_desk, retrieval
from . import agent_grade, fields, gate, judge, stats


def fingerprint() -> str:
    """Changes when the world's data changes. The orientation check recomputes it."""
    digest = hashlib.sha256()
    for name in ("keys.jsonl", "planted_faults.jsonl"):
        digest.update((paths.DATA / name).read_bytes())
    return digest.hexdigest()[:12]


def _split():
    return json.loads((paths.DATA / "splits.json").read_text())


def _show(field: str, value) -> str:
    """One abstract value as the demo table prints it: money in dollars, rent steps as a count."""
    if field in ("monthly_rent", "deposit"):
        return leases.money(value)
    if field == "rent_steps":
        return str(len(value)) + " step(s)"
    return str(value)


def _demo_abstractor(lease_id: str, key: dict) -> bool:
    """Step 1 of the demo. Returns False when replay has no recorded reply."""
    try:
        abstract = abstractor.run(lease_id)
    except llm.ReplayMissingError as error:
        print(f"  {error}")
        return False
    print("1. Lease abstractor wrote this abstract to the system of record")
    print(f"   {'field':<22} {'abstract':<16} {'the signed lease':<16}")
    for field, ok in fields.score(abstract, key).items():
        if field in leases.CRITICAL or not ok:
            written = _show(field, abstract.get(field))
            signed = _show(field, key.get(field))
            verdict = "ok" if ok else "WRONG"
            print(f"   {field:<22} {written:<16} {signed:<16} {verdict}")
    return True


def _demo_lease_desk(lease_id: str) -> None:
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    lease_questions = [question for question in questions if question["lease_id"] == lease_id]
    print("\n2. Lease desk answered a staff question")
    for question in lease_questions[:1]:
        result = lease_desk.run(lease_id, question["question"])
        print(f"   Q: {question['question']}\n   A: {result['answer']}")


def _demo_agent(lease_id: str) -> None:
    all_tasks = paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")
    tasks = [task for task in all_tasks if task["lease_id"] == lease_id]
    print("\n3. Rent review agent")
    if not tasks:
        tasks = paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")[:1]
        print(
            f"   No lease event on {lease_id} this month, "
            f"so here is the agent on lease {tasks[0]['lease_id']}."
        )
        print(f"   Task: {tasks[0]['prompt']}")
    for task in tasks[:1]:
        run = agent.run(task, db.copy(paths.RUNS / f"demo-{task['id']}.db"))
        for step in run["steps"]:
            # The notice body is long, so the demo leaves it out.
            shown = [f"{name}={value}" for name, value in step["args"].items() if name != "body"]
            print(f"   {step['tool']}({', '.join(shown)})")
        print(f"   done: {run['final']}")


def demo(args: list[str]) -> int:
    lease_by_id = {lease["id"]: lease for lease in leases.leases()}
    lease_id = _split()["demo_lease"]
    if "--lease" in args:
        lease_id = args[args.index("--lease") + 1]
    if lease_id not in lease_by_id:
        print(f"There is no lease {lease_id}. Leases run from L001 to L130.")
        return 1
    lease, key = lease_by_id[lease_id], leases.keys()[lease_id]
    print(
        f"Fernhill demo: lease {lease_id}, unit {lease['unit']} at {lease['building']} "
        f"(provider: {llm.provider()})\n"
    )
    if not _demo_abstractor(lease_id, key):
        return 2
    _demo_lease_desk(lease_id)
    _demo_agent(lease_id)
    print("\nNext: uv run fernhill report")
    return 0


def _field_accuracy(split: dict) -> dict:
    """Field accuracy of the live abstractor on the gate set, with rent on amended leases apart."""
    keys = leases.keys()
    lease_by_id = {lease["id"]: lease for lease in leases.leases()}
    rows = [
        row
        for row in gate.load("live")
        if row["kind"] == "abstract" and row["trial"] == 1 and row["lease_id"] in split["gate"]
    ]
    scores = {row["lease_id"]: fields.score(row["output"], keys[row["lease_id"]]) for row in rows}
    fields_right = sum(sum(score.values()) for score in scores.values())
    fields_checked = sum(len(score) for score in scores.values())
    amended = [lease_id for lease_id in scores if lease_by_id[lease_id]["amendments"]]
    rent_wrong = [lease_id for lease_id in amended if not scores[lease_id]["monthly_rent"]]
    return {
        "accuracy": fields_right / fields_checked,
        "amended": len(amended),
        "rent_wrong": len(rent_wrong),
    }


class _Judging:
    """Runs the grounded judge on lease desk traces, reading each lease's clauses once."""

    def __init__(self):
        self.clauses_by_lease = {}

    def verdict(self, trace: dict) -> str:
        lease_id = trace["lease_id"]
        if lease_id not in self.clauses_by_lease:
            lease_clauses = leases.clauses(lease_id)
            self.clauses_by_lease[lease_id] = {clause["id"]: clause for clause in lease_clauses}
        clauses = self.clauses_by_lease[lease_id]
        cited = [
            {"id": clause_id, "text": clauses[clause_id]["text"]}
            for clause_id in trace["cited"]
            if clause_id in clauses
        ]
        return judge.judge(trace["question"], trace["answer"], cited)["verdict"]


def _grounded_rate() -> dict:
    """The judge on unlabelled runs, corrected by its TPR and TNR on held-out labels."""
    traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    desk = {trace["trace_id"]: trace for trace in traces}
    with open(paths.LABELS / "grounded.csv") as labels_file:
        labels = list(csv.DictReader(labels_file))
    judging = _Judging()
    test = [
        (label["label"], judging.verdict(desk[label["trace_id"]]))
        for label in labels
        if label["split"] == "test"
    ]
    labelled = {label["trace_id"] for label in labels}
    unlabelled = [
        judging.verdict(trace) for trace_id, trace in desk.items() if trace_id not in labelled
    ]
    tpr, tnr = stats.tpr_tnr(test)
    observed = sum(verdict == "pass" for verdict in unlabelled) / len(unlabelled)
    low, high = stats.bootstrap(test, unlabelled)
    return {
        "corrected": stats.corrected(observed, tpr, tnr),
        "low": low,
        "high": high,
        "tpr": tpr,
        "tnr": tnr,
        "test_labels": len(test),
    }


def _retrieval_recall() -> float:
    """Recall@5 on the answerable questions: the share of each gold clause set found, averaged."""
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    answerable = [question for question in questions if question["answerable"]]
    total = 0
    for question in answerable:
        found = retrieval.search(question["lease_id"], question["question"], 5)
        found_ids = {clause["id"] for clause in found}
        gold = set(question["gold"])
        total += len(gold & found_ids) / len(question["gold"])
    return total / len(answerable)


def _report_lines(split: dict) -> list[str]:
    fields_part = _field_accuracy(split)
    grounded = _grounded_rate()
    recall = _retrieval_recall()
    # The agent, graded by the end state of a fresh copy of the system of record.
    graded = agent_grade.run_all()
    pass_hat_three = agent_grade.pass_hat_k(graded)
    posted = sum(result["posted"] for result in graded)
    gate_result = gate.gate("cheaper-model")
    if gate_result["verdict"] == "block":
        verdict = "BLOCKED: " + gate_result["reasons"][0]
    else:
        verdict = "SHIP"
    units = db.counts()["units"]
    eval_corpus = len(leases.keys()) - 10
    return [
        "Fernhill eval report, release: live",
        f"  Abstract fields correct ............ {fields_part['accuracy'] * 100:.1f}%   "
        f"critical: rent wrong on {fields_part['rent_wrong']} of {fields_part['amended']} "
        "amended leases",
        f"  Lease desk grounded (corrected) .... {grounded['corrected'] * 100:.0f}% "
        f"(95% interval {grounded['low'] * 100:.0f}% to {grounded['high'] * 100:.0f}%)   "
        f"judge TPR {grounded['tpr']:.2f} TNR {grounded['tnr']:.2f} "
        f"on {grounded['test_labels']} held-out labels",
        f"  Retrieval recall@5 ................. {recall:.2f}",
        f"  Agent outcome pass^3 ............... {pass_hat_three:.2f}   "
        f"{posted} charge(s) posted without approval",
        f"  Gate vs cheaper-model .............. {verdict}",
        f"World: {units:,} units, {eval_corpus} leases in the eval corpus, "
        f"fingerprint {fingerprint()}",
    ]


def report(args: list[str]) -> int:
    out_path = args[args.index("--out") + 1] if "--out" in args else None
    lines = _report_lines(_split())
    text = "\n".join(lines)
    print(text)
    paths.log("reports", {"provider": llm.provider(), "lines": lines})
    if out_path:
        with open(out_path, "w") as out_file:
            out_file.write(text + "\n")
        print(f"Wrote {out_path}")
    return 0
