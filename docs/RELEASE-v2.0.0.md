# Codex Quota Monitor v2.0.0 · macOS

首个 V2 正式版仅面向 macOS。Windows 将在后续真机测试后另行发布。

## 本版内容

- V2 自有的会话读取、CDP 通信、面板与服务运行链，不调用旧版 injector 或启动脚本。
- 当前账户额度、本地上下文和七天采样报告；项目名称仅取已验证任务的目录末级，历史与通知写入独立私有目录。
- 可选的额度通知、手动检查更新、macOS 菜单栏与离线七天报告。
- `doctor` 同时检查服务、配置与面板最近成功发布状态；服务和菜单栏均可显式安装、查询、卸载。

## 安装与边界

下载 `codex-quota-monitor-v2.0.0-macos.zip` 与 `SHA256SUMS`，先核对 SHA-256，再解压到新目录。包内 `RELEASE.txt` 说明虚拟环境、私有配置、前台验证、LaunchAgent 安装与回退顺序。请先停止旧版监视器，避免两个实例写入同一 Codex 页面。

需要 macOS、Python 3.9 或以上，并按包内 `requirements-cdp.txt` 安装依赖。菜单栏程序包含 arm64 与 x86_64 两种架构；本轮真实 UI 验收在 Apple Silicon Mac 上完成，Intel Mac 尚未真机验收。此包为手动安装，未签名或公证，也不是 Codex 官方插件。

包内保留 Kevin Ke 与 Ailble 的 MIT `LICENSE` 和 `NOTICE`。12 个伴宠视觉资源继续保留来源声明；发行不声称其初始创作权属已完成独立鉴定。

## 验证

Python 3.9 全套测试、Swift 类型检查、合成 Chromium/WebKit 面板测试、ZIP 内容审计通过。本机真实 Codex 前台发布与退出清理、V2 LaunchAgent、`doctor=updated`、菜单栏显示、Codex 退出重开、Mac 重新登录，以及卸载 V2、恢复旧版后重新安装 V2 已完成验证。详情见 [验收记录](BETA-VALIDATION.md)和 [macOS 发行门槛](mac-release-gate.md)。
