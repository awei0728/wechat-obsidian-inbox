# wechat-obsidian-inbox v0.2 Release Notes

## Version status

v0.2 is the OpenClaw / QQ Bot integrated version.

This version has been verified in the actual deployment environment:

```text
Windows 11
→ WSL2 Ubuntu-24.04
→ OpenClaw Gateway
→ QQ Bot
→ wechat shortcut command
→ Obsidian vault
```

## Integration summary

v0.2 keeps the v0.1 WeChat capture behavior and documents the verified production-style invocation path for OpenClaw and QQ Bot.

The verified QQ Bot command is:

```text
wechat WECHAT_ARTICLE_URL
```

Example:

```text
wechat https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

For Linux/WSL deployment, OpenClaw or QQ Bot should call:

```bash
scripts/run_wechat_router.sh "wechat WECHAT_ARTICLE_URL"
```

The wrapper script:

1. Enters the skill root.
2. Loads private environment variables from `${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env` if the file exists.
3. Uses the skill-local Python virtual environment at `.venv/bin/python`.
4. Calls `scripts/url_router.py`.
5. Passes the original message or JSON payload unchanged.
6. Forwards the final JSON result printed by the router.

The env file path can be overridden explicitly:

```text
WECHAT_OBSIDIAN_ENV_FILE=/path/to/env
```

For legacy compatibility, the wrapper also checks the old config directory name under `${XDG_CONFIG_HOME:-~/.config}`.

## Core capabilities

1. Accept raw WeChat article URLs.
2. Accept chat text containing a WeChat article URL.
3. Accept QQ Bot style JSON payload with a `message` field.
4. Accept the verified shortcut command format: `wechat WECHAT_ARTICLE_URL`.
5. Extract the first `mp.weixin.qq.com` URL.
6. Fetch WeChat article title, account name, publish time, body, and images.
7. Save article body as Markdown.
8. Download article images locally.
9. Use relative image paths compatible with Obsidian.
10. Generate a DeepSeek summary when `DEEPSEEK_API_KEY` is available.
11. Fall back to `待整理。` when DeepSeek API key is missing or summary generation fails.
12. Detect duplicate URLs from existing Markdown frontmatter and avoid repeated saving.
13. Return structured JSON for OpenClaw or QQ Bot.
14. Support output path overrides through environment variables for WSL or OpenClaw runtimes.

## Public entrypoints

Preferred OpenClaw / QQ Bot wrapper:

```bash
scripts/run_wechat_router.sh "MESSAGE_OR_JSON_PAYLOAD"
```

Router entrypoint:

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

WeChat handler, mainly for debugging:

```bash
python scripts/wechat_to_obsidian.py "WECHAT_ARTICLE_URL"
```

## Runtime environment

Recommended Python version:

```text
Python 3.10+
```

Install recommended dependencies:

```bash
pip install -r requirements.txt
```

Private runtime environment file used by the verified WSL wrapper:

```text
${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env
```

Supported environment variables:

```text
DEEPSEEK_API_KEY
OBSIDIAN_WECHAT_MD_DIR
OBSIDIAN_WECHAT_IMAGE_DIR
```

Path priority:

```text
command line arguments > config.toml > environment variables > safe local defaults
```

## Output contract

The router prints a final JSON object to stdout. OpenClaw or QQ Bot should parse the last JSON object.

Success includes:

- `status`
- `source`
- `url`
- `title`
- `author`
- `markdown_path`
- `image_dir`
- `image_count`
- `failed_image_count`
- `summary_status`
- `duplicate`

Duplicate saves return `duplicate: true` and do not fetch the webpage, download images, or generate a summary again.

## Current limitations

1. Currently only WeChat public account article URLs are supported.
2. Bilibili, Dedao, and Feishu URLs are detected but return unsupported JSON.
3. WeChat article HTML structure may change; parser adjustments may be needed if WeChat changes the page format.
4. DeepSeek summary generation depends on network availability and a valid `DEEPSEEK_API_KEY`.
5. The verified wrapper expects a Linux/WSL virtual environment at `.venv/bin/python`.
