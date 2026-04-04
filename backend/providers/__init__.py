"""Provider registry — single source of truth for available models and provider routing."""

MODELS = [
    # Anthropic (Claude)
    {"value": "claude-sonnet-4-20250514", "label": "Claude Sonnet", "provider": "claude"},
    {"value": "claude-opus-4-20250514", "label": "Claude Opus", "provider": "claude"},
    {"value": "claude-haiku-3-5-20241022", "label": "Claude Haiku", "provider": "claude"},
    # OpenAI (Codex / Reasoning)
    {"value": "codex-mini-latest", "label": "Codex Mini", "provider": "openai"},
    {"value": "o4-mini", "label": "O4 Mini", "provider": "openai"},
    {"value": "o3-mini", "label": "O3 Mini", "provider": "openai"},
]

_MODEL_PROVIDER_MAP: dict[str, str] = {m["value"]: m["provider"] for m in MODELS}

_PREFIX_PROVIDER_MAP = {
    "claude-": "claude",
    "codex-": "openai",
    "o3-": "openai",
    "o4-": "openai",
}


def get_provider(model: str) -> str:
    """Determine the provider for a given model string.

    Resolution order:
      1. Exact match in the model registry
      2. Known prefix match
      3. Default to 'claude'
    """
    if model in _MODEL_PROVIDER_MAP:
        return _MODEL_PROVIDER_MAP[model]
    for prefix, provider in _PREFIX_PROVIDER_MAP.items():
        if model.startswith(prefix):
            return provider
    return "claude"
