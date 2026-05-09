# wechat-obsidian-inbox v0.1 Release Notes

## Version status

v0.1 is a usable local version for collecting WeChat public account articles into Obsidian.

v0.1 has been superseded by the v0.2 OpenClaw / QQ Bot integrated documentation state. See:

```text
references/release-v0.2.md
```

## Core capabilities

1. Accept raw WeChat article URLs.
2. Accept chat text containing a WeChat article URL.
3. Accept QQ-bot style JSON payload with a `message` field.
4. Extract the first `mp.weixin.qq.com` URL.
5. Fetch WeChat article title, account name, publish time, body, and images.
6. Save article body as Markdown.
7. Download article images locally.
8. Use relative image paths compatible with Obsidian.
9. Generate DeepSeek summary when `DEEPSEEK_API_KEY` is available.
10. Fall back to `待整理。` when DeepSeek API key is missing or summary generation fails.
11. Detect duplicate URLs from existing Markdown frontmatter and avoid repeated saving.
12. Return structured JSON for OpenClaw or QQ-bot.
13. Allow output paths to be configured with environment variables for WSL or OpenClaw runtimes.
14. Provide a verified QQ-bot command format: `wechat WECHAT_ARTICLE_URL`.

## Public entrypoint

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

For Linux/WSL deployment, OpenClaw or QQ-bot should call:

```bash
scripts/run_wechat_router.sh "wechat WECHAT_ARTICLE_URL"
```

The wrapper loads the private environment file, uses the skill-local Python virtual environment, calls `scripts/url_router.py`, and forwards the final JSON result.

The private environment file can be configured with:

```text
WECHAT_OBSIDIAN_ENV_FILE=/path/to/env
```

When no explicit env file is provided, the wrapper checks:

```text
${XDG_CONFIG_HOME:-~/.config}/wechat-obsidian-inbox/env
```

## Default output paths

Markdown files:

```text
/path/to/your/ObsidianVault/01_Inbox/微信收藏
```

Article images:

```text
/path/to/your/ObsidianVault/01_Inbox/微信收藏/assets
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

## Runtime requirements

Recommended Python version:

```text
Python 3.10+
```

Install recommended dependencies:

```bash
pip install -r requirements.txt
```

Optional summary environment variable:

```text
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## Smoke test

Run from the skill root:

```bash
python scripts/smoke_test.py
```

Expected success marker:

```text
All smoke tests passed.
```

## Output contract

The router prints a final JSON object to stdout. OpenClaw or QQ-bot should parse the last JSON object.

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
2. Bilibili, 得到, and 飞书 URLs are detected but return unsupported JSON.
3. WeChat article HTML structure may change; parser adjustments may be needed if WeChat changes the page format.
4. DeepSeek summary generation depends on network availability and a valid `DEEPSEEK_API_KEY`.
5. WSL or OpenClaw environments should set `OBSIDIAN_WECHAT_MD_DIR` and `OBSIDIAN_WECHAT_IMAGE_DIR`, or configure output paths in `~/.config/wechat-obsidian-inbox/config.toml`.
