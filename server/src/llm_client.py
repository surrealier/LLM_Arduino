"""Ollama HTTP API 클라이언트 - 단일 LLM 인스턴스로 전체 서버에서 공유"""
import logging
import requests

log = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.url = f"{self.base_url}/api/chat/"
        self.url_generate = f"{self.base_url}/api/generate/"

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
            data = resp.json()
            content = ""
            if isinstance(data, dict):
                msg = data.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content") or ""
                elif "response" in data:
                    content = data.get("response") or ""
            if not content.strip():
                log.warning("Ollama returned empty content. status=%s body=%s", resp.status_code, resp.text[:500])
                fallback = self._generate_fallback(messages, temperature, max_tokens)
                if fallback.strip():
                    log.info("Ollama chat empty -> generate fallback ok (len=%d)", len(fallback.strip()))
                    return fallback.strip()
            return content.strip()
        except Exception as exc:
            log.error("Ollama API error: %s", exc)
            return ""

    def _generate_fallback(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Fallback to /api/generate when /api/chat returns empty content."""
        try:
            prompt = self._messages_to_prompt(messages)
            resp = requests.post(self.url_generate, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return (data.get("response") or "").strip()
        except Exception as exc:
            log.error("Ollama generate fallback error: %s", exc)
        return ""

    @staticmethod
    def _messages_to_prompt(messages: list) -> str:
        """Simple chat-to-prompt converter for /api/generate."""
        lines = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                lines.append(f"SYSTEM: {content}")
            elif role == "user":
                lines.append(f"USER: {content}")
            elif role == "assistant":
                lines.append(f"ASSISTANT: {content}")
        lines.append("ASSISTANT:")
        return "\n".join(lines)


