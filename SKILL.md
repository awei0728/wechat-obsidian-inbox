---
name: wechat-obsidian-inbox
description: Capture and organize WeChat public account articles into the user's Obsidian inbox. Use this skill when the user provides a mp.weixin.qq.com article URL from QQ-bot, chat, or manual input and wants the article saved as Markdown with local images, YAML metadata, and an optional DeepSeek-generated Chinese summary.
---

# WeChat to Obsidian Inbox

## Version

Current package version:

```text
v0.2
```

Release notes:

```text
references/release-v0.2.md
```

## Purpose

Use this skill to save WeChat public account articles into the user's Obsidian inbox as Markdown files.

The skill should:
1. Fetch the WeChat article from a `mp.weixin.qq.com` URL.
2. Extract title, account name, publish time, article body, and images.
3. Download article images to the configured Obsidian image folder.
4. Convert the article body to Markdown.
5. Generate a Chinese summary with DeepSeek if `DEEPSEEK_API_KEY` is available.
6. Save the Markdown file into the user's Obsidian inbox.
7. Return a structured JSON result for QQ-bot or OpenClaw.

## Default paths

By default, the handler writes Markdown into a safe local directory under the current working directory:

```text
wechat-obsidian-output
```

Article images default to:

```text
wechat-obsidian-output/assets
```

Output paths can be configured by environment variables:

```text
OBSIDIAN_WECHAT_MD_DIR
OBSIDIAN_WECHAT_IMAGE_DIR
```

Path priority:

```text
command line arguments > config.toml > environment variables > safe local defaults
```

OpenClaw or WSL deployments should set these environment variables, or configure `~/.config/wechat-obsidian-inbox/config.toml`, to point to the intended Obsidian vault paths.

## Main script

Use the router as the public entrypoint:

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

`scripts/url_router.py` is the unified entrypoint for OpenClaw and QQ-bot. It extracts URLs from raw URLs, chat text, or JSON payloads.

Currently, the router only dispatches `mp.weixin.qq.com` links to `scripts/wechat_to_obsidian.py`.

`scripts/wechat_to_obsidian.py` is the WeChat article handler. QQ-bot should not call it directly unless bypassing the router is explicitly required for debugging.

## Handler relationship

- `scripts/url_router.py` is the public entrypoint for OpenClaw and QQ-bot.
- `scripts/wechat_to_obsidian.py` is the WeChat article handler.
- Future handlers may include:
  - `bilibili_to_obsidian.py`
  - `dedao_to_obsidian.py`
  - `feishu_to_obsidian.py`
- The router should dispatch URLs to source-specific handlers.
- Each handler should return a final JSON object to stdout.
- The router should parse and forward the handler's final JSON result.

## Execution rule

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

## OpenClaw integration

Current integrated version:

```text
v0.2
```

OpenClaw should use `scripts/url_router.py` as the public entrypoint for this skill.

QQ-bot may pass either:

1. Raw WeChat article URL.
2. Chat message text containing a WeChat article URL.
3. JSON payload containing a `message` field.

The router extracts the first `mp.weixin.qq.com` URL and dispatches it to the WeChat handler:

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

### Verified QQ-bot command

The final verified QQ-bot command is:

```text
wechat WECHAT_ARTICLE_URL
```

Example:

```text
wechat https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

On Linux/WSL, OpenClaw or QQ-bot should call the wrapper script and pass the full message or JSON payload unchanged:

```bash
scripts/run_wechat_router.sh "wechat WECHAT_ARTICLE_URL"
```

The wrapper loads a private env file from `${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env` when present, falls back to the legacy compatibility config name, uses `.venv/bin/python`, calls `scripts/url_router.py`, and forwards the final JSON result.

The env file path can be overridden explicitly:

```text
WECHAT_OBSIDIAN_ENV_FILE=/path/to/env
```

The verified deployment flow is:

```text
Windows 11
→ WSL2 Ubuntu-24.04
→ OpenClaw Gateway
→ QQ Bot
→ wechat shortcut command
→ Obsidian vault
```

## OpenClaw and QQ-bot invocation contract

This skill is designed to be called by OpenClaw when a QQ-bot message contains a WeChat public account article URL.

### Expected input from QQ-bot

The input may be:

1. A raw URL only:

```text
https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

2. A chat message that contains a WeChat article URL:

```text
帮我收藏这篇文章：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

3. A structured payload that includes a message field:

```json
{
  "source": "qq-bot",
  "message": "帮我收藏这篇文章：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ",
  "user": "awei"
}
```

### Invocation behavior

When a QQ-bot or OpenClaw input contains one or more URLs, pass the original message or JSON payload to the router. The router extracts the first supported URL and dispatches it to the appropriate handler.

Use default output paths unless the caller explicitly provides output directory arguments to a handler-specific debug command.

```bash
python scripts/url_router.py "收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ"
```

The router currently supports WeChat public account article links and routes them to `scripts/wechat_to_obsidian.py`.

Currently, this skill only supports WeChat public account articles and does not support Bilibili、得到、or 飞书 links.

Do not call `scripts/wechat_to_obsidian.py` directly from QQ-bot; use `scripts/url_router.py` as the stable integration boundary.

## Duplicate handling

1. If the same URL already exists in the frontmatter of a note in the Markdown directory, return the existing note path directly.
2. Do not fetch the webpage again.
3. Do not download images again.
4. Do not generate a summary again.
5. Return JSON with `duplicate` set to `true`.
6. If the same URL is not found, create a new note and return JSON with `duplicate` set to `false`.

### Response behavior

Return or forward the final JSON object printed by the script. If a human-readable reply is needed, include the Markdown path, image count, failed image count, and summary status.

If the input does not contain a `mp.weixin.qq.com` URL, do not run the script. Return a clear message that this skill only supports WeChat public account article links.

## DeepSeek summary

Do not hard-code API keys. The script reads:

```text
DEEPSEEK_API_KEY
```

If the environment variable is missing or the API call fails, the Markdown is still generated and the summary section is filled with `待整理。`.

## Output contract

The script prints normal progress logs and ends with a JSON object. For exact fields and examples, read `references/wechat-output-format.md` when integrating with QQ-bot or OpenClaw.
