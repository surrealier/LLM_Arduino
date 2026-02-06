"""
작업 큐 관리 모듈
- STT, TTS, 명령 처리를 위한 큐 시스템
- 큐 오버플로우 시 오래된 항목 자동 제거
"""
import logging
from queue import Queue, Full, Empty
from typing import Any

log = logging.getLogger(__name__)


class JobQueue:
    """작업 큐 관리자 클래스"""
    
    def __init__(self, stt_maxsize: int = 4, tts_maxsize: int = 2, command_maxsize: int = 10):
        # 각 작업 유형별 큐 초기화
        self.stt_queue = Queue(maxsize=stt_maxsize)
        self.tts_queue = Queue(maxsize=tts_maxsize)
        self.command_queue = Queue(maxsize=command_maxsize)

    def put(self, queue: Queue, item: Any, drop_oldest: bool = True) -> bool:
        # 큐에 항목 추가 (큐 가득 찰 경우 처리)
        try:
            queue.put_nowait(item)
            return True
        except Full:
            if not drop_oldest:
                log.warning("Queue full -> rejecting new item")
                return False
            try:
                # 가장 오래된 항목 제거
                queue.get_nowait()
            except Empty:
                return False
            try:
                # 새 항목 추가
                queue.put_nowait(item)
                log.warning("Queue full -> dropped oldest item")
                return True
            except Full:
                log.warning("Queue full -> still full after drop")
                return False