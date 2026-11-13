"""Count each failure mode in labels.csv and write rates.json.

Run: uv run python count.py
"""

import csv
import json

# Each row of labels.csv is one reviewed trace, with a 0 or 1 for every failure mode.
with open("labels.csv") as labels_file:
    labeled_traces = list(csv.DictReader(labels_file))
reviewed = len(labeled_traces)

# Every column except trace_id is one failure mode. An empty file has no modes yet.
modes = []
if labeled_traces:
    modes = [column for column in labeled_traces[0] if column != "trace_id"]

# TODO: for each mode, count the rows with "1" and divide by the number of rows.
# TODO: choose a decision per mode: "fix the prompt", "code check", "judge" or "monitor".
decisions = {mode: "TODO" for mode in modes}

results = {"n": reviewed, "top_mode": "", "modes": {}}
with open("rates.json", "w") as rates_file:
    json.dump(results, rates_file, indent=2)
print("Wrote rates.json")
