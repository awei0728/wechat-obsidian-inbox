# Environment Setup

## Version status

Current environment document version:

```text
v0.2
```

v0.2 has been verified for the integrated OpenClaw / QQ Bot runtime:

```text
Windows 11
→ WSL2 Ubuntu-24.04
→ OpenClaw Gateway
→ QQ Bot
→ wechat shortcut command
→ Obsidian vault
```

## Python version

Recommended Python version:

Python 3.10+

## Install dependencies

```bash
pip install -r requirements.txt
```

The scripts have standard-library fallbacks, but installing the recommended dependencies gives more stable network handling and Markdown conversion.

## Dependency notes

`scripts/url_router.py` uses only the Python standard library:

- `json`
- `pathlib`
- `re`
- `subprocess`
- `sys`

`scripts/wechat_to_obsidian.py` uses the Python standard library plus optional third-party packages:

- `requests`: preferred HTTP client for article fetching, image download, and DeepSeek API calls.
- `markdownify`: preferred HTML-to-Markdown converter.
- `beautifulsoup4`: currently detected as an optional dependency and recommended for future or stricter HTML parsing workflows.

The script does not use the `openai` Python SDK. DeepSeek is called directly through the HTTP API with `requests` when available, otherwise with `urllib`.

## Environment variables

Create a local `.env` or configure the runtime environment with:

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
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

For WSL or OpenClaw deployments, set both output path variables to directories that are writable in that runtime, or configure them in `~/.config/wechat-obsidian-inbox/config.toml`.

In Linux/WSL deployments, private environment variables are loaded by `scripts/run_wechat_router.sh` from:

```text
${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env
```

The env file path can be overridden explicitly:

```text
WECHAT_OBSIDIAN_ENV_FILE=/path/to/env
```

For legacy compatibility, the wrapper also checks the old config directory name under `${XDG_CONFIG_HOME:-~/.config}`.

Do not commit real API keys. Use `.env.example` as the template.

If `DEEPSEEK_API_KEY` is not set, the script still saves the WeChat article and images, and the Markdown summary section is filled with:

```text
待整理。
```

## Run from the skill root

The public entrypoint is:

```bash
python scripts/url_router.py "MESSAGE_OR_JSON_PAYLOAD"
```

## Verified QQ-bot command

The final verified QQ-bot command is:

```text
wechat WECHAT_ARTICLE_URL
```

Example:

```text
wechat https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ
```

On Linux/WSL, OpenClaw or QQ-bot should call:

```bash
scripts/run_wechat_router.sh "wechat WECHAT_ARTICLE_URL"
```

The wrapper script loads `${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env` when present, uses `.venv/bin/python`, and invokes `scripts/url_router.py`.

Examples:

```bash
python scripts/url_router.py "https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ"
```

```bash
python scripts/url_router.py "收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ"
```

```bash
python scripts/url_router.py "{\"source\":\"qq-bot\",\"message\":\"收藏这篇：https://mp.weixin.qq.com/s/MUFTJPUZDR6c2cJROwtnMQ\",\"user\":\"awei\"}"
```

## Smoke test

```bash
python scripts/smoke_test.py
```

## Default output paths

Markdown files:

```text
wechat-obsidian-output
```

Images:

```text
wechat-obsidian-output/assets
```

These safe local paths are fallback defaults. In WSL or OpenClaw, prefer setting:

```text
OBSIDIAN_WECHAT_MD_DIR
OBSIDIAN_WECHAT_IMAGE_DIR
```

You can also place persistent path configuration in:

```text
~/.config/wechat-obsidian-inbox/config.toml
```

## Generated files to ignore

The skill ignores local secrets and generated debug/cache files:

- `.env`
- `__pycache__/`
- `*.pyc`
- `debug_wechat/`
