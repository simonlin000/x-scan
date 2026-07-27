# Changelog

## 0.2.1 - 2026-07-28

- 修复 Skill 快速命令写死安装路径的问题
- 普通搜索正确标记为 Top，Latest 搜索正确标记为 Latest
- 拒绝空白查询并校验 CDP 端口范围
- 显式指定无效 Chrome 路径时不再回退到其他浏览器
- 收紧推文链接和摘要文本的清理
- 增加 Windows 常见 Chrome 路径探测

## 0.2.0 - 2026-07-27

- 修复 Latest 搜索使用错误的 `f=latest` 参数，改为 X 使用的 `f=live`
- 支持跨用户的 Chrome Profile、Chrome 路径和输出目录配置
- 改进 Chrome/CDP/页面失败时的错误信息和退出码
- 增加端口、扫描轮数和模式参数校验
- 增加 Markdown、YAML 和媒体 URL 的基本安全处理
- 增加 `requirements.txt`、离线单元测试和 Agent 安装说明
- 补充 README、MIT License 和公开发布所需元数据
