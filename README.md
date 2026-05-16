# x-scan

Scan X/Twitter feed for AI-related content and save relevant tweets to a knowledge vault.

## What It Does

x-scan connects to a running Chrome browser via Chrome DevTools Protocol (CDP), navigates to X.com, scrolls to load content, extracts tweets with metadata (handle, time, text, stats), filters by keywords, and saves as Markdown files.

## Features

- 🔌 **Chrome CDP Connection** — Connects to existing Chrome instance via remote debugging
- 🔄 **Auto-scroll Loading** — Scrolls to load more tweets (configurable count)
- 🎯 **Keyword Filtering** — Filters tweets by AI-related keywords (Chinese/English/Both)
- 🗂️ **Knowledge Vault Export** — Saves matching tweets as Markdown with YAML frontmatter
- 🔒 **Login Check** — Verifies X.com login before scanning

## Installation

### For AI Agents

If you are an AI agent installing this tool for a user, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/simonlin000/x-scan.git
   cd x-scan
   ```

2. **Install Playwright (required for browser automation):**
   ```bash
   pip install playwright
   playwright install chromium
   ```

3. **Set environment variables:**
   ```bash
   export XCOLAB_CDP_PORT="19542"           # Chrome CDP port
   export XCOLAB_USERNAME="your_handle"      # X/Twitter @handle
   export XCOLAB_VAULT="/path/to/vault"      # Where to save tweets
   export XCOLAB_KEYWORD_MODE="zh"           # zh | en | both
   export XCOLAB_SCROLL="4"                  # Number of scrolls
   ```

4. **Ensure Chrome is running with remote debugging:**
   ```bash
   # macOS example
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=19542 \
     --user-data-dir=/tmp/chrome-xscan
   ```

5. **Verify the user is logged into X.com** in that Chrome instance

6. **Run the scanner:**
   ```bash
   python3 scripts/x-scan.py
   ```

### For Humans

1. Install Playwright: `pip install playwright && playwright install chromium`
2. Set env vars (see above)
3. Run Chrome with `--remote-debugging-port=19542`
4. Log into X.com
5. Run: `python3 scripts/x-scan.py`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `XCOLAB_CDP_PORT` | `19542` | Chrome CDP port |
| `XCOLAB_USERNAME` | `your_x_username` | Your X @handle |
| `XCOLAB_VAULT` | `/path/to/vault` | Knowledge vault path |
| `XCOLAB_KEYWORD_MODE` | `zh` | Keyword set: `zh`, `en`, or `both` |
| `XCOLAB_SCROLL` | `4` | Number of scrolls to load more content |

## Output Format

Saved to `{VAULT}/auto-scan-{YYYY-MM-DD}.md`:

```markdown
---
date: 2026-05-16
type: x-read
source: X For You Feed（自动扫描）
tags: [x, AI, auto-scan, zh]
related: []
ai-first: true
---

## For future Agent

X feed 自动扫描，时间：2026-05-16 12:00:00。
从 25 条推文中筛出 8 条相关 AI 内容。

## 推文列表

### @someuser · 2026-05-16

Tweet text here...

*2 replies, 5 reposts, 10 likes*

---
```

## Keywords

### Chinese (default)
`ai`, `人工智能`, `chatgpt`, `claude`, `llm`, `agent`, `大模型`, `gpt`, `deepseek`, `openai`, `anthropic`, `提示词`, `prompt`, `自动化`, `工作流`, `工具`, `智能体`, `机器学习`, `程序员`, `代码`, `编程`, `开发者`, `国产`, `设计`, `产品`, `cursor`, `notion`, `obsidian`, `kimi`, `豆包`, `通义`, `文心`

### English
`AI`, `LLM`, `GPT`, `Claude`, `Agent`, `automation`, `prompt engineering`, `machine learning`, `open source`, `API`, `startup`, `tool`, `workflow`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "无法连接到Chrome" | Ensure Chrome is running with `--remote-debugging-port=19542` |
| "X 未登录" | Log into X.com in the Chrome instance first |
| "playwright not installed" | Run `pip install playwright && playwright install chromium` |
| No tweets found | Increase `XCOLAB_SCROLL` or check keyword matching |
| Empty output file | Verify keywords match content in your feed |

## License

MIT
