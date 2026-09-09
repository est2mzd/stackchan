from __future__ import annotations

import os
from urllib.parse import urljoin

import httpx

OLLAMA_DEFAULT = "http://127.0.0.1:11434"
OPENAI_DEFAULT = "https://api.openai.com/v1"


class LlmError(RuntimeError):
    pass


def openai_base(base_url: str) -> str:
    url = (base_url or "").strip()
    if not url or "11434" in url:
        return OPENAI_DEFAULT
    return url.rstrip("/")


def ollama_base(base_url: str) -> str:
    url = (base_url or "").strip()
    return (url or OLLAMA_DEFAULT).rstrip("/")


async def complete(prompt: str, backend: str, model: str, base_url: str, api_key: str) -> str:
    if backend == "echo":
        return f"「{prompt}」ですね。"
    if backend == "ollama":
        url = urljoin(ollama_base(base_url) + "/", "api/chat")
        payload = {
            "model": model or "llama3.2",
            "messages": [
                {"role": "system", "content": "日本語で2文まで。1文は20字以内。"},
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
        url = urljoin(openai_base(base_url) + "/", "chat/completions")
        headers = {"Authorization": f"Bearer {key}"}
        payload = {
            "model": model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "日本語で2文まで。1文は20字以内。"},
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    raise LlmError(f"unknown llm backend {backend}")
