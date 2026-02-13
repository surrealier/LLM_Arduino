import numpy as np

import src.stt_engine as stt_engine_module
from src.stt_engine import STTEngine


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def transcribe(self, pcm_f32, **kwargs):
        return [FakeSegment("테스트")], {"language": "ko"}


def test_safe_transcribe_with_fake_model():
    engine = STTEngine(model_size="tiny", device="cpu", language="ko")
    engine.model = FakeModel()
    pcm = np.zeros(16000, dtype=np.float32)

    segments, info = engine.safe_transcribe(pcm)
    assert segments[0].text == "테스트"
    assert info["language"] == "ko"


def test_load_model_on_cuda_runs_runtime_preflight(monkeypatch):
    calls = []

    def fake_ensure():
        calls.append("ensure")

    def fake_preload():
        calls.append("preload")

    class DummyWhisperModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(STTEngine, "_ensure_cuda_runtime_paths", staticmethod(fake_ensure))
    monkeypatch.setattr(STTEngine, "_preload_cuda_runtime", staticmethod(fake_preload))
    monkeypatch.setattr(stt_engine_module, "WhisperModel", DummyWhisperModel)

    engine = STTEngine(model_size="tiny", device="cuda", language="ko")
    engine.load_model("cuda")

    assert calls == ["ensure", "preload"]
    assert engine.device_in_use == "cuda"


def test_safe_transcribe_cuda_runtime_error_with_cuda_index_falls_back_to_cpu(monkeypatch):
    class RuntimeErrorModel:
        def transcribe(self, pcm_f32, **kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    class CpuModel:
        def transcribe(self, pcm_f32, **kwargs):
            return [FakeSegment("복구")], {"language": "ko"}

    engine = STTEngine(model_size="tiny", device="cuda", language="ko")
    engine.model = RuntimeErrorModel()
    engine.device_in_use = "cuda:0"

    loaded = []

    def fake_load_model(device):
        loaded.append(device)
        engine.model = CpuModel()
        engine.device_in_use = device

    monkeypatch.setattr(engine, "load_model", fake_load_model)

    segments, info = engine.safe_transcribe(np.zeros(800, dtype=np.float32))
    assert loaded == ["cpu"]
    assert segments[0].text == "복구"
    assert info["language"] == "ko"
