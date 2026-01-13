import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import socket, struct, time, wave, re, logging, json, threading
from queue import Queue, Full, Empty
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
import yaml

from robot_mode_improved import RobotMode
from agent_mode_improved import AgentMode
from config_loader import get_config
from logger_config import setup_logging, get_performance_logger

# Load configuration
config = get_config()

# Setup logging first
logging_config = config.get_logging_config()
setup_logging(
    level=logging_config.get("level", "INFO"),
    save_to_file=logging_config.get("save_to_file", True),
    log_dir=logging_config.get("log_dir", "logs")
)

log = logging.getLogger("stt")
perf_logger = get_performance_logger()

# Server settings
HOST = config.get("server", "host")
PORT = config.get("server", "port")
SR = 16000

# STT settings
MODEL_SIZE = config.get("stt", "model_size")
PREFER_DEVICE = config.get("stt", "device")
CPU_FALLBACK_COMPUTE = "int8"

# Protocol
PTYPE_START = 0x01
PTYPE_AUDIO = 0x02
PTYPE_END = 0x03
PTYPE_PING = 0x10
PTYPE_PONG = 0x1F
PTYPE_CMD = 0x11
PTYPE_AUDIO_OUT = 0x12

UNSURE_POLICY = "NOOP"

SERVO_MIN = 0
SERVO_MAX = 180
DEFAULT_ANGLE_CENTER = 90
DEFAULT_STEP = 20

ACTIONS_CONFIG = []
current_mode = "robot"

robot_handler = None
agent_handler = None

def clamp(v, lo, hi): 
    return max(lo, min(hi, v))

def recv_exact(conn, n: int):
    """안정적인 데이터 수신 with 타임아웃 처리"""
    # Check if socket is still valid
    try:
        if conn is None or conn.fileno() == -1:
            return None
    except (OSError, AttributeError):
        return None
    
    buf = b""
    timeout_count = 0
    max_timeouts = 20
    while len(buf) < n:
        try:
            # Check socket validity before each recv
            if conn.fileno() == -1:
                return None
            chunk = conn.recv(n - len(buf))
        except socket.timeout:
            timeout_count += 1
            if timeout_count >= max_timeouts:
                log.warning("Too many timeouts in recv_exact - connection may be dead")
                return None
            continue
        except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
            log.warning(f"Connection error in recv_exact: {e}")
            return None
        if not chunk:
            return None
        timeout_count = 0
        buf += chunk
    return buf

def send_packet(conn, ptype: int, payload: bytes = b"", lock=None) -> bool:
    """안정적인 패킷 전송"""
    try:
        # Check if socket is still valid before sending
        if conn is None or conn.fileno() == -1:
            return False
        
        if payload is None: 
            payload = b""
        
        def _send():
            # Double-check socket validity inside the function
            try:
                if conn.fileno() == -1:
                    return False
            except (OSError, AttributeError):
                return False
            
            offset = 0
            total = len(payload)
            if total == 0:
                conn.sendall(struct.pack("<BH", ptype & 0xFF, 0))
                return True
            
            if ptype == PTYPE_AUDIO_OUT:
                max_chunk = 4096
                while offset < total:
                    remaining = total - offset
                    if remaining < 2:
                        break
                    
                    chunk_size = min(remaining, max_chunk)
                    if chunk_size % 2 != 0:
                        chunk_size -= 1
                    
                    chunk = payload[offset:offset+chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
                    
                    if offset < total:
                        time.sleep(0.002)
            else:
                while offset < total:
                    chunk_size = min(total - offset, 60000)
                    chunk = payload[offset:offset+chunk_size]
                    header = struct.pack("<BH", ptype & 0xFF, len(chunk))
                    conn.sendall(header + chunk)
                    offset += chunk_size
            return True

        if lock:
            with lock:
                return _send()
        else:
            return _send()

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as e:
        log.warning(f"send_packet error ptype=0x{ptype:02X}: {e}")
        return False
    except Exception as e:
        log.warning(f"send_packet failed ptype=0x{ptype:02X}: {e}")
        return False

def send_action(conn: socket.socket, action_dict: dict, lock: threading.Lock):
    """ESP32로 액션 명령 전송"""
    payload = json.dumps(action_dict, ensure_ascii=False).encode("utf-8")
    ok = send_packet(conn, PTYPE_CMD, payload, lock=lock)
    if ok:
        log.info(f"➡️ CMD to ESP32: {action_dict}")
    return ok

def send_audio(conn: socket.socket, pcm_bytes: bytes, lock: threading.Lock):
    """ESP32로 오디오 스트림 전송"""
    ok = send_packet(conn, PTYPE_AUDIO_OUT, pcm_bytes, lock=lock)
    if ok:
        log.info(f"➡️ AUDIO to ESP32: {len(pcm_bytes)} bytes")
    return ok

def send_pong(conn: socket.socket, lock: threading.Lock):
    """PING에 대한 PONG 응답"""
    return send_packet(conn, PTYPE_PONG, b"", lock=lock)

def save_wav(path: str, pcm_f32: np.ndarray, sr: int = SR):
    x = np.clip(pcm_f32, -1.0, 1.0)
    x16 = (x * 32767.0).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(x16.tobytes())

def qc(pcm_f32: np.ndarray):
    peak = float(np.max(np.abs(pcm_f32))) if pcm_f32.size else 0.0
    rms = float(np.sqrt(np.mean(pcm_f32**2) + 1e-12)) if pcm_f32.size else 0.0
    rms_db = 20.0 * np.log10(rms + 1e-12)
    clip = float(np.mean(np.abs(pcm_f32) >= 0.999)) * 100.0
    return rms_db, peak, clip

def trim_energy(pcm: np.ndarray, sr: int, top_db: float = 35.0, pad_ms: int = 140):
    if pcm.size == 0: 
        return pcm.astype(np.float32, copy=False)
    frame = int(sr * 0.02)
    hop = frame
    n = pcm.size
    if n < frame: 
        return pcm.astype(np.float32, copy=False)

    rms = []
    for i in range(0, n - frame + 1, hop):
        x = pcm[i:i+frame]
        rms.append(np.sqrt(np.mean(x*x) + 1e-12))
    rms = np.array(rms, dtype=np.float32)
    thr = float(np.max(rms)) * (10 ** (-top_db / 20.0))

    idx = np.where(rms > thr)[0]
    if idx.size == 0: 
        return pcm.astype(np.float32, copy=False)

    start_f = int(idx[0])
    end_f = int(idx[-1])
    start = max(0, start_f * hop - int(sr * pad_ms / 1000))
    end = min(n, (end_f * hop + frame) + int(sr * pad_ms / 1000))
    return pcm[start:end].astype(np.float32, copy=False)

def normalize_to_dbfs(pcm: np.ndarray, target_dbfs: float = -22.0, max_gain_db: float = 18.0):
    rms = float(np.sqrt(np.mean(pcm*pcm) + 1e-12))
    rms_db = 20.0 * np.log10(rms + 1e-12)
    gain_db = np.clip(target_dbfs - rms_db, -6.0, max_gain_db)
    gain = 10 ** (gain_db / 20.0)
    return np.clip(pcm * gain, -1.0, 1.0).astype(np.float32, copy=False)

def clean_text(text: str):
    t = (text or "").strip()
    t = re.sub(r"[,，]{3,}", ",", t)
    t = re.sub(r"([,，。.!?])\1{1,}", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) >= 8:
        punct = sum(ch in ",，。.!?…" for ch in t)
        if punct / max(1, len(t)) > 0.35:
            return ""
    t = re.sub(r"[,，]+$", "", t).strip()
    return t

def load_commands_config():
    global ACTIONS_CONFIG
    try:
        with open("commands.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            ACTIONS_CONFIG = data.get("commands", [])
            log.info(f"Loaded {len(ACTIONS_CONFIG)} commands from commands.yaml")
    except Exception as e:
        log.error(f"Failed to load commands.yaml: {e}")
        ACTIONS_CONFIG = []

# Whisper Model
model_lock = threading.Lock()
model = None
device_in_use = None

def load_stt_model(device: str):
    global model, device_in_use
    log.info(f"Loading STT model: {MODEL_SIZE} on {device}...")
    m = WhisperModel(MODEL_SIZE, device=device, compute_type=("int8" if device=="cpu" else "int8"),
                     cpu_threads=1, num_workers=1)
    model = m
    device_in_use = device
    log.info(f"STT model loaded on {device}")

def ensure_stt_model():
    global model
    if model is None:
        try:
            load_stt_model(PREFER_DEVICE)
        except Exception as e:
            log.warning(f"GPU init failed -> fallback CPU: {e}")
            load_stt_model("cpu")

def safe_transcribe(pcm_f32: np.ndarray):
    ensure_stt_model()
    pcm_f32 = np.ascontiguousarray(pcm_f32, dtype=np.float32)

    def _run():
        segments, info = model.transcribe(
            pcm_f32,
            language="ko",
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=1.15,
            no_repeat_ngram_size=3,
            log_prob_threshold=-1.2,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=200,
                min_silence_duration_ms=150,
                speech_pad_ms=120,
            ),
            suppress_blank=True,
        )
        segments = list(segments)
        return segments, info

    with model_lock:
        try:
            return _run()
        except RuntimeError as e:
            msg = str(e)
            if "cublas64_12.dll" in msg or "cublas" in msg:
                log.error("CUDA runtime missing/broken -> switching to CPU now.")
                load_stt_model("cpu")
                return _run()
            raise

def handle_connection(conn, addr):
    global current_mode, robot_handler, agent_handler

    log.info(f"📡 Connected: {addr}")
    conn.settimeout(0.5)
    try:
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    except Exception as e:
        log.warning(f"Failed to set keepalive: {e}")

    send_lock = threading.Lock()
    jobs = Queue(maxsize=4)
    connection_active = threading.Event()
    connection_active.set()  # Initially active

    state = {"sid": 0, "current_angle": DEFAULT_ANGLE_CENTER}
    state_lock = threading.Lock()

    def worker():
        global current_mode
        while True:
            try:
                job = jobs.get(timeout=1)
            except Empty:
                # Check if connection is still active
                if not connection_active.is_set():
                    break
                continue
            
            if job is None:
                return
            
            # Check connection before processing
            if not connection_active.is_set():
                break
            
            sid, data = job
            sec = len(data) / 2 / SR
            
            try:
                if sec < 0.45:
                    if current_mode == "robot" and connection_active.is_set():
                        action = {"action": "NOOP" if UNSURE_POLICY=="NOOP" else "WIGGLE",
                                  "sid": sid, "meaningful": False, "recognized": False}
                        send_action(conn, action, send_lock)
                    continue

                pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                rms_db, peak, clip = qc(pcm)
                log.info(f"QC sid={sid} rms={rms_db:.1f}dBFS peak={peak:.3f} clip={clip:.2f}%")

                if rms_db < -45.0:
                    if current_mode == "robot" and connection_active.is_set():
                        action = {"action": "NOOP" if UNSURE_POLICY=="NOOP" else "WIGGLE",
                                  "sid": sid, "meaningful": False, "recognized": False}
                        send_action(conn, action, send_lock)
                    continue

                pcm = trim_energy(pcm, SR)
                pcm = normalize_to_dbfs(pcm, target_dbfs=-22.0)

                ts = time.strftime("%Y%m%d_%H%M%S")
                wav_path = f"wav_logs/sid{sid}_{ts}_{len(pcm)/SR:.2f}s.wav"
                save_wav(wav_path, pcm, SR)
                log.info(f"Saved wav: {wav_path}")

                text = ""
                try:
                    stt_start = time.time()
                    segments, info = safe_transcribe(pcm)
                    text = clean_text("".join(seg.text for seg in segments))
                    stt_duration = time.time() - stt_start
                    perf_logger.log_stt(stt_duration)
                except Exception as e:
                    log.exception(f"Transcribe failed sid={sid}: {e}")
                    perf_logger.log_error()
                    continue

                if text:
                    log.info(f"🗣️ STT Raw: {text} (Mode: {current_mode})")
                else:
                    log.info("🗣️ (empty/filtered)")

                with state_lock:
                    cur = state["current_angle"]

                # Mode Switch Check
                sys_action, meaningful, _ = robot_handler.process_text(text, cur)
                
                if meaningful and sys_action.get("action") == "SWITCH_MODE":
                    new_mode = sys_action.get("mode")
                    if new_mode in ["robot", "agent"]:
                        current_mode = new_mode
                        log.info(f"🔄 Mode Switched to: {current_mode}")
                        
                        notify_text = f"{new_mode} 모드로 변경되었습니다."
                        if current_mode == "agent" and connection_active.is_set():
                            wav_bytes = agent_handler.text_to_audio(notify_text)
                            if wav_bytes:
                                send_audio(conn, wav_bytes, send_lock)
                        elif connection_active.is_set():
                            action = {"action": "WIGGLE", "sid": sid}
                            send_action(conn, action, send_lock)
                    continue

                # Mode-specific Processing
                if current_mode == "robot":
                    # LLM으로 STT 정제 및 명령 결정
                    llm_start = time.time()
                    refined_text, robot_action = robot_handler.process_with_llm(text, cur)
                    llm_duration = time.time() - llm_start
                    perf_logger.log_llm(llm_duration)
                    
                    if refined_text != text:
                        log.info(f"🔧 LLM Refined: {text} -> {refined_text}")
                    
                    action = robot_action
                    action["sid"] = sid
                    action["meaningful"] = meaningful
                    action["recognized"] = bool(text)

                    if meaningful and "angle" in action:
                        with state_lock:
                            state["current_angle"] = action["angle"]

                    if connection_active.is_set():
                        send_action(conn, action, send_lock)

                elif current_mode == "agent":
                    if not text: 
                        continue
                    
                    llm_start = time.time()
                    response = agent_handler.generate_response(text)
                    llm_duration = time.time() - llm_start
                    perf_logger.log_llm(llm_duration)
                    
                    if response and connection_active.is_set():
                        tts_start = time.time()
                        wav_bytes = agent_handler.text_to_audio(response)
                        tts_duration = time.time() - tts_start
                        perf_logger.log_tts(tts_duration)
                        if wav_bytes and connection_active.is_set():
                            send_audio(conn, wav_bytes, send_lock)
                        else:
                            log.error("TTS returned empty bytes")
            
            except Exception as e:
                log.exception(f"Worker error processing sid={sid}: {e}")
                perf_logger.log_error()
                continue

    threading.Thread(target=worker, daemon=True).start()

    audio_buf = bytearray()
    last_ping_time = time.time()

    while True:
        try:
            t = recv_exact(conn, 1)
            if t is None:
                log.info("Disconnect detected")
                connection_active.clear()  # Signal worker to stop
                break
            ptype = t[0]

            raw_len = recv_exact(conn, 2)
            if raw_len is None:
                log.info("Disconnect (len)")
                connection_active.clear()  # Signal worker to stop
                break
            (plen,) = struct.unpack("<H", raw_len)

            payload = b""
            if plen:
                payload = recv_exact(conn, plen)
                if payload is None:
                    log.info("Disconnect (payload)")
                    connection_active.clear()  # Signal worker to stop
                    break

            # Packet Handling
            if ptype == PTYPE_PING:
                last_ping_time = time.time()
                send_pong(conn, send_lock)
                continue

            if ptype == PTYPE_START:
                with state_lock:
                    state["sid"] += 1
                    sid = state["sid"]
                audio_buf = bytearray()
                log.info(f"🎙️ START (sid={sid})")

            elif ptype == PTYPE_AUDIO:
                audio_buf.extend(payload)
                if len(audio_buf) > int(12 * SR * 2):
                    log.warning("Buffer too large -> force END")
                    ptype = PTYPE_END

            if ptype == PTYPE_END:
                with state_lock:
                    sid = state["sid"]
                data = bytes(audio_buf)
                sec = len(data) / 2 / SR
                log.info(f"🛑 END (sid={sid}) bytes={len(data)} sec={sec:.2f}")

                try:
                    jobs.put_nowait((sid, data))
                except Full:
                    log.warning("Job queue full -> drop utterance")
                audio_buf = bytearray()
        
        except Exception as e:
            log.exception(f"Connection loop error: {e}")
            connection_active.clear()  # Signal worker to stop
            break

    try:
        jobs.put_nowait(None)
    except Exception:
        pass

def main():
    global robot_handler, agent_handler
    
    load_commands_config()
    
    # Get config
    weather_config = config.get_weather_config()
    weather_api_key = weather_config.get("api_key")
    location = weather_config.get("location", "Seoul")
    
    assistant_config = config.get_assistant_config()
    proactive_enabled = assistant_config.get("proactive", True)
    proactive_interval = assistant_config.get("proactive_interval", 1800)
    
    tts_config = config.get_tts_config()
    tts_voice = tts_config.get("voice", "ko-KR-SunHiNeural")
    
    robot_handler = RobotMode(ACTIONS_CONFIG, PREFER_DEVICE)
    agent_handler = AgentMode(PREFER_DEVICE, weather_api_key, location, 
                               proactive_enabled, proactive_interval, tts_voice)
    
    log.info(f"🤖 Assistant: {assistant_config.get('name', '아이')} ({assistant_config.get('personality', 'cheerful')})")
    
    robot_handler.load_model()
    agent_handler.load_model()
    
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)

    log.info(f"🚀 Server started on {PORT}. Default Mode: {current_mode}")
    
    # 통계 출력 타이머
    import signal
    def print_stats_handler(signum, frame):
        perf_logger.print_stats()
    
    # Ctrl+C 시 통계 출력
    signal.signal(signal.SIGINT, print_stats_handler)

    while True:
        log.info("Ready for next connection...")
        try:
            conn, addr = srv.accept()
        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error(f"Accept failed: {e}")
            time.sleep(1)
            continue
            
        try:
            handle_connection(conn, addr)
        except Exception as e:
            log.exception(f"Connection handler error: {e}")
        finally:
            try: 
                conn.close()
            except Exception: 
                pass
            log.info(f"🔌 Disconnected: {addr}")
            time.sleep(0.1)

if __name__ == "__main__":
    main()
