"""Count each failure mode in labels.csv and write rates.json.

Run: uv run python count.py
"""
import csv
import json

rows = list(csv.DictReader(open("labels.csv")))
modes = [c for c in rows[0] if c != "trace_id"]
counts = {m: sum(r[m] == "1" for r in rows) for m in modes}

# Rent values have one right answer in the lease, so code checks them. The others are prompt fixes first.
decisions = {m: "code check" if "rent" in m or "notice" in m else "fix the prompt" for m in modes}

out = {
    "n": len(rows),
    "top_mode": max(counts, key=counts.get),
    "modes": {m: {"count": counts[m], "rate": round(counts[m] / len(rows), 4), "decision": decisions[m]} for m in modes},
}
json.dump(out, open("rates.json", "w"), indent=2)
print(f"Wrote rates.json: top mode {out['top_mode']} at {counts[out['top_mode']]} of {len(rows)} traces")
