#!/usr/bin/env python3
"""
xcolab — X Feed Scanner (New Page Approach)
创建新页面来访问X，绕过context查找问题
"""
import subprocess
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

# ============================================================
# 配置区 — 在这里改设置
# ============================================================

# Chrome CDP 端口
CDP_PORT = os.environ.get("XCOLAB_CDP_PORT", "19542")

# X 用户名（你的 @handle）
USERNAME = os.environ.get("XCOLAB_USERNAME", "your_x_username")

# 知识库路径（推文保存到这里）
VAULT = Path(os.environ.get("XCOLAB_VAULT", "/path/to/your/knowledge-base/X资源收藏"))

# 过滤关键词（中文为主时用这个）
KEYWORDS_ZH = [
    'ai', '人工智能', 'chatgpt', 'claude', 'llm', 'agent', '大模型',
    'gpt', 'deepseek', 'openai', 'anthropic', '提示词', 'prompt',
    '自动化', '工作流', '工具', '智能体', '机器学习', '程序员',
    '代码', '编程', '开发者', '国产', '设计', '产品', 'cursor',
    'notion', 'obsidian', 'kimi', '豆包', '通义', '文心'
]

# 英文为主时用这个
KEYWORDS_EN = [
    'AI', 'LLM', 'GPT', 'Claude', 'Agent', 'automation',
    'prompt engineering', 'machine learning', 'open source',
    'API', 'startup', 'tool', 'workflow'
]

# 用哪套关键词？'zh', 'en', 'both'
KEYWORD_MODE = os.environ.get("XCOLAB_KEYWORD_MODE", "zh")

# 忽略词（噪音过滤）
IGNORE = ['高考', '高考志愿', '房子', '房价', '股市', '彩票', '炒股']

# 每次扫描滚动几次加载更多内容
SCROLL_COUNT = int(os.environ.get("XCOLAB_SCROLL", "4"))

# ============================================================
# 以下不需要改
# ============================================================

# JavaScript：提取 X 页面真实推文内容
EXTRACT_JS = """
() => {
    const posts = [];
    const articles = document.querySelectorAll('article[role="article"]');
    articles.forEach((article, i) => {
        if (i > 40) return;
        // 账号名
        const allLinks = article.querySelectorAll('a[role="link"]');
        let handle = '';
        for (const a of allLinks) {
            const spans = a.querySelectorAll('span');
            for (const s of spans) {
                const t = s.innerText.trim();
                if (t && t.startsWith('@') && t.length > 1) {
                    handle = t.slice(1);
                    break;
                }
            }
            if (handle) break;
        }
        // 时间
        const timeEl = article.querySelector('time');
        const time = timeEl ? timeEl.getAttribute('datetime') || '' : '';
        // 正文
        const textEl = article.querySelector('[data-testid="tweetText"]');
        const text = textEl ? textEl.innerText.trim() : '';
        // 互动数据
        const stats = [];
        const statEls = article.querySelectorAll('[aria-label]');
        for (const el of statEls) {
            const label = el.getAttribute('aria-label');
            if (label && (label.includes('回复') || label.includes('转发') || label.includes('喜欢') || label.includes('浏览') || label.includes('repost') || label.includes('reply') || label.includes('like') || label.includes('view'))) {
                stats.push(label);
            }
        }
        if (text && text.trim()) {
            posts.push({ handle, time, text: text.trim(), stats });
        }
    });
    return posts;
}
"""


def get_keywords():
    if KEYWORD_MODE == 'zh':
        return KEYWORDS_ZH
    elif KEYWORD_MODE == 'en':
        return KEYWORDS_EN
    else:  # both
        return KEYWORDS_ZH + KEYWORDS_EN


def is_relevant(post):
    text = post['text']
    for kw in get_keywords():
        if kw.lower() in text.lower():
            for ig in IGNORE:
                if ig in text:
                    return False
            return True
    return False


def is_chinese(text):
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff') > 5


def get_browser_ws_url():
    """获取浏览器WebSocket URL"""
    import urllib.request
    try:
        req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=5)
        data = json.loads(req.read())
        return data.get('webSocketDebuggerUrl')
    except Exception as e:
        print(f"[错误] 无法获取浏览器WS URL: {e}")
    return None


def main():
    ts = datetime.now()
    print(f"[{ts.strftime('%H:%M:%S')}] xcolab 扫描 X feed...")

    # 获取浏览器WS URL
    browser_ws = get_browser_ws_url()
    if not browser_ws:
        print("[错误] 无法连接到Chrome，请确认Chrome已开启调试模式")
        sys.exit(1)

    print(f"[连接] {browser_ws}")

    # 读取 Chrome
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[错误] 请先安装: pip install playwright && playwright install chromium")
        sys.exit(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(browser_ws)
            ctx = browser.contexts[0]

            # 创建新页面访问X
            print("[打开] x.com...")
            x_tab = ctx.new_page()
            x_tab.goto("https://x.com/home", wait_until="networkidle", timeout=30000)
            
            print(f"[页面] {x_tab.url}")
            print(f"[标题] {x_tab.title()}")
            
            # 检查登录状态
            login_btn = x_tab.query_selector('a[href="/login"]')
            if login_btn:
                print("[错误] X 未登录，请先在Chrome中登录X.com")
                x_tab.close()
                sys.exit(1)
            
            print("[状态] 已登录")
            
            # 等待页面加载
            x_tab.wait_for_timeout(2000)
            
            # 滚动加载更多
            for i in range(SCROLL_COUNT):
                x_tab.evaluate("window.scrollBy(0, 800)")
                x_tab.wait_for_timeout(800)

            posts = x_tab.evaluate(EXTRACT_JS)
            
            # 关闭页面
            x_tab.close()
            
    except Exception as e:
        print(f"[错误] Chrome 连接失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"抓取到 {len(posts)} 条推文")

    # 过滤
    if KEYWORD_MODE == 'zh':
        relevant = [p for p in posts if is_relevant(p) and is_chinese(p['text'])]
    else:
        relevant = [p for p in posts if is_relevant(p)]

    print(f"相关：{len(relevant)} 条")

    if not relevant:
        print("没有发现相关内容")
        return

    # 写知识库
    VAULT.mkdir(parents=True, exist_ok=True)
    date_str = ts.strftime("%Y-%m-%d")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "---",
        f"date: {date_str}",
        "type: x-read",
        "source: X For You Feed（自动扫描）",
        f"tags: [x, AI, auto-scan, {KEYWORD_MODE}]",
        "related: []",
        "ai-first: true",
        "---",
        "",
        "## For future Agent",
        "",
        f"X feed 自动扫描，时间：{ts_str}。",
        f"从 {len(posts)} 条推文中筛出 {len(relevant)} 条相关 AI 内容。",
        "",
        "## 推文列表",
        "",
    ]

    for p in relevant:
        lines.append(f"### @{p['handle']} · {p['time'][:10] if p['time'] else '未知时间'}")
        lines.append("")
        lines.append(p['text'])
        lines.append("")
        if p['stats']:
            lines.append(f"*{', '.join(p['stats'][:2])}*")
            lines.append("")
        lines.append("---")
        lines.append("")

    # 写文件
    filename = f"auto-scan-{date_str}.md"
    filepath = VAULT / filename
    filepath.write_text('\n'.join(lines), encoding='utf-8')

    print(f"[保存] {filepath}")
    print(f"[{ts.strftime('%H:%M:%S')}] 完成")


if __name__ == '__main__':
    main()
