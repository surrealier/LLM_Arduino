"""
오디오 신호 처리 모듈
- 음성 품질 분석 및 정규화
- 에너지 기반 음성 구간 트리밍
- WAV 파일 저장 유틸리티
"""
import os
import wave
import numpy as np


def qc(pcm_f32: np.ndarray):
    """
    오디오 품질 분석 함수
    - RMS dB, 피크값, 클리핑 비율 계산
    - 음성 품질 평가를 위한 메트릭 제공
    """
    peak = float(np.max(np.abs(pcm_f32))) if pcm_f32.size else 0.0
    rms = float(np.sqrt(np.mean(pcm_f32**2) + 1e-12)) if pcm_f32.size else 0.0
    rms_db = 20.0 * np.log10(rms + 1e-12)  # RMS를 dB로 변환
    clip = float(np.mean(np.abs(pcm_f32) >= 0.999)) * 100.0  # 클리핑 비율 (%)
    return rms_db, peak, clip


def trim_energy(pcm: np.ndarray, sr: int, top_db: float = 35.0, pad_ms: int = 140):
    """
    에너지 기반 음성 구간 트리밍
    - 프레임별 RMS 에너지 계산하여 음성 구간 감지
    - 무음 구간 제거 및 패딩 적용
    """
    if pcm.size == 0:
        return pcm.astype(np.float32, copy=False)
    
    # 프레임 설정 (20ms 프레임, 홉 크기 동일)
    frame = int(sr * 0.02)
    hop = frame
    n = pcm.size
    if n < frame:
        return pcm.astype(np.float32, copy=False)

    # 프레임별 RMS 에너지 계산
    rms = []
    for i in range(0, n - frame + 1, hop):
        x = pcm[i : i + frame]
        rms.append(np.sqrt(np.mean(x * x) + 1e-12))
    rms = np.array(rms, dtype=np.float32)
    
    # 에너지 임계값 계산 (최대값 대비 -top_db)
    thr = float(np.max(rms)) * (10 ** (-top_db / 20.0))

    # 임계값 이상의 프레임 인덱스 찾기
    idx = np.where(rms > thr)[0]
    if idx.size == 0:
        return pcm.astype(np.float32, copy=False)

    # 음성 구간 시작/끝 계산 및 패딩 적용
    start_f = int(idx[0])
    end_f = int(idx[-1])
    start = max(0, start_f * hop - int(sr * pad_ms / 1000))
    end = min(n, (end_f * hop + frame) + int(sr * pad_ms / 1000))
    return pcm[start:end].astype(np.float32, copy=False)


def normalize_to_dbfs(pcm: np.ndarray, target_dbfs: float = -22.0, max_gain_db: float = 18.0):
    """
    dBFS 기준 오디오 정규화
    - 목표 dBFS 레벨로 오디오 볼륨 조정
    - 최대 게인 제한으로 과증폭 방지
    """
    rms = float(np.sqrt(np.mean(pcm * pcm) + 1e-12))
    rms_db = 20.0 * np.log10(rms + 1e-12)
    # 필요한 게인 계산 (제한 범위 내에서)
    gain_db = np.clip(target_dbfs - rms_db, -6.0, max_gain_db)
    gain = 10 ** (gain_db / 20.0)
    # 게인 적용 및 클리핑 방지
    return np.clip(pcm * gain, -1.0, 1.0).astype(np.float32, copy=False)


def save_wav(path: str, pcm_f32: np.ndarray, sr: int):
    """
    PCM 데이터를 WAV 파일로 저장
    - float32 → int16 변환
    - 디렉토리 자동 생성
    """
    # float32를 int16으로 변환 (클리핑 적용)
    x = np.clip(pcm_f32, -1.0, 1.0)
    x16 = (x * 32767.0).astype(np.int16)
    
    # 디렉토리 생성 및 WAV 파일 저장
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)      # 모노
        wf.setsampwidth(2)      # 16비트
        wf.setframerate(sr)     # 샘플레이트
        wf.writeframes(x16.tobytes())