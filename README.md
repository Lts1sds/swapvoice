# swapvoice

**Swap the voice in any video with a completely different one.** No GPU required, no model training, no API keys, no cost.

![web ui](docs/screenshot.png)

English | [简体中文](README.zh-CN.md)

## How it works

swapvoice does not "transform" the original voice — it **re-dubs** the video:

```
video ──► extract audio ──► Whisper ASR (local, CPU or GPU) ──► text + timestamps
                                                                      │
new video ◄── remux (video stream untouched) ◄── align to timeline ◄── TTS with a new voice
```

The picture stays bit-identical; only the audio track is rebuilt. Because the new voice is generated from the recognized text and placed back at the original timestamps, what you hear is a different person saying exactly the same things.

## Features

- **22 neural voices** — Mandarin female/male, Taiwan-accented, Cantonese, Northeast/Shaanxi dialects, English (US/UK), Japanese, Korean
- **Auto language matching** — detects the video's language; if it doesn't fit the chosen voice, swaps to a matching-gender voice of that language automatically (15 languages covered)
- **GPU auto-detect** — uses CUDA when an NVIDIA GPU is present, silently falls back to CPU otherwise
- **Two frontends** — drag-and-drop CLI, and a local web UI with upload progress, live log, built-in preview player and download
- **2 instant pitch modes** — raise/lower pitch without re-dubbing; long videos are split at detected speech pauses and processed in parallel chunks, so a 1-hour video finishes in about a minute on CPU
- **Completely free** — TTS runs on Microsoft's public edge-tts endpoint; ASR runs locally. No keys, no accounts.

## Performance

Measured on a laptop with **integrated graphics only** (pure CPU): recognition runs at **~1.7x realtime** (whisper-medium, int8, VAD on, batched inference with word-level timestamps) and TTS runs in parallel with recognition — a 30-minute video finishes in roughly 20 minutes. With an NVIDIA GPU the ASR stage is several times faster.

## Install

```bash
pip install -r requirements.txt
python download_model.py
```

- `download_model.py` fetches the ~1.5 GB whisper-medium model (one time only). It defaults to the `hf-mirror.com` mirror for mainland China; overseas users can set `HF_ENDPOINT=https://huggingface.co`.
- **ffmpeg** must be reachable: either on `PATH`, or point the `VOICECHANGER_FFMPEG` environment variable to its directory.

## Usage

**CLI** (interactive voice menu):

```bash
python change_voice.py your_video.mp4
```

**Web UI**:

```bash
python web_server.py            # open http://127.0.0.1:8765
python web_server.py --share    # allow LAN access
```

**Windows shortcuts**: double-click `start-cli.bat` / `start-web.bat`, or drag a video file onto `start-cli.bat`.

Output is saved next to the input as `<name>_换声_<voice>.mp4`.

## Limitations

- Background music is replaced — the whole audio track is rebuilt from the new voice
- This is re-dubbing, not voice cloning: the new voice is a TTS voice, not a transformation of the original speaker's timbre
- Recognition accuracy caps the quality: a misrecognized word will be re-spoken wrong

## License

[MIT](LICENSE)
