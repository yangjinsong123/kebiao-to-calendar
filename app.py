#!/usr/bin/env python3
"""网页版：python app.py  然后浏览器打开 http://127.0.0.1:8765
想让手机直接下载 .ics：python app.py --host 0.0.0.0，手机和电脑连同一个 Wi-Fi，手机浏览器打开电脑的局域网 IP:8765。
截图只在本机内存/临时文件里处理，识别完立即删除，不上传任何第三方（除非你自己开启了 kebiao/llm.py 里的大模型模式）。
"""
import argparse, datetime as dt, json, os, tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, Response

from kebiao import llm
from kebiao.ics import build_ics, course_sessions, merge_periods, DEFAULT_PERIODS
from kebiao.table import parse_table

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024


def base_periods():
    pf = ROOT / "periods.json"
    if pf.exists():
        return {k: v for k, v in json.loads(pf.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    return DEFAULT_PERIODS


@app.get("/")
def index():
    return send_from_directory(ROOT / "web", "index.html")


@app.get("/web/<path:p>")
def static_files(p):
    return send_from_directory(ROOT / "web", p)


@app.get("/api/config")
def config():
    return jsonify({"periods": base_periods(), "llm_enabled": llm.enabled(),
                    "llm": llm.endpoint_info() if llm.enabled() else None, "prompt": llm.PROMPT})


@app.post("/api/recognize")
def recognize_api():
    f = request.files.get("image")
    if not f:
        return jsonify({"error": "没有收到图片"}), 400
    data = f.read()
    try:
        if request.form.get("mode") == "llm":
            if not llm.enabled():
                return jsonify({"error": "没有配置大模型（见 README）"}), 400
            return jsonify({"courses": llm.recognize_llm(data, f.mimetype or "image/png"),
                            "periods": {}, "semester_start": None, "engine": "llm"})
        from kebiao.recognize import recognize
        suffix = Path(f.filename or "x.png").suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as t:
            t.write(data)
            tmp = t.name
        try:
            r = recognize(tmp)
        finally:
            os.unlink(tmp)          # 识别完立刻删掉
        r.pop("raw", None)
        r["engine"] = "local-ocr"
        return jsonify(r)
    except Exception as e:  # noqa
        return jsonify({"error": str(e)}), 422


@app.post("/api/table")
def table_api():
    try:
        return jsonify({"courses": parse_table(request.json.get("text", ""))})
    except Exception as e:  # noqa
        return jsonify({"error": str(e)}), 422


def _args(j):
    periods = merge_periods(j.get("periods") or {}, base_periods())
    start = dt.date.fromisoformat(j["start"])
    skip = [(dt.date.fromisoformat(a), dt.date.fromisoformat(b or a)) for a, b in j.get("skip") or []]
    return j.get("courses") or [], start, periods, skip


@app.post("/api/expand")
def expand_api():
    try:
        courses, start, periods, skip = _args(request.json)
        out = []
        for c in courses:
            ss = [s for s in course_sessions(c, start, periods)
                  if not any(a <= s[0] <= b for a, b in skip)]
            out.append({"name": c["name"], "weeks": c["weeks"],
                        "time": f"{ss[0][1]:%H:%M}-{ss[0][2]:%H:%M}" if ss else "",
                        "dates": [f"{d:%Y-%m-%d}" for d, _, _ in ss]})
        return jsonify({"items": out})
    except Exception as e:  # noqa
        return jsonify({"error": str(e)}), 422


@app.post("/api/ics")
def ics_api():
    j = request.json
    courses, start, periods, skip = _args(j)
    text = build_ics(courses, start, periods, int(j.get("alarm", 10)), skip_ranges=skip)
    return Response(text, mimetype="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''%E8%AF%BE%E8%A1%A8.ics"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"打开 http://{a.host if a.host != '0.0.0.0' else '本机IP'}:{a.port}")
    app.run(host=a.host, port=a.port, debug=False)
