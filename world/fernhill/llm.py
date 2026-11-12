"""One door to every model. Code asks for a role (fast, smart, judge), never a model id.

LLM_PROVIDER=replay (the default) answers from recorded replies in world/replay/, so the course,
its checks and CI run with no key. Any other provider calls the model live through LiteLLM.
"""

import hashlib
import json
import os
from dataclasses import dataclass

from . import paths


class ReplayMissing(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    role: str
    provider: str
    replayed: bool
    cost_usd: float


def key(role: str, messages: list[dict], trial: int = 1) -> str:
    blob = json.dumps({"role": role, "messages": messages, "trial": trial}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


_RECORDED: dict[str, dict] | None = None


def recorded() -> dict[str, dict]:
    global _RECORDED
    if _RECORDED is None:
        _RECORDED = {}
        for f in sorted(paths.REPLAY.glob("*.jsonl")):
            for row in paths.read_jsonl(f):
                _RECORDED[row["key"]] = row
    return _RECORDED


def provider() -> str:
    paths.load_env()
    return paths.config_models().provider()


def complete(
    role: str, messages: list[dict], *, trial: int = 1, system: str = "", max_tokens: int = 800
) -> Reply:
    """Send messages to the model for a role. trial picks one of several recorded replies in replay."""
    prov = provider()
    if prov == "replay":
        row = recorded().get(key(role, messages, trial))
        if row is None:
            paths.log(
                "calls",
                {"system": system, "role": role, "provider": prov, "ok": False, "replayed": True},
            )
            raise ReplayMissing(
                "No recorded reply for this prompt. Replay only knows the prompts the finished system sends. "
                "To run your own prompt, set LLM_PROVIDER and one key in .env (see .env.example)."
            )
        paths.log(
            "calls",
            {
                "system": system,
                "role": role,
                "provider": prov,
                "ok": True,
                "replayed": True,
                "cost_usd": 0.0,
            },
        )
        return Reply(row["reply"], role, prov, True, 0.0)
    return _live(prov, role, messages, system, max_tokens)


def _live(prov: str, role: str, messages: list[dict], system: str, max_tokens: int) -> Reply:
    cm = paths.config_models()
    key_name = cm.KEY_NAME.get(prov)
    if key_name and not os.environ.get(key_name):
        raise RuntimeError(f"LLM_PROVIDER={prov} needs {key_name} in .env (see .env.example).")
    import litellm  # imported late so replay never loads it

    litellm.suppress_debug_info = True
    resp = litellm.completion(
        model=cm.model_for(role, prov), messages=messages, max_tokens=max_tokens, temperature=0
    )
    text = resp.choices[0].message.content or ""
    try:
        cost = float(litellm.completion_cost(completion_response=resp))
    except Exception:
        cost = 0.0
    paths.log(
        "calls",
        {
            "system": system,
            "role": role,
            "provider": prov,
            "ok": True,
            "replayed": False,
            "cost_usd": cost,
        },
    )
    return Reply(text, role, prov, False, cost)
