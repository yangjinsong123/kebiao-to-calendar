"""解析 AI（Cursor / ChatGPT / 豆包 等）返回的 Markdown 表格或 CSV。
列名：课程、老师、教室、星期、节次、周次（顺序随意，缺老师/教室也行）。"""
import csv, io, re

from .parse import parse_weekday, parse_periods

ALIASES = {
    "name": ["课程", "课程名", "课程名称", "课名"],
    "teacher": ["老师", "教师", "任课老师", "任课教师"],
    "room": ["教室", "地点", "上课地点"],
    "weekday": ["星期", "周几", "星期几"],
    "periods": ["节次", "第几节", "节"],
    "weeks": ["周次", "上课周", "周数", "哪几周"],
}


def _key(h):
    h = h.strip()
    for k, names in ALIASES.items():
        if h in names:
            return k
    return None


def parse_table(text: str):
    rows = []
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if lines and "|" in lines[0]:
        for l in lines:
            if re.fullmatch(r"\|?[\s:\-|]+\|?", l):
                continue
            rows.append([c.strip() for c in l.strip("|").split("|")])
    else:
        rows = list(csv.reader(io.StringIO("\n".join(lines))))
    if not rows:
        return []
    keys = [_key(h) for h in rows[0]]
    if "name" not in keys:
        raise ValueError("表格第一行要有列名：课程、老师、教室、星期、节次、周次")
    out = []
    for r in rows[1:]:
        d = {k: (r[i] if i < len(r) else "") for i, k in enumerate(keys) if k}
        if not d.get("name"):
            continue
        p = parse_periods(d.get("periods", "")) or (1, 2)
        out.append({"name": d["name"], "teacher": d.get("teacher", ""), "room": d.get("room", ""),
                    "weekday": parse_weekday(d.get("weekday", "")) or 1,
                    "start_period": p[0], "end_period": p[1], "weeks": d.get("weeks", "1-16周")})
    return out
