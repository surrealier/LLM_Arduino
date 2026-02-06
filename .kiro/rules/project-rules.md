# LLM_Arduino 프로젝트 규칙

## 프로젝트 개발 기준

### 🔒 프로덕션 레벨 코드 품질

**❌ 절대 금지**
- 문제 있는 코드를 주석처리하고 넘어가기
- 불확실한 테스트성 임시 수정 (`if True:` 등)
- 여러 파일/기능을 한 번에 대량 수정

**✅ 코드 변경 원칙**
1. **완전성**: 모든 변경은 완전히 동작하는 상태여야 함
2. **점진성**: 한 번에 하나의 기능만 수정
3. **검증성**: 각 변경 후 반드시 테스트
4. **지속성**: 임시방편이 아닌 영구적 솔루션

### 🏗️ 서버-클라이언트 아키텍처 (서버 중심 설계)

**서버(Python) 담당**: 모든 비즈니스 로직, 상태 관리, 로깅, 에러 처리, AI/LLM 통신, 외부 서비스 연동

**클라이언트(ESP32) 담당**: 오디오 캡처/전송/재생, LED 제어, 서보 제어, 간단한 상태 보고

```cpp
// ❌ ESP32에서 복잡한 로직 금지
// ✅ ESP32는 서버 명령을 단순 실행만
void executeServerCommand(uint8_t cmd) {
    switch(cmd) {
        case CMD_LED_ON: led.on(); break;
        case CMD_SERVO_MOVE: servo.move(angle); break;
    }
}
```

**로깅**: 서버에서 모든 로깅 수행. ESP32는 `Serial.println("READY")` 수준의 필수 디버그만.

### 📝 문서 관리

- 모든 기능 변경 시 README.md 업데이트 필수
- 기능 구현 상태는 TODO.md로 관리
- 기능 추가/수정 → TODO.md 항목 추가 → 완료 시 상태 업데이트 → README.md 동기화

---

## Arduino .ino 파일 규칙

### ⚠️ 최우선 원칙: Arduino 문법 준수

**❌ 자주 발생하는 문법 오류**

```cpp
// ❌ C++ 표준 라이브러리 사용 금지
#include <vector>
#include <string>
std::vector<int> data;
std::to_string(value);

// ❌ 잘못된 메모리 관리
char* buffer = new char[1024];  // delete 없이 사용

// ❌ 부적절한 전역 변수 초기화
WiFiClient client = WiFiClient();  // setup()에서 초기화해야 함
```

**✅ Arduino 호환 코드**

```cpp
// ✅ Arduino String 사용
String message = "Hello";
message += String(value);

// ✅ 적절한 메모리 관리
uint8_t buffer[1024];
memset(buffer, 0, sizeof(buffer));

// ✅ 전역 변수는 선언만, setup()에서 초기화
WiFiClient client;
void setup() { client = WiFiClient(); }
```

### 📋 .ino 수정 체크리스트

- Arduino 표준 라이브러리만 사용 (C++ STL 금지)
- 동적 할당 최소화, 스택 크기 고려 (ESP32: 8KB 기본)
- `setup()` 및 `loop()` 존재 확인
- `uint8_t`, `uint16_t`, `uint32_t` 등 명시적 크기 타입 사용
- 문자열은 `String` 또는 `char[]` (`std::string` 금지)

### 🔍 ESP32 특화 사항

```cpp
// ✅ ESP32 Task
xTaskCreate(audioTask, "AudioTask", 8192, NULL, 1, &audioTaskHandle);

// ✅ PSRAM
#ifdef BOARD_HAS_PSRAM
    uint8_t* largeBuffer = (uint8_t*)ps_malloc(32768);
#endif

// ✅ WiFi 연결 패턴
void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        attempts++;
    }
}
```

### 🚫 절대 금지 (컴파일 오류 발생)

```cpp
// ❌ RTTI: typeid(), dynamic_cast
// ❌ 예외 처리: try/catch (권장하지 않음)
// ❌ 표준 입출력: std::cout, std::cin
// ❌ 파일 시스템: fopen(), fread() (라이브러리 없이)
// ✅ 대신: Serial.println(), SPIFFS.open()
```

### ✅ 검증 프로세스

1. **문법 검사**: Arduino IDE 또는 PlatformIO로 컴파일, 경고 해결
2. **메모리 확인**: 프로그램 저장 < 80%, 동적 메모리 < 70%
3. **하드웨어 테스트**: 시리얼 모니터 확인, 재부팅/메모리 누수 점검
