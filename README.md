# Codex Quota Monitor V2

[macOS v2.0.0 正式版](https://github.com/ailble-abum/codex-quota-monitor/releases/tag/v2.0.0) 已发布。Windows 留待后续真机测试。本仓库默认分支为 `v2`；旧版 `main` 的历史和代码保留，未被覆盖。

V2 提供 Codex 侧栏面板、账户额度、本地上下文和七天采样报告、可选系统通知、macOS 菜单栏、手动检查更新，以及可核对服务和面板状态的 `doctor`。运行链使用本仓库的 V2 会话读取、CDP 通信和 renderer；发行内容保留 MIT `LICENSE` 与 `NOTICE`。

## 下载与使用

从[发布页](https://github.com/ailble-abum/codex-quota-monitor/releases/tag/v2.0.0)下载 `codex-quota-monitor-v2.0.0-macos.zip` 和 `SHA256SUMS`，先运行 `shasum -a 256 -c SHA256SUMS`。解压后阅读包内 `RELEASE.txt`，在新目录建立 Python 3.9+ 虚拟环境、安装 `requirements-cdp.txt`，并填写私有 `config.json`。先停止旧版监视器，避免两个实例同时写入同一 Codex 页面。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cdp.txt
cp config.example.json config.json
# 编辑 config.json：填写 page_url、session_root、host_app；菜单栏另需 history_root
.venv/bin/python run.py --config "$PWD/config.json" --wait-for-host
```

前台验证通过后按 Ctrl+C 停止，再显式安装服务和菜单栏：

```sh
.venv/bin/python -m quota_monitor.service install --config "$PWD/config.json"
.venv/bin/python -m quota_monitor.service doctor
.venv/bin/python -m quota_monitor.service menu-install --config "$PWD/config.json"
.venv/bin/python -m quota_monitor.service menu-status
```

`doctor` 应同时报告 `service=running`、`config=valid`、`panel=updated`。回退时先执行 `menu-uninstall`，再执行 `uninstall`，然后按旧版原有方式恢复。V2 不会自动替换旧版安装；只有显式配置 `host_app` 时才会在调试端口不可用且宿主仍运行时请求重开 Codex。

## 范围与验证

发行 ZIP 含 arm64/x86_64 双架构菜单栏程序，但真实界面验收在 Apple Silicon Mac 上完成；Intel Mac 尚未真机验收。此包为手动安装，未签名或公证，也不是 Codex 官方插件。Python 3.9 全套 198 项测试、Swift 类型检查、Chromium/WebKit 合成挂载、真实 Codex 的服务、菜单栏、退出重开、重新登录与回退已核对。详见[发行说明](docs/RELEASE-v2.0.0.md)和[验证记录](docs/BETA-VALIDATION.md)。

伴宠资源和上游 MIT 来源继续按[资源来源记录](docs/asset-provenance.md)保留归因，不声称初始创作权属已完成独立鉴定。Beta 阶段的设计、契约和历史证据仍在 `docs/` 与 Git 历史中。
