"""
로깅 시스템 설정 모듈
- 컬러 콘솔 출력 및 파일 로깅 설정
- 성능 메트릭 수집 및 통계 출력
"""
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
        # 로그 레벨에 따른 컬러 적용
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


class PerformanceLogger:
    """성능 메트릭 로깅"""

    def __init__(self):
        # 성능 메트릭 초기화
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
        # STT 처리 시간 기록
        self.metrics["stt_requests"] += 1
        self.metrics["stt_total_time"] += duration
        avg = self.metrics["stt_total_time"] / self.metrics["stt_requests"]
        self.log.debug("STT: %.2fs (avg: %.2fs)", duration, avg)

    def log_llm(self, duration: float):
        # LLM 처리 시간 기록
        self.metrics["llm_requests"] += 1
        self.metrics["llm_total_time"] += duration
        avg = self.metrics["llm_total_time"] / self.metrics["llm_requests"]
        self.log.debug("LLM: %.2fs (avg: %.2fs)", duration, avg)

    def log_tts(self, duration: float):
        # TTS 처리 시간 기록
        self.metrics["tts_requests"] += 1
        self.metrics["tts_total_time"] += duration
        avg = self.metrics["tts_total_time"] / self.metrics["tts_requests"]
        self.log.debug("TTS: %.2fs (avg: %.2fs)", duration, avg)

    def log_error(self):
        # 에러 카운트 증가
        self.metrics["errors"] += 1

    def get_stats(self) -> dict:
        # 통계 데이터 계산 및 반환
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
        # 성능 통계 출력
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
    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 로그 포맷 정의
    console_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
    file_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(filename)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(console_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 설정
    if save_to_file:
        # 로그 디렉토리 생성
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")

        # 일반 로그 파일 핸들러
        log_file = log_path / f"app_{today}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(file_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # 에러 전용 로그 파일 핸들러
        error_file = log_path / f"error_{today}.log"
        error_handler = logging.FileHandler(error_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

        logging.getLogger(__name__).info("Logging to: %s", log_file)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Logging initialized (level: %s)", level)


# 전역 성능 로거 인스턴스
performance_logger = PerformanceLogger()


def get_performance_logger() -> PerformanceLogger:
    """성능 로거 인스턴스 반환"""
    return performance_logger