import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  abstractorTraces,
  danaAbstractor,
  fingerprint,
  plantedFaults,
  ROOT,
  splits,
} from "../checks/lib/world";

test("every planted fault is numbered 1 to 7 and points at something real", () => {
  const traces = abstractorTraces();
  for (const f of plantedFaults()) {
    expect(f.fault).toBeGreaterThanOrEqual(1);
    expect(f.fault).toBeLessThanOrEqual(7);
    if (f.system === "abstractor" && f.ref.startsWith("abs-")) expect(traces.has(f.ref)).toBe(true);
  }
  expect(new Set(plantedFaults().map((f) => f.fault))).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]));
});

test("Dana labels every abstractor trace", () => {
  expect(danaAbstractor().size).toBe(abstractorTraces().size);
});

test("the golden and gate sets do not overlap", () => {
  const s = splits();
  expect(s.golden.filter((x: string) => s.gate.includes(x))).toEqual([]);
});

test("the orientation's sample report was made from this world", () => {
  const r = readFileSync(join(ROOT, "00-orientation/01-meet-fernhill/solution/report.txt"), "utf8");
  expect(r).toContain(`fingerprint ${fingerprint()}`);
});
