# Codex Quota Monitor

[中文](#中文介绍) · [English](#english)

## 中文介绍

我做这个工具的原因很简单：Codex 的用量信息藏得比较深，而我经常想在开始一个长任务之前看一眼，还剩多少额度、当前上下文有多满、这次到底用了多少 Token。

Codex Quota Monitor 把这些信息放回工作现场。它在 Codex 桌面窗口里显示一个可拖动的小面板，同时在 macOS 菜单栏保留一份简要状态。所有会话分析都在本机完成，不上传日志，也不会改动 Codex 的认证文件。

### 能看到什么

- 账户实际返回的配额窗口、剩余比例、重置时间和倒计时
- 当前消耗速度与均匀进度的差值，以及按当前速度计算的预计耗尽时间
- 本轮、当前会话、输入、缓存输入、输出和推理 Token
- 当前模型、推理强度和上下文占用
- Codex 压缩事件、压缩后的首个请求大小和交接提醒
- 官方账户 Token 活动摘要与每日用量
- 最近会话按模型和项目的本地 Token 排名
- 可用重置额度数量及最近到期时间

面板有迷你、标准和大字三种尺寸。位置、展开状态、显示单位和提醒设置都会保留。

### 安装

要求：

- macOS 14 或更新版本
- 已安装并登录 ChatGPT/Codex 桌面端
- Python 3
- Xcode Command Line Tools（用于编译菜单栏组件）

从 GitHub 安装插件市场：

```bash
codex plugin marketplace add https://github.com/ailble-abum/codex-quota-monitor --ref main
codex plugin add codex-quota-monitor@codex-quota-monitor
```

安装本地服务：

`codex plugin add` 会打印 `Installed plugin root`。进入该目录后运行：

```bash
python3 scripts/monitorctl.py install
```

然后重新打开一个 Codex 任务，输入：

```text
启动 Codex 用量监控
```

首次连接桌面窗口时，程序可能需要重启 ChatGPT/Codex，以便启用仅监听 `127.0.0.1` 的本地调试端口。

### 常用命令

在插件目录运行：

```bash
python3 scripts/monitorctl.py status
python3 scripts/monitorctl.py doctor
python3 scripts/monitorctl.py show
python3 scripts/monitorctl.py reset-position
python3 scripts/monitorctl.py stop
python3 scripts/monitorctl.py start
```

`doctor` 会分别检查后台服务、菜单栏、桌面连接和账户额度。只看到进程启动并不代表面板已经成功注入，排查时优先看这个命令。

### 数据怎么读取

账户额度来自 Codex 本地 app-server 的 `account/rateLimits/read`。账户 Token 活动来自 `account/usage/read`。当前会话统计来自 `~/.codex/sessions` 和 `~/.codex/archived_sessions` 中的本地 JSONL 记录。

配额和 Token 是两套不同的数字。插件不会把本地 Token 估算成账户剩余额度。缓存输入已经包含在输入 Token 中，会话累计 Token 也不等于当前上下文占用。

历史文件保存在：

```text
~/Library/Application Support/CodexQuotaMonitor/
```

其中只有数值摘要、短项目文件夹名和生成的离线图表，没有聊天正文、密钥或完整项目路径。

### 隐私边界

这个项目不会：

- 上传会话日志
- 修改 `Codex.app`、`ChatGPT.app` 或 `app.asar`
- 写入认证文件
- 自动切换账户
- 自动消耗重置额度
- 在未开启的情况下发送配额通知

低额度通知默认关闭。即使打开，同一账户、同一窗口、同一重置周期也只提醒一次。

### Windows 状态

仓库包含 Windows 适配器和托盘脚本，运行文件会放到 `%LOCALAPPDATA%\CodexQuotaMonitor`。目前它们通过自动测试，但还没有在真实 Windows 机器上完成完整验收，所以我把 Windows 支持视为实验功能。

### 已知限制

- 桌面悬浮层依赖 CDP 和 Codex 当前的 DOM，桌面应用升级后可能需要跟进选择器。
- “预计耗尽时间”只是按当前窗口平均速度做的线性预测。任务大小、模型、缓存和空闲时间都会让它变化。
- 账户和 CLI 登录不一致时，app-server 返回的是 CLI 当前账户数据。
- 项目排名统计最近最多 100 个本地会话，不是账单明细。

### 开发与测试

```bash
python3 -m unittest discover -s plugins/codex-quota-monitor/scripts -p 'test_*.py' -v
swiftc -typecheck plugins/codex-quota-monitor/scripts/QuotaMenu.swift
```

提交问题时，请附上操作系统、Codex/ChatGPT 版本以及 `monitorctl.py doctor` 的输出。不要提交认证文件或完整会话日志。

### 来源与许可

桌面注入和会话解析部分最初基于 Kevin Ke 的 [Codex Monitor](https://github.com/KevinKE93/Codex-Monitor)。这个分支增加了账户额度、历史趋势、菜单栏、提醒、压缩观察、模型/项目分析和 Windows 适配。

项目采用 MIT License。原项目版权声明保留在 [LICENSE](LICENSE) 和 [NOTICE](NOTICE) 中。

## English

Codex Quota Monitor keeps the numbers I check most often close to the work: account quota, reset times, context pressure, session Tokens, model settings, compaction events, and recent local trends.

It runs locally. The overlay reads Codex session JSONL files, while account limits and Token activity come from the local Codex app-server. It does not upload session logs, modify authentication files, or consume reset credits.

Install:

```bash
codex plugin marketplace add https://github.com/ailble-abum/codex-quota-monitor --ref main
codex plugin add codex-quota-monitor@codex-quota-monitor
# Change into the "Installed plugin root" printed by the previous command.
python3 scripts/monitorctl.py install
```

Start a new Codex task and ask it to start Codex Quota Monitor. For diagnostics, run `python3 scripts/monitorctl.py doctor` from the installed plugin directory.

macOS is the tested platform. The Windows adapter is included but still needs full validation on real hardware.

MIT licensed. The desktop injection and session parsing work began from [KevinKE93/Codex-Monitor](https://github.com/KevinKE93/Codex-Monitor); attribution is preserved.
