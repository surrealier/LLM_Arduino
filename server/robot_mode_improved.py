import re
import logging
import json

log = logging.getLogger("robot_mode")

SERVO_MIN = 0
SERVO_MAX = 180
DEFAULT_ANGLE_CENTER = 90
DEFAULT_STEP = 20
UNSURE_POLICY = "NOOP"

def clamp(v, lo, hi): 
    return max(lo, min(hi, v))

class RobotMode:
    def __init__(self, actions_config, device="cuda"):
        self.actions_config = actions_config
        self.device = device
        self.model = None
        self.tokenizer = None

    def load_model(self):
        """LLM 모델 로드 - STT 정제 및 명령 해석용"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            log.info(f"Loading Qwen2.5-0.5B-Instruct for Robot Mode on {self.device}...")
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            torch_dtype = torch.float16 if self.device == "cuda" else torch.float32
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                device_map=self.device,
                trust_remote_code=True
            )
            log.info("Robot Mode LLM loaded.")
            
        except ImportError:
            log.error("Transformers/Torch not installed. pip install transformers torch accelerate")
        except Exception as e:
            log.error(f"Failed to load Robot LLM: {e}")

    def process_text(self, text: str, current_angle: int):
        """
        기존 YAML 기반 명령 파싱 (모드 전환 등 시스템 명령용)
        Returns: (action_dict, meaningful_bool, new_angle)
        """
        t = (text or "").strip()
        if not t:
            return ({"action": "NOOP"} if UNSURE_POLICY == "NOOP" else {"action": "WIGGLE"}, False, current_angle)

        for cmd in self.actions_config:
            matched = False
            captured_val = None

            if "keywords" in cmd:
                for k in cmd["keywords"]:
                    if k in t:
                        matched = True
                        break
            
            if not matched and "pattern" in cmd:
                m = re.search(cmd["pattern"], t)
                if m:
                    matched = True
                    if cmd.get("use_captured") and m.lastindex and m.lastindex >= 1:
                        try:
                            captured_val = int(m.group(1))
                        except:
                            pass
            
            if matched:
                a_type = cmd.get("action", "NOOP")
                servo_idx = cmd.get("servo", 0)
                
                if a_type == "SWITCH_MODE":
                    return ({"action": "SWITCH_MODE", "mode": cmd.get("mode", "robot")}, True, current_angle)
                
                if a_type == "SERVO_SET":
                    angle = cmd.get("angle")
                    if cmd.get("use_captured") and captured_val is not None:
                        angle = captured_val
                    if angle is None: 
                        angle = DEFAULT_ANGLE_CENTER
                    
                    final_angle = clamp(angle, SERVO_MIN, SERVO_MAX)
                    return ({"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle}, True, final_angle)

                elif a_type == "SERVO_INC":
                    step = cmd.get("value", DEFAULT_STEP)
                    final_angle = clamp(current_angle + step, SERVO_MIN, SERVO_MAX)
                    return ({"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle}, True, final_angle)

                elif a_type == "SERVO_DEC":
                    step = cmd.get("value", DEFAULT_STEP)
                    final_angle = clamp(current_angle - step, SERVO_MIN, SERVO_MAX)
                    return ({"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle}, True, final_angle)

                else:
                    return ({"action": a_type, "servo": servo_idx}, True, current_angle)

        return ({"action": "NOOP"} if UNSURE_POLICY == "NOOP" else {"action": "WIGGLE"}, False, current_angle)

    def process_with_llm(self, text: str, current_angle: int):
        """
        LLM을 사용하여:
        1. STT 결과 정제 (오타 수정, 명확화)
        2. 정제된 텍스트로 로봇 명령 결정
        
        Returns: (refined_text, action_dict)
        """
        if not self.model or not self.tokenizer:
            # LLM 없으면 기존 방식 사용
            action, _, _ = self.process_text(text, current_angle)
            return text, action

        try:
            # Step 1: STT 정제
            refined_text = self._refine_stt(text)
            
            # Step 2: 정제된 텍스트로 명령 결정
            action = self._determine_action(refined_text, current_angle)
            
            return refined_text, action
            
        except Exception as e:
            log.error(f"LLM processing failed: {e}")
            action, _, _ = self.process_text(text, current_angle)
            return text, action

    def _refine_stt(self, text: str) -> str:
        """STT 결과를 LLM으로 정제"""
        if not text or len(text) < 2:
            return text
        
        try:
            system_prompt = """당신은 음성인식 결과를 정제하는 전문가입니다.
사용자의 음성인식 결과에 오타나 불명확한 부분이 있으면 올바른 한국어로 수정하세요.
로봇 제어 명령어 맥락을 고려하여 정제하세요.

예시:
- "안냥하시오" -> "안녕하세요"
- "가운대로" -> "가운데로"
- "오론쪽" -> "오른쪽"
- "멈춰라" -> "멈춰"

정제된 텍스트만 출력하세요. 설명이나 추가 문장 없이 결과만 반환하세요."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 음성인식 결과를 정제하세요: {text}"}
            ]
            
            text_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            model_inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                max_new_tokens=64,
                do_sample=False,
                temperature=0.1
            )
            
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]

            refined = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            
            # 너무 길거나 이상한 응답이면 원본 사용
            if len(refined) > len(text) * 3 or len(refined) < 1:
                return text
            
            return refined
            
        except Exception as e:
            log.error(f"STT refinement failed: {e}")
            return text

    def _determine_action(self, text: str, current_angle: int) -> dict:
        """정제된 텍스트로 로봇 동작 결정"""
        try:
            # 사용 가능한 명령어 목록 생성
            commands_desc = []
            for cmd in self.actions_config:
                if cmd.get("action") == "SWITCH_MODE":
                    continue  # 모드 전환은 제외
                
                name = cmd.get("name", "")
                keywords = cmd.get("keywords", [])
                action = cmd.get("action", "")
                
                if keywords:
                    commands_desc.append(f"- {name}: {', '.join(keywords[:3])} -> {action}")
            
            commands_text = "\n".join(commands_desc[:10])  # 최대 10개만
            
            system_prompt = f"""당신은 로봇 제어 명령을 해석하는 AI입니다.
사용자의 음성 명령을 분석하여 적절한 로봇 동작을 JSON 형식으로 반환하세요.

현재 서보 각도: {current_angle}도
서보 각도 범위: 0-180도

사용 가능한 명령:
{commands_text}

응답 형식 (JSON만 출력):
{{"action": "SERVO_SET", "servo": 0, "angle": 90}}
또는
{{"action": "STOP", "servo": 0}}
또는
{{"action": "NOOP"}}

규칙:
1. 각도 지정 명령은 SERVO_SET 사용
2. 상대 이동(올려/내려)은 현재 각도 기준으로 계산
3. 불명확한 명령은 NOOP 반환
4. JSON 형식만 출력, 설명 금지"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"명령: {text}"}
            ]
            
            text_input = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            model_inputs = self.tokenizer([text_input], return_tensors="pt").to(self.device)

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                max_new_tokens=128,
                do_sample=False,
                temperature=0.1
            )
            
            generated_ids = [
                output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
            ]

            response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            
            # JSON 추출
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                action_dict = json.loads(json_match.group(0))
                
                # 각도 범위 검증
                if "angle" in action_dict:
                    action_dict["angle"] = clamp(action_dict["angle"], SERVO_MIN, SERVO_MAX)
                
                return action_dict
            else:
                # JSON 파싱 실패 시 기존 방식 사용
                action, _, _ = self.process_text(text, current_angle)
                return action
                
        except Exception as e:
            log.error(f"Action determination failed: {e}")
            action, _, _ = self.process_text(text, current_angle)
            return action
