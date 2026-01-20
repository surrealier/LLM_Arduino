import os
import wave
import numpy as np


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
        x = pcm[i : i + frame]
        rms.append(np.sqrt(np.mean(x * x) + 1e-12))
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
    rms = float(np.sqrt(np.mean(pcm * pcm) + 1e-12))
    rms_db = 20.0 * np.log10(rms + 1e-12)
    gain_db = np.clip(target_dbfs - rms_db, -6.0, max_gain_db)
    gain = 10 ** (gain_db / 20.0)
    return np.clip(pcm * gain, -1.0, 1.0).astype(np.float32, copy=False)


def save_wav(path: str, pcm_f32: np.ndarray, sr: int):
    x = np.clip(pcm_f32, -1.0, 1.0)
    x16 = (x * 32767.0).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(x16.tobytes())
