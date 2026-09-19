# V2 账户窗口正文构建

2026-09-20，接续 4c6ac0b。生成器移除旧 applyHud 的逐窗口 HTML 拼接，改用 panel_account_windows.js。输入限于 accountFreshness 接受的完整窗口组；不重复校验或创建账户读取通路。

以 DOM 文本节点创建窗口标题、剩余数值、meter、状态/进度说明和重置/预测文字，再由浏览器序列化为 HTML，供保留的账户聚合与 put 比较更新使用。没有手工拼接字段为 HTML；仍复用 windowLabel/quotaTone/toneLabel 和原视觉类名。总预算、账户附加用量、来源行及状态说明尚未替换，完整 renderer 继续保留 LICENSE/NOTICE。

保留规则：剩余额度文字四舍五入，meter 使用实际百分比；账户受限时所有窗口 low。重置分钟向上取整，已到期显示等待刷新，60 分钟起按小时、1440 分钟起按天显示；pace 绝对值小于 2 为均匀进度，其他显示正负偏差的整数绝对值；预测只在提供 projectedExhaustAt 时展示。采用现有 DOM、Date 标准能力，无新增依赖。

## 验证

- verify_account_windows.cjs 在实现文件不存在时先失败，实现后 Chromium/WebKit 通过中英文、0/1/60/1440 分钟、预测、正负与均匀 pace、受限双窗口、空窗口及字面 HTML 标签安全显示。
- 完整候选通过 verify_mount.cjs：0%/100% 双窗口、受限低色、重复发布保留原卡片节点，并回归既有账户异常、时效、单位/语言/健康/详情/节点所有权。
- 完整 Chromium/WebKit 明暗主题面板探针通过；Python 3.9.6 / 3.14.3 全套各 120 项通过。
- 已目视核验从实际候选导出的受限双窗口卡片，使用保留 CSS 的独立固定位置视觉夹具，明暗主题通过。证据 /tmp/quota-window-view-cards-isolated，普通完整面板探针 /tmp/quota-window-view-panel-evidence，候选 /tmp/quota-window-view-candidate。

## 明确保留的布局边界

尝试在完整交互夹具加入 expanded edge:right/y:80 的初始布局时，后续折叠按钮移出视口，点击超时；最初未固定位置的双窗口截图也出现截断。没有将这些失败截图记为验收通过。本轮未修改布局实现，已恢复原交互夹具并通过；独立卡片截图只证明正文视觉，不能证明该初始停靠组合可用。下一步优先复现和处理这一布局问题，而非将窗口正文通过当作完整窗口布局通过。

仅为合成浏览器验收；现用安装与真实会话未改，真实账户、原生窗口、Windows 和发行尚未验收。

后续核查：[固定停靠折叠往返](docking-toggle-contract.md)已区分正常初始收起，并复现、修复固定面板模式往返后的可见状态丢失；相关左右停靠组合已补验收。
