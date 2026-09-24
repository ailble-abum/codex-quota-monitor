# V2 macOS 发行候选包

`tools/package_candidate.py` 只接受已通过 `audit_release.py` 的隔离预览目录，向一个尚不存在的输出目录生成确定性 ZIP、`SHA256SUMS` 与 `CANDIDATE.json`。它拒绝覆盖现有输出，ZIP 内保留随 renderer 分发的 MIT `LICENSE`/`NOTICE`，清单明确标记 `candidate-not-release`。包中只有源码、renderer 和配置示例，不复制虚拟环境、认证、会话或运行状态。

2026-09-24 的实际候选位于 `/Users/ailble/Desktop/季二六软件项目-V2发行候选-20260924`，文件名 `codex-quota-monitor-v2.0.0-rc.1-macos.zip`，SHA-256 为 `833237b4e964352e97f133f2a561c773213d964fcdcd8b5653dff5c599fb9754`；`shasum -a 256 -c SHA256SUMS` 已通过。`rc.1` 只是候选标签，包内运行版本与 GitHub 正式发布标签尚未提升。

该工具为正式发行准备可重复的输入，但不会创建 tag、推送 release、修改 `main` 或注册系统服务。只有 [macOS 原生验收门槛](mac-release-gate.md) 通过后，才可决定最终版本号、重建发行内容并发布。
