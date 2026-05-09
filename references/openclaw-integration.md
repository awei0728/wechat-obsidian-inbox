# OpenClaw Integration Guide

## Version status

Current integration document version:

```text
v0.2
```

v0.2 is the OpenClaw / QQ Bot integrated version.

Verified deployment flow:

```text
Windows 11
→ WSL2 Ubuntu-24.04
→ OpenClaw Gateway
→ QQ Bot
→ wechat shortcut command
→ Obsidian vault
```

## Public entrypoint

OpenClaw should call:

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

`scripts/url_router.py` is the public integration boundary. It accepts raw URLs, chat text, or JSON payloads, extracts the first supported URL, and dispatches it to the matching handler.

Do not call `scripts/wechat_to_obsidian.py` directly from OpenClaw unless debugging the WeChat handler itself.

## Verified QQ-bot command

The final verified QQ-bot command is:

```text
wechat WECHAT_ARTICLE_URL
```

Example:

```text
wechat https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

For OpenClaw or QQ-bot deployment on Linux/WSL, call the wrapper script and pass the full command text or JSON payload unchanged:

```bash
scripts/run_wechat_router.sh "wechat WECHAT_ARTICLE_URL"
```

The wrapper script:

1. Enters the skill root.
2. Loads the private environment file at `${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env` if it exists.
3. Uses the skill-local Python interpreter at `.venv/bin/python`.
4. Calls `scripts/url_router.py`.
5. Forwards the final JSON result from the router.

The env file path can be overridden explicitly:

```text
WECHAT_OBSIDIAN_ENV_FILE=/path/to/env
```

For legacy compatibility, the wrapper also checks the old config directory name under `${XDG_CONFIG_HOME:-~/.config}`.

JSON payload example:

```json
{
  "source": "qq-bot",
  "message": "wechat https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ",
  "user": "awei"
}
```

## Supported input shapes

Raw WeChat URL:

```text
https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

Chat message:

```text
收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

JSON payload:

```json
{
  "source": "qq-bot",
  "message": "收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ",
  "user": "awei"
}
```

When the input is JSON, the router reads the `message` field first. If JSON parsing fails, it treats the full argument as plain text.

## Current routing behavior

Currently supported:

- `mp.weixin.qq.com` -> `scripts/wechat_to_obsidian.py`

Currently unsupported:

- Bilibili
- 得到
- 飞书

Unsupported URLs return a failed JSON object without calling a handler.

## Output path configuration

Output paths can be configured by environment variables:

```text
OBSIDIAN_WECHAT_MD_DIR
OBSIDIAN_WECHAT_IMAGE_DIR
```

Path priority:

```text
command line arguments > config.toml > environment variables > safe local defaults
```

OpenClaw should set these variables before calling the router when the safe local defaults are not the intended Obsidian vault paths. The router does not need to pass `--md-dir` or `--image-dir`; `scripts/wechat_to_obsidian.py` reads `config.toml` and environment variables automatically.

## Output contract

OpenClaw should parse the final JSON object printed to stdout.

Success:

```json
{
  "status": "success",
  "source": "wechat",
  "url": "https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ",
  "title": "文章标题",
  "author": "公众号名称",
  "markdown_path": "/path/to/obsidian/inbox/文章.md",
  "image_dir": "/path/to/obsidian/inbox/assets/文章",
  "image_count": 8,
  "failed_image_count": 0,
  "summary_status": "skipped",
  "duplicate": false
}
```

Duplicate:

```json
{
  "status": "success",
  "source": "wechat",
  "url": "https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ",
  "markdown_path": "/path/to/obsidian/inbox/文章.md",
  "image_count": 0,
  "failed_image_count": 0,
  "summary_status": "skipped",
  "duplicate": true,
  "message": "该微信推文已收藏，未重复保存。"
}
```

Failure:

```json
{
  "status": "failed",
  "source": "router",
  "error": "当前 Skill 仅支持微信推文链接，未检测到 mp.weixin.qq.com URL。"
}
```

## Runtime notes

Run from the skill root:

```bash
cd wechat-obsidian-inbox
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

Install recommended dependencies:

```bash
pip install -r requirements.txt
```

Set `DEEPSEEK_API_KEY` in the runtime environment to enable automatic summaries. If the variable is missing, the note is still saved and the summary section is filled with `待整理。`.

## Smoke test

```bash
python scripts/smoke_test.py
```
