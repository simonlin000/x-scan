# x-scan

通过专用 Chrome DevTools Protocol（CDP）浏览器扫描 X/Twitter 的 AI 内容，支持 For You 信息流、关键词搜索、Latest 搜索、结构化推文提取、AI 相关性过滤、Tweet ID 去重、中文摘要和 Markdown 输出。

这是一个 Cola Skill，也可以作为独立的 Python CLI 使用。

## 能做什么

- 扫描 X For You 信息流
- 搜索关键词的 Top 或 Latest 推文
- 提取作者、时间、正文、引用推文、互动数据、媒体和原文链接
- Feed 模式按 AI 关键词过滤
- 按稳定 Tweet ID 去重，`/status/123` 和 `/status/123/photo/1` 视为同一条
- 追加写入每日 Markdown 文件
- 使用独立 Chrome Profile，不碰用户主 Chrome

## 安装

需要 Python 3、Google Chrome 或 Chromium，以及一个已经登录 X 的专用浏览器 Profile。

```bash
git clone https://github.com/simonlin000/x-scan.git
cd x-scan
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

很多人会让 Agent 帮忙安装 Skill。Agent 可以直接执行上面的依赖安装、测试和 smoke test。首次真正扫描时，只需要在专用浏览器 Profile 中登录一次 X，不要复制主 Chrome 的 Cookie 或会话文件。

## 使用

```bash
python3 scripts/xscan.py --mode feed
python3 scripts/xscan.py --mode search --query "Claude Code"
python3 scripts/xscan.py --mode search --query "Claude Code" --latest
python3 scripts/xscan.py --mode feed --rounds 3
python3 scripts/xscan.py --mode search --query "OpenAI" --summary-only
```

Latest 搜索使用 X 的 `f=live` 筛选参数。

## 配置

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `XCOLAB_CDP_PORT` | `19542` | 专用 Chrome CDP 端口 |
| `XCOLAB_CHROME_PROFILE` | `~/.cola/chrome-debug-profile` | 专用浏览器 Profile |
| `XCOLAB_CHROME_PATH` | 自动探测 | Chrome 或 Chromium 可执行文件 |
| `XSCAN_OUTPUT_DIR` | `~/Documents/X资源收藏` | Markdown 输出目录 |

例如：

```bash
XCOLAB_CDP_PORT=19542 \
XCOLAB_CHROME_PROFILE="$HOME/.cola/chrome-debug-profile" \
XSCAN_OUTPUT_DIR="$HOME/Documents/X资源收藏" \
python3 scripts/xscan.py --mode feed
```

## 输出

- Feed：`auto-scan-YYYY-MM-DD.md`
- Search：`search-{query}-YYYY-MM-DD.md`

输出包含 YAML frontmatter、中文摘要和推文列表。查询词会安全写入 YAML，外部内容和媒体地址会进行基本 Markdown/URL 校验。

## 安全边界

- 永远使用独立 Chrome Profile，不碰用户主 Chrome
- 不请求、不复制、不导出 X 密码、Cookie 或登录态
- 不使用 `pkill Chrome`
- Cron 调度属于宿主 Agent 的职责，不由这个仓库自动创建

## 故障排查

- 找不到浏览器：安装 Chrome/Chromium，或设置 `XCOLAB_CHROME_PATH`
- CDP 连接失败：检查 `XCOLAB_CDP_PORT` 是否被占用
- 未登录：在专用 Profile 中打开 `x.com` 并登录
- 没有推文 DOM：检查网络、登录状态或 X 页面结构是否变化
- 依赖错误：运行 `python3 -m pip install -r requirements.txt`

## License

MIT License，详见 [LICENSE](LICENSE)。
