---
name: x-scan
description: >
  Scan X/Twitter feed for AI-related content and save relevant tweets to a knowledge vault.
  Supports both single scan and scheduled looping with automatic deduplication.
  Automatically connects to a running Chrome browser via CDP, navigates to X.com,
  scrolls to load content, extracts tweets with metadata (handle, time, text, stats),
  filters by keywords, and saves as Markdown files.
  Use when the user wants to scan X feed, monitor X/Twitter for AI content,
  auto-collect tweets, build a knowledge base from social media, run scheduled
  Twitter monitoring, or mentions xcolab, x-scan, X feed scanner, or Twitter monitoring.
---

# X Feed Scanner (xcolab)

Scan X/Twitter For You feed for AI-related content and save relevant tweets to a knowledge vault.

## Overview

This skill connects to a running Chrome browser via Chrome DevTools Protocol (CDP),
creates a new page to visit X.com, scrolls to load more content, extracts tweet data,
filters by configurable keywords, and saves matching tweets as Markdown files in a
knowledge vault for later review or AI processing.

**Two modes:**
- **Single scan** — Run once, save results
- **Scheduled scan** — Loop every N minutes with automatic deduplication

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

### Single Scan Mode

```bash
python3 scripts/x-scan.py
```

### Scheduled Scan Mode

```bash
# Every 30 minutes, infinite loop
python3 scripts/x-scan.py --schedule 30

# Every 60 minutes, max 5 runs
python3 scripts/x-scan.py --schedule 60 --max-runs 5
```

**Features in scheduled mode:**
- Loads all existing `auto-scan-*.md` files for deduplication
- Skips tweets already saved in previous runs
- Appends new tweets to today's file
- Shows next scan time and progress

### Step-by-Step

1. **Verify Chrome Connection**
   ```bash
   curl -s http://127.0.0.1:$XCOLAB_CDP_PORT/json/version | jq .
   ```

2. **Run the Scanner**
   ```bash
   python3 scripts/x-scan.py
   ```

3. **Review Output**
   - Output file: `{VAULT}/auto-scan-{YYYY-MM-DD}.md`
   - Contains YAML frontmatter, summary, and tweet list

## Keyword Filtering

### Chinese Keywords (default)
AI-related terms: ai, 人工智能, chatgpt, claude, llm, agent, 大模型, gpt, deepseek, openai, anthropic, 提示词, prompt, 自动化, 工作流, 工具, 智能体, 机器学习, 程序员, 代码, 编程, 开发者, 国产, 设计, 产品, cursor, notion, obsidian, kimi, 豆包, 通义, 文心

### English Keywords
AI, LLM, GPT, Claude, Agent, automation, prompt engineering, machine learning, open source, API, startup, tool, workflow

### Ignore List
Noise terms filtered out: 高考, 高考志愿, 房子, 房价, 股市, 彩票, 炒股

## Command Line Options

| Option | Description |
|--------|-------------|
| `--schedule MINUTES` | Run in scheduled mode every N minutes |
| `--max-runs N` | Maximum number of scans (requires `--schedule`) |
| `--once` | Force single scan mode (default) |

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
