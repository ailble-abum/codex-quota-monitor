# Codex Quota Monitor

Author / Creator / Developer: **Ailble**

## English

Codex Quota Monitor is a local, read-only monitor for Codex quota, token usage, context, and compaction state.

- Account limits and quota windows are dynamic. Not every user has a 5-hour window, so the monitor does not assume that one exists.
- Every quota window is an AND gate: each one needs headroom, and a reached window stops the account even while another still has some. So the collapsed bar and the quota headline answer with a time budget -- how long the account can keep working at the pace it has been spending -- and a window that would refill before it runs out is reported as "at least", not as a measurement.
- A reached limit is drawn as a stopped gauge rather than as per-window fills, because a half-empty pair of cells reads as "partly usable" while the account is in fact stopped. The nearest reset is named alongside it.
- The overlay is draggable and resizable, and adapts its layout to the information it displays.
- Mini, Standard, and Large layout presets are available.
- Quota history is kept locally.
- Context occupancy and cached-input share trends are included when local records provide them.
- Soft edge docking tucks the overlay behind a companion on the left or right wall. Six selectable companions are included, all six shipping illustrated artwork. A docked companion carries no card or plate -- just the character against the window edge, with the account gauge beside it. The gauge draws one cell per quota window the account reports, so a plan reporting a weekly window alone shows one cell while a plan reporting a short and a weekly window shows both.
- The installed build is named in the settings panel and by `monitorctl.py status`: the declared plugin version, the cachebuster Codex keys its cache directory on, the injected runtime version, and when the last install landed. A plugin cache does not refresh on its own, so this is what distinguishes "the update did not apply" from "there was no update".
- macOS menu bar support is available.
- A Windows adapter and tray companion are included; real-machine runtime verification is still pending.

## 中文

Codex Quota Monitor 是一个本地只读的 Codex 配额监视器，用于查看配额、令牌使用量、上下文和压缩状态。

- 账户限制和配额窗口是动态的，并非每个用户都有 5 小时窗口，因此监视器不会默认假设存在该窗口。
- 每个配额窗口都是「与」关系：每个窗口都要有余量，任一窗口见底即停止服务，哪怕另一个还有剩余。因此折叠栏与配额区首行都以时间预算作答——按当前消耗速度还能继续用多久；如果某个窗口会在耗尽前先重置，则给出「至少」下限，而不是一个会被读成截止时间的测量值。
- 已达上限时画成整条停止的配额计，而不是逐窗口填充：一格空、一格还满会被读成「部分可用」，而账户其实已经停了。旁边同时给出最近的重置时间。
- 悬浮层可拖动、可调整大小，并会根据显示内容自适应布局。
- 提供迷你、标准、大字三档布局预设。
- 配额历史记录保存在本地。
- 本地记录具备相应字段时，会展示上下文占用和缓存输入占比趋势。
- 左右边缘软吸附可把悬浮层收成角色伴宠，提供六款角色，六款均带插画。位图伴宠不套卡片边框，直接浮在窗口边缘，旁边是账户配额计。账户上报几个配额窗口就画几格：只上报每周窗口的套餐显示一格，同时上报短周期与每周窗口的套餐两格都显示。
- 设置面板与 `monitorctl.py status` 都会标出当前安装的版本：声明的插件版本、Codex 用来命名缓存目录的 cachebuster、注入脚本的运行时版本，以及最近一次安装时间。插件缓存不会自行刷新，因此这一行正是「更新没生效」与「根本没有更新」的分界。
- 已支持 macOS 菜单栏。
- 已包含 Windows 适配器与托盘组件；Windows 实机运行验证仍待完成。
