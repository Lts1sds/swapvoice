import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pipeline


def pick_voice():
    print()
    print("请选择要换成什么声音：")
    group = None
    for i, v in enumerate(pipeline.VOICES):
        if v[5] != group:
            group = v[5]
            print(f"—— {group} ——")
        print(f"  {i+1:2d}. {v[1]}")
    print("—— 快速变调（不重新配音，秒完成）——")
    print(f"  {pipeline.PITCH_UP:2d}. 声音变高")
    print(f"  {pipeline.PITCH_DOWN:2d}. 声音变低")
    valid = [str(i) for i in range(1, len(pipeline.VOICES) + 3)]
    while True:
        c = input(f"输入数字 1-{len(pipeline.VOICES)+2} 回车：").strip()
        if c in valid:
            return int(c)
        print("输入无效，请重新输入")


def main():
    if len(sys.argv) >= 2:
        video = sys.argv[1]
    else:
        print("请把视频文件拖到本窗口，或直接输入视频完整路径：")
        video = input().strip().strip('"')
    if not os.path.isfile(video):
        print(f"找不到文件：{video}")
        return
    choice = int(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[2].isdigit() and 1 <= int(sys.argv[2]) <= len(pipeline.VOICES) + 2 else pick_voice()
    device = None
    if len(sys.argv) >= 4 and sys.argv[3] in ("cpu", "cuda"):
        device = sys.argv[3]

    last_stage = [None]

    def progress(stage, pct, msg):
        if stage != last_stage[0] or msg.startswith(("识别完成", "已自动切换", "警告", "检测到", "未检测", "GPU", "第 ")) or msg.startswith("配音中"):
            print(msg)
        last_stage[0] = stage

    out = pipeline.process(video, choice, progress, device)
    print(f"完成！已保存：{out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"出错了：{type(e).__name__}: {e}")
    input("按回车退出...")
