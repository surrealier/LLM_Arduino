import numpy as np

from src import audio_processor


def test_qc_and_normalize():
    sr = 16000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    pcm = 0.1 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    rms_db, peak, clip = audio_processor.qc(pcm)
    assert rms_db < 0
    assert 0 < peak < 1
    assert clip == 0.0

    normalized = audio_processor.normalize_to_dbfs(pcm, target_dbfs=-22.0)
    new_rms_db, _, _ = audio_processor.qc(normalized)
    assert new_rms_db > rms_db
