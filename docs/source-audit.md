# 最小替换范围审计

## V2 源码复核（2026-09-24）

以 [KevinKE93/Codex-Monitor](https://github.com/KevinKE93/Codex-Monitor) 的 `56b2ea3602cf8395bdc9d0513a8088f8e38d657e` 为固定上游基线，逐文件对比 V2 当前 `quota_monitor` 与 `tools` 的 Python、JavaScript/CJS 源码和上游 Python、JavaScript、Shell、Swift、PowerShell、CSS、HTML 源码。使用 `difflib.SequenceMatcher(autojunk=False)` 定位连续相同文本行；只记录至少 4 行、其中至少 3 行非空的块。初扫发现 `panel_metrics.js` 中三个未被产品调用的文案辅助函数，以及 `panel_host_details.js` 的一小段宿主节点筛选流程。前者已删除；后者按当前 V2 选择器契约改为取首个非空匹配组、保持顺序去重并排除自有面板节点，附独立 Node 回归检查。

修改后同口径重扫，符合上述门槛的相同块为 0；Python 3.9 全套 172 项、指标与宿主节点 Node 检查通过，V2 consumer 构建及 Node 语法检查通过。该扫描只定位逐行相同文本，不覆盖改写表达、短于门槛的片段、图像或第三方来源，也不是独立著作权证明。伴宠资源和正式发行内容仍须分别复核；现有 LICENSE/NOTICE 继续保留。

日期：2026-09-20。当前版本基线：`2213aeb`（检查时工作区干净）。上游基线：`56b2ea3602cf8395bdc9d0513a8088f8e38d657e`。这是工程来源排查，不是著作权鉴定或所有历史版本的穷尽审查。

## 结论

保留现有产品设计和本项目新增能力，定点替换继承底层。无需为了移除特定上游实现而重建全部产品、改用 Web Component 或换语言。此前整体 V2 重建建议范围过大；旧工期估算不应继续使用。

产品已经包含大量本项目设计和新增实现。拥有这些贡献与必须保留仍在使用的上游许可可以同时成立，不必等到重写后才称它为自己的产品。

## 方法和限制

对 scripts 下 Python/Shell/Swift/PowerShell 源文件，与上游 scripts 所有文本文件做跨文件 SequenceMatcher 比较（autojunk=False），记录连续至少 8 行相同块内的非空行；至少 16 行才列出结果。检查关键命中块、函数边界、调用点，并核对拆分提交 `3b12c59`。

补充扫描当前测试、Markdown、JSON、SVG 与上游相应文本：连续至少 12 行且累计至少 20 行的长块命中未检出。未逐版本追溯上游历史；未完成 AST 等价、改写表达、第三方来源或图像权属鉴定。未命中不能当成原创证明；通用语法、协议字段与短函数相同也不能自动当成受保护表达。

## 建议保留的新增部分

| 模块 | 保留内容 | 当前证据与边界 |
| --- | --- | --- |
| quota_reader.py、quota_alerts.py | 官方账户读取、动态配额窗口、时间预算、重置额度、通知去重 | 上游脚本未检出上述长块；功能为本项目扩展，来源仍可继续追溯 |
| context_health.py、usage_history.py | 压缩观测、交接提醒、历史、周报、模型/项目统计 | 无上述长块；消费者需适配新会话数据契约 |
| QuotaMenu.swift、monitorctl.py | 菜单栏、安装、版本记录、doctor | 无上述长块；安装仍调用旧启动器，控制命令含旧 DOM 标识，需联动适配 |
| windows_monitor.py、windows_tray.ps1 | Windows worker、计划任务、托盘、诊断 | 无上述长块；worker 启动旧 injector，不能把整个运行链视为已脱离上游 |
| update_check.py、injector_status.py、platform_paths.py | 更新检测、注入健康、平台路径 | 无上述长块，优先保留 |
| 伴宠插画、Logo、build_companion_art.py、companion_art.py | 六款角色、美术处理与生成产物 | 有独立新增提交链：a3d40a9、afe50a2、17c5302、ec483c0、c9b63e5、f99e41c；图像来源/生成记录仍需归档，未做权属鉴定 |
| injector 内的新增交互 | 伴宠皮肤、吸附、上下文环、尺寸、四角缩放、提示定位、配额计 | 主要在当前约 174–227、260–325、874–1248、1629–1969 行；这些是功能定位，不是整个区间原创认证，需逐函数保留并去除周边派生代码 |

## 实质性替换候选

行号全部相对当前基线，后续修改会漂移。相同块统计仅用于定位。

| 候选 | 证据 | 最小动作 | 相对代价 |
| --- | --- | --- | --- |
| context_token_inspector.py | 520 行；长块内 428 非空行命中上游同名文件；186–520 为连续相同块 | 独立实现日志读取、摘要、消息/Token 对应、增量解析和输出格式；保留本项目需要的数据接口 | 中高 |
| cdp_transport.py | 181 行；118 非空行命中上游 injector；CDPClient、帧编解码、目标发现都有命中 | 独立 CDP 适配；先评估成熟 WebSocket 库的许可、Python 3.9 和安装成本，避免继续复制手写协议实现 | 中 |
| payload_builder.py | 165 行；30 非空行长块命中，21–40、121–130 有连续块；结构来自拆分 | 保留“只下发活动任务”和载荷裁剪要求，独立编写数据组装与缓存；不能只替换命中行 | 中 |
| port_utils.sh | 238 行与上游完全一致 | 合并为小型平台启动/发现适配层，覆盖端口占用和应用退出状态 | 中 |
| reopen_codex_with_debug.sh | 38 行与上游完全一致 | 独立实现必要的启动参数与重启协调，保持用户退出语义 | 与启动器合并 |
| start_codex_monitor.sh | 前 60 行连续一致；69 行中命中块含 51 非空行 | 保留新增健康告警需求，重写监视循环和恢复处理；联动 monitorctl 安装命令 | 与启动器合并 |
| context_token_injector.py | 2262 行；长块内 807 非空行命中；1396–1631 连续 236 行、1968–2072 连续 105 行尤为明显 | 保留新增产品 UI，替换宿主定位、消息匹配、详情挂载、观察器与运行循环，并审计共用样式/文案/辅助函数 | 高 |

injector 优先检查函数：summaryHover/itemChip/itemTitle、activeSidebarRow、assistantNodes/actionRowForAssistant/assistantChipTargets、visibleItemForNode、detailCandidates/detailPrefixes/scoreDetailForNodes/textChunks/textMatchScore/detailForVisiblePage、applyFooters、detailForCurrentThread/scheduleDetailApply/applyAll/installObserver，以及 Python main。不能因配额面板与这些代码在同一文件，就整张 UI 推倒重做。

## 调用关系及替换顺序

monitorctl → start/reopen/port_utils → injector → cdp_transport + payload_builder → inspector。

Windows worker 也会调用 injector。历史和菜单栏消费整合后的快照，需要保持数据含义兼容。

1. 冻结现有行为契约和合成验收样例；保存新增 UI 的深浅主题对照，不复制上游测试实现。
2. 独立替换 inspector 与 payload_builder，保持消费者接口，验证增量、半行、截断、重复事件、缺失字段和任务切换。
3. 替换 CDP 与三个启动脚本；验证连接失败、重连、端口冲突、用户退出和安装恢复。
4. 替换 injector 的继承宿主集成，保留伴宠/配额等新增交互；验证刷新不重复、切换不串任务、断连不显示伪新鲜数据、键盘与缩放。
5. 清查测试、资源、打包文件和文档来源；对实际发行内容复核。Windows 真机另列验收，不能以 macOS 或模拟测试代替。

审计提交时尚未开始实现。后续用户确认继续最小范围替换，首批读取器进度见 [读取器契约](reader-contract.md)。本报告不要求另建公开仓库或删除现有历史；新仓库不提供自动的法律免责效果。

阶段接续：新数据链已通过 [外部面板隔离验证](panel-probe.md)；独立 [CDP 通信层](cdp-contract.md) 已通过合成服务和临时 Chromium 验证。二者尚未连成现用安装中的更新循环，旧 injector/启动器、消息级对应与完整发行来源审计仍未完成，不能将部分测试通过记为整个候选已替换。

## 何时可调整归因

MIT 要求包含软件副本或实质性部分时保留版权与许可文本：https://opensource.org/license/mit （2026-09-20 核对）。必须在发行内容已处理全部上游实质性实现后，依据来源记录评估新版本声明；不能用某个相似度阈值决定。仍分发的旧版、旧源码及历史内容保留对应声明。不声称上游贡献从未发生。

按上述最小范围落实阶段 1 的行为规格与可运行验收。成本以单模块探针结果估计；现阶段无可靠依据给出新的日历工期。
