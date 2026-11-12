"""The finished system: `uv run fernhill demo` shows one lease end to end; `uv run fernhill report` prints
the eval report card a learner builds over the course."""
import csv
import hashlib
import json

from .. import db, leases, llm, paths
from ..systems import abstractor, agent, lease_desk, retrieval
from . import agent_grade, fields, gate, judge, stats


def fingerprint() -> str:
    """Changes when the world's data changes. The orientation check recomputes it."""
    h = hashlib.sha256()
    for name in ("keys.jsonl", "planted_faults.jsonl"):
        h.update((paths.DATA / name).read_bytes())
    return h.hexdigest()[:12]


def _split():
    return json.loads((paths.DATA / "splits.json").read_text())


def demo(args: list[str]) -> int:
    meta = {m["id"]: m for m in leases.leases()}
    lid = _split()["demo_lease"]
    if "--lease" in args:
        lid = args[args.index("--lease") + 1]
    if lid not in meta:
        print(f"There is no lease {lid}. Leases run from L001 to L130.")
        return 1
    m, key = meta[lid], leases.keys()[lid]
    print(f"Fernhill demo: lease {lid}, unit {m['unit']} at {m['building']} (provider: {llm.provider()})\n")
    try:
        got = abstractor.run(lid)
    except llm.ReplayMissing as e:
        print(f"  {e}")
        return 2
    print("1. Lease abstractor wrote this abstract to the system of record")
    print(f"   {'field':<22} {'abstract':<16} {'the signed lease':<16}")
    for f, ok in fields.score(got, key).items():
        if f in leases.CRITICAL or not ok:
            show = lambda v: leases.money(v) if f in ("monthly_rent", "deposit") else (str(len(v)) + " step(s)" if f == "rent_steps" else str(v))
            print(f"   {f:<22} {show(got.get(f)):<16} {show(key.get(f)):<16} {'ok' if ok else 'WRONG'}")
    qs = [q for q in paths.read_jsonl(paths.DATA / "questions.jsonl") if q["lease_id"] == lid]
    print("\n2. Lease desk answered a staff question")
    for q in qs[:1]:
        r = lease_desk.run(lid, q["question"])
        print(f"   Q: {q['question']}\n   A: {r['answer']}")
    tasks = [t for t in paths.read_jsonl(paths.DATA / "agent_tasks.jsonl") if t["lease_id"] == lid]
    print("\n3. Rent review agent")
    if not tasks:
        tasks = paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")[:1]
        print(f"   No lease event on {lid} this month, so here is the agent on lease {tasks[0]['lease_id']}.")
        print(f"   Task: {tasks[0]['prompt']}")
    for t in tasks[:1]:
        res = agent.run(t, db.copy(paths.RUNS / f"demo-{t['id']}.db"))
        for s in res["steps"]:
            print(f"   {s['tool']}({', '.join(f'{k}={v}' for k, v in s['args'].items() if k != 'body')})")
        print(f"   done: {res['final']}")
    print("\nNext: uv run fernhill report")
    return 0


def report(args: list[str]) -> int:
    out_path = args[args.index("--out") + 1] if "--out" in args else None
    split = _split()
    keys = leases.keys()
    meta = {m["id"]: m for m in leases.leases()}

    # 1. Field accuracy of the live abstractor on the gate set, critical fields apart.
    rows = [r for r in gate.load("live") if r["kind"] == "abstract" and r["trial"] == 1 and r["lease_id"] in split["gate"]]
    scores = {r["lease_id"]: fields.score(r["output"], keys[r["lease_id"]]) for r in rows}
    acc = sum(sum(s.values()) for s in scores.values()) / sum(len(s) for s in scores.values())
    am = [x for x in scores if meta[x]["amendments"]]
    rent_bad = [x for x in am if not scores[x]["monthly_rent"]]

    # 2. Grounded rate: the judge on unlabelled runs, corrected by its TPR and TNR on held-out labels.
    desk = {d["trace_id"]: d for d in paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")}
    labels = list(csv.DictReader(open(paths.LABELS / "grounded.csv")))
    clauses = {}

    def run_judge(d):
        if d["lease_id"] not in clauses:
            clauses[d["lease_id"]] = {c["id"]: c for c in leases.clauses(d["lease_id"])}
        cited = [{"id": c, "text": clauses[d["lease_id"]][c]["text"]} for c in d["cited"] if c in clauses[d["lease_id"]]]
        return judge.judge(d["question"], d["answer"], cited)["verdict"]

    test = [(r["label"], run_judge(desk[r["trace_id"]])) for r in labels if r["split"] == "test"]
    labelled = {r["trace_id"] for r in labels}
    unl = [run_judge(d) for t, d in desk.items() if t not in labelled]
    tpr, tnr = stats.tpr_tnr(test)
    p_obs = sum(v == "pass" for v in unl) / len(unl)
    corr = stats.corrected(p_obs, tpr, tnr)
    lo, hi = stats.bootstrap(test, unl)

    # 3. Retrieval recall@5 on the answerable questions.
    qs = [q for q in paths.read_jsonl(paths.DATA / "questions.jsonl") if q["answerable"]]
    rec = sum(len(set(q["gold"]) & {c["id"] for c in retrieval.search(q["lease_id"], q["question"], 5)}) / len(q["gold"])
              for q in qs) / len(qs)

    # 4. The agent, graded by the end state of a fresh copy of the system of record.
    graded = agent_grade.run_all()
    p3 = agent_grade.pass_hat_k(graded)
    posted = sum(g["posted"] for g in graded)

    # 5. The gate on the cheaper model.
    g = gate.gate("cheaper-model")
    verdict = "BLOCKED: " + g["reasons"][0] if g["verdict"] == "block" else "SHIP"

    lines = [
        "Fernhill eval report, release: live",
        f"  Abstract fields correct ............ {acc * 100:.1f}%   critical: rent wrong on {len(rent_bad)} of {len(am)} amended leases",
        f"  Lease desk grounded (corrected) .... {corr * 100:.0f}% (95% interval {lo * 100:.0f}% to {hi * 100:.0f}%)   "
        f"judge TPR {tpr:.2f} TNR {tnr:.2f} on {len(test)} held-out labels",
        f"  Retrieval recall@5 ................. {rec:.2f}",
        f"  Agent outcome pass^3 ............... {p3:.2f}   {posted} charge(s) posted without approval",
        f"  Gate vs cheaper-model .............. {verdict}",
        f"World: {db.counts()['units']:,} units, {len(keys) - 10} leases in the eval corpus, fingerprint {fingerprint()}",
    ]
    text = "\n".join(lines)
    print(text)
    paths.log("reports", {"provider": llm.provider(), "lines": lines})
    if out_path:
        with open(out_path, "w") as f:
            f.write(text + "\n")
        print(f"Wrote {out_path}")
    return 0
