import { expect, test } from "bun:test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

type Session = { name: string; parts: string[]; minutes: number };

const ROOT = join(import.meta.dir, "..");

function stepMinutes(stepFolder: string): number {
  const path = join(stepFolder, "step.toml");
  if (!existsSync(path)) return 0;
  return Number(readFileSync(path, "utf8").match(/minutes\s*=\s*(\d+)/)?.[1] ?? 0);
}

function minutesOfPart(partFolder: string): number {
  const entries = readdirSync(partFolder, { withFileTypes: true });
  const steps = entries.filter((entry) => entry.isDirectory());
  return steps.reduce((total, step) => total + stepMinutes(join(partFolder, step.name)), 0);
}

// Minutes per part come from the step.toml files, the one source.
function partMinutes(): Record<string, number> {
  const found: Record<string, number> = {};
  const folders = [join(ROOT, "00-orientation")];
  for (const name of readdirSync(join(ROOT, "parts"))) folders.push(join(ROOT, "parts", name));
  for (const folder of folders) {
    found[folder.replace(/^.*\/\d\d-/, "")] = minutesOfPart(folder);
  }
  return found;
}

test("every session's minutes equal the sum of its parts", () => {
  const minutes = partMinutes();
  const text = readFileSync(join(ROOT, "schedules.toml"), "utf8");
  const schedules = Bun.TOML.parse(text) as Record<string, { sessions: Session[] }>;
  for (const schedule of Object.values(schedules)) {
    for (const session of schedule.sessions) {
      const sum = session.parts.reduce((total, part) => total + (minutes[part] ?? Number.NaN), 0);
      expect(session.minutes, session.name).toBe(sum);
    }
  }
});
