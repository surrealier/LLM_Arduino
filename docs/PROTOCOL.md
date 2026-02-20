# ccoli TCP Protocol

## Packet Format

Every packet uses:
- `1 byte` packet type
- `2 bytes` payload length (little-endian)
- `N bytes` payload

## Packet Types

### ESP32 -> Server

- `0x01` `START`
  - Voice stream started
- `0x02` `AUDIO`
  - PCM16LE mono audio chunk
- `0x03` `END`
  - Voice stream ended
- `0x10` `PING`
  - Keepalive heartbeat
- `0x13` `BUFFER_STATUS` (optional)
  - ESP32 buffer telemetry (if enabled)

### Server -> ESP32

- `0x11` `CMD`
  - JSON command payload
- `0x12` `AUDIO_OUT`
  - PCM16LE mono TTS chunk
- `0x1F` `PONG`
  - Keepalive response

## Audio Format

- Encoding: PCM 16-bit little-endian
- Channel: mono
- Sample rate: 16kHz

## Command Payload (`0x11`)

Server sends JSON, for example:

```json
{
  "action": "NOOP",
  "sid": 7,
  "meaningful": false,
  "recognized": true
}
```

## Connection Notes

- ESP32 reconnect logic is handled on firmware side.
- Server answers `PING` with `PONG`.
- Server-side socket timeout is configured in `server/config.yaml` under `connection.socket_timeout`.
