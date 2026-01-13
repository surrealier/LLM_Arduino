# LLM_Arduino - 홈 어시스턴트 IoT 프로젝트

## 개요
M5Stack Atom Echo(ESP32)를 사용한 LLM 기반 홈 어시스턴트 시스템입니다.
음성 인식(STT), LLM 대화, TTS, 서보 모터 제어를 통합하여 가정용 AI 비서를 구현합니다.

## 주요 기능

### 🎯 핵심 개선 사항
1. **안정적인 서버-클라이언트 연결**
   - 자동 재연결 메커니즘
   - 하트비트(PING/PONG) 시스템
   - 연결 상태 모니터링 및 복구

2. **LLM 기반 STT 정제**
   - Qwen2.5-0.5B 모델로 음성인식 오류 자동 수정
   - "안냥하시오" → "안녕하세요" 등 자동 명확화

3. **LLM 기반 로봇 제어**
   - 자연어 명령을 LLM이 해석하여 서보 동작 결정
   - 유연한 명령 처리 (기존 키워드 매칭 + LLM 추론)

4. **영구 대화 컨텍스트**
   - 대화 내용 자동 백업 (10개 대화마다)
   - 중요 정보 자동 추출 및 저장
   - 서버 재시작 시 이전 대화 복원

5. **안정적인 음성 인식 루프**
   - 예외 처리 강화
   - 상태 복구 메커니즘
   - 메모리 관리 최적화

### 🤖 동작 모드

#### Robot Mode (로봇 모드)
- 서보 모터 제어 명령 처리
- 빠른 응답 (TTS 없음)
- 명령어: 가운데, 왼쪽, 오른쪽, 올려, 내려, 멈춰, 회전 등

#### Agent Mode (에이전트 모드)
- LLM 기반 자연어 대화
- TTS 음성 응답
- 대화 컨텍스트 유지
- 가족 정보, 일정, 선호사항 기억

## 프로젝트 구조
```
LLM_Arduino/
├── arduino/
│   └── atom_echo_m5stack_esp32_ino/
│       ├── atom_echo_improved.ino      # 개선된 ESP32 펌웨어
│       └── atom_echo_m5stack_esp32_ino.ino  # 기존 버전
├── server/
│   ├── stt_improved.py                 # 개선된 메인 서버
│   ├── robot_mode_improved.py          # LLM 기반 로봇 제어
│   ├── agent_mode_improved.py          # 대화 컨텍스트 관리
│   ├── commands.yaml                   # 로봇 명령 정의
│   ├── requirements.txt                # Python 의존성
│   └── context_backup/                 # 대화 백업 디렉토리 (자동 생성)
└── README.md
```

## 설치 및 설정

### 1. 하드웨어 준비
- M5Stack Atom Echo (ESP32)
- 서보 모터 (SG90 등)
- 연결: 서보 신호선 → GPIO 25번 핀

### 2. 서버 설정

#### Python 환경 (Python 3.9+ 권장)
```bash
cd server
pip install -r requirements.txt
```

#### GPU 사용 시 (권장)
```bash
# CUDA 11.8 이상 필요
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### 모델 다운로드
첫 실행 시 자동으로 다운로드됩니다:
- Whisper STT: `small` 모델 (~500MB)
- Qwen LLM: `Qwen2.5-0.5B-Instruct` (~1GB)

### 3. Arduino 설정

#### Arduino IDE 설정
1. ESP32 보드 매니저 설치
2. 라이브러리 설치:
   - M5Unified
   - ESP32Servo

#### 펌웨어 업로드
1. `atom_echo_improved.ino` 파일 열기
2. WiFi 정보 수정:
   ```cpp
   const char* SSID = "YOUR_WIFI_SSID";
   const char* PASS = "YOUR_WIFI_PASSWORD";
   const char* SERVER_IP = "YOUR_PC_IP";  // 서버 PC의 IP
   ```
3. 보드 선택: `M5Stack Atom`
4. 업로드 (115200 baud)

## 실행 방법

### 1. 서버 시작
```bash
cd server
python stt_improved.py
```

출력 예시:
```
2024-01-01 12:00:00 | INFO | Loading STT model: small on cuda...
2024-01-01 12:00:05 | INFO | STT model loaded on cuda
2024-01-01 12:00:05 | INFO | Loading Qwen2.5-0.5B-Instruct for Robot Mode on cuda...
2024-01-01 12:00:10 | INFO | Robot Mode LLM loaded.
2024-01-01 12:00:10 | INFO | Loading Qwen2.5-0.5B-Instruct for Agent Mode on cuda...
2024-01-01 12:00:15 | INFO | Agent Mode LLM loaded.
2024-01-01 12:00:15 | INFO | Context restored: 15 conversations, 5 memories
2024-01-01 12:00:15 | INFO | 🚀 Server started on 5001. Default Mode: robot
```

### 2. ESP32 전원 켜기
- 자동으로 WiFi 연결 → 서버 연결
- LED 색상:
  - 🔴 빨강: WiFi/서버 연결 중
  - 🔵 파랑: 대기 중
  - 🟢 초록: 녹음 중
  - 🟡 노랑: 음성 재생 중

## 사용 예시

### Robot Mode 명령어
```
"가운데"          → 서보 90도
"왼쪽"            → 서보 30도
"오른쪽"          → 서보 150도
"올려"            → 현재 각도 +20도
"내려"            → 현재 각도 -20도
"45도"            → 서보 45도
"멈춰"            → 정지
"에이전트 모드"   → Agent 모드로 전환
```

### Agent Mode 대화
```
사용자: "안녕하세요"
AI: "안녕하세요! 무엇을 도와드릴까요?"

사용자: "내 이름은 홍길동이야"
AI: "반갑습니다, 홍길동님! 기억하겠습니다."

사용자: "내 이름이 뭐였지?"
AI: "홍길동님이시죠!"

사용자: "로봇 모드"
AI: [로봇 모드로 전환]
```

## 프로토콜 사양

### 패킷 구조
```
[1 byte Type] [2 bytes Length (LE)] [Payload]
```

### 패킷 타입
- `0x01` START: 녹음 시작
- `0x02` AUDIO: 오디오 데이터 (PCM16LE, 16kHz, Mono)
- `0x03` END: 녹음 종료
- `0x10` PING: 클라이언트 → 서버 (3초마다)
- `0x1F` PONG: 서버 → 클라이언트
- `0x11` CMD: 서버 → 클라이언트 (JSON 명령)
- `0x12` AUDIO_OUT: 서버 → 클라이언트 (TTS 오디오)

### CMD JSON 형식
```json
{
  "action": "SERVO_SET",
  "servo": 0,
  "angle": 90,
  "sid": 123,
  "meaningful": true,
  "recognized": true
}
```

## 고급 설정

### VAD (Voice Activity Detection) 튜닝
`atom_echo_improved.ino`:
```cpp
static constexpr float VAD_ON_MUL = 3.0f;   // 음성 감지 민감도
static constexpr float VAD_OFF_MUL = 1.8f;  // 침묵 감지 민감도
static constexpr uint32_t MIN_TALK_MS = 500;     // 최소 발화 시간
static constexpr uint32_t SILENCE_END_MS = 350;  // 종료 침묵 시간
static constexpr uint32_t MAX_TALK_MS = 8000;    // 최대 발화 시간
```

### LLM 모델 변경
`stt_improved.py`:
```python
MODEL_SIZE = "small"  # Whisper: tiny, base, small, medium, large
PREFER_DEVICE = "cuda"  # cuda 또는 cpu
```

`robot_mode_improved.py` / `agent_mode_improved.py`:
```python
model_name = "Qwen/Qwen2.5-0.5B-Instruct"  # 다른 모델로 변경 가능
```

### 대화 컨텍스트 설정
`agent_mode_improved.py`:
```python
self.max_history = 20  # 유지할 최근 대화 수
self.context_backup_interval = 10  # 백업 주기
```

## 문제 해결

### WiFi 연결 실패
- SSID/비밀번호 확인
- 2.4GHz WiFi 사용 (5GHz 미지원)
- 시리얼 모니터에서 연결 상태 확인

### 서버 연결 실패
- 방화벽에서 TCP 5001 포트 허용
- 서버 IP 주소 확인 (`ipconfig` / `ifconfig`)
- 같은 네트워크에 있는지 확인

### STT 느림
- GPU 사용 권장 (CUDA 설치)
- Whisper 모델 크기 줄이기 (`tiny` 또는 `base`)
- CPU 사용 시 `int8` 양자화 자동 적용

### 음성 인식 안됨
- VAD 파라미터 조정
- 마이크에 가까이 말하기
- 배경 소음 줄이기
- 시리얼 모니터에서 RMS 값 확인

### 대화 컨텍스트 손실
- `context_backup/` 디렉토리 확인
- 백업 파일 존재 여부 확인
- 수동 백업: `latest_context.json` 복사

## 성능 최적화

### GPU 메모리 부족 시
```python
# 더 작은 모델 사용
MODEL_SIZE = "tiny"  # Whisper
model_name = "Qwen/Qwen2.5-0.5B-Instruct"  # 이미 최소 크기
```

### CPU 사용 시
```python
PREFER_DEVICE = "cpu"
# int8 양자화 자동 적용됨
```

### 네트워크 최적화
- WiFi 신호 강도 확인
- 서버와 ESP32를 가까운 거리에 배치
- 유선 LAN 사용 (서버 측)

## 확장 아이디어

1. **다중 서보 제어**
   - `commands.yaml`에서 `servo: 1, 2, 3...` 추가
   - 아두이노 코드에서 서보 배열 관리

2. **스마트홈 연동**
   - Home Assistant 통합
   - MQTT 프로토콜 추가
   - IoT 기기 제어

3. **음성 명령 확장**
   - 날씨 정보 조회
   - 타이머/알람 설정
   - 뉴스 읽기

4. **다국어 지원**
   - Whisper `language` 파라미터 변경
   - TTS 음성 변경

5. **웹 인터페이스**
   - Flask/FastAPI 웹 서버 추가
   - 실시간 대화 로그 확인
   - 설정 변경 UI

## 라이선스
MIT License

## 기여
이슈 및 PR 환영합니다!

## 참고 자료
- [M5Stack Atom Echo 문서](https://docs.m5stack.com/en/atom/atomecho)
- [Faster Whisper](https://github.com/guillaumekln/faster-whisper)
- [Qwen2.5](https://github.com/QwenLM/Qwen2.5)
- [Edge TTS](https://github.com/rany2/edge-tts)
