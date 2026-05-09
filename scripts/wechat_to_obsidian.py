# -*- coding: utf-8 -*-
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urldefrag, urlparse
from urllib.request import Request, urlopen
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import sys
import time

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


DEFAULT_MD_DIR = Path.cwd() / "wechat-obsidian-output"
DEFAULT_ASSET_ROOT_RELATIVE = "assets"
DEFAULT_IMAGE_DIR = DEFAULT_MD_DIR / DEFAULT_ASSET_ROOT_RELATIVE
MD_DIR_ENV_VAR = "OBSIDIAN_WECHAT_MD_DIR"
IMAGE_DIR_ENV_VAR = "OBSIDIAN_WECHAT_IMAGE_DIR"
CONFIG_PATH = Path.home() / ".config" / "wechat-obsidian-inbox" / "config.toml"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_SUMMARY_MODEL = "deepseek/deepseek-v4-pro"
DEFAULT_ASSET_DIR_STRATEGY = "per-article"
DEFAULT_IMAGE_FILENAME_TEMPLATE = "image_{index:02d}{ext}"
DEFAULT_INDEX_FILENAME = "_wechat_articles_index.jsonl"
LEGACY_IMAGE_DIRS = ()
LEGACY_FLAT_DIR_MARKERS = ("推文图片", "æŽ¨æ–‡å›¾ç‰‡", "鎺ㄦ枃鍥剧墖")
SUMMARY_STATUS_LABELS = {
    "success": "成功",
    "skipped": "跳过",
    "failed": "失败",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

ARTICLE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "close",
}

IMAGE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://mp.weixin.qq.com/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Connection": "close",
}

IMG_ATTR_PRIORITY = (
    "data-src",
    "src",
    "data-original",
    "data-backsrc",
    "data-origin-src",
    "data-actualsrc",
    "data-lazy-src",
    "data-url",
    "data-imgurl",
    "data-thumb",
    "data-cover",
    "data-coverurl",
    "data-croporisrc",
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


REQUESTS_AVAILABLE = importlib.util.find_spec("requests") is not None
BS4_AVAILABLE = importlib.util.find_spec("bs4") is not None
MARKDOWNIFY_AVAILABLE = importlib.util.find_spec("markdownify") is not None

if REQUESTS_AVAILABLE:
    import requests
else:
    requests = None

if MARKDOWNIFY_AVAILABLE:
    from markdownify import markdownify as markdownify_html
else:
    markdownify_html = None


class BasicMarkdownParser(HTMLParser):
    block_tags = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "figure",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.link_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "br":
            self.newline(1)
        elif tag == "hr":
            self.newline(2)
            self.parts.append("---")
            self.newline(2)
        elif tag == "li":
            self.newline(1)
            self.parts.append("- ")
        elif tag in self.block_tags:
            self.newline(2)
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "a":
            href = attrs.get("href", "").strip()
            if href:
                self.link_stack.append(href)
                self.parts.append("[")
            else:
                self.link_stack.append("")
        elif tag == "img":
            src = attrs.get("src") or attrs.get("data-src") or ""
            if src:
                self.newline(2)
                self.parts.append(f"![]({src})")
                self.newline(2)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"}:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "a":
            href = self.link_stack.pop() if self.link_stack else ""
            if href:
                self.parts.append(f"]({href})")
        elif tag in self.block_tags:
            self.newline(2)

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = unescape(data)
        text = re.sub(r"\s+", " ", text)
        if text.strip():
            self.parts.append(text.strip())

    def newline(self, count):
        current = "".join(self.parts)
        existing = len(current) - len(current.rstrip("\n"))
        if existing < count:
            self.parts.append("\n" * (count - existing))

    def markdown(self):
        return cleanup_markdown("".join(self.parts))


def warn_missing_optional_packages():
    missing = []
    if not REQUESTS_AVAILABLE:
        missing.append("requests")
    if not BS4_AVAILABLE:
        missing.append("beautifulsoup4")
    if not MARKDOWNIFY_AVAILABLE:
        missing.append("markdownify")
    if missing:
        print(f"Optional packages missing: {', '.join(missing)}")
        print("Install with: pip install beautifulsoup4 markdownify requests")
        print("Using standard-library fallback for this run.")
        print()


def path_from_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def parse_minimal_toml(text):
    data = {}
    section = data
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = data
            for part in line[1:-1].strip().split("."):
                section = section.setdefault(part.strip(), {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        section[key] = value
    return data


def load_config(path=CONFIG_PATH):
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        if tomllib:
            with path.open("rb") as config_file:
                return tomllib.load(config_file)
        return parse_minimal_toml(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"配置文件读取失败，已使用默认配置：{exc}")
        return {}


def config_value(config, section, key, default=None):
    value = config.get(section, {}).get(key, default)
    if isinstance(value, str):
        value = value.strip()
    return value if value not in {"", None} else default


def path_from_config(config, section, key):
    value = config_value(config, section, key)
    if not value:
        return None
    return Path(str(value)).expanduser()


def resolve_default_md_dir(config=None):
    config = config or {}
    return path_from_config(config, "obsidian", "markdown_dir") or path_from_env(MD_DIR_ENV_VAR) or DEFAULT_MD_DIR


def resolve_asset_root(config=None, md_dir=None):
    config = config or {}
    relative_root = config_value(config, "assets", "asset_root_relative", DEFAULT_ASSET_ROOT_RELATIVE)
    configured_root = path_from_config(config, "assets", "asset_root")
    if configured_root:
        return configured_root
    env_root = path_from_env(IMAGE_DIR_ENV_VAR)
    if env_root:
        return env_root
    md_dir = Path(md_dir) if md_dir else resolve_default_md_dir(config)
    return md_dir / relative_root


def resolve_output_dirs(md_dir_arg=None, image_dir_arg=None):
    runtime = resolve_runtime_config(md_dir_arg, image_dir_arg)
    md_dir = runtime["markdown_dir"]
    image_dir = runtime["asset_root"]
    return md_dir, image_dir


def resolve_runtime_config(md_dir_arg=None, image_dir_arg=None):
    config = load_config()
    md_dir = Path(md_dir_arg).expanduser() if md_dir_arg else resolve_default_md_dir(config)
    asset_root = Path(image_dir_arg).expanduser() if image_dir_arg else resolve_asset_root(config, md_dir)
    asset_root_relative = config_value(config, "assets", "asset_root_relative", DEFAULT_ASSET_ROOT_RELATIVE)
    asset_dir_strategy = config_value(config, "assets", "asset_dir_strategy", DEFAULT_ASSET_DIR_STRATEGY)
    image_filename_template = config_value(
        config, "assets", "image_filename_template", DEFAULT_IMAGE_FILENAME_TEMPLATE
    )
    summary_model = config_value(config, "models", "summarizer", DEFAULT_SUMMARY_MODEL)
    index_filename = config_value(config, "dedupe", "index_filename", DEFAULT_INDEX_FILENAME)
    return {
        "markdown_dir": md_dir,
        "asset_root": asset_root,
        "asset_root_relative": str(asset_root_relative).strip("/\\") or DEFAULT_ASSET_ROOT_RELATIVE,
        "asset_dir_strategy": str(asset_dir_strategy or DEFAULT_ASSET_DIR_STRATEGY),
        "image_filename_template": str(image_filename_template or DEFAULT_IMAGE_FILENAME_TEMPLATE),
        "summary_model": str(summary_model or DEFAULT_SUMMARY_MODEL),
        "index_filename": str(index_filename or DEFAULT_INDEX_FILENAME),
    }


def normalize_path_for_guard(path):
    value = str(Path(path).expanduser()).replace("\\", "/")
    value = re.sub(r"/+", "/", value).rstrip("/")
    return value.lower()


def assert_asset_root_allowed(asset_root):
    normalized = normalize_path_for_guard(asset_root)
    for forbidden in LEGACY_IMAGE_DIRS:
        forbidden_normalized = normalize_path_for_guard(forbidden)
        if normalized == forbidden_normalized or normalized.startswith(forbidden_normalized + "/"):
            raise RuntimeError(f"禁止将新图片写入旧目录：{forbidden}")


def fetch_bytes(url, headers, timeout=30):
    if requests:
        response = requests.get(url, headers=headers, timeout=timeout)
        return response.status_code, response.headers.get("Content-Type", ""), response.content

    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return getattr(response, "status", response.getcode()), response.headers.get("Content-Type", ""), response.read()


def fetch_html(url):
    status, content_type, body = fetch_bytes(url, ARTICLE_HEADERS)
    if status < 200 or status >= 300:
        raise RuntimeError(f"Failed to fetch article: HTTP {status}")
    charset = find_charset(content_type, body)
    return body.decode(charset, errors="replace")


def find_charset(content_type, data):
    match = re.search(r"charset=([\w.-]+)", content_type or "", re.I)
    if match:
        return match.group(1)
    head = data[:4096].decode("ascii", errors="ignore")
    match = re.search(r"<meta[^>]+charset=[\"']?([\w.-]+)", head, re.I)
    if match:
        return match.group(1)
    return "utf-8"


def parse_attrs(attr_text):
    attrs = {}
    quoted = re.compile(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.S)
    for name, _, value in quoted.findall(attr_text):
        attrs[name.lower()] = unescape(value)

    consumed = quoted.sub(" ", attr_text)
    unquoted = re.compile(r"([\w:-]+)\s*=\s*([^\s\"'>/]+)")
    for name, value in unquoted.findall(consumed):
        attrs[name.lower()] = unescape(value)
    return attrs


def strip_tags(fragment):
    fragment = re.sub(r"(?is)<script\b.*?</script>", " ", fragment)
    fragment = re.sub(r"(?is)<style\b.*?</style>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", unescape(fragment)).strip()


def extract_first(pattern, html):
    match = re.search(pattern, html, re.I | re.S)
    return strip_tags(match.group(match.lastindex or 1)) if match else ""


def decode_js_literal(literal):
    if not literal:
        return ""
    try:
        return ast.literal_eval(literal)
    except (SyntaxError, ValueError):
        value = literal[1:-1] if literal[:1] in {"'", '"'} else literal
        return value.replace(r"\/", "/")


def get_js_var(html, var_name):
    string_literal = r"(?P<literal>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    pattern = re.compile(r"\bvar\s+" + re.escape(var_name) + r"\s*=\s*" + string_literal, re.S)
    match = pattern.search(html)
    if match:
        return unescape(decode_js_literal(match.group("literal"))).strip()
    return ""


def get_meta(html, *keys):
    wanted = {key.lower() for key in keys}
    for match in re.finditer(r"(?is)<meta\b([^>]*)>", html):
        attrs = parse_attrs(match.group(1))
        marker = (attrs.get("property") or attrs.get("name") or "").lower()
        if marker in wanted and attrs.get("content"):
            return attrs["content"].strip()
    return ""


def extract_between_tags(html, tag, id_value):
    start_pattern = re.compile(
        r"(?is)<" + tag + r"\b(?=[^>]*\bid\s*=\s*([\"'])" + re.escape(id_value) + r"\1)[^>]*>"
    )
    start = start_pattern.search(html)
    if not start:
        return ""

    tag_pattern = re.compile(r"(?is)<!--.*?-->|<\s*/?\s*" + tag + r"\b[^>]*>")
    depth = 0
    for match in tag_pattern.finditer(html, start.start()):
        token = match.group(0)
        if token.startswith("<!--"):
            continue
        is_close = bool(re.match(r"(?is)<\s*/", token))
        is_self_closing = token.rstrip().endswith("/>")
        if is_close:
            depth -= 1
            if depth == 0:
                return html[start.start() : match.end()]
        elif not is_self_closing:
            depth += 1
    return html[start.start() :]


def parse_article(html):
    title = (
        extract_first(r"<h1\b[^>]*\bid\s*=\s*([\"'])activity-name\1[^>]*>(.*?)</h1>", html)
        or get_js_var(html, "msg_title")
        or get_meta(html, "og:title")
        or extract_first(r"<title\b[^>]*>(.*?)</title>", html)
    )
    author = (
        extract_first(r"<(?:a|strong)\b[^>]*\bid\s*=\s*([\"'])js_name\1[^>]*>(.*?)</(?:a|strong)>", html)
        or extract_first(r"<strong\b[^>]*\bclass\s*=\s*([\"'])[^\"']*profile_nickname[^\"']*\1[^>]*>(.*?)</strong>", html)
        or get_js_var(html, "nickname")
    )
    summary = (
        get_js_var(html, "msg_desc")
        or get_meta(html, "og:description", "description")
        or get_meta(html, "twitter:description")
    )
    published = format_timestamp(get_js_var(html, "ct"))
    content_html = extract_between_tags(html, "div", "js_content")
    if not content_html:
        raise RuntimeError("Could not find js_content in article HTML")
    return {
        "title": title or "微信文章",
        "author": author or "",
        "summary": summary or "",
        "published": published,
        "content_html": content_html,
    }


def format_timestamp(value):
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def clean_windows_filename(name):
    cleaned = re.sub(r'[\\/:*?"<>|？]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "微信文章"


def build_filename_stem(article, run_started):
    date_part = run_started.strftime("%Y_%m_%d")
    author = clean_windows_filename(article["author"] or "未知公众号")
    title = clean_windows_filename(article["title"] or "微信文章")
    return clean_windows_filename(f"{date_part}_{author}_{title}")


def unique_markdown_path(base_dir, stem):
    path = base_dir / f"{stem}.md"
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = base_dir / f"{stem}_{index}.md"
        if not candidate.exists():
            return candidate
        index += 1


def unquote_yaml_value(value):
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def extract_frontmatter_fields(markdown_text):
    lines = markdown_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = unquote_yaml_value(value.strip())
    return fields


def find_existing_markdown_by_url(md_dir, source_url):
    md_dir = Path(md_dir)
    if not md_dir.exists():
        return None

    needle = f"url: {source_url}"
    for markdown_path in sorted(md_dir.glob("*.md")):
        try:
            markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fields = extract_frontmatter_fields(markdown_text)
        if fields.get("source_url") == source_url or fields.get("url") == source_url or needle in markdown_text:
            return {
                "path": markdown_path,
                "title": fields.get("title", ""),
                "author": fields.get("author", ""),
            }
    return None


def source_url_hash(source_url):
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()


def index_path_for(md_dir, index_filename):
    return Path(md_dir) / (index_filename or DEFAULT_INDEX_FILENAME)


def iter_index_records(index_path):
    index_path = Path(index_path)
    if not index_path.exists():
        return
    try:
        for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    except OSError:
        return


def find_existing_in_index(md_dir, source_url, index_filename):
    found = None
    for record in iter_index_records(index_path_for(md_dir, index_filename)) or []:
        if record.get("source_url") == source_url:
            found = record
    if not found:
        return None

    md_path = Path(found.get("md_path", ""))
    if not md_path.is_absolute():
        md_path = Path(md_dir) / md_path
    if not md_path.exists():
        return None

    return {
        "path": md_path,
        "md_path": found.get("md_path", ""),
        "title": found.get("title", ""),
        "author": found.get("author", ""),
        "asset_mode": found.get("asset_mode", ""),
        "asset_dir": found.get("asset_dir", ""),
        "image_dir": found.get("image_dir", ""),
        "image_count": found.get("image_count", 0),
        "summary_status": found.get("summary_status", ""),
        "summary_error": found.get("summary_error", ""),
        "summary_model": found.get("summary_model", ""),
    }


def infer_duplicate_asset_mode(existing):
    asset_mode = (existing.get("asset_mode") or "").strip()
    if asset_mode:
        return asset_mode

    asset_dir = str(existing.get("asset_dir") or existing.get("image_dir") or "").strip()
    normalized = asset_dir.replace("\\", "/").strip("/")
    normalized_with_slashes = f"/{normalized}/"
    if any(
        normalized.endswith(marker) or normalized == marker or f"/{marker}/" in normalized_with_slashes
        for marker in LEGACY_FLAT_DIR_MARKERS
    ):
        return "legacy-flat"
    if normalized == "assets" or normalized.startswith("assets/"):
        return "per-article"
    return "unknown"


def upsert_index_record(md_dir, index_filename, record):
    index_path = index_path_for(md_dir, index_filename)
    records = []
    replaced = False
    for existing in iter_index_records(index_path) or []:
        if existing.get("source_url") == record.get("source_url"):
            records.append(record)
            replaced = True
        else:
            records.append(existing)
    if not replaced:
        records.append(record)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_text = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records)
    index_path.write_text(index_text + "\n", encoding="utf-8")


def normalize_url(value):
    value = unescape(value or "").strip().strip("\"'")
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith(("http://", "https://")):
        return value
    return ""


def choose_image_url(attrs):
    for name in IMG_ATTR_PRIORITY:
        url = normalize_url(attrs.get(name, ""))
        if url:
            return url

    for name, value in attrs.items():
        imageish_name = name.startswith("data-") and any(
            token in name for token in ("src", "url", "img", "thumb", "cover", "back")
        )
        if imageish_name:
            url = normalize_url(value)
            if url:
                return url
    return ""


def extension_from_content_type(content_type):
    content_type = (content_type or "").lower()
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    return ""


def normalize_ext(value):
    value = (value or "").lower().strip(". ;")
    if value in {"jpeg", "jpg"}:
        return ".jpg"
    if value in {"png", "gif", "webp"}:
        return "." + value
    return ""


def extension_from_url(url):
    parsed = urlparse(url)
    path = unquote(parsed.path).lower()
    for ext in (".jpeg", ".jpg", ".png", ".gif", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext

    query = parse_qs(parsed.query)
    for key in ("wx_fmt", "fmt", "format", "type", "tp"):
        for value in query.get(key, []):
            ext = normalize_ext(value)
            if ext:
                return ext
    return ""


def infer_extension(url, content_type):
    return extension_from_content_type(content_type) or extension_from_url(url) or ".jpg"


def format_image_filename(template, index, ext):
    template = template or DEFAULT_IMAGE_FILENAME_TEMPLATE
    values = {
        "index": index,
        "index02": f"{index:02d}",
        "seq": f"{index:02d}",
        "number": index,
        "ext": ext,
    }
    try:
        filename = template.format(**values)
    except (KeyError, ValueError):
        filename = DEFAULT_IMAGE_FILENAME_TEMPLATE.format(**values)
    if not filename.lower().endswith(ext.lower()):
        filename += ext
    return clean_windows_filename(filename[: -len(ext)]) + ext


def download_image(url, index, image_dir, image_filename_template=DEFAULT_IMAGE_FILENAME_TEMPLATE):
    request_url = urldefrag(url)[0]
    try:
        status, content_type, body = fetch_bytes(request_url, IMAGE_HEADERS)
        if status < 200 or status >= 300:
            return None, status, content_type
        ext = infer_extension(url, content_type)
        image_path = image_dir / format_image_filename(image_filename_template, index, ext)
        image_path.write_bytes(body)
        return image_path, status, content_type
    except HTTPError as exc:
        return None, exc.code, exc.headers.get("Content-Type", "") if exc.headers else ""
    except URLError as exc:
        return None, f"URL error: {exc.reason}", ""
    except OSError as exc:
        return None, f"OS error: {exc}", ""


def relative_markdown_path(path, base_dir):
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def markdown_image_link(image_path, md_dir, asset_relative_prefix=None):
    if asset_relative_prefix:
        prefix = str(asset_relative_prefix).strip("/\\")
        return f"{prefix}/{image_path.name}" if prefix else image_path.name
    return relative_markdown_path(image_path, md_dir)


def replace_images_with_local_markdown(
    content_html,
    md_dir,
    image_dir,
    asset_relative_prefix=None,
    image_filename_template=DEFAULT_IMAGE_FILENAME_TEMPLATE,
):
    local_paths = []
    failures = []
    image_index = 0
    output = []
    last_end = 0

    for match in re.finditer(r"(?is)<img\b[^>]*>", content_html):
        output.append(content_html[last_end : match.start()])
        tag = match.group(0)
        attrs = parse_attrs(tag)
        url = choose_image_url(attrs)

        if not url:
            output.append("")
            failures.append({"url": "[missing]", "status": "missing image URL", "content_type": ""})
            last_end = match.end()
            continue

        image_index += 1
        image_path, status, content_type = download_image(url, image_index, image_dir, image_filename_template)
        if image_path:
            local_paths.append(image_path)
            relative = markdown_image_link(image_path, md_dir, asset_relative_prefix)
            output.append(f"\n\n![]({relative})\n\n")
        else:
            failures.append({"url": url, "status": status, "content_type": content_type})
            output.append(f"\n\n![]({url})\n\n")
        last_end = match.end()

    output.append(content_html[last_end:])
    return "".join(output), local_paths, failures


def html_to_markdown(content_html):
    if markdownify_html:
        markdown = markdownify_html(content_html, heading_style="ATX")
        return cleanup_markdown(markdown)

    parser = BasicMarkdownParser()
    parser.feed(content_html)
    return parser.markdown()


def cleanup_markdown(markdown):
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"\*\*\s*\*\*", "", markdown)
    markdown = normalize_local_asset_image_links(markdown)
    return markdown.strip()


def normalize_local_asset_image_links(markdown):
    def replace(match):
        target = match.group("target").strip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if not target.startswith("assets/"):
            return match.group(0)
        target = target.replace(r"\_", "_")
        return f"{match.group('prefix')}<{target}>{match.group('suffix')}"

    return re.sub(r"(?P<prefix>!\[[^\]]*\]\()(?P<target>[^)\n]+)(?P<suffix>\))", replace, markdown)


def yaml_scalar(value):
    value = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if not value:
        return '""'
    needs_quotes = (
        value.lower() in {"true", "false", "null", "~"}
        or value[:1] in {"-", "?", "@", "`", "!", "&", "*", "{", "}", "[", "]", "#"}
        or ": " in value
        or any(char in value for char in "{}[]")
    )
    if needs_quotes:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def deepseek_api_model_name(model):
    model = (model or DEFAULT_SUMMARY_MODEL).strip()
    if model.startswith("deepseek/"):
        return model.split("/", 1)[1]
    return model


def short_error_message(message, limit=240):
    message = re.sub(r"\s+", " ", str(message or "")).strip()
    if len(message) > limit:
        return message[: limit - 3].rstrip() + "..."
    return message


def parse_deepseek_response_json(response_text):
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"JSON parse error: {exc}; response text: {response_text[:500]}"
        ) from exc


def request_deepseek_summary(url, headers, payload):
    if requests:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
        except Exception as exc:
            exc_name = exc.__class__.__name__
            raise RuntimeError(f"{exc_name}: {exc}") from exc

        response_text = response.text
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"HTTP {response.status_code}: {response_text[:500]}")
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError(
                f"JSON parse error: {exc}; response text: {response_text[:500]}"
            ) from exc

    request = Request(url, headers=headers, data=json.dumps(payload).encode("utf-8"), method="POST")
    try:
        with urlopen(request, timeout=60) as response:
            response_text = response.read().decode("utf-8", errors="replace")
            status = getattr(response, "status", response.getcode())
    except HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {response_text[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Timeout error: {exc}") from exc

    if status < 200 or status >= 300:
        raise RuntimeError(f"HTTP {status}: {response_text[:500]}")
    return parse_deepseek_response_json(response_text)


def generate_summary(article_text, summary_model=DEFAULT_SUMMARY_MODEL):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("未检测到 DEEPSEEK_API_KEY，已跳过自动摘要。")
        return "待整理。", "skipped", ""

    prompt = (
        "请为以下微信文章生成150-250字中文摘要。"
        "不要评价文章，不要扩展发挥。"
        "保留文章核心观点、论证逻辑和关键事实。"
        "摘要适合放入 Obsidian 作为资料卡片摘要。\n\n"
        f"{article_text[:12000]}"
    )
    payload = {
        "model": deepseek_api_model_name(summary_model),
        "messages": [
            {"role": "system", "content": "你是严谨的中文资料卡片摘要助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }
    url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    delays = [2, 5]
    last_error = ""
    for attempt in range(1, 4):
        try:
            data = request_deepseek_summary(url, headers, payload)
            try:
                summary = data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Unexpected DeepSeek response shape: {exc}; response data: {str(data)[:500]}") from exc
            if not summary:
                raise RuntimeError(f"DeepSeek returned an empty summary; response data: {str(data)[:500]}")
            return cleanup_summary(summary), "success", ""
        except Exception as exc:
            last_error = short_error_message(exc)
            print(f"DeepSeek 摘要生成失败（第 {attempt}/3 次）：{last_error}")
            if attempt < 3:
                time.sleep(delays[attempt - 1])

    return "待整理。", "failed", last_error


def cleanup_summary(summary):
    summary = summary.replace("\r\n", "\n").replace("\r", "\n")
    summary = re.sub(r"^#+\s*", "", summary.strip())
    summary = re.sub(r"\n{3,}", "\n\n", summary)
    return summary or "待整理。"


def summary_preview(summary):
    return re.sub(r"\s+", " ", summary).strip()[:100]


def build_markdown(article, body_markdown, summary, run_started, source_url, metadata=None):
    metadata = metadata or {}
    title = article["title"]
    author = article["author"]
    published = article["published"]
    created = run_started.strftime("%Y-%m-%d")
    saved_at = metadata.get("saved_at") or run_started.strftime("%Y-%m-%d %H:%M:%S")
    source_hash = metadata.get("source_url_hash") or source_url_hash(source_url)
    summary_model = metadata.get("summary_model") or DEFAULT_SUMMARY_MODEL
    summary_status = metadata.get("summary_status") or ""
    summary_error = metadata.get("summary_error") or ""
    asset_mode = metadata.get("asset_mode") or ""
    asset_dir = metadata.get("asset_dir") or ""
    image_count = metadata.get("image_count", 0)

    frontmatter = "\n".join(
        [
            "---",
            "source: wechat",
            f"source_url: {source_url}",
            f"source_url_hash: {source_hash}",
            f"url: {source_url}",
            f"title: {yaml_scalar(title)}",
            f"author: {yaml_scalar(author)}",
            f"published: {yaml_scalar(published)}",
            f"created: {yaml_scalar(created)}",
            f"saved_at: {yaml_scalar(saved_at)}",
            f"summary_model: {yaml_scalar(summary_model)}",
            f"summary_status: {yaml_scalar(summary_status)}",
            f"summary_error: {yaml_scalar(summary_error)}",
            f"asset_mode: {yaml_scalar(asset_mode)}",
            f"asset_dir: {yaml_scalar(asset_dir)}",
            f"image_count: {image_count}",
            "tags:",
            "  - inbox",
            "  - wechat",
            "---",
        ]
    )

    source_info = "\n".join(
        [
            f"# {title}",
            "",
            f"> 来源：{author}  ",
            f"> 原文：{source_url}  ",
            f"> 发布时间：{published}  ",
        ]
    )

    summary_section = "\n".join(
        [
            "## 摘要",
            "",
            summary,
        ]
    )

    notes_section = "\n".join(
        [
            "---",
            "",
            "## 我的笔记",
            "",
            "待补充。",
        ]
    )

    return f"{frontmatter}\n\n{summary_section}\n\n{source_info}\n\n{body_markdown}\n\n{notes_section}\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch a WeChat article, download images, and save it as an Obsidian Markdown note."
    )
    parser.add_argument("url", nargs="?", help="微信推文 URL，例如 https://mp.weixin.qq.com/s/...")
    parser.add_argument(
        "--md-dir",
        default=None,
        help=(
            "Markdown 输出目录。优先级：命令行参数 > config.toml > "
            f"{MD_DIR_ENV_VAR} > 默认路径 {DEFAULT_MD_DIR}"
        ),
    )
    parser.add_argument(
        "--image-dir",
        default=None,
        help=(
            "图片 asset_root 输出目录；per-article 模式会在其下创建文章子目录。"
            f"优先级：命令行参数 > config.toml > {IMAGE_DIR_ENV_VAR} > Markdown目录/assets"
        ),
    )
    return parser.parse_args(argv)


def validate_wechat_url(url):
    url = (url or "").strip()
    if not url:
        raise ValueError("URL 不能为空。用法：python wechat_to_obsidian.py \"微信推文URL\"")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "mp.weixin.qq.com":
        raise ValueError("当前脚本仅支持微信推文链接")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("微信推文 URL 必须以 http:// 或 https:// 开头")
    return url


def print_json_result(result):
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_export(url, md_dir=None, image_dir=None, runtime=None):
    run_started = datetime.now()
    url = validate_wechat_url(url)

    runtime = runtime or resolve_runtime_config(md_dir, image_dir)
    md_dir = Path(runtime["markdown_dir"])
    asset_root = Path(runtime["asset_root"])
    asset_root_relative = runtime["asset_root_relative"]
    asset_mode = runtime["asset_dir_strategy"]
    image_filename_template = runtime["image_filename_template"]
    summary_model = runtime["summary_model"]
    index_filename = runtime["index_filename"]

    assert_asset_root_allowed(asset_root)

    existing = find_existing_in_index(md_dir, url, index_filename) or find_existing_markdown_by_url(md_dir, url)
    if existing:
        print(f"Duplicate article found: {existing['path']}")
        print("该微信推文已收藏，未重复保存。")
        duplicate_asset_mode = infer_duplicate_asset_mode(existing)
        duplicate_image_dir = existing.get("image_dir") or existing.get("asset_dir") or str(asset_root)
        return {
            "status": "success",
            "source": "wechat",
            "url": url,
            "title": existing.get("title", ""),
            "author": existing.get("author", ""),
            "markdown_path": str(existing["path"]),
            "md_path": existing.get("md_path", ""),
            "image_dir": duplicate_image_dir,
            "asset_dir": existing.get("asset_dir") or duplicate_image_dir,
            "image_count": existing.get("image_count", 0) or 0,
            "failed_image_count": 0,
            "summary_status": "skipped",
            "summary_error": existing.get("summary_error", ""),
            "summary_model": existing.get("summary_model") or summary_model,
            "asset_mode": duplicate_asset_mode,
            "duplicate": True,
            "message": "该微信推文已收藏，未重复保存。",
        }

    warn_missing_optional_packages()

    md_dir.mkdir(parents=True, exist_ok=True)
    asset_root.mkdir(parents=True, exist_ok=True)

    print(f"Fetching article: {url}")
    html = fetch_html(url)
    article = parse_article(html)

    filename_stem = build_filename_stem(article, run_started)
    markdown_path = unique_markdown_path(md_dir, filename_stem)
    article_stem = markdown_path.stem

    if asset_mode == "per-article":
        article_asset_dir = asset_root / article_stem
        asset_relative_prefix = f"{asset_root_relative}/{article_stem}" if asset_root_relative else article_stem
    else:
        article_asset_dir = asset_root
        asset_relative_prefix = asset_root_relative or None
    relative_asset_dir = asset_relative_prefix or relative_markdown_path(article_asset_dir, md_dir)

    assert_asset_root_allowed(article_asset_dir)
    article_asset_dir.mkdir(parents=True, exist_ok=True)

    patched_html, local_image_paths, failures = replace_images_with_local_markdown(
        article["content_html"],
        md_dir,
        article_asset_dir,
        asset_relative_prefix,
        image_filename_template,
    )
    body_markdown = html_to_markdown(patched_html)
    article_text = strip_tags(article["content_html"])
    summary, summary_status, summary_error = generate_summary(article_text, summary_model)
    saved_at = run_started.strftime("%Y-%m-%d %H:%M:%S")
    relative_asset_files = [
        markdown_image_link(path, md_dir, asset_relative_prefix) for path in local_image_paths
    ]
    markdown_metadata = {
        "source_url_hash": source_url_hash(url),
        "saved_at": saved_at,
        "summary_model": summary_model,
        "summary_status": summary_status,
        "summary_error": summary_error,
        "asset_mode": asset_mode,
        "asset_dir": relative_asset_dir,
        "image_count": len(local_image_paths),
    }
    markdown = build_markdown(article, body_markdown, summary, run_started, url, markdown_metadata)
    markdown_path.write_text(markdown, encoding="utf-8")

    index_record = {
        "source_url": url,
        "source_url_hash": source_url_hash(url),
        "title": article["title"],
        "author": article["author"],
        "md_path": relative_markdown_path(markdown_path, md_dir),
        "asset_mode": asset_mode,
        "asset_dir": relative_asset_dir,
        "asset_files": relative_asset_files,
        "image_count": len(local_image_paths),
        "saved_at": saved_at,
        "summary_model": summary_model,
        "summary_status": summary_status,
        "summary_error": summary_error,
        "status": "saved",
    }
    upsert_index_record(md_dir, index_filename, index_record)

    print(f"Article title: {article['title']}")
    print(f"Account name: {article['author']}")
    print(f"Markdown path: {markdown_path}")
    print(f"Markdown filename: {markdown_path.name}")
    print(f"Asset root: {asset_root}")
    print(f"Image directory: {article_asset_dir}")
    print(f"Summary status: {SUMMARY_STATUS_LABELS.get(summary_status, summary_status)}")
    print(f"Summary model: {summary_model}")
    if summary_error:
        print(f"Summary error: {summary_error}")
    print(f"Summary preview: {summary_preview(summary)}")
    print(f"Downloaded images: {len(local_image_paths)}")
    print(f"Failed images: {len(failures)}")
    print("First 5 local image paths:")
    for path in local_image_paths[:5]:
        print(f"- {path}")

    if failures:
        print()
        print("Failed image details:")
        for failure in failures[:5]:
            print(f"- status={failure['status']} content_type={failure['content_type']} url={failure['url']}")

    return {
        "status": "success",
        "source": "wechat",
        "url": url,
        "title": article["title"],
        "author": article["author"],
        "markdown_path": str(markdown_path),
        "image_dir": str(article_asset_dir),
        "asset_root": str(asset_root),
        "asset_mode": asset_mode,
        "asset_files": [str(path) for path in local_image_paths],
        "image_count": len(local_image_paths),
        "failed_image_count": len(failures),
        "summary_status": summary_status,
        "summary_error": summary_error,
        "summary_model": summary_model,
        "index_path": str(index_path_for(md_dir, index_filename)),
        "duplicate": False,
    }


def main(argv=None):
    args = parse_args(argv)
    source_url = args.url or ""
    runtime = resolve_runtime_config(args.md_dir, args.image_dir)
    try:
        result = run_export(source_url, runtime=runtime)
        print_json_result(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        result = {
            "status": "failed",
            "source": "wechat",
            "url": source_url,
            "error": str(exc),
        }
        print_json_result(result)
        return 1


if __name__ == "__main__":
    sys.exit(main())
