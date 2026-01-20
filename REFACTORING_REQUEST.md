# LLM_Arduino 프로젝트 리팩토링 요청

## 프로젝트 개요

**목적**: M5Stack Atom Echo(ESP32) 기반 음성 인식 로봇 시스템
- ESP32가 내장 마이크로 16kHz 오디오를 실시간 스트리밍
- PC 서버에서 Whisper STT로 음성 인식
- 두 가지 모드 지원:
  1. **Robot Mode**: 간단한 서보 제어 명령 (각도 설정, 회전 등)
  2. **Agent Mode**: LLM 기반 대화 + TTS 응답

**현재 구조**:
```
LLM_Arduino/
├── arduino/atom_echo_m5stack_esp32_ino/
│   └── atom_echo_m5stack_esp32_ino.ino  (ESP32 펌웨어, ~700줄)
└── server/
    ├── stt.py                            (메인 서버, ~500줄)
    ├── robot_mode.py                     (로봇 모드 핸들러)
    ├── agent_mode.py                     (에이전트 모드 핸들러)
    ├── commands.yaml                     (명령어 설정)
    └── requirements.txt
```

**프로토콜**: TCP 소켓 기반 바이너리 패킷
- ESP32 → PC: `0x01` START, `0x02` AUDIO(PCM16LE), `0x03` END, `0x10` PING
- PC → ESP32: `0x11` JSON CMD, `0x12` AUDIO_OUT(PCM16LE)

**핵심 기능**:
- VAD(Voice Activity Detection) 기반 음성 구간 감지
- 200ms 프리롤 버퍼로 음성 시작 부분 보존
- Whisper STT (faster-whisper, tiny/small 모델)
- 음성 품질 검증 (RMS, peak, clipping 체크)
- 에너지 기반 트리밍 및 정규화
- 서보 모터 제어 (0-180도)
- LED 감정 표현 (색상 변경)
- TTS 오디오 스트리밍 재생

---

## 리팩토링 목표

### 1. 완전한 모듈화 (Modularization)

**현재 문제점**:
- `stt.py`가 500줄 이상으로 비대함 (네트워크, STT, 오디오 처리, 프로토콜 등 혼재)
- Arduino 코드가 700줄 단일 파일 (setup/loop에 모든 로직 집중)
- 함수들이 전역 변수에 강하게 의존
- 테스트 불가능한 구조
- 알 수 없는 이유로 동작하지 않으며, Arduino 코드를 수정하여 upload 할 때마다 다양한 오류 발생 (코드 문법 오류 등)

**요구사항**:
- **서버 측 모듈 분리**:
  - `protocol.py`: 패킷 송수신, 프로토콜 상수 정의
  - `audio_processor.py`: 오디오 품질 검증, 트리밍, 정규화, WAV 저장
  - `stt_engine.py`: Whisper 모델 로딩/추론, 스레드 안전성 보장
  - `connection_manager.py`: TCP 연결 관리, 재연결 로직, 타임아웃 처리
  - `job_queue.py`: 작업 큐 관리 (STT, TTS 작업 분리)
  - `robot_mode.py`: 로봇 명령 파싱 (이미 존재, 개선 필요)
  - `agent_mode.py`: LLM 대화 처리 (이미 존재, 개선 필요)
  - `server.py`: 메인 서버 (각 모듈 조합, 최소한의 코드)

- **Arduino 측 모듈 분리** (가능한 범위 내):
  - 별도 `.h` 파일로 분리:
    - `vad.h`: VAD 로직 (노이즈 플로어, 임계값 계산)
    - `protocol.h`: 패킷 송수신 함수
    - `connection.h`: WiFi/서버 연결 관리
    - `audio_buffer.h`: 프리롤 버퍼 관리
    - `servo_control.h`: 서보 모터 제어
    - `led_control.h`: LED 감정 표현
  - `.ino` 파일은 setup/loop만 유지

### 2. 통합 테스트 및 단위 테스트 기능

**요구사항**:
- **서버 측 테스트**:
  - `tests/test_protocol.py`: 패킷 인코딩/디코딩 테스트
  - `tests/test_audio_processor.py`: 오디오 처리 함수 테스트
  - `tests/test_stt_engine.py`: STT 모델 로딩/추론 테스트 (mock 가능)
  - `tests/test_connection.py`: 연결 관리 테스트 (mock socket)
  - `tests/integration_test.py`: 전체 시스템 통합 테스트
  - `tests/mock_esp32.py`: ESP32 시뮬레이터 (테스트용 클라이언트)

- **Arduino 측 테스트**:
  - `test_mode.ino`: 각 모듈별 독립 테스트 모드
    - WiFi 연결 테스트
    - 서버 연결 테스트
    - 마이크 녹음 테스트
    - 스피커 재생 테스트
    - 서보 동작 테스트
    - LED 테스트
  - 시리얼 명령으로 각 테스트 실행 가능

### 3. 디버깅 용이성 개선

**현재 문제점**:
- 로그가 너무 많거나 중요한 정보가 묻힘
- 에러 발생 시 어느 모듈에서 문제인지 파악 어려움
- 연결 끊김 시 원인 추적 불가

**요구사항**:
- **구조화된 로깅**:
  - 로그 레벨 분리: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
  - 모듈별 로거 사용 (`logging.getLogger(__name__)`)
  - 설정 파일로 로그 레벨 제어 (`config.yaml`)
  - 중요 이벤트만 INFO 레벨로 출력:
    - 연결/연결 해제
    - STT 결과
    - 명령 실행
    - 에러 발생
  - 상세 디버그 정보는 DEBUG 레벨로 분리

- **에러 추적**:
  - 각 모듈에서 발생하는 예외를 명확히 로깅
  - 연결 끊김 원인 분류 (타임아웃, 네트워크 에러, 프로토콜 에러)
  - 스택 트레이스 포함 (개발 모드)

- **상태 모니터링**:
  - 현재 상태를 주기적으로 출력 (연결 상태, 큐 크기, 모델 로드 상태)
  - 성능 메트릭 (STT 처리 시간, 오디오 버퍼 크기)

### 4. 로그 출력 최적화

**요구사항**:
- 불필요한 로그 제거:
  - 매 프레임마다 출력되는 로그 삭제
  - QC(품질 체크) 로그는 DEBUG 레벨로 이동
  - PING 로그 제거 (또는 DEBUG 레벨)
  
- 의미 있는 로그만 유지:
  - 음성 인식 시작/종료
  - STT 결과 텍스트
  - 명령 실행 결과
  - 에러 및 경고

- 로그 포맷 개선:
  - 타임스탬프, 모듈명, 레벨, 메시지 명확히 구분
  - 예: `2024-01-15 10:30:45 | protocol.INFO | 📡 Client connected: 192.168.1.100`

### 5. 연결성 및 무한루프 방지

**현재 문제점**:
- 연결 끊김 후 재연결 로직이 불안정
- 타임아웃 처리가 일부 누락
- 무한 대기 가능성 (recv_exact, 큐 대기 등)
- 스레드 종료 시 데드락 가능성

**요구사항**:
- **연결 관리 강화**:
  - 모든 소켓 작업에 타임아웃 설정
  - 연결 끊김 감지 즉시 정리 및 재연결 시도
  - 재연결 시 지수 백오프 (exponential backoff) 적용
  - 최대 재시도 횟수 제한

- **무한루프 방지**:
  - 모든 while 루프에 탈출 조건 명확히 설정
  - 타임아웃 기반 루프 종료
  - 큐 대기 시 timeout 파라미터 사용
  - 스레드 종료 시그널 (Event 객체) 사용

- **리소스 정리**:
  - 연결 종료 시 모든 리소스 해제 (소켓, 스레드, 큐)
  - Context manager 사용 (`with` 문)
  - 예외 발생 시에도 정리 보장 (`finally` 블록)

### 6. 큐 기반 작업 관리

**현재 문제점**:
- STT 작업 큐가 가득 차면 음성 데이터 손실
- TTS 작업과 STT 작업이 동일 큐 사용 (우선순위 없음)
- 큐 오버플로우 시 서버 다운 가능성

**요구사항**:
- **분리된 큐 시스템**:
  - `stt_queue`: STT 작업 전용 (maxsize=4)
  - `tts_queue`: TTS 작업 전용 (maxsize=2)
  - `command_queue`: 명령 처리 전용 (maxsize=10)

- **큐 오버플로우 처리**:
  - 큐가 가득 찬 경우 가장 오래된 작업 제거 (FIFO)
  - 또는 새 작업 거부 + 경고 로그
  - 큐 크기 모니터링 및 경고

- **우선순위 큐**:
  - 긴급 명령(STOP, 모드 전환)은 우선 처리
  - `queue.PriorityQueue` 사용 고려

- **워커 스레드 관리**:
  - 각 큐마다 전용 워커 스레드
  - 스레드 풀 사용 고려 (`concurrent.futures.ThreadPoolExecutor`)
  - 스레드 안전성 보장 (Lock, Event 사용)

### 7. 상용 제품 수준 구현

**요구사항**:
- **설정 파일 분리**:
  - `config.yaml`: 서버 설정 (포트, 모델, 로그 레벨 등)
  - `arduino/config.h`: WiFi, 서버 IP, VAD 파라미터 등
  - 환경 변수 지원 (`.env` 파일)

- **에러 핸들링**:
  - 모든 예외를 적절히 처리
  - 사용자 친화적 에러 메시지
  - 복구 가능한 에러는 자동 복구 시도

- **성능 최적화**:
  - 불필요한 메모리 복사 제거
  - 오디오 버퍼 재사용
  - GPU 메모리 관리 (CUDA OOM 방지)

- **문서화**:
  - 각 모듈에 docstring 추가
  - API 문서 생성 (Sphinx 또는 MkDocs)
  - 사용자 매뉴얼 작성

- **배포 준비**:
  - Docker 컨테이너화 (서버)
  - systemd 서비스 파일 (Linux)
  - 자동 시작 스크립트
  - 버전 관리 (semantic versioning)

- **모니터링 및 헬스체크**:
  - 서버 상태 확인 엔드포인트 (HTTP `/health`)
  - 메트릭 수집 (Prometheus 호환)
  - 로그 집계 (ELK 스택 호환)

---

## 리팩토링 우선순위

1. **Phase 1 - 모듈화 및 구조 개선** (가장 중요)
   - 서버 코드 모듈 분리
   - Arduino 코드 헤더 파일 분리
   - 전역 변수 제거, 클래스 기반 설계

2. **Phase 2 - 안정성 강화**
   - 연결 관리 개선
   - 무한루프 방지
   - 큐 시스템 구현
   - 에러 핸들링 강화

3. **Phase 3 - 디버깅 및 로깅**
   - 로그 시스템 개선
   - 테스트 코드 작성
   - 디버그 모드 구현

4. **Phase 4 - 상용화 준비**
   - 설정 파일 분리
   - 문서화
   - 배포 스크립트
   - 모니터링 시스템

---

## 기술 스택 및 제약사항

**서버**:
- Python 3.9+
- faster-whisper (STT)
- PyTorch (LLM, TTS)
- CUDA 지원 (선택적)
- 표준 라이브러리 우선 (외부 의존성 최소화)

**Arduino**:
- ESP32 (M5Stack Atom Echo)
- Arduino IDE / PlatformIO
- M5Unified 라이브러리
- ESP32Servo 라이브러리
- 메모리 제약 (SRAM ~520KB)

**프로토콜**:
- TCP 소켓 (바이너리 패킷)
- 하위 호환성 유지 (기존 프로토콜 변경 최소화)

---

## 예상 결과물

리팩토링 후 프로젝트 구조:

```
LLM_Arduino/
├── arduino/
│   ├── atom_echo_m5stack_esp32_ino/
│   │   ├── atom_echo_m5stack_esp32_ino.ino  (~100줄)
│   │   ├── config.h
│   │   ├── vad.h / vad.cpp
│   │   ├── protocol.h / protocol.cpp
│   │   ├── connection.h / connection.cpp
│   │   ├── audio_buffer.h / audio_buffer.cpp
│   │   ├── servo_control.h / servo_control.cpp
│   │   └── led_control.h / led_control.cpp
│   └── test_mode/
│       └── test_mode.ino
├── server/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── protocol.py
│   │   ├── audio_processor.py
│   │   ├── stt_engine.py
│   │   ├── connection_manager.py
│   │   ├── job_queue.py
│   │   ├── robot_mode.py
│   │   ├── agent_mode.py
│   │   └── utils.py
│   ├── tests/
│   │   ├── test_protocol.py
│   │   ├── test_audio_processor.py
│   │   ├── test_stt_engine.py
│   │   ├── test_connection.py
│   │   ├── integration_test.py
│   │   └── mock_esp32.py
│   ├── server.py  (~150줄)
│   ├── config.yaml
│   ├── requirements.txt
│   └── README.md
├── docs/
│   ├── API.md
│   ├── PROTOCOL.md
│   └── USER_GUIDE.md
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── README.md
```

---

## 요청 사항

위 내용을 바탕으로 **전체 프로젝트를 리팩토링**해주세요.

**중요 원칙**:
1. 기존 기능은 모두 유지 (하위 호환성)
2. 각 모듈은 독립적으로 테스트 가능하도록 설계
3. 코드 중복 최소화 (DRY 원칙)
4. 명확한 책임 분리 (Single Responsibility Principle)
5. 에러 처리 철저히 (Fail-safe 설계)
6. 성능 저하 없도록 최적화 유지
7. 주석 및 docstring 충실히 작성

**구현 순서**:
1. 서버 측 모듈 분리 및 리팩토링
2. Arduino 측 헤더 파일 분리
3. 테스트 코드 작성
4. 설정 파일 및 문서 작성
5. 통합 테스트 및 검증

각 단계마다 동작 확인 후 다음 단계로 진행해주세요.
