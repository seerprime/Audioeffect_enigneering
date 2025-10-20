import numpy as np
from scipy import signal


def low_pass_filter(audio: np.ndarray, fs: float, cutoff: float, order: int = 5) -> np.ndarray:
 
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    filtered = signal.filtfilt(b, a, audio.astype(np.float32))
    return filtered.astype(np.float32)


def high_pass_filter(audio: np.ndarray, fs: float, cutoff: float, order: int = 5) -> np.ndarray:
    
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='high', analog=False)
    filtered = signal.filtfilt(b, a, audio.astype(np.float32))
    return filtered.astype(np.float32)


def band_pass_filter(audio: np.ndarray, fs: float, lowcut: float, highcut: float, order: int = 5) -> np.ndarray:
    
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    filtered = signal.filtfilt(b, a, audio.astype(np.float32))
    return filtered.astype(np.float32)
