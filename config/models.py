"""The only file that names a model.

Code asks for a role, never an id: models.fast (cheap, most calls), models.smart (hard reasoning),
models.judge (grading). The provider comes from LLM_PROVIDER: replay (default, no key), anthropic,
openrouter, openai or ollama. Ids were read from the providers' live model lists on the build date.
"""

import os

IDS = {
    "anthropic": {
        "fast": "claude-haiku-5-5",
        "smart": "claude-sonnet-5-5",
        "judge": "claude-haiku-5-5",
    },
    "openrouter": {
        "fast": "nvidia/nemotron-3.5-lightning",
        "smart": "anthropic/claude-sonnet-5.5",
        "judge": "anthropic/claude-haiku-5.5",
    },
    "openai": {"fast": "gpt-6-luna", "smart": "gpt-6-luna-pro", "judge": "gpt-6-luna"},
}

# LiteLLM routes a call by this prefix.
PREFIX = {
    "anthropic": "anthropic/",
    "openrouter": "openrouter/",
    "openai": "openai/",
    "ollama": "ollama/",
}
KEY_NAME = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}
ROLES = ("fast", "smart", "judge")
PROVIDERS = ("replay", "anthropic", "openrouter", "openai", "ollama")


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "replay").strip().lower() or "replay"


def model_for(role: str, prov: str | None = None) -> str:
    """The LiteLLM model string for a role on a provider. Never printed to the learner."""
    prov = prov or provider()
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; use one of {', '.join(ROLES)}")
    if prov == "ollama":
        local = os.environ.get("OLLAMA_MODEL", "").strip()
        if not local:
            raise RuntimeError(
                "LLM_PROVIDER=ollama needs OLLAMA_MODEL in .env (the local model to use)."
            )
        return PREFIX[prov] + local
    if prov not in IDS:
        raise ValueError(f"LLM_PROVIDER={prov!r} has no models; use one of {', '.join(PROVIDERS)}")
    return PREFIX[prov] + IDS[prov][role]


class _Models:
    """models.fast, models.smart, models.judge: the id for the current provider."""

    def __getattr__(self, role: str) -> str:
        return model_for(role)


models = _Models()
