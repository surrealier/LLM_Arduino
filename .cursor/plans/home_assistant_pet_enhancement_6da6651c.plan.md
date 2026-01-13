---
name: Home Assistant Pet Enhancement
overview: Atom Echo 기반 홈 어시스턴트/펫 시스템의 기능 확장 및 코드 개선. 감정 표현, 실용적 기능 추가, 안정성 향상을 목표로 합니다.
todos:
  - id: fix-arduino-bugs
    content: Arduino 코드 문법 오류 수정 및 설정 분리
    status: completed
  - id: emotion-system
    content: 감정 상태 시스템 구현 (LED 패턴, 서보 동작)
    status: completed
    dependencies:
      - fix-arduino-bugs
  - id: info-services
    content: 시간/날씨/뉴스 정보 서비스 추가
    status: completed
  - id: proactive-interaction
    content: 프로액티브 상호작용 기능 (자발적 대화)
    status: completed
    dependencies:
      - emotion-system
  - id: config-management
    content: 통합 설정 관리 (config.yaml, .env)
    status: completed
  - id: scheduler
    content: 일정 및 리마인더 시스템
    status: completed
    dependencies:
      - info-services
  - id: personality-customization
    content: 개성 및 이름 커스터마이즈
    status: completed
    dependencies:
      - config-management
  - id: logging-improvements
    content: 로깅 및 모니터링 강화
    status: completed
---

# 홈 어시스턴트/펫 기능 강화 및 개선 계획

## 현재 시스템 개요

프로젝트는 Atom Echo (ESP32)를 사용한 음성 기반 IoT 시스템으로, 두 가지 모드를 지원합니다:

- **Robot Mode**: 서보 모터 제어 (빠른 응답)
- **Agent Mode**: 대화형 LLM (컨텍스트 유지)

주요 파일:

- [`arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino`](arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino): ESP32 펌웨어
- [`server/stt_improved.py`](server/stt_improved.py): 메인 서버 (STT, 모드 관리)
- [`server/robot_mode_improved.py`](server/robot_mode_improved.py): 로봇 모드 LLM
- [`server/agent_mode_improved.py`](server/agent_mode_improved.py): 에이전트 모드 LLM
- [`server/commands.yaml`](server/commands.yaml): 명령어 정의

---

## 1단계: 펫 기능 강화 (감정 표현 및 상호작용)

### 1.1 감정 상태 시스템 추가

**목표**: 펫처럼 감정 상태를 가지고, LED 색상과 서보 동작으로 표현

**구현 사항**:

- 감정 상태: `happy`, `sad`, `excited`, `sleepy`, `angry`, `neutral`
- 감정에 따른 LED 패턴 (무지개, 점멸, 페이드 등)
- 감정에 따른 서보 동작 패턴 (흔들기, 끄덕이기, 고개 젓기)
- 대화 내용 분석으로 감정 자동 변경

**파일**:

- 새 파일: `server/emotion_system.py` - 감정 분석 및 관리
- 수정: [`server/agent_mode_improved.py`](server/agent_mode_improved.py) - 감정 분석 통합
- 수정: [`arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino`](arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino) - LED 패턴 추가

### 1.2 프로액티브 상호작용

**목표**: 사용자 개입 없이 자발적으로 말을 거는 펫 기능

**구현 사항**:

- 일정 시간 침묵 후 랜덤 멘트 ("심심해요", "뭐 하세요?")
- 시간대별 자동 인사 (아침/점심/저녁/취침 시간)
- 기념일/생일 알림 (대화 컨텍스트에서 추출)
- 활동 제안 ("날씨 좋은데 산책 어때요?")

**파일**:

- 새 파일: `server/proactive_interaction.py`
- 수정: [`server/stt_improved.py`](server/stt_improved.py) - 타이머 및 이벤트 관리

### 1.3 개성 및 이름 설정

**목표**: 사용자가 펫의 이름과 성격을 커스터마이즈

**구현 사항**:

- 설정 파일: `config.yaml` (이름, 성격, 목소리 톤)
- 성격 타입: `cheerful`, `calm`, `playful`, `serious`
- 시스템 프롬프트 자동 조정

**파일**:

- 새 파일: `config.yaml`
- 수정: [`server/agent_mode_improved.py`](server/agent_mode_improved.py) - 설정 로드 및 프롬프트 커스터마이즈

---

## 2단계: 실용적 홈 어시스턴트 기능

### 2.1 시간/날씨/뉴스 정보

**목표**: 일상 정보를 음성으로 제공

**구현 사항**:

- 현재 시각 및 날짜 조회
- 날씨 정보 (API 연동: OpenWeatherMap 무료)
- 간단한 뉴스 헤드라인 (RSS 피드)
- 타이머 및 알람 기능

**파일**:

- 새 파일: `server/info_services.py` - 정보 서비스 통합
- 수정: [`server/agent_mode_improved.py`](server/agent_mode_improved.py) - 도구 호출 통합

### 2.2 스마트홈 통합 (선택적)

**목표**: 간단한 IoT 기기 제어 (조명, 온도계)

**구현 사항**:

- MQTT 프로토콜 지원
- Home Assistant 웹훅 통합
- 기본 명령: "불 켜줘", "온도 알려줘"

**파일**:

- 새 파일: `server/smart_home.py`
- 수정: [`server/commands.yaml`](server/commands.yaml) - 스마트홈 명령 추가

### 2.3 일정 및 리마인더

**목표**: 간단한 일정 관리 및 알림

**구현 사항**:

- 일정 저장 ("내일 오후 3시 회의 있어")
- 주기적 확인 및 알림
- JSON 파일 기반 저장

**파일**:

- 새 파일: `server/scheduler.py`
- 수정: [`server/agent_mode_improved.py`](server/agent_mode_improved.py) - 일정 관리 통합

---

## 3단계: 코드 품질 및 안정성 개선

### 3.1 Arduino 코드 버그 수정

**문제점**:

- Line 448: `M5.Mic.setSampleRate(SR);` 다음에 `s` 오타
- 에러 처리 부족
- 하드코딩된 WiFi 정보

**수정 사항**:

- 문법 오류 수정
- WiFi 설정을 별도 헤더 파일로 분리 (`config.h`)
- 에러 로깅 강화
- OTA 업데이트 지원 (선택적)

**파일**:

- 수정: [`arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino`](arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino)
- 새 파일: `arduino/atom_echo_m5stack_esp32_ino/config.h`

### 3.2 설정 관리 통합

**목표**: 모든 설정을 중앙에서 관리

**구현 사항**:

- `config.yaml` 생성 (서버 포트, 모델 크기, 음성, 감정 등)
- 환경 변수 지원 (`.env` 파일)
- 설정 검증 및 기본값

**파일**:

- 새 파일: `config.yaml`, `.env.example`
- 수정: 모든 Python 서버 파일 - 설정 로드 로직 추가

### 3.3 로깅 및 모니터링

**목표**: 디버깅 및 운영 가시성 향상

**구현 사항**:

- 구조화된 로그 (JSON 형식)
- 로그 레벨 설정
- 성능 메트릭 (응답 시간, 오류율)
- 선택적: 웹 대시보드

**파일**:

- 새 파일: `server/logger_config.py`
- 수정: 모든 Python 파일 - 로거 사용 표준화

---

## 4단계: 추가 기능 (선택적)

### 4.1 웨이크워드 감지

**목표**: "헤이 (이름)" 으로 활성화

**구현 사항**:

- Porcupine 또는 Snowboy 라이브러리 사용
- 항상 대기 모드
- 웨이크워드 감지 시에만 STT 활성화

**파일**:

- 새 파일: `server/wake_word.py`
- 수정: [`server/stt_improved.py`](server/stt_improved.py)

### 4.2 다중 서보 지원

**목표**: 더 풍부한 움직임 표현 (고개, 팔 등)

**구현 사항**:

- 최대 4개 서보 지원
- 동기화된 동작 패턴
- 애니메이션 시퀀스 정의

**파일**:

- 수정: [`arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino`](arduino/atom_echo_m5stack_esp32_ino/atom_echo_m5stack_esp32_ino.ino)
- 수정: [`server/commands.yaml`](server/commands.yaml)

### 4.3 오프라인 모드

**목표**: 서버 없이도 기본 기능 동작

**구현 사항**:

- ESP32에 작은 STT 모델 (ESP32-S3 필요)
- 사전 정의된 명령어만 로컬 처리
- 서버 연결 시 풀 기능 활성화

**파일**:

- 새 버전: `arduino/atom_echo_offline/`

---

## 우선순위 및 단계별 실행

### 높은 우선순위 (즉시 시작)

1. **Arduino 버그 수정** (3.1) - 현재 코드 문법 오류 해결
2. **감정 시스템 기본** (1.1) - 펫 느낌을 위한 핵심 기능
3. **시간/날씨 정보** (2.1) - 실용적 가치 높음

### 중간 우선순위 (1-2주 내)

4. **프로액티브 상호작용** (1.2) - 펫다움 강화
5. **설정 관리** (3.2) - 유지보수성 향상
6. **일정 관리** (2.3) - 어시스턴트 핵심 기능

### 낮은 우선순위 (장기)

7. **스마트홈 통합** (2.2) - 선택적, 환경 의존적
8. **웨이크워드** (4.1) - UX 향상이지만 복잡도 높음
9. **다중 서보** (4.2) - 하드웨어 추가 필요

---

## 예상 효과

### 펫 기능

- 감정 표현으로 더 생동감 있는 상호작용
- 자발적 대화로 동반자 느낌
- 개성 커스터마이즈로 애착 형성

### 어시스턴트 기능

- 실생활 유용 정보 제공
- 일정 관리로 생산성 향상
- 스마트홈 통합으로 편의성 증대

### 코드 품질

- 버그 감소, 유지보수성 향상
- 설정 관리 간소화
- 모니터링으로 문제 조기 발견