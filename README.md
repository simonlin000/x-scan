# x-scan

Scan X/Twitter feed for AI-related content and save relevant tweets to a knowledge vault.

## What It Does

x-scan connects to a running Chrome browser via Chrome DevTools Protocol (CDP), navigates to X.com, scrolls to load content, extracts tweets with metadata (handle, time, text, stats), filters by keywords, and saves as Markdown files.

**Key Features:**
- 🔌 **Chrome CDP Connection** — Connects to existing Chrome instance via remote debugging
- 🔄 **Auto-scroll Loading** — Scrolls to load more tweets (configurable count)
- 🎯 **Keyword Filtering** — Filters tweets by AI-related keywords (Chinese/English/Both)
- 🗂️ **Knowledge Vault Export** — Saves matching tweets as Markdown with YAML frontmatter
- 🔒 **Login Check** — Verifies X.com login before scanning
- ⏰ **Scheduled Scanning** — Run once or loop every N minutes with deduplication
- 🔄 **Auto-dedup** — Skips already-saved tweets across runs

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
   # Single scan
   python3 scripts/x-scan.py

   # Scheduled scan every 30 minutes
   python3 scripts/x-scan.py --schedule 30

   # Scheduled scan with max 10 runs
   python3 scripts/x-scan.py --schedule 30 --max-runs 10
   ```

### For Humans

1. Install Playwright: `pip install playwright && playwright install chromium`
2. Set env vars (see above)
3. Run Chrome with `--remote-debugging-port=19542`
4. Log into X.com
5. Run: `python3 scripts/x-scan.py`

## Usage

### Single Scan (Default)

Run once and save results:

```bash
python3 scripts/x-scan.py
```

Output: `{VAULT}/auto-scan-{YYYY-MM-DD}.md`

### Scheduled Scanning

Run every N minutes, automatically deduplicating against previously saved tweets:

```bash
# Every 30 minutes, infinite loop
python3 scripts/x-scan.py --schedule 30

# Every 60 minutes, max 5 runs
python3 scripts/x-scan.py --schedule 60 --max-runs 5

# Every 15 minutes (aggressive monitoring)
python3 scripts/x-scan.py --schedule 15
```

**How deduplication works:**
- On first run, loads all existing `auto-scan-*.md` files in the vault
- Extracts tweet fingerprints (`@handle:text_preview`)
- Skips tweets already seen in previous runs
- New tweets are appended to today's file

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--schedule MINUTES` | `-s` | Run in scheduled mode every N minutes |
| `--max-runs N` | `-m` | Maximum number of scans (requires `--schedule`) |
| `--once` | `-o` | Force single scan mode (default) |

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
从本次抓取中筛出 8 条相关 AI 内容。

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

## Scheduling Examples

### Run as Background Service (macOS/Linux)

```bash
# Using nohup
nohup python3 scripts/x-scan.py --schedule 30 > xscan.log 2>&1 &

# Using screen/tmux
tmux new -s xscan
python3 scripts/x-scan.py --schedule 30
# Detach: Ctrl+B, D
```

### Run with Systemd (Linux)

Create `/etc/systemd/system/xscan.service`:

```ini
[Unit]
Description=X Feed Scanner
After=network.target

[Service]
Type=simple
User=youruser
Environment=XCOLAB_VAULT=/path/to/vault
Environment=XCOLAB_CDP_PORT=19542
ExecStart=/usr/bin/python3 /path/to/x-scan/scripts/x-scan.py --schedule 30
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable xscan
sudo systemctl start xscan
```

### Run with LaunchAgent (macOS)

Create `~/Library/LaunchAgents/com.xscan.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.xscan</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/x-scan/scripts/x-scan.py</string>
        <string>--schedule</string>
        <string>30</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>XCOLAB_VAULT</key>
        <string>/path/to/vault</string>
        <key>XCOLAB_CDP_PORT</key>
        <string>19542</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Then:
```bash
launchctl load ~/Library/LaunchAgents/com.xscan.plist
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "无法连接到Chrome" | Ensure Chrome is running with `--remote-debugging-port=19542` |
| "X 未登录" | Log into X.com in the Chrome instance first |
| "playwright not installed" | Run `pip install playwright && playwright install chromium` |
| No tweets found | Increase `XCOLAB_SCROLL` or check keyword matching |
| Empty output file | Verify keywords match content in your feed |
| Duplicate tweets | Deduplication is automatic; old fingerprints are loaded on startup |

## Notes

- The script creates a **new page** rather than reusing existing tabs to avoid context contamination
- X.com uses lazy loading — multiple scrolls are needed to capture more than ~10 tweets
- Tweet extraction relies on DOM selectors which may break if X changes their HTML structure
- The script is designed for personal use — respect X's Terms of Service and rate limits
- In scheduled mode, the script loads all existing `auto-scan-*.md` files for deduplication. Large vaults may slow startup.

## License

MIT
