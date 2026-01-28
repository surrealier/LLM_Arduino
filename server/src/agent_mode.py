import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from emotion_system import EmotionSystem
from info_services import InfoServices
from proactive_interaction import ProactiveInteraction
from scheduler import Scheduler

log = logging.getLogger(__name__)


class AgentMode:
    def __init__(
        self,
        device="cuda",
        weather_api_key=None,
        location="Seoul",
        proactive_enabled=True,
        proactive_interval=1800,
        tts_voice=None,
    ):
        self.device = device
        self.model = None
        self.tokenizer = None
        self.tts_voice = tts_voice or "ko-KR-SunHiNeural"

        self.conversation_history = []
        self.important_memories = []
        self.max_history = 20
        self.context_backup_interval = 10
        self.conversation_count = 0

        self.emotion_system = EmotionSystem()
        self.info_services = InfoServices(weather_api_key, location)
        self.proactive = ProactiveInteraction(proactive_enabled, proactive_interval)
        self.scheduler = Scheduler()

        self.backup_dir = Path("context_backup")
        self.backup_dir.mkdir(exist_ok=True)

        self._restore_context()

    def load_model(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            log.info("Loading Qwen2.5-0.5B-Instruct for Agent Mode on %s...", self.device)
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                device_map=self.device,
                trust_remote_code=True,
            )
            log.info("Agent Mode LLM loaded.")
        except ImportError:
            log.error("Transformers/Torch not installed. pip install transformers torch accelerate")
        except Exception as exc:
            log.error("Failed to load Agent LLM: %s", exc)

    def _get_personality_traits(self, personality: str) -> str:
        traits = {
            "cheerful": "밝고 활발하며 긍정적입니다. 대화에서 즐거움과 에너지를 전달합니다.",
            "calm": "차분하고 안정적이며 신중합니다. 편안하고 믿을 수 있는 분위기를 만듭니다.",
            "playful": "장난기 있고 유쾌하며 창의적입니다. 재미있는 표현을 자주 사용합니다.",
            "serious": "진지하고 전문적이며 효율적입니다. 정확한 정보와 실용적인 조언을 제공합니다.",
        }
        return traits.get(personality, traits["cheerful"])

    def _get_system_prompt(self) -> str:
        from config_loader import get_config

        config = get_config()
        assistant_config = config.get_assistant_config()

        assistant_name = assistant_config.get("name", "아이")
        personality = assistant_config.get("personality", "cheerful")
        personality_trait = self._get_personality_traits(personality)

        memories_text = ""
        if self.important_memories:
            memories_text = "\n\n중요한 기억:\n" + "\n".join(
                f"- {mem}" for mem in self.important_memories[-10:]
            )

        return (
            f"당신은 가정용 AI 홈 어시스턴트입니다. 이름은 '{assistant_name}'입니다.\n\n"
            f"성격: {personality_trait}\n\n"
            "핵심 역할:\n"
            "1. 가족 구성원들과 자연스럽고 친근한 대화\n"
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
            "- 필요시 이전 대화 내용 언급\n"
            "- 불확실한 정보는 솔직히 모른다고 말하기\n"
            f"- 자신을 '{assistant_name}'이라고 소개하세요\n\n"
            "현재 기능:\n"
            "- 음성 대화 (STT/TTS)\n"
            "- 서보 모터 제어 (로봇 모드 전환 시)\n"
            "- 정보 제공 및 대화\n"
            f"{memories_text}"
        )

    def generate_response(self, text: str, is_proactive: bool = False) -> str:
        if not self.model or not self.tokenizer:
            return "모델이 로드되지 않았습니다."

        try:
            if not is_proactive:
                self.proactive.update_interaction()

            if not is_proactive:
                sleep_response = self._check_sleep_commands(text)
                if sleep_response:
                    return sleep_response

            if not is_proactive:
                info_response = self.info_services.process_info_request(text)
                if info_response:
                    log.info("Info request processed: %s...", text[:30])
                    return info_response

                schedule_response = self.scheduler.process_schedule_request(text)
                if schedule_response:
                    log.info("Schedule request processed: %s...", text[:30])
                    return schedule_response

            detected_emotion = self.emotion_system.analyze_emotion(text)

            self.conversation_history.append(
                {
                    "role": "user",
                    "content": text,
                    "timestamp": datetime.now().isoformat(),
                    "emotion": detected_emotion,
                }
            )

            messages = [{"role": "system", "content": self._get_system_prompt()}]
            for conv in self.conversation_history[-self.max_history :]:
                messages.append({"role": conv["role"], "content": conv["content"]})

            text_input = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            model_inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.1,
            )

            generated_ids = [
                output_ids[len(input_ids) :] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]
            response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

            response_emotion = self.emotion_system.analyze_emotion(response)
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat(),
                    "emotion": response_emotion,
                }
            )

            self.conversation_count += 1
            if self.conversation_count % self.context_backup_interval == 0:
                self._backup_context()

            self._extract_important_info(text, response)
            log.info("Agent Response: %s", response)
            return response
        except Exception as exc:
            log.error("LLM generation failed: %s", exc)
            return "죄송해요, 오류가 발생했어요."

    def _extract_important_info(self, user_text: str, assistant_response: str):
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

        if len(self.important_memories) > 50:
            self.important_memories = self.important_memories[-50:]

    def _backup_context(self):
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
        sleep_keywords = ["자러", "잘게", "잘게요", "잘게요", "그만", "쉬자"]
        if any(keyword in text for keyword in sleep_keywords):
            self.proactive.sleep_mode = True
            self.proactive.sleep_until = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
            return "알겠어요. 쉬는 동안 조용히 있을게요."
        return None

    async def _tts_gen(self, text, output_file):
        import edge_tts

        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_file)

    def text_to_audio(self, text: str):
        try:
            import librosa
            import os
            from audio_processor import normalize_to_dbfs, qc, trim_energy

            tmp_mp3 = "temp_tts.mp3"

            log.info("Generating TTS for: %s", text[:50])

            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self._tts_gen(text, tmp_mp3))

            if not os.path.exists(tmp_mp3):
                log.error("TTS file not created: %s", tmp_mp3)
                return b""

            # 오디오 로드 및 리샘플링 (16kHz, mono)
            pcm_f32, sr = librosa.load(tmp_mp3, sr=16000, mono=True)

            if pcm_f32.size == 0:
                log.error("TTS audio empty after decoding: %s", tmp_mp3)
                return b""

            # DC 오프셋 제거 + 무음 구간 트림
            pcm_f32 = (pcm_f32 - np.mean(pcm_f32)).astype(np.float32, copy=False)
            pcm_f32 = trim_energy(pcm_f32, sr=sr, top_db=35.0, pad_ms=140)

            # 가능한 크게 재생되도록 RMS 정규화 (클리핑 방지)
            pcm_f32 = normalize_to_dbfs(pcm_f32, target_dbfs=-12.0, max_gain_db=24.0)
            peak = float(np.max(np.abs(pcm_f32))) if pcm_f32.size else 0.0
            if peak > 0.98:
                pcm_f32 = (pcm_f32 / peak * 0.98).astype(np.float32, copy=False)

            # 16-bit PCM 변환 (PCM16LE)
            pcm_16 = (pcm_f32 * 32767.0).astype("<i2")
            audio_bytes = pcm_16.tobytes()

            rms_db, peak, clip = qc(pcm_f32)
            log.info(
                "TTS generated: %d bytes, %.2f seconds, RMS: %.2f dBFS, peak: %.3f, clip: %.2f%%",
                len(audio_bytes),
                len(pcm_16) / 16000.0,
                rms_db,
                peak,
                clip,
            )

            return audio_bytes
        except ImportError:
            log.error("Install edge-tts, librosa, soundfile: pip install edge-tts librosa soundfile")
            return b""
        except Exception as exc:
            log.error("TTS failed: %s", exc, exc_info=True)
            return b""
