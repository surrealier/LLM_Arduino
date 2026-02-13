"""
RobotMode — LLM 기반 서보 제어 + 모드 전환 의도 파악
키워드 매칭 대신 LLM이 명령 의도를 판단
"""

import re
import logging
import json

log = logging.getLogger("robot_mode")

SERVO_MIN = 0
SERVO_MAX = 180
DEFAULT_ANGLE_CENTER = 90
DEFAULT_STEP = 20

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class RobotMode:
    def __init__(self, actions_config, device="cuda"):
        self.actions_config = actions_config
        self.device = device
        self.model = None
        self.tokenizer = None

    def load_model(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            log.info(f"Loading Qwen2.5-0.5B-Instruct for Robot Mode on {self.device}...")
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch_dtype,
                device_map=self.device, trust_remote_code=True
            )
            log.info("Robot Mode LLM loaded.")

        except ImportError:
            log.error("Transformers/Torch not installed. pip install transformers torch accelerate")
        except Exception as e:
            log.error(f"Failed to load Robot LLM: {e}")

    def process_with_llm(self, text: str, current_angle: int):
        """LLM으로 STT 정제 + 명령 결정 (서보 제어 + 모드 전환 포함).
        Returns: (refined_text, action_dict)
        """
        if not self.model or not self.tokenizer:
            return text, {"action": "NOOP"}

        try:
            refined_text = self._refine_stt(text)
            action = self._determine_action(refined_text, current_angle)
            return refined_text, action
        except Exception as e:
            log.error(f"LLM processing failed: {e}")
            return text, {"action": "NOOP"}

    def _refine_stt(self, text: str) -> str:
        if not text or len(text) < 2:
            return text
        try:
            messages = [
                {"role": "system", "content": "음성인식 결과를 정제해. 로봇 제어 명령 맥락을 고려해. 정제된 텍스트만 출력."},
                {"role": "user", "content": text}
            ]
            text_input = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)
            generated = self.model.generate(
                inputs.input_ids, max_new_tokens=64, do_sample=False, temperature=0.1
            )
            output_ids = generated[0][len(inputs.input_ids[0]):]
            refined = self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()
            return refined if 0 < len(refined) <= len(text) * 3 else text
        except Exception as e:
            log.error(f"STT refinement failed: {e}")
            return text

    def _determine_action(self, text: str, current_angle: int) -> dict:
        """LLM으로 명령 의도 판단 — 서보 제어 + 모드 전환 통합"""
        try:
            system_prompt = f"""로봇 제어 명령을 해석해. JSON만 출력해.

현재 서보 각도: {current_angle}도 (범위: 0~180)

가능한 명령:
- 서보 각도 설정: {{"action":"SERVO_SET","servo":0,"angle":숫자}}
- 정지: {{"action":"STOP","servo":0}}
- 에이전트/대화 모드 전환: {{"action":"SWITCH_MODE","mode":"agent"}}
- 해당 없음: {{"action":"NOOP"}}

규칙:
- "왼쪽"=30, "오른쪽"=150, "가운데/중앙"=90
- "올려/위로"=현재+20, "내려/아래로"=현재-20
- 숫자 언급 시 해당 각도로 설정
- "대화하자", "얘기하자", "에이전트 모드" 등은 SWITCH_MODE
- 불명확하면 NOOP"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
            text_input = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)
            generated = self.model.generate(
                inputs.input_ids, max_new_tokens=64, do_sample=False, temperature=0.1
            )
            output_ids = generated[0][len(inputs.input_ids[0]):]
            response = self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()

            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                action = json.loads(json_match.group(0))
                if "angle" in action:
                    action["angle"] = clamp(action["angle"], SERVO_MIN, SERVO_MAX)
                return action

            return {"action": "NOOP"}

        except Exception as e:
            log.error(f"Action determination failed: {e}")
            return {"action": "NOOP"}
