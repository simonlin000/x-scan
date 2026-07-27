---
name: x-scan
description: >
  Scan X/Twitter via Chrome DevTools Protocol for AI content. Supports For You
  feed scanning, keyword search, latest search, structured tweet extraction,
  AI relevance filtering, Tweet ID deduplication, Chinese summaries, and
  Markdown vault output. Use when the user says xscan, x-scan, 跑一波xscan,
  扫一下X, 搜一下推特, X feed, scan X, search X/Twitter, 帮我看看X上有什么,
  AI圈大事, 跑一轮, 再跑一轮, For You扫描, 搜索推文, or mentions monitoring X.
---

# X Scan

Scan X/Twitter through a dedicated Chrome DevTools Protocol (CDP) browser. The
skill keeps the user's main Chrome untouched and deduplicates by stable Tweet ID,
so `/status/123` and `/status/123/photo/1` are treated as the same tweet.

## Agent Installation

When installing or preparing this skill for someone else, the agent should do
these steps automatically:

1. Check that `python3` and Google Chrome or Chromium are available.
2. Run `python3 -m pip install -r requirements.txt` if `websocket-client` is not
   importable. Use the same `python3` that will run the scanner.
3. Run the offline tests with
   `python3 -m unittest discover -s tests -v`.
4. Run `python3 scripts/xscan.py --help` as the smoke test.
5. On the first real scan, the only expected manual step is logging into X in
   the dedicated browser profile. Never request or copy the user's main Chrome
   profile or cookies.

Do not silently install packages into a different Python environment. If the
agent cannot install dependencies, report the exact command and the reason.

## Quick Reference

```bash
SCRIPT=~/.cola/skills/x-scan/scripts/xscan.py

# For You feed, five rounds, AI keyword filter
python3 "$SCRIPT" --mode feed

# Search top results
python3 "$SCRIPT" --mode search --query "Gemini 3.6"

# Search latest results
python3 "$SCRIPT" --mode search --query "Claude Code" --latest

# Custom rounds
python3 "$SCRIPT" --mode feed --rounds 3

# Feed without AI keyword filtering
python3 "$SCRIPT" --mode feed --no-filter

# Print summary without writing a file
python3 "$SCRIPT" --mode search --query "OpenAI" --summary-only
```

## Modes

| Mode | What it does | Filtering |
|---|---|---|
| `feed` | Scans the For You timeline | AI keyword filter by default |
| `search` | Searches a keyword on X | All extracted results |

`--latest` is only valid with `--mode search` and uses X's `f=live` filter.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `XCOLAB_CDP_PORT` | `19542` | Dedicated Chrome CDP port |
| `XCOLAB_CHROME_PROFILE` | `~/.cola/chrome-debug-profile` | Dedicated browser profile |
| `XCOLAB_CHROME_PATH` | Auto-detected | Chrome or Chromium executable |
| `XSCAN_OUTPUT_DIR` | `~/Documents/X资源收藏` | Markdown output directory |

CLI flags override the output directory. The scanner creates it when needed.

## How It Works

1. Checks the configured CDP port.
2. If needed, launches a dedicated Chrome or Chromium instance with the
   dedicated profile and `--remote-allow-origins=*`.
3. Reuses an existing X tab or creates a new one.
4. Scrolls the requested number of rounds and extracts structured tweet data.
5. Filters For You results by AI keywords when filtering is enabled.
6. Deduplicates within the scan and against the day's output by Tweet ID.
7. Prints a Chinese summary and writes Markdown unless `--summary-only` is set.

Each extracted tweet may include its handle, display name, timestamp, full text,
quoted tweet text, views, likes, reposts, bookmarks, replies, media URLs, and
permalink.

## Output

The scanner writes:

- Feed: `auto-scan-YYYY-MM-DD.md`
- Search: `search-{query}-YYYY-MM-DD.md`

Output includes YAML frontmatter, a summary, and a tweet list. Query values are
quoted safely and only HTTPS X/Twitter permalinks and HTTPS `pbs.twimg.com` media
URLs are emitted.

## Prerequisites

- Python 3
- Google Chrome or Chromium
- `websocket-client` from `requirements.txt`
- An X login in the dedicated profile, required only once per profile

The scanner cannot carry an X login between machines. If the session expires,
open the dedicated browser profile, log into `x.com`, and run the scan again.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser not found | Install Chrome/Chromium or set `XCOLAB_CHROME_PATH` |
| CDP connection refused | Check the dedicated port or set `XCOLAB_CDP_PORT` |
| X not logged in | Log into X in the dedicated profile |
| No tweet DOM detected | Check network/login status or X DOM changes |
| Dependency error | Run `python3 -m pip install -r requirements.txt` |
| Output in the wrong place | Set `XSCAN_OUTPUT_DIR` or pass `--output` |

The scanner exits non-zero for invalid arguments, browser/CDP failures, login
failures, and page extraction failures. A genuine empty result is reported
separately from an execution failure.

## Scheduling

Cron scheduling is external to this skill. A host agent may create recurring
jobs after confirming the user's timezone, output directory, and delivery route.
This directory does not claim to install or configure cron jobs by itself.

## Safety Rules

- Never touch the user's main Chrome profile.
- Never use `pkill Chrome`. If a dedicated instance must be stopped, target only
  the process bound to the configured CDP port.
- Do not request or export X cookies, passwords, or session data.
- Search mode captures all extracted results; feed mode filters by AI relevance.
- Re-running on the same day is idempotent by Tweet ID.
