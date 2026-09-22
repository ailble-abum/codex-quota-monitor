# V2 版本、更新与界面诊断正文

2026-09-20，接续 1bd4e26。固定源生成器移除 applyHud 中的版本/更新/诊断构建及不再调用的 put 辅助函数，接入 panel_diagnostics.js；元数据采用文本节点，不解析 HTML。标准 DOM、URL、Date 足以完成本次替换，无新依赖。

版本字段接受非空字符串；运行时版本要求非负安全整数，安装时间要求可表示为 Date 的非负有限 Unix 秒。版本字符串只做文字展示，不声称进行 semver 校验。

更新入口仅接受显式 HTTPS URL，拒绝带账号密码的 URL、相对路径和其他协议。无效链接仍可显示新版本文字，但不产生入口，也不回退到旧项目发布页。原生链接使用新窗口及 noopener noreferrer；取消旧剪贴板回退。同版本 URL 改变时同步更新 href，状态离开可用更新后清除旧入口；相同内容保留节点。

旧源的 dom 合约为 sidebarRows 数量、activeRow 布尔值和 conversationId 布尔值。行数要求非负安全整数，标记只接受布尔值；缺失字段显示未知，全部缺失显示“界面探测未提供”。只有明确的零行或已知行数配合活动行 false 才提示界面可能更新。V2 runtime 现在始终发布受限 `build.pluginVersion` 与 `update.status`；更新状态默认 `not_configured`，只有显式 HTTPS manifest 才后台低频请求，响应仅接受版本号和 HTTPS 链接，网络失败不阻塞日志或账户数据。

## 验证与边界

- verify_diagnostics.cjs 在实现前因文件缺失失败，实现后 Chromium/WebKit 双语通过：字面元数据、缺失诊断、同版本链接变化、非法 URL、状态清除及重复内容节点保留。
- 完整候选通过 verify_mount 与 verify_panel --bridge，覆盖 Chromium/WebKit、明暗主题及既有切换/数据失效行为。设置内更新提示有合成数据集成断言。
- Python 3.9.6 与 3.14.3 全套各 120 项通过。候选位于 /tmp/quota-diagnostics-candidate，完整截图位于 /tmp/quota-diagnostics-panel-evidence，更新行截图位于 /tmp/quota-diagnostics-components。

以上为隔离合成浏览器证据，未执行真实更新检查或下载，不构成原生、Windows 或发行验收。现用安装与真实会话未改动。剩余视图初始化、布局、标签/时长及伴宠代码仍保留来源归因，候选携带 LICENSE/NOTICE；整份 renderer 的独立替换尚未完成。
