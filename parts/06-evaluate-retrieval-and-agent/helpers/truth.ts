// Shared by the checks of Evaluate retrieval and the agent. The supervisor may move it to
// checks/lib/. Each helper script prints JSON that the checks compare the learner's work with.
import { join } from "node:path";
import { python, run } from "../../../checks/lib/run";
import { ROOT } from "../../../checks/lib/world";

const cached = new Map<string, unknown>();

/** Runs one helper script in replay mode, once per check process, and parses what it prints. */
export function helperOutput<Shape>(script: string, args: string[] = []): Shape {
  const cacheKey = [script, ...args].join(" ");
  if (!cached.has(cacheKey)) {
    const path = join(import.meta.dir, script);
    const ran = run([...python(), path, ...args], ROOT, 180_000);
    if (ran.code !== 0) throw new Error(`${script} failed: ${ran.err}`);
    cached.set(cacheKey, JSON.parse(ran.out));
  }
  return cached.get(cacheKey) as Shape;
}
