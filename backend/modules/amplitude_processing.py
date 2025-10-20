import librosa as lib
import numpy as np
from import_engine import get_audio_file, pick_audio_file

audio_original = None   # float audio only
sample_rate = None
audio_current = None    # working buffer

def upload():
    pick_audio_file()

def loadfile():
    global audio_original, sample_rate
    upload()
    try:
        y, sr = lib.load(get_audio_file(), sr=None)  # exact unpack!
        audio_original = y
        sample_rate = sr
        print("Loaded:", get_audio_file())

    except RuntimeError as e:
        print("No Audio file selected", e)

def gain_control(audio_imported, gain_db: float):
    global audio_current
    
    gain_factor = 10 ** (gain_db / 20)
    x = audio_imported.astype(np.float32)
    out = x * gain_factor

    # float audio from librosa => NO integer clipping needed
    audio_current = out
    return out

def normalize_audio(audio_imported, target_peak=0.99):
    x = audio_imported.astype(np.float32)
    peak = np.max(np.abs(x))
    if peak == 0:
        return audio_imported
    out = x * (target_peak / peak)
    return out
