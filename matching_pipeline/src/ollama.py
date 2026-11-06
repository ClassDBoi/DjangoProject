"""Calls the local Ollama server (standard library only). A mock stands in for quick checks."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from common import extract_json


class BackendError(RuntimeError):
    pass


class OllamaBackend:
    """Schema-constrained JSON from a local Ollama model (the `format` parameter)."""

    def __init__(self, generator: dict, settings: dict):
        self.generator, self.settings = generator, settings
        self.url = settings["ollama_url"].rstrip("/")

    def check(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=10) as response:
                tags = json.load(response)
        except (urllib.error.URLError, OSError) as exc:
            raise BackendError(f"Ollama is not reachable at {self.url}. Start the Ollama app first.") from exc
        names = {m["name"] for m in tags.get("models", [])}
        wanted = self.generator["model_id"]
        if wanted not in names and f"{wanted}:latest" not in names:
            raise BackendError(f"Model '{wanted}' is not installed. Run:  ollama pull {wanted}")

    def chat(self, messages: list[dict], schema: dict) -> dict:
        body = {
            "model": self.generator["model_id"],
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": self.settings["temperature"],
                "seed": self.settings["seed"],
                "num_ctx": self.settings["num_ctx"],
                "num_predict": self.settings["max_new_tokens"],
            },
        }
        if "think" in self.generator:
            body["think"] = self.generator["think"]
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.settings["request_timeout_s"]) as response:
                reply = json.load(response)
        except urllib.error.HTTPError as exc:
            raise BackendError(f"Ollama error {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        text = reply.get("message", {}).get("content", "")
        prompt_tokens = reply.get("prompt_eval_count")
        return {
            "text": text,
            "parsed": extract_json(text),
            "seconds": round(time.perf_counter() - started, 2),
            "prompt_tokens": prompt_tokens,
            "output_tokens": reply.get("eval_count"),
            # Ollama silently drops the start of prompts longer than num_ctx.
            "truncated": bool(prompt_tokens and prompt_tokens >= self.settings["num_ctx"] - 8),
            "hit_max_tokens": reply.get("done_reason") == "length",
        }


class MockBackend:
    """Stand-in for checking the pipeline runs end to end without Ollama.
    Its "topics" are just words copied from the text, so its output is meaningless."""

    def __init__(self, generator: dict, settings: dict):
        pass

    def check(self) -> None:
        pass

    def chat(self, messages: list[dict], schema: dict) -> dict:
        user = messages[-1]["content"]
        source = user.split('"""')[1] if '"""' in user else user
        words = list(dict.fromkeys(w.title() for w in re.findall(r"[A-Za-z]{6,}", source)))[:6] or ["Placeholder"]
        data = {"analysis": "mock", "items": [
            {"term": w, "type": "keyword", "importance": 5 - i % 5, "justification": "mock"} for i, w in enumerate(words)]}
        text = json.dumps(data)
        return {"text": text, "parsed": data, "seconds": 0.0, "prompt_tokens": len(user) // 4,
                "output_tokens": len(text) // 4, "truncated": False, "hit_max_tokens": False}


def make_backend(config: dict, mock: bool = False):
    backend = MockBackend if mock else OllamaBackend
    return backend(config["generator"], config["generation"])
