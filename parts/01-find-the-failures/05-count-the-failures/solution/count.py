"""Count each failure mode in labels.csv and write rates.json.

Run: uv run python count.py
"""

import csv
import json


def choose_decision(mode: str) -> str:
    # Rent and notice days have one right answer in the lease, so code can check them.
    # The other modes come from how the model reads the lease, so fix the prompt first.
    if "rent" in mode or "notice" in mode:
        return "code check"
    return "fix the prompt"


# Each row of labels.csv is one reviewed trace, with a 0 or 1 for every failure mode.
with open("labels.csv") as labels_file:
    labeled_traces = list(csv.DictReader(labels_file))
reviewed = len(labeled_traces)

# Every column except trace_id is one failure mode.
modes = [column for column in labeled_traces[0] if column != "trace_id"]

# A "1" in a mode's column means that trace shows the mode.
counts = {}
for mode in modes:
    counts[mode] = sum(trace[mode] == "1" for trace in labeled_traces)

# The rate divides by every reviewed trace, not only the failed ones.
mode_results = {}
for mode in modes:
    mode_results[mode] = {
        "count": counts[mode],
        "rate": round(counts[mode] / reviewed, 4),
        "decision": choose_decision(mode),
    }

# When two modes tie, max() keeps the one whose column comes first.
top_mode = max(counts, key=counts.get)

results = {"n": reviewed, "top_mode": top_mode, "modes": mode_results}
with open("rates.json", "w") as rates_file:
    json.dump(results, rates_file, indent=2)
print(f"Wrote rates.json: top mode {top_mode} at {counts[top_mode]} of {reviewed} traces")
