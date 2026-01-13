import logging
import random
from typing import Dict, Tuple

log = logging.getLogger("emotion_system")

class EmotionSystem:
    """
    감정 상태 시스템
    대화 내용을 분석하여 감정 상태를 결정하고, 
    적절한 LED 색상과 서보 동작을 반환합니다.
    """
    
    EMOTIONS = ["happy", "sad", "excited", "sleepy", "angry", "neutral"]
    
    # 감정별 LED 색상 (RGB 0-255)
    EMOTION_COLORS = {
        "happy": (255, 200, 0),      # 밝은 노란색
        "sad": (0, 100, 255),        # 파란색
        "excited": (255, 50, 200),   # 핑크/마젠타
        "sleepy": (100, 100, 150),   # 은은한 보라
        "angry": (255, 0, 0),        # 빨간색
        "neutral": (100, 255, 100),  # 연두색
    }
    
    # 감정별 LED 패턴 (pattern_type, speed)
    EMOTION_PATTERNS = {
        "happy": ("pulse", "medium"),       # 부드러운 펄스
        "sad": ("slow_fade", "slow"),       # 천천히 페이드
        "excited": ("rainbow", "fast"),     # 빠른 무지개
        "sleepy": ("breathing", "slow"),    # 느린 호흡
        "angry": ("blink", "fast"),         # 빠른 깜빡임
        "neutral": ("solid", "none"),       # 고정
    }
    
    # 감정별 서보 동작
    EMOTION_SERVO_ACTIONS = {
        "happy": "NOD",           # 끄덕이기
        "sad": "SHAKE_SLOW",      # 천천히 좌우
        "excited": "WIGGLE_FAST", # 빠르게 흔들기
        "sleepy": "DRIFT",        # 천천히 내려가기
        "angry": "SHAKE_SHARP",   # 빠르게 좌우
        "neutral": "CENTER",      # 중앙
    }
    
    # 감정 키워드
    EMOTION_KEYWORDS = {
        "happy": ["행복", "기쁘", "좋아", "웃", "즐거", "신나", "재밌", "굿", "최고", "좋다"],
        "sad": ["슬프", "우울", "힘들", "아프", "외로", "쓸쓸", "답답", "안타깝", "아쉽"],
        "excited": ["와", "대박", "짱", "신난다", "흥분", "놀라", "멋지", "환상", "완전"],
        "sleepy": ["피곤", "졸려", "자고", "잠", "쉬고", "휴식", "지쳐"],
        "angry": ["화", "짜증", "싫", "귀찮", "답답", "속상", "빡", "열받"],
        "neutral": []  # 기본값
    }
    
    def __init__(self):
        self.current_emotion = "neutral"
        self.emotion_history = []  # 최근 감정 기록
        self.max_history = 10
    
    def analyze_emotion(self, text: str) -> str:
        """
        텍스트에서 감정을 분석
        Returns: emotion string
        """
        if not text:
            return self.current_emotion
        
        text_lower = text.lower()
        
        # 각 감정별로 키워드 매칭 점수 계산
        scores = {emotion: 0 for emotion in self.EMOTIONS}
        
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[emotion] += 1
        
        # 가장 높은 점수의 감정 선택
        max_score = max(scores.values())
        if max_score > 0:
            detected_emotion = max(scores, key=scores.get)
            self._update_emotion(detected_emotion)
            log.info(f"Emotion detected: {detected_emotion} (from text: {text[:30]}...)")
            return detected_emotion
        
        # 키워드 없으면 현재 감정 유지 (점진적 변화)
        return self.current_emotion
    
    def _update_emotion(self, new_emotion: str):
        """감정 상태 업데이트"""
        if new_emotion != self.current_emotion:
            self.emotion_history.append(self.current_emotion)
            if len(self.emotion_history) > self.max_history:
                self.emotion_history.pop(0)
            self.current_emotion = new_emotion
    
    def get_led_color(self, emotion: str = None) -> Tuple[int, int, int]:
        """감정에 해당하는 LED RGB 색상 반환"""
        emotion = emotion or self.current_emotion
        return self.EMOTION_COLORS.get(emotion, self.EMOTION_COLORS["neutral"])
    
    def get_led_pattern(self, emotion: str = None) -> Dict:
        """감정에 해당하는 LED 패턴 정보 반환"""
        emotion = emotion or self.current_emotion
        pattern, speed = self.EMOTION_PATTERNS.get(emotion, self.EMOTION_PATTERNS["neutral"])
        
        rgb = self.get_led_color(emotion)
        
        return {
            "pattern": pattern,
            "speed": speed,
            "color": {"r": rgb[0], "g": rgb[1], "b": rgb[2]}
        }
    
    def get_servo_action(self, emotion: str = None) -> str:
        """감정에 해당하는 서보 동작 반환"""
        emotion = emotion or self.current_emotion
        return self.EMOTION_SERVO_ACTIONS.get(emotion, "CENTER")
    
    def get_emotion_command(self, emotion: str = None) -> Dict:
        """
        ESP32로 전송할 감정 표현 명령 생성
        Returns: JSON command dict
        """
        emotion = emotion or self.current_emotion
        
        led_pattern = self.get_led_pattern(emotion)
        servo_action = self.get_servo_action(emotion)
        
        return {
            "action": "EMOTION",
            "emotion": emotion,
            "led": led_pattern,
            "servo_action": servo_action
        }
    
    def set_emotion(self, emotion: str):
        """감정을 수동으로 설정"""
        if emotion in self.EMOTIONS:
            self._update_emotion(emotion)
            log.info(f"Emotion manually set to: {emotion}")
        else:
            log.warning(f"Invalid emotion: {emotion}")
    
    def get_random_emotion(self, exclude_current: bool = True) -> str:
        """랜덤 감정 반환 (프로액티브 상호작용용)"""
        emotions = self.EMOTIONS.copy()
        if exclude_current and self.current_emotion in emotions:
            emotions.remove(self.current_emotion)
        return random.choice(emotions)
    
    def decay_to_neutral(self, probability: float = 0.1):
        """
        시간이 지나면 점진적으로 neutral로 회귀
        probability: neutral로 변경될 확률 (0.0-1.0)
        """
        if self.current_emotion != "neutral" and random.random() < probability:
            self._update_emotion("neutral")
            log.info("Emotion decayed to neutral")
            return True
        return False
