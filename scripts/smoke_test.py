# -*- coding: utf-8 -*-
from pathlib import Path
import json
import subprocess
import sys


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def extract_last_json(text):
    decoder = json.JSONDecoder()
    text = text or ""

    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        candidate = text[index:].strip()
        try:
            payload, end = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            continue
        if not candidate[end:].strip():
            return payload
    raise ValueError("No final JSON object found in stdout")


def run_router(message):
    script_path = Path(__file__).parent / "url_router.py"
    completed = subprocess.run(
        [sys.executable, str(script_path), message],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    try:
        payload = extract_last_json(completed.stdout)
    except ValueError as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "stdout_tail": (completed.stdout or "")[-1000:],
            "stderr_tail": (completed.stderr or "")[-1000:],
            "returncode": completed.returncode,
        }
    return payload


def check_no_url():
    payload = run_router("请帮我收藏一下")
    ok = payload.get("status") == "failed" and "未检测到 mp.weixin.qq.com URL" in payload.get("error", "")
    return ok, payload, "no URL text should fail with missing WeChat URL message"


def check_bilibili():
    payload = run_router("https://www.bilibili.com/video/BVxxxx")
    ok = payload.get("status") == "failed" and "尚未支持 bilibili" in payload.get("error", "")
    return ok, payload, "bilibili URL should fail with unsupported message"


def check_wechat():
    payload = run_router("收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ")
    ok = payload.get("status") == "success" and bool(payload.get("markdown_path"))
    return ok, payload, "WeChat URL should succeed and return markdown_path"


def main():
    checks = [
        ("no_url", check_no_url),
        ("bilibili", check_bilibili),
        ("wechat", check_wechat),
    ]
    failed = False

    for name, check in checks:
        ok, payload, reason = check()
        print(f"[{name}] {'PASS' if ok else 'FAIL'}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not ok:
            failed = True
            print(f"Reason: {reason}")

    if failed:
        print("Smoke tests failed.")
        return 1

    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
