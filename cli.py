#!/usr/bin/env python3
"""命令行版：python cli.py 课表截图.png --start 2026-09-07 -o 课表.ics
也可以：python cli.py --table ai_table.md --start 2026-09-07   （用 AI 返回的表格）
"""
import argparse, datetime as dt, json, sys
from pathlib import Path

from kebiao.ics import build_ics, course_sessions, merge_periods, DEFAULT_PERIODS
from kebiao.parse import parse_weeks

WD = "一二三四五六日"


def main():
    ap = argparse.ArgumentParser(description="课表截图 → .ics 日历文件（本地运行）")
    ap.add_argument("image", nargs="?", help="课表截图（png/jpg）")
    ap.add_argument("--table", help="改用 Markdown/CSV 表格文件（列：课程|老师|教室|星期|节次|周次）")
    ap.add_argument("--json", help="改用 JSON 课程列表")
    ap.add_argument("--start", help="第 1 周的任意一天（一般是开学那周周一），如 2026-09-07")
    ap.add_argument("--periods", help="节次时间表 JSON 文件，默认 periods.json")
    ap.add_argument("--alarm", type=int, default=10, help="提前几分钟提醒，默认 10，0 表示不提醒")
    ap.add_argument("--skip", action="append", default=[],
                    help="放假不上课的日期段，如 2026-10-01:2026-10-07，可写多次")
    ap.add_argument("-o", "--out", default="课表.ics")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    found_periods, start = {}, a.start
    if a.json:
        courses = json.loads(Path(a.json).read_text(encoding="utf-8"))
    elif a.table:
        from kebiao.table import parse_table
        courses = parse_table(Path(a.table).read_text(encoding="utf-8"))
    elif a.image:
        from kebiao.recognize import recognize
        print(f"[1/3] 本地 OCR 识别 {Path(a.image).name} …")
        r = recognize(a.image)
        courses, found_periods = r["courses"], r["periods"]
        start = start or r["semester_start"]
    else:
        ap.error("请给一张课表截图，或用 --table / --json")
    if not start:
        ap.error("请用 --start 指定开学第 1 周的日期")
    base = DEFAULT_PERIODS
    pf = Path(a.periods) if a.periods else Path(__file__).with_name("periods.json")
    if pf.exists():
        base = {k: v for k, v in json.loads(pf.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    periods = merge_periods(found_periods, base)
    sd = dt.date.fromisoformat(start)

    print(f"[2/3] 识别到 {len(courses)} 门次课程，开学日期 {sd}（第 1 周）")
    if not a.quiet:
        for c in courses:
            ss = course_sessions(c, sd, periods)
            dates = "、".join(f"{d:%m/%d}" for d, _, _ in ss[:5]) + (" …" if len(ss) > 5 else "")
            print(f"  周{WD[int(c['weekday'])-1]} 第{c['start_period']}-{c['end_period']}节 "
                  f"{ss[0][1]:%H:%M}-{ss[0][2]:%H:%M}  {c['name']:<10} {c.get('room',''):<8} "
                  f"{c['weeks']:<10} → {len(ss)} 次：{dates}")
    skip = []
    for r in a.skip:
        x, _, y = r.partition(":")
        skip.append((dt.date.fromisoformat(x), dt.date.fromisoformat(y or x)))
    text = build_ics(courses, sd, periods, a.alarm, skip_ranges=skip)
    Path(a.out).write_text(text, encoding="utf-8", newline="")
    n = sum(len(parse_weeks(c["weeks"])) for c in courses)
    print(f"[3/3] 已生成 {a.out}：共 {n} 节课，每节课提前 {a.alarm} 分钟提醒")


if __name__ == "__main__":
    sys.exit(main())
