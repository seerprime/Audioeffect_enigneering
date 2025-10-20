import numpy as np
from scipy import signal


def apply_reverb(audio: np.ndarray, ir: np.ndarray, mode: str = "full") -> np.ndarray:
    audio = audio.astype(np.float32)
    ir = ir.astype(np.float32)

    out = signal.fftconvolve(audio, ir, mode=mode)
    return out.astype(np.float32)


def smoothing_filter(audio: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    if kernel_size <= 1:
        return audio.copy()

    kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
    out = np.convolve(audio.astype(np.float32), kernel, mode="same")

    return out.astype(np.float32)


def soft_limiter(audio: np.ndarray, threshold: float = 0.9) -> np.ndarray:
    x = audio.astype(np.float32)
    limit = float(threshold)
    hardness = 3.0  # higher = steeper compression

    above = np.abs(x) > limit
    out = x.copy()

    # apply tanh smoothing beyond threshold
    out[above] = np.sign(x[above]) * limit * (
        1.0 + np.tanh(hardness * (np.abs(x[above]) - limit))
    )

    # safety clip in float space
    out = np.clip(out, -1.0, 1.0)
    return out.astype(np.float32)