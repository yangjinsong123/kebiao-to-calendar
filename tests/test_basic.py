"""python -m pytest tests  或  python tests/test_basic.py"""
import datetime as dt, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from icalendar import Calendar
from dateutil.rrule import rrulestr

from kebiao.ics import build_ics, DEFAULT_PERIODS
from kebiao.parse import parse_weeks
from kebiao.table import parse_table

ROOT = pathlib.Path(__file__).resolve().parents[1]
COURSES = json.loads((ROOT / "examples/sample_courses.json").read_text(encoding="utf-8"))
START = dt.date(2026, 9, 7)


def occurrences(ev):
    start = ev["DTSTART"].dt
    if "RRULE" not in ev:
        occ = [start]
    else:
        occ = list(rrulestr(ev["RRULE"].to_ical().decode(), dtstart=start))
    ex = set()
    exd = ev.get("EXDATE")
    for e in (exd if isinstance(exd, list) else [exd] if exd else []):
        ex |= {d.dt for d in e.dts}
    return [o for o in occ if o not in ex]


def test_weeks():
    assert parse_weeks("1-15周(单)") == list(range(1, 16, 2))
    assert parse_weeks("2-16周（双）") == list(range(2, 17, 2))
    assert parse_weeks("1-8,10-16周") == [*range(1, 9), *range(10, 17)]


def test_ics_parses_and_counts():
    cal = Calendar.from_ical(build_ics(COURSES, START))
    evs = cal.walk("VEVENT")
    total = sum(len(occurrences(e)) for e in evs)
    assert total == sum(len(parse_weeks(c["weeks"])) for c in COURSES)
    for e in evs:
        al = e.walk("VALARM")
        assert al and al[0]["TRIGGER"].dt == -dt.timedelta(minutes=10)


def test_odd_even_dates():
    cal = Calendar.from_ical(build_ics(COURSES, START))
    by = {str(e["SUMMARY"]): e for e in cal.walk("VEVENT")}
    phy = [o.date() for o in occurrences(by["物理实验"])]
    assert phy[0] == dt.date(2026, 9, 16) and phy[1] == dt.date(2026, 9, 30) and len(phy) == 8
    wed = [e for e in cal.walk("VEVENT") if str(e["SUMMARY"]) == "大学物理" and e["DTSTART"].dt.weekday() == 2][0]
    o = occurrences(wed)
    assert (o[0].hour, o[0].minute) == (9, 55) and o[1].date() == dt.date(2026, 9, 23)  # 单周


def test_skip_holiday():
    skip = [(dt.date(2026, 10, 1), dt.date(2026, 10, 7))]
    cal = Calendar.from_ical(build_ics(COURSES, START, skip_ranges=skip))
    for e in cal.walk("VEVENT"):
        for o in occurrences(e):
            assert not (skip[0][0] <= o.date() <= skip[0][1])


def test_markdown_table():
    md = """| 课程 | 老师 | 教室 | 星期 | 节次 | 周次 |
|---|---|---|---|---|---|
| 大学物理 | 孙立 | 4教402 | 周三 | 3-4 | 1-15周(单) |"""
    c = parse_table(md)[0]
    assert c["weekday"] == 3 and c["start_period"] == 3 and c["weeks"] == "1-15周(单)"


def test_ocr_sample():
    try:
        import rapidocr_onnxruntime  # noqa
    except ImportError:
        return
    from kebiao.recognize import recognize
    r = recognize(ROOT / "examples/sample_timetable.png")
    key = lambda c: (c["name"], c["teacher"], c["room"], c["weekday"], c["start_period"], c["weeks"])
    assert set(map(key, r["courses"])) == set(map(key, COURSES))
    assert r["semester_start"] == "2026-09-07"


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("PASS", k)
