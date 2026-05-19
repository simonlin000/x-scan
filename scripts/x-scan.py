#!/usr/bin/env python3
"""
xcolab — X Feed Scanner (New Page Approach)
支持单次扫描和定时循环扫描，自动保存到知识库
"""
import subprocess
import json
import re
import sys
import os
import time
import argparse
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

# 滚动次数（环境变量可覆盖）
SCROLL_COUNT = int(os.environ.get("XCOLAB_SCROLL", "15"))

# 忽略词（噪音过滤）
IGNORE = ['高考', '高考志愿', '房子', '房价', '股市', '彩票', '炒股']

# 每次扫描滚动几次加载更多内容（已在上文定义，此处删除重复）
# SCROLL_COUNT = int(os.environ.get("XCOLAB_SCROLL", "4"))

# ============================================================
# 以下不需要改
# ============================================================

# JavaScript：提取 X 页面真实推文内容
EXTRACT_JS = """
() => {
    const posts = [];
    const articles = document.querySelectorAll('article[role="article"]');
    articles.forEach((article, i) => {
        // 移除40条限制，提取所有可见推文
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

# 已保存推文指纹集合（用于去重）
seen_fingerprints = set()


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


def load_existing_fingerprints():
    """加载已保存的推文指纹，用于去重"""
    global seen_fingerprints
    if not VAULT.exists():
        return
    
    for md_file in VAULT.glob("auto-scan-*.md"):
        content = md_file.read_text(encoding='utf-8')
        # 提取推文文本作为指纹
        for match in re.finditer(r'### @(.+?) · (.+?)\n\n(.+?)(?=\n\n\*|$|\n---)', content, re.DOTALL):
            handle = match.group(1)
            text = match.group(3).strip()
            fingerprint = f"@{handle}:{text[:100]}"
            seen_fingerprints.add(fingerprint)
    
    print(f"[去重] 已加载 {len(seen_fingerprints)} 条历史推文指纹")


def get_fingerprint(post):
    """生成推文指纹"""
    return f"@{post['handle']}:{post['text'][:100]}"


def save_posts(posts, ts, is_append=False):
    """保存推文到知识库，支持追加模式"""
    if not posts:
        return None
    
    VAULT.mkdir(parents=True, exist_ok=True)
    date_str = ts.strftime("%Y-%m-%d")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    
    filename = f"auto-scan-{date_str}.md"
    filepath = VAULT / filename
    
    # 如果是追加模式且文件已存在，读取现有内容
    existing_content = ""
    if is_append and filepath.exists():
        existing_content = filepath.read_text(encoding='utf-8')
        # 如果已有内容，找到推文列表部分追加
        if "## 推文列表" in existing_content:
            # 提取 frontmatter 和头部信息
            parts = existing_content.split("## 推文列表")
            header = parts[0] + "## 推文列表\n\n"
            
            # 生成新推文内容
            new_lines = []
            for p in posts:
                new_lines.append(f"### @{p['handle']} · {p['time'][:10] if p['time'] else '未知时间'}")
                new_lines.append("")
                new_lines.append(p['text'])
                new_lines.append("")
                if p['stats']:
                    new_lines.append(f"*{', '.join(p['stats'][:2])}*")
                    new_lines.append("")
                new_lines.append("---")
                new_lines.append("")
            
            # 合并：header + 新推文 + 旧推文
            old_posts = parts[1] if len(parts) > 1 else ""
            full_content = header + '\n'.join(new_lines) + old_posts
            filepath.write_text(full_content, encoding='utf-8')
            
            print(f"[追加] {filepath} (+{len(posts)} 条)")
            return filepath
    
    # 新建文件或覆盖
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
        f"从本次抓取中筛出 {len(posts)} 条相关 AI 内容。",
        "",
        "## 推文列表",
        "",
    ]
    
    for p in posts:
        lines.append(f"### @{p['handle']} · {p['time'][:10] if p['time'] else '未知时间'}")
        lines.append("")
        lines.append(p['text'])
        lines.append("")
        if p['stats']:
            lines.append(f"*{', '.join(p['stats'][:2])}*")
            lines.append("")
        lines.append("---")
        lines.append("")
    
    filepath.write_text('\n'.join(lines), encoding='utf-8')
    print(f"[保存] {filepath}")
    return filepath


def scan_once():
    """执行一次扫描"""
    ts = datetime.now()
    print(f"\n[{ts.strftime('%H:%M:%S')}] xcolab 扫描 X feed...")
    
    # 获取浏览器WS URL
    browser_ws = get_browser_ws_url()
    if not browser_ws:
        print("[错误] 无法连接到Chrome，请确认Chrome已开启调试模式")
        return []
    
    print(f"[连接] {browser_ws}")
    
    # 读取 Chrome
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[错误] 请先安装: pip install playwright && playwright install chromium")
        return []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(browser_ws)
            ctx = browser.contexts[0]
            
            # 始终创建新页面访问x.com/home，确保检测准确
            print("[打开] x.com...")
            x_tab = ctx.new_page()
            x_tab.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            
            print(f"[页面] {x_tab.url}")
            print(f"[标题] {x_tab.title()}")
            
            # 检查登录状态 - 等待页面完全加载后再检测
            x_tab.wait_for_timeout(3000)
            login_btn = x_tab.query_selector('a[href="/login"]')
            if login_btn:
                print("[错误] X 未登录，请先在Chrome中登录X.com")
                x_tab.close()
                return []
            
            print("[状态] 已登录")
            
            # 等待页面加载
            x_tab.wait_for_timeout(2000)
            
            # 滚动加载更多，多次滚动后提取
            for i in range(SCROLL_COUNT):
                x_tab.evaluate("window.scrollBy(0, 1200)")
                x_tab.wait_for_timeout(1500)
            
            # 滚动完成后再提取，获取更多推文
            posts = x_tab.evaluate(EXTRACT_JS)
            
            # 关闭页面
            x_tab.close()
            
    except Exception as e:
        print(f"[错误] Chrome 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    print(f"抓取到 {len(posts)} 条推文")
    
    # 过滤
    if KEYWORD_MODE == 'zh':
        relevant = [p for p in posts if is_relevant(p) and is_chinese(p['text'])]
    else:
        relevant = [p for p in posts if is_relevant(p)]
    
    print(f"相关：{len(relevant)} 条")
    
    # 去重
    new_posts = []
    for p in relevant:
        fp = get_fingerprint(p)
        if fp not in seen_fingerprints:
            seen_fingerprints.add(fp)
            new_posts.append(p)
    
    if new_posts:
        print(f"新推文：{len(new_posts)} 条（去重后）")
    else:
        print("没有新推文")
    
    return new_posts


def run_scheduler(interval_minutes=30, max_runs=None):
    """定时循环扫描"""
    print(f"[定时模式] 每 {interval_minutes} 分钟扫描一次")
    if max_runs:
        print(f"[限制] 最多运行 {max_runs} 次")
    print(f"[知识库] {VAULT}")
    print(f"[关键词模式] {KEYWORD_MODE}")
    print("按 Ctrl+C 停止\n")
    
    # 加载历史指纹
    load_existing_fingerprints()
    
    run_count = 0
    while True:
        run_count += 1
        print(f"\n{'='*50}")
        print(f"第 {run_count} 次扫描")
        print(f"{'='*50}")
        
        posts = scan_once()
        
        if posts:
            ts = datetime.now()
            save_posts(posts, ts, is_append=True)
        
        if max_runs and run_count >= max_runs:
            print(f"\n[完成] 已达到最大运行次数 ({max_runs})")
            break
        
        next_time = datetime.now().timestamp() + interval_minutes * 60
        print(f"\n[等待] 下次扫描: {datetime.fromtimestamp(next_time).strftime('%H:%M:%S')}")
        time.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description='X Feed Scanner - 扫描X/Twitter AI相关内容')
    parser.add_argument('--schedule', '-s', type=int, metavar='MINUTES',
                        help='定时模式：每N分钟扫描一次')
    parser.add_argument('--max-runs', '-m', type=int,
                        help='最大运行次数（配合--schedule使用）')
    parser.add_argument('--once', '-o', action='store_true',
                        help='单次扫描模式（默认）')
    
    args = parser.parse_args()
    
    if args.schedule:
        # 定时模式
        run_scheduler(interval_minutes=args.schedule, max_runs=args.max_runs)
    else:
        # 单次模式
        posts = scan_once()
        if posts:
            ts = datetime.now()
            save_posts(posts, ts)
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 完成")


if __name__ == '__main__':
    main()
