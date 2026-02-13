"""
AgentMode — 콜리 (Colly) 홈 에이전트
MemoryManager 기반 구조화된 메모리 + 자비스 스타일 시스템 프롬프트
"""

import json
import asyncio
import logging
import numpy as np
from datetime import datetime
from typing import Optional

from emotion_system import EmotionSystem
from info_services import InfoServices
from proactive_interaction import ProactiveInteraction
from scheduler import Scheduler
from memory_manager import MemoryManager

log = logging.getLogger("agent_mode")


class AgentMode:
    def __init__(self, device="cuda", weather_api_key=None, location="Seoul",
                 proactive_enabled=True, proactive_interval=1800, tts_voice=None):
        self.device = device
        self.model = None
        self.tokenizer = None
        self.tts_voice = tts_voice or "ko-KR-SunHiNeural"

        # 대화 컨텍스트 (현재 세션용, LLM context window)
        self.conversation_history = []
        self.max_history = 20

        # 구조화된 메모리 시스템
        self.memory = MemoryManager(
            refresh_interval=300,    # 5분마다 자동 refresh
            refresh_after_turns=5,   # 5턴마다 refresh
            idle_threshold=120       # 2분 idle 시 refresh
        )

        # 서브시스템
        self.emotion_system = EmotionSystem()
        self.info_services = InfoServices(weather_api_key, location)
        self.proactive = ProactiveInteraction(proactive_enabled, proactive_interval)
        self.scheduler = Scheduler()

    def load_model(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            log.info(f"Loading Qwen2.5-0.5B-Instruct for Agent Mode on {self.device}...")
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch_dtype,
                device_map=self.device, trust_remote_code=True
            )
            log.info("Agent Mode LLM loaded.")

            # MemoryManager에 LLM 함수 주입
            self.memory.set_llm(self._llm_generate)

        except ImportError:
            log.error("Transformers/Torch not installed. pip install transformers torch accelerate")
        except Exception as e:
            log.error(f"Failed to load Agent LLM: {e}")

    def _llm_generate(self, prompt: str, max_tokens=128) -> str:
        """MemoryManager가 사용하는 내부 LLM 호출"""
        if not self.model or not self.tokenizer:
            return ""
        try:
            messages = [
                {"role": "system", "content": "간결하게 한국어로 답해."},
                {"role": "user", "content": prompt}
            ]
            text_input = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)
            generated = self.model.generate(
                inputs.input_ids,
                attention_mask=inputs.get("attention_mask"),
                max_new_tokens=max_tokens,
                do_sample=False, temperature=0.3
            )
            output_ids = generated[0][len(inputs.input_ids[0]):]
            return self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()
        except Exception as e:
            log.error(f"LLM generate (internal) failed: {e}")
            return ""

    def generate_response(self, text: str, is_proactive: bool = False) -> str:
        """사용자 입력에 대한 응답 생성"""
        if not self.model or not self.tokenizer:
            return "모델이 로드되지 않았습니다."

        try:
            if not is_proactive:
                self.proactive.update_interaction()

                # 수면 모드 명령
                sleep_response = self._check_sleep_commands(text)
                if sleep_response:
                    return sleep_response

                # 정보 요청 (날씨, 시간 등)
                info_response = self.info_services.process_info_request(text)
                if info_response:
                    return info_response

                # 일정 요청
                schedule_response = self.scheduler.process_schedule_request(text)
                if schedule_response:
                    return schedule_response

            # 감정 분석
            self.emotion_system.analyze_emotion(text)

            # 대화 히스토리 + 메모리에 기록
            self.conversation_history.append({"role": "user", "content": text})
            self.memory.add_turn("user", text)

            # 시스템 프롬프트 (메모리 기반)
            messages = [{"role": "system", "content": self.memory.build_system_prompt()}]
            messages += [{"role": c["role"], "content": c["content"]}
                         for c in self.conversation_history[-self.max_history:]]

            text_input = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            model_inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)

            attention_mask = model_inputs.get("attention_mask")
            if attention_mask is None:
                pad_id = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id
                attention_mask = (model_inputs.input_ids != pad_id).long()

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                attention_mask=attention_mask,
                max_new_tokens=256,
                do_sample=True, temperature=0.8,
                top_p=0.9, repetition_penalty=1.1
            )

            output_ids = generated_ids[0][len(model_inputs.input_ids[0]):]
            response = self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()

            # 응답 기록
            self.conversation_history.append({"role": "assistant", "content": response})
            self.memory.add_turn("assistant", response)

            self.emotion_system.analyze_emotion(response)
            log.info(f"Agent Response: {response}")
            return response

        except Exception as e:
            log.error(f"LLM generation failed: {e}")
            return "미안, 잠깐 오류가 났어."

    # ── TTS ──

    async def _tts_gen(self, text, output_file):
        import edge_tts
        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_file)

    def text_to_audio(self, text: str) -> bytes:
        """TTS: 텍스트를 16kHz Mono PCM 오디오로 변환"""
        try:
            import librosa

            tmp_mp3 = "temp_tts.mp3"
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self._tts_gen(text, tmp_mp3))
            data, _ = librosa.load(tmp_mp3, sr=16000, mono=True)
            data = np.clip(data, -1.0, 1.0)
            return (data * 32767).astype(np.int16).tobytes()

        except ImportError:
            log.error("Install: pip install edge-tts librosa soundfile")
            return b""
        except Exception as e:
            log.error(f"TTS failed: {e}")
            return b""

    # ── 감정/수면/프로액티브 ──

    def get_emotion_command(self):
        return self.emotion_system.get_emotion_command()

    def _check_sleep_commands(self, text: str) -> Optional[str]:
        text_lower = text.lower()

        sleep_keywords = ["잘게", "잔다", "자러", "잘 시간", "수면", "조용히", "그만 말해"]
        if any(kw in text_lower for kw in sleep_keywords):
            return self.proactive.enter_sleep_mode()

        pause_keywords = ["멈춰", "조용히 해", "시끄러", "잠깐만", "좀 쉬어"]
        if any(kw in text_lower for kw in pause_keywords):
            import re
            m = re.search(r'(\d+)\s*시간', text_lower)
            return self.proactive.pause_temporarily(int(m.group(1)) if m else 1)

        wake_keywords = ["일어나", "다시 말해", "깨워", "시작"]
        if any(kw in text_lower for kw in wake_keywords):
            return self.proactive.wake_up()

        return None

    def get_proactive_message(self) -> Optional[str]:
        return self.proactive.get_proactive_message(
            current_emotion=self.emotion_system.current_emotion,
            important_memories=[]  # 메모리는 이제 .md 파일에서 관리
        )

    def check_timers_and_alarms(self):
        messages = []
        for timer in self.info_services.check_timers():
            messages.append(f"⏰ {timer['label']} 타이머가 완료되었습니다!")
        for alarm in self.info_services.check_alarms():
            messages.append(f"⏰ {alarm['label']} 알람입니다!")
        for schedule in self.scheduler.check_reminders():
            dt = datetime.fromisoformat(schedule["datetime"])
            messages.append(f"📅 {dt.strftime('%H:%M')}에 '{schedule['title']}' 일정이 있습니다!")
        return messages

    def clear_context(self):
        """컨텍스트 초기화 (메모리 flush 후)"""
        self.memory.refresh()
        self.conversation_history = []
        log.info("Context cleared. Memory persisted to .md files.")
