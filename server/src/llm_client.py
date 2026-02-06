"""Ollama HTTP API 클라이언트 - 단일 LLM 인스턴스로 전체 서버에서 공유"""
import logging
import requests

log = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.url = f"{self.base_url}/api/chat"

    def chat(self, messages: list, temperature: float = 0.8, max_tokens: int = 256) -> str:
        """ollama /api/chat 호출. messages는 [{"role": ..., "content": ...}, ...] 형식."""
        try:
            resp = requests.post(self.url, json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }, timeout=30)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except Exception as exc:
            log.error("Ollama API error: %s", exc)
            return ""
