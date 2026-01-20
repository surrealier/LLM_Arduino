import logging
from queue import Queue, Full, Empty
from typing import Any

log = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, stt_maxsize: int = 4, tts_maxsize: int = 2, command_maxsize: int = 10):
        self.stt_queue = Queue(maxsize=stt_maxsize)
        self.tts_queue = Queue(maxsize=tts_maxsize)
        self.command_queue = Queue(maxsize=command_maxsize)

    def put(self, queue: Queue, item: Any, drop_oldest: bool = True) -> bool:
        try:
            queue.put_nowait(item)
            return True
        except Full:
            if not drop_oldest:
                log.warning("Queue full -> rejecting new item")
                return False
            try:
                queue.get_nowait()
            except Empty:
                return False
            try:
                queue.put_nowait(item)
                log.warning("Queue full -> dropped oldest item")
                return True
            except Full:
                log.warning("Queue full -> still full after drop")
                return False
