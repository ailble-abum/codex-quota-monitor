# Codex Quota Monitor

[中文](#中文介绍) · [English](#english)

## 中文介绍

我做这个工具的原因很简单：Codex 的用量信息藏得比较深，而我经常想在开始一个长任务之前看一眼，还剩多少额度、当前上下文有多满、这次到底用了多少 Token。

Codex Quota Monitor 把这些信息放回工作现场。它在 Codex 桌面窗口里显示一个可拖动的小面板，同时在 macOS 菜单栏保留一份简要状态。所有会话分析都在本机完成，不上传日志，也不会改动 Codex 的认证文件。

### 能看到什么

- 折叠栏和配额区首行直接回答"还能用多久"：按当前速度给出还能继续工作的时长
- 账户实际返回的配额窗口、剩余比例、重置时间和倒计时
- 当前消耗速度与均匀进度的差值，以及按当前速度计算的预计耗尽时间
- 本轮、当前会话、输入、缓存输入、输出和推理 Token
- 当前模型、推理强度和上下文占用
- Codex 压缩事件、压缩后的首个请求大小和交接提醒
- 官方账户 Token 活动摘要与每日用量
- 最近会话按模型和项目的本地 Token 排名
- 可用重置额度数量及最近到期时间

每个配额窗口都是一个"与"条件：每个窗口都要有余量，任一窗口见底就停止服务，哪怕另一个还剩很多。所以面板不会只报一个百分比——它按当前速度折算成剩余时间。如果某个窗口会在耗尽之前先重置，它会显示"至少还能用"加一个下限，而不是一个会被读成截止时间的数字。已达上限时，伴宠旁边的配额计整条转成停止态并给出最近的重置时间，因为"一格空、一格还满"看起来像"部分可用"，而账户其实已经停了。

设置面板底部会显示当前安装的版本：插件版本、Codex 用来命名缓存目录的 cachebuster、注入脚本的运行时版本，以及最近一次安装时间。`monitorctl.py status` 输出同一串信息。插件缓存不会自行刷新，这一行就是"更新没生效"和"根本没有更新"的分界。监视器每天最多一次读取 GitHub 上的公开 `plugin.json`，有新版本时在这里提示；请求不携带本地版本、账户信息或会话内容，失败时静默保持离线功能。

面板会用「官方账户」「本地会话」和「估算」微标区分数据性质。消息级详情只解析并下发当前活动任务；任务切换后下一次刷新跟进。注入失败会在菜单栏显示警告，`doctor` 同时报告注入器状态。菜单栏的「本地 7 天周报」汇总采样跨度、期间最低配额、上下文峰值、平均缓存占比及主要模型/项目。

面板有迷你、标准和大字三种尺寸。位置、展开状态、显示单位和提醒设置都会保留。

面板整体都可以拖动：标题栏、配额数字、行与行之间的空白都能起拖。只有真正需要自己接管点击的控件会挡住拖拽——按钮、单位选择、折叠标题，以及四个不可见的角部缩放热区；鼠标经过角落时只显示对应的缩放光标，不再让缩放 UI 占用内容空间。滚轮滚动条那片区域仍然属于滚动，不会变成拖动。顶部的用量标题栏固定不动，往下翻列表时它不会跟着滚走。

### 角色伴宠与边缘软吸附

把面板拖到屏幕左侧或右侧边缘松手，它会软吸附收起，只剩一只角色伴宠。鼠标移到伴宠上展开面板，移开自动收起，点一下则固定展开；拖动面板任意位置可以重新脱离。

显示设置里提供六款角色：薄荷黑猫、软糖女孩、柯基助手、薄荷萌男、霜夜先生、红茶御姐。吸附只覆盖左右两侧——每只角色都是"从侧边探头"的姿态，贴到上边或下边只会变成躺倒。六款都带插画，构建脚本 `scripts/build_companion_art.py` 把源图背景抠成透明后内联进注入脚本。位图伴宠不套卡片外框，角色直接浮在窗口边缘，旁边只留一条可抓的长条；上下文环按每款角色的头部单独校准，上下文提示也会以当前可见角色为锚点跟随左右停靠位置。玻璃卡片只保留给矢量回落形象，因为它在浅色主题下需要底板撑出轮廓。角色皮肤在设置里是可折叠的一项，收起时标题上仍显示当前选中的角色名。

伴宠旁边是账户配额计：账户上报几个配额窗口就画几格，各自按自己的剩余比例填充。命中任一窗口的上限时，它不再逐格填充，而是整条转成停止态并横过一条停止标记——AND 门下一格空一格满会被读成"部分可用"，而账户已经停了。悬停可以看到各窗口的精确百分比和最近的重置时间。

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

`install` 会先把所有文件写好再操作 launchd，因此注册被拒时不会留下过期的运行目录。定义未变化的服务就地重启，不拆不建；定义有变化的才会重建，且重建被拒时会恢复原定义。如果 launchd 拒绝注册（受限或沙箱会话可能返回 `Bootstrap failed: 5: Input/output error`），命令仍会同步运行目录、指出未注册的服务并以非零码退出，在普通终端重跑同一条命令即可完成注册。

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

遇到问题、发现 Bug，或者有改进建议，可以提交 [GitHub Issue](https://github.com/ailble-abum/codex-quota-monitor/issues)，也可以直接写信给我：[ailblechase@gmail.com](mailto:ailblechase@gmail.com)。

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

### Companions and soft edge docking

Release the panel within 14px of the left or right wall and it tucks away, leaving only a companion. Hover the companion to reveal the panel, move away to hide it, click to pin it open, or drag the revealed header to detach it.

Display settings offer six companions. Docking covers the two side walls only, because every companion is drawn peeking in from a vertical edge. All six ship illustrated artwork, keyed out of the source renders and inlined into the injected script by `scripts/build_companion_art.py`.

Beside the companion sits the account gauge: one cell per quota window the account reports, each filled by its own remaining share. When any window reaches its limit the gauge stops filling per window and becomes a single stopped bar with a bar drawn across it -- under the AND gate a half-empty pair of cells reads as "partly usable" while the account is in fact stopped. Hovering names each window's exact percentage and the nearest reset.

The collapsed bar and the quota headline answer with a time budget rather than a share: how long the account can keep working at the pace it has been spending. A window that would refill before it runs out is shown as "at least", so a comfortable account is not handed a number that reads like a deadline. The settings panel and `monitorctl.py status` both name the installed build, because a plugin cache does not refresh on its own. At most once a day, the monitor reads the public `plugin.json` on GitHub and shows a notice here when a newer build exists. That request carries no local version, account data, or conversation content; failure is silent and the offline monitor keeps working.

Trust badges distinguish official account data, local-session observations, and estimates. Message-level detail is parsed and delivered only for the active task. Injection failures surface in the menu bar and in `doctor`. The menu bar also opens a local seven-day report summarizing sample coverage, minimum quota, peak context, average cache share, and the leading model/project.

macOS is the tested platform. The Windows adapter is included but still needs full validation on real hardware.

Bug reports, questions, and suggestions are welcome through [GitHub Issues](https://github.com/ailble-abum/codex-quota-monitor/issues) or by email at [ailblechase@gmail.com](mailto:ailblechase@gmail.com).

MIT licensed. The desktop injection and session parsing work began from [KevinKE93/Codex-Monitor](https://github.com/KevinKE93/Codex-Monitor); attribution is preserved.
