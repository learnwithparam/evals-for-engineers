// Reads the repo layout once. Every other script asks this file where things are.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

export const ROOT = join(import.meta.dir, "..");

export type Step = {
  name: string; // verb-the-thing, also the command argument
  dir: string;
  part: string;
  meta: { minutes: number; screen: boolean; solution: boolean };
};
export type Part = { name: string; dir: string; steps: Step[] };

const dirs = (p: string) =>
  existsSync(p)
    ? readdirSync(p)
        .filter((d) => statSync(join(p, d)).isDirectory())
        .sort()
    : [];

// Folders keep an order prefix for sorting only. Learners never type it.
export const bareName = (folder: string) => folder.replace(/^\d+-/, "");

// A folder is a step once it has step.toml or problem/. A part with no step yet is a skeleton: it has a
// README for the session that builds it, and the checks skip it until its first step lands.
const isStep = (d: string) => existsSync(join(d, "step.toml")) || existsSync(join(d, "problem"));

export function parts(): Part[] {
  const root = join(ROOT, "parts");
  const found = dirs(root).map((p) => ({ dir: join(root, p), name: bareName(p) }));
  // The orientation holds a checked step too, so it counts as the first part.
  const orient = join(ROOT, "00-orientation");
  if (dirs(orient).some((d) => isStep(join(orient, d))))
    found.unshift({ dir: orient, name: "orientation" });
  return found
    .filter(({ dir }) => dirs(dir).some((d) => isStep(join(dir, d))))
    .map(({ dir, name }) => {
      const steps = dirs(dir)
        .filter((s) => isStep(join(dir, s)))
        .map((s) => {
          const sdir = join(dir, s);
          const metaPath = join(sdir, "step.toml");
          const raw = existsSync(metaPath)
            ? (Bun.TOML.parse(readFileSync(metaPath, "utf8")) as any)
            : {};
          return {
            name: bareName(s),
            dir: sdir,
            part: name,
            meta: {
              minutes: Number(raw.minutes ?? 0),
              screen: Boolean(raw.screen),
              solution: Boolean(raw.solution),
            },
          };
        });
      return { name, dir, steps };
    });
}

export const allSteps = () => parts().flatMap((p) => p.steps);

export function findStep(name: string): Step | undefined {
  return allSteps().find((s) => s.name === name);
}

/** Part folders under parts/ that have no step yet: built later by their own session. */
export function skeletons(): string[] {
  const root = join(ROOT, "parts");
  return dirs(root)
    .filter((p) => !dirs(join(root, p)).some((d) => isStep(join(root, p, d))))
    .map(bareName);
}
