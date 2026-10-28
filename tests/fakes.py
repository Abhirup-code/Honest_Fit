"""A stand-in for Ollama so tests never need a real model or network."""

from __future__ import annotations

import json

import httpx

from app.llm import AIError, AIStatus, ExtraRequirements, Tips


def ollama_transport(answers: list[dict] | None = None, models=("llama3.2:3b",), fail: str | None = None):
    """Fake /api/tags and /api/chat. `answers` are returned in order as the model's JSON content."""
    queue = list(answers or [])
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if fail == "connect":
            raise httpx.ConnectError("refused", request=request)
        if fail == "timeout" and request.url.path == "/api/chat":
            raise httpx.ReadTimeout("slow", request=request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in models]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content)
            seen.append(body)
            if fail == "500":
                return httpx.Response(500, json={"error": "boom"})
            content = queue.pop(0) if queue else {}
            text = content if isinstance(content, str) else json.dumps(content)
            return httpx.Response(200, json={"message": {"role": "assistant", "content": text}, "done": True})
        return httpx.Response(404)

    return httpx.MockTransport(handler), seen


class FakeProvider:
    def __init__(self, extras=None, tips=None, available=True, error: str | None = None):
        # error is an AIError code: "timeout", "unreachable", or "bad_answer"
        self.extras = extras or []
        self.tips = tips or []
        self.available = available
        self.error = error

    def status(self) -> AIStatus:
        return AIStatus(self.available, "fake model" if self.available else "Ollama is not running.")

    def extra_requirements(self, job, known):
        if self.error:
            raise AIError(self.error)
        return ExtraRequirements.model_validate({"requirements": self.extras})

    def rewrite_tips(self, job, resume, matched):
        return Tips.model_validate({"tips": self.tips})
