// frontend/script.js
// Handles UI, upload, waveform drawing, and interactions

const fileInput = document.getElementById("fileInput");
const btnUpload = document.getElementById("btnUpload");
const btnApply = document.getElementById("btnApply");
const audioOrig = document.getElementById("audioOrig");
const audioProc = document.getElementById("audioProc");
const status = document.getElementById("status");
const downloadLink = document.getElementById("downloadLink");

// controls
const gainSlider = document.getElementById("gain_db");
const gainVal = document.getElementById("gainVal");
const normalize = document.getElementById("normalize");
const reverb = document.getElementById("reverb");
const reverb_len = document.getElementById("reverb_len");
const smoothing_k = document.getElementById("smoothing_k");
const soft_limiter_th = document.getElementById("soft_limiter_th");
const limVal = document.getElementById("limVal");
const low_pass_cutoff = document.getElementById("low_pass_cutoff");
const high_pass_cutoff = document.getElementById("high_pass_cutoff");
const band_low = document.getElementById("band_low");
const band_high = document.getElementById("band_high");
const filter_order = document.getElementById("filter_order");

// canvases
const canvasOrig = document.getElementById("canvasOrig");
const canvasProc = document.getElementById("canvasProc");

const ctxOrig = canvasOrig.getContext("2d");
const ctxProc = canvasProc.getContext("2d");

let uploadedFile = null;
let origUrl = null;
let procUrl = null;

gainSlider.addEventListener("input", () => {
  gainVal.textContent = gainSlider.value;
});
soft_limiter_th.addEventListener("input", () => {
  limVal.textContent = soft_limiter_th.value;
});

// helper: draw waveform from audio buffer (Float32Array mono)
function drawWave(canvasCtx, samples) {
  const w = canvasCtx.canvas.width;
  const h = canvasCtx.canvas.height;
  canvasCtx.clearRect(0, 0, w, h);

  canvasCtx.fillStyle = "rgba(255,255,255,0.02)";
  canvasCtx.fillRect(0, 0, w, h);

  canvasCtx.lineWidth = 1.2;
  canvasCtx.strokeStyle = "#6ee7b7";
  canvasCtx.beginPath();

  const step = Math.ceil(samples.length / w);
  const amp = h / 2;
  for (let i = 0; i < w; i++) {
    const start = i * step;
    let min = 1.0;
    let max = -1.0;
    for (let j = 0; j < step && (start + j) < samples.length; j++) {
      const v = samples[start + j];
      if (v < min) min = v;
      if (v > max) max = v;
    }
    const y1 = (1 + min) * amp;
    const y2 = (1 + max) * amp;
    canvasCtx.moveTo(i, y1);
    canvasCtx.lineTo(i, y2);
  }
  canvasCtx.stroke();
}

// decode audio ArrayBuffer into Float32 samples mono using AudioContext
async function decodeAudioBuffer(arrayBuffer) {
  const ac = new (window.AudioContext || window.webkitAudioContext)();
  const audioBuffer = await ac.decodeAudioData(arrayBuffer);
  const ch = audioBuffer.numberOfChannels;
  const data = audioBuffer.getChannelData(0).slice(0); // start with first channel
  if (ch > 1) {
    // mix to mono by averaging (simple)
    const tmp = new Float32Array(audioBuffer.length);
    for (let c = 0; c < ch; c++) {
      const channelData = audioBuffer.getChannelData(c);
      for (let i = 0; i < channelData.length; i++) tmp[i] += channelData[i] / ch;
    }
    return tmp;
  }
  return data;
}

btnUpload.addEventListener("click", async (e) => {
  if (!fileInput.files || !fileInput.files[0]) {
    status.textContent = "Please choose an audio file first.";
    return;
  }
  uploadedFile = fileInput.files[0];
  status.textContent = "Previewing file locally...";

  // preview original locally (no server yet)
  const url = URL.createObjectURL(uploadedFile);
  audioOrig.src = url;
  // draw waveform locally
  const ab = await uploadedFile.arrayBuffer();
  try {
    const samples = await decodeAudioBuffer(ab);
    drawWave(ctxOrig, samples);
  } catch (err) {
    console.warn("Could not decode for waveform:", err);
  }
  status.textContent = `Loaded ${uploadedFile.name}`;
});

// helper to collect settings
function getSettings() {
  return {
    gain_db: parseFloat(gainSlider.value),
    normalize: normalize.checked,
    reverb: reverb.checked,
    reverb_len: parseFloat(reverb_len.value) || 1.0,
    smoothing_k: parseInt(smoothing_k.value) || 1,
    soft_limiter_th: parseFloat(soft_limiter_th.value) || 0.9,
    low_pass_cutoff: low_pass_cutoff.value ? parseFloat(low_pass_cutoff.value) : null,
    high_pass_cutoff: high_pass_cutoff.value ? parseFloat(high_pass_cutoff.value) : null,
    band_low: band_low.value ? parseFloat(band_low.value) : null,
    band_high: band_high.value ? parseFloat(band_high.value) : null,
    filter_order: parseInt(filter_order.value) || 5,
  };
}

btnApply.addEventListener("click", async (e) => {
  if (!uploadedFile) {
    status.textContent = "Please upload a file first.";
    return;
  }
  status.textContent = "Uploading and processing...";
  btnApply.disabled = true;
  btnUpload.disabled = true;

  const fd = new FormData();
  fd.append("file", uploadedFile);
  fd.append("settings", JSON.stringify(getSettings()));

  try {
    const resp = await fetch("/upload", { method: "POST", body: fd });
    if (!resp.ok) {
      const err = await resp.json().catch(()=>({error:"unknown"}));
      status.textContent = "Error: " + (err.error || resp.statusText);
      btnApply.disabled = false;
      btnUpload.disabled = false;
      return;
    }
    const json = await resp.json();
    // set players
    audioOrig.src = json.original_url;
    audioProc.src = json.processed_url;
    downloadLink.href = json.download_url;

    // fetch processed audio and draw waveform
    try {
      const ab = await (await fetch(json.processed_url)).arrayBuffer();
      const samples = await decodeAudioBuffer(ab);
      drawWave(ctxProc, samples);
    } catch (err) {
      console.warn("Could not fetch or decode processed:", err);
    }

    status.textContent = "Processing complete.";
  } catch (err) {
    status.textContent = "Upload failed: " + err.message;
  } finally {
    btnApply.disabled = false;
    btnUpload.disabled = false;
  }
});
