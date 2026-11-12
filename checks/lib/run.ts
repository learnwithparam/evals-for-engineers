// Runs the learner's work: a Python script or a command, always in replay mode, so no check needs a key.
import { existsSync } from "node:fs";
import { ROOT } from "./world";

export type Ran = { code: number; out: string; err: string };

/** The Python to use: the course's uv environment when uv is here, else python3 (CI has only Bun). */
export function python(): string[] {
  if (process.env.PYTHON) return [process.env.PYTHON];
  if (Bun.which("uv") && existsSync(`${ROOT}/pyproject.toml`)) return ["uv", "run", "--quiet", "python"];
  return [Bun.which("python3") ?? "python"];
}

export function run(cmd: string[], cwd: string, timeoutMs = 60_000): Ran {
  const p = Bun.spawnSync(cmd, {
    cwd,
    env: { ...process.env, LLM_PROVIDER: "replay", PYTHONDONTWRITEBYTECODE: "1" },
    timeout: timeoutMs,
    stdout: "pipe",
    stderr: "pipe",
  });
  return { code: p.exitCode ?? -1, out: p.stdout.toString(), err: p.stderr.toString() };
}

export const runPython = (script: string, args: string[], cwd: string, timeoutMs?: number) =>
  run([...python(), script, ...args], cwd, timeoutMs);

/** Behaviour that depends on a model is judged over three fresh runs in replay mode. */
export function threeRuns(cmd: string[], cwd: string): Ran[] {
  return [1, 2, 3].map(() => run(cmd, cwd));
}

/** Memoise a run per folder, so several rules can read one run of the learner's work. */
export function once<T>(fn: (dir: string) => T): (dir: string) => T {
  const cache = new Map<string, T>();
  return (dir) => {
    if (!cache.has(dir)) cache.set(dir, fn(dir));
    return cache.get(dir)!;
  };
}
