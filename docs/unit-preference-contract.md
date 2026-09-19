# V2 单位偏好读取与写入

2026-09-20，接续 031cacc。以现有四种单位行为为接口，移除固定外部来源的 ensureDefaultUnit/unitMode，在 panel_controls.js 实现单位偏好。已有 localStorage 单位键保持兼容；不再读取或写入旧默认化标记。

## 规则

- 初始化不写单位偏好，也不覆盖已保存的 auto/raw/k/m；缺失、非法值、读取异常均只在显示时回退 auto。
- 只有显式选择有效单位才尝试写入 localStorage；非法选择不写入、不改变本次状态。
- 写入失败时保留本次挂载的临时选择，使显示和选中态继续一致，不能视为已持久保存。后续成功选择清除临时状态；此后外部修改可再次被读取。
- 重新挂载创建新的闭包，未保存的临时选择不跨实例。仍可能读到此前持久值。
- 复用原生 localStorage 和现有挂载/更新链路，不增加依赖、事件监听或轮询。没有建立通用偏好框架。

这只处理单位键的失败。保留的语言、布局、皮肤逻辑仍直接使用 localStorage；整个存储接口不可用时，不能承诺完整面板仍能挂载。

## 验证

`node tools/verify_unit_preference.cjs` 覆盖有效/缺失/非法值、初始化零写入、读异常、写异常保留临时选择、成功恢复、外部修改及实例隔离。测试先因缺少新函数失败，实现后通过。

增强的 verify_mount.cjs 在旧候选上复现已存 K 被重置 auto；新候选在 Chromium/WebKit 保留该偏好及空旧标记。通过模拟单位键 QuotaExceededError，核对点击 K 后显示和 aria-pressed 更新、持久 raw 不变；恢复写入后选择 auto 可持久化。同时回归语言、四种单位、键盘、挂载、样式和节点所有权。

Python 3.9.6 / 3.14.3 全套各 120 项通过；格式化探针及完整 Chromium/WebKit 明暗主题探针通过，已目视核对 WebKit 明暗截图。候选 /tmp/quota-preference-candidate；截图 /tmp/quota-preference-panel-evidence。LICENSE/NOTICE 继续保留。

现用安装和真实会话未修改。浏览器证据不等于原生窗口、Windows 或发行验收。正文 applyHud、其他偏好和布局仍含保留实现，完整来源替换未完成；下一步拆分正文更新的独立数据展示段。
