# Codex Quota Monitor v2.0.3 · macOS

这是 v2.0 正式线的更新修正版，包含“星瞳诺瓦”和面板更新提示。它修复了此前版本自动安装器的 GitHub 请求头、临时目录解包和 LaunchAgent 切换时序问题。旧版发行包保留供追溯。

## 安装与更新

v2.0.0、v2.0.1、v2.0.2 用户需手动安装本版一次：下载 ZIP 与 `SHA256SUMS`，运行 `shasum -a 256 -c SHA256SUMS`，然后按包内 `RELEASE.txt` 在新目录安装。不要同时运行两个监视器。v2.0.3 起，由 V2 LaunchAgent 管理的 macOS 安装可在面板点击“检测更新”并选择“安装并重启”，更新后续正式版。前台运行或其他安装方式仍提供发布页链接。

更新器验证 GitHub 最新正式发行的 ZIP、SHA-256 和包内文件摘要，在旧目录旁建立新版本并迁移私有配置，随后切换服务和菜单栏。切换失败时尝试恢复旧 plist。旧目录及其 Python 虚拟环境需继续保留。首次安装仍需 macOS、Python 3.9+ 和手动配置；ZIP 未签名或公证。

本版继续包含 Kevin Ke 与 Ailble 的 MIT `LICENSE`、`NOTICE`。其他伴宠及源码来源边界见[资源记录](asset-provenance.md)和[源码复核](source-audit.md)。

## 验收

完整验收记录见 [v2.0.3 验收](ACCEPTANCE-v2.0.3.md)。其中包括公开 v2.0.2 包的实际下载与安全解包，以及独立合成 Codex 页面上的真实 macOS LaunchAgent 升级和失败回退。验收没有改动现用监视器、认证文件或会话记录。
