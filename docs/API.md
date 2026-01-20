# LLM_Arduino Server API

## Server Entry
- `server/server.py`: 메인 서버 진입점

## 주요 모듈
- `server/src/protocol.py`: 패킷 송수신 및 프로토콜 상수
- `server/src/audio_processor.py`: 오디오 품질/정규화/저장
- `server/src/stt_engine.py`: Whisper 모델 로딩/추론
- `server/src/job_queue.py`: STT/TTS/명령 큐 관리
- `server/src/connection_manager.py`: TCP 연결 수명 관리
- `server/src/robot_mode.py`: 로봇 명령 파싱/LLM 정제
- `server/src/agent_mode.py`: 대화/정보/감정/프로액티브 처리

## 설정
- `server/config.yaml`과 `.env`로 동작 제어
