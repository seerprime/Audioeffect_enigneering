# file_picker.py
import tkinter as tk
from tkinter import filedialog

AUDIO_FILE = None   # global "environment-like" variable

def pick_audio_file():
    
    global AUDIO_FILE
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select WAV or MP4",
        filetypes=[("Audio Files", "*.wav *.mp4 *.mp3"), ("All Files", "*.*")]
    )
    if file_path:
        AUDIO_FILE = file_path
        print(f"[OK] Selected file: {AUDIO_FILE}")
    else:
        print("[!] No file selected.")

def get_audio_file():
    """Access the saved file path everywhere"""
    global AUDIO_FILE
    if AUDIO_FILE is None:
        raise RuntimeError("No audio file selected yet. Call pick_audio_file() first.")
    return AUDIO_FILE

