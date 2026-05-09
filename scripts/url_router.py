# -*- coding: utf-8 -*-
from pathlib import Path
import json
import re
import subprocess
import sys


ERROR_NO_WECHAT_URL = "当前 Skill 仅支持微信推文链接，未检测到 mp.weixin.qq.com URL。"
URL_REGEX = r"""https?://[^\s"'<>{}\[\]，,“”,]+"""
URL_PATTERN = re.compile(URL_REGEX)
TRAILING_PUNCTUATION = ".,，。)）]】"


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def json_result(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_message(raw_input):
    raw_input = (raw_input or "").strip()
    if not raw_input:
        return ""

    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError:
        return raw_input

    if isinstance(payload, dict):
        message = payload.get("message")
        if message is not None:
            return str(message)
    return raw_input


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_PATTERN.finditer(text or ""):
        url = match.group(0).rstrip(TRAILING_PUNCTUATION)
        if url:
            urls.append(url)
    return urls


def is_wechat_url(url):
    return "mp.weixin.qq.com" in (url or "").lower()


def is_bilibili_url(url):
    lowered = (url or "").lower()
    return "bilibili.com" in lowered or "b23.tv" in lowered


def is_dedao_url(url):
    lowered = (url or "").lower()
    return "dedao.cn" in lowered or "dedao.com" in lowered


def is_feishu_url(url):
    lowered = (url or "").lower()
    return "feishu.cn" in lowered or "larksuite.com" in lowered


def unsupported(kind, url):
    return {
        "status": "failed",
        "source": "router",
        "url": url,
        "error": f"当前 Skill 尚未支持 {kind} 链接。",
    }


def no_wechat_url_error():
    return {
        "status": "failed",
        "source": "router",
        "error": ERROR_NO_WECHAT_URL,
    }


def extract_last_json_text(text):
    decoder = json.JSONDecoder()
    text = text or ""

    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        candidate = text[index:].strip()
        try:
            _, end = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        remainder = candidate[end:].strip()
        if not remainder:
            return candidate[:end]
    return ""


def run_wechat_handler(wechat_url):
    python_exe = sys.executable
    script_path = Path(__file__).parent / "wechat_to_obsidian.py"

    completed = subprocess.run(
        [python_exe, str(script_path), wechat_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    json_text = extract_last_json_text(completed.stdout)
    if json_text:
        try:
            json.loads(json_text)
        except json.JSONDecodeError:
            pass
        else:
            return json_text

    return json_result(
        {
            "status": "failed",
            "source": "router",
            "url": wechat_url,
            "error": "无法解析 wechat_to_obsidian.py 的 JSON 输出",
            "stdout_tail": (completed.stdout or "")[-1000:],
            "stderr_tail": (completed.stderr or "")[-1000:],
        }
    )


def route_url(url):
    if is_wechat_url(url):
        return run_wechat_handler(url)
    elif is_bilibili_url(url):
        return json_result(unsupported("bilibili", url))
    elif is_dedao_url(url):
        return json_result(unsupported("dedao", url))
    elif is_feishu_url(url):
        return json_result(unsupported("feishu", url))
    else:
        return json_result(unsupported("unknown", url))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    raw_input = " ".join(argv).strip()
    message = parse_message(raw_input)
    urls = extract_urls(message)

    for url in urls:
        if is_wechat_url(url):
            print(route_url(url))
            return 0

    if urls:
        print(route_url(urls[0]))
        return 1

    print(json_result(no_wechat_url_error()))
    return 1


if __name__ == "__main__":
    sys.exit(main())
