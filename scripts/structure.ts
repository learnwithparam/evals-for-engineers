// Reads the repo layout once. Every other script asks this file where things are.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join } from "node:path";

export const ROOT = join(import.meta.dir, "..");

export type Step = {
  name: string; // verb-the-thing, also the command argument
  dir: string;
  part: string;
  meta: { minutes: number; screen: boolean; solution: boolean };
};
export type Part = { name: string; dir: string; steps: Step[] };

// step.toml as written by hand: any field may be missing or have the wrong type.
type StepToml = { minutes?: unknown; screen?: unknown; solution?: unknown };

function folders(path: string): string[] {
  if (!existsSync(path)) return [];
  const entries = readdirSync(path);
  const onlyFolders = entries.filter((entry) => statSync(join(path, entry)).isDirectory());
  return onlyFolders.sort();
}

// Folders keep an order prefix for sorting only. Learners never type it.
export const bareName = (folder: string) => folder.replace(/^\d+-/, "");

// A folder is a step once it has step.toml or problem/. A part with no step yet is a skeleton:
// it has a README for the session that builds it, and the checks skip it until a step lands.
const isStep = (folder: string) =>
  existsSync(join(folder, "step.toml")) || existsSync(join(folder, "problem"));

const hasSteps = (folder: string) => folders(folder).some((child) => isStep(join(folder, child)));

function readStepToml(stepFolder: string): StepToml {
  const metaPath = join(stepFolder, "step.toml");
  if (!existsSync(metaPath)) return {};
  return Bun.TOML.parse(readFileSync(metaPath, "utf8")) as StepToml;
}

function readStep(stepFolder: string, partName: string): Step {
  const raw = readStepToml(stepFolder);
  return {
    name: bareName(basename(stepFolder)),
    dir: stepFolder,
    part: partName,
    meta: {
      minutes: Number(raw.minutes ?? 0),
      screen: Boolean(raw.screen),
      solution: Boolean(raw.solution),
    },
  };
}

function readPart(partFolder: string, partName: string): Part {
  const stepFolders = folders(partFolder)
    .map((child) => join(partFolder, child))
    .filter(isStep);
  const steps = stepFolders.map((stepFolder) => readStep(stepFolder, partName));
  return { name: partName, dir: partFolder, steps };
}

export function parts(): Part[] {
  const partsFolder = join(ROOT, "parts");
  const found = folders(partsFolder).map((folder) => ({
    dir: join(partsFolder, folder),
    name: bareName(folder),
  }));
  // The orientation holds a checked step too, so it counts as the first part.
  const orientation = join(ROOT, "00-orientation");
  if (hasSteps(orientation)) found.unshift({ dir: orientation, name: "orientation" });
  const withSteps = found.filter(({ dir }) => hasSteps(dir));
  return withSteps.map(({ dir, name }) => readPart(dir, name));
}

export const allSteps = () => parts().flatMap((part) => part.steps);

export function findStep(name: string): Step | undefined {
  return allSteps().find((step) => step.name === name);
}

/** Part folders under parts/ that have no step yet: built later by their own session. */
export function skeletons(): string[] {
  const partsFolder = join(ROOT, "parts");
  const empty = folders(partsFolder).filter((folder) => !hasSteps(join(partsFolder, folder)));
  return empty.map(bareName);
}
