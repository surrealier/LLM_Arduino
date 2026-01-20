import os
import signal
import threading
import time
from queue import Empty

import numpy as np
import yaml

from config_loader import get_config
from src.agent_mode import AgentMode
from src.audio_processor import normalize_to_dbfs, qc, save_wav, trim_energy
from src.connection_manager import ConnectionManager
from src.job_queue import JobQueue
from src.logging_setup import get_performance_logger, setup_logging
from src.protocol import (
    PTYPE_AUDIO,
    PTYPE_END,
    PTYPE_PING,
    PTYPE_START,
    recv_exact,
    send_action,
    send_audio,
    send_pong,
)
from src.robot_mode import RobotMode
from src.stt_engine import STTEngine
from src.utils import clean_text

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


SR = 16000
UNSURE_POLICY = "NOOP"

ACTIONS_CONFIG = []
current_mode = "agent"  # 디폴트 모드: agent

robot_handler = None
agent_handler = None


def load_commands_config(path: str = "commands.yaml"):
    global ACTIONS_CONFIG
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            ACTIONS_CONFIG = data.get("commands", [])
    except Exception:
        ACTIONS_CONFIG = []


def handle_connection(conn, addr, stt_engine: STTEngine, config):
    global current_mode, robot_handler, agent_handler

    log = __import__("logging").getLogger("server")
    perf_logger = get_performance_logger()

    log.info("Connected: %s", addr)
    conn.settimeout(config.get("connection", "socket_timeout", default=0.5))
    try:
        conn.setsockopt(1, 9, 1)
    except Exception:
        pass

    send_lock = threading.Lock()
    job_queue = JobQueue(
        stt_maxsize=config.get("queue", "stt_maxsize", default=4),
        tts_maxsize=config.get("queue", "tts_maxsize", default=2),
        command_maxsize=config.get("queue", "command_maxsize", default=10),
    )

    state = {"sid": 0, "current_angle": 90}
    state_lock = threading.Lock()
    stop_event = threading.Event()

    def worker():
        global current_mode
        while not stop_event.is_set():
            try:
                job = job_queue.stt_queue.get(timeout=1)
            except Empty:
                continue

            if job is None:
                return

            sid, data = job
            sec = len(data) / 2 / SR

            try:
                if sec < 0.45:
                    if current_mode == "robot":
                        action = {
                            "action": "NOOP" if UNSURE_POLICY == "NOOP" else "WIGGLE",
                            "sid": sid,
                            "meaningful": False,
                            "recognized": False,
                        }
                        send_action(conn, action, send_lock)
                    continue

                pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                rms_db, peak, clip = qc(pcm)
                log.debug("QC sid=%s rms=%.1fdBFS peak=%.3f clip=%.2f%%", sid, rms_db, peak, clip)

                if rms_db < -45.0:
                    if current_mode == "robot":
                        action = {
                            "action": "NOOP" if UNSURE_POLICY == "NOOP" else "WIGGLE",
                            "sid": sid,
                            "meaningful": False,
                            "recognized": False,
                        }
                        send_action(conn, action, send_lock)
                    continue

                pcm = trim_energy(pcm, SR)
                pcm = normalize_to_dbfs(pcm, target_dbfs=-22.0)

                # 녹음 파일 저장 비활성화
                # ts = time.strftime("%Y%m%d_%H%M%S")
                # wav_path = f"wav_logs/sid{sid}_{ts}_{len(pcm)/SR:.2f}s.wav"
                # save_wav(wav_path, pcm, SR)
                # log.info("Saved wav: %s", wav_path)

                text = ""
                try:
                    stt_start = time.time()
                    segments, _ = stt_engine.safe_transcribe(pcm)
                    text = clean_text("".join(seg.text for seg in segments))
                    perf_logger.log_stt(time.time() - stt_start)
                except Exception as exc:
                    log.exception("Transcribe failed sid=%s: %s", sid, exc)
                    perf_logger.log_error()
                    continue

                if text:
                    log.info("STT: %s (Mode: %s)", text, current_mode)
                else:
                    log.info("STT: (empty/filtered)")

                with state_lock:
                    cur = state["current_angle"]

                sys_action, meaningful, _ = robot_handler.process_text(text, cur)

                if meaningful and sys_action.get("action") == "SWITCH_MODE":
                    new_mode = sys_action.get("mode")
                    if new_mode in ["robot", "agent"]:
                        old_mode = current_mode
                        current_mode = new_mode
                        log.info("=" * 50)
                        log.info("모드 변경: %s -> %s", old_mode.upper(), current_mode.upper())
                        log.info("=" * 50)

                        notify_text = f"{new_mode} 모드로 변경되었습니다."
                        if current_mode == "agent":
                            wav_bytes = agent_handler.text_to_audio(notify_text)
                            if wav_bytes:
                                send_audio(conn, wav_bytes, send_lock)
                        else:
                            send_action(conn, {"action": "WIGGLE", "sid": sid}, send_lock)
                    continue

                if current_mode == "robot":
                    llm_start = time.time()
                    refined_text, robot_action = robot_handler.process_with_llm(text, cur)
                    perf_logger.log_llm(time.time() - llm_start)

                    if refined_text != text:
                        log.info("LLM Refined: %s -> %s", text, refined_text)

                    action = robot_action
                    action["sid"] = sid
                    action["meaningful"] = meaningful
                    action["recognized"] = bool(text)

                    if meaningful and "angle" in action:
                        with state_lock:
                            state["current_angle"] = action["angle"]

                    send_action(conn, action, send_lock)

                elif current_mode == "agent":
                    if not text:
                        continue

                    log.info("Agent Mode: Processing text: %s", text)
                    
                    llm_start = time.time()
                    response = agent_handler.generate_response(text)
                    perf_logger.log_llm(time.time() - llm_start)

                    if response:
                        log.info("Agent Response: %s", response)
                        tts_start = time.time()
                        wav_bytes = agent_handler.text_to_audio(response)
                        perf_logger.log_tts(time.time() - tts_start)
                        if wav_bytes:
                            log.info("Sending audio to device: %d bytes", len(wav_bytes))
                            success = send_audio(conn, wav_bytes, send_lock)
                            if success:
                                log.info("Audio sent successfully")
                            else:
                                log.error("Failed to send audio to device")
                        else:
                            log.error("TTS returned empty bytes")
                    else:
                        log.error("Agent generated empty response")

            except Exception as exc:
                log.exception("Worker error processing sid=%s: %s", sid, exc)
                perf_logger.log_error()

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    audio_buf = bytearray()
    last_status_log = time.time()

    while True:
        try:
            t = recv_exact(conn, 1)
            if t is None:
                log.info("Disconnect detected")
                break
            ptype = t[0]

            raw_len = recv_exact(conn, 2)
            if raw_len is None:
                log.info("Disconnect (len)")
                break
            (plen,) = __import__("struct").unpack("<H", raw_len)

            payload = b""
            if plen:
                payload = recv_exact(conn, plen)
                if payload is None:
                    log.info("Disconnect (payload)")
                    break

            if ptype == PTYPE_PING:
                send_pong(conn, send_lock)
                continue

            if ptype == PTYPE_START:
                with state_lock:
                    state["sid"] += 1
                    sid = state["sid"]
                audio_buf = bytearray()
                log.info("START (sid=%s)", sid)

            elif ptype == PTYPE_AUDIO:
                audio_buf.extend(payload)
                if len(audio_buf) > int(config.get("audio", "max_seconds", default=12) * SR * 2):
                    log.warning("Buffer too large -> force END")
                    ptype = PTYPE_END

            if ptype == PTYPE_END:
                with state_lock:
                    sid = state["sid"]
                data = bytes(audio_buf)
                sec = len(data) / 2 / SR
                log.info("END (sid=%s) bytes=%s sec=%.2f", sid, len(data), sec)

                job_queue.put(job_queue.stt_queue, (sid, data), drop_oldest=True)
                audio_buf = bytearray()

            if time.time() - last_status_log >= 10:
                last_status_log = time.time()
                log.info(
                    "Status: mode=%s stt_queue=%s model_loaded=%s",
                    current_mode,
                    job_queue.stt_queue.qsize(),
                    stt_engine.model is not None,
                )

        except Exception as exc:
            log.exception("Connection loop error: %s", exc)
            break

    stop_event.set()
    try:
        job_queue.put(job_queue.stt_queue, None, drop_oldest=False)
    except Exception:
        pass


def main():
    global robot_handler, agent_handler

    config = get_config()
    logging_config = config.get_logging_config()
    setup_logging(
        level=logging_config.get("level", "INFO"),
        save_to_file=logging_config.get("save_to_file", True),
        log_dir=logging_config.get("log_dir", "logs"),
    )
    log = __import__("logging").getLogger("server")

    load_commands_config()

    host = config.get("server", "host")
    port = config.get("server", "port")
    model_size = config.get("stt", "model_size")
    device = config.get("stt", "device")
    language = config.get("stt", "language", default="ko")

    weather_config = config.get_weather_config()
    assistant_config = config.get_assistant_config()
    tts_config = config.get_tts_config()

    robot_handler = RobotMode(ACTIONS_CONFIG, device)
    agent_handler = AgentMode(
        device,
        weather_config.get("api_key"),
        weather_config.get("location", "Seoul"),
        assistant_config.get("proactive", True),
        assistant_config.get("proactive_interval", 1800),
        tts_config.get("voice", "ko-KR-SunHiNeural"),
    )

    log.info(
        "Assistant: %s (%s)",
        assistant_config.get("name", "아이"),
        assistant_config.get("personality", "cheerful"),
    )

    robot_handler.load_model()
    agent_handler.load_model()

    stt_engine = STTEngine(model_size=model_size, device=device, language=language)

    perf_logger = get_performance_logger()
    signal.signal(signal.SIGINT, lambda *_: perf_logger.print_stats())

    conn_manager = ConnectionManager(
        host=host,
        port=port,
        handler=lambda conn, addr: handle_connection(conn, addr, stt_engine, config),
    )
    log.info("Server started. Default Mode: %s", current_mode)
    conn_manager.accept_loop()


if __name__ == "__main__":
    main()
