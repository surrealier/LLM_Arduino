import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

class ColoredFormatter(logging.Formatter):
    """컬러 출력 포맷터 (콘솔용)"""
    
    # ANSI 색상 코드
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        # 레벨에 따라 색상 추가
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
            "errors": 0
        }
        self.log = logging.getLogger("performance")
    
    def log_stt(self, duration: float):
        """STT 성능 로깅"""
        self.metrics["stt_requests"] += 1
        self.metrics["stt_total_time"] += duration
        avg = self.metrics["stt_total_time"] / self.metrics["stt_requests"]
        self.log.debug(f"STT: {duration:.2f}s (avg: {avg:.2f}s)")
    
    def log_llm(self, duration: float):
        """LLM 성능 로깅"""
        self.metrics["llm_requests"] += 1
        self.metrics["llm_total_time"] += duration
        avg = self.metrics["llm_total_time"] / self.metrics["llm_requests"]
        self.log.debug(f"LLM: {duration:.2f}s (avg: {avg:.2f}s)")
    
    def log_tts(self, duration: float):
        """TTS 성능 로깅"""
        self.metrics["tts_requests"] += 1
        self.metrics["tts_total_time"] += duration
        avg = self.metrics["tts_total_time"] / self.metrics["tts_requests"]
        self.log.debug(f"TTS: {duration:.2f}s (avg: {avg:.2f}s)")
    
    def log_error(self):
        """에러 카운트"""
        self.metrics["errors"] += 1
    
    def get_stats(self) -> dict:
        """통계 반환"""
        stats = self.metrics.copy()
        
        # 평균 계산
        if stats["stt_requests"] > 0:
            stats["stt_avg"] = stats["stt_total_time"] / stats["stt_requests"]
        else:
            stats["stt_avg"] = 0
        
        if stats["llm_requests"] > 0:
            stats["llm_avg"] = stats["llm_total_time"] / stats["llm_requests"]
        else:
            stats["llm_avg"] = 0
        
        if stats["tts_requests"] > 0:
            stats["tts_avg"] = stats["tts_total_time"] / stats["tts_requests"]
        else:
            stats["tts_avg"] = 0
        
        return stats
    
    def print_stats(self):
        """통계 출력"""
        stats = self.get_stats()
        self.log.info("=" * 50)
        self.log.info("Performance Statistics")
        self.log.info("-" * 50)
        self.log.info(f"STT Requests: {stats['stt_requests']} (avg: {stats['stt_avg']:.2f}s)")
        self.log.info(f"LLM Requests: {stats['llm_requests']} (avg: {stats['llm_avg']:.2f}s)")
        self.log.info(f"TTS Requests: {stats['tts_requests']} (avg: {stats['tts_avg']:.2f}s)")
        self.log.info(f"Errors: {stats['errors']}")
        self.log.info("=" * 50)

def setup_logging(level: str = "INFO", save_to_file: bool = True, log_dir: str = "logs"):
    """
    로깅 시스템 초기화
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        save_to_file: 파일 저장 여부
        log_dir: 로그 디렉토리
    """
    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 포맷 설정
    console_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
    file_format = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(filename)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 콘솔 핸들러 (컬러 출력)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(console_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러
    if save_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # 일반 로그 (모든 레벨)
        today = datetime.now().strftime("%Y%m%d")
        log_file = log_path / f"app_{today}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(file_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # 에러 로그 (ERROR 이상만)
        error_file = log_path / f"error_{today}.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        logging.info(f"📝 Logging to: {log_file}")
    
    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    
    logging.info(f"✅ Logging initialized (level: {level})")

# 전역 성능 로거
performance_logger = PerformanceLogger()

def get_performance_logger() -> PerformanceLogger:
    """성능 로거 인스턴스 반환"""
    return performance_logger
