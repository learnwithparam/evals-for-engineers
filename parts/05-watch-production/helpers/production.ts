// Shared by the checks of Watch production. The supervisor may move it to checks/lib/.
import { join } from "node:path";
import { python, run } from "../../../checks/lib/run";
import { ROOT } from "../../../checks/lib/world";

export type ProductionTrace = {
  batch: number;
  building: string;
  template: string;
  // True when the golden set has no lease on this template.
  unseen: boolean;
  verdict: string;
};

let cachedTruth: Map<string, ProductionTrace> | undefined;

/** Every production trace with its batch, building, template and the aligned judge's verdict. */
export function productionTruth(): Map<string, ProductionTrace> {
  if (cachedTruth !== undefined) return cachedTruth;
  const script = join(import.meta.dir, "production_truth.py");
  const ran = run([...python(), script], ROOT, 120_000);
  if (ran.code !== 0) throw new Error(`production_truth.py failed: ${ran.err}`);
  const rows = JSON.parse(ran.out) as Record<string, ProductionTrace>;
  cachedTruth = new Map(Object.entries(rows));
  return cachedTruth;
}

/** The trace ids of one batch. */
export function batchIds(batch: number): string[] {
  const ids: string[] = [];
  for (const [id, trace] of productionTruth()) if (trace.batch === batch) ids.push(id);
  return ids;
}

export const BATCHES = [1, 2, 3, 4, 5, 6, 7];

/** The new template's name, read from the traces, so no check hard-codes it. */
export function newTemplates(): Set<string> {
  const names = new Set<string>();
  for (const trace of productionTruth().values()) if (trace.unseen) names.add(trace.template);
  return names;
}
