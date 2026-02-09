---
description: LLM_Arduino project rules and Arduino .ino coding guidelines
alwaysApply: true
---

# LLM_Arduino Project Rules

## Production-Grade Code Quality

### Absolute Prohibitions

Do not apply quick, temporary fixes.

```python
# Prohibited: commenting out broken code and moving on
# def problematic_function():
#     ...
# TODO: fix later

# Prohibited: uncertain, test-only edits
if True:  # temporary test
    pass

# Prohibited: large, multi-file edits in a single shot
# Do not change multiple files or multiple features at once
```

### Correct Approach

```python
# Correct: fully understand and fix the root cause
def fixed_function():
    """A fully working implementation."""
    # clear logic
    return result

# Correct: incremental, step-by-step change
# 1. Change one feature at a time
# 2. Test after each change
# 3. Apply only verified changes
```

### Change Principles

1. **Completeness**: every change must leave the system fully working
2. **Incrementalism**: change one feature at a time
3. **Verifiability**: test after each change
4. **Durability**: prefer permanent solutions over temporary patches

## Server-Client Architecture

### Core Rule: Server-Centric Design

**Server (Python) responsibilities**
- Business logic
- State management
- Logging and monitoring
- Error handling and recovery
- Complex data processing
- AI/LLM communication
- External service integrations

**Client (ESP32) responsibilities**
- Audio capture and transmission
- Audio playback
- LED control
- Servo control
- Simple status reporting

```cpp
// Prohibited on ESP32: complex logic
void complex_decision_making() {
    // AI model calls, complex state management, etc.
}

// Correct on ESP32: simple execution
void executeServerCommand(uint8_t cmd) {
    switch(cmd) {
        case CMD_LED_ON: led.on(); break;
        case CMD_SERVO_MOVE: servo.move(angle); break;
    }
}
```

### Logging Strategy

```python
# Server handles all detailed logging
logger.info(f"ESP32 connected: {client_id}")
logger.debug(f"Audio data received: {len(data)} bytes")
logger.error(f"Processing failed: {error}", exc_info=True)
```

```cpp
// Prohibited on ESP32: verbose logs
// Serial.println("Complex state: ...");

// Allowed: minimal essential debug output
Serial.println("READY");
```

## Documentation Maintenance

### README Update Rule

Any feature change requires updating `README.md`.

- New feature added: update README
- Existing feature modified: update README
- Feature removed: update README
- API changed: update README
- Configuration changed: update README

```markdown
# README.md update checklist

- [ ] Feature list updated
- [ ] Usage updated
- [ ] Configuration examples updated
- [ ] API docs updated
- [ ] Dependency info updated
```

## Connection Initialization Test

Run a full end-to-end test on each server-client connection.

```python
# On connect: initialize and run tests
async def on_client_connected(client):
    logger.info("Client connected - starting initialization tests")

    # 1. LED test
    await client.test_led()

    # 2. Servo test
    await client.test_servo()

    # 3. Audio test
    await client.test_audio()

    # 4. Full protocol test
    await client.test_protocol()

    logger.info("Initialization tests complete - OK")
```

## TODO List Management

Track implementation status in `TODO.md`.

```markdown
# TODO.md structure example

## In Progress
- [ ] Emotion system refactor
  - [x] Define base emotion states
  - [ ] Emotion transition logic
  - [ ] LED expression mapping

## Done
- [x] WebSocket connection stabilization
- [x] Audio buffer improvement

## Planned
- [ ] Home Assistant integration
- [ ] Multilingual support
```

**When adding or modifying features**
1. Add an item to `TODO.md`
2. Update status as implementation progresses
3. Move finished items to Done
4. Update `README.md` as well

---

# Arduino .ino File Rules

These rules apply when editing `.ino` files.

## Highest Priority: Follow Arduino Syntax

### Required checks before any `.ino` change

**Common syntax mistakes**

```cpp
// Prohibited: C++ standard library (not available on Arduino)
#include <vector>
#include <string>
std::vector<int> data;

// Prohibited: functions not supported by Arduino
std::to_string(value);
std::bind();

// Prohibited: incorrect memory management
char* buffer = new char[1024];  // used without delete

// Prohibited: improper global initialization
WiFiClient client = WiFiClient();  // must initialize in setup()
```

**Arduino-compatible code**

```cpp
// Allowed: Arduino String
String message = "Hello";
message += String(value);

// Allowed: proper memory usage
uint8_t buffer[1024];
memset(buffer, 0, sizeof(buffer));

// Allowed: declare globals only; initialize in setup()
WiFiClient client;

void setup() {
    client = WiFiClient();
}
```

## `.ino` Edit Checklist

- [ ] Use only Arduino standard libraries
  - `WiFi.h`, `WebSocketsClient.h`, `M5Atom.h`, etc.
  - Do not use C++ STL libraries

- [ ] Memory management
  - Minimize dynamic allocation
  - Consider stack size (ESP32: 8KB default)
  - Keep global array sizes reasonable

- [ ] Function signatures
  - `setup()` and `loop()` must exist
  - Function declaration order matters (Arduino parses top-down)

- [ ] Type usage
  - Prefer `uint8_t`, `uint16_t`, `uint32_t`
  - Prefer explicit sizes over `int`/`long`

- [ ] String handling
  - Use `String` or `char[]`
  - Do not use `std::string`

## ESP32-Specific Notes

```cpp
// Use ESP32 tasks
xTaskCreate(
    audioTask,
    "AudioTask",
    8192,  // stack size
    NULL,
    1,     // priority
    &audioTaskHandle
);

// When using PSRAM, do it explicitly
#ifdef BOARD_HAS_PSRAM
    uint8_t* largeBuffer = (uint8_t*)ps_malloc(32768);
#endif

// Use appropriate delays
delay(10);        // ms
delayMicroseconds(500);  // microseconds
vTaskDelay(pdMS_TO_TICKS(10));  // FreeRTOS task delay
```

### WiFi Connection Pattern

```cpp
// Stable WiFi connection
void connectWiFi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected");
        Serial.println(WiFi.localIP());
    }
}
```

## Absolute Prohibitions

These will cause compile errors.

```cpp
// Prohibited: RTTI
typeid(obj)
dynamic_cast<Type*>(ptr)

// Prohibited: exceptions (limited on ESP32)
try { } catch { }  // possible but not recommended

// Prohibited: standard I/O
std::cout << "message";
std::cin >> value;

// Prohibited: file system without proper libraries
fopen(), fread(), fwrite()

// Allowed alternatives
Serial.println("message");
SPIFFS.open("/file.txt");
```

## Verification Process

After modifying a `.ino` file, do all of the following:

1. **Compile check**
   - Build with Arduino IDE or PlatformIO
   - Resolve all warnings

2. **Memory usage check**
   ```
   Sketch uses 850232 bytes (64%) of program storage space.
   Global variables use 45672 bytes (13%) of dynamic memory.
   ```
   - Program storage: < 80%
   - Dynamic memory: < 70%

3. **On-device test**
   - Verify output on Serial Monitor
   - Ensure no unexpected reboots
   - Run long tests to check for memory leaks

## Arduino Idioms

```cpp
// LED control
pinMode(LED_PIN, OUTPUT);
digitalWrite(LED_PIN, HIGH);

// Timer
unsigned long previousMillis = 0;
const long interval = 1000;

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
        previousMillis = currentMillis;
        // run every second
    }
}

// Serial communication
Serial.begin(115200);
Serial.println("Message");
if (Serial.available()) {
    char c = Serial.read();
}
```

## Summary

1. **Follow Arduino syntax**: use only Arduino-standard APIs
2. **Mind memory limits**: ESP32 has constrained resources
3. **Compile every change**: build after every edit
4. **Test on hardware**: verify real-device behavior
5. **No C++ STL**: avoid standard C++ libraries
