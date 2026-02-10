"""
ESP32와 서버 간 TCP 통신 프로토콜 모듈
- 패킷 송수신 및 프로토콜 타입 정의
- 안정적인 데이터 전송을 위한 유틸리티 함수들
"""
import json
import logging
import socket
import struct
import time
from typing import Optional

log = logging.getLogger(__name__)

# 프로토콜 타입 정의 - ESP32와 서버 간 통신 메시지 타입
PTYPE_START = 0x01          # 음성 녹음 시작 신호
PTYPE_AUDIO = 0x02          # 오디오 데이터 전송
PTYPE_END = 0x03            # 음성 녹음 종료 신호
PTYPE_PING = 0x10           # 연결 상태 확인 (ESP32 → 서버)
PTYPE_PONG = 0x1F           # 연결 응답 (서버 → ESP32)
PTYPE_CMD = 0x11            # 명령 전송 (서버 → ESP32)
PTYPE_AUDIO_OUT = 0x12      # 오디오 출력 데이터 (서버 → ESP32)
PTYPE_BUFFER_STATUS = 0x13  # 버퍼 상태 보고 (선택적)


def recv_exact(conn: socket.socket, n: int, max_timeouts: int = 120) -> Optional[bytes]:
    """
    정확히 n바이트를 수신하는 함수
    - 타임아웃 발생 시 재시도하며, 최대 횟수 초과 시 None 반환
    - 연결 오류 발생 시 즉시 None 반환
    """
    buf = b""
    timeout_count = 0
    # 요청된 바이트 수만큼 수신할 때까지 반복
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
        except socket.timeout:
            # 타임아웃 발생 시 카운터 증가 및 재시도
            timeout_count += 1
            if timeout_count >= max_timeouts:
                log.warning("recv_exact timeout - connection may be dead")
                return None
            continue
        except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
            # 연결 오류 발생 시 즉시 종료
            log.warning("recv_exact connection error: %s", exc)
            return None
        if not chunk:
            return None
        timeout_count = 0  # 성공적으로 데이터 수신 시 타임아웃 카운터 리셋
        buf += chunk
    return buf


def send_packet(
    conn: socket.socket,
    ptype: int,
    payload: Optional[bytes] = b"",
    lock=None,
    audio_chunk: int = 1024,
    audio_sleep_s: float = 0.030,
) -> bool:
    """
    안정적인 패킷 전송 함수
    - 패킷 타입과 페이로드를 헤더와 함께 전송
    - 오디오 데이터의 경우 샘플 경계를 유지하며 청크 단위로 전송
    - 스레드 안전성을 위한 락 지원
    """
    try:
        if payload is None:
            payload = b""

        def _send():
            offset = 0
            total = len(payload)
            # 페이로드가 없는 경우 헤더만 전송
            if total == 0:
                conn.sendall(struct.pack("<BH", ptype & 0xFF, 0))
                return True

            # 오디오 출력 데이터의 경우 특별 처리
            if ptype == PTYPE_AUDIO_OUT:
                while offset < total:
                    remaining = total - offset
                    if remaining < 2:  # 16비트 샘플 최소 크기 체크
                        break
                    chunk_size = min(remaining, audio_chunk)
                    # 샘플 경계 유지 (16비트 = 2바이트)
                    if chunk_size % 2 != 0:
                        chunk_size -= 1
                    chunk = payload[offset : offset + chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
                    # 오디오 스트리밍을 위한 지연
                    if offset < total:
                        time.sleep(audio_sleep_s)
            else:
                # 일반 데이터의 경우 청크 단위로 전송
                while offset < total:
                    chunk_size = min(total - offset, 60000)
                    chunk = payload[offset : offset + chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
            return True

        # 락이 제공된 경우 스레드 안전 전송
        if lock:
            with lock:
                return _send()
        return _send()

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as exc:
        log.warning("send_packet error ptype=0x%02X: %s", ptype, exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("send_packet failed ptype=0x%02X: %s", ptype, exc)
        return False


def send_action(conn: socket.socket, action_dict: dict, lock=None) -> bool:
    """
    ESP32에 액션 명령을 JSON 형태로 전송
    - 딕셔너리를 JSON으로 직렬화하여 CMD 패킷으로 전송
    """
    payload = json.dumps(action_dict, ensure_ascii=False).encode("utf-8")
    ok = send_packet(conn, PTYPE_CMD, payload, lock=lock)
    if ok:
        log.info("CMD to ESP32: %s", action_dict)
    return ok


def send_audio(conn: socket.socket, pcm_bytes: bytes, lock=None) -> bool:
    """
    ESP32에 오디오 데이터 전송
    - PCM 바이트 데이터를 AUDIO_OUT 패킷으로 전송
    """
    ok = send_packet(conn, PTYPE_AUDIO_OUT, pcm_bytes, lock=lock)
    if ok:
        log.info("AUDIO to ESP32: %s bytes", len(pcm_bytes))
    return ok


def send_pong(conn: socket.socket, lock=None) -> bool:
    """
    ESP32의 PING에 대한 PONG 응답 전송
    - 연결 상태 확인을 위한 응답 패킷
    """
    return send_packet(conn, PTYPE_PONG, b"", lock=lock)
