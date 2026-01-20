import json
import logging
import socket
import struct
import time
from typing import Optional

log = logging.getLogger(__name__)

PTYPE_START = 0x01
PTYPE_AUDIO = 0x02
PTYPE_END = 0x03
PTYPE_PING = 0x10
PTYPE_PONG = 0x1F
PTYPE_CMD = 0x11
PTYPE_AUDIO_OUT = 0x12
PTYPE_AUDIO_OUT_END = 0x13


def recv_exact(conn: socket.socket, n: int, max_timeouts: int = 20) -> Optional[bytes]:
    """정확히 n바이트 수신. 타임아웃 누적 시 None 반환."""
    buf = b""
    timeout_count = 0
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
        except socket.timeout:
            timeout_count += 1
            if timeout_count >= max_timeouts:
                log.warning("recv_exact timeout - connection may be dead")
                return None
            continue
        except (ConnectionResetError, ConnectionAbortedError, OSError) as exc:
            log.warning("recv_exact connection error: %s", exc)
            return None
        if not chunk:
            return None
        timeout_count = 0
        buf += chunk
    return buf


def send_packet(
    conn: socket.socket,
    ptype: int,
    payload: Optional[bytes] = b"",
    lock=None,
    audio_chunk: int = 4096,
    audio_sleep_s: float = 0.002,
) -> bool:
    """안정적인 패킷 전송. 오디오는 샘플 경계 유지."""
    try:
        if payload is None:
            payload = b""

        def _send():
            offset = 0
            total = len(payload)
            if total == 0:
                conn.sendall(struct.pack("<BH", ptype & 0xFF, 0))
                return True

            if ptype == PTYPE_AUDIO_OUT:
                while offset < total:
                    remaining = total - offset
                    if remaining < 2:
                        break
                    chunk_size = min(remaining, audio_chunk)
                    if chunk_size % 2 != 0:
                        chunk_size -= 1
                    chunk = payload[offset : offset + chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
                    if offset < total:
                        time.sleep(audio_sleep_s)
            else:
                while offset < total:
                    chunk_size = min(total - offset, 60000)
                    chunk = payload[offset : offset + chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
            return True

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
    payload = json.dumps(action_dict, ensure_ascii=False).encode("utf-8")
    ok = send_packet(conn, PTYPE_CMD, payload, lock=lock)
    if ok:
        log.info("CMD to ESP32: %s", action_dict)
    return ok


def send_audio(conn: socket.socket, pcm_bytes: bytes, lock=None) -> bool:
    # #region agent log
    import json
    with open('/Users/b__ono__ng/Main/Projects/LLM_Adruino/.cursor/debug.log', 'a', encoding='utf-8') as f:
        f.write(json.dumps({"location":"protocol.py:107","message":"send_audio called","data":{"pcm_bytes_len":len(pcm_bytes),"samples":len(pcm_bytes)//2,"duration_sec":len(pcm_bytes)/2/16000},"timestamp":int(time.time()*1000),"sessionId":"debug-session","hypothesisId":"H2"}) + '\n')
    # #endregion
    
    ok = send_packet(conn, PTYPE_AUDIO_OUT, pcm_bytes, lock=lock)
    if ok:
        log.info("AUDIO to ESP32: %s bytes", len(pcm_bytes))
        # 오디오 전송 완료 신호 전송
        end_ok = send_packet(conn, PTYPE_AUDIO_OUT_END, b"", lock=lock)
        if end_ok:
            log.info("AUDIO_OUT_END sent to ESP32")
        return end_ok
    return ok


def send_pong(conn: socket.socket, lock=None) -> bool:
    return send_packet(conn, PTYPE_PONG, b"", lock=lock)
