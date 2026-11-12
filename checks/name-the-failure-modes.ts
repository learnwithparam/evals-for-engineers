import { existsSync } from "node:fs";
import { join } from "node:path";
import type { Rule } from "../scripts/verify";
import { csvHeader, plantedIn, readCsv, readYaml } from "./lib/world";

type Mode = { name: string; definition: string; examples: string[] };
const modes = (d: string): Mode[] => {
  const y = readYaml(join(d, "failure_modes.yaml"));
  return Array.isArray(y?.modes) ? y.modes : [];
};
const marks = (d: string) => new Map(readCsv(join(d, "marks.csv")).map((r) => [r.trace_id, r.mark]));
const notes = (d: string) => new Map(readCsv(join(d, "notes.csv")).map((r) => [r.trace_id, r.note]));
const labels = (d: string) => readCsv(join(d, "labels.csv"));
const GENERIC = /^(hallucinations?|accuracy|inaccurac(y|ies)|inaccurate|errors?|wrong|bad|quality|format(ting)?|other|misc|general|incorrect|issues?|problems?)$/;
const sentences = (s: string) => s.trim().split(/[.!?](\s|$)/).filter((x) => x && x.trim()).length;

export default [
  {
    says: "failure_modes.yaml lists 4 to 8 modes",
    test: (d) => existsSync(join(d, "failure_modes.yaml")) && modes(d).length >= 4 && modes(d).length <= 8,
    tryNext: "group your notes: merge modes that share a cause in the data, split one that hides two behaviours",
  },
  {
    says: "every mode has a name in lower-case-with-dashes, a definition and at least one example",
    test: (d) => modes(d).every((m) => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(m.name ?? "") && !!m.definition && (m.examples ?? []).length > 0),
    tryNext: "copy the block shape from the comment at the top of failure_modes.yaml",
  },
  {
    says: "no mode has a generic name like hallucination, formatting or other",
    test: (d) => modes(d).every((m) => !GENERIC.test(m.name ?? "")),
    tryNext: "name what happened to which field, for example amended-rent-missed",
  },
  {
    says: "every definition is one sentence of 25 words or fewer",
    test: (d) => modes(d).every((m) => sentences(String(m.definition)) === 1 && String(m.definition).split(/\s+/).length <= 25),
    tryNext: "write each definition so a colleague could apply it to a new trace in one read",
  },
  {
    says: "every example is a trace you marked fail and wrote a note on",
    test: (d) => modes(d).every((m) => (m.examples ?? []).every((i) => marks(d).get(i) === "fail" && !!notes(d).get(i))),
    tryNext: "use trace ids from notes.csv as examples",
  },
  {
    says: "labels.csv has a column per mode and a row per reviewed trace, with 0 or 1 in every cell",
    test: (d) => {
      if (!existsSync(join(d, "labels.csv"))) return false;
      const head = csvHeader(join(d, "labels.csv"));
      const names = modes(d).map((m) => m.name);
      const rows = labels(d);
      return head[0] === "trace_id" && names.every((n) => head.includes(n)) && rows.length === marks(d).size
        && rows.every((r) => marks(d).has(r.trace_id) && names.every((n) => r[n] === "0" || r[n] === "1"));
    },
    tryNext: "give every trace in marks.csv one row, and put 0 or 1 under every mode",
  },
  {
    says: "every failed trace has at least one mode, and every passed trace has none",
    test: (d) => labels(d).every((r) => {
      const n = modes(d).filter((m) => r[m.name] === "1").length;
      return marks(d).get(r.trace_id) === "fail" ? n > 0 : n === 0;
    }),
    tryNext: "a failed trace with no mode means a mode is missing; add one or widen a definition",
  },
  {
    says: "the examples of each mode carry a 1 in that mode's column",
    test: (d) => modes(d).every((m) => (m.examples ?? []).every((i) => labels(d).find((r) => r.trace_id === i)?.[m.name] === "1")),
    tryNext: "label the examples you named in failure_modes.yaml with 1 in labels.csv",
  },
  {
    says: "one mode covers every amendment failure in the sample",
    test: (d) => {
      const am = plantedIn([...marks(d).keys()]).filter((p) => p.mode === "amended-rent-missed").map((p) => p.id);
      return modes(d).some((m) => am.every((i) => labels(d).find((r) => r.trace_id === i)?.[m.name] === "1"));
    },
    tryNext: "the traces where rent misses Amendment No. 1 are one behaviour; give them one mode",
  },
] satisfies Rule[];
