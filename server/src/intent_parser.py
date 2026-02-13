"""의도(intent) 태그 파서 — LLM 응답에서 [INTENT:xxx] 추출"""
import re

_INTENT_RE = re.compile(r"\[INTENT:(\w+)\]")
_VALID_INTENTS = {"none", "sleep", "mode_robot", "mode_agent"}


def parse_intent(text: str) -> tuple[str, str]:
    """LLM 응답에서 intent 태그를 추출하고 본문을 분리한다.

    Returns:
        (intent, clean_text) — intent가 없거나 유효하지 않으면 "none"
    """
    if not text:
        return "none", ""
    m = _INTENT_RE.search(text)
    if m:
        intent = m.group(1).lower()
        clean = (text[:m.start()] + text[m.end():]).strip()
        return intent if intent in _VALID_INTENTS else "none", clean
    return "none", text.strip()
