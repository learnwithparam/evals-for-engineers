// Reads the Fernhill world: its data, Dana's labels, the planted faults, the system of record and its logs.
// A check reads these and the learner's files. It never reads a model's reply to judge it.

import { Database } from "bun:sqlite";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const ROOT = join(import.meta.dir, "..", "..");
export const DATA = join(ROOT, "world", "data");
export const LOGS = join(ROOT, "world", "logs");
export const DB = join(ROOT, "world", "fernhill.db");

export const readJsonl = <T = any>(p: string): T[] =>
  readFileSync(p, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l));

/** A small CSV reader: a header row, commas, and double quotes around fields that hold commas. */
export function readCsv(p: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [],
    cell = "",
    quoted = false;
  const text = readFileSync(p, "utf8").replace(/^﻿/, "");
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((x) => x.trim() !== "")) rows.push(row);
      row = [];
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim() !== "")) rows.push(row);
  if (rows.length === 0) return [];
  const head = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => Object.fromEntries(head.map((h, i) => [h, (r[i] ?? "").trim()])));
}

export const csvHeader = (p: string): string[] =>
  (readFileSync(p, "utf8").replace(/^﻿/, "").split(/\r?\n/)[0] ?? "")
    .split(",")
    .map((h) => h.trim());

export const readYaml = (p: string): any => Bun.YAML.parse(readFileSync(p, "utf8"));
export const readJson = (p: string): any => JSON.parse(readFileSync(p, "utf8"));

let _traces: Map<string, any> | undefined;
/** The 300 recorded abstractor runs, by trace id. */
export function abstractorTraces(): Map<string, any> {
  _traces ??= new Map(
    readJsonl(join(DATA, "traces", "abstractor.jsonl")).map((t) => [t.trace_id, t]),
  );
  return _traces;
}

/** Dana Mensah's label for every abstractor trace: her verdict and the failure modes she saw. */
export function danaAbstractor(): Map<string, { verdict: string; modes: string[] }> {
  const out = new Map();
  for (const r of readCsv(join(DATA, "labels", "abstractor.csv"))) {
    const modes = Object.keys(r).filter((k) => k !== "trace_id" && k !== "verdict" && r[k] === "1");
    out.set(r.trace_id, { verdict: r.verdict, modes });
  }
  return out;
}

/** The three planted abstractor faults, as the mode Dana gives each. */
export const PLANTED_MODES: Record<string, { fault: number; words: RegExp; what: string }> = {
  "amended-rent-missed": {
    fault: 1,
    words: /rent|amend/i,
    what: "the rent misses Amendment No. 1",
  },
  "rent-step-dropped": {
    fault: 2,
    words: /step|increase|rise|raise|anniversar|escalat/i,
    what: "a rent step in prose is dropped",
  },
  "notice-days-wrong-clause": {
    fault: 3,
    words: /notice|renew|days/i,
    what: "renewal notice days come from another clause",
  },
};

/** Trace ids in a list that carry a planted fault, with the mode for each. */
export function plantedIn(ids: string[]): { id: string; mode: string }[] {
  const dana = danaAbstractor();
  const out: { id: string; mode: string }[] = [];
  for (const id of ids)
    for (const m of dana.get(id)?.modes ?? []) if (m in PLANTED_MODES) out.push({ id, mode: m });
  return out;
}

export const plantedFaults = () => readJsonl(join(DATA, "planted_faults.jsonl"));
export const splits = () => readJson(join(DATA, "splits.json"));

/** Same as fingerprint() in world/fernhill/evals/report.py: changes when the world's data changes. */
export function fingerprint(): string {
  const h = new Bun.CryptoHasher("sha256");
  for (const f of ["keys.jsonl", "planted_faults.jsonl"]) h.update(readFileSync(join(DATA, f)));
  return h.digest("hex").slice(0, 12);
}

/** Read-only access to the system of record, or undefined when `uv run world reset` has not run. */
export function db(): Database | undefined {
  return existsSync(DB) ? new Database(DB, { readonly: true }) : undefined;
}

/** Lines from world/logs/<name>.jsonl, written by the finished system and the learner's runs. */
export const log = (name: string): any[] =>
  existsSync(join(LOGS, `${name}.jsonl`)) ? readJsonl(join(LOGS, `${name}.jsonl`)) : [];
