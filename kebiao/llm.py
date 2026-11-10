"""可选：用你自己配置的多模态大模型识别课表（默认关闭）。

只有设置了下面的环境变量，网页上才会出现“用大模型识别”按钮；
开启后，截图会发送到你配置的 OpenAI 兼容接口（例如你自己的 OpenAI / 通义 / 豆包 / 本地 Ollama 账号），
请自行确认该服务的隐私政策。默认的本地 OCR 模式不联网。
  KEBIAO_LLM_BASE_URL   例：https://api.openai.com/v1  或  http://localhost:11434/v1
  KEBIAO_LLM_API_KEY    你的 key（本地模型可随便填）
  KEBIAO_LLM_MODEL      例：gpt-4o-mini / qwen-vl-max / llava
"""
import base64, json, os, re, urllib.request

from .table import parse_table

PROMPT = ("这是一张大学课表截图。请把每节课的课程名、老师、教室、星期几、第几节、上哪几周，"
          "整理成一张 Markdown 表格，列名依次是：课程|老师|教室|星期|节次|周次。"
          "周次保留原文写法（如 1-16周、1-15周(单)、2-16周(双)）。同一格里有两门课要拆成两行。只输出表格。")


def enabled():
    return bool(os.environ.get("KEBIAO_LLM_BASE_URL") and os.environ.get("KEBIAO_LLM_MODEL"))


def endpoint_info():
    return {"base_url": os.environ.get("KEBIAO_LLM_BASE_URL", ""), "model": os.environ.get("KEBIAO_LLM_MODEL", "")}


def recognize_llm(image_bytes: bytes, mime="image/png"):
    b64 = base64.b64encode(image_bytes).decode()
    body = {"model": os.environ["KEBIAO_LLM_MODEL"], "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}]}
    req = urllib.request.Request(os.environ["KEBIAO_LLM_BASE_URL"].rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + os.environ.get("KEBIAO_LLM_API_KEY", "none")})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = json.load(r)["choices"][0]["message"]["content"]
    m = re.search(r"\|.*\|", text, re.S)
    return parse_table(m.group(0) if m else text)
