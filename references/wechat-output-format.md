# WeChat Output Format

The bundled script prints a JSON object at the end of every run.

## Success

```json
{
  "status": "success",
  "source": "wechat",
  "url": "原始URL",
  "title": "文章标题",
  "author": "公众号名称",
  "markdown_path": "Markdown完整路径",
  "image_dir": "图片目录",
  "image_count": 8,
  "failed_image_count": 0,
  "summary_status": "success"
}
```

`summary_status` can be:

- `success`: DeepSeek summary generated.
- `skipped`: `DEEPSEEK_API_KEY` was not detected.
- `failed`: DeepSeek call failed, but Markdown generation continued.

## Failure

```json
{
  "status": "failed",
  "source": "wechat",
  "url": "原始URL",
  "error": "失败原因"
}
```

## Markdown Layout

Generated notes use this structure:

```markdown
---
source: wechat
url: 原始链接
title: 文章标题
author: 公众号名称
published: 发布时间
created: 当前抓取时间
tags:
  - inbox
  - wechat
---

## 摘要

DeepSeek 摘要或待整理。

# 文章标题

> 来源：公众号名称
> 原文：原始链接
> 发布时间：发布时间

正文内容……

---

## 我的笔记

待补充。
```
