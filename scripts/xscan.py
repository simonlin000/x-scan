#!/usr/bin/env python3
"""
xscan — X/Twitter Feed & Search Scanner via CDP
零外部依赖（仅 stdlib + websocket-client），直连 Cola Chrome。

用法:
  python3 xscan.py --mode feed                          # For You feed 扫描
  python3 xscan.py --mode search --query "Gemini 3.6"   # 关键词搜索
  python3 xscan.py --mode search --query "Claude" --latest  # 搜索最新
  python3 xscan.py --mode feed --rounds 3               # 自定义轮数
"""

import json
import os
import re
import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import quote, urlparse
from datetime import datetime
from pathlib import Path

try:
    import websocket
except ImportError:
    print("[错误] 缺少 websocket-client。请运行: python3 -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

# ============================================================
# 配置
# ============================================================

def env_int(name, default, minimum=None, maximum=None):
    """读取并校验整数环境变量，避免导入阶段出现难懂的 traceback。"""
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"[错误] {name} 必须是整数，当前值为: {raw!r}")
    if minimum is not None and value < minimum:
        raise SystemExit(f"[错误] {name} 必须 >= {minimum}，当前值为: {value}")
    if maximum is not None and value > maximum:
        raise SystemExit(f"[错误] {name} 必须 <= {maximum}，当前值为: {value}")
    return value


CDP_PORT = env_int("XCOLAB_CDP_PORT", 19542, minimum=1, maximum=65535)
ALLOW_UNVERIFIED_CDP = os.environ.get("XCOLAB_ALLOW_UNVERIFIED_CDP", "0").lower() in {"1", "true", "yes"}
CHROME_PROFILE = Path(os.environ.get(
    "XCOLAB_CHROME_PROFILE",
    str(Path.home() / ".cola" / "chrome-debug-profile"),
)).expanduser()
DEFAULT_OUTPUT = Path(os.environ.get(
    "XSCAN_OUTPUT_DIR",
    str(Path.home() / "Documents" / "X资源收藏"),
)).expanduser()
DEFAULT_ROUNDS = 5
SCROLL_PAUSE = 2.0  # 每次滚动后等待秒数
OWNER_MARKER = CHROME_PROFILE / ".xscan-cdp-owner.json"


def find_chrome():
    """查找常见 Chrome/Chromium 安装位置，优先使用环境变量。"""
    configured = os.environ.get("XCOLAB_CHROME_PATH")
    if configured:
        return configured if Path(configured).is_file() else None
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google/Chrome/Application/chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google/Chrome/Application/chrome.exe"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None

# Feed 模式关键词过滤
KEYWORDS = [
    'ai', '人工智能', 'chatgpt', 'claude', 'llm', 'agent', '大模型',
    'gpt', 'deepseek', 'openai', 'anthropic', 'gemini', '提示词', 'prompt',
    '自动化', '工作流', '智能体', '机器学习', '程序员', '代码', '编程',
    '开发者', 'cursor', 'kimi', '豆包', '通义', '文心', 'coding',
    'open source', '开源', 'api', 'startup', 'workflow', 'mcp',
    'context engineering', 'agentic', 'reasoning', 'model',
]

IGNORE = ['高考', '高考志愿', '房子', '房价', '股市', '彩票', '炒股', '减肥', '星座']

# ============================================================
# Cola Chrome 生命周期
# ============================================================

def raw_cdp_info():
    """读取本机 CDP 信息；只绑定 localhost。"""
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3)
        data = json.loads(req.read())
        return data if data.get("webSocketDebuggerUrl") else None
    except Exception:
        return None


def listening_pid():
    """找出占用 CDP 端口的进程，无法查询时返回 None。"""
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{CDP_PORT}", "-sTCP:LISTEN", "-Fp"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        for line in result.stdout.splitlines():
            if line.startswith("p") and line[1:].isdigit():
                return line[1:]
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def process_command(pid):
    if not pid:
        return ""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=3, check=False,
        )
        return result.stdout.strip()
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""


def profile_is_suspicious(profile):
    """拒绝明显指向用户主 Chrome Profile 的路径。"""
    normalized = str(profile.expanduser().resolve()).lower()
    markers = (
        "/library/application support/google/chrome",
        "/appdata/local/google/chrome/user data",
        "/.config/google-chrome",
        "/.config/chromium",
    )
    return any(marker in normalized for marker in markers)


def marker_owns_process():
    """在没有 lsof 的平台上，用本 Skill 启动时留下的 PID 标记做回退校验。"""
    try:
        marker = json.loads(OWNER_MARKER.read_text(encoding="utf-8"))
        pid = int(marker.get("pid", 0))
        profile = Path(marker.get("profile", "")).expanduser().resolve()
        if profile != CHROME_PROFILE.expanduser().resolve() or pid <= 0:
            return False
        os.kill(pid, 0)
        command = process_command(str(pid))
        return not command or str(CHROME_PROFILE.expanduser().resolve()) in command
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return False


def cdp_owner_state():
    """返回 down、owned、unverified 或 foreign，避免误控其他 CDP 浏览器。"""
    if not raw_cdp_info():
        return "down"
    pid = listening_pid()
    command = process_command(pid)
    expected = str(CHROME_PROFILE.expanduser().resolve())
    if f"--user-data-dir={expected}" in command or f'--user-data-dir="{expected}"' in command:
        return "owned"
    if marker_owns_process():
        return "owned"
    if ALLOW_UNVERIFIED_CDP:
        return "unverified"
    return "foreign"


def chrome_alive():
    """只把已验证归属的 CDP 浏览器视为可用。"""
    return cdp_owner_state() in {"owned", "unverified"}


def launch_chrome():
    """拉起 Cola Chrome 独立实例，绝不碰主 Chrome。"""
    if profile_is_suspicious(CHROME_PROFILE) and not ALLOW_UNVERIFIED_CDP:
        print("[错误] XCOLAB_CHROME_PROFILE 指向疑似主 Chrome Profile，已拒绝启动。请使用独立目录。")
        return False
    if raw_cdp_info():
        print("[错误] CDP 端口已被其他浏览器占用，未连接以避免误控。请更换 XCOLAB_CDP_PORT。")
        return False
    chrome_app = find_chrome()
    if not chrome_app:
        print("[错误] 找不到 Google Chrome 或 Chromium。请安装浏览器，或设置 XCOLAB_CHROME_PATH。")
        return False
    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    print(f"[启动] Cola Chrome (port {CDP_PORT}, profile: {CHROME_PROFILE})")
    cmd = [
        chrome_app,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_PROFILE}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        OWNER_MARKER.write_text(json.dumps({
            "pid": process.pid,
            "port": CDP_PORT,
            "profile": str(CHROME_PROFILE),
        }), encoding="utf-8")
    except OSError as exc:
        print(f"[错误] 启动 Chrome 失败: {exc}")
        return False
    # 等待启动
    for i in range(15):
        time.sleep(1)
        if chrome_alive():
            print("[就绪] Cola Chrome 已启动")
            return True
    print("[错误] Cola Chrome 启动超时")
    return False


def ensure_chrome():
    """确保 Cola Chrome 可用，并拒绝未验证的浏览器归属。"""
    if profile_is_suspicious(CHROME_PROFILE) and not ALLOW_UNVERIFIED_CDP:
        print("[错误] XCOLAB_CHROME_PROFILE 指向疑似主 Chrome Profile，已拒绝操作。请使用独立目录。")
        return False
    state = cdp_owner_state()
    if state in {"owned", "unverified"}:
        if state == "unverified":
            print("[警告] CDP 归属无法验证，已按 XCOLAB_ALLOW_UNVERIFIED_CDP=1 继续。")
        return True
    if state == "foreign":
        print("[错误] CDP 端口已被其他浏览器占用，未连接以避免误控。请更换 XCOLAB_CDP_PORT。")
        return False
    return launch_chrome()


# ============================================================
# CDP 通信
# ============================================================

class CDPSession:
    """轻量 CDP 会话管理"""

    def __init__(self, port):
        self.port = port
        self.ws = None
        self.msg_id = 0
        self.tab_id = None

    def connect(self):
        """连接到浏览器，获取或创建 tab"""
        # 获取 tab 列表
        resp = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=5)
        tabs = json.loads(resp.read())

        # 优先找已有的 X 页面
        target = None
        for tab in tabs:
            url = tab.get("url", "")
            if "x.com" in url or "twitter.com" in url:
                target = tab
                break

        if not target:
            # 创建新 tab
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/json/new?about:blank", timeout=5
            )
            target = json.loads(resp.read())

        self.tab_id = target["id"]
        ws_url = target["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        return target.get("url", "")

    def evaluate(self, expr, timeout=20):
        """执行 JS 并返回结果"""
        self.msg_id += 1
        msg_id = self.msg_id
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
            }
        }))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                result = data.get("result", {}).get("result", {})
                if "value" in result:
                    return result["value"]
                return result.get("description", "")
        return None

    def navigate(self, url, wait=8):
        """导航到指定 URL，等待页面就绪"""
        self.msg_id += 1
        msg_id = self.msg_id
        self.ws.send(json.dumps({
            "id": msg_id,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        # 等待导航确认
        deadline = time.time() + 15
        while time.time() < deadline:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                break
        time.sleep(wait)

    def wait_for_tweets(self, max_wait=15):
        """等待推文 DOM 出现"""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            count = self.evaluate(
                'document.querySelectorAll(\'article[data-testid="tweet"]\').length'
            )
            if count and int(count) > 0:
                return int(count)
            time.sleep(1.5)
        return 0

    def close(self):
        if self.ws:
            self.ws.close()


# ============================================================
# 推文提取 JS
# ============================================================

EXTRACT_JS = """
(() => {
    const posts = [];
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    articles.forEach(article => {
        try {
            // 作者信息
            let handle = '';
            let displayName = '';
            const userLinks = article.querySelectorAll('a[role="link"]');
            for (const a of userLinks) {
                const href = a.getAttribute('href') || '';
                if (href.match(/^\\/[^/]+$/) && !href.includes('/status/')) {
                    handle = href.slice(1);
                    const nameSpan = a.querySelector('span');
                    if (nameSpan) displayName = nameSpan.innerText.trim();
                    break;
                }
            }

            // 时间
            const timeEl = article.querySelector('time');
            const time = timeEl ? timeEl.getAttribute('datetime') || '' : '';

            // 正文
            const textEl = article.querySelector('[data-testid="tweetText"]');
            const text = textEl ? textEl.innerText.trim() : '';

            // 结构化互动数据，兼容中文和英文界面。
            let stats = { replies: 0, retweets: 0, likes: 0, views: 0, bookmarks: 0 };
            const groupEl = article.querySelector('[role="group"][aria-label]');
            const parseStat = (label, pattern, key) => {
                const match = label.match(pattern);
                if (match) stats[key] = match[1];
            };
            const groupLabel = groupEl ? groupEl.getAttribute('aria-label') || '' : '';
            parseStat(groupLabel, /([\\d,.]+[KMB]?)\\s*(?:回复|repl(?:y|ies))/i, 'replies');
            parseStat(groupLabel, /([\\d,.]+[KMB]?)\\s*(?:次?转帖|转发|repost(?:s)?|retweet(?:s)?)/i, 'retweets');
            parseStat(groupLabel, /([\\d,.]+[KMB]?)\\s*(?:喜欢|like(?:s)?)/i, 'likes');
            parseStat(groupLabel, /([\\d,.]+[KMB]?)\\s*(?:书签|bookmark(?:s)?)/i, 'bookmarks');
            parseStat(groupLabel, /([\\d,.]+[KMB]?)\\s*(?:次?(?:观看|查看)|view(?:s)?)/i, 'views');

            // 某些 X 版本把数字拆在独立按钮上，补齐组合标签没有的字段。
            const statEls = article.querySelectorAll('[aria-label]');
            for (const el of statEls) {
                const label = el.getAttribute('aria-label') || '';
                const numMatch = label.match(/([\\d,.]+[KMB]?)/);
                if (!numMatch) continue;
                const num = numMatch[1];
                if (!stats.replies && /repl|回复/i.test(label)) stats.replies = num;
                else if (!stats.retweets && /repost|retweet|转帖|转发/i.test(label)) stats.retweets = num;
                else if (!stats.likes && /like|喜欢/i.test(label)) stats.likes = num;
                else if (!stats.views && /view|观看|查看/i.test(label)) stats.views = num;
                else if (!stats.bookmarks && /bookmark|书签/i.test(label)) stats.bookmarks = num;
            }

            // 媒体链接
            let media = [];
            const imgs = article.querySelectorAll('[data-testid="tweetPhoto"] img');
            imgs.forEach(img => {
                const src = img.getAttribute('src') || '';
                if (src.includes('pbs.twimg.com')) media.push(src);
            });
            const videos = article.querySelectorAll('video source');
            videos.forEach(v => {
                const src = v.getAttribute('src') || '';
                if (src) media.push(src);
            });

            // 推文链接
            let tweetUrl = '';
            const statusLinks = article.querySelectorAll('a[href*="/status/"]');
            for (const a of statusLinks) {
                const href = a.getAttribute('href') || '';
                if (href.includes('/status/')) {
                    tweetUrl = 'https://x.com' + href;
                    break;
                }
            }

            // 引用推文
            let quotedText = '';
            const quotedEl = article.querySelector('[data-testid="quoteTweet"] [data-testid="tweetText"]');
            if (quotedEl) quotedText = quotedEl.innerText.trim();

            if (text || quotedText) {
                posts.push({
                    handle, displayName, time, text, stats, media,
                    tweetUrl, quotedText
                });
            }
        } catch(e) {}
    });
    return JSON.stringify(posts);
})()
"""


# ============================================================
# 核心逻辑
# ============================================================

def is_relevant(post):
    """Feed 模式关键词过滤"""
    text = (post.get("text", "") + " " + post.get("quotedText", "")).lower()
    for ig in IGNORE:
        if ig in text:
            return False
    for kw in KEYWORDS:
        if kw.lower() in text:
            return True
    return False


def parse_views(v):
    """解析浏览量字符串为数字"""
    if not v or v == 0:
        return 0
    v = str(v).replace(",", "")
    multiplier = 1
    if v.endswith("K"):
        multiplier = 1000
        v = v[:-1]
    elif v.endswith("M"):
        multiplier = 1000000
        v = v[:-1]
    elif v.endswith("B"):
        multiplier = 1000000000
        v = v[:-1]
    try:
        return int(float(v) * multiplier)
    except ValueError:
        return 0


def tweet_id(url):
    """Return the stable X status ID, ignoring /photo/N and query suffixes."""
    match = re.search(r'/status/(\d+)', url or '')
    return match.group(1) if match else ''


def post_key(post):
    """Use tweet ID for dedupe; fall back to handle + text when unavailable."""
    status_id = tweet_id(post.get('tweetUrl', ''))
    if status_id:
        return f'id:{status_id}'
    return f"text:{post.get('handle', '')}:{post.get('text', '')[:120]}"


def search_url(query, latest=False):
    """Build an X search URL. X uses `live` for the latest-results tab."""
    search_type = "live" if latest else "top"
    encoded_q = quote(query)
    return f"https://x.com/search?q={encoded_q}&src=typed_query&f={search_type}"


def scan(session, mode, query=None, latest=False, rounds=DEFAULT_ROUNDS):
    """执行扫描，返回推文列表。页面异常会抛出 RuntimeError。"""
    if rounds < 1:
        raise ValueError("rounds 必须 >= 1")
    all_posts = []
    seen_keys = set()
    extraction_failures = 0

    # 导航
    if mode == "search":
        search_type = "live" if latest else "top"
        url = search_url(query, latest=latest)
        print(f"[搜索] {query} (模式: {search_type})")
        session.navigate(url, wait=6)
    else:
        print("[扫描] For You Feed")
        session.navigate("https://x.com/home", wait=6)

    # 检查登录
    page_url = session.evaluate("window.location.href")
    if page_url and ("login" in str(page_url) or "i/flow" in str(page_url)):
        raise RuntimeError("X 未登录。请在 Cola Chrome 中登录 x.com 后重试。")

    # 等待推文 DOM 就绪
    tweet_count = session.wait_for_tweets(max_wait=15)
    if tweet_count == 0:
        raise RuntimeError("等待 15 秒后仍未检测到推文 DOM，可能是页面结构变化、网络问题或未登录。")
    else:
        print(f"[就绪] 检测到 {tweet_count} 条推文")

    # 多轮滚动 + 提取
    for r in range(1, rounds + 1):
        print(f"  第 {r}/{rounds} 轮...")

        # 提取当前可见推文
        raw = session.evaluate(EXTRACT_JS)
        try:
            if raw is None or raw == "":
                raise ValueError("CDP 未返回提取结果")
            posts = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(posts, list):
                raise TypeError("提取结果不是列表")
            new_count = 0
            for p in posts:
                key = post_key(p)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_posts.append(p)
                    new_count += 1
            print(f"    本轮新增 {new_count} 条 (累计 {len(all_posts)})")
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            extraction_failures += 1
            print(f"    [错误] 第 {r} 轮提取失败: {e}", file=sys.stderr)

        # 滚动
        if r < rounds:
            session.evaluate("window.scrollBy(0, 1500)")
            time.sleep(SCROLL_PAUSE)

    if extraction_failures:
        raise RuntimeError(f"有 {extraction_failures}/{rounds} 轮提取失败，已拒绝保存不完整结果。")
    print(f"[完成] 共抓取 {len(all_posts)} 条独立推文")
    return all_posts


def filter_posts(posts, mode):
    """Feed 模式过滤，Search 模式全量"""
    if mode == "search":
        return posts
    filtered = [p for p in posts if is_relevant(p)]
    print(f"[过滤] {len(filtered)}/{len(posts)} 条与 AI 相关")
    return filtered


def dedup_against_file(posts, output_path):
    """对比已有文件去重"""
    if not output_path.exists():
        return posts

    content = output_path.read_text(encoding="utf-8")
    existing_ids = set(re.findall(r'https://x\.com/\w+/status/(\d+)', content))
    existing_fps = set(re.findall(r'@(\w+).*?\n\n(.{0,80})', content))

    new_posts = []
    for p in posts:
        status_id = tweet_id(p.get("tweetUrl", ""))
        if status_id and status_id in existing_ids:
            continue
        fp_text = p.get("text", "")[:80]
        if (p.get("handle", ""), fp_text) in existing_fps:
            continue
        new_posts.append(p)

    skipped = len(posts) - len(new_posts)
    if skipped > 0:
        print(f"[去重] 跳过 {skipped} 条已存在推文")
    return new_posts


def safe_text(value, limit=None):
    """Normalize scraped text before writing it into a local Markdown file."""
    text = str(value or "").replace("\x00", "").replace("```", "` ` `")
    if limit:
        text = text[:limit]
    return text


def safe_handle(value):
    return re.sub(r"[^A-Za-z0-9_一-龥]", "", str(value or ""))[:80] or "unknown"


def safe_display(value):
    return safe_text(value, 120).replace("\n", " ").strip()


def safe_tweet_url(value):
    parsed = urlparse(str(value or ""))
    allowed_hosts = {"x.com", "twitter.com", "www.x.com", "www.twitter.com"}
    match = re.match(r"^/([^/]+)/status/(\d+)", parsed.path)
    if parsed.scheme == "https" and parsed.netloc.lower() in allowed_hosts and match:
        handle, status_id = match.groups()
        if re.fullmatch(r"[A-Za-z0-9_]{1,30}", handle):
            return f"https://x.com/{handle}/status/{status_id}"
    return ""


def safe_media_url(value):
    parsed = urlparse(str(value or ""))
    host = parsed.netloc.lower()
    if parsed.scheme == "https" and (host == "pbs.twimg.com" or host.endswith(".pbs.twimg.com")) and parsed.path.startswith("/media/"):
        return quote(str(value).replace("\n", ""), safe=":/?&=%,.-_~")
    return ""


def markdown_body(value):
    """Keep scraped Markdown from changing the surrounding document structure."""
    text = safe_text(value)
    lines = []
    for line in text.splitlines():
        if line.startswith(("#", "- ", "* ", ">", "```")):
            line = "\\" + line
        lines.append(line)
    return "\n".join(lines)


def generate_summary(posts, mode, query=None):
    """生成中文摘要"""
    if not posts:
        return "本轮扫描未发现新内容。"

    # 按浏览量排序取 top
    sorted_posts = sorted(posts, key=lambda p: parse_views(p.get("stats", {}).get("views", 0)), reverse=True)
    top = sorted_posts[:5]

    lines = []
    if mode == "search":
        clean_query = safe_text(query).replace("\n", " ")
        lines.append(f"「{clean_query}」搜索完成，共 {len(posts)} 条结果。")
    else:
        lines.append(f"For You 扫描完成，筛出 {len(posts)} 条 AI 相关内容。")

    lines.append("热点速览：")
    for i, p in enumerate(top, 1):
        handle = p.get("handle", "?")
        views = p.get("stats", {}).get("views", "?")
        text_preview = markdown_body(p.get("text", ""))[:60].replace("\n", " ")
        lines.append(f"{i}. @{handle} ({views} 浏览): {text_preview}...")

    return "\n".join(lines)


def save_results(posts, summary, mode, query, output_dir, latest=False):
    """保存为 Markdown"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H:%M:%S")

    if mode == "search":
        safe_q = re.sub(r'[^\w\u4e00-\u9fff]', '-', query)[:30]
        filename = f"search-{safe_q}-{date_str}.md"
    else:
        filename = f"auto-scan-{date_str}.md"

    filepath = output_dir / filename

    # 构建内容
    lines = [
        "---",
        f"date: {date_str}",
        f"time: {time_str}",
        f"type: x-{mode}",
    ]
    if query:
        lines.append(f"query: {json.dumps(safe_text(query), ensure_ascii=False)}")
    lines.extend([
        f"source: X {mode.title()} {'(Latest)' if latest else '(Top)'}" if mode == "search" else "source: X Feed",
        "tags: [x, AI, auto-scan]",
        "---",
        "",
        "## 摘要",
        "",
        summary,
        "",
        "## 推文列表",
        "",
    ])

    for p in posts:
        handle = safe_handle(p.get("handle", "unknown"))
        display = safe_display(p.get("displayName", ""))
        t = safe_text(p.get("time", ""), 32)[:16].replace("T", " ")
        text = markdown_body(p.get("text", ""))
        stats = p.get("stats", {})
        media = [safe_media_url(m) for m in p.get("media", [])]
        media = [m for m in media if m]
        url = safe_tweet_url(p.get("tweetUrl", ""))
        quoted = markdown_body(p.get("quotedText", ""))

        display = display.replace("(", "\\(").replace(")", "\\)")
        lines.append(f"### @{handle} ({display}) · {t}")
        lines.append("")
        lines.append(text)
        if quoted:
            lines.append("")
            lines.append(f"> 引用: {quoted[:200].replace(chr(10), ' ')}")
        lines.append("")

        # 互动数据
        stat_parts = []
        if stats.get("views"):
            stat_parts.append(f"👁 {stats['views']}")
        if stats.get("likes"):
            stat_parts.append(f"❤️ {stats['likes']}")
        if stats.get("retweets"):
            stat_parts.append(f"🔁 {stats['retweets']}")
        if stats.get("bookmarks"):
            stat_parts.append(f"🔖 {stats['bookmarks']}")
        if stat_parts:
            lines.append(f"*{' · '.join(stat_parts)}*")
            lines.append("")

        # 媒体
        if media:
            for m in media[:4]:
                lines.append(f"![media]({m})")
            lines.append("")

        # 链接
        if url:
            lines.append(f"[原文链接]({url})")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 追加或新建
    if filepath.exists():
        existing = filepath.read_text(encoding="utf-8")
        # 在 "## 推文列表" 后插入新内容
        if "## 推文列表" in existing:
            parts = existing.split("## 推文列表", 1)
            new_content = parts[0] + "## 推文列表\n\n" + "\n".join(lines[lines.index("## 推文列表") + 2:]) + "\n" + parts[1]
            filepath.write_text(new_content, encoding="utf-8")
        else:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(lines))
        print(f"[追加] {filepath}")
    else:
        filepath.write_text("\n".join(lines), encoding="utf-8")
        print(f"[保存] {filepath}")

    return filepath


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="xscan — X/Twitter Scanner via CDP")
    parser.add_argument("--mode", choices=["feed", "search"], default="feed",
                        help="扫描模式: feed (For You) 或 search (关键词)")
    parser.add_argument("--query", "-q", type=str, default=None,
                        help="搜索关键词 (search 模式必填)")
    parser.add_argument("--latest", action="store_true",
                        help="搜索最新推文 (默认搜热门)")
    parser.add_argument("--rounds", "-r", type=int, default=DEFAULT_ROUNDS,
                        help=f"滚动轮数 (默认 {DEFAULT_ROUNDS})")
    parser.add_argument("--output", "-o", type=str, default=str(DEFAULT_OUTPUT),
                        help="输出目录")
    parser.add_argument("--no-filter", action="store_true",
                        help="Feed 模式不做关键词过滤")
    parser.add_argument("--summary-only", action="store_true",
                        help="只输出摘要，不保存文件")

    args = parser.parse_args()

    if args.mode == "search":
        if not args.query or not args.query.strip():
            parser.error("search 模式需要非空的 --query 参数")
        args.query = args.query.strip()
    if args.rounds < 1:
        parser.error("--rounds 必须是大于等于 1 的整数")
    if args.latest and args.mode != "search":
        parser.error("--latest 只能用于 search 模式")

    # 1. 确保 Chrome 可用
    if not ensure_chrome():
        sys.exit(1)

    # 2. 连接 CDP
    print(f"\n[连接] CDP port {CDP_PORT}")
    session = CDPSession(CDP_PORT)
    try:
        current_url = session.connect()
        print(f"[Tab] {current_url[:80]}")
    except Exception as e:
        print(f"[错误] CDP 连接失败: {e}")
        sys.exit(1)

    # 3. 扫描
    try:
        posts = scan(session, args.mode, query=args.query,
                     latest=args.latest, rounds=args.rounds)
    except Exception as e:
        print(f"[错误] 扫描异常: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()

    if not posts:
        print("\n[结果] 未抓到推文。", file=sys.stderr)
        sys.exit(1)

    # 4. 过滤
    if args.no_filter:
        filtered = posts
    else:
        filtered = filter_posts(posts, args.mode)

    if not filtered:
        print("[结果] 过滤后无相关内容")
        sys.exit(0)

    # 5. 去重
    output_dir = Path(args.output)
    date_str = datetime.now().strftime("%Y-%m-%d")
    if args.mode == "search":
        safe_q = re.sub(r'[^\w\u4e00-\u9fff]', '-', args.query)[:30]
        target_file = output_dir / f"search-{safe_q}-{date_str}.md"
    else:
        target_file = output_dir / f"auto-scan-{date_str}.md"
    filtered = dedup_against_file(filtered, target_file)

    if not filtered:
        print("[结果] 去重后无新推文")
        sys.exit(0)

    # 6. 摘要
    summary = generate_summary(filtered, args.mode, args.query)
    print(f"\n{'='*50}")
    print(summary)
    print(f"{'='*50}\n")

    # 7. 保存
    if not args.summary_only:
        filepath = save_results(filtered, summary, args.mode, args.query, args.output, latest=args.latest)
        print(f"\n[完成] {len(filtered)} 条推文 → {filepath}")
    else:
        print(f"\n[完成] {len(filtered)} 条推文 (仅摘要模式)")


if __name__ == "__main__":
    main()
