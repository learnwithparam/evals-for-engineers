// Reads the Fernhill world: its data, Dana's labels, the planted faults,
// the system of record and its logs.
// A check reads these and the learner's files. It never reads a model's reply to judge it.

import { Database } from "bun:sqlite";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

export const ROOT = join(import.meta.dir, "..", "..");
export const DATA = join(ROOT, "world", "data");
export const LOGS = join(ROOT, "world", "logs");
export const DB = join(ROOT, "world", "fernhill.db");

/** One parsed line of JSON. Its keys come from the Python side, so they are snake_case. */
export type JsonRecord = { [field: string]: unknown };

/** A recorded abstractor run. Fields like trace_id and lease_type are read by name. */
export type Trace = { amendments: number; [field: string]: unknown };

export type PlantedFault = { fault: number; system: string; ref: string; [field: string]: unknown };

export type Splits = { golden: string[]; gate: string[] };

// Some editors save a byte order mark at the start of a CSV; it is not part of the first header.
const BYTE_ORDER_MARK = /^﻿/;

export const readJsonl = <Shape = JsonRecord>(path: string): Shape[] => {
  const lines = readFileSync(path, "utf8").split("\n");
  const filled = lines.filter((line) => line.trim());
  return filled.map((line) => JSON.parse(line));
};

type CsvReader = { rows: string[][]; row: string[]; cell: string; quoted: boolean };

function endCell(reader: CsvReader) {
  reader.row.push(reader.cell);
  reader.cell = "";
}

// A row of only blank cells is a blank line, so it is dropped.
function endRow(reader: CsvReader) {
  endCell(reader);
  if (reader.row.some((cell) => cell.trim() !== "")) reader.rows.push(reader.row);
  reader.row = [];
}

/** Reads one character inside double quotes. Returns how many characters it used. */
function readQuoted(reader: CsvReader, text: string, i: number): number {
  const character = text[i];
  if (character === '"' && text[i + 1] === '"') {
    reader.cell += '"';
    return 2;
  }
  if (character === '"') reader.quoted = false;
  else reader.cell += character;
  return 1;
}

/** Reads one character outside quotes. Returns how many characters it used. */
function readPlain(reader: CsvReader, text: string, i: number): number {
  const character = text[i];
  if (character === '"') reader.quoted = true;
  else if (character === ",") endCell(reader);
  else if (character === "\n" || character === "\r") {
    endRow(reader);
    // Windows ends a line with \r\n; treat the pair as one line break.
    if (character === "\r" && text[i + 1] === "\n") return 2;
  } else reader.cell += character;
  return 1;
}

function csvRows(text: string): string[][] {
  const reader: CsvReader = { rows: [], row: [], cell: "", quoted: false };
  let i = 0;
  while (i < text.length) {
    if (reader.quoted) i += readQuoted(reader, text, i);
    else i += readPlain(reader, text, i);
  }
  endRow(reader);
  return reader.rows;
}

/** A small CSV reader: a header row, commas, and double quotes around fields that hold commas. */
export function readCsv(path: string): Record<string, string>[] {
  const text = readFileSync(path, "utf8").replace(BYTE_ORDER_MARK, "");
  const rows = csvRows(text);
  if (rows.length === 0) return [];
  const header = rows[0].map((name) => name.trim());
  return rows.slice(1).map((row) => {
    const cells = header.map((name, i) => [name, (row[i] ?? "").trim()]);
    return Object.fromEntries(cells);
  });
}

export const csvHeader = (path: string): string[] => {
  const text = readFileSync(path, "utf8").replace(BYTE_ORDER_MARK, "");
  const firstLine = text.split(/\r?\n/)[0] ?? "";
  return firstLine.split(",").map((name) => name.trim());
};

/** Parses a YAML file. The caller names the shape it expects, since the learner wrote the file. */
export const readYaml = <Shape = JsonRecord>(path: string): Shape =>
  Bun.YAML.parse(readFileSync(path, "utf8")) as Shape;

/** Parses a JSON file. The caller names the shape it expects. */
export const readJson = <Shape = JsonRecord>(path: string): Shape =>
  JSON.parse(readFileSync(path, "utf8"));

// Read once per process: every rule of every check looks traces up here.
let cachedTraces: Map<string, Trace> | undefined;

/** The 300 recorded abstractor runs, by trace id. */
export function abstractorTraces(): Map<string, Trace> {
  if (cachedTraces === undefined) {
    const traces = readJsonl<Trace>(join(DATA, "traces", "abstractor.jsonl"));
    cachedTraces = new Map(traces.map((trace) => [trace.trace_id as string, trace]));
  }
  return cachedTraces;
}

export type DanaLabel = { verdict: string; modes: string[] };

/** Dana Mensah's label for every abstractor trace: her verdict and the failure modes she saw. */
export function danaAbstractor(): Map<string, DanaLabel> {
  const labels = new Map<string, DanaLabel>();
  for (const row of readCsv(join(DATA, "labels", "abstractor.csv"))) {
    const columns = Object.keys(row);
    const modes = columns.filter(
      (column) => column !== "trace_id" && column !== "verdict" && row[column] === "1",
    );
    labels.set(row.trace_id, { verdict: row.verdict, modes });
  }
  return labels;
}

export type PlantedMode = { fault: number; words: RegExp; what: string };

/** The three planted abstractor faults, as the mode Dana gives each. */
export const PLANTED_MODES: Record<string, PlantedMode> = {
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

export type PlantedTrace = { id: string; mode: string };

/** Trace ids in a list that carry a planted fault, with the mode for each. */
export function plantedIn(ids: string[]): PlantedTrace[] {
  const dana = danaAbstractor();
  const found: PlantedTrace[] = [];
  for (const id of ids) {
    const modes = dana.get(id)?.modes ?? [];
    for (const mode of modes) if (mode in PLANTED_MODES) found.push({ id, mode });
  }
  return found;
}

export const plantedFaults = () => readJsonl<PlantedFault>(join(DATA, "planted_faults.jsonl"));
export const splits = () => readJson<Splits>(join(DATA, "splits.json"));

/**
 * Same as fingerprint() in world/fernhill/evals/report.py. It changes when the world's data does,
 * so a report made from another copy of the world is caught.
 */
export function fingerprint(): string {
  const hasher = new Bun.CryptoHasher("sha256");
  for (const file of ["keys.jsonl", "planted_faults.jsonl"]) {
    hasher.update(readFileSync(join(DATA, file)));
  }
  return hasher.digest("hex").slice(0, 12);
}

/** Read-only access to the system of record, or undefined when `uv run world reset` has not run. */
export function db(): Database | undefined {
  return existsSync(DB) ? new Database(DB, { readonly: true }) : undefined;
}

/** Lines from world/logs/<name>.jsonl, written by the finished system and the learner's runs. */
export const log = (name: string): JsonRecord[] => {
  const path = join(LOGS, `${name}.jsonl`);
  return existsSync(path) ? readJsonl(path) : [];
};
