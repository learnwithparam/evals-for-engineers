import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { fingerprint } from "./lib/world";

// A missing report reads as empty text, so every rule fails with its own message.
const report = (folder: string) => {
  const path = join(folder, "report.txt");
  return existsSync(path) ? readFileSync(path, "utf8") : "";
};
const LINES = [
  "Abstract fields correct",
  "Lease desk grounded",
  "Retrieval recall@5",
  "Agent outcome pass^3",
  "Gate vs cheaper-model",
];

export default [
  {
    says: "report.txt exists in this folder",
    test: (folder) => report(folder) !== "",
    tryNext:
      "from the repo root run uv run fernhill report " +
      "--out 00-orientation/01-meet-fernhill/problem/report.txt",
  },
  {
    says: "it is the report for the live release",
    test: (folder) => report(folder).startsWith("Fernhill eval report, release: live"),
    tryNext:
      "write the file with uv run fernhill report, not by hand, " +
      "so the first line is the report title",
  },
  {
    says: "it has all five report lines",
    test: (folder) => LINES.every((line) => report(folder).includes(line)),
    tryNext:
      "run the whole report; if a line is missing, " +
      "read the error above it and see troubleshooting.md",
  },
  {
    says: "the gate blocks the cheaper model",
    test: (folder) => /Gate vs cheaper-model \.+ BLOCKED/.test(report(folder)),
    tryNext: "run uv run world reset, then write the report again on the default replay provider",
  },
  {
    says: "its world line matches the world in this repo",
    test: (folder) => report(folder).includes(`fingerprint ${fingerprint()}`),
    tryNext:
      "the report came from another copy of the world; " +
      "run uv run world reset and write the report again",
  },
] satisfies Rule[];
