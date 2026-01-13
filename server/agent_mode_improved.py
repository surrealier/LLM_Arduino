import logging
import io
import asyncio
import numpy as np
import json
import time
from pathlib import Path
from datetime import datetime

log = logging.getLogger("agent_mode")

class AgentMode:
    def __init__(self, device="cuda"):
        self.device = device
        self.model = None
        self.tokenizer = None
        self.tts_voice = "ko-KR-SunHiNeural"
        
        # 대화 컨텍스트 관리
        self.conversation_history = []
        self.important_memories = []
        self.max_history = 20  # 최근 20개 대화만 유지
        self.context_backup_interval = 10  # 10개 대화마다 백업
        self.conversation_count = 0
        
        # 백업 디렉토리
        self.backup_dir = Path("context_backup")
        self.backup_dir.mkdir(exist_ok=True)
        
        # 시작 시 이전 컨텍스트 복원
        self._restore_context()

    def load_model(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            log.info(f"Loading Qwen2.5-0.5B-Instruct for Agent Mode on {self.device}...")
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                device_map=self.device,
                trust_remote_code=True
            )
            log.info("Agent Mode LLM loaded.")
            
        except ImportError:
            log.error("Transformers/Torch not installed. pip install transformers torch accelerate")
        except Exception as e:
            log.error(f"Failed to load Agent LLM: {e}")

    def _get_system_prompt(self) -> str:
        """홈 어시스턴트 시스템 프롬프트"""
        memories_text = ""
        if self.important_memories:
            memories_text = "\n\n중요한 기억:\n" + "\n".join(f"- {mem}" for mem in self.important_memories[-10:])
        
        return f"""당신은 가정용 AI 홈 어시스턴트입니다. 이름은 사용자가 정해줄 수 있습니다.

핵심 역할:
1. 가족 구성원들과 자연스럽고 친근한 대화
2. 일상적인 질문에 대한 도움 제공
3. 간단한 정보 검색 및 안내
4. 가족의 일정, 선호사항, 중요한 정보 기억
5. 따뜻하고 공감적인 응답

중요 원칙:
- 대화 내용을 절대 잊어서는 안 됩니다
- 사용자가 이전에 말한 내용을 기억하고 참조하세요
- 가족 구성원 각자의 특성과 선호를 기억하세요
- 중요한 날짜, 약속, 선호사항은 반드시 기억하세요
- 이전 대화의 맥락을 이어가세요

응답 스타일:
- 한국어로 자연스럽게 대화
- 2-3문장 이내로 간결하게 답변
- 친근하고 따뜻한 어조 유지
- 필요시 이전 대화 내용 언급
- 불확실한 정보는 솔직히 모른다고 말하기

현재 기능:
- 음성 대화 (STT/TTS)
- 서보 모터 제어 (로봇 모드 전환 시)
- 정보 제공 및 대화
{memories_text}"""

    def generate_response(self, text: str) -> str:
        """사용자 입력에 대한 응답 생성"""
        if not self.model or not self.tokenizer:
            return "모델이 로드되지 않았습니다."

        try:
            # 대화 히스토리에 추가
            self.conversation_history.append({
                "role": "user",
                "content": text,
                "timestamp": datetime.now().isoformat()
            })
            
            # 컨텍스트 구성
            messages = [{"role": "system", "content": self._get_system_prompt()}]
            
            # 최근 대화 추가
            for conv in self.conversation_history[-self.max_history:]:
                messages.append({
                    "role": conv["role"],
                    "content": conv["content"]
                })
            
            text_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            model_inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.1
            )
            
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]

            response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            
            # 응답을 히스토리에 추가
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })
            
            self.conversation_count += 1
            
            # 주기적 백업
            if self.conversation_count % self.context_backup_interval == 0:
                self._backup_context()
            
            # 중요 정보 추출 및 저장
            self._extract_important_info(text, response)
            
            log.info(f"Agent Response: {response}")
            return response
            
        except Exception as e:
            log.error(f"LLM generation failed: {e}")
            return "죄송해요, 오류가 발생했어요."

    def _extract_important_info(self, user_text: str, assistant_response: str):
        """대화에서 중요한 정보 추출"""
        # 간단한 키워드 기반 중요 정보 감지
        important_keywords = [
            "이름", "생일", "좋아", "싫어", "알레르기", "약속", "일정",
            "가족", "친구", "전화번호", "주소", "기억", "잊지마"
        ]
        
        combined_text = user_text + " " + assistant_response
        
        for keyword in important_keywords:
            if keyword in combined_text:
                memory_entry = f"[{datetime.now().strftime('%Y-%m-%d')}] {user_text[:50]}"
                if memory_entry not in self.important_memories:
                    self.important_memories.append(memory_entry)
                    log.info(f"Important memory saved: {memory_entry}")
                break
        
        # 최대 50개 기억만 유지
        if len(self.important_memories) > 50:
            self.important_memories = self.important_memories[-50:]

    def _backup_context(self):
        """대화 컨텍스트 백업"""
        try:
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "conversation_count": self.conversation_count,
                "conversation_history": self.conversation_history[-self.max_history:],
                "important_memories": self.important_memories
            }
            
            backup_file = self.backup_dir / "latest_context.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # 날짜별 백업도 생성
            dated_backup = self.backup_dir / f"context_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(dated_backup, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            log.info(f"Context backed up: {self.conversation_count} conversations")
            
            # 오래된 백업 정리 (최근 30개만 유지)
            self._cleanup_old_backups()
            
        except Exception as e:
            log.error(f"Context backup failed: {e}")

    def _restore_context(self):
        """이전 대화 컨텍스트 복원"""
        try:
            backup_file = self.backup_dir / "latest_context.json"
            if backup_file.exists():
                with open(backup_file, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                
                self.conversation_history = backup_data.get("conversation_history", [])
                self.important_memories = backup_data.get("important_memories", [])
                self.conversation_count = backup_data.get("conversation_count", 0)
                
                log.info(f"Context restored: {len(self.conversation_history)} conversations, "
                        f"{len(self.important_memories)} memories")
            else:
                log.info("No previous context found, starting fresh")
                
        except Exception as e:
            log.error(f"Context restoration failed: {e}")

    def _cleanup_old_backups(self):
        """오래된 백업 파일 정리"""
        try:
            backup_files = sorted(self.backup_dir.glob("context_*.json"))
            if len(backup_files) > 30:
                for old_file in backup_files[:-30]:
                    old_file.unlink()
                    log.info(f"Deleted old backup: {old_file.name}")
        except Exception as e:
            log.error(f"Backup cleanup failed: {e}")

    async def _tts_gen(self, text, output_file):
        import edge_tts
        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_file)

    def text_to_audio(self, text: str) -> bytes:
        """TTS: 텍스트를 16kHz Mono PCM 오디오로 변환"""
        try:
            import soundfile as sf
            import librosa
            
            tmp_mp3 = "temp_tts.mp3"
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            loop.run_until_complete(self._tts_gen(text, tmp_mp3))
            
            data, samplerate = librosa.load(tmp_mp3, sr=16000, mono=True)
            data = np.clip(data, -1.0, 1.0)
            pcm_16 = (data * 32767).astype(np.int16)
            
            return pcm_16.tobytes()
            
        except ImportError:
            log.error("Install: pip install edge-tts librosa soundfile")
            return b""
        except Exception as e:
            log.error(f"TTS failed: {e}")
            return b""

    def clear_context(self):
        """컨텍스트 수동 초기화 (백업 후)"""
        self._backup_context()
        self.conversation_history = []
        self.conversation_count = 0
        log.info("Context cleared (memories preserved)")
