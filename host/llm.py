from __future__ import annotations

import os
from urllib.parse import urljoin

import httpx


class LlmError(RuntimeError):
    pass


async def complete(prompt: str, backend: str, model: str, base_url: str, api_key: str) -> str:
    if backend == "echo":
        return f"「{prompt}」ですね。"
    if backend == "ollama":
        url = urljoin(base_url.rstrip("/") + "/", "api/chat")
        payload = {
            "model": model or "llama3.2",
            "messages": [
                {"role": "system", "content": "短く日本語で答えてください。"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()["message"]["content"]
    if backend == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise LlmError("OPENAI_API_KEY が無い")
        url = urljoin(base_url.rstrip("/") + "/", "chat/completions")
        headers = {"Authorization": f"Bearer {key}"}
        payload = {
            "model": model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "短く日本語で答えてください。"},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    raise LlmError(f"unknown llm backend {backend}")
