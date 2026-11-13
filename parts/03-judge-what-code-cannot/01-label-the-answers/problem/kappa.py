"""Compare your labels with Dana's and write agreement.json.

Run: uv run python kappa.py
Cohen's kappa measures how much two people agree, beyond the agreement chance alone gives.
Use it only between two people. A judge is measured against Dana with TPR and TNR instead.
"""

import csv
import json

from fernhill import paths


def read_labels(path, label_column: str) -> dict[str, str]:
    with open(path) as labels_file:
        rows = list(csv.DictReader(labels_file))
    return {row["trace_id"]: row[label_column].strip().lower() for row in rows}


def cohens_kappa(mine: list[str], hers: list[str]) -> float:
    """(observed agreement - chance agreement) / (1 - chance agreement)."""
    # TODO: observed = the share of answers where your label and Dana's label are the same.
    # TODO: chance = (your share of pass x Dana's share of pass)
    #              + (your share of fail x Dana's share of fail).
    # TODO: return (observed - chance) / (1 - chance).
    raise NotImplementedError("cohens_kappa() is still the starter")


my_labels = read_labels("labels.csv", "label")
dana = read_labels(paths.LABELS / "grounded.csv", "label")

trace_ids = sorted(my_labels)
mine = [my_labels[trace_id] for trace_id in trace_ids]
hers = [dana[trace_id] for trace_id in trace_ids]
differ = [trace_id for trace_id in trace_ids if my_labels[trace_id] != dana[trace_id]]

kappa = cohens_kappa(mine, hers)
agreement = {
    "n": len(trace_ids),
    "agreed": len(trace_ids) - len(differ),
    "kappa": round(kappa, 3),
    "differ": differ,
}
with open("agreement.json", "w") as agreement_file:
    json.dump(agreement, agreement_file, indent=2)

print(f"You and Dana agree on {agreement['agreed']} of {agreement['n']} answers.")
print(f"Cohen's kappa: {agreement['kappa']}")
for trace_id in differ:
    print(f"  {trace_id}: you said {my_labels[trace_id]}, Dana said {dana[trace_id]}")
print("Wrote agreement.json")
