"""Provider-agnostic LLM client. FREE providers only.

- gemini : Google AI Studio free tier
- ollama : fully offline local models

Exposes .chat() for text and .json() for structured output.
"""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from ..config import settings


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from an LLM response."""
    text = text.strip()
    # strip markdown code fences
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # try direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # try to find first {...} or [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                continue
    raise LLMError(f"Could not parse JSON from LLM output:\n{text[:500]}")


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()
        self._gemini = None
        if self.provider == "gemini":
            self._init_gemini()

    def _init_gemini(self) -> None:
        if not settings.gemini_api_key:
            # Defer error until first call so the server can still boot.
            return
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self._gemini = genai

    # ------------------------------------------------------------------
    def chat(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if self.provider == "gemini":
            return self._chat_gemini(prompt, system, temperature, max_tokens)
        if self.provider == "ollama":
            return self._chat_ollama(prompt, system, temperature, max_tokens)
        raise LLMError(f"Unknown LLM provider: {self.provider}")

    def json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
    ) -> Any:
        """Ask the model and parse a JSON object/array from the reply."""
        guard = (
            "\n\nRespond with ONLY valid JSON. No markdown, no prose, "
            "no code fences."
        )
        raw = self.chat(prompt + guard, system, temperature, max_tokens)
        return _extract_json(raw)

    # ------------------------------------------------------------------
    def _chat_gemini(self, prompt, system, temperature, max_tokens) -> str:
        if self._gemini is None:
            self._init_gemini()
        if self._gemini is None:
            raise LLMError(
                "GEMINI_API_KEY missing. Get a FREE key at "
                "https://aistudio.google.com/app/apikey"
            )
        model = self._gemini.GenerativeModel(
            settings.gemini_model,
            system_instruction=system or None,
        )
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        try:
            return resp.text
        except Exception as exc:  # blocked / empty
            raise LLMError(f"Gemini returned no text: {exc}")

    def _chat_ollama(self, prompt, system, temperature, max_tokens) -> str:
        url = f"{settings.ollama_base_url}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            r = requests.post(
                url,
                json={
                    "model": settings.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=180,
            )
            r.raise_for_status()
        except Exception as exc:
            raise LLMError(f"Ollama request failed: {exc}")
        return r.json().get("message", {}).get("content", "")


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client