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
  for (const fault of plantedFaults()) {
    expect(fault.fault).toBeGreaterThanOrEqual(1);
    expect(fault.fault).toBeLessThanOrEqual(7);
    // Only abstractor faults that name a trace can be looked up in the recorded traces.
    if (fault.system === "abstractor" && fault.ref.startsWith("abs-")) {
      expect(traces.has(fault.ref)).toBe(true);
    }
  }
  const numbers = new Set(plantedFaults().map((fault) => fault.fault));
  expect(numbers).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]));
});

test("Dana labels every abstractor trace", () => {
  expect(danaAbstractor().size).toBe(abstractorTraces().size);
});

test("the golden and gate sets do not overlap", () => {
  const { golden, gate } = splits();
  expect(golden.filter((id) => gate.includes(id))).toEqual([]);
});

test("the orientation's sample report was made from this world", () => {
  const reportPath = join(ROOT, "00-orientation/01-meet-fernhill/solution/report.txt");
  const report = readFileSync(reportPath, "utf8");
  expect(report).toContain(`fingerprint ${fingerprint()}`);
});
