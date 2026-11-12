"""uv run models: one tiny call per role on the chosen provider.

Prints the provider, then each role with pass or fail and the cost.
"""

import sys

from . import llm, paths

PING = [{"role": "user", "content": "Reply with the single word ok."}]


def check_role(role: str) -> bool:
    """Make one tiny call for a role, print how it went, and say whether it passed."""
    try:
        reply = llm.complete(role, PING, llm.CallSettings(system="models", max_tokens=5))
    except Exception as error:  # the message never holds a key
        first_line = str(error).splitlines()[0]
        print(f"  {role:<6} FAIL  {first_line[:160]}")
        return False
    passed = "ok" in reply.text.lower()
    verdict = "PASS" if passed else "FAIL"
    print(f"  {role:<6} {verdict}  cost ${reply.cost_usd:.6f}")
    return passed


def main() -> int:
    provider_name = llm.provider()
    model_config = paths.config_models()
    if provider_name not in model_config.PROVIDERS:
        known = ", ".join(model_config.PROVIDERS)
        print(f"LLM_PROVIDER={provider_name} is not known. Use one of: {known}.")
        return 2
    print(f"Provider: {provider_name}")
    failed = 0
    for role in model_config.ROLES:
        if not check_role(role):
            failed += 1
    if failed:
        print(f"{failed} role(s) failed. See 00-orientation/troubleshooting.md.")
        return 1
    print("Every role answers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
