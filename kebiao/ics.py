"""课程列表 → .ics（RFC 5545），含单双周重复规则和上课前提醒 VALARM。"""
import datetime as dt
import hashlib

from .parse import parse_weeks, week_runs

VTIMEZONE_SHANGHAI = (
    "BEGIN:VTIMEZONE\r\nTZID:Asia/Shanghai\r\nBEGIN:STANDARD\r\n"
    "DTSTART:19700101T000000\r\nTZOFFSETFROM:+0800\r\nTZOFFSETTO:+0800\r\n"
    "TZNAME:CST\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n"
)

DEFAULT_PERIODS = {
    "1": ["08:00", "08:45"], "2": ["08:50", "09:35"],
    "3": ["09:55", "10:40"], "4": ["10:45", "11:30"],
    "5": ["14:00", "14:45"], "6": ["14:50", "15:35"],
    "7": ["15:55", "16:40"], "8": ["16:45", "17:30"],
    "9": ["19:00", "19:45"], "10": ["19:50", "20:35"],
    "11": ["20:40", "21:25"], "12": ["21:30", "22:15"],
}


def _esc(text: str) -> str:
    return (str(text or "").replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """按 75 字节折行（UTF-8 安全）。"""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def _hm(s):
    h, m = s.split(":")
    return int(h), int(m)


def course_sessions(course, semester_start: dt.date, periods=None):
    """展开一门课的所有具体上课日期 → [(date, start_dt, end_dt), ...]"""
    periods = periods or DEFAULT_PERIODS
    weeks = parse_weeks(course["weeks"])
    p0, p1 = int(course["start_period"]), int(course["end_period"])
    sh, sm = _hm(periods[str(p0)][0])
    eh, em = _hm(periods[str(p1)][1])
    monday = semester_start - dt.timedelta(days=semester_start.weekday())
    out = []
    for w in weeks:
        d = monday + dt.timedelta(weeks=w - 1, days=int(course["weekday"]) - 1)
        out.append((d, dt.datetime(d.year, d.month, d.day, sh, sm),
                    dt.datetime(d.year, d.month, d.day, eh, em)))
    return out


def _in_skip(d, skip):
    return any(a <= d <= b for a, b in (skip or []))


def build_ics(courses, semester_start: dt.date, periods=None, alarm_minutes=10,
              calname="课表", skip_ranges=None):
    """skip_ranges: [(date_from, date_to), ...] 放假不上课的日期段，会写成 EXDATE。"""
    periods = periods or DEFAULT_PERIODS
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//kebiao-to-calendar//CN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(calname)}",
             "X-WR-TIMEZONE:Asia/Shanghai"]
    body = []
    monday = semester_start - dt.timedelta(days=semester_start.weekday())
    p_start_end = lambda c: (_hm(periods[str(int(c["start_period"]))][0]),
                             _hm(periods[str(int(c["end_period"]))][1]))
    for c in courses:
        weeks = parse_weeks(c["weeks"])
        if not weeks:
            continue
        (sh, sm), (eh, em) = p_start_end(c)
        for (w0, step, count) in week_runs(weeks):
            d = monday + dt.timedelta(weeks=w0 - 1, days=int(c["weekday"]) - 1)
            ds = dt.datetime(d.year, d.month, d.day, sh, sm)
            de = dt.datetime(d.year, d.month, d.day, eh, em)
            uid_src = f"{c['name']}|{c['weekday']}|{c['start_period']}|{w0}|{step}|{count}"
            uid = hashlib.sha1(uid_src.encode()).hexdigest()[:16] + "@kebiao-to-calendar"
            desc = "\n".join(x for x in [
                f"老师：{c.get('teacher','')}" if c.get("teacher") else "",
                f"周次：{c['weeks']}",
                f"节次：第{c['start_period']}-{c['end_period']}节"] if x)
            ev = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
                  f"DTSTART;TZID=Asia/Shanghai:{ds:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Asia/Shanghai:{de:%Y%m%dT%H%M%S}",
                  f"SUMMARY:{_esc(c['name'])}"]
            if c.get("room"):
                ev.append(f"LOCATION:{_esc(c['room'])}")
            ev.append(f"DESCRIPTION:{_esc(desc)}")
            ex = [monday + dt.timedelta(weeks=w0 - 1 + k * step, days=int(c["weekday"]) - 1)
                  for k in range(count)]
            ex = [x for x in ex if _in_skip(x, skip_ranges)]
            if ex:
                ev.append("EXDATE;TZID=Asia/Shanghai:" + ",".join(
                    f"{x:%Y%m%d}T{sh:02d}{sm:02d}00" for x in ex))
            if count > 1:
                rule = f"RRULE:FREQ=WEEKLY;COUNT={count}"
                if step > 1:
                    rule = f"RRULE:FREQ=WEEKLY;INTERVAL={step};COUNT={count}"
                ev.append(rule)
            if alarm_minutes and int(alarm_minutes) > 0:
                ev += ["BEGIN:VALARM", "ACTION:DISPLAY",
                       f"DESCRIPTION:{_esc(c['name'] + ' ' + c.get('room',''))}",
                       f"TRIGGER:-PT{int(alarm_minutes)}M", "END:VALARM"]
            ev.append("END:VEVENT")
            body += ev
    text = "\r\n".join(_fold(l) for l in lines) + "\r\n" + VTIMEZONE_SHANGHAI
    text += "\r\n".join(_fold(l) for l in body) + ("\r\n" if body else "")
    text += "END:VCALENDAR\r\n"
    return text


def merge_periods(found=None, base=None):
    """把截图里读到的作息时间合并进默认表（读不到的格子沿用默认值）。"""
    out = {k: list(v) for k, v in (base or DEFAULT_PERIODS).items()}
    for k, (s, e) in (found or {}).items():
        out.setdefault(k, [None, None])
        if s: out[k][0] = s
        if e: out[k][1] = e
    return out
