# LLM_Arduino 사용자 가이드

## 서버 실행
1. `server/requirements.txt` 설치
2. `server/config.yaml`과 `server/.env` 설정
3. `python server.py` 실행

## Arduino 업로드
1. `arduino/atom_echo_m5stack_esp32_ino/config.h` 설정
2. `.ino` 업로드

## 기본 사용 흐름
- 전원 ON → WiFi 연결 → 서버 연결
- 음성 입력 → STT → 모드별 처리 → 명령/음성 출력
