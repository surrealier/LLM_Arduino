# LLM_Arduino Protocol

## Packet Format
- Header: `1 byte type` + `2 bytes length (LE)`
- Payload: `length` bytes

## ESP32 -> PC
- `0x01` START: 음성 시작
- `0x02` AUDIO: PCM16LE 오디오 프레임
- `0x03` END: 음성 종료
- `0x10` PING: keepalive
- `0x13` BUFFER_STATUS: 버퍼 상태 보고 (선택적)

## PC -> ESP32
- `0x11` CMD: JSON 명령
- `0x12` AUDIO_OUT: PCM16LE 오디오 스트림
- `0x1F` PONG: PING 응답

## Packet Details

### AUDIO_OUT (0x12)
TTS 오디오를 ESP32로 스트리밍합니다.
- Format: PCM16LE, 16kHz, mono
- Chunk size: 2048 bytes (1024 samples)
- Send interval: 10ms
- ESP32는 32KB 링 버퍼를 사용하여 비블로킹 재생

### BUFFER_STATUS (0x13) - Optional
ESP32가 오디오 버퍼 상태를 서버에 보고합니다 (향후 구현 가능).
- Payload: JSON format
  ```json
  {
    "used": 12345,      // 사용 중인 버퍼 크기 (bytes)
    "available": 20223, // 사용 가능한 버퍼 크기 (bytes)
    "total": 32768      // 전체 버퍼 크기 (bytes)
  }
  ```

## Audio Streaming Flow

### PC → ESP32 (TTS Output)
```
1. 서버: TTS 오디오 생성
2. 서버: 2KB 청크로 분할
3. 서버: 각 청크를 AUDIO_OUT 패킷으로 전송 (10ms 간격)
4. ESP32: 수신한 데이터를 링 버퍼에 저장
5. ESP32: 버퍼에 4KB 이상 쌓이면 재생 시작
6. ESP32: 재생 완료 시 다음 청크 재생 (비블로킹)
7. 반복...
```

### ESP32 → PC (Voice Input)
```
1. ESP32: VAD로 음성 감지
2. ESP32: START 패킷 전송
3. ESP32: 프리롤 버퍼 전송 (200ms)
4. ESP32: 20ms마다 AUDIO 패킷 전송 (320 samples)
5. ESP32: 음성 종료 감지 시 END 패킷 전송
```

## Buffer Management

### ESP32 Audio Ring Buffer
- Size: 32KB (configurable via `AUDIO_RING_BUFFER_SIZE`)
- Capacity: ~1 second of audio at 16kHz
- Non-blocking: 수신과 재생이 동시에 진행

### Benefits
- Prevents TCP buffer overflow
- Smooth audio playback
- Allows simultaneous recording and playback
- CPU-efficient non-blocking design

## Performance Characteristics

### Network
- Audio data rate: 32 KB/s (16kHz × 2 bytes)
- Server send rate: ~200 KB/s (with 10ms interval)
- Overhead: 6.25x (sufficient buffer margin)

### Memory
- RX buffer: 2KB (increased from 512B)
- Audio ring buffer: 32KB
- Dynamic allocation for large packets

## Notes
- AUDIO_OUT는 샘플 경계(2바이트)에 맞춰 분할 전송합니다.
- ESP32는 비블로킹 재생 방식을 사용하여 버퍼 오버플로우를 방지합니다.
- 링 버퍼는 동적으로 할당되며 첫 AUDIO_OUT 패킷 수신 시 초기화됩니다.