"""
로봇 모드 처리 모듈
- 음성 명령을 서보 모터 제어 명령으로 변환
- 키워드 기반 명령 파싱 및 LLM 기반 명령 해석
- 서보 각도 제어 및 동작 명령 생성
"""
import json
import logging
import re

from .utils import clamp

log = logging.getLogger(__name__)

# 서보 모터 제어 상수 정의
SERVO_MIN = 0
SERVO_MAX = 180
DEFAULT_ANGLE_CENTER = 90
DEFAULT_STEP = 20
UNSURE_POLICY = "NOOP"


class RobotMode:
    """로봇 모드 메인 클래스 - 음성 명령을 로봇 동작으로 변환"""
    def __init__(self, actions_config, llm_client=None):
        self.actions_config = actions_config
        self.llm = llm_client

    def process_text(self, text: str, current_angle: int):
        """키워드 기반 텍스트 명령 처리 - 설정된 액션 규칙에 따라 명령 파싱"""
        t = (text or "").strip()
        if not t:
            return (
                {"action": "NOOP"} if UNSURE_POLICY == "NOOP" else {"action": "WIGGLE"},
                False,
                current_angle,
            )

        # 설정된 명령어 패턴 순회하며 매칭 검사
        for cmd in self.actions_config:
            matched = False
            captured_val = None

            # 키워드 매칭 검사
            if "keywords" in cmd:
                for key in cmd["keywords"]:
                    if key in t:
                        matched = True
                        break

            # 정규식 패턴 매칭 검사
            if not matched and "pattern" in cmd:
                match = re.search(cmd["pattern"], t)
                if match:
                    matched = True
                    if cmd.get("use_captured") and match.lastindex and match.lastindex >= 1:
                        try:
                            captured_val = int(match.group(1))
                        except Exception:
                            pass

            # 매칭된 명령어 처리
            if matched:
                action_type = cmd.get("action", "NOOP")
                servo_idx = cmd.get("servo", 0)

                # 모드 전환 명령 처리
                if action_type == "SWITCH_MODE":
                    return ({"action": "SWITCH_MODE", "mode": cmd.get("mode", "robot")}, True, current_angle)

                # 서보 절대 각도 설정 명령 처리
                if action_type == "SERVO_SET":
                    angle = cmd.get("angle")
                    if cmd.get("use_captured") and captured_val is not None:
                        angle = captured_val
                    if angle is None:
                        angle = DEFAULT_ANGLE_CENTER

                    final_angle = clamp(angle, SERVO_MIN, SERVO_MAX)
                    return (
                        {"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle},
                        True,
                        final_angle,
                    )

                # 서보 각도 증가 명령 처리
                if action_type == "SERVO_INC":
                    step = cmd.get("value", DEFAULT_STEP)
                    final_angle = clamp(current_angle + step, SERVO_MIN, SERVO_MAX)
                    return (
                        {"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle},
                        True,
                        final_angle,
                    )

                # 서보 각도 감소 명령 처리
                if action_type == "SERVO_DEC":
                    step = cmd.get("value", DEFAULT_STEP)
                    final_angle = clamp(current_angle - step, SERVO_MIN, SERVO_MAX)
                    return (
                        {"action": "SERVO_SET", "servo": servo_idx, "angle": final_angle},
                        True,
                        final_angle,
                    )

                return ({"action": action_type, "servo": servo_idx}, True, current_angle)

        # 매칭되지 않은 경우 기본 동작 반환
        return (
            {"action": "NOOP"} if UNSURE_POLICY == "NOOP" else {"action": "WIGGLE"},
            False,
            current_angle,
        )

    def process_with_llm(self, text: str, current_angle: int):
        """LLM 기반 명령 처리 - 음성 텍스트 정제 및 지능형 명령 해석"""
        if not self.llm:
            action, _, _ = self.process_text(text, current_angle)
            return text, action

        try:
            refined_text = self._refine_stt(text)
            action = self._determine_action(refined_text, current_angle)
            return refined_text, action
        except Exception as exc:
            log.error("LLM processing failed: %s", exc)
            action, _, _ = self.process_text(text, current_angle)
            return text, action

    def _refine_stt(self, text: str) -> str:
        """음성인식 결과 정제 - STT 오류 수정 및 텍스트 품질 향상"""
        if not text or len(text) < 2:
            return text

        system_prompt = (
            "당신은 음성인식 결과를 정제하는 전문가입니다.\n"
            "사용자의 음성인식 결과에 오타나 불명확한 부분이 있으면 올바른 한국어로 수정하세요.\n"
            "로봇 제어 명령어 맥락을 고려하여 정제하세요.\n\n"
            "예시:\n"
            "- \"안냥하시오\" -> \"안녕하세요\"\n"
            "- \"가운대로\" -> \"가운데로\"\n"
            "- \"오론쪽\" -> \"오른쪽\"\n"
            "- \"멈춰라\" -> \"멈춰\"\n\n"
            "정제된 텍스트만 출력하세요. 설명이나 추가 문장 없이 결과만 반환하세요."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 음성인식 결과를 정제하세요: {text}"},
        ]

        refined = self.llm.chat(messages, temperature=0.1, max_tokens=64)

        # 정제 결과 검증 - 비정상적인 결과 필터링
        if len(refined) > len(text) * 3 or len(refined) < 1:
            return text
        return refined

    def _determine_action(self, text: str, current_angle: int) -> dict:
        """LLM 기반 동작 결정 - 정제된 텍스트를 로봇 명령으로 변환"""
        # 사용 가능한 명령어 목록 생성
        commands_desc = []
        for cmd in self.actions_config:
            if cmd.get("action") == "SWITCH_MODE":
                continue

            name = cmd.get("name", "")
            keywords = cmd.get("keywords", [])
            action = cmd.get("action", "")

            if keywords:
                commands_desc.append(f"- {name}: {', '.join(keywords[:3])} -> {action}")

        commands_text = "\n".join(commands_desc[:10])

        system_prompt = (
            "당신은 로봇 제어 명령을 해석하는 AI입니다.\n"
            "사용자의 음성 명령을 분석하여 적절한 로봇 동작을 JSON 형식으로 반환하세요.\n\n"
            f"현재 서보 각도: {current_angle}도\n"
            "서보 각도 범위: 0-180도\n\n"
            "사용 가능한 명령:\n"
            f"{commands_text}\n\n"
            "응답 형식 (JSON만 출력):\n"
            "{\"action\": \"SERVO_SET\", \"servo\": 0, \"angle\": 90}\n"
            "또는\n"
            "{\"action\": \"STOP\", \"servo\": 0}\n"
            "또는\n"
            "{\"action\": \"NOOP\"}\n\n"
            "규칙:\n"
            "1. 각도 지정 명령은 SERVO_SET 사용\n"
            "2. 상대 이동(올려/내려)은 현재 각도 기준으로 계산\n"
            "3. 불명확한 명령은 NOOP 반환\n"
            "4. JSON 형식만 출력, 설명 금지"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"명령: {text}"},
        ]

        # LLM을 통한 명령 해석
        response = self.llm.chat(messages, temperature=0.1, max_tokens=128)

        # JSON 응답 파싱 및 각도 범위 검증
        match = re.search(r"\{[^}]+\}", response)
        if match:
            action_dict = json.loads(match.group(0))
            if "angle" in action_dict:
                action_dict["angle"] = clamp(action_dict["angle"], SERVO_MIN, SERVO_MAX)
            return action_dict

        return {"action": "NOOP"}