"""渲染一张【虚构】的教务系统风格课表截图：examples/sample_timetable.png
学校、老师、课程、教室全部是编的，不含任何真实个人信息。
用法：python examples/make_sample.py   （需要 pip install playwright && playwright install chromium）
"""
import json, pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
courses = json.loads((HERE / "sample_courses.json").read_text(encoding="utf-8"))
COLORS = ["#E3F2FD", "#FCE4EC", "#E8F5E9", "#FFF3E0", "#EDE7F6", "#E0F7FA", "#FFFDE7", "#F3E5F5"]
BORDER = ["#64B5F6", "#F06292", "#81C784", "#FFB74D", "#9575CD", "#4DD0E1", "#FFD54F", "#BA68C8"]
names = sorted({c["name"] for c in courses})
cidx = {n: i % len(COLORS) for i, n in enumerate(names)}
rows = [(1, 2, "08:00-09:35"), (3, 4, "09:55-11:30"), (5, 6, "14:00-15:35"),
        (7, 8, "15:55-17:30"), (9, 10, "19:00-20:35")]
days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

def cell(day, p0):
    items = [c for c in courses if c["weekday"] == day and c["start_period"] == p0]
    out = ""
    for c in items:
        i = cidx[c["name"]]
        out += (f'<div class="c" style="background:{COLORS[i]};border-left-color:{BORDER[i]}">'
                f'<b>{c["name"]}</b><span>{c["teacher"]}</span><span>{c["room"]}</span>'
                f'<span>{c["weeks"]}</span></div>')
    return out

trs = ""
for p0, p1, t in rows:
    trs += f'<tr><th class="sec">第{p0}-{p1}节<small>{t}</small></th>'
    trs += "".join(f"<td>{cell(d, p0)}</td>" for d in range(1, 8)) + "</tr>"

html = f"""<html><head><meta charset="utf-8"><style>
body{{margin:0;font-family:'Noto Sans CJK SC',sans-serif;background:#f4f6f9;color:#333}}
.top{{background:#1f5fa8;color:#fff;padding:14px 24px;font-size:20px;display:flex;justify-content:space-between}}
.top small{{font-size:14px;opacity:.85}}
.bar{{padding:12px 24px;font-size:15px;color:#555;display:flex;gap:28px;background:#fff;border-bottom:1px solid #dde3ea}}
.bar b{{color:#1f5fa8}}
table{{border-collapse:collapse;margin:14px 24px;background:#fff;width:calc(100% - 48px);table-layout:fixed}}
th,td{{border:1px solid #d6dde6;vertical-align:top;padding:4px}}
thead th{{background:#eef3f9;font-size:16px;padding:10px 0;color:#1f5fa8}}
th.sec{{width:96px;background:#f8fafc;font-size:15px;font-weight:600;vertical-align:middle}}
th.sec small{{display:block;font-weight:400;color:#888;font-size:12px;margin-top:4px}}
td{{height:128px}}
.c{{border-left:4px solid;border-radius:4px;padding:5px 7px;margin-bottom:4px;font-size:13px;line-height:1.45}}
.c b{{display:block;font-size:14.5px;color:#222}} .c span{{display:block;color:#555}}
.foot{{margin:0 24px 16px;font-size:12px;color:#999}}
</style></head><body>
<div class="top"><span>星河大学（虚构） 教学综合信息服务平台</span><small>示例数据 · 仅供演示</small></div>
<div class="bar"><span>学年学期：<b>2026-2027 第1学期</b></span><span>姓名：<b>示例同学</b></span><span>班级：<b>示例班</b></span><span>开学日期：<b>2026-09-07</b></span></div>
<table><thead><tr><th class="sec">节次</th>{''.join(f'<th>{d}</th>' for d in days)}</tr></thead>
<tbody>{trs}</tbody></table>
<div class="foot">本课表为虚构示例，学校、课程、教师、教室均为编造。</div>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5)
    pg.set_content(html)
    pg.screenshot(path=str(HERE / "sample_timetable.png"), full_page=True)
    b.close()
print("saved", HERE / "sample_timetable.png")
