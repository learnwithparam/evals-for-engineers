// Runs the learner's work: a Python script or a command, always in replay mode,
// so no check needs a key.
import { existsSync } from "node:fs";
import { ROOT } from "./world";

export type Ran = { code: number; out: string; err: string };

/**
 * The Python to use: the course's uv environment when uv is here, else python3.
 * CI has only Bun, so there it falls back to whatever python3 the runner has.
 */
export function python(): string[] {
  if (process.env.PYTHON) return [process.env.PYTHON];
  if (Bun.which("uv") && existsSync(`${ROOT}/pyproject.toml`)) {
    return ["uv", "run", "--quiet", "python"];
  }
  return [Bun.which("python3") ?? "python"];
}

// Replay mode answers from recordings, and no .pyc files are left in the learner's folder.
function replayEnvironment(): Record<string, string | undefined> {
  const environment: Record<string, string | undefined> = { ...process.env };
  environment.LLM_PROVIDER = "replay";
  environment.PYTHONDONTWRITEBYTECODE = "1";
  return environment;
}

export function run(command: string[], cwd: string, timeoutMs = 60_000): Ran {
  const finished = Bun.spawnSync(command, {
    cwd,
    env: replayEnvironment(),
    timeout: timeoutMs,
    stdout: "pipe",
    stderr: "pipe",
  });
  return {
    code: finished.exitCode ?? -1,
    out: finished.stdout.toString(),
    err: finished.stderr.toString(),
  };
}

export const runPython = (script: string, args: string[], cwd: string, timeoutMs?: number) =>
  run([...python(), script, ...args], cwd, timeoutMs);

/** Behaviour that depends on a model is judged over three fresh runs in replay mode. */
export function threeRuns(command: string[], cwd: string): Ran[] {
  return [1, 2, 3].map(() => run(command, cwd));
}

/** Memoise a run per folder, so several rules can read one run of the learner's work. */
export function once<Value>(work: (dir: string) => Value): (dir: string) => Value {
  const cache = new Map<string, Value>();
  return (dir) => {
    if (!cache.has(dir)) cache.set(dir, work(dir));
    return cache.get(dir) as Value;
  };
}
