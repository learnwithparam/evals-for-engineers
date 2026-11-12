"""uv run models: one tiny call per role on the chosen provider. Prints role, provider, pass or fail, cost."""

import sys

from . import llm, paths

PING = [{"role": "user", "content": "Reply with the single word ok."}]


def main() -> int:
    prov = llm.provider()
    cm = paths.config_models()
    if prov not in cm.PROVIDERS:
        print(f"LLM_PROVIDER={prov} is not known. Use one of: {', '.join(cm.PROVIDERS)}.")
        return 2
    print(f"Provider: {prov}")
    bad = 0
    for role in cm.ROLES:
        try:
            r = llm.complete(role, PING, system="models", max_tokens=5)
            ok = "ok" in r.text.lower()
            print(f"  {role:<6} {'PASS' if ok else 'FAIL'}  cost ${r.cost_usd:.6f}")
            bad += 0 if ok else 1
        except Exception as e:  # the message never holds a key
            print(f"  {role:<6} FAIL  {str(e).splitlines()[0][:160]}")
            bad += 1
    print(
        "Every role answers."
        if not bad
        else f"{bad} role(s) failed. See 00-orientation/troubleshooting.md."
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
