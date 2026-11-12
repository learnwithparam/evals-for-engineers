"""Count each failure mode in labels.csv and write rates.json.

Run: uv run python count.py
"""

import csv
import json

rows = list(csv.DictReader(open("labels.csv")))
modes = [c for c in rows[0] if c != "trace_id"] if rows else []

# TODO: for each mode, count the rows with "1" and divide by the number of rows.
# TODO: choose a decision per mode: "fix the prompt", "code check", "judge" or "monitor".
decisions = {m: "TODO" for m in modes}

out = {"n": len(rows), "top_mode": "", "modes": {}}
json.dump(out, open("rates.json", "w"), indent=2)
print("Wrote rates.json")
