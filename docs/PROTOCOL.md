# LLM_Arduino Protocol

## Packet Format
- Header: `1 byte type` + `2 bytes length (LE)`
- Payload: `length` bytes

## ESP32 -> PC
- `0x01` START: 음성 시작
- `0x02` AUDIO: PCM16LE 오디오 프레임
- `0x03` END: 음성 종료
- `0x10` PING: keepalive

## PC -> ESP32
- `0x11` CMD: JSON 명령
- `0x12` AUDIO_OUT: PCM16LE 오디오 스트림
- `0x1F` PONG: PING 응답

## Notes
- AUDIO_OUT는 샘플 경계(2바이트)에 맞춰 분할 전송합니다.
