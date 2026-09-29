import os, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
REPO = "Systran/faster-whisper-medium"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "whisper-medium")
FILES = ["config.json", "tokenizer.json", "vocabulary.txt", "model.bin"]


def fetch(name):
    url = f"{ENDPOINT}/{REPO}/resolve/main/{name}"
    dest = os.path.join(DEST, name)
    os.makedirs(DEST, exist_ok=True)
    while True:
        have = os.path.getsize(dest) if os.path.isfile(dest) else 0
        req = urllib.request.Request(url)
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:
                print(f"  {name} 已是完整文件")
                return
            raise
        if have and resp.status == 200:
            have = 0
        total = resp.headers.get("Content-Length")
        total = int(total) + have if total else None
        mode = "ab" if have else "wb"
        t0 = time.time()
        done = have
        with open(dest, mode) as f:
            while True:
                chunk = resp.read(1024 * 512)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and time.time() - t0 > 0.5:
                    t0 = time.time()
                    pct = done * 100 // total
                    print(f"\r  {name} {pct}%  ({done/1048576:.0f}/{total/1048576:.0f} MB)", end="", flush=True)
        print(f"\r  {name} 完成 ({done/1048576:.1f} MB)" + " " * 20)
        if total is None or done >= total:
            return


def main():
    print(f"下载 faster-whisper-medium 模型（约 1.5GB，仅需一次）")
    print(f"下载源：{ENDPOINT}（海外用户可设置环境变量 HF_ENDPOINT=https://huggingface.co）")
    for name in FILES:
        print(f"[{name}]")
        for attempt in range(5):
            try:
                fetch(name)
                break
            except Exception as e:
                if attempt == 4:
                    print(f"  下载失败：{e}")
                    sys.exit(1)
                print(f"  中断（{type(e).__name__}），{5*(attempt+1)}秒后断点续传...")
                time.sleep(5 * (attempt + 1))
    print("模型下载完成，保存在：", DEST)


if __name__ == "__main__":
    main()
