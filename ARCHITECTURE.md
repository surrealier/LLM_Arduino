# LLM Arduino — 시스템 아키텍처

---

## 1. Application Level — 전체 시스템 구성

사용자 음성 → ESP32 → PC 서버 → AI 처리 → ESP32 응답의 전체 흐름.

```mermaid
flowchart TB
    subgraph User["👤 사용자"]
        Voice["🎤 음성 입력"]
        Listen["🔊 음성 청취"]
    end

    subgraph ESP32["📦 M5Stack Atom Echo (ESP32)"]
        MIC["SPM1423 PDM 마이크"]
        SPK["NS4168 I2S 스피커"]
        LED["SK6812 RGB LED"]
        SERVO["서보 모터 (G25)"]
        BTN["버튼 (G39)"]
    end

    subgraph Network["🌐 WiFi 2.4GHz"]
        TCP["TCP :5001"]
    end

    subgraph Server["🖥️ PC 서버 (Python)"]
        STT["Whisper STT\n음성→텍스트"]
        LLM["Qwen2.5 LLM\nAI 대화/명령 해석"]
        TTS["Edge TTS\n텍스트→음성"]
        CMD["명령 파서\n서보/감정/액션"]
    end

    subgraph Cloud["☁️ 외부 서비스"]
        Weather["OpenWeatherMap"]
        News["Google News RSS"]
        EdgeTTS["Microsoft Edge TTS"]
    end

    Voice --> MIC
    MIC -->|"PCM16LE 16kHz"| TCP
    TCP -->|"START/AUDIO/END"| STT
    STT -->|"텍스트"| LLM
    LLM -->|"응답 텍스트"| TTS
    LLM -->|"액션 JSON"| CMD
    TTS -->|"PCM 오디오"| TCP
    CMD -->|"CMD JSON"| TCP
    TCP -->|"AUDIO_OUT"| SPK
    TCP -->|"CMD"| LED
    TCP -->|"CMD"| SERVO
    SPK --> Listen
    LLM -.->|"API 호출"| Cloud

    style ESP32 fill:#1a1a2e,color:#fff
    style Server fill:#16213e,color:#fff
    style Cloud fill:#0f3460,color:#fff
```

---

## 2. Module Level — ESP32 소프트웨어 모듈 의존성

각 `.cpp/.h` 파일 간의 의존 관계와 데이터 흐름.

```mermaid
flowchart TB
    subgraph Main["atom_echo_m5stack_esp32_ino.ino"]
        setup["setup()"]
        loop["loop()"]
    end

    subgraph Config["config.h"]
        WiFiCfg["WiFi/Server extern"]
        HWCfg["Servo/Audio/VAD/LED #define"]
    end

    subgraph Conn["connection.cpp/h"]
        connInit["connection_init()"]
        connManage["connection_manage()"]
    end

    subgraph Proto["protocol.cpp/h"]
        protoInit["protocol_init()"]
        sendPkt["send_packet()"]
        poll["protocol_poll()"]
        audioProc["audio_process()"]
        ringBuf["링 버퍼 32KB"]
        jsonParser["JSON 파서"]
    end

    subgraph VAD["vad.cpp/h"]
        vadInit["vad_init()"]
        vadUpdate["vad_update()"]
    end

    subgraph AudioBuf["audio_buffer.cpp/h"]
        prerollInit["preroll_init()"]
        prerollPush["preroll_push()"]
        prerollSend["preroll_send()"]
    end

    subgraph LEDCtrl["led_control.cpp/h"]
        ledInit["led_init()"]
        ledColor["led_set_color()"]
        ledEmotion["led_show_emotion()"]
    end

    subgraph ServoCtrl["servo_control.cpp/h"]
        servoInit["servo_init()"]
        servoAngle["servo_set_angle()"]
        servoUpdate["servo_update()"]
    end

    Config --> Main
    Config --> Conn
    Config --> Proto
    Config --> VAD
    Config --> AudioBuf
    Config --> ServoCtrl

    Main --> Conn
    Main --> Proto
    Main --> VAD
    Main --> AudioBuf
    Main --> LEDCtrl
    Main --> ServoCtrl

    Proto --> LEDCtrl
    Proto --> ServoCtrl
    AudioBuf --> Proto

    style Config fill:#2d3436,color:#fff
    style Main fill:#6c5ce7,color:#fff
```

---

## 3. Data Flow Level — 음성 입출력 파이프라인

20ms 프레임 단위의 오디오 데이터 흐름.

```mermaid
sequenceDiagram
    participant MIC as SPM1423 마이크
    participant INO as main loop()
    participant VAD as VAD 엔진
    participant PRE as 프리롤 버퍼
    participant TCP as TCP 소켓
    participant SRV as PC 서버
    participant RING as 링 버퍼 32KB
    participant SPK as NS4168 스피커

    Note over MIC,SPK: ── 음성 입력 (ESP32 → Server) ──

    loop 매 20ms (320샘플)
        MIC->>INO: PCM16 프레임
        INO->>INO: frame_rms() 계산
        INO->>PRE: preroll_push()
        INO->>VAD: vad_update(rms)
    end

    VAD-->>INO: VAD_START
    INO->>TCP: 0x01 START
    PRE->>TCP: 0x02 AUDIO (프리롤 200ms)

    loop 발화 진행 중
        MIC->>INO: PCM16 프레임
        INO->>VAD: vad_update(rms)
        VAD-->>INO: VAD_CONTINUE
        INO->>TCP: 0x02 AUDIO (640B)
    end

    VAD-->>INO: VAD_END
    INO->>TCP: 0x03 END

    Note over MIC,SPK: ── 음성 출력 (Server → ESP32) ──

    SRV->>TCP: 0x11 CMD (JSON)
    TCP->>INO: handleCmdJson()
    INO->>SPK: LED/서보 동작

    loop TTS 스트리밍
        SRV->>TCP: 0x12 AUDIO_OUT (2KB 청크)
        TCP->>RING: audio_ring_push()
    end

    loop 재생 (비블로킹)
        RING->>SPK: audio_ring_pop() → playRaw()
    end
```

---

## 4. Hardware Level — Atom Echo 핀 맵 및 버스 구조

ESP32-PICO-D4 내부 버스와 외부 핀 연결.

```mermaid
flowchart LR
    subgraph ESP32["ESP32-PICO-D4 (240MHz Dual Core)"]
        CPU["CPU 0/1\n240MHz"]
        I2S["I2S 페리페럴\n(마이크+스피커 공유)"]
        LEDC["LEDC PWM\n(서보 제어)"]
        WIFI["WiFi 모듈\n2.4GHz STA"]
        GPIO["GPIO 컨트롤러"]
        SRAM["SRAM 520KB"]
        FLASH["Flash 4MB"]
    end

    subgraph Audio["오디오 (I2S 버스)"]
        MIC_HW["SPM1423\nPDM 마이크"]
        SPK_HW["NS4168\nI2S DAC + 0.8W 스피커"]
    end

    subgraph HMI["사용자 인터페이스"]
        LED_HW["SK6812\nRGB LED"]
        BTN_HW["택트 버튼"]
    end

    subgraph EXT["외부 연결 (헤더/Grove)"]
        SERVO_HW["서보 모터\n(PWM 50Hz)"]
        GROVE["Grove 포트\nG26, G32"]
    end

    I2S -->|"G33 CLK\nG23 DATA"| MIC_HW
    I2S -->|"G22 DATA\nG19 BCLK\nG33 LRCK"| SPK_HW
    GPIO -->|"G27"| LED_HW
    GPIO -->|"G39 (입력)"| BTN_HW
    LEDC -->|"G25 PWM"| SERVO_HW
    GPIO -->|"G26, G32"| GROVE
    CPU --> I2S
    CPU --> LEDC
    CPU --> WIFI
    CPU --> GPIO
    CPU --> SRAM
    CPU --> FLASH

    style ESP32 fill:#2d3436,color:#fff
    style Audio fill:#d63031,color:#fff
    style HMI fill:#0984e3,color:#fff
    style EXT fill:#00b894,color:#fff
```

---

## 5. State Machine Level — 메인 루프 상태 전이

loop() 내부의 상태 전이 다이어그램.

```mermaid
stateDiagram-v2
    [*] --> Booting: 전원 ON

    Booting --> WiFiConnecting: setup() 완료
    WiFiConnecting --> WiFiConnecting: 5초마다 재시도
    WiFiConnecting --> ServerConnecting: WiFi 연결 성공

    ServerConnecting --> ServerConnecting: 5초마다 재시도
    ServerConnecting --> Idle: TCP 연결 성공

    Idle --> Recording: VAD_START\n(2프레임 연속 음성)
    Idle --> Playing: AUDIO_OUT 수신\n(4KB 축적)
    Idle --> WiFiConnecting: WiFi 끊김
    Idle --> ServerConnecting: TCP 끊김

    Recording --> Recording: VAD_CONTINUE\n(AUDIO 패킷 전송)
    Recording --> Idle: VAD_END\n(침묵 or 타임아웃)

    Playing --> Playing: 링 버퍼 재생 중
    Playing --> Idle: 버퍼 소진 + 재생 완료
    Playing --> Idle: 버튼 인터럽트

    state Idle {
        [*] --> Listening
        Listening --> Listening: 프리롤 버퍼 축적
        Listening --> PingCheck: 3초 경과
        PingCheck --> Listening: PING 전송
    }

    note right of Recording
        LED: 초록
        마이크: 활성
        스피커: 비활성
    end note

    note right of Playing
        LED: 노랑
        마이크: 비활성 (Half-duplex)
        스피커: 활성
    end note

    note right of Idle
        LED: 파랑
        마이크: 활성
        스피커: 대기
    end note
```

---

## 6. Protocol Level — 패킷 구조 및 방향

```mermaid
flowchart LR
    subgraph ESP32_TX["ESP32 → Server"]
        S1["0x01 START\n(페이로드 없음)"]
        S2["0x02 AUDIO\n640B PCM16LE"]
        S3["0x03 END\n(페이로드 없음)"]
        S4["0x10 PING\n(페이로드 없음)"]
    end

    subgraph Packet["패킷 구조"]
        P["[Type 1B][Length 2B LE][Payload NB]"]
    end

    subgraph Server_TX["Server → ESP32"]
        R1["0x11 CMD\nJSON ≤2KB"]
        R2["0x12 AUDIO_OUT\nPCM16LE 2KB 청크"]
        R3["0x1F PONG\n(페이로드 없음)"]
    end

    ESP32_TX --> Packet
    Packet --> Server_TX

    style Packet fill:#fdcb6e,color:#2d3436
```

---

## 7. Memory Layout — ESP32 DRAM 사용량

```mermaid
pie title ESP32 DRAM 사용량 (약 320KB 가용)
    "프리롤 버퍼 (6.4KB)" : 6.4
    "RX 버퍼 (2KB)" : 2
    "링 버퍼 (32KB, 동적)" : 32
    "재생 버퍼 (8KB, static)" : 8
    "JSON 파서 (2KB, static)" : 2
    "RX 오디오 (≤16KB, 동적)" : 16
    "M5Unified/WiFi/스택 (~100KB)" : 100
    "여유 공간 (~153KB)" : 153
```
