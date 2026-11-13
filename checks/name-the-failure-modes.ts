import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, plantedIn, readCsv, readYaml } from "./lib/world";

type Mode = { name: string; definition: string; examples: string[] };

const modes = (folder: string): Mode[] => {
  const failureModes = readYaml<{ modes?: unknown } | undefined>(
    join(folder, "failure_modes.yaml"),
  );
  return Array.isArray(failureModes?.modes) ? failureModes.modes : [];
};
const marks = (folder: string) => {
  const rows = readCsv(join(folder, "marks.csv"));
  return new Map(rows.map((row) => [row.trace_id, row.mark]));
};
const notes = (folder: string) => {
  const rows = readCsv(join(folder, "notes.csv"));
  return new Map(rows.map((row) => [row.trace_id, row.note]));
};
const labels = (folder: string) => readCsv(join(folder, "labels.csv"));
const labelOf = (folder: string, traceId: string, mode: string) =>
  labels(folder).find((row) => row.trace_id === traceId)?.[mode];

// Names that say something went wrong but not what. A mode name says which field and how.
const GENERIC_NAMES = [
  "hallucinations?",
  "accuracy",
  "inaccurac(y|ies)",
  "inaccurate",
  "errors?",
  "wrong",
  "bad",
  "quality",
  "format(ting)?",
  "other",
  "misc",
  "general",
  "incorrect",
  "issues?",
  "problems?",
];
const GENERIC = new RegExp(`^(${GENERIC_NAMES.join("|")})$`);

const sentences = (text: string) => {
  const pieces = text.trim().split(/[.!?](\s|$)/);
  return pieces.filter((piece) => piece?.trim()).length;
};

const isOneShortSentence = (definition: unknown) => {
  const text = String(definition);
  return sentences(text) === 1 && text.split(/\s+/).length <= 25;
};

const hasWellFormedName = (mode: Mode) =>
  /^[a-z0-9]+(-[a-z0-9]+)*$/.test(mode.name ?? "") &&
  !!mode.definition &&
  (mode.examples ?? []).length > 0;

function labelsMatchModes(folder: string): boolean {
  if (!existsSync(join(folder, "labels.csv"))) return false;
  const header = csvHeader(join(folder, "labels.csv"));
  const names = modes(folder).map((mode) => mode.name);
  const rows = labels(folder);
  const isBinary = (cell: string) => cell === "0" || cell === "1";
  return (
    header[0] === "trace_id" &&
    names.every((name) => header.includes(name)) &&
    rows.length === marks(folder).size &&
    rows.every(
      (row) => marks(folder).has(row.trace_id) && names.every((name) => isBinary(row[name])),
    )
  );
}

function modesMatchMark(folder: string, row: Record<string, string>): boolean {
  const modeCount = modes(folder).filter((mode) => row[mode.name] === "1").length;
  return marks(folder).get(row.trace_id) === "fail" ? modeCount > 0 : modeCount === 0;
}

function oneModeCoversAmendments(folder: string): boolean {
  const planted = plantedIn([...marks(folder).keys()]);
  const amended = planted.filter((trace) => trace.mode === "amended-rent-missed");
  const amendedIds = amended.map((trace) => trace.id);
  return modes(folder).some((mode) =>
    amendedIds.every((id) => labelOf(folder, id, mode.name) === "1"),
  );
}

export default [
  {
    says: "failure_modes.yaml lists 4 to 8 modes",
    test: (folder) =>
      existsSync(join(folder, "failure_modes.yaml")) &&
      modes(folder).length >= 4 &&
      modes(folder).length <= 8,
    tryNext:
      "group your notes: merge modes that share a cause in the data, " +
      "split one that hides two behaviours",
  },
  {
    says: "every mode has a name in lower-case-with-dashes, a definition and at least one example",
    test: (folder) => modes(folder).every(hasWellFormedName),
    tryNext: "copy the block shape from the comment at the top of failure_modes.yaml",
  },
  {
    says: "no mode has a generic name like hallucination, formatting or other",
    test: (folder) => modes(folder).every((mode) => !GENERIC.test(mode.name ?? "")),
    tryNext: "name what happened to which field, for example amended-rent-missed",
  },
  {
    says: "every definition is one sentence of 25 words or fewer",
    test: (folder) => modes(folder).every((mode) => isOneShortSentence(mode.definition)),
    tryNext: "write each definition so a colleague could apply it to a new trace in one read",
  },
  {
    says: "every example is a trace you marked fail and wrote a note on",
    test: (folder) =>
      modes(folder).every((mode) =>
        (mode.examples ?? []).every(
          (id) => marks(folder).get(id) === "fail" && !!notes(folder).get(id),
        ),
      ),
    tryNext: "use trace ids from notes.csv as examples",
  },
  {
    says:
      "labels.csv has a column per mode and a row per reviewed trace, " +
      "with 0 or 1 in every cell",
    test: labelsMatchModes,
    tryNext: "give every trace in marks.csv one row, and put 0 or 1 under every mode",
  },
  {
    says: "every failed trace has at least one mode, and every passed trace has none",
    test: (folder) => labels(folder).every((row) => modesMatchMark(folder, row)),
    tryNext: "a failed trace with no mode means a mode is missing; add one or widen a definition",
  },
  {
    says: "the examples of each mode carry a 1 in that mode's column",
    test: (folder) =>
      modes(folder).every((mode) =>
        (mode.examples ?? []).every((id) => labelOf(folder, id, mode.name) === "1"),
      ),
    tryNext: "label the examples you named in failure_modes.yaml with 1 in labels.csv",
  },
  {
    says: "one mode covers every amendment failure in the sample",
    test: oneModeCoversAmendments,
    tryNext: "the traces where rent misses Amendment No. 1 are one behaviour; give them one mode",
  },
] satisfies Rule[];
