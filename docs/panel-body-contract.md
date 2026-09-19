# V2 正文挂载与语言重建

2026-09-20，接续 c1c8714。本轮依据现有正文占位符与控件合约，用标准 template/DocumentFragment/replaceChildren 完成挂载，不增加依赖。固定源生成器将旧正文模板提取为 panelBodyTemplate 视觉资产，原样保留归因；V2 preparePanelBody 负责是否重建、单位节点迁移、设置展开状态及语言标记。

同语言且正文存在时不重建。语言改变时先构建脱离页面的模板，再迁移原单位控件并替换正文，单位节点身份和数量保持不变。设置区原来的打开/关闭状态随重建保留，同时同步设置按钮 aria-expanded；首次挂载仍关闭。修复旧行为中切换语言后正文关闭设置，但按钮仍标记展开的问题。

范围裁定：本轮只替换挂载逻辑；模板中的文案、皮肤按钮与外部视觉资产，以及重建后的设置事件绑定仍为保留实现。没有把模板搬移称作独立重写，也未扩大到偏好存储容错。

## 验证

- verify_mount 新增中英往返切换测试，在旧候选上明确失败于“language switch must preserve open settings”，在新候选上 Chromium/WebKit 通过；同时检查原单位节点身份、唯一数量和 aria-expanded。
- 完整候选通过 verify_panel --bridge 的双浏览器明暗主题、任务切换、缺失/失效数据和单实例验证；verify_docking 左右停靠、固定折叠往返及缩小视口通过；verify_dispose 的清理、重新挂载与所有权保护通过。
- Python 3.9.6 / 3.14.3 各 120 项通过。已目视核验语言往返后的 WebKit 设置区明暗截图；长设置区仍使用原有滚动布局。

候选 /tmp/quota-body-candidate；截图 /tmp/quota-body-components、/tmp/quota-body-panel-evidence、/tmp/quota-body-docking-evidence。以上仅为隔离合成浏览器验收，不是原生、Windows 或发行验证。现用安装与真实会话未修改，LICENSE/NOTICE 继续保留。下一步处理保留的设置事件与偏好读取边界。
