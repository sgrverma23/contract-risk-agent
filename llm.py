"""
Thin LLM wrapper using the OpenAI SDK with configurable providers.

Google Gemini exposes an OpenAI-compatible endpoint, so we use the same
openai.OpenAI client for all providers — no extra libraries needed.

Set LLM_PROVIDER in .env to switch:
  gemini    → Google Gemini (free)   — aistudio.google.com
  groq      → Groq / Llama (free)    — console.groq.com
  anthropic → Anthropic (paid)       — console.anthropic.com
"""

import os
import json
from openai import OpenAI

_PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-1.5-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "openai/gpt-oss-20b",
    },
    "anthropic": {
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-opus-4-5",
    },
}


def _client_and_model():
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    cfg = _PROVIDERS.get(provider, _PROVIDERS["gemini"])

    api_key = os.environ.get(cfg["api_key_env"], "")
    model   = os.environ.get("LLM_MODEL", cfg["model"])

    kwargs = {"api_key": api_key}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]

    return OpenAI(**kwargs), model


def call_with_tool(
    messages: list[dict],
    tool: dict,
    system: str = "",
    max_tokens: int = 4096,
) -> tuple[dict, int]:
    """Call the LLM with a single tool. Returns (parsed_args, tokens_used)."""
    client, model = _client_and_model()

    all_msgs = []
    if system:
        all_msgs.append({"role": "system", "content": system})
    all_msgs.extend(messages)

    response = client.chat.completions.create(
        model=model,
        messages=all_msgs,
        tools=[{"type": "function", "function": tool}],
        tool_choice="auto",
        max_tokens=max_tokens,
    )

    tokens     = response.usage.total_tokens if response.usage else 0
    tool_calls = response.choices[0].message.tool_calls or []
    if tool_calls:
        return json.loads(tool_calls[0].function.arguments), tokens
    return {}, tokens


def call(messages: list[dict], system: str = "", max_tokens: int = 3000) -> tuple[str, int]:
    """Simple text completion. Returns (text, tokens_used)."""
    client, model = _client_and_model()

    all_msgs = []
    if system:
        all_msgs.append({"role": "system", "content": system})
    all_msgs.extend(messages)

    response = client.chat.completions.create(
        model=model,
        messages=all_msgs,
        max_tokens=max_tokens,
    )

    tokens = response.usage.total_tokens if response.usage else 0
    return response.choices[0].message.content or "", tokens
