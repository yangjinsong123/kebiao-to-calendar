"""课表截图识别：本地 OCR（RapidOCR，离线运行）+ 表格版面规则。

思路：
1. OCR 得到每一行文字和它的位置框；
2. 表头里找“星期一…星期日/周一…周日”确定列；左侧找“第1-2节”确定行，
   有表格横线时用 OpenCV 找横线来切行（更稳）；
3. 同一个格子里的文字按从上到下的顺序，切成一门或多门课
   （课程名 → 老师 → 教室 → 周次；同一格里单双周两门课也能拆开）；
4. 左侧节次格里如果写了时间（如 08:00-09:35），顺便读出作息时间表；
   如果截图里写了“开学日期 2026-09-07”，也顺便读出来。
截图只在本机处理，不会上传到任何地方。
"""
import re

from .parse import norm, parse_weekday, parse_periods, is_weeks_text

_ENGINE = None

WEEKDAY_RE = re.compile(r"^(星期|周|礼拜)[一二三四五六日天]$")
SECTION_RE = re.compile(r"第?\s*(\d{1,2})\s*[-~—至]\s*(\d{1,2})\s*节|^第\s*(\d{1,2})\s*节$")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[-~—至]\s*(\d{1,2}):(\d{2})")
ROOM_RE = re.compile(r"(教|楼|室|馆|场|厅|中心|[A-Za-z]?\d{3,4}[A-Za-z]?$)")
TEACHER_RE = re.compile(r"^[\u4e00-\u9fa5·]{2,4}(老师|教授)?$")
DATE_RE = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def ocr_lines(image_path):
    res, _ = _engine()(str(image_path))
    out = []
    for box, text, score in res or []:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        out.append({"text": text.strip(), "x0": min(xs), "x1": max(xs),
                    "y0": min(ys), "y1": max(ys),
                    "cx": (min(xs) + max(xs)) / 2, "cy": (min(ys) + max(ys)) / 2,
                    "score": float(score)})
    return out


def _h_lines(image_path, x0, x1):
    """用 OpenCV 找表格横线的 y 坐标（找不到就返回空）。"""
    try:
        import cv2, numpy as np
    except ImportError:
        return []
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    x0, x1 = max(0, int(x0)), min(img.shape[1], int(x1))
    roi = img[:, x0:x1]
    bw = cv2.adaptiveThreshold(255 - roi, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, (x1 - x0) // 2), 1))
    lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, k)
    ys = np.where(lines.sum(axis=1) > 0)[0]
    merged = []
    for y in ys:
        if not merged or y - merged[-1][-1] > 3:
            merged.append([y])
        else:
            merged[-1].append(y)
    return [sum(g) / len(g) for g in merged]


def _split_cell(lines):
    """一个格子里的若干行 → 若干门课。"""
    courses, cur = [], None
    for ln in lines:
        t = norm(ln["text"])
        if not t:
            continue
        sec = re.search(r"[(（]?第?(\d{1,2})-(\d{1,2})节[)）]?", t)
        if sec and cur and not is_weeks_text(t.replace(sec.group(0), "")):
            cur["_periods"] = (int(sec.group(1)), int(sec.group(2)))
            t = t.replace(sec.group(0), "")
            if not t:
                continue
        if is_weeks_text(t):
            if cur is None:
                continue
            cur["weeks"] = t
            continue
        if cur is not None and not cur.get("weeks"):
            if not cur.get("teacher") and not cur.get("room") and TEACHER_RE.match(t) and not ROOM_RE.search(t):
                cur["teacher"] = re.sub(r"(老师|教授)$", "", t)
                continue
            if not cur.get("room") and ROOM_RE.search(t):
                cur["room"] = t
                continue
            if not cur.get("teacher") and not cur.get("room"):
                cur["name"] += t          # 课程名换行了
                continue
        cur = {"name": t, "teacher": "", "room": "", "weeks": ""}
        courses.append(cur)
    return courses


def recognize(image_path, lines=None):
    """返回 {"courses": [...], "periods": {...}, "semester_start": "YYYY-MM-DD"|None, "raw": [...]}"""
    lines = lines if lines is not None else ocr_lines(image_path)
    heads = [l for l in lines if WEEKDAY_RE.match(norm(l["text"]))]
    if not heads:
        raise ValueError("没找到“星期一/周一”这样的表头，可能不是格子式课表，请手动填写或换一张截图。")
    heads.sort(key=lambda l: l["cx"])
    head_y = max(h["y1"] for h in heads)
    cols = [(parse_weekday(norm(h["text"])), h["cx"]) for h in heads]
    step = (cols[-1][1] - cols[0][1]) / max(1, len(cols) - 1) if len(cols) > 1 else 200
    left_edge = cols[0][1] - step / 2

    def col_of(cx):
        best = min(cols, key=lambda c: abs(c[1] - cx))
        return best[0] if abs(best[1] - cx) < step * 0.6 else None

    sections = []
    for l in lines:
        if l["cx"] < left_edge and l["y0"] > head_y - 2:
            m = SECTION_RE.search(norm(l["text"]))
            if m:
                a = int(m.group(1) or m.group(3)); b = int(m.group(2) or m.group(3))
                sections.append({"p": (a, b), "cy": l["cy"], "y0": l["y0"], "y1": l["y1"]})
    sections.sort(key=lambda s: s["cy"])
    if not sections:
        raise ValueError("没找到左侧的“第1-2节”这样的节次列，请手动填写。")

    # 行边界：优先用表格横线，否则用相邻节次标签的中点
    hl = [y for y in _h_lines(image_path, left_edge, cols[-1][1] + step / 2) if y > head_y] if image_path else []
    bounds = []
    for i, s in enumerate(sections):
        above = [y for y in hl if y < s["y0"]]
        below = [y for y in hl if y > s["y1"]]
        if above and below:
            top, bot = max(above), min(below)
        else:
            top = (sections[i - 1]["cy"] + s["cy"]) / 2 if i else head_y
            bot = (sections[i + 1]["cy"] + s["cy"]) / 2 if i + 1 < len(sections) else 1e9
        bounds.append((top, bot))

    def row_of(cy):
        for s, (top, bot) in zip(sections, bounds):
            if top <= cy < bot:
                return s["p"]
        return None

    # 作息时间（左侧节次格里的 08:00-09:35）
    periods = {}
    for l in lines:
        if l["cx"] < left_edge:
            m = TIME_RE.search(norm(l["text"]))
            p = row_of(l["cy"])
            if m and p:
                periods[str(p[0])] = [f"{int(m.group(1)):02d}:{m.group(2)}", None]
                periods.setdefault(str(p[1]), [None, None])
                periods[str(p[1])][1] = f"{int(m.group(3)):02d}:{m.group(4)}"

    cells = {}
    for l in lines:
        if l["cx"] < left_edge or l["y0"] < head_y:
            continue
        d, p = col_of(l["cx"]), row_of(l["cy"])
        if d and p:
            cells.setdefault((d, p), []).append(l)

    courses = []
    for (d, p), ls in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1][0])):
        ls.sort(key=lambda l: (round(l["cy"] / 6), l["cx"]))
        for c in _split_cell(ls):
            pp = c.pop("_periods", p)
            c.update({"weekday": d, "start_period": pp[0], "end_period": pp[1]})
            if not c["weeks"]:
                c["weeks"] = "1-16周"
                c["note"] = "未识别到周次，默认 1-16 周，请核对"
            courses.append(c)

    semester_start = None
    for l in lines:
        t = norm(l["text"])
        m = DATE_RE.search(t)
        if m and ("开学" in t or "第1周" in t or "起始" in t):
            semester_start = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return {"courses": courses, "periods": periods, "semester_start": semester_start,
            "raw": [{k: l[k] for k in ("text", "cx", "cy")} for l in lines]}
