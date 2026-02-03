# LLM Arduino 시스템 구성도

## 1. 전체 시스템 개요

```mermaid
graph TB
    subgraph ESP32["ESP32 (M5Stack Atom Echo)"]
        MIC[마이크<br/>16kHz Audio]
        SPK[스피커<br/>Audio Output]
        LED[RGB LED<br/>상태 표시]
        SERVO[서보 모터<br/>0-180도]
        WIFI[WiFi<br/>TCP 통신]
        VAD[VAD<br/>음성 활동 감지]
        PROTO_ESP[프로토콜<br/>핸들러]
    end
    
    subgraph SERVER["Python 서버 (PC)"]
        TCP[TCP 서버<br/>:5001]
        STT[STT Engine<br/>Whisper]
        LLM[LLM<br/>Qwen2.5-0.5B]
        TTS[TTS Engine<br/>edge-tts]
        
        subgraph MODES["동작 모드"]
            ROBOT[Robot Mode<br/>서보 제어]
            AGENT[Agent Mode<br/>대화 AI]
        end
        
        subgraph SYSTEMS["보조 시스템"]
            EMOTION[Emotion System<br/>감정 분석]
            INFO[Info Services<br/>날씨/뉴스/시간]
            SCHED[Scheduler<br/>일정 관리]
            PROACTIVE[Proactive<br/>자발적 대화]
        end
    end
    
    MIC --> VAD
    VAD --> PROTO_ESP
    PROTO_ESP --> WIFI
    WIFI <--> |"패킷 송수신"| TCP
    
    TCP --> STT
    STT --> LLM
    LLM --> ROBOT
    LLM --> AGENT
    
    AGENT --> EMOTION
    AGENT --> INFO
    AGENT --> SCHED
    AGENT --> PROACTIVE
    
    ROBOT --> |"명령 JSON"| TCP
    AGENT --> TTS
    TTS --> |"오디오"| TCP
    
    TCP --> WIFI
    WIFI --> PROTO_ESP
    PROTO_ESP --> LED
    PROTO_ESP --> SERVO
    PROTO_ESP --> SPK
    
    style ESP32 fill:#e1f5ff
    style SERVER fill:#fff4e1
    style MODES fill:#f0f0f0
    style SYSTEMS fill:#f0f0f0
```

## 2. 통신 프로토콜 상세

```mermaid
sequenceDiagram
    participant ESP as ESP32
    participant SRV as Server
    participant STT as Whisper STT
    participant LLM as Qwen LLM
    participant TTS as Edge TTS
    
    Note over ESP,SRV: 연결 및 유지
    ESP->>SRV: WiFi 연결
    loop 3초마다
        ESP->>SRV: PING (0x10)
        SRV-->>ESP: PONG (0x1F)
    end
    
    Note over ESP,SRV: 음성 녹음 및 전송
    ESP->>ESP: VAD 음성 감지
    ESP->>SRV: START (0x01)
    ESP->>SRV: 프리롤 버퍼 (200ms)
    loop 20ms마다
        ESP->>SRV: AUDIO (0x02)<br/>320 샘플
    end
    ESP->>SRV: END (0x03)
    
    Note over ESP,SRV: Robot Mode 처리
    SRV->>STT: PCM 오디오
    STT->>SRV: "왼쪽으로"
    SRV->>LLM: 텍스트 정제
    LLM->>SRV: "왼쪽으로"
    SRV->>LLM: 명령 해석
    LLM->>SRV: {"action":"SERVO_SET","angle":30}
    SRV->>ESP: CMD (0x11) + JSON
    ESP->>ESP: 서보 제어 + LED
    
    Note over ESP,SRV: Agent Mode 처리
    SRV->>STT: PCM 오디오
    STT->>SRV: "오늘 날씨 어때?"
    SRV->>LLM: 대화 생성
    LLM->>SRV: "오늘은 맑고 화창해요"
    SRV->>TTS: 응답 텍스트
    TTS->>SRV: MP3 오디오
    SRV->>SRV: 16kHz PCM 변환
    SRV->>ESP: AUDIO_OUT (0x12) + PCM
    ESP->>ESP: 스피커 재생
```

## 3. ESP32 소프트웨어 구조

```mermaid
graph LR
    subgraph MAIN["atom_echo_m5stack_esp32_ino.ino"]
        SETUP[setup]
        LOOP[loop]
    end
    
    subgraph MODULES["모듈"]
        CONFIG[config.h<br/>WiFi 설정]
        CONN[connection.cpp<br/>WiFi 연결 관리]
        PROTO[protocol.cpp<br/>패킷 송수신]
        VAD_M[vad.cpp<br/>음성 활동 감지]
        LED_M[led_control.cpp<br/>RGB LED 제어]
        SERVO_M[servo_control.cpp<br/>서보 제어]
        AUDIO_M[audio_buffer.cpp<br/>프리롤 버퍼]
    end
    
    subgraph HW["하드웨어"]
        M5[M5Unified<br/>MIC/SPK]
        WIFI_HW[WiFi]
        LED_HW[RGB LED]
        SERVO_HW[서보 모터]
    end
    
    SETUP --> CONFIG
    SETUP --> CONN
    SETUP --> PROTO
    SETUP --> VAD_M
    SETUP --> LED_M
    SETUP --> SERVO_M
    SETUP --> M5
    
    LOOP --> CONN
    LOOP --> PROTO
    LOOP --> VAD_M
    LOOP --> LED_M
    LOOP --> SERVO_M
    
    CONN --> WIFI_HW
    PROTO --> WIFI_HW
    VAD_M --> M5
    AUDIO_M --> M5
    LED_M --> LED_HW
    SERVO_M --> SERVO_HW
    
    style MAIN fill:#ffebee
    style MODULES fill:#e8f5e9
    style HW fill:#e3f2fd
```

## 4. 서버 소프트웨어 구조

```mermaid
graph TB
    subgraph MAIN_S["server.py (메인)"]
        MAIN_LOOP[메인 루프<br/>연결 수락]
        CONN_HANDLER[handle_connection<br/>클라이언트 처리]
        WORKER[Worker Thread<br/>STT/LLM 처리]
    end
    
    subgraph CORE["핵심 모듈 (src/)"]
        STT_E[stt_engine.py<br/>Whisper STT]
        ROBOT_M[robot_mode.py<br/>명령 파싱/제어]
        AGENT_M[agent_mode.py<br/>대화 AI]
        AUDIO_P[audio_processor.py<br/>오디오 정규화]
        PROTO_S[protocol.py<br/>패킷 송수신]
        CONN_M[connection_manager.py<br/>TCP 연결]
        QUEUE[job_queue.py<br/>작업 큐]
    end
    
    subgraph FEATURES["기능 시스템"]
        EMOTION_S[emotion_system.py<br/>감정 분석]
        INFO_S[info_services.py<br/>날씨/뉴스/시간]
        SCHED_S[scheduler.py<br/>일정/리마인더]
        PROACT_S[proactive_interaction.py<br/>자발적 상호작용]
    end
    
    subgraph CONFIG_S["설정"]
        CFG_YAML[config.yaml<br/>전역 설정]
        CMD_YAML[commands.yaml<br/>로봇 명령]
        CFG_LOADER[config_loader.py<br/>설정 로더]
        ENV[.env<br/>API 키]
    end
    
    subgraph UTILS["유틸리티"]
        LOG[logging_setup.py<br/>로깅]
        UTILS[utils.py<br/>헬퍼 함수]
    end
    
    MAIN_LOOP --> CONN_HANDLER
    CONN_HANDLER --> WORKER
    CONN_HANDLER --> CONN_M
    CONN_HANDLER --> PROTO_S
    CONN_HANDLER --> QUEUE
    
    WORKER --> STT_E
    WORKER --> ROBOT_M
    WORKER --> AGENT_M
    WORKER --> AUDIO_P
    
    ROBOT_M --> CMD_YAML
    AGENT_M --> EMOTION_S
    AGENT_M --> INFO_S
    AGENT_M --> SCHED_S
    AGENT_M --> PROACT_S
    
    CONN_HANDLER --> CFG_LOADER
    CFG_LOADER --> CFG_YAML
    CFG_LOADER --> ENV
    
    MAIN_LOOP --> LOG
    WORKER --> LOG
    AGENT_M --> UTILS
    ROBOT_M --> UTILS
    
    style MAIN_S fill:#ffebee
    style CORE fill:#e1f5fe
    style FEATURES fill:#f3e5f5
    style CONFIG_S fill:#fff9c4
    style UTILS fill:#e0f2f1
```

## 5. 데이터 흐름 (Robot Mode)

```mermaid
flowchart TD
    START([사용자 음성])
    
    MIC[마이크 녹음<br/>16kHz, 20ms]
    VAD_CHECK{VAD<br/>음성 감지?}
    BUFFER[프리롤 버퍼<br/>200ms 유지]
    SEND_START[START 전송]
    SEND_AUDIO[AUDIO 전송<br/>20ms마다]
    SILENCE{침묵<br/>감지?}
    SEND_END[END 전송]
    
    RECV[서버 수신]
    QC[품질 체크<br/>RMS/Peak]
    QC_OK{품질<br/>OK?}
    TRIM[무음 제거<br/>정규화]
    STT_PROC[Whisper STT]
    TEXT{텍스트<br/>있음?}
    
    LLM_REFINE[LLM 정제<br/>오타 수정]
    PARSE[commands.yaml<br/>패턴 매칭]
    MATCH{명령<br/>매칭?}
    LLM_INTERP[LLM 해석<br/>JSON 생성]
    
    ACTION[{"action":"SERVO_SET"<br/>"angle":90}]
    SEND_CMD[CMD 전송]
    
    ESP_RECV[ESP32 수신]
    SERVO_CTRL[서보 제어]
    LED_CTRL[LED 표시]
    
    FINISH([완료])
    
    START --> MIC
    MIC --> VAD_CHECK
    VAD_CHECK -->|No| BUFFER
    BUFFER --> MIC
    VAD_CHECK -->|Yes| SEND_START
    SEND_START --> SEND_AUDIO
    SEND_AUDIO --> SILENCE
    SILENCE -->|No| SEND_AUDIO
    SILENCE -->|Yes| SEND_END
    
    SEND_END --> RECV
    RECV --> QC
    QC --> QC_OK
    QC_OK -->|No| FINISH
    QC_OK -->|Yes| TRIM
    TRIM --> STT_PROC
    STT_PROC --> TEXT
    TEXT -->|No| FINISH
    TEXT -->|Yes| LLM_REFINE
    
    LLM_REFINE --> PARSE
    PARSE --> MATCH
    MATCH -->|Yes| ACTION
    MATCH -->|No| LLM_INTERP
    LLM_INTERP --> ACTION
    
    ACTION --> SEND_CMD
    SEND_CMD --> ESP_RECV
    ESP_RECV --> SERVO_CTRL
    ESP_RECV --> LED_CTRL
    SERVO_CTRL --> FINISH
    LED_CTRL --> FINISH
    
    style START fill:#c8e6c9
    style FINISH fill:#ffccbc
    style VAD_CHECK fill:#fff9c4
    style QC_OK fill:#fff9c4
    style TEXT fill:#fff9c4
    style MATCH fill:#fff9c4
    style SILENCE fill:#fff9c4
```

## 6. 데이터 흐름 (Agent Mode)

```mermaid
flowchart TD
    START([사용자 음성])
    
    MIC[마이크 녹음]
    VAD[VAD 처리]
    SEND[START+AUDIO+END]
    
    RECV[서버 수신]
    STT[Whisper STT]
    TEXT{텍스트<br/>추출}
    
    INFO_CHK{정보<br/>요청?}
    INFO_PROC[Info Services<br/>날씨/뉴스/시간]
    
    SCHED_CHK{일정<br/>관련?}
    SCHED_PROC[Scheduler<br/>일정 추가/조회]
    
    EMOTION[Emotion Analysis<br/>감정 분석]
    HISTORY[대화 히스토리<br/>컨텍스트]
    
    LLM_GEN[LLM 응답 생성<br/>Qwen2.5]
    
    RESPONSE[응답 텍스트]
    TTS[Edge TTS<br/>MP3 생성]
    CONVERT[16kHz PCM<br/>변환 + 정규화]
    
    SEND_AUDIO[AUDIO_OUT 전송]
    ESP_PLAY[스피커 재생]
    
    SAVE_CONV[대화 저장<br/>백업]
    
    PROACTIVE{프로액티브<br/>타이머?}
    PROACT_MSG[자발적 메시지<br/>생성]
    
    FINISH([완료])
    
    START --> MIC
    MIC --> VAD
    VAD --> SEND
    SEND --> RECV
    RECV --> STT
    STT --> TEXT
    
    TEXT -->|No| FINISH
    TEXT -->|Yes| INFO_CHK
    
    INFO_CHK -->|Yes| INFO_PROC
    INFO_PROC --> RESPONSE
    
    INFO_CHK -->|No| SCHED_CHK
    SCHED_CHK -->|Yes| SCHED_PROC
    SCHED_PROC --> RESPONSE
    
    SCHED_CHK -->|No| EMOTION
    EMOTION --> HISTORY
    HISTORY --> LLM_GEN
    LLM_GEN --> RESPONSE
    
    RESPONSE --> TTS
    TTS --> CONVERT
    CONVERT --> SEND_AUDIO
    SEND_AUDIO --> ESP_PLAY
    ESP_PLAY --> SAVE_CONV
    SAVE_CONV --> PROACTIVE
    
    PROACTIVE -->|Yes| PROACT_MSG
    PROACT_MSG --> TTS
    PROACTIVE -->|No| FINISH
    
    style START fill:#c8e6c9
    style FINISH fill:#ffccbc
    style INFO_CHK fill:#fff9c4
    style SCHED_CHK fill:#fff9c4
    style TEXT fill:#fff9c4
    style PROACTIVE fill:#fff9c4
```

## 7. 패킷 프로토콜 명세

```mermaid
graph LR
    subgraph ESP_TO_SERVER["ESP32 → Server"]
        P_START["0x01 START<br/>음성 시작"]
        P_AUDIO["0x02 AUDIO<br/>PCM16LE 데이터"]
        P_END["0x03 END<br/>음성 종료"]
        P_PING["0x10 PING<br/>연결 유지"]
    end
    
    subgraph SERVER_TO_ESP["Server → ESP32"]
        P_CMD["0x11 CMD<br/>JSON 명령"]
        P_AUDIO_OUT["0x12 AUDIO_OUT<br/>PCM16LE 재생"]
        P_PONG["0x1F PONG<br/>핑 응답"]
    end
    
    subgraph PACKET_FORMAT["패킷 구조"]
        BYTE1["[1 byte]<br/>Type"]
        BYTE2["[2 bytes LE]<br/>Length"]
        PAYLOAD["[N bytes]<br/>Payload"]
    end
    
    BYTE1 --> BYTE2
    BYTE2 --> PAYLOAD
    
    style ESP_TO_SERVER fill:#e1f5fe
    style SERVER_TO_ESP fill:#fff3e0
    style PACKET_FORMAT fill:#f3e5f5
```

## 8. 감정 시스템 구조

```mermaid
graph TB
    INPUT[사용자 입력<br/>텍스트]
    
    ANALYZE[감정 분석<br/>키워드 매칭]
    
    subgraph EMOTIONS["감정 상태"]
        HAPPY[😊 Happy<br/>기쁨]
        SAD[😢 Sad<br/>슬픔]
        EXCITED[🤩 Excited<br/>흥분]
        SLEEPY[😴 Sleepy<br/>졸림]
        ANGRY[😠 Angry<br/>화남]
        NEUTRAL[😐 Neutral<br/>중립]
    end
    
    subgraph LED_PATTERNS["LED 패턴"]
        LED_HAPPY[초록색<br/>점멸]
        LED_SAD[파란색<br/>느린 점멸]
        LED_EXCITED[빠른 무지개]
        LED_SLEEPY[어두운 보라]
        LED_ANGRY[빨간색<br/>빠른 점멸]
        LED_NEUTRAL[흰색<br/>고정]
    end
    
    subgraph SERVO_PATTERNS["서보 동작"]
        S_HAPPY[좌우 흔들기]
        S_SAD[천천히 숙이기]
        S_EXCITED[빠른 왕복]
        S_SLEEPY[느린 하강]
        S_ANGRY[급격한 움직임]
        S_NEUTRAL[중앙 위치]
    end
    
    INPUT --> ANALYZE
    
    ANALYZE --> HAPPY
    ANALYZE --> SAD
    ANALYZE --> EXCITED
    ANALYZE --> SLEEPY
    ANALYZE --> ANGRY
    ANALYZE --> NEUTRAL
    
    HAPPY --> LED_HAPPY
    SAD --> LED_SAD
    EXCITED --> LED_EXCITED
    SLEEPY --> LED_SLEEPY
    ANGRY --> LED_ANGRY
    NEUTRAL --> LED_NEUTRAL
    
    HAPPY --> S_HAPPY
    SAD --> S_SAD
    EXCITED --> S_EXCITED
    SLEEPY --> S_SLEEPY
    ANGRY --> S_ANGRY
    NEUTRAL --> S_NEUTRAL
    
    style INPUT fill:#e8f5e9
    style EMOTIONS fill:#fff9c4
    style LED_PATTERNS fill:#e1f5fe
    style SERVO_PATTERNS fill:#f3e5f5
```

## 9. 디렉토리 구조

```mermaid
graph TB
    ROOT[LLM_Arduino/]
    
    subgraph ARDUINO_DIR["arduino/"]
        ATOM[atom_echo_m5stack_esp32_ino/]
        INO[*.ino 메인]
        CPP[*.cpp 모듈]
        H[*.h 헤더]
        CFG_H[config.h 설정]
    end
    
    subgraph SERVER_DIR["server/"]
        MAIN_PY[server.py]
        
        subgraph SRC["src/"]
            SRC_FILES[agent_mode.py<br/>robot_mode.py<br/>stt_engine.py<br/>...]
        end
        
        YAML[config.yaml<br/>commands.yaml]
        FEAT[emotion_system.py<br/>info_services.py<br/>scheduler.py<br/>proactive_interaction.py]
        CFG_PY[config_loader.py]
        ENV_FILE[.env]
    end
    
    subgraph DOCS["docs/"]
        API_MD[API.md]
        PROTO_MD[PROTOCOL.md]
        USER_MD[USER_GUIDE.md]
    end
    
    subgraph DOCKER["docker/"]
        DOCKERFILE[Dockerfile]
        COMPOSE[docker-compose.yml]
    end
    
    MD_FILES[README.md<br/>FEATURES_GUIDE.md<br/>IMPLEMENTATION_SUMMARY.md<br/>SYSTEM_ARCHITECTURE.md]
    
    ROOT --> ARDUINO_DIR
    ROOT --> SERVER_DIR
    ROOT --> DOCS
    ROOT --> DOCKER
    ROOT --> MD_FILES
    
    ATOM --> INO
    ATOM --> CPP
    ATOM --> H
    ATOM --> CFG_H
    
    SERVER_DIR --> MAIN_PY
    SERVER_DIR --> SRC
    SERVER_DIR --> YAML
    SERVER_DIR --> FEAT
    SERVER_DIR --> CFG_PY
    SERVER_DIR --> ENV_FILE
    
    style ROOT fill:#ffebee
    style ARDUINO_DIR fill:#e1f5fe
    style SERVER_DIR fill:#f3e5f5
    style DOCS fill:#e8f5e9
    style DOCKER fill:#fff9c4
```

## 10. 주요 기능 흐름

```mermaid
mindmap
  root((LLM Arduino<br/>System))
    음성 인식
      VAD 음성 감지
      16kHz 스트리밍
      Whisper STT
      텍스트 정제
    로봇 제어
      서보 모터 제어
      0-180도 각도
      명령 패턴 매칭
      LLM 해석
    대화 AI
      자연어 처리
      대화 히스토리
      감정 분석
      개성 설정
    음성 출력
      Edge TTS
      16kHz PCM
      볼륨 정규화
      스피커 재생
    정보 서비스
      현재 시간
      날씨 정보
      뉴스 헤드라인
      타이머 알람
    일정 관리
      일정 추가
      일정 조회
      자동 리마인더
      JSON 저장
    프로액티브
      자발적 대화
      시간대별 인사
      침묵 후 말 걸기
      활동 제안
    감정 표현
      6가지 감정
      LED 패턴
      서보 동작
      감정 인식
```

## 설정 파일 요약

### config.yaml (서버)
- 서버 설정 (host, port)
- STT 설정 (model, device)
- 어시스턴트 설정 (이름, 성격, TTS 음성)
- 로깅 설정
- 큐 설정

### commands.yaml (로봇 모드)
- 명령 패턴 정의
- 키워드 매칭
- 정규식 패턴
- 서보 각도 설정

### config.h (ESP32)
- WiFi SSID/비밀번호
- 서버 IP/포트
- LED 색상
- 오디오 설정

## 시스템 요구사항

### 하드웨어
- **ESP32**: M5Stack Atom Echo
- **PC/서버**: GPU 권장 (CUDA 지원)
- **네트워크**: 동일 LAN 환경

### 소프트웨어
- **Arduino**: M5Unified 라이브러리
- **Python**: 3.9+
- **주요 라이브러리**:
  - faster-whisper (STT)
  - transformers (LLM)
  - edge-tts (TTS)
  - numpy, librosa (오디오 처리)

## 성능 특성

- **STT 레이턴시**: ~0.5-1초 (GPU)
- **LLM 레이턴시**: ~0.2-2초
- **TTS 레이턴시**: ~1-2초
- **총 응답 시간**: ~2-4초
- **오디오 품질**: 16kHz, 16-bit PCM
- **네트워크 대역폭**: ~32KB/s (녹음 시)

---

**생성 날짜**: 2026-02-03
