# 本地开发与验证

源码工作目录与正在使用的监视器安装相互独立。以下命令在仓库根目录运行；验证只使用合成会话、临时浏览器和隔离目录，不安装服务，不读取或修改真实认证与会话。

## 安装开发依赖

使用 Python 3.9+、Node.js 18+ 与 npm。macOS 菜单栏验证还需要 Xcode Command Line Tools。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cdp.txt
npm ci --ignore-scripts
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" npx --no-install playwright install chromium webkit
```

Playwright 版本固定在 `package-lock.json`。浏览器存放于仓库内的忽略目录，不依赖 Codex 应用内附带的 Node 模块。不要提交 `.venv`、`node_modules`、`.local` 或私有 `config.json`。

## 基础检查

```sh
.venv/bin/python -m unittest discover -s tests
swiftc -typecheck quota_monitor/QuotaMenu.swift
```

## 合成浏览器验证

```sh
export PYTHON="$PWD/.venv/bin/python"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers"
npm run test:live
```

面板修改还应构建一个未使用过的输出目录，再运行仓库现有面板探针：

```sh
.venv/bin/python tools/build_panel.py .local/panel-candidate
node --check .local/panel-candidate/consumer.js
QUOTA_PANEL_CANDIDATE="$PWD/.local/panel-candidate/consumer.js" \
  node tools/verify_panel.cjs .local/panel-candidate .local/panel-artifacts --bridge
```

构建器拒绝已存在的输出目录；重复验证时换一个目录名。合成浏览器通过不等于真实 Codex UI、系统通知或 Windows 真机通过，分别记录验收证据。

## 协作

从最新 `origin/v2` 创建功能分支，遵循根目录 `AGENTS.md`。按任务提交聚焦的 commit，通过 PR 交接；本地环境准备本身不要求推送或发行。

提交前检查 `git diff --cached`，排除个人路径、认证、聊天正文、运行快照和日志。不要使用本机安装目录或 Codex 插件缓存作为源码仓库。涉及发行时另按发行文档验证安装包、来源声明和回退流程。
