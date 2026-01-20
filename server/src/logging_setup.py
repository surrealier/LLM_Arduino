import logging
import sys
from datetime import datetime
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """컬러 출력 포맷터 (콘솔용)"""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "RESET": "\033[0m",
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


class PerformanceLogger:
    """성능 메트릭 로깅"""

    def __init__(self):
        self.metrics = {
            "stt_requests": 0,
            "stt_total_time": 0.0,
            "llm_requests": 0,
            "llm_total_time": 0.0,
            "tts_requests": 0,
            "tts_total_time": 0.0,
            "errors": 0,
        }
        self.log = logging.getLogger("performance")

    def log_stt(self, duration: float):
        self.metrics["stt_requests"] += 1
        self.metrics["stt_total_time"] += duration
        avg = self.metrics["stt_total_time"] / self.metrics["stt_requests"]
        self.log.debug("STT: %.2fs (avg: %.2fs)", duration, avg)

    def log_llm(self, duration: float):
        self.metrics["llm_requests"] += 1
        self.metrics["llm_total_time"] += duration
        avg = self.metrics["llm_total_time"] / self.metrics["llm_requests"]
        self.log.debug("LLM: %.2fs (avg: %.2fs)", duration, avg)

    def log_tts(self, duration: float):
        self.metrics["tts_requests"] += 1
        self.metrics["tts_total_time"] += duration
        avg = self.metrics["tts_total_time"] / self.metrics["tts_requests"]
        self.log.debug("TTS: %.2fs (avg: %.2fs)", duration, avg)

    def log_error(self):
        self.metrics["errors"] += 1

    def get_stats(self) -> dict:
        stats = self.metrics.copy()
        stats["stt_avg"] = (
            stats["stt_total_time"] / stats["stt_requests"]
            if stats["stt_requests"] > 0
            else 0
        )
        stats["llm_avg"] = (
            stats["llm_total_time"] / stats["llm_requests"]
            if stats["llm_requests"] > 0
            else 0
        )
        stats["tts_avg"] = (
            stats["tts_total_time"] / stats["tts_requests"]
            if stats["tts_requests"] > 0
            else 0
        )
        return stats

    def print_stats(self):
        stats = self.get_stats()
        self.log.info("=" * 50)
        self.log.info("Performance Statistics")
        self.log.info("-" * 50)
        self.log.info("STT Requests: %s (avg: %.2fs)", stats["stt_requests"], stats["stt_avg"])
        self.log.info("LLM Requests: %s (avg: %.2fs)", stats["llm_requests"], stats["llm_avg"])
        self.log.info("TTS Requests: %s (avg: %.2fs)", stats["tts_requests"], stats["tts_avg"])
        self.log.info("Errors: %s", stats["errors"])
        self.log.info("=" * 50)


def setup_logging(level: str = "INFO", save_to_file: bool = True, log_dir: str = "logs"):
    """로깅 시스템 초기화"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
    file_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(filename)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(console_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if save_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        log_file = log_path / f"app_{today}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(file_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        error_file = log_path / f"error_{today}.log"
        error_handler = logging.FileHandler(error_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

        logging.getLogger(__name__).info("Logging to: %s", log_file)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging initialized (level: %s)", level)


performance_logger = PerformanceLogger()


def get_performance_logger() -> PerformanceLogger:
    return performance_logger
