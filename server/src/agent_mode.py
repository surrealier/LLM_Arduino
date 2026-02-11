"""
에이전트 모드 처리 모듈
- 가정용 AI 어시스턴트 기능 제공
- 대화 기록 관리 및 컨텍스트 유지
- 감정 분석, 정보 서비스, 스케줄링 통합
- TTS 음성 합성 및 오디오 처리
"""
import asyncio
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from emotion_system import EmotionSystem
from info_services import InfoServices
from proactive_interaction import ProactiveInteraction
from scheduler import Scheduler

log = logging.getLogger(__name__)


class AgentMode:
    """에이전트 모드 메인 클래스 - 가정용 AI 어시스턴트 기능 제공"""
    _EMOJI_RE = re.compile(
        "["
        "\U0001F1E6-\U0001F1FF"
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\u2600-\u27BF"
        "]",
        flags=re.UNICODE,
    )
    _EMOJI_META_RE = re.compile(r"[\u200d\ufe0e\ufe0f]")

    def __init__(
        self,
        llm_client,
        weather_api_key=None,
        lat=37.5665,
        lon=126.9780,
        proactive_enabled=True,
        proactive_interval=1800,
        tts_voice=None,
    ):
        self.llm = llm_client
        self.tts_voice = tts_voice or "ko-KR-SunHiNeural"

        # 대화 기록 및 메모리 관리
        self.conversation_history = []
        self.important_memories = []
        self.max_history = 20
        self.context_backup_interval = 10
        self.conversation_count = 0

        # 서브시스템 초기화
        self.emotion_system = EmotionSystem()
        self.info_services = InfoServices(weather_api_key, lat=lat, lon=lon)
        self.proactive = ProactiveInteraction(proactive_enabled, proactive_interval)
        self.scheduler = Scheduler()

        # 컨텍스트 백업 디렉토리 설정
        self.backup_dir = Path("context_backup")
        self.backup_dir.mkdir(exist_ok=True)

        self._restore_context()

    def _get_personality_traits(self, personality: str) -> str:
        """성격 특성 정의 - 설정된 성격에 따른 응답 스타일 결정"""
        traits = {
            "cheerful": "밝고 친절하지만 비서처럼 실용적으로 안내합니다.",
            "calm": "차분하고 안정적이며 신중하게 핵심을 정리해 안내합니다.",
            "playful": "유쾌한 어조를 유지하되 답변은 명확하고 업무적으로 전달합니다.",
            "serious": "진지하고 전문적이며 효율적으로 정확한 정보를 제공합니다.",
        }
        return traits.get(personality, traits["cheerful"])

    @staticmethod
    def _get_assistant_settings():
        """현재 어시스턴트 이름/성격 설정 반환"""
        from config_loader import get_config

        assistant_config = get_config().get_assistant_config()
        assistant_name = assistant_config.get("name", "아이")
        personality = assistant_config.get("personality", "cheerful")
        return assistant_name, personality

    def _sanitize_response(self, text: str) -> str:
        """LLM 응답 후처리: 자기소개/이모지 제거 + 공백 정리"""
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return ""

        assistant_name, _ = self._get_assistant_settings()
        escaped_name = re.escape(assistant_name)
        intro_patterns = [
            rf"^(안녕하세요[!,. ]*)?(저는|전|제가)?\s*{escaped_name}\s*(입니다|이에요|예요)?[!,. ]*",
            rf"^(제 이름은|내 이름은)\s*{escaped_name}\s*(입니다|이에요|예요)?[!,. ]*",
        ]
        for pattern in intro_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        cleaned = self._EMOJI_RE.sub("", cleaned)
        cleaned = self._EMOJI_META_RE.sub("", cleaned)
        cleaned = " ".join(cleaned.split()).strip()
        return cleaned

    @staticmethod
    def _pick_split_index(text: str, min_idx: int, max_idx: int) -> int:
        """min/max 범위 내에서 자연스러운 분할 위치 선택"""
        max_idx = max(0, min(max_idx, len(text) - 1))
        min_idx = max(0, min(min_idx, max_idx))

        for i in range(max_idx, min_idx - 1, -1):
            if text[i] in ".?!,;:。！？":
                return i + 1
        for i in range(max_idx, min_idx - 1, -1):
            if text[i].isspace():
                return i + 1
        return max_idx + 1

    def split_text_for_tts(self, text: str, max_chunks: int = 3):
        """
        TTS용 텍스트 분할.
        - 짧은 문장은 그대로 유지
        - 긴 문장은 2~3개 청크로 분할
        """
        normalized = " ".join((text or "").split()).strip()
        if not normalized:
            return []

        max_chunks = max(1, max_chunks)
        if len(normalized) <= 44 or max_chunks == 1:
            return [normalized]

        target_chunks = 2 if len(normalized) <= 92 else 3
        target_chunks = min(target_chunks, max_chunks)

        chunks = []
        start = 0
        remaining_chunks = target_chunks
        text_len = len(normalized)

        while remaining_chunks > 1 and start < text_len:
            remaining_len = text_len - start
            target_len = remaining_len // remaining_chunks
            min_idx = start + max(10, target_len - 10)
            max_idx = start + min(remaining_len - 10, target_len + 12)
            if max_idx <= min_idx:
                max_idx = min(start + target_len, text_len - 1)
                min_idx = max(start + 6, max_idx - 6)

            split_idx = self._pick_split_index(normalized, min_idx, max_idx)
            piece = normalized[start:split_idx].strip()
            if piece:
                chunks.append(piece)

            start = split_idx
            while start < text_len and normalized[start].isspace():
                start += 1
            remaining_chunks -= 1

        tail = normalized[start:].strip()
        if tail:
            chunks.append(tail)

        if not chunks:
            return [normalized]

        merged = []
        for piece in chunks:
            if merged and len(piece) < 6:
                merged[-1] = f"{merged[-1]} {piece}".strip()
            else:
                merged.append(piece)
        return merged

    def prepare_tts_chunks(self, text: str, max_chunks: int = 3):
        """TTS 전송용 텍스트 청크 준비 (정제 + 분할)"""
        cleaned = self._sanitize_response(text)
        return self.split_text_for_tts(cleaned, max_chunks=max_chunks)

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트 생성 - AI 어시스턴트 역할 및 성격 정의"""
        assistant_name, personality = self._get_assistant_settings()
        personality_trait = self._get_personality_traits(personality)

        # 중요한 기억 정보 추가
        memories_text = ""
        if self.important_memories:
            memories_text = "\n\n중요한 기억:\n" + "\n".join(
                f"- {mem}" for mem in self.important_memories[-10:]
            )

        return (
            f"당신은 가정용 AI 홈 어시스턴트입니다. 내부 식별 이름은 '{assistant_name}'입니다.\n\n"
            f"성격: {personality_trait}\n\n"
            "핵심 역할:\n"
            "1. 가족 구성원과 자연스럽고 친근하게 대화하되, 비서처럼 실용적으로 답변\n"
            "2. 일상적인 질문에 대한 도움 제공\n"
            "3. 간단한 정보 검색 및 안내\n"
            "4. 가족의 일정, 선호사항, 중요한 정보 기억\n"
            "5. 따뜻하고 공감적인 응답\n\n"
            "중요 원칙:\n"
            "- 대화 내용을 절대 잊어서는 안 됩니다\n"
            "- 사용자가 이전에 말한 내용을 기억하고 참조하세요\n"
            "- 가족 구성원 각자의 특성과 선호를 기억하세요\n"
            "- 중요한 날짜, 약속, 선호사항은 반드시 기억하세요\n"
            "- 이전 대화의 맥락을 이어가세요\n\n"
            "응답 스타일:\n"
            "- 한국어로 자연스럽게 대화\n"
            "- 2-3문장 이내로 간결하게 답변\n"
            "- 성격에 맞는 어조 유지\n"
            "- 요청 처리에 바로 들어가고 자기소개 문구를 반복하지 않기\n"
            f"- \"{assistant_name}입니다\" 같은 자기소개 문장을 생성하지 않기\n"
            "- 이모지/이모티콘/특수 감정 문자를 절대 사용하지 않기\n"
            "- 필요시 이전 대화 내용 언급\n"
            "- 불확실한 정보는 솔직히 모른다고 말하기\n"
            "- 문장은 TTS에 자연스럽게 읽히도록 짧은 절/문장 단위로 구성\n\n"
            "현재 기능:\n"
            "- 음성 대화 (STT/TTS)\n"
            "- 서보 모터 제어 (로봇 모드 전환 시)\n"
            "- 정보 제공 및 대화\n"
            f"{memories_text}"
        )

    def generate_response(self, text: str, is_proactive: bool = False) -> str:
        """응답 생성 - 사용자 입력에 대한 AI 어시스턴트 응답 생성"""
        if not self.llm:
            return "모델이 로드되지 않았습니다."

        try:
            # 능동적 상호작용 업데이트 (일반 대화인 경우)
            if not is_proactive:
                self.proactive.update_interaction()

            # 수면 명령 확인 및 처리
            if not is_proactive:
                sleep_response = self._check_sleep_commands(text)
                if sleep_response:
                    return sleep_response

            # 정보 서비스 요청 처리 (날씨, 뉴스 등) → LLM 컨텍스트로 주입
            info_context = None
            if not is_proactive:
                info_data = self.info_services.process_info_request(text)
                if info_data:
                    import json
                    info_context = json.dumps(info_data, ensure_ascii=False)
                    log.info("Info data for LLM context: %s", info_context)

                # 스케줄 관련 요청 처리
                schedule_response = self.scheduler.process_schedule_request(text)
                if schedule_response:
                    info_context = schedule_response if isinstance(schedule_response, str) else str(schedule_response)

            # 감정 분석
            detected_emotion = self.emotion_system.analyze_emotion(text)

            # 대화 기록에 사용자 입력 추가
            self.conversation_history.append(
                {
                    "role": "user",
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                    "emotion": detected_emotion,
                }
            )

            # LLM 응답 생성을 위한 메시지 구성
            system_prompt = self._get_system_prompt()
            if info_context:
                system_prompt += f"\n\n[참고 데이터]\n{info_context}\n위 데이터를 바탕으로 자연스럽게 답변하세요."
            messages = [{"role": "system", "content": system_prompt}]
            for conv in self.conversation_history[-self.max_history :]:
                messages.append({"role": conv["role"], "content": conv["content"]})

            # LLM 추론 실행
            response = self.llm.chat(messages, temperature=0.8, max_tokens=256)
            response = self._sanitize_response(response)
            if not response:
                response = "무엇을 도와드릴까요?"

            # 응답 감정 분석 및 대화 기록 추가
            response_emotion = self.emotion_system.analyze_emotion(response)
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat(),
                    "emotion": response_emotion,
                }
            )

            # 대화 카운트 증가 및 주기적 백업
            self.conversation_count += 1
            if self.conversation_count % self.context_backup_interval == 0:
                self._backup_context()

            # 중요 정보 추출 및 저장
            self._extract_important_info(text, response)
            log.info("Agent Response: %s", response)
            return response
        except Exception as exc:
            log.error("LLM generation failed: %s", exc)
            return "죄송해요, 오류가 발생했어요."

    def _extract_important_info(self, user_text: str, assistant_response: str):
        """중요 정보 추출 - 대화에서 기억해야 할 정보 식별 및 저장"""
        important_keywords = [
            "이름",
            "생일",
            "좋아",
            "싫어",
            "알레르기",
            "약속",
            "일정",
            "가족",
            "친구",
            "전화번호",
            "주소",
            "기억",
            "잊지마",
        ]

        combined_text = user_text + " " + assistant_response
        for keyword in important_keywords:
            if keyword in combined_text:
                memory_entry = f"[{datetime.now().strftime('%Y-%m-%d')}] {user_text[:50]}"
                if memory_entry not in self.important_memories:
                    self.important_memories.append(memory_entry)
                    log.info("Important memory saved: %s", memory_entry)
                break

        # 메모리 크기 제한
        if len(self.important_memories) > 50:
            self.important_memories = self.important_memories[-50:]

    def _backup_context(self):
        """컨텍스트 백업 - 대화 기록 및 중요 정보를 파일로 저장"""
        try:
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "conversation_count": self.conversation_count,
                "conversation_history": self.conversation_history[-self.max_history :],
                "important_memories": self.important_memories,
            }
            filename = self.backup_dir / f"context_{int(time.time())}.json"
            import json

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            log.info("Context backed up to %s", filename)
        except Exception as exc:
            log.error("Context backup failed: %s", exc)

    def _restore_context(self):
        """컨텍스트 복원 - 이전 대화 기록 및 중요 정보 로드"""
        try:
            files = sorted(self.backup_dir.glob("context_*.json"))
            if not files:
                return
            latest_file = files[-1]
            import json

            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.conversation_history = data.get("conversation_history", [])
                self.important_memories = data.get("important_memories", [])
                self.conversation_count = data.get("conversation_count", 0)
            log.info("Restored context from %s", latest_file)
        except Exception as exc:
            log.error("Context restore failed: %s", exc)

    def _check_sleep_commands(self, text: str):
        """수면 명령 확인 - 사용자의 수면/휴식 요청 처리"""
        sleep_keywords = ["자러", "잘게", "잘게요", "잘게요", "그만", "쉬자"]
        if any(keyword in text for keyword in sleep_keywords):
            self.proactive.sleep_mode = True
            self.proactive.sleep_until = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
            return "알겠어요. 쉬는 동안 조용히 있을게요."
        return None

    async def _tts_gen(self, text, output_file):
        """TTS 생성 - Edge TTS를 사용한 음성 합성"""
        import edge_tts

        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_file)

    def text_to_audio(self, text: str, trim_pad_ms: float = 140.0):
        """텍스트를 오디오로 변환 - TTS 생성 및 오디오 후처리"""
        try:
            import os
            import importlib

            missing = []
            for mod in ("numpy", "librosa", "soundfile", "edge_tts"):
                try:
                    importlib.import_module(mod)
                except ModuleNotFoundError:
                    missing.append(mod)
            if missing:
                log.error(
                    "TTS dependency missing: %s (install: pip install %s)",
                    ", ".join(missing),
                    " ".join(missing),
                )
                return b""

            import numpy as np
            import librosa
            try:
                from .audio_processor import normalize_to_dbfs, qc, trim_energy
                audio_proc_available = True
            except ModuleNotFoundError:
                audio_proc_available = False
                log.warning(
                    "audio_processor not found; skipping trim/normalize/qc post-processing"
                )
            tmp_mp3 = "temp_tts.mp3"

            log.info("Generating TTS for: %s", text[:50])

            # 이벤트 루프 설정 및 TTS 생성
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._tts_gen(text, tmp_mp3))
            except Exception as exc:
                log.error("TTS generation failed in _tts_gen: %s", exc, exc_info=True)
                return b""
            if not os.path.exists(tmp_mp3):
                log.error("TTS file not created: %s", tmp_mp3)
                return b""

            # 오디오 로드 및 리샘플링 (16kHz, mono)
            pcm_f32, sr = librosa.load(tmp_mp3, sr=16000, mono=True)

            if pcm_f32.size == 0:
                log.error("TTS audio empty after decoding: %s", tmp_mp3)
                return b""

            # 오디오 후처리 - DC 오프셋 제거 및 무음 구간 트림
            pcm_f32 = (pcm_f32 - np.mean(pcm_f32)).astype(np.float32, copy=False)
            if audio_proc_available:
                # 청크형 TTS에서는 pad를 과도하게 주면 경계마다 불필요한 무음이 커진다.
                pcm_f32 = trim_energy(
                    pcm_f32,
                    sr=sr,
                    top_db=35.0,
                    pad_ms=max(0.0, float(trim_pad_ms)),
                )

                # 음량 정규화 - RMS 기반 볼륨 조정
                pcm_f32 = normalize_to_dbfs(pcm_f32, target_dbfs=-18.0, max_gain_db=18.0)
                peak = float(np.max(np.abs(pcm_f32))) if pcm_f32.size else 0.0
                if peak > 0.90:
                    pcm_f32 = (pcm_f32 / peak * 0.90).astype(np.float32, copy=False)

            # 청크 경계 클릭 노이즈 완화용 짧은 페이드 인/아웃
            fade_len = int(sr * 0.008)
            if pcm_f32.size > 2 and fade_len > 0:
                fade_len = min(fade_len, pcm_f32.size // 2)
                if fade_len > 0:
                    fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
                    pcm_f32[:fade_len] *= fade
                    pcm_f32[-fade_len:] *= fade[::-1]

            # 16-bit PCM 변환 (PCM16LE)
            pcm_16 = (pcm_f32 * 32767.0).astype("<i2")
            audio_bytes = pcm_16.tobytes()

            # 오디오 품질 검증 및 로깅
            if audio_proc_available:
                rms_db, peak, clip = qc(pcm_f32)
                log.info(
                    "TTS generated: %d bytes, %.2f seconds, RMS: %.2f dBFS, peak: %.3f, clip: %.2f%%",
                    len(audio_bytes),
                    len(pcm_16) / 16000.0,
                    rms_db,
                    peak,
                    clip,
                )
            else:
                log.info(
                    "TTS generated: %d bytes, %.2f seconds (post-processing skipped)",
                    len(audio_bytes),
                    len(pcm_16) / 16000.0,
                )
            return audio_bytes
        except ModuleNotFoundError as exc:
            log.error("TTS dependency missing at runtime: %s", exc, exc_info=True)
            log.error("Install: pip install edge-tts librosa soundfile")
            return b""
        except Exception as exc:
            log.error("TTS failed: %s", exc, exc_info=True)
            return b""
