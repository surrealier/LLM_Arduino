import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("config_loader")

class Config:
    """
    설정 관리 클래스
    config.yaml과 .env를 읽어서 통합 설정 제공
    환경 변수가 우선순위 높음
    """
    
    DEFAULT_CONFIG = {
        "server": {
            "host": "0.0.0.0",
            "port": 5001
        },
        "stt": {
            "model_size": "small",
            "device": "cuda",
            "language": "ko"
        },
        "llm": {
            "model_name": "Qwen/Qwen2.5-0.5B-Instruct",
            "device": "cuda"
        },
        "tts": {
            "voice": "ko-KR-SunHiNeural"
        },
        "assistant": {
            "name": "아이",
            "personality": "cheerful",
            "proactive": True,
            "proactive_interval": 1800
        },
        "weather": {
            "api_key": "",
            "location": "Seoul"
        },
        "context": {
            "max_history": 20,
            "backup_interval": 10,
            "auto_save": True
        },
        "emotion": {
            "enabled": True,
            "decay_to_neutral": True,
            "decay_interval": 300
        },
        "logging": {
            "level": "INFO",
            "save_to_file": True,
            "log_dir": "logs"
        },
        "connection": {
            "socket_timeout": 0.5
        },
        "queue": {
            "stt_maxsize": 4,
            "tts_maxsize": 2,
            "command_maxsize": 10
        },
        "audio": {
            "max_seconds": 12
        }
    }
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Load from YAML
        self._load_yaml()
        
        # Load from .env
        self._load_env()
        
        log.info("Configuration loaded successfully")
    
    def _load_yaml(self):
        """config.yaml 파일 로드"""
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        self._merge_config(self.config, yaml_config)
                        log.info(f"Loaded config from {self.config_file}")
            else:
                log.warning(f"{self.config_file} not found, using defaults")
        except Exception as e:
            log.error(f"Failed to load {self.config_file}: {e}")
    
    def _load_env(self):
        """환경 변수 로드 (.env 파일 지원)"""
        try:
            # python-dotenv 사용 (있으면)
            try:
                from dotenv import load_dotenv
                load_dotenv()
                log.info("Loaded .env file")
            except ImportError:
                pass
            
            # 환경 변수 오버라이드
            if "WEATHER_API_KEY" in os.environ:
                self.config["weather"]["api_key"] = os.environ["WEATHER_API_KEY"]
            
            if "SERVER_PORT" in os.environ:
                self.config["server"]["port"] = int(os.environ["SERVER_PORT"])
            
            if "DEVICE" in os.environ:
                device = os.environ["DEVICE"]
                self.config["stt"]["device"] = device
                self.config["llm"]["device"] = device
            
            if "ASSISTANT_NAME" in os.environ:
                self.config["assistant"]["name"] = os.environ["ASSISTANT_NAME"]
            
            if "LOG_LEVEL" in os.environ:
                self.config["logging"]["level"] = os.environ["LOG_LEVEL"]
                
        except Exception as e:
            log.error(f"Failed to load environment variables: {e}")
    
    def _merge_config(self, base: Dict, override: Dict):
        """딕셔너리를 재귀적으로 병합"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, *keys, default=None) -> Any:
        """
        중첩된 키로 값 가져오기
        예: config.get("server", "port") -> 5001
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_server_config(self) -> Dict:
        """서버 설정 반환"""
        return self.config.get("server", {})
    
    def get_stt_config(self) -> Dict:
        """STT 설정 반환"""
        return self.config.get("stt", {})
    
    def get_llm_config(self) -> Dict:
        """LLM 설정 반환"""
        return self.config.get("llm", {})
    
    def get_tts_config(self) -> Dict:
        """TTS 설정 반환"""
        return self.config.get("tts", {})
    
    def get_assistant_config(self) -> Dict:
        """어시스턴트 설정 반환"""
        return self.config.get("assistant", {})
    
    def get_weather_config(self) -> Dict:
        """날씨 설정 반환"""
        return self.config.get("weather", {})
    
    def get_context_config(self) -> Dict:
        """컨텍스트 설정 반환"""
        return self.config.get("context", {})
    
    def get_emotion_config(self) -> Dict:
        """감정 설정 반환"""
        return self.config.get("emotion", {})
    
    def get_logging_config(self) -> Dict:
        """로깅 설정 반환"""
        return self.config.get("logging", {})
    
    def save(self, config_file: str = None):
        """현재 설정을 YAML 파일로 저장"""
        file_path = config_file or self.config_file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            log.info(f"Configuration saved to {file_path}")
        except Exception as e:
            log.error(f"Failed to save config to {file_path}: {e}")

# Global config instance
_config = None

def get_config(config_file: str = "config.yaml") -> Config:
    """싱글톤 Config 인스턴스 반환"""
    global _config
    if _config is None:
        _config = Config(config_file)
    return _config
