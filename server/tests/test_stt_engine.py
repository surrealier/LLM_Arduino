import numpy as np

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
