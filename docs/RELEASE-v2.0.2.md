# Codex Quota Monitor v2.0.2 · macOS

这是 v2.0 正式线的修正版，包含 v2.0.1 的星瞳诺瓦与更新界面，并修复自动安装器访问 GitHub 发行元数据时的 HTTP 415。v2.0.1 原包保留，供追溯；请使用本版。

## 安装与升级

从 v2.0.0 或 v2.0.1 升级需要手动下载安装本版：旧版没有可用的自动安装链。下载 `codex-quota-monitor-v2.0.2-macos.zip` 与 `SHA256SUMS`，先运行 `shasum -a 256 -c SHA256SUMS`，再按包内 `RELEASE.txt` 在新目录配置和安装。不要同时运行两个监视器。

从本版开始，面板“检测更新”默认查询本项目最新正式发行。用户点击后会看到更新状态卡片；V2 LaunchAgent 管理的 macOS 安装可确认“安装并重启”。安装器核对下载 ZIP、发行文件清单和摘要，在旧目录旁创建新版本，复制并更新私有配置，切换服务与菜单栏；失败时尝试恢复旧 plist。旧目录与 Python 虚拟环境仍需保留。其他安装方式提供发布页链接，不会自动替换。

本版仍是手动首次安装的第三方工具，需要 macOS 和 Python 3.9+；ZIP 未签名或公证。五款其他伴宠及代码的来源边界见[资源记录](asset-provenance.md)和[源码复核](source-audit.md)。包内保留 Kevin Ke 与 Ailble 的 MIT `LICENSE` 与 `NOTICE`。

## 验证

Python 3.9 单元测试、Swift 类型检查、Chromium/WebKit 面板和贴边显示回归、发行包文件摘要审计通过。对公开 v2.0.1 包已实际完成发行元数据请求、ZIP 下载、SHA-256 校验和安全解包冒烟测试；LaunchAgent 切换及失败回退采用合成测试，没有改动现用安装。
