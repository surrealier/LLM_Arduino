import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import re

log = logging.getLogger("scheduler")

class Scheduler:
    """
    일정 및 리마인더 관리 시스템
    JSON 기반 영구 저장
    """
    
    def __init__(self, schedule_file: str = "schedules.json"):
        self.schedule_file = Path(schedule_file)
        self.schedules = []
        self._load_schedules()
    
    def _load_schedules(self):
        """저장된 일정 불러오기"""
        try:
            if self.schedule_file.exists():
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.schedules = data.get("schedules", [])
                    log.info(f"Loaded {len(self.schedules)} schedules")
            else:
                log.info("No existing schedule file found")
        except Exception as e:
            log.error(f"Failed to load schedules: {e}")
            self.schedules = []
    
    def _save_schedules(self):
        """일정 저장"""
        try:
            data = {
                "schedules": self.schedules,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log.info(f"Saved {len(self.schedules)} schedules")
        except Exception as e:
            log.error(f"Failed to save schedules: {e}")
    
    def add_schedule(self, title: str, date_time: datetime, 
                     description: str = "", reminder_before: int = 0) -> str:
        """
        일정 추가
        Args:
            title: 일정 제목
            date_time: 일정 시간
            description: 설명
            reminder_before: 몇 분 전에 알림 (0 = 알림 없음)
        Returns: confirmation message
        """
        schedule = {
            "id": len(self.schedules) + 1,
            "title": title,
            "datetime": date_time.isoformat(),
            "description": description,
            "reminder_before": reminder_before,
            "created_at": datetime.now().isoformat(),
            "completed": False,
            "reminded": False
        }
        
        self.schedules.append(schedule)
        self._save_schedules()
        
        date_str = date_time.strftime("%Y년 %m월 %d일 %H:%M")
        
        if reminder_before > 0:
            return f"'{title}' 일정을 {date_str}에 등록했습니다. {reminder_before}분 전에 알려드릴게요."
        else:
            return f"'{title}' 일정을 {date_str}에 등록했습니다."
    
    def parse_and_add_schedule(self, text: str) -> Optional[str]:
        """
        자연어에서 일정 추출 및 추가
        예: "내일 오후 3시 회의 있어", "다음주 월요일 10시 병원 가야해"
        """
        # 날짜 키워드
        date_keywords = {
            "오늘": 0,
            "내일": 1,
            "모레": 2,
        }
        
        # 시간 추출 (오전/오후 N시)
        time_pattern = r'(오전|오후)?\s*(\d{1,2})\s*시\s*(\d{1,2}분)?'
        time_match = re.search(time_pattern, text)
        
        # 날짜 추출
        target_date = None
        for keyword, days in date_keywords.items():
            if keyword in text:
                target_date = datetime.now() + timedelta(days=days)
                break
        
        if not target_date:
            # 기본값: 오늘
            target_date = datetime.now()
        
        # 시간 설정
        if time_match:
            period = time_match.group(1)  # 오전/오후
            hour = int(time_match.group(2))
            minute_str = time_match.group(3)
            minute = int(minute_str.replace("분", "")) if minute_str else 0
            
            # 오후면 +12시간
            if period == "오후" and hour < 12:
                hour += 12
            elif period == "오전" and hour == 12:
                hour = 0
            
            target_date = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # 시간 정보 없으면 현재 시간 기준 1시간 후
            target_date = datetime.now() + timedelta(hours=1)
            target_date = target_date.replace(second=0, microsecond=0)
        
        # 과거 시간이면 다음날로
        if target_date < datetime.now():
            target_date += timedelta(days=1)
        
        # 제목 추출 (키워드 제거)
        title = text
        for keyword in ["있어", "있다", "가야해", "가야", "해야", "일정"]:
            title = title.replace(keyword, "")
        title = re.sub(time_pattern, "", title)
        for keyword in date_keywords.keys():
            title = title.replace(keyword, "")
        title = title.strip()
        
        if not title or len(title) < 2:
            title = "새 일정"
        
        # 일정 추가 (10분 전 알림)
        return self.add_schedule(title, target_date, reminder_before=10)
    
    def get_upcoming_schedules(self, hours: int = 24) -> List[Dict]:
        """
        다가오는 일정 조회
        Args:
            hours: 앞으로 몇 시간 이내의 일정을 가져올지
        Returns: 일정 목록
        """
        now = datetime.now()
        end_time = now + timedelta(hours=hours)
        
        upcoming = []
        for schedule in self.schedules:
            if schedule.get("completed"):
                continue
            
            schedule_time = datetime.fromisoformat(schedule["datetime"])
            if now <= schedule_time <= end_time:
                upcoming.append(schedule)
        
        # 시간순 정렬
        upcoming.sort(key=lambda s: s["datetime"])
        return upcoming
    
    def check_reminders(self) -> List[Dict]:
        """
        알림이 필요한 일정 확인
        Returns: 알림이 필요한 일정 목록
        """
        now = datetime.now()
        reminders = []
        
        for schedule in self.schedules:
            if schedule.get("completed") or schedule.get("reminded"):
                continue
            
            schedule_time = datetime.fromisoformat(schedule["datetime"])
            reminder_before = schedule.get("reminder_before", 0)
            
            if reminder_before > 0:
                reminder_time = schedule_time - timedelta(minutes=reminder_before)
                
                if now >= reminder_time and now < schedule_time:
                    reminders.append(schedule)
                    schedule["reminded"] = True
        
        if reminders:
            self._save_schedules()
        
        return reminders
    
    def complete_schedule(self, schedule_id: int) -> str:
        """일정 완료 처리"""
        for schedule in self.schedules:
            if schedule.get("id") == schedule_id:
                schedule["completed"] = True
                self._save_schedules()
                return f"'{schedule['title']}' 일정을 완료했습니다."
        
        return "해당 일정을 찾을 수 없습니다."
    
    def delete_schedule(self, schedule_id: int) -> str:
        """일정 삭제"""
        for i, schedule in enumerate(self.schedules):
            if schedule.get("id") == schedule_id:
                title = schedule["title"]
                self.schedules.pop(i)
                self._save_schedules()
                return f"'{title}' 일정을 삭제했습니다."
        
        return "해당 일정을 찾을 수 없습니다."
    
    def get_today_schedules(self) -> str:
        """오늘의 일정 요약"""
        today = datetime.now().date()
        today_schedules = []
        
        for schedule in self.schedules:
            if schedule.get("completed"):
                continue
            
            schedule_time = datetime.fromisoformat(schedule["datetime"])
            if schedule_time.date() == today:
                today_schedules.append(schedule)
        
        if not today_schedules:
            return "오늘은 예정된 일정이 없습니다."
        
        today_schedules.sort(key=lambda s: s["datetime"])
        
        result = f"오늘의 일정 {len(today_schedules)}개입니다. "
        for schedule in today_schedules:
            time_str = datetime.fromisoformat(schedule["datetime"]).strftime("%H:%M")
            result += f"{time_str} {schedule['title']}, "
        
        return result.rstrip(", ")
    
    def process_schedule_request(self, text: str) -> Optional[str]:
        """
        텍스트에서 일정 요청 감지 및 처리
        Returns: response string or None
        """
        text_lower = text.lower()
        
        # 일정 추가
        if any(keyword in text_lower for keyword in ["일정", "약속", "회의", "병원", "있어", "가야"]):
            if any(keyword in text_lower for keyword in ["오늘", "내일", "모레", "시"]):
                return self.parse_and_add_schedule(text)
        
        # 일정 조회
        if "일정" in text_lower and any(keyword in text_lower for keyword in ["뭐", "무엇", "확인", "알려", "있어"]):
            if "오늘" in text_lower:
                return self.get_today_schedules()
            else:
                schedules = self.get_upcoming_schedules(hours=24*7)  # 7일
                if not schedules:
                    return "예정된 일정이 없습니다."
                
                result = f"다가오는 일정 {len(schedules)}개입니다. "
                for schedule in schedules[:3]:  # 최대 3개만
                    dt = datetime.fromisoformat(schedule["datetime"])
                    time_str = dt.strftime("%m월 %d일 %H:%M")
                    result += f"{time_str} {schedule['title']}, "
                
                return result.rstrip(", ")
        
        return None
