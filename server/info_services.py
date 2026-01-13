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
    
    def __init__(self, weather_api_key: Optional[str] = None, location: str = "Seoul"):
        self.weather_api_key = weather_api_key
        self.location = location
        self.timers = []  # List of active timers
        self.alarms = []  # List of active alarms
        
        # 날씨 캐시 (5분마다 갱신)
        self.weather_cache = None
        self.weather_cache_time = 0
        self.weather_cache_ttl = 300  # 5 minutes
    
    def get_current_time(self) -> str:
        """현재 시각 반환"""
        now = datetime.now()
        time_str = now.strftime("%Y년 %m월 %d일 %H시 %M분")
        weekday = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][now.weekday()]
        return f"현재 시각은 {time_str}, {weekday}입니다."
    
    def get_current_date(self) -> str:
        """현재 날짜 반환"""
        now = datetime.now()
        return now.strftime("%Y년 %m월 %d일")
    
    def get_day_of_week(self) -> str:
        """요일 반환"""
        weekday = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][datetime.now().weekday()]
        return weekday
    
    def get_weather(self) -> str:
        """
        날씨 정보 반환
        OpenWeatherMap API 사용 (무료 tier)
        """
        if not self.weather_api_key:
            return "날씨 정보를 가져오려면 API 키가 필요합니다."
        
        # 캐시 확인
        now = time.time()
        if self.weather_cache and (now - self.weather_cache_time) < self.weather_cache_ttl:
            return self.weather_cache
        
        try:
            import requests
            
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": self.location,
                "appid": self.weather_api_key,
                "units": "metric",
                "lang": "kr"
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            weather_desc = data["weather"][0]["description"]
            
            weather_str = (
                f"{self.location}의 현재 날씨는 {weather_desc}입니다. "
                f"기온은 {temp:.1f}도, 체감온도는 {feels_like:.1f}도이며, "
                f"습도는 {humidity}%입니다."
            )
            
            # 캐시 저장
            self.weather_cache = weather_str
            self.weather_cache_time = now
            
            return weather_str
            
        except ImportError:
            log.warning("requests 라이브러리가 필요합니다: pip install requests")
            return "날씨 정보를 가져올 수 없습니다. (requests 라이브러리 필요)"
        except Exception as e:
            log.error(f"날씨 정보 가져오기 실패: {e}")
            return "날씨 정보를 가져오는 중 오류가 발생했습니다."
    
    def get_news_headlines(self, count: int = 3) -> str:
        """
        뉴스 헤드라인 반환 (RSS 피드)
        """
        try:
            import feedparser
            
            # 네이버 뉴스 RSS (헤드라인)
            feed_url = "https://news.naver.com/main/rss/home.nhn"
            
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                return "뉴스를 가져올 수 없습니다."
            
            headlines = []
            for i, entry in enumerate(feed.entries[:count]):
                title = entry.get('title', '제목 없음')
                headlines.append(f"{i+1}. {title}")
            
            return "최신 뉴스입니다. " + " ".join(headlines)
            
        except ImportError:
            log.warning("feedparser 라이브러리가 필요합니다: pip install feedparser")
            return "뉴스를 가져올 수 없습니다. (feedparser 라이브러리 필요)"
        except Exception as e:
            log.error(f"뉴스 가져오기 실패: {e}")
            return "뉴스를 가져오는 중 오류가 발생했습니다."
    
    def set_timer(self, seconds: int, label: str = "") -> str:
        """
        타이머 설정
        Returns: confirmation message
        """
        timer_id = len(self.timers)
        end_time = time.time() + seconds
        
        timer = {
            "id": timer_id,
            "label": label or f"타이머 {timer_id + 1}",
            "end_time": end_time,
            "duration": seconds
        }
        
        self.timers.append(timer)
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        if minutes > 0:
            time_str = f"{minutes}분 {remaining_seconds}초" if remaining_seconds > 0 else f"{minutes}분"
        else:
            time_str = f"{remaining_seconds}초"
        
        return f"{timer['label']} 타이머를 {time_str} 후로 설정했습니다."
    
    def set_alarm(self, hour: int, minute: int, label: str = "") -> str:
        """
        알람 설정
        Returns: confirmation message
        """
        alarm_id = len(self.alarms)
        
        # 오늘 해당 시간으로 datetime 생성
        now = datetime.now()
        alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 이미 지난 시간이면 내일로 설정
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
        
        return f"{alarm['label']} 알람을 {hour:02d}:{minute:02d}로 설정했습니다."
    
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
    
    def get_active_timers(self) -> str:
        """활성 타이머 목록 반환"""
        if not self.timers:
            return "활성화된 타이머가 없습니다."
        
        now = time.time()
        timer_list = []
        
        for timer in self.timers:
            remaining = int(timer["end_time"] - now)
            minutes = remaining // 60
            seconds = remaining % 60
            
            if minutes > 0:
                time_str = f"{minutes}분 {seconds}초"
            else:
                time_str = f"{seconds}초"
            
            timer_list.append(f"{timer['label']}: {time_str} 남음")
        
        return "활성 타이머: " + ", ".join(timer_list)
    
    def get_active_alarms(self) -> str:
        """활성 알람 목록 반환"""
        if not self.alarms:
            return "설정된 알람이 없습니다."
        
        alarm_list = []
        for alarm in self.alarms:
            alarm_list.append(f"{alarm['label']}: {alarm['hour']:02d}:{alarm['minute']:02d}")
        
        return "설정된 알람: " + ", ".join(alarm_list)
    
    def cancel_all_timers(self) -> str:
        """모든 타이머 취소"""
        count = len(self.timers)
        self.timers = []
        return f"{count}개의 타이머를 취소했습니다." if count > 0 else "취소할 타이머가 없습니다."
    
    def cancel_all_alarms(self) -> str:
        """모든 알람 취소"""
        count = len(self.alarms)
        self.alarms = []
        return f"{count}개의 알람을 취소했습니다." if count > 0 else "취소할 알람이 없습니다."
    
    def process_info_request(self, text: str) -> Optional[str]:
        """
        텍스트에서 정보 요청을 감지하고 처리
        Returns: response string or None if not an info request
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
            return f"오늘은 {self.get_day_of_week()}입니다."
        
        # 날씨 관련
        if any(keyword in text_lower for keyword in ["날씨", "기온", "온도", "비", "눈"]):
            return self.get_weather()
        
        # 뉴스 관련
        if any(keyword in text_lower for keyword in ["뉴스", "뉴스들", "헤드라인"]):
            return self.get_news_headlines()
        
        # 타이머 설정
        if "타이머" in text_lower and ("설정" in text_lower or "맞춰" in text_lower or "켜" in text_lower):
            # 간단한 숫자 추출 (예: "3분 타이머", "30초 타이머")
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
                return "타이머 시간을 말씀해주세요. 예: 3분 타이머"
        
        # 타이머 확인
        if "타이머" in text_lower and any(keyword in text_lower for keyword in ["확인", "남", "얼마"]):
            return self.get_active_timers()
        
        # 타이머 취소
        if "타이머" in text_lower and any(keyword in text_lower for keyword in ["취소", "끄", "중지"]):
            return self.cancel_all_timers()
        
        return None
