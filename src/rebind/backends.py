"""Model backends. All of them speak the OpenAI chat-completions protocol.

Specs:
  ollama:<model>                 local Ollama, e.g. ollama:olmo-3:7b-instruct
  openai-compat:<model>@<url>    any OpenAI-compatible server, e.g. LM Studio or llama.cpp.
                                 The key is read from REBIND_API_KEY.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class Backend:
    spec: str
    model: str
    base_url: str
    api_key: str

    def __post_init__(self):
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=600)

    def describe(self) -> dict:
        info = {"spec": self.spec, "model": self.model, "base_url": self.base_url}
        if self.spec.startswith("ollama:"):
            info.update(_ollama_info(self.base_url, self.model))
        return info

    def chat(self, messages: list[dict], schema: dict, *, temperature: float, seed: int, max_tokens: int,
             schema_name: str = "passage_reading") -> dict:
        t0 = time.time()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
        )
        choice = resp.choices[0]
        return {
            "text": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "served_model": resp.model,
            "usage": resp.usage.model_dump() if resp.usage else None,
            "latency_s": round(time.time() - t0, 2),
        }


def _ollama_info(base_url: str, model: str) -> dict:
    """Pin the exact weights a run used: Ollama version, model digest, size and quantization,
    and the server's context length (prompts longer than it would be silently cut)."""
    root = base_url.removesuffix("/").removesuffix("/v1")

    def get(path):
        try:
            with urllib.request.urlopen(root + path, timeout=5) as r:
                return json.load(r)
        except Exception:
            return {}

    tag = model if ":" in model else model + ":latest"
    m = next((m for m in get("/api/tags").get("models", []) if m["name"] == tag), {})
    loaded = next((m for m in get("/api/ps").get("models", []) if m["name"] == tag), {})
    return {
        "server_version": get("/api/version").get("version"),
        "digest": m.get("digest"),
        "parameter_size": m.get("details", {}).get("parameter_size"),
        "quantization": m.get("details", {}).get("quantization_level"),
        "context_length": loaded.get("context_length"),  # known only while the model is loaded
    }


def from_spec(spec: str) -> Backend:
    kind, _, rest = spec.partition(":")
    if kind == "ollama":
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")
        return Backend(spec, rest, url, "ollama")
    if kind == "openai-compat":
        model, _, url = rest.rpartition("@")
        return Backend(spec, model, url, os.environ.get("REBIND_API_KEY", "none"))
    raise ValueError(f"Unknown backend spec {spec!r}")
