"""
MemoryManager — 구조화된 .md 파일 기반 메모리 시스템
- Soul.md, User.md, Shortterm_Memory.md, Longterm_Memory.md, Relation.md 관리
- LLM 기반 대화 정보 추출 및 메모리 업데이트
- 자동 refresh (주기적 / idle 감지)
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("memory_manager")

MEMORY_DIR = Path(__file__).parent / "memory"
FILES = {
    "soul": MEMORY_DIR / "Soul.md",
    "user": MEMORY_DIR / "User.md",
    "shortterm": MEMORY_DIR / "Shortterm_Memory.md",
    "longterm": MEMORY_DIR / "Longterm_Memory.md",
    "relation": MEMORY_DIR / "Relation.md",
}

# 메모리 추출용 프롬프트 템플릿
EXTRACT_USER_PROMPT = """아래 대화에서 사용자에 대한 새로운 정보를 추출해줘.
이름, 나이, 직업, 취미, 좋아하는 것, 싫어하는 것, 거주지, 생활 패턴 등.
새로운 정보가 없으면 "없음"이라고만 답해.
정보가 있으면 "- 항목: 내용" 형식으로 한 줄씩 답해.

대화:
{conversation}"""

EXTRACT_RELATION_PROMPT = """아래 대화에서 사용자의 인간관계 정보를 추출해줘.
가족, 친구, 연인, 동료 등 언급된 사람에 대한 정보.
새로운 정보가 없으면 "없음"이라고만 답해.
정보가 있으면 "- 관계(이름): 내용" 형식으로 한 줄씩 답해.

대화:
{conversation}"""

SUMMARIZE_PROMPT = """아래 대화를 한두 문장으로 요약해줘. 핵심 주제와 중요한 내용만.

대화:
{conversation}"""

CONSOLIDATE_PROMPT = """아래 단기 기억들을 정리해서 중요한 것만 남겨줘.
각 항목을 "- [날짜] 내용" 형식으로, 최대 10개.

단기 기억:
{memories}"""


class MemoryManager:
    def __init__(self, refresh_interval=300, refresh_after_turns=5, idle_threshold=120):
        """
        refresh_interval: 자동 refresh 주기 (초, 기본 5분)
        refresh_after_turns: N턴마다 refresh
        idle_threshold: idle 감지 기준 (초, 기본 2분)
        """
        MEMORY_DIR.mkdir(exist_ok=True)

        self.refresh_interval = refresh_interval
        self.refresh_after_turns = refresh_after_turns
        self.idle_threshold = idle_threshold

        # 메모리 캐시
        self.memory = {k: self._read(v) for k, v in FILES.items()}

        # 대화 버퍼 (마지막 refresh 이후 쌓인 대화)
        self.pending_conversations = []
        self.turn_count = 0
        self.last_interaction = time.time()
        self.last_refresh = time.time()

        # LLM 참조 (외부에서 주입)
        self._llm_fn = None

        # 자동 refresh 스레드
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._auto_refresh_loop, daemon=True)
        self._thread.start()

        log.info(f"MemoryManager initialized. Files: {list(FILES.keys())}")

    def set_llm(self, llm_fn):
        """LLM 호출 함수 주입. llm_fn(prompt) -> str"""
        self._llm_fn = llm_fn

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8") if path.exists() else ""
        except Exception as e:
            log.error(f"Failed to read {path}: {e}")
            return ""

    def _write(self, path: Path, content: str):
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to write {path}: {e}")

    # ── 시스템 프롬프트 조합 ──

    def build_system_prompt(self) -> str:
        now = datetime.now()
        time_ctx = now.strftime("%Y년 %m월 %d일 %A %H:%M")

        parts = [
            self.memory["soul"],
            f"\n현재 시각: {time_ctx}\n",
            "---\n# 사용자 정보\n" + self.memory["user"],
            "---\n# 사용자 관계\n" + self.memory["relation"],
            "---\n# 장기 기억\n" + self.memory["longterm"],
            "---\n# 최근 기억\n" + self.memory["shortterm"],
        ]
        return "\n".join(parts)

    # ── 대화 기록 ──

    def add_turn(self, role: str, content: str):
        """대화 턴 추가. role='user' or 'assistant'"""
        self.pending_conversations.append({
            "role": role,
            "content": content,
            "time": datetime.now().strftime("%H:%M")
        })
        if role == "user":
            self.last_interaction = time.time()
            self.turn_count += 1

        # N턴마다 refresh
        if self.turn_count > 0 and self.turn_count % self.refresh_after_turns == 0:
            self.refresh()

    # ── Refresh (메모리 업데이트) ──

    def refresh(self):
        """pending 대화를 분석하여 .md 파일 업데이트"""
        if not self.pending_conversations or not self._llm_fn:
            return

        log.info(f"Memory refresh started. {len(self.pending_conversations)} pending turns.")
        conv_text = self._format_conversations()

        try:
            # 1) 사용자 정보 추출
            user_info = self._llm_fn(EXTRACT_USER_PROMPT.format(conversation=conv_text))
            if user_info and "없음" not in user_info:
                self._update_user_md(user_info)

            # 2) 관계 정보 추출
            relation_info = self._llm_fn(EXTRACT_RELATION_PROMPT.format(conversation=conv_text))
            if relation_info and "없음" not in relation_info:
                self._update_relation_md(relation_info)

            # 3) 대화 요약 → 단기 기억
            summary = self._llm_fn(SUMMARIZE_PROMPT.format(conversation=conv_text))
            if summary:
                self._append_shortterm(summary)

            # 4) 단기 기억이 길어지면 장기로 승격
            self._promote_to_longterm()

        except Exception as e:
            log.error(f"Memory refresh failed: {e}")

        self.pending_conversations = []
        self.last_refresh = time.time()
        log.info("Memory refresh completed.")

    def _format_conversations(self) -> str:
        lines = []
        for turn in self.pending_conversations:
            prefix = "사용자" if turn["role"] == "user" else "콜리"
            lines.append(f"[{turn['time']}] {prefix}: {turn['content']}")
        return "\n".join(lines)

    def _update_user_md(self, new_info: str):
        """User.md에 새 정보 반영 — 기존 내용에 추가/갱신"""
        current = self.memory["user"]
        # 새 정보 라인을 파싱하여 기존 md에 병합
        for line in new_info.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("-"):
                continue
            # "- 항목: 내용" 형식에서 항목 추출
            if ":" in line:
                key = line.split(":")[0].replace("-", "").strip()
                # 기존에 "(아직 모름)" 패턴이 있으면 교체
                for placeholder in ["(아직 모름)", "(아직 파악된 내용 없음)"]:
                    # 해당 섹션 근처의 placeholder를 교체
                    if placeholder in current:
                        current = current.replace(placeholder, line.lstrip("- ").strip(), 1)
                        break
                else:
                    # placeholder가 없으면 관련 섹션 끝에 추가
                    if line not in current:
                        current += f"\n{line}"

        self.memory["user"] = current
        self._write(FILES["user"], current)
        log.info("User.md updated.")

    def _update_relation_md(self, new_info: str):
        """Relation.md에 새 관계 정보 추가"""
        current = self.memory["relation"]
        for line in new_info.strip().split("\n"):
            line = line.strip()
            if line and line.startswith("-") and line not in current:
                # placeholder 교체
                for placeholder in ["(아직 파악된 내용 없음)"]:
                    if placeholder in current:
                        current = current.replace(placeholder, line.lstrip("- ").strip(), 1)
                        break
                else:
                    current += f"\n{line}"

        self.memory["relation"] = current
        self._write(FILES["relation"], current)
        log.info("Relation.md updated.")

    def _append_shortterm(self, summary: str):
        """단기 기억에 요약 추가"""
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{date_str}] {summary.strip()}"

        current = self.memory["shortterm"]
        # 초기 placeholder 제거
        current = current.replace("(아직 대화 기록 없음)", "")
        current = current.replace("(없음)", "")
        current = current.replace("(아직 파악 안 됨)", "")

        # "## 최근 대화 요약" 섹션에 추가
        if "## 최근 대화 요약" in current:
            current = current.replace(
                "## 최근 대화 요약",
                f"## 최근 대화 요약\n{entry}",
                1
            )
        else:
            current += f"\n{entry}"

        self.memory["shortterm"] = current
        self._write(FILES["shortterm"], current)

    def _promote_to_longterm(self):
        """단기 기억이 20개 이상이면 오래된 것을 장기로 이동"""
        shortterm = self.memory["shortterm"]
        lines = [l for l in shortterm.split("\n") if l.strip().startswith("- [")]

        if len(lines) <= 15:
            return

        # 오래된 항목들을 장기로 이동
        to_promote = lines[:-10]  # 최근 10개만 단기에 남김
        remaining = lines[-10:]

        # 장기 기억에 추가
        longterm = self.memory["longterm"]
        longterm = longterm.replace("(아직 축적된 기억 없음)", "")
        if "## 주요 대화 기록" in longterm:
            promote_text = "\n".join(to_promote)
            longterm = longterm.replace(
                "## 주요 대화 기록",
                f"## 주요 대화 기록\n{promote_text}",
                1
            )
        self.memory["longterm"] = longterm
        self._write(FILES["longterm"], longterm)

        # 단기 기억 정리
        header = shortterm.split("## 최근 대화 요약")[0] + "## 최근 대화 요약\n"
        rest_sections = ""
        parts = shortterm.split("## 현재 진행 중인 주제")
        if len(parts) > 1:
            rest_sections = "\n## 현재 진행 중인 주제" + parts[1]

        self.memory["shortterm"] = header + "\n".join(remaining) + rest_sections
        self._write(FILES["shortterm"], self.memory["shortterm"])
        log.info(f"Promoted {len(to_promote)} memories to longterm.")

    # ── 자동 Refresh 루프 ──

    def _auto_refresh_loop(self):
        """백그라운드 스레드: idle 감지 및 주기적 refresh"""
        while not self._stop_event.is_set():
            time.sleep(10)  # 10초마다 체크

            now = time.time()
            idle_time = now - self.last_interaction
            since_refresh = now - self.last_refresh

            # idle 상태이고 pending이 있으면 refresh
            if idle_time >= self.idle_threshold and self.pending_conversations:
                log.info(f"Idle detected ({idle_time:.0f}s). Auto-refreshing memory.")
                self.refresh()
            # 주기적 refresh
            elif since_refresh >= self.refresh_interval and self.pending_conversations:
                log.info(f"Periodic refresh ({since_refresh:.0f}s elapsed).")
                self.refresh()

    # ── 수동 리로드 ──

    def reload(self):
        """디스크에서 모든 .md 파일 다시 읽기"""
        self.memory = {k: self._read(v) for k, v in FILES.items()}
        log.info("All memory files reloaded from disk.")

    def shutdown(self):
        """종료 시 pending 대화 flush"""
        if self.pending_conversations:
            self.refresh()
        self._stop_event.set()
        log.info("MemoryManager shut down.")
