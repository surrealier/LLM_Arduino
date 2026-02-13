"""Ollama HTTP API 클라이언트 - 단일 LLM 인스턴스로 전체 서버에서 공유"""
import json
import logging
from typing import Optional, Union

import requests


log = logging.getLogger(__name__)
ThinkType = Optional[Union[bool, str]]


class LLMClient:
    def __init__(self, base_url: str, model: str, default_think: ThinkType = False):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_think = default_think
        self.url = f"{self.base_url}/api/chat"
        self.url_generate = f"{self.base_url}/api/generate"

    def chat(
        self,
        messages: list,
        temperature: float = 0.8,
        max_tokens: int = 256,
        think: ThinkType = None,
    ) -> str:
        """ollama /api/chat 호출. messages는 [{"role": ..., "content": ...}, ...] 형식."""
        try:
            if think is None:
                think = self.default_think

            content, done_reason, thinking = self._chat_once(
                messages,
                temperature,
                max_tokens,
                think=think,
            )

            # 모델이 길이 제한으로 끊긴 경우 한 번 더 크게 재시도
            if content.strip() and done_reason == "length":
                retry_tokens = min(max(max_tokens * 2, 384), 1024)
                retry_think = False if think else think
                log.warning(
                    "Ollama response hit token limit (num_predict=%d). retrying once with %d (think=%s).",
                    max_tokens,
                    retry_tokens,
                    retry_think,
                )
                retry_content, retry_done_reason, retry_thinking = self._chat_once(
                    messages,
                    temperature,
                    retry_tokens,
                    think=retry_think,
                )
                if retry_content.strip():
                    content = retry_content
                    done_reason = retry_done_reason
                    thinking = retry_thinking

            if not content.strip():
                if thinking.strip() and think:
                    # thinking은 생성됐지만 최종 content가 비는 경우, think=false로 1회 재시도
                    retry_tokens = min(max(max_tokens, 384), 1024)
                    log.warning(
                        "Ollama returned empty content (thinking_len=%d). retrying once with think=false.",
                        len(thinking),
                    )
                    retry_content, retry_done_reason, _ = self._chat_once(
                        messages,
                        temperature,
                        retry_tokens,
                        think=False,
                    )
                    if retry_content.strip():
                        log.info(
                            "Ollama empty content recovered via think=false (done_reason=%s, len=%d)",
                            retry_done_reason,
                            len(retry_content.strip()),
                        )
                        return retry_content.strip()

                log.warning("Ollama returned empty content.")
                fallback = self._generate_fallback(messages, temperature, max_tokens)
                if fallback.strip():
                    log.info("Ollama chat empty -> generate fallback ok (len=%d)", len(fallback.strip()))
                    return fallback.strip()
            return content.strip()
        except Exception as exc:
            log.error("Ollama API error: %s", exc)
            return ""

    def _chat_once(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
        think: ThinkType = True,
    ) -> tuple[str, str, str]:
        """
        /api/chat 스트리밍 응답을 조합해 최종 텍스트를 반환.
        Returns:
            (content, done_reason, thinking)
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if think is not None:
            payload["think"] = think

        chunks = []
        thinking_chunks = []
        done_reason = ""

        with requests.post(
            self.url,
            json=payload,
            timeout=(5, 180),
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("Skipping non-JSON Ollama stream chunk: %r", line[:200])
                    continue

                if not isinstance(data, dict):
                    continue
                if data.get("error"):
                    raise RuntimeError(data.get("error"))

                piece = ""
                think_piece = ""
                msg = data.get("message")
                if isinstance(msg, dict):
                    piece = msg.get("content") or ""
                    think_piece = msg.get("thinking") or ""
                elif "response" in data:
                    piece = data.get("response") or ""
                    think_piece = data.get("thinking") or ""

                if piece:
                    chunks.append(piece)
                if think_piece:
                    thinking_chunks.append(think_piece)

                if data.get("done") is True:
                    done_reason = (data.get("done_reason") or "").strip().lower()
                    break

        return "".join(chunks).strip(), done_reason, "".join(thinking_chunks).strip()

    def _generate_fallback(self, messages: list, temperature: float, max_tokens: int) -> str:
        """Fallback to /api/generate when /api/chat returns empty content."""
        try:
            prompt = self._messages_to_prompt(messages)
            resp = requests.post(self.url_generate, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }, timeout=(5, 180))
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

