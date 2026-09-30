"""语音识别子进程：pipeline.py 以独立进程调用本脚本，崩溃隔离、可安全重试。
逐行输出 JSON：首行 {"lang": ...}，段落行 [start, end, text, words]，末行 {"done": true}；出错输出 {"error": ...}。
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bs", type=int, default=8, help="0=顺序识别, >0=批处理 batch_size")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(args.model, device=args.device,
                             compute_type="float16" if args.device == "cuda" else "int8")
        if args.bs > 0:
            from faster_whisper import BatchedInferencePipeline
            segs, info = BatchedInferencePipeline(model=model).transcribe(
                args.audio, vad_filter=True, beam_size=1, batch_size=args.bs, word_timestamps=True)
        else:
            segs, info = model.transcribe(args.audio, vad_filter=True, beam_size=1, word_timestamps=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps({"lang": info.language, "prob": getattr(info, "language_probability", None)}) + "\n")
            f.flush()
            for s in segs:
                if s.text.strip():
                    words = [[w.start, w.end, w.word] for w in (s.words or [])]
                    f.write(json.dumps([s.start, s.end, s.text.strip(), words], ensure_ascii=False) + "\n")
                    f.flush()
            f.write(json.dumps({"done": True}) + "\n")
    except Exception as e:
        try:
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps({"error": str(e)}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
