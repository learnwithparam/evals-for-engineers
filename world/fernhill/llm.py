"""One door to every model. Code asks for a role (fast, smart, judge), never a model id.

LLM_PROVIDER=replay (the default) answers from recorded replies in world/replay/, so the course,
its checks and CI run with no key. Any other provider calls the model live through LiteLLM.
"""

import hashlib
import json
import os
from dataclasses import dataclass

from . import paths


class ReplayMissingError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    role: str
    provider: str
    replayed: bool
    cost_usd: float


@dataclass
class CallSettings:
    """How to make one call.

    system names the Fernhill system that is calling, for the call log. trial picks one of several
    recorded replies in replay. max_tokens caps the length of a live reply.
    """

    system: str = ""
    trial: int = 1
    max_tokens: int = 800


def key(role: str, messages: list[dict], trial: int = 1) -> str:
    blob = json.dumps({"role": role, "messages": messages, "trial": trial}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


# Every recorded reply by its key, read from world/replay/ on the first replayed call.
_RECORDED: dict[str, dict] | None = None


def recorded() -> dict[str, dict]:
    global _RECORDED
    if _RECORDED is None:
        _RECORDED = {}
        for replay_file in sorted(paths.REPLAY.glob("*.jsonl")):
            for row in paths.read_jsonl(replay_file):
                _RECORDED[row["key"]] = row
    return _RECORDED


def provider() -> str:
    paths.load_env()
    return paths.config_models().provider()


def complete(role: str, messages: list[dict], settings: CallSettings | None = None) -> Reply:
    """Send messages to the model for a role."""
    settings = settings or CallSettings()
    provider_name = provider()
    if provider_name == "replay":
        return _replay(role, messages, settings)
    return _live(provider_name, role, messages, settings)


def _log_call(settings: CallSettings, reply: Reply) -> None:
    paths.log(
        "calls",
        {
            "system": settings.system,
            "role": reply.role,
            "provider": reply.provider,
            "ok": True,
            "replayed": reply.replayed,
            "cost_usd": reply.cost_usd,
        },
    )


def _replay(role: str, messages: list[dict], settings: CallSettings) -> Reply:
    row = recorded().get(key(role, messages, settings.trial))
    if row is None:
        paths.log(
            "calls",
            {
                "system": settings.system,
                "role": role,
                "provider": "replay",
                "ok": False,
                "replayed": True,
            },
        )
        raise ReplayMissingError(
            "No recorded reply for this prompt. "
            "Replay only knows the prompts the finished system sends. "
            "To run your own prompt, set LLM_PROVIDER and one key in .env (see .env.example)."
        )
    reply = Reply(row["reply"], role, "replay", True, 0.0)
    _log_call(settings, reply)
    return reply


def _live(provider_name: str, role: str, messages: list[dict], settings: CallSettings) -> Reply:
    model_config = paths.config_models()
    key_name = model_config.KEY_NAME.get(provider_name)
    if key_name and not os.environ.get(key_name):
        raise RuntimeError(
            f"LLM_PROVIDER={provider_name} needs {key_name} in .env (see .env.example)."
        )
    import litellm  # imported late so replay never loads it

    litellm.suppress_debug_info = True
    response = litellm.completion(
        model=model_config.model_for(role, provider_name),
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=0,
    )
    text = response.choices[0].message.content or ""
    try:
        cost = float(litellm.completion_cost(completion_response=response))
    except Exception:
        cost = 0.0
    reply = Reply(text, role, provider_name, False, cost)
    _log_call(settings, reply)
    return reply
