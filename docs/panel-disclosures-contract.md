# V2 详情与皮肤区展开偏好

2026-09-20，接续 d735da3。生成器移除固定外部源对两个 details 节点的展开读取和独立 toggle 监听。V2 panel_disclosures.js 使用原生 details/open、WeakMap 和根节点捕获阶段的 toggle 事件；无需新依赖。

首次挂载只认持久偏好的字符串 true，其他值或读取失败均关闭；初始化不写偏好。正文因语言重建时，优先使用旧正文中节点的实时 open 状态，避免写入失败或尚未派发 toggle 时从旧持久值恢复错误状态。用户展开/关闭后尝试保存，写入失败仍保留当前 DOM 选择并重新约束面板位置。此临时选择随正文重建保留，但不跨卸载/新挂载，也不承诺尚未派发的事件已落盘。

WeakMap 记录各节点已知状态，忽略初始化与无变化事件。根监听仅绑定一次；只处理仍属于已连接面板的已登记节点，旧正文和卸载后的延迟 toggle 不写回。其他设置的存储容错不包含在本轮。

## 验证

- verify_disclosures.cjs 实现前缺文件失败，实现后 Chromium/WebKit 通过持久默认值、非法值、无初始化写入、写入失败、重建保留、旧节点事件、恢复写入及读取失败。
- verify_mount 在前一轮候选上复现写入失败后语言切换丢失展开状态；新候选双浏览器通过详情/皮肤展开跨中英往返保留、恢复后关闭落盘，既有语言与复制回归继续通过。
- 完整候选通过 verify_panel --bridge 双浏览器明暗主题和数据切换/失效，以及 verify_dispose 卸载重挂载与所有权保护。Python 3.9.6 / 3.14.3 各 120 项通过。
- 已目视核验 WebKit 明暗截图，语言往返后的详情内容和皮肤网格保持展开，延续原有滚动布局。

候选 /tmp/quota-disclosures-candidate，截图 /tmp/quota-disclosures-components 与 /tmp/quota-disclosures-panel-evidence。仅为隔离合成浏览器证据，现用安装、真实偏好未动；不等于原生、Windows 或发行验收。模板、皮肤资源和其余设置继续保留归因及 LICENSE/NOTICE。下一步继续处理其余显示偏好事件。
