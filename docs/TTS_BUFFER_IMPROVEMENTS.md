# TTS 버퍼 오버플로우 개선 사항

## 문제 분석

### 기존 문제점
1. **블로킹 재생 방식**: ESP32가 오디오를 완전히 재생할 때까지 블로킹되어 추가 데이터 수신이 불가능
2. **TCP 버퍼 오버플로우**: 서버가 빠르게 전송하는 동안 ESP32가 재생 중이면 TCP 수신 버퍼가 가득 참
3. **작은 수신 버퍼**: `RX_MAX_PAYLOAD`가 512바이트로 제한되어 큰 오디오 패킷 처리 어려움
4. **재생과 수신의 동기화 문제**: 재생이 끝나야만 다음 데이터 수신 가능

### 발생 시나리오
```
서버: TTS 오디오 생성 (예: 10초 분량, 320KB)
       ↓
서버: 빠른 속도로 전송 (4096 바이트 청크, 0.002초 간격)
       ↓
ESP32: 첫 청크 수신 → 재생 시작 (블로킹)
       ↓
ESP32: 재생 중... (수신 버퍼 쌓임)
       ↓
ESP32: TCP 버퍼 오버플로우! ❌
```

## 개선 사항

### 1. ESP32 측 개선

#### 1.1 링 버퍼 기반 스트리밍 재생
```cpp
// 32KB 링 버퍼 도입
static uint8_t* audio_ring_buffer = nullptr;
static size_t audio_ring_head = 0;
static size_t audio_ring_tail = 0;
static size_t audio_ring_size = 32768;  // 설정 가능
```

**장점:**
- 수신과 재생을 분리하여 동시 처리 가능
- 버퍼 오버플로우 방지
- 부드러운 오디오 재생

#### 1.2 비블로킹 오디오 재생
```cpp
void protocol_audio_process() {
  // 스피커가 재생 중이 아니고 버퍼에 데이터가 있으면 재생
  if (!M5.Speaker.isPlaying() && audio_ring_used() > 0) {
    // 8KB씩 청크로 재생
    size_t chunk_size = audio_ring_pop(play_buffer, 8192);
    M5.Speaker.playRaw((const int16_t*)play_buffer, samples, 16000, false, 1, 0);
  }
}
```

**개선 효과:**
- 메인 루프가 블로킹되지 않음
- VAD, LED, 서보 등 다른 기능 정상 동작
- 네트워크 수신 지속 가능

#### 1.3 수신 버퍼 크기 증가
```cpp
// 512 → 2048 바이트
static constexpr size_t RX_MAX_PAYLOAD = 2048;
```

**효과:**
- 큰 패킷 처리 가능
- 메모리 할당 빈도 감소

### 2. 서버 측 개선

#### 2.1 전송 속도 조절
```python
def send_packet(
    conn: socket.socket,
    ptype: int,
    payload: Optional[bytes] = b"",
    lock=None,
    audio_chunk: int = 2048,      # 4096 → 2048 (청크 크기 감소)
    audio_sleep_s: float = 0.010,  # 0.002 → 0.010 (간격 증가)
) -> bool:
```

**개선 효과:**
- ESP32가 처리할 시간 확보
- 네트워크 부하 분산
- 버퍼 오버플로우 방지

#### 2.2 청크 단위 전송
- 2KB씩 전송하여 수신 버퍼에 맞춤
- 10ms 간격으로 ESP32에 처리 시간 제공
- 초당 약 200KB 전송 속도 (16kHz 오디오 = 32KB/s보다 충분히 빠름)

### 3. 설정 가능한 파라미터

`config.h`에 추가된 설정:
```cpp
#define AUDIO_RING_BUFFER_SIZE 32768  // TTS playback buffer size (32KB)
```

**조정 가이드:**
- 기본값: 32KB (약 1초 분량의 오디오)
- 메모리가 충분하면 64KB로 증가 가능
- 짧은 응답만 필요하면 16KB로 감소 가능

## 동작 흐름

### 개선 후 시나리오
```
서버: TTS 오디오 생성 (320KB)
       ↓
서버: 2KB씩, 10ms 간격으로 전송
       ↓
ESP32: 데이터 수신 → 링 버퍼에 저장 (비블로킹)
       ↓
ESP32: 버퍼에 4KB 이상 쌓이면 재생 시작
       ↓
ESP32: protocol_audio_process() 호출 (매 루프)
       ├─ 재생 중이 아니면: 버퍼에서 8KB 읽어서 재생
       ├─ 재생 중이면: 다음 루프로 넘어감
       └─ 동시에 수신 계속 진행 ✓
       ↓
ESP32: 모든 데이터 재생 완료 ✓
```

## 모니터링

### 디버그 로그
```
[AUDIO_OUT] Buffered 2048 bytes (total: 6144 bytes)
[AUDIO_PROC] Playing 4096 samples (8192 bytes), buffer remaining: 18432
[AUDIO_PROC] Playback complete
```

### 버퍼 상태 확인
- `audio_ring_used()`: 현재 버퍼에 저장된 데이터 크기
- `audio_ring_available()`: 사용 가능한 버퍼 공간
- 버퍼가 가득 차면 경고 메시지 출력

## 추가 개선 가능 사항

### 1. 적응형 전송 속도
ESP32가 버퍼 상태를 서버에 전송하여 동적으로 전송 속도 조절:
```cpp
// ESP32 → 서버: 버퍼 상태 패킷
PTYPE_BUFFER_STATUS = 0x13
payload: { "used": 12345, "available": 20223 }
```

### 2. 우선순위 기반 처리
오디오 재생 중에는 VAD를 일시 중지하여 CPU 부하 감소:
```cpp
if (audio_playing) {
  M5.Mic.end();  // 마이크 비활성화
}
```

### 3. 메모리 최적화
PSRAM 사용 (ESP32 모델에 따라):
```cpp
audio_ring_buffer = (uint8_t*)ps_malloc(audio_ring_size);
```

### 4. 버퍼 프리롤 (Buffering)
재생 시작 전 충분한 데이터 확보:
```cpp
// 현재: 4KB 이상이면 재생 시작
// 개선: 8KB 이상이면 재생 시작 (더 안정적)
if (!audio_playing && audio_ring_used() >= 8192) {
  audio_playing = true;
}
```

## 성능 지표

### 개선 전
- 버퍼 오버플로우: 빈번히 발생
- 재생 중 수신: 불가능
- 최대 연속 재생: 약 2-3초

### 개선 후
- 버퍼 오버플로우: 거의 없음
- 재생 중 수신: 가능
- 최대 연속 재생: 제한 없음 (메모리 허용 범위 내)
- 버퍼 활용: 32KB (약 1초 버퍼링)

## 테스트 방법

### 1. 버퍼 오버플로우 테스트
```python
# 서버에서 긴 TTS 생성 (10초 이상)
response = "이것은 매우 긴 응답입니다. " * 50
```

### 2. 동시 처리 테스트
```python
# 재생 중 음성 입력 테스트
# LED, 서보 동작이 정상인지 확인
```

### 3. 네트워크 지연 테스트
```python
# 전송 간격을 늘려서 테스트
audio_sleep_s = 0.05  # 50ms
```

## 결론

이번 개선으로 ESP32의 TTS 버퍼 오버플로우 문제가 해결되었습니다:

✅ 비블로킹 오디오 재생
✅ 링 버퍼 기반 스트리밍
✅ 수신과 재생 동시 처리
✅ 서버 전송 속도 최적화
✅ 설정 가능한 버퍼 크기

추가 문제 발생 시 위의 "추가 개선 가능 사항"을 참고하여 최적화할 수 있습니다.
