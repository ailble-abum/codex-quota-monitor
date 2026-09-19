# V2 账户聚合正文与附加用量

2026-09-20，接续 e5b4f69。固定生成器移除 applyHud 的 quotaHtml 聚合段，改用 panel_account_overview.js。来源行、预算、空窗口状态、多窗口说明、受限提示和附加用量由文本 DOM 构建；窗口卡片仅接收 V2 accountWindowHTML 的文本节点序列化结果，仍通过已校验的完整窗口组。重复同内容不替换已挂载节点。

预算函数也从固定外部源移除：只接受 floor/exhaust、有限非负秒数，复用仍保留的 durationPhrase。枚举核查自旧提交 2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed 的 quota_reader.py:33–60。非法预算或未知类型不生成时长结论；受限账户仍优先说明上限/重置。

日用量采用数组最后一项，累计用量采用 summary.lifetimeTokens；仅展示有限非负数，不对日期重排或推断完整历史。重置额度要求非负安全整数；到期时间仅接受可表示为 Date 的非负有限 Unix 秒。无效到期时间省略，有效额度计数可保留。附加值只在 live 账户状态下展示，过期数据不继续冒充当前数值。多窗口说明改为“所有窗口”，兼容超过两个窗口。

采用标准 DOM/Date/Number 与现有格式化接口，无新依赖。文案、视觉资产及剩余标签/时长/布局/伴宠实现继续归因，LICENSE/NOTICE 保留。没有新增真实账户、历史用量或重置接口。

## 验证

- verify_account_overview.cjs 先因无实现文件失败；实现后 Chromium/WebKit 通过中英、有效/过期附加值、无效预算类型/负数/字符串/无穷值、负用量/非法额度/日期、空窗口受限提示、读取中状态及重复节点身份。
- 完整候选通过 verify_mount、verify_panel 和 verify_docking：包括原有异常输入、时间/任务切换、双窗口、固定停靠折叠往返、左右停靠缩小视口与明暗主题。
- 已目视核验 WebKit 完整右侧停靠面板的明暗截图，来源/窗口/多窗口说明布局正常。Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-overview-candidate，截图 /tmp/quota-overview-panel-evidence 与 /tmp/quota-overview-docking-evidence。隔离合成浏览器证据不等于真实账户、原生窗口、Windows 或发行验收；现用安装和真实会话未动。下一步继续处理保留的版本/更新信息与诊断正文。
