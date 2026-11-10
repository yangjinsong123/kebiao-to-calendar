"""周次、节次、星期等文本解析（纯规则，不依赖网络）。"""
import re

WEEKDAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
               "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7}

_CN_DIGITS = str.maketrans("０１２３４５６７８９，、－—～~（）", "0123456789,,----()")


def norm(s: str) -> str:
    return (s or "").translate(_CN_DIGITS).replace(" ", "").strip()


def parse_weekday(s: str):
    """'星期三' / '周三' / '3' → 3"""
    s = norm(s)
    m = re.search(r"(?:星期|周|礼拜)?([一二三四五六日天1-7])", s)
    return WEEKDAY_MAP.get(m.group(1)) if m else None


def parse_periods(s: str):
    """'第1-2节' / '1-2' / '3,4节' → (1, 2)"""
    nums = [int(x) for x in re.findall(r"\d+", norm(s))]
    if not nums:
        return None
    return (min(nums), max(nums))


def parse_weeks(s: str):
    """把周次文本展开成周号列表。
    支持：'1-16周' '1-15周(单)' '2-16周(双)' '1-8,10-16周' '3,5,7周' '1-16单周' '[1-16周]双'
    """
    s = norm(s)
    if not s:
        return []
    weeks = set()
    # 先按逗号切段，每段可带自己的单/双
    global_odd = bool(re.search(r"单", s)) and "," not in s
    global_even = bool(re.search(r"双", s)) and "," not in s
    for part in s.split(","):
        odd = "单" in part or global_odd
        even = "双" in part or global_even
        m = re.search(r"(\d+)\s*-\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            rng = range(min(a, b), max(a, b) + 1)
        else:
            nums = [int(x) for x in re.findall(r"\d+", part)]
            rng = nums
        for w in rng:
            if odd and w % 2 == 0:
                continue
            if even and w % 2 == 1:
                continue
            weeks.add(w)
    return sorted(weeks)


def is_weeks_text(s: str) -> bool:
    s = norm(s)
    return bool(re.search(r"\d", s) and re.search(r"周", s))


def week_runs(weeks):
    """把周号列表切成若干等差段（步长 1 或 2），方便写成 RRULE。
    [1,2,...,8,10,...,16] → [(1,1,8), (10,1,7)]   (起始周, 步长, 次数)
    """
    weeks = sorted(set(weeks))
    runs = []
    i = 0
    while i < len(weeks):
        start = weeks[i]
        if i + 1 < len(weeks) and weeks[i + 1] - start in (1, 2):
            step = weeks[i + 1] - start
            j = i + 1
            while j + 1 < len(weeks) and weeks[j + 1] - weeks[j] == step:
                j += 1
            runs.append((start, step, j - i + 1))
            i = j + 1
        else:
            runs.append((start, 1, 1))
            i += 1
    return runs
