from __future__ import annotations


DEFAULT_MODEL = "google/gemini-3.5-flash"

MODEL_PRESETS = [
    {
        "id": DEFAULT_MODEL,
        "name": "Gemini 3.5 Flash",
        "tier": "Default",
        "description": "Fast, high-quality default for project analysis and context planning.",
        "context": "1M",
        "price": "$1.50 input / $9 output per 1M tokens",
    },
    {
        "id": "openai/gpt-5.5",
        "name": "GPT-5.5 Extra High",
        "tier": "Premium alternative",
        "description": "High-end reasoning alternative for critical planning and architecture review.",
        "context": "1M",
        "price": "$5 input / $30 output per 1M tokens",
        "reasoning_effort": "xhigh",
    },
    {
        "id": "anthropic/claude-opus-4.7",
        "name": "Claude Opus 4.7 Max",
        "tier": "Maximum alternative",
        "description": "Highest-effort alternative for the hardest architecture and planning decisions.",
        "context": "1M",
        "price": "$5 input / $25 output per 1M tokens",
        "verbosity": "max",
    },
]


def model_presets() -> list[dict[str, str]]:
    return [preset.copy() for preset in MODEL_PRESETS]


def model_request_options(model_id: str) -> dict[str, str]:
    for preset in MODEL_PRESETS:
        if preset["id"] != model_id:
            continue
        options = {}
        for key in ("reasoning_effort", "verbosity"):
            if key in preset:
                options[key] = preset[key]
        return options
    return {}
