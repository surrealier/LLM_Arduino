"""
입력 게이트 모듈
- 한 턴(STT→LLM→TTS) 처리 중에는 추가 음성 입력을 드롭
- 스트림 START/AUDIO/END 상태를 스레드 안전하게 관리
"""
from __future__ import annotations

import threading


class InputGate:
    """단일 턴 처리 동안 추가 입력을 차단하는 half-duplex 게이트."""

    DECISION_ACCEPT = "accept"
    DECISION_DROP = "drop"
    DECISION_IGNORE = "ignore"

    def __init__(self):
        self._lock = threading.Lock()
        self._busy = False
        self._stream_active = False
        self._drop_stream = False

    def mark_busy(self) -> None:
        with self._lock:
            self._busy = True

    def mark_idle(self) -> None:
        with self._lock:
            self._busy = False

    def is_busy(self) -> bool:
        with self._lock:
            return self._busy

    def start_stream(self) -> bool:
        """
        새 음성 스트림 시작.
        - True: 수집 허용
        - False: 현재 스트림은 드롭 대상으로 전환
        """
        with self._lock:
            if self._busy or self._stream_active:
                self._stream_active = True
                self._drop_stream = True
                return False
            self._stream_active = True
            self._drop_stream = False
            return True

    def can_accept_audio(self) -> bool:
        with self._lock:
            return self._stream_active and not self._drop_stream

    def has_active_stream(self) -> bool:
        with self._lock:
            return self._stream_active

    def end_stream(self) -> str:
        """
        현재 스트림 종료.
        Returns:
        - "accept": 정상 수집된 스트림
        - "drop": busy 상태로 드롭된 스트림
        - "ignore": 활성 스트림 없이 END만 들어온 경우
        """
        with self._lock:
            if not self._stream_active:
                return self.DECISION_IGNORE

            dropped = self._drop_stream
            self._stream_active = False
            self._drop_stream = False
            return self.DECISION_DROP if dropped else self.DECISION_ACCEPT
