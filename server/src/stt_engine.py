import logging
import threading
import numpy as np
from faster_whisper import WhisperModel


log = logging.getLogger(__name__)


class STTEngine:
    def __init__(self, model_size: str, device: str, language: str = "ko"):
        self.model_size = model_size
        self.device = device
        self.language = language
        self.model_lock = threading.Lock()
        self.model = None
        self.device_in_use = None

    def load_model(self, device: str):
        log.info("Loading STT model: %s on %s...", self.model_size, device)
        m = WhisperModel(
            self.model_size,
            device=device,
            compute_type=("int8" if device == "cpu" else "int8"),
            cpu_threads=1,
            num_workers=1,
        )
        self.model = m
        self.device_in_use = device
        log.info("STT model loaded on %s", device)

    def ensure_model(self):
        if self.model is None:
            try:
                self.load_model(self.device)
            except Exception as exc:
                log.warning("GPU init failed -> fallback CPU: %s", exc)
                self.load_model("cpu")

    def safe_transcribe(self, pcm_f32: np.ndarray):
        self.ensure_model()
        pcm_f32 = np.ascontiguousarray(pcm_f32, dtype=np.float32)

        def _run():
            segments, info = self.model.transcribe(
                pcm_f32,
                language=self.language,
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
            return list(segments), info

        with self.model_lock:
            try:
                return _run()
            except RuntimeError as exc:
                msg = str(exc)
                if "cublas64_12.dll" in msg or "cublas" in msg:
                    log.error("CUDA runtime missing/broken -> switching to CPU now.")
                    self.load_model("cpu")
                    return _run()
                raise
