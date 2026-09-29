import sys, os, time, uuid, queue, shutil, socket, threading, tempfile
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_file
import pipeline

PORT = 8765
JOBS_DIR = os.path.join(tempfile.gettempdir(), "vcweb")
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

JOBS = {}
JOBQ = queue.Queue()
LOCK = threading.Lock()


def cleanup_old():
    now = time.time()
    for jid in list(JOBS.keys()):
        j = JOBS[jid]
        if now - j.get("created", now) > 3 * 3600:
            shutil.rmtree(j["dir"], ignore_errors=True)
            with LOCK:
                JOBS.pop(jid, None)


def worker():
    while True:
        jid = JOBQ.get()
        j = JOBS.get(jid)
        if not j:
            continue
        with LOCK:
            j["state"] = "running"
        try:
            def progress(stage, pct, msg):
                with LOCK:
                    j["stage"] = stage
                    j["pct"] = round(pct, 1)
                    j["msg"] = msg
                    j["log"].append(msg)
                    if len(j["log"]) > 14:
                        j["log"] = j["log"][-14:]
            out = pipeline.process(j["input"], j["voice"], progress)
            with LOCK:
                j["state"] = "done"
                j["pct"] = 100
                j["result"] = out
                j["result_name"] = os.path.basename(out)
                j["msg"] = "完成"
                j["log"].append("完成")
        except Exception as e:
            with LOCK:
                j["state"] = "error"
                j["error"] = f"{type(e).__name__}: {e}"
                j["msg"] = "出错了"
                j["log"].append(f"出错：{type(e).__name__}: {e}")


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频换声音</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft YaHei", system-ui, sans-serif; background: #111827; color: #e5e7eb;
       min-height: 100vh; display: flex; justify-content: center; padding: 40px 16px; }
.card { width: 640px; max-width: 100%; }
h1 { font-size: 24px; margin-bottom: 6px; color: #f9fafb; }
.sub { color: #9ca3af; font-size: 13px; margin-bottom: 24px; }
.panel { background: #1f2937; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
#drop { border: 2px dashed #4b5563; border-radius: 10px; padding: 44px 16px; text-align: center;
        color: #9ca3af; cursor: pointer; transition: all .15s; font-size: 15px; }
#drop.on { border-color: #6366f1; background: #312e81; color: #c7d2fe; }
#fileinfo { margin-top: 10px; font-size: 13px; color: #a5b4fc; display: none; word-break: break-all; }
select { width: 100%; padding: 10px 12px; margin-top: 16px; background: #111827; color: #e5e7eb;
         border: 1px solid #4b5563; border-radius: 8px; font-size: 14px; }
button { width: 100%; margin-top: 16px; padding: 13px; background: #6366f1; color: white; border: 0;
         border-radius: 8px; font-size: 15px; cursor: pointer; }
button:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
button:not(:disabled):hover { background: #4f46e5; }
#progwrap { display: none; margin-top: 16px; }
#barbg { height: 10px; background: #111827; border-radius: 5px; overflow: hidden; }
#bar { height: 100%; width: 0%; background: linear-gradient(90deg,#6366f1,#8b5cf6); transition: width .5s; }
#stage { margin-top: 8px; font-size: 13px; color: #9ca3af; text-align: center; }
#log { margin-top: 10px; max-height: 130px; overflow-y: auto; font-size: 12px; color: #6b7280;
       font-family: Consolas, monospace; line-height: 1.7; }
#result { display: none; }
video { width: 100%; border-radius: 10px; background: black; margin-top: 4px; }
#dl { display: block; text-align: center; margin-top: 14px; padding: 12px; background: #059669;
      color: white; border-radius: 8px; text-decoration: none; font-size: 15px; }
#dl:hover { background: #047857; }
.err { color: #f87171 !important; }
</style>
</head>
<body>
<div class="card">
  <h1>视频换声音</h1>
  <div class="sub">导入视频，把里面的人声换成另一个声音。画面不动，只换声音。</div>
  <div class="panel">
    <div id="drop">点击选择视频，或把视频拖到这里<br><span style="font-size:12px">支持 mp4 / mkv / avi / mov / webm 等常见格式</span></div>
    <div id="fileinfo"></div>
    <input type="file" id="picker" accept="video/*,.mkv,.mp4,.avi,.mov,.webm,.flv,.wmv,.ts" style="display:none">
    <select id="voice"></select>
    <button id="btn" disabled>开始换声音</button>
    <div id="progwrap">
      <div id="barbg"><div id="bar"></div></div>
      <div id="stage"></div>
      <div id="log"></div>
    </div>
  </div>
  <div class="panel" id="result">
    <div style="font-size:15px;margin-bottom:10px;color:#a7f3d0">换声完成，可以预览：</div>
    <video id="player" controls></video>
    <a id="dl" href="#">下载成品视频</a>
  </div>
</div>
<script>
let file = null, job = null, timer = null;
const $ = id => document.getElementById(id);

fetch('/api/voices').then(r=>r.json()).then(d=>{
  let h = '';
  for (const g of d.groups) h += `<optgroup label="${g.name}">` +
      g.items.map(v=>`<option value="${v.n}">${v.n}. ${v.label}</option>`).join('') + '</optgroup>';
  $('voice').innerHTML = h;
});

const drop = $('drop');
drop.onclick = ()=> $('picker').click();
$('picker').onchange = e=> setFile(e.target.files[0]);
drop.ondragover = e=>{ e.preventDefault(); drop.classList.add('on'); };
drop.ondragleave = ()=> drop.classList.remove('on');
drop.ondrop = e=>{ e.preventDefault(); drop.classList.remove('on'); setFile(e.dataTransfer.files[0]); };

function setFile(f){
  if(!f) return;
  file = f;
  $('fileinfo').style.display = 'block';
  $('fileinfo').textContent = '已选择：' + f.name + '（' + (f.size/1048576).toFixed(1) + ' MB）';
  $('btn').disabled = false;
}

$('btn').onclick = ()=>{
  if(!file) return;
  $('btn').disabled = true;
  $('progwrap').style.display = 'block';
  $('result').style.display = 'none';
  const fd = new FormData();
  fd.append('file', file);
  fd.append('voice', $('voice').value);
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/start');
  xhr.upload.onprogress = e=> setStage('upload', e.loaded/e.total*5, '上传中... ' + (e.loaded/1048576).toFixed(1) + ' / ' + (e.total/1048576).toFixed(1) + ' MB');
  xhr.onload = ()=>{
    if(xhr.status != 200){ setStage('error', 0, '上传失败：' + xhr.responseText, true); return; }
    job = JSON.parse(xhr.responseText).job;
    timer = setInterval(poll, 800);
  };
  xhr.onerror = ()=> setStage('error', 0, '上传失败，请重试', true);
  xhr.send(fd);
};

function poll(){
  fetch('/api/status?job=' + job).then(r=>r.json()).then(d=>{
    setStage(d.state, d.pct, d.msg, d.state=='error');
    $('log').innerHTML = (d.log||[]).map(x=>'<div>'+x+'</div>').join('');
    $('log').scrollTop = $('log').scrollHeight;
    if(d.state=='done'){
      clearInterval(timer);
      $('player').src = '/api/result/' + job;
      $('dl').href = '/api/result/' + job + '?dl=1';
      $('dl').setAttribute('download', d.result_name);
      $('result').style.display = 'block';
      $('btn').disabled = false;
    } else if(d.state=='error'){
      clearInterval(timer);
      $('btn').disabled = false;
    }
  });
}

function setStage(state, pct, msg, isErr){
  $('bar').style.width = Math.max(0, Math.min(100, pct)) + '%';
  const s = $('stage');
  s.textContent = msg;
  s.className = isErr ? 'err' : '';
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    return INDEX_HTML


@app.route("/api/voices")
def voices():
    groups = []
    cur = None
    for i, v in enumerate(pipeline.VOICES):
        if cur is None or v[5] != cur["name"]:
            cur = {"name": v[5], "items": []}
            groups.append(cur)
        cur["items"].append({"n": i + 1, "label": v[1]})
    groups.append({"name": "快速变调（不重新配音，秒完成）", "items": [
        {"n": pipeline.PITCH_UP, "label": "声音变高"},
        {"n": pipeline.PITCH_DOWN, "label": "声音变低"},
    ]})
    return jsonify({"groups": groups})


@app.route("/api/start", methods=["POST"])
def start():
    f = request.files.get("file")
    voice = request.form.get("voice")
    if not f or not voice or not voice.isdigit() or not 1 <= int(voice) <= len(pipeline.VOICES) + 2:
        return "参数无效", 400
    cleanup_old()
    jid = uuid.uuid4().hex[:12]
    jdir = os.path.join(JOBS_DIR, jid)
    os.makedirs(jdir, exist_ok=True)
    ext = os.path.splitext(f.filename or "v.mp4")[1] or ".mp4"
    inp = os.path.join(jdir, "input" + ext)
    f.save(inp)
    with LOCK:
        JOBS[jid] = {"dir": jdir, "input": inp, "voice": int(voice), "state": "queued",
                     "stage": "queue", "pct": 0, "msg": "排队中...", "log": ["已上传，等待处理"],
                     "created": time.time()}
    JOBQ.put(jid)
    return jsonify({"job": jid})


@app.route("/api/status")
def status():
    j = JOBS.get(request.args.get("job", ""))
    if not j:
        return jsonify({"state": "error", "msg": "任务不存在", "log": []})
    with LOCK:
        d = {"state": j["state"], "stage": j["stage"], "pct": j["pct"], "msg": j["msg"],
             "log": j["log"], "result_name": j.get("result_name", ""), "error": j.get("error", "")}
    return jsonify(d)


@app.route("/api/result/<jid>")
def result(jid):
    j = JOBS.get(jid)
    if not j or not j.get("result") or not os.path.isfile(j["result"]):
        return "结果不存在", 404
    return send_file(j["result"], as_attachment=request.args.get("dl") == "1",
                     download_name=j.get("result_name", "result.mp4"))


def main():
    host = "0.0.0.0" if "--share" in sys.argv else "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, PORT))
        s.close()
    except OSError:
        print(f"端口 {PORT} 已被占用，网页版可能已在运行。")
        return
    threading.Thread(target=worker, daemon=True).start()
    print(f"视频换声音网页版已启动：http://127.0.0.1:{PORT}" + ("（局域网可访问）" if host == "0.0.0.0" else ""))
    print("关闭本窗口或按 Ctrl+C 即可停止。")
    app.run(host=host, port=PORT, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
