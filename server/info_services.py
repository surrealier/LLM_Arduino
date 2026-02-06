# ============================================================
# info_services.py — 정보 서비스 통합 모듈
# ============================================================
# 역할: 사용자의 정보 요청을 감지하고 처리.
#       시간/날짜, 날씨(OpenWeatherMap), 뉴스(RSS),
#       타이머/알람 기능을 제공.
#
# 날씨: 5분 캐시로 API 호출 최소화
# 타이머: 메모리 내 관리, check_timers()로 만료 확인
# 키워드 매칭으로 자연어 요청 감지 (process_info_request)
# ============================================================
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json

log = logging.getLogger("info_services")

class InfoServices:
    """
    정보 서비스 통합 클래스
    - 시간/날짜
    - 날씨 (OpenWeatherMap API)
    - 뉴스 (RSS 피드)
    - 타이머/알람
    """
    
    def __init__(self, weather_api_key: Optional[str] = None, lat: float = 37.5665, lon: float = 126.9780):
        self.weather_api_key = weather_api_key
        self.lat = lat
        self.lon = lon
        self.timers = []  # List of active timers
        self.alarms = []  # List of active alarms
        
        # 날씨 캐시 (5분마다 갱신)
        self.weather_cache = None
        self.weather_cache_time = 0
        self.weather_cache_ttl = 300  # 5 minutes
    
    def get_current_time(self) -> Dict:
        """현재 시각 반환"""
        now = datetime.now()
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        return {
            "type": "time",
            "datetime": now.strftime("%Y-%m-%d %H:%M"),
            "weekday": weekdays[now.weekday()],
        }

    def get_current_date(self) -> Dict:
        """현재 날짜 반환"""
        now = datetime.now()
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        return {
            "type": "date",
            "date": now.strftime("%Y-%m-%d"),
            "weekday": weekdays[now.weekday()],
        }

    def get_day_of_week(self) -> Dict:
        """요일 반환"""
        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        return {"type": "weekday", "weekday": weekdays[datetime.now().weekday()]}
    
    def get_weather(self) -> Optional[Dict]:
        """날씨 정보 반환 (OpenWeatherMap API, lat/lon 사용)"""
        if not self.weather_api_key:
            return None

        now = time.time()
        if self.weather_cache and (now - self.weather_cache_time) < self.weather_cache_ttl:
            return self.weather_cache

        try:
            import requests

            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": self.lat,
                "lon": self.lon,
                "appid": self.weather_api_key,
                "units": "metric",
                "lang": "kr"
            }

            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            result = {
                "type": "weather",
                "city": data.get("name", ""),
                "description": data["weather"][0]["description"],
                "temp": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data.get("wind", {}).get("speed", 0),
            }

            self.weather_cache = result
            self.weather_cache_time = now
            return result

        except Exception as e:
            log.error("날씨 정보 가져오기 실패: %s", e)
            return None
    
    def get_news_headlines(self, count: int = 3) -> Optional[Dict]:
        """뉴스 헤드라인 반환 (RSS 피드)"""
        try:
            import feedparser

            feed = feedparser.parse("https://news.naver.com/main/rss/home.nhn")
            if not feed.entries:
                return None

            headlines = [entry.get("title", "") for entry in feed.entries[:count]]
            return {"type": "news", "headlines": headlines}

        except Exception as e:
            log.error("뉴스 가져오기 실패: %s", e)
            return None
    
    def set_timer(self, seconds: int, label: str = "") -> Dict:
        """타이머 설정"""
        timer_id = len(self.timers)
        end_time = time.time() + seconds

        timer = {
            "id": timer_id,
            "label": label or f"타이머 {timer_id + 1}",
            "end_time": end_time,
            "duration": seconds
        }
        self.timers.append(timer)
        return {"type": "timer_set", "label": timer["label"], "duration_sec": seconds}
    
    def set_alarm(self, hour: int, minute: int, label: str = "") -> Dict:
        """알람 설정"""
        alarm_id = len(self.alarms)
        now = datetime.now()
        alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if alarm_time <= now:
            alarm_time += timedelta(days=1)

        alarm = {
            "id": alarm_id,
            "label": label or f"알람 {alarm_id + 1}",
            "time": alarm_time,
            "hour": hour,
            "minute": minute
        }
        self.alarms.append(alarm)
        return {"type": "alarm_set", "label": alarm["label"], "hour": hour, "minute": minute}
    
    def check_timers(self) -> List[Dict]:
        """
        타이머 확인 및 만료된 타이머 반환
        Returns: list of expired timers
        """
        now = time.time()
        expired = []
        
        for timer in self.timers[:]:
            if now >= timer["end_time"]:
                expired.append(timer)
                self.timers.remove(timer)
        
        return expired
    
    def check_alarms(self) -> List[Dict]:
        """
        알람 확인 및 울려야 할 알람 반환
        Returns: list of alarms to trigger
        """
        now = datetime.now()
        triggered = []
        
        for alarm in self.alarms[:]:
            if now >= alarm["time"]:
                triggered.append(alarm)
                # 알람은 한 번만 울리고 제거
                self.alarms.remove(alarm)
        
        return triggered
    
    def get_active_timers(self) -> Dict:
        """활성 타이머 목록 반환"""
        now = time.time()
        timers = [
            {"label": t["label"], "remaining_sec": int(t["end_time"] - now)}
            for t in self.timers
        ]
        return {"type": "timers", "timers": timers}

    def get_active_alarms(self) -> Dict:
        """활성 알람 목록 반환"""
        alarms = [
            {"label": a["label"], "hour": a["hour"], "minute": a["minute"]}
            for a in self.alarms
        ]
        return {"type": "alarms", "alarms": alarms}

    def cancel_all_timers(self) -> Dict:
        """모든 타이머 취소"""
        count = len(self.timers)
        self.timers = []
        return {"type": "timers_cancelled", "count": count}

    def cancel_all_alarms(self) -> Dict:
        """모든 알람 취소"""
        count = len(self.alarms)
        self.alarms = []
        return {"type": "alarms_cancelled", "count": count}
    
    def process_info_request(self, text: str) -> Optional[Dict]:
        """
        텍스트에서 정보 요청을 감지하고 처리
        Returns: raw data dict or None if not an info request
        """
        text_lower = text.lower()

        # 시간 관련
        if any(keyword in text_lower for keyword in ["시간", "몇 시", "지금"]):
            if "알람" not in text_lower and "타이머" not in text_lower:
                return self.get_current_time()

        # 날짜 관련
        if any(keyword in text_lower for keyword in ["날짜", "며칠", "오늘"]):
            return self.get_current_date()

        # 요일 관련
        if "요일" in text_lower:
            return self.get_day_of_week()

        # 날씨 관련
        if any(keyword in text_lower for keyword in ["날씨", "기온", "온도", "비", "눈"]):
            return self.get_weather()

        # 뉴스 관련
        if any(keyword in text_lower for keyword in ["뉴스", "뉴스들", "헤드라인"]):
            return self.get_news_headlines()

        # 타이머 설정
        if "타이머" in text_lower and ("설정" in text_lower or "맞춰" in text_lower or "켜" in text_lower):
            import re
            minutes = re.search(r'(\d+)\s*분', text_lower)
            seconds = re.search(r'(\d+)\s*초', text_lower)

            total_seconds = 0
            if minutes:
                total_seconds += int(minutes.group(1)) * 60
            if seconds:
                total_seconds += int(seconds.group(1))

            if total_seconds > 0:
                return self.set_timer(total_seconds)
            else:
                return {"type": "timer_error", "message": "시간을 지정해주세요"}

        # 타이머 확인
        if "타이머" in text_lower and any(keyword in text_lower for keyword in ["확인", "남", "얼마"]):
            return self.get_active_timers()

        # 타이머 취소
        if "타이머" in text_lower and any(keyword in text_lower for keyword in ["취소", "끄", "중지"]):
            return self.cancel_all_timers()

        return None
