import re


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def clean_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"[,，]{3,}", ",", t)
    t = re.sub(r"([,，。.!?])\1{1,}", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) >= 8:
        punct = sum(ch in ",，。.!?…" for ch in t)
        if punct / max(1, len(t)) > 0.35:
            return ""
    t = re.sub(r"[,，]+$", "", t).strip()
    return t
