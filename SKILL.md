---
name: x-scan
description: >
  Scan X/Twitter feed for AI-related content and save relevant tweets to a knowledge vault.
  Automatically connects to a running Chrome browser via CDP, navigates to X.com,
  scrolls to load content, extracts tweets with metadata (handle, time, text, stats),
  filters by keywords, and saves as Markdown files.
  Use when the user wants to scan X feed, monitor X/Twitter for AI content,
  auto-collect tweets, build a knowledge base from social media, or mentions
  xcolab, x-scan, X feed scanner, or Twitter monitoring.
---

# X Feed Scanner (xcolab)

Scan X/Twitter For You feed for AI-related content and save relevant tweets to a knowledge vault.

## Overview

This skill connects to a running Chrome browser via Chrome DevTools Protocol (CDP),
creates a new page to visit X.com, scrolls to load more content, extracts tweet data,
filters by configurable keywords, and saves matching tweets as Markdown files in a
knowledge vault for later review or AI processing.

## Prerequisites

1. **Chrome running with remote debugging enabled** on a known port (default: 19542)
2. **User logged into X.com** in that Chrome instance
3. **Playwright installed** (`pip install playwright && playwright install chromium`)

## Configuration

Set these environment variables before running:

| Variable | Default | Description |
|----------|---------|-------------|
| `XCOLAB_CDP_PORT` | `19542` | Chrome CDP port |
| `XCOLAB_USERNAME` | `your_x_username` | Your X @handle |
| `XCOLAB_VAULT` | `/path/to/vault` | Knowledge vault path for saving tweets |
| `XCOLAB_KEYWORD_MODE` | `zh` | Keyword set: `zh`, `en`, or `both` |
| `XCOLAB_SCROLL` | `4` | Number of scrolls to load more content |

## Workflow

### Step 1: Verify Chrome Connection

Check if Chrome is accessible on the configured CDP port:

```bash
curl -s http://127.0.0.1:$XCOLAB_CDP_PORT/json/version | jq .
```

Expected: JSON with `webSocketDebuggerUrl` field.

### Step 2: Run the Scanner

Execute the bundled script:

```bash
python3 ~/.cola/skills/x-scan/scripts/x-scan.py
```

The script will:
1. Connect to Chrome via CDP
2. Create a new page and navigate to `https://x.com/home`
3. Verify login status (exit if not logged in)
4. Scroll down N times to load more tweets
5. Extract tweet data (handle, timestamp, text, engagement stats)
6. Filter tweets by keywords and ignore-list
7. Save matching tweets as a Markdown file in the vault

### Step 3: Review Output

Output file: `{VAULT}/auto-scan-{YYYY-MM-DD}.md`

Contains:
- YAML frontmatter with date, type, source, tags
- Summary of scan results
- List of relevant tweets with handles, dates, text, and engagement stats

## Keyword Filtering

### Chinese Keywords (default)
AI-related terms: ai, 人工智能, chatgpt, claude, llm, agent, 大模型, gpt, deepseek, openai, anthropic, 提示词, prompt, 自动化, 工作流, 工具, 智能体, 机器学习, 程序员, 代码, 编程, 开发者, 国产, 设计, 产品, cursor, notion, obsidian, kimi, 豆包, 通义, 文心

### English Keywords
AI, LLM, GPT, Claude, Agent, automation, prompt engineering, machine learning, open source, API, startup, tool, workflow

### Ignore List
Noise terms filtered out: 高考, 高考志愿, 房子, 房价, 股市, 彩票, 炒股

## Customization

To modify keywords or ignore list, edit the script directly or set environment variables before running.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "无法连接到Chrome" | Ensure Chrome is running with `--remote-debugging-port=19542` |
| "X 未登录" | Log into X.com in the Chrome instance first |
| "playwright not installed" | Run `pip install playwright && playwright install chromium` |
| No tweets found | Increase `XCOLAB_SCROLL` or check keyword matching |
| Empty output file | Verify keywords match content in your feed |

## Notes

- The script creates a **new page** rather than reusing existing tabs to avoid context contamination
- X.com uses lazy loading — multiple scrolls are needed to capture more than ~10 tweets
- Tweet extraction relies on DOM selectors which may break if X changes their HTML structure
- The script is designed for personal use — respect X's Terms of Service and rate limits
