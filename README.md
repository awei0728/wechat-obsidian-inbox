# wechat-obsidian-inbox

Save WeChat public account articles to an Obsidian inbox with images, summaries, and deduplication.

`wechat-obsidian-inbox` is a deterministic article collector for personal knowledge management. It takes a WeChat public account article URL, fetches the article content, downloads images, optionally generates a summary, and saves everything as a Markdown note in an Obsidian vault.

It is designed to be called by a shell command, message router, bot, OpenClaw / QQBot workflow, or other automation system.

## Why this project exists

When a WeChat article link is sent to a chat bot or automation agent, relying on the agent to freely decide how to save the article is unstable. It may only save a short summary, miss the full article, ignore images, or fail to maintain a duplicate index.

This project uses a deterministic runner instead:

```text
WeChat article URL
-> URL router
-> article fetcher
-> image downloader
-> summary generator
-> Markdown writer
-> Obsidian inbox
-> deduplication index

The goal is simple: the agent may route the task, but the actual saving process should be handled by predictable scripts.

Features
Fetch WeChat public account articles from mp.weixin.qq.com
Save article content as Markdown
Download article images
Store images in per-article asset folders
Generate article summaries through a configurable model provider
Record summary status and summary errors
Maintain a JSONL deduplication index
Skip duplicated articles by default
Keep API keys outside the source code
Keep local Obsidian paths outside the source code
Support OpenClaw / QQBot integration through a shell runner
Provide safer defaults for public release
Project structure
.
├── scripts/
│   ├── wechat_to_obsidian.py
│   ├── url_router.py
│   ├── run_wechat_router.sh
│   └── smoke_test.py
├── references/
│   ├── environment.md
│   ├── openclaw-integration.md
│   ├── release-v0.1.md
│   ├── release-v0.2.md
│   └── wechat-output-format.md
├── .env.example
├── .gitignore
├── requirements.txt
├── SKILL.md
├── LICENSE
└── README.md
Installation

Clone the repository:

git clone https://github.com/awei0728/wechat-obsidian-inbox.git
cd wechat-obsidian-inbox

Create a virtual environment:

python3 -m venv .venv
source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt
Configuration

Copy the example environment file:

cp .env.example .env

Do not commit .env.

A recommended runtime configuration file path is:

~/.config/wechat-obsidian-inbox/config.toml

Example configuration:

[obsidian]
vault_path = "/path/to/your/ObsidianVault"
inbox_relative_path = "01_Inbox/WeChat"
markdown_dir = "/path/to/your/ObsidianVault/01_Inbox/WeChat"

[assets]
download_images = true
asset_dir_strategy = "per-article"
asset_root = "/path/to/your/ObsidianVault/01_Inbox/WeChat/assets"
asset_root_relative = "assets"
article_asset_dir_template = "{article_stem}"
image_filename_template = "image_{index:02d}.{ext}"
on_image_failed = "continue"

[models]
router = "deepseek/deepseek-v4-pro"
summarizer = "deepseek/deepseek-v4-pro"
summary_temperature = 0.3
summary_max_tokens = 2000

[providers.deepseek]
api_key_env = "DEEPSEEK_API_KEY"
runtime = "openclaw"

[dedupe]
enabled = true
index_filename = "_wechat_articles_index.jsonl"
mode = "index_and_files"
on_duplicate = "skip"
allow_resync_if_file_missing = true
Environment variables

The API key should be provided through an environment variable:

export DEEPSEEK_API_KEY=your_api_key_here

Do not write real API keys into Python scripts, shell scripts, Markdown files, or Git-tracked configuration files.

Usage

Run the shell router:

scripts/run_wechat_router.sh "https://mp.weixin.qq.com/s/example"

Run the Python script directly:

python scripts/wechat_to_obsidian.py "https://mp.weixin.qq.com/s/example"

Use explicit output directories for testing:

python scripts/wechat_to_obsidian.py \
  "https://mp.weixin.qq.com/s/example" \
  --md-dir /tmp/wechat-obsidian-output \
  --image-dir /tmp/wechat-obsidian-output/assets
Markdown output

Generated Markdown files include metadata such as:

source_url:
source_url_hash:
summary_model:
summary_status:
summary_error:
asset_mode:
asset_dir:
image_count:

Images are stored by default in a per-article directory:

assets/<article_stem>/image_01.png
assets/<article_stem>/image_02.webp

Markdown image links use angle brackets for better compatibility with paths that may contain spaces or special characters:

![](<assets/<article_stem>/image_01.png>)
Deduplication

The project maintains a JSONL index file, usually named:

_wechat_articles_index.jsonl

When a previously saved article is detected, the default behavior is to skip saving it again.

OpenClaw / QQBot integration

This project can be integrated with OpenClaw / QQBot by routing WeChat article URLs to:

scripts/run_wechat_router.sh

Recommended principle:

Use the agent for routing.
Use deterministic scripts for article saving.

See:

references/openclaw-integration.md
Public release safety checklist

Before publishing or pushing changes, check that the repository does not include:

real API keys
.env
real Obsidian vault contents
generated Markdown notes from a private vault
generated image assets
local verification logs
local machine paths
patched third-party node_modules files
virtual environments
zip archives
Python cache files

A useful check:

find . -maxdepth 3 -type f \
  ! -path "./.git/*" \
  ! -path "./.venv/*" \
  ! -path "./scripts/__pycache__/*" \
  ! -name "*.zip" \
  ! -name "*.local.md" \
  | sort
Status

Current release line: v0.4

The v0.4 line focuses on:

configurable Obsidian output paths
per-article image asset directories
summary success and failure handling
duplicate detection
safer public-release defaults
OpenClaw / QQBot runner integration
Roadmap

Possible future improvements:

package the project as an installable Python CLI
add a default config.example.toml
provide a cleaner OpenClaw integration hook
add automated tests for article parsing and Markdown output
add GitHub Actions for linting and smoke tests
support more article sources beyond WeChat public account articles
License

This project is licensed under the MIT License. See LICENSE
 for details.
