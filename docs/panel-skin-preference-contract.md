# V2 皮肤偏好与选择事件

2026-09-20，接续 ee67152。替换旧 mascotSkin、updateSkinButtons 和正文逐按钮监听，接入 V2 偏好与根 click 委托；皮肤表、图像、SVG、markup 及伴宠重建仍为保留资产/实现，无新依赖。

只接受皮肤表自有的字符串键，拒绝 constructor、toString、__proto__ 等继承属性。缺失、非法或读取失败回退 cat。写入失败时当前挂载保留临时皮肤；实际伴宠、选中按钮 data-active/aria-pressed 和名称共用同一读取，成功写入后清除临时值。名称使用文本节点，切换语言后按当前皮肤同步。临时值不跨卸载/重启，不自动重试。

## 验证

- verify_skin_preference.cjs 实现前缺文件失败，实现后通过注册键限定、缺失/非法值、读取拒绝、写入失败、非法写入拒绝及恢复。
- verify_mount 在旧候选复现保存失败后仍为 cat；新候选 Chromium/WebKit 通过 candy 临时选择、真实伴宠 data-skin、按钮选中态、语言重建与名称一致、原持久值不变、恢复选择 cat，以及持久值 constructor 时安全回退且继续刷新。
- verify_dispose 卸载重挂载/所有权检查与 verify_docking 既有左右停靠、尺寸、重置回归通过。Python 3.9.6 / 3.14.3 各 120 项通过。
- 已目视核验 WebKit 明暗皮肤选择截图，选中边框与当前名称一致。

候选 /tmp/quota-skin-candidate，截图 /tmp/quota-skin-components。仅为隔离合成浏览器证据，不构成原生、Windows 或发行验收；现用安装与真实偏好未动。艺术资源和剩余布局/伴宠代码继续保留归因与 LICENSE/NOTICE。下一步核查剩余 renderer 行为与来源替换边界。
