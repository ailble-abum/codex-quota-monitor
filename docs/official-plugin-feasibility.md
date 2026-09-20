# 官方插件内嵌与启动能力核查

核查日期：2026-09-20。基线：`4196e66`，分支 `codex/page-update-loop`，开始时工作区干净。此记录是文档与本地文件核查，不是真实宿主验收。

## 决策

保留 Codex 内嵌额度条与普通启动自动跟随目标。当前未找到满足“在现有宿主侧栏常驻挂载额度条”的公开第三方插件接口，因此本轮不新增启动器、不迁移为独立窗口、不安装试验插件、不更新现用监视器，也不上传。不能将“未找到公开支持”写成“官方绝不支持”。

## 能力与证据

| 问题 | 已核实的官方资料 | 对本项目的结论 |
| --- | --- | --- |
| 插件能安装吗 | [插件打包](https://developers.openai.com/plugins/build/plugins)描述本地 marketplace 与插件清单 | 文档支持；本轮未安装 V2 插件。个人目录可安装不代表进入官方公共目录 |
| 插件能执行程序吗 | [Hooks](https://learn.chatgpt.com/docs/hooks)提供命令钩子；[MCP](https://learn.chatgpt.com/docs/extend/mcp)支持通过命令启动本地 STDIO 服务 | 存在程序执行机制；不是任意后台启动器或宿主重启授权。本轮未执行钩子或 MCP 服务 |
| 打开应用就触发吗 | SessionStart 针对会话启动，source 包含 startup/resume/clear/compact；插件钩子需要审查信任 | 没有证据保证仅点击应用图标、尚未打开任务时就启动额度条。不能用会话事件冒充应用生命周期事件 |
| 插件能显示界面吗 | [MCP UI](https://developers.openai.com/plugins/build/chatgpt-ui)描述工具关联 UI 资源、iframe 与对话旁显示 | 存在对话组件能力；该文档以 ChatGPT 为宿主，不能据此确认当前 Codex 桌面版本支持所需挂载位置或持久性 |
| interface 是侧栏插槽吗 | 打包文档将 interface 定义为安装界面的名称、图标、介绍等元数据 | 不是宿主 DOM 挂载 API，不能凭此声明侧栏扩展支持 |
| 官方插件有原生侧栏界面吗 | [Codex Security 工作台](https://learn.chatgpt.com/docs/security/plugin/workbench)明确说明安装启用后可从侧栏进入 Security | 官方产品确有此体验；该页面没有提供第三方注册同类插槽的接口，不能照此推导 V2 可接入 |
| 能直接上架吗 | [提交与发布](https://developers.openai.com/plugins/deploy/submission)要求提交、审核、获批后发布；公开目录由 ChatGPT 与 Codex 共用 | 有公开分发流程，不是本项目获批或调试注入被允许的证据；未提交、未审核、未发布 |

## 本地官方资料与版本差异

先只读检查随环境提供的 `openai-docs/SKILL.md`、`plugin-creator/SKILL.md` 与 `plugin-creator/references/plugin-json-spec.md`（位于 `/Users/ailble/.codex/skills/.system/`）。本地样例的 interface 也是安装展示元数据，没有常驻侧栏注册字段。

本地插件创建技能对 hooks 的样例与验证限制存在差异；当前在线打包文档另有根目录 `plugin.json` 和 `extensions.com.openai` 格式。不能把本地旧脚手架校验通过当作当前宿主支持证明，也不应直接改写现用清单来碰运气。本轮没有创建插件或引入依赖。

在线核查已打开上述官方正文，另检索 Codex plugin sidebar/status bar 与 app startup；检出的 Security 工作台作为单独证据记录。不是穷尽全部内部接口的源码审计。未发现能直接覆盖目标的公开接口，故未开展无关开源库选型或复制旧版实现。

## 当前安装的只读核对

- 安装目录 `~/Library/Application Support/CodexQuotaMonitorV2/preview-20260920-switch` 仍存在。
- `~/Library/LaunchAgents/local.codex-quota-monitor-v2.plist` 仍指向该目录的 `.venv/bin/python` 与 `run.py --config .../config.json`，RunAtLoad/KeepAlive 为 true，没有 `--wait-for-host`。
- 安装副本 `run.py`、`quota_monitor/live.py` 未检出 `wait-for-host` / `wait_for_host`，与交接“等待模式未部署”一致。
- 以上只证明磁盘文件状态；没有查询宿主调试端口、修改认证/会话、操作真实窗口或重启进程，也不证明服务此刻健康。

## 接续门槛与验收

目前官方路径缺少常驻挂载位置和普通应用启动生命周期两项证据。下一步应获取针对第三方插件的公开宿主扩展规范或官方明确说明，核实这两项能力后，再设计不依赖调试注入的最小合成适配。对话 iframe 可以作为能力研究，但不能擅自取代用户已确定的常驻额度条。

既有调试注入路径仍受交接中的安全拒绝约束，不能改用 CDP、AppleScript、CLI、后台任务或另一 Agent 绕过。不会把允许执行命令的 hooks 当作绕过入口。

| 证据层 | 本轮状态 |
| --- | --- |
| 官方资料与安装文件 | 已只读核查，来源如上 |
| 文档改动 | 检查差异、链接与交接一致性；纯文档不新增行为测试 |
| Python 135 项、隔离 Chromium | 沿用交接历史记录，本轮未重跑，不增加通过声明 |
| 真实 macOS 普通启动自动跟随 | 未完成 |
| Windows 真机 / 正式发行 / 官方目录 | 未完成 |

本轮没有产品代码变更，不撤销既有内嵌实现和来源归因。实现接入仍待允许且有依据的路径；研究完成不等于产品完成。
