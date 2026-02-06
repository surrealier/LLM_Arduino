"""
공통 유틸리티 함수 모듈
- 값 범위 제한 및 텍스트 정리 함수
- 음성 인식 결과 후처리를 위한 도구들
"""
import re


def clamp(value: int, lo: int, hi: int) -> int:
    """
    값을 지정된 범위로 제한
    - 최소값과 최대값 사이로 값을 클램핑
    """
    return max(lo, min(hi, value))


def clean_text(text: str) -> str:
    """
    음성 인식 결과 텍스트 정리 함수
    - 반복되는 구두점 제거
    - 과도한 구두점이 포함된 텍스트 필터링
    - 공백 정규화 및 후행 구두점 제거
    """
    t = (text or "").strip()
    
    # 연속된 쉼표 정리 (3개 이상 → 1개)
    t = re.sub(r"[,，]{3,}", ",", t)
    
    # 반복되는 구두점 정리 (2개 이상 → 1개)
    t = re.sub(r"([,，。.!?])\1{1,}", r"\1", t)
    
    # 공백 정규화 (연속 공백 → 단일 공백)
    t = re.sub(r"\s+", " ", t).strip()
    
    # 구두점 비율이 너무 높은 텍스트 필터링 (노이즈 제거)
    if len(t) >= 8:
        punct = sum(ch in ",，。.!?…" for ch in t)
        if punct / max(1, len(t)) > 0.35:  # 구두점이 35% 이상이면 빈 문자열 반환
            return ""
    
    # 후행 쉼표 제거
    t = re.sub(r"[,，]+$", "", t).strip()
    return t