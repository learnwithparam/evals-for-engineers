import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { type JsonRecord, readJsonl } from "./lib/world";

type Case = { id: string; history: string; template: string };

const CURRENT_TEMPLATE = "FH-RES-2026";

const cases = (folder: string) => readJsonl<Case>(join(folder, "cases.jsonl"));

function suites(folder: string): JsonRecord {
  const path = join(folder, "suites.json");
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
}

const wanted = (folder: string, keep: (row: Case) => boolean) =>
  cases(folder)
    .filter(keep)
    .map((row) => row.id)
    .sort();

function listIs(folder: string, name: string, keep: (row: Case) => boolean): boolean {
  const written = suites(folder)[name];
  if (!Array.isArray(written)) return false;
  return JSON.stringify([...written].sort()) === JSON.stringify(wanted(folder, keep));
}

export default [
  {
    says: "suites.json has regression, capability and refresh lists",
    test: (folder) =>
      ["regression", "capability", "refresh"].every((name) => name in suites(folder)),
    tryNext: "run uv run python split_suites.py; it writes suites.json for you",
  },
  {
    says: "regression holds only the cases that passed all 5 runs",
    test: (folder) => listIs(folder, "regression", (row) => row.history === "PPPPP"),
    tryNext: "keep a case in regression only when its history is PPPPP, so any failure is a break",
  },
  {
    says: "capability holds the cases that failed at least 3 of 5 runs",
    test: (folder) => listIs(folder, "capability", (row) => row.history.split("F").length - 1 >= 3),
    tryNext: "count the F letters in each history; 3 or more means the system cannot do it yet",
  },
  {
    says: "refresh holds every case not on the current template",
    test: (folder) => listIs(folder, "refresh", (row) => row.template !== CURRENT_TEMPLATE),
    tryNext: `list each case whose template is not ${CURRENT_TEMPLATE}; old cases need new data`,
  },
  {
    says: "no case is in both regression and capability",
    test: (folder) => {
      const regression = suites(folder).regression;
      const capability = suites(folder).capability;
      if (!Array.isArray(regression) || !Array.isArray(capability)) return false;
      return !regression.some((id) => capability.includes(id));
    },
    tryNext: "a case that always passes cannot also be one the system fails; check your tests",
  },
] satisfies Rule[];
