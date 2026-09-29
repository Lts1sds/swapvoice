import os, sys, subprocess, asyncio, tempfile, wave, time, shutil


def _find_exe(name):
    p = shutil.which(name)
    if p:
        return p
    env_dir = os.environ.get("VOICECHANGER_FFMPEG")
    if env_dir:
        p = os.path.join(env_dir, name + (".exe" if os.name == "nt" else ""))
        if os.path.isfile(p):
            return p
    fallback = os.path.join(r"D:\pyvideotrans\ffmpeg", name + ".exe")
    if os.path.isfile(fallback):
        return fallback
    raise RuntimeError(f"未找到 {name}。请安装 ffmpeg 并加入 PATH，或设置环境变量 VOICECHANGER_FFMPEG 指向 ffmpeg 所在目录")


FFMPEG = _find_exe("ffmpeg")
FFPROBE = _find_exe("ffprobe")
MODEL_DIR = os.environ.get("VOICECHANGER_MODEL") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "whisper-medium")
SR = 16000

VOICES = [
    ("zh-CN-XiaoxiaoNeural", "温柔大方（晓晓）", "晓晓", "f", "zh", "中文女声"),
    ("zh-CN-XiaoyiNeural", "活泼开朗（晓伊）", "晓伊", "f", "zh", "中文女声"),
    ("zh-TW-HsiaoChenNeural", "台湾腔（曉臻）", "台湾女声", "f", "zh", "中文女声"),
    ("zh-HK-HiuMaanNeural", "粤语（曉曼）", "粤语女声", "f", "zh", "中文女声"),
    ("zh-CN-YunxiNeural", "阳光少年（云希）", "云希", "m", "zh", "中文男声"),
    ("zh-CN-YunjianNeural", "沉稳磁性（云健）", "云健", "m", "zh", "中文男声"),
    ("zh-CN-YunyangNeural", "新闻播音（云扬）", "云扬", "m", "zh", "中文男声"),
    ("zh-CN-YunxiaNeural", "青春少年（云夏）", "云夏", "m", "zh", "中文男声"),
    ("zh-TW-YunJheNeural", "台湾腔（雲哲）", "台湾男声", "m", "zh", "中文男声"),
    ("zh-HK-WanLungNeural", "粤语（雲龍）", "粤语男声", "m", "zh", "中文男声"),
    ("zh-CN-liaoning-XiaobeiNeural", "东北话（小北）", "东北话", "f", "zh", "方言"),
    ("zh-CN-shaanxi-XiaoniNeural", "陕西话（小妮）", "陕西话", "f", "zh", "方言"),
    ("en-US-JennyNeural", "美音（Jenny）", "英语Jenny", "f", "en", "英语女声"),
    ("en-US-AriaNeural", "美音（Aria）", "英语Aria", "f", "en", "英语女声"),
    ("en-GB-SoniaNeural", "英音（Sonia）", "英语Sonia", "f", "en", "英语女声"),
    ("en-US-GuyNeural", "美音（Guy）", "英语Guy", "m", "en", "英语男声"),
    ("en-US-AndrewNeural", "美音（Andrew）", "英语Andrew", "m", "en", "英语男声"),
    ("en-GB-RyanNeural", "英音（Ryan）", "英语Ryan", "m", "en", "英语男声"),
    ("ja-JP-NanamiNeural", "女声（七海）", "日语女声", "f", "ja", "日语"),
    ("ja-JP-KeitaNeural", "男声（圭太）", "日语男声", "m", "ja", "日语"),
    ("ko-KR-SunHiNeural", "女声（SunHi）", "韩语女声", "f", "ko", "韩语"),
    ("ko-KR-InJoonNeural", "男声（InJoon）", "韩语男声", "m", "ko", "韩语"),
]

LANG_DEFAULTS = {
    "zh": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"),
    "yue": ("zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural"),
    "en": ("en-US-JennyNeural", "en-US-GuyNeural"),
    "ja": ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
    "ko": ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural"),
    "fr": ("fr-FR-DeniseNeural", "fr-FR-HenriNeural"),
    "de": ("de-DE-KatjaNeural", "de-DE-ConradNeural"),
    "es": ("es-ES-ElviraNeural", "es-ES-AlvaroNeural"),
    "ru": ("ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"),
    "it": ("it-IT-ElsaNeural", "it-IT-DiegoNeural"),
    "pt": ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"),
    "vi": ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"),
    "th": ("th-TH-PremwadeeNeural", "th-TH-NiwatNeural"),
    "id": ("id-ID-GadisNeural", "id-ID-ArdiNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
}

PITCH_UP = len(VOICES) + 1
PITCH_DOWN = len(VOICES) + 2


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[-800:])
    return r


def probe_duration(path):
    r = run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.decode().strip())


def probe_codec(path):
    r = run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", path])
    return r.stdout.decode().strip()


def read_wav(path):
    import numpy as np
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def short_name(voice_id):
    return voice_id.replace("Neural", "").split("-")[-1]


def detect_device():
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() >= 1:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


async def tts_one(text, voice, out_mp3):
    import edge_tts
    delays = [2, 4, 8, 16, 30]
    for attempt in range(5):
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice).save(out_mp3), timeout=60)
            return
        except Exception:
            if attempt == 4:
                raise
            await asyncio.sleep(delays[attempt])


async def tts_all(items, voice, tmpdir, on_done=None):
    sem = asyncio.Semaphore(2)
    failed = []

    async def work(i, text):
        mp3 = os.path.join(tmpdir, f"seg{i}.mp3")
        async with sem:
            try:
                await tts_one(text, voice, mp3)
            except Exception:
                failed.append((i, text))
        if on_done:
            on_done()

    await asyncio.gather(*[work(i, t) for i, t in items])
    if failed:
        await asyncio.sleep(10)
        for i, text in failed:
            try:
                await asyncio.sleep(3)
                await tts_one(text, voice, os.path.join(tmpdir, f"seg{i}.mp3"))
            except Exception:
                print(f"  第 {i+1} 段最终失败，将跳过：{text[:20]}")
        if on_done:
            on_done()


def _silence_points(src):
    import re
    r = subprocess.run([FFMPEG, "-i", src, "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"], capture_output=True)
    err = r.stderr.decode("utf-8", "ignore")
    starts = [float(m) for m in re.findall(r"silence_start: ([0-9.]+)", err)]
    ends = [float(m) for m in re.findall(r"silence_end: ([0-9.]+)", err)]
    return [(a + b) / 2 for a, b in zip(starts, ends) if b - a >= 0.25]


def pitch_mode(src, dst, factor, progress=None):
    dur = probe_duration(src)
    sr = int(run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", src]).stdout.decode().strip() or 48000)
    af = f"asetrate={int(sr*factor)},aresample={sr},atempo={1/factor}"

    n = max(1, min(10, int(dur // 420)))
    splits = []
    if n >= 2:
        sil = _silence_points(src)
        for i in range(1, n):
            t = dur * i / n
            cands = [p for p in sil if abs(p - t) < 60 and all(abs(p - q) > 30 for q in splits)]
            if cands:
                splits.append(min(cands, key=lambda p: abs(p - t)))

    if len(splits) == 0:
        run([FFMPEG, "-y", "-i", src, "-map", "0:v", "-map", "0:a", "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", dst])
        return

    if progress:
        progress("pitch", 15, f"检测到语音停顿，{len(splits)+1} 路并行加速处理...")
    p = 1024 / sr
    bounds = [0] + sorted(splits) + [dur]
    tmpdir = tempfile.mkdtemp(prefix="vp_")
    try:
        procs = []
        for i in range(len(bounds) - 1):
            s = bounds[i]
            e = dur if i == len(bounds) - 2 else bounds[i + 1] - p
            chain = f"atrim=start={s:.4f}:end={e:.4f},{af},asetpts=PTS-STARTPTS"
            procs.append(subprocess.Popen(
                [FFMPEG, "-y", "-nostdin", "-threads", "1", "-filter_threads", "1", "-i", src, "-map", "0:a", "-af", chain, "-c:a", "aac", "-b:a", "192k", os.path.join(tmpdir, f"c{i}.m4a")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for pr in procs:
            if pr.wait() != 0:
                raise RuntimeError("并行变调失败")
        lst = os.path.join(tmpdir, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for i in range(len(bounds) - 1):
                f.write(f"file '{os.path.join(tmpdir, f'c{i}.m4a')}'\n")
        merged = os.path.join(tmpdir, "pitch.m4a")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", merged])
        if progress:
            progress("pitch", 80, "正在合成视频...")
        run([FFMPEG, "-y", "-i", src, "-i", merged, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest", dst])
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def process(video, choice, progress=None, device=None):
    def emit(stage, pct, msg):
        if progress:
            progress(stage, pct, msg)

    base, _ = os.path.splitext(video)

    if choice == PITCH_UP or choice == PITCH_DOWN:
        factor = 1.25 if choice == PITCH_UP else 0.8
        tag = "声音变高" if choice == PITCH_UP else "声音变低"
        out = f"{base}_换声_{tag}.mp4"
        emit("pitch", 10, "正在快速变调...")
        pitch_mode(video, out, factor, emit)
        emit("pitch", 100, "完成")
        return out

    voice, label, file_label, gender, family, _ = VOICES[choice - 1]
    out = f"{base}_换声_{file_label}.mp4"
    tmpdir = tempfile.mkdtemp(prefix="vc_")
    if not os.path.isfile(os.path.join(MODEL_DIR, "model.bin")):
        raise RuntimeError("语音识别模型未下载。请先运行：python download_model.py")
    try:
        emit("extract", 3, "第一步：提取音频...")
        audio_wav = os.path.join(tmpdir, "audio.wav")
        run([FFMPEG, "-y", "-i", video, "-vn", "-ac", "1", "-ar", str(SR), "-f", "wav", audio_wav])
        audio_dur = probe_duration(audio_wav)

        if device is None:
            device, ctype = detect_device()
        else:
            ctype = "float16" if device == "cuda" else "int8"
        if device == "cuda":
            emit("asr", 8, "检测到独立显卡，使用 GPU 加速识别...")
        else:
            emit("asr", 8, "未检测到 NVIDIA 独显，使用 CPU 识别（约 1.5 倍实时速度）...")

        from faster_whisper import WhisperModel
        try:
            model = WhisperModel(MODEL_DIR, device=device, compute_type=ctype)
        except Exception:
            if device == "cuda":
                emit("asr", 8, "GPU 加载失败（可能缺 CUDA 组件），已回退 CPU...")
                device, ctype = "cpu", "int8"
                model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
            else:
                raise

        emit("asr", 10, "第二步：识别语音内容...")
        segs, info = model.transcribe(audio_wav, vad_filter=True, beam_size=1)
        expected = audio_dur / (6.0 if device == "cuda" else 1.4)
        t0 = time.time()
        seg_list = []
        for s in segs:
            if s.text.strip():
                seg_list.append((s.start, s.end, s.text.strip()))
            emit("asr", min(55, 10 + 45 * (time.time() - t0) / max(expected, 1)), f"识别中... 已识别 {len(seg_list)} 段")
        if not seg_list:
            raise RuntimeError("没有识别到语音，可能是视频里没有人说话。")
        emit("asr", 55, f"识别完成，共 {len(seg_list)} 段语音，语言：{info.language}")

        detected = info.language
        if family == "zh" and detected in ("zh", "yue"):
            pass
        elif family == detected:
            pass
        elif detected in LANG_DEFAULTS:
            new_voice = LANG_DEFAULTS[detected][0 if gender == "f" else 1]
            emit("tts", 55, f"检测到视频语言与所选音色不匹配，已自动切换音色：{short_name(new_voice)}")
            voice, file_label = new_voice, short_name(new_voice)
            out = f"{base}_换声_{file_label}.mp4"
        else:
            emit("tts", 55, f"警告：检测到语言 {detected}，所选音色可能不适用，效果可能不佳")

        emit("tts", 56, f"第三步：用新声音重新配音（{len(seg_list)} 段）...")

        def on_done():
            done_count[0] += 1
            emit("tts", 56 + 34 * done_count[0] / len(seg_list), f"配音中... {done_count[0]}/{len(seg_list)}")

        done_count = [0]
        asyncio.run(tts_all([(i, seg_list[i][2]) for i in range(len(seg_list))], voice, tmpdir, on_done))

        import numpy as np
        emit("align", 91, "第四步：对齐时间轴...")
        dur = probe_duration(video)
        total = int(dur * SR) + SR
        track = np.zeros(total, dtype=np.int16)
        cursor = 0
        for i, (start, end, text) in enumerate(seg_list):
            mp3 = os.path.join(tmpdir, f"seg{i}.mp3")
            if not os.path.isfile(mp3):
                emit("align", 91, f"第 {i+1} 段配音失败，跳过：{text[:20]}")
                continue
            wav1 = os.path.join(tmpdir, f"s{i}.wav")
            run([FFMPEG, "-y", "-i", mp3, "-ac", "1", "-ar", str(SR), "-f", "wav", wav1])
            pcm = read_wav(wav1)
            slot = max(0.2, end - start)
            if len(pcm) > slot * SR:
                tempo = min(len(pcm) / (slot * SR), 1.45)
                wav2 = os.path.join(tmpdir, f"f{i}.wav")
                run([FFMPEG, "-y", "-i", wav1, "-af", f"atempo={tempo:.4f}", "-f", "wav", wav2])
                pcm = read_wav(wav2)
                if len(pcm) > slot * SR:
                    pcm = pcm[: int(slot * SR)]
            pos = max(int(start * SR), cursor)
            endpos = min(pos + len(pcm), total)
            track[pos:endpos] = pcm[: endpos - pos]
            cursor = endpos
            emit("align", 91 + 4 * (i + 1) / len(seg_list), f"对齐 {i+1}/{len(seg_list)}")

        new_wav = os.path.join(tmpdir, "new_track.wav")
        with wave.open(new_wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(track.tobytes())

        emit("mux", 96, "第五步：合成视频...")
        codec = probe_codec(video)
        if codec in ("h264", "hevc"):
            vcodec = ["-c:v", "copy"]
        else:
            vcodec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
        run([FFMPEG, "-y", "-i", video, "-i", new_wav, "-map", "0:v", "-map", "1:a"] + vcodec + ["-c:a", "aac", "-b:a", "192k", "-shortest", out])
        emit("mux", 100, "完成")
        return out
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
