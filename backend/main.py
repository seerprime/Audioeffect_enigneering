# backend/main.py
import os
import tempfile
import uuid
from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template_string,
)
from werkzeug.utils import safe_join

import numpy as np
import soundfile as sf
import librosa

# Import user's modules (assumes they exist in same backend folder or PYTHONPATH)
from modules.amplitude_processing import gain_control, normalize_audio
from modules.effect_processing import apply_reverb, smoothing_filter, soft_limiter
from modules.frequency_filters import (
    low_pass_filter,
    high_pass_filter,
    band_pass_filter,
)

app = Flask(__name__, static_folder="../frontend", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB uploads
TMP_DIR = tempfile.gettempdir()
OUT_DIR = os.path.join(TMP_DIR, "audio_process_outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def _make_filename(prefix="out", ext=".wav"):
    return os.path.join(OUT_DIR, f"{prefix}_{uuid.uuid4().hex}{ext}")


def _ensure_mono(y: np.ndarray) -> np.ndarray:
    """
    Return mono (1D) array.
    Handles either:
      - soundfile shape: (frames, channels)  -> average axis=1
      - librosa (mono=False) shape: (channels, samples) -> average axis=0
    """
    if y is None:
        return y
    y = np.asarray(y)
    if y.ndim == 1:
        return y
    # decide which axis is time (longer dimension)
    if y.shape[0] >= y.shape[1]:
        # probably (frames, channels)
        return np.mean(y, axis=1)
    else:
        # probably (channels, samples)
        return np.mean(y, axis=0)


def _generate_impulse_response(sr: int, length_sec: float = 1.0, decay: float = 3.0):
    """Create a simple reverb IR (exponential decay)."""
    t = np.linspace(0, length_sec, int(sr * length_sec), endpoint=False)
    ir = np.exp(-decay * t)
    # small noise to make it less sterile
    ir *= np.random.uniform(0.9, 1.1, size=ir.shape).astype(np.float32)
    return ir.astype(np.float32)


def apply_pipeline(y: np.ndarray, sr: int, settings: dict) -> np.ndarray:
    """
    settings: dict containing booleans/values for all controls.
    Expected keys:
      gain_db, normalize (bool), reverb (bool), reverb_ir (None or path),
      smoothing_k, soft_limiter_th,
      low_pass_cutoff, high_pass_cutoff, band_low, band_high, filter_order
    """
    x = y.astype(np.float32).copy()

    # Gain
    gain_db = float(settings.get("gain_db", 0.0))
    if abs(gain_db) > 0.0001:
        x = gain_control(x, gain_db)

    # Normalize
    if settings.get("normalize", False):
        x = normalize_audio(x, target_peak=0.99)

    # Reverb
    if settings.get("reverb", False):
        # If user provided an IR file path (not implemented via upload here), else generate IR
        ir_path = settings.get("reverb_ir", None)
        if ir_path and os.path.exists(ir_path):
            ir, _ = librosa.load(ir_path, sr=sr, mono=True)
        else:
            ir = _generate_impulse_response(sr, length_sec=1.2, decay=3.0)
        x = apply_reverb(x, ir, mode="full")

    # Smoothing filter (moving average)
    k = int(settings.get("smoothing_k", 1))
    if k is None:
        k = 1
    if k > 1:
        x = smoothing_filter(x, kernel_size=k)

    # Soft limiter
    limiter_th = float(settings.get("soft_limiter_th", 0.9))
    if 0.0 < limiter_th < 1.0:
        x = soft_limiter(x, threshold=limiter_th)

    # Frequency filters - apply in sequence if values provided
    order = int(settings.get("filter_order", 5))
    # Low-pass
    low_cut = settings.get("low_pass_cutoff", None)
    if low_cut:
        low_cut = float(low_cut)
        try:
            x = low_pass_filter(x, fs=sr, cutoff=low_cut, order=order)
        except Exception:
            pass

    # High-pass
    high_cut = settings.get("high_pass_cutoff", None)
    if high_cut:
        high_cut = float(high_cut)
        try:
            x = high_pass_filter(x, fs=sr, cutoff=high_cut, order=order)
        except Exception:
            pass

    # Band-pass (overrides other filters if provided both)
    band_low = settings.get("band_low", None)
    band_high = settings.get("band_high", None)
    if band_low and band_high:
        try:
            bl = float(band_low)
            bh = float(band_high)
            x = band_pass_filter(x, fs=sr, lowcut=bl, highcut=bh, order=order)
        except Exception:
            pass

    # Final safety normalization / clipping to [-1,1]
    peak = np.max(np.abs(x)) if x.size else 0.0
    if peak > 0:
        # keep it reasonable
        if peak > 1.0:
            x = x / peak
    x = np.clip(x, -1.0, 1.0)
    return x.astype(np.float32)


@app.route("/")
def index():
    # Serve frontend index.html from static folder
    return app.send_static_file("index.html")


@app.route("/upload", methods=["POST"])
def upload_and_process():
    """
    Accepts multipart/form-data:
      - file: audio file (wav, mp3, mp4, etc)
      - settings: JSON string with parameters
    Returns JSON:
      { original_url, processed_url, download_url }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No selected file"}), 400

    settings = {}
    # attempt to read JSON settings
    try:
        if "settings" in request.form:
            import json
            settings = json.loads(request.form["settings"])
    except Exception:
        settings = {}

    # Save input file temporarly
    in_path = _make_filename(prefix="in", ext=os.path.splitext(f.filename)[1] or ".wav")
    f.save(in_path)

    # Try decoding with soundfile first (often more reliable & full-length)
    try:
        data, sr = sf.read(in_path, always_2d=False)
        y = np.asarray(data).astype(np.float32)
    except Exception:
        # fallback to librosa
        try:
            y, sr = librosa.load(in_path, sr=None, mono=False)
            y = np.asarray(y).astype(np.float32)
        except Exception as e:
            return jsonify({"error": f"Could not read uploaded audio: {e}"}), 400

    # convert to mono for processing convenience
    y_mono = _ensure_mono(y)

    # Process
    try:
        processed = apply_pipeline(y_mono, sr, settings)
    except Exception as e:
        return jsonify({"error": f"Processing error: {e}"}), 500

    # Save processed wav (16-bit PCM)
    out_path = _make_filename(prefix="processed", ext=".wav")
    # soundfile will accept float32; use subtype PCM_16 to be broadly supported
    sf.write(out_path, processed, sr, subtype="PCM_16")

    # Also copy original (converted to WAV for consistent playback)
    orig_out_path = _make_filename(prefix="original", ext=".wav")
    try:
        sf.write(orig_out_path, _ensure_mono(y).astype(np.float32), sr, subtype="PCM_16")
    except Exception:
        # fallback: return the uploaded file as-is
        orig_out_path = in_path

    response = {
        "original_url": f"/file/{os.path.basename(orig_out_path)}",
        "processed_url": f"/file/{os.path.basename(out_path)}",
        "download_url": f"/file/{os.path.basename(out_path)}?dl=1",
    }
    return jsonify(response)


@app.route("/file/<filename>")
def serve_file(filename):
    # serve from OUT_DIR with safe join
    file_path = safe_join(OUT_DIR, filename)
    if not file_path or not os.path.exists(file_path):
        # try to find in temp dir as fallback
        alt_path = os.path.join(TMP_DIR, filename)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            return jsonify({"error": "file not found"}), 404

    # allow download param
    if request.args.get("dl") == "1":
        return send_file(file_path, as_attachment=True)
    return send_file(file_path, mimetype="audio/wav")


if __name__ == "__main__":
    # run dev
    app.run(host="0.0.0.0", port=5000, debug=True)
