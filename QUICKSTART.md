# 🚀 빠른 시작 가이드

## 5분 안에 시작하기

### 1단계: 서버 설치 (2분)

```bash
# 프로젝트 디렉토리로 이동
cd LLM_Arduino/server

# 의존성 설치
pip install -r requirements.txt

# GPU 사용자 (권장)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2단계: 서버 실행 (1분)

```bash
python stt_improved.py
```

**첫 실행 시 모델 다운로드 (약 1.5GB, 5-10분 소요)**

### 3단계: Arduino 설정 (2분)

1. `atom_echo_improved.ino` 열기
2. WiFi 정보 수정:
```cpp
const char* SSID = "YOUR_WIFI";
const char* PASS = "YOUR_PASSWORD";
const char* SERVER_IP = "192.168.1.100";  // 서버 PC IP
```
3. 업로드!

### 4단계: 테스트

1. ESP32 전원 켜기
2. LED가 파란색이 될 때까지 대기
3. "안녕하세요" 말하기
4. 서보가 90도로 이동하면 성공! 🎉

---

## 명령어 치트시트

### Robot Mode (기본)
```
"가운데"     → 90도
"왼쪽"       → 30도
"오른쪽"     → 150도
"올려"       → +20도
"내려"       → -20도
"45도"       → 45도
```

### 모드 전환
```
"에이전트 모드"  → 대화 모드로 전환
"로봇 모드"      → 제어 모드로 전환
```

---

## 문제 해결

### WiFi 연결 안됨
- 2.4GHz WiFi 사용 확인
- SSID/비밀번호 재확인

### 서버 연결 안됨
- 방화벽 5001 포트 허용
- 서버 IP 확인: `ipconfig` (Windows) / `ifconfig` (Mac/Linux)

### 음성 인식 안됨
- 마이크에 가까이 말하기
- 배경 소음 줄이기
- 시리얼 모니터 확인

---

## 다음 단계

1. `README_IMPROVED.md` 읽기
2. `IMPROVEMENTS.md`에서 상세 기능 확인
3. `commands.yaml`에서 명령어 커스터마이징

**즐거운 코딩 되세요! 🎉**
