# V2 控件状态和语言同步

2026-09-20，接续 ec891b6。固定来源生成器移除外部 updateUnitButtons/updateHudLanguage，插入 panel_controls.js。本轮依据已有控件接口实现 DOM 状态投影，保留样式、翻译表、单位偏好、尺寸预设及皮肤处理。采用现有 DOM API，不增加依赖。

单位按钮同时更新 data-active 和 aria-pressed，每轮从当前单位偏好计算。更新范围限于传入面板；原有 updatePresetButtons/updateSkinButtons 的调用仍保留。语言同步覆盖面板 lang、单位组标签、auto/raw 文字、折叠标签、刷新/设置按钮标签及提示。修复中英切换后 auto 文字停留在首次挂载语言的问题。

初始化、applyHud 和折叠更新沿用已有调用点；没有新增监听器、定时器或全局状态。单位偏好非法值的 auto 回退仍由现有 unitMode 负责。缺失的可选控件跳过处理。

## 验证

- 增强 verify_mount.cjs，在旧候选上先复现“自动不变为 Auto”的失败；新候选 Chromium/WebKit 通过中英往返、四种单位唯一 aria-pressed/data-active、折叠/展开标签，并回归键盘、样式边界、挂载和节点所有权。
- 完整 Chromium/WebKit 明暗主题数值、切换、缺失、过期和单实例探针通过，已目视核对 WebKit 明暗主题。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。
- 生成后核对两个替换函数各仅一份，LICENSE/NOTICE 与固定来源一致。临时候选 /tmp/quota-controls-candidate；截图 /tmp/quota-controls-panel-evidence。

这不是整份展示链路的替换完成。applyHud、布局、偏好和伴宠相关实现仍有保留部分；继续归因，不宣称法律审计完成。只验证隔离合成浏览器，现用安装未修改，原生窗口、Windows 和发行验收未执行。下一步可独立处理单位偏好读取/初始化，再继续拆分 applyHud 的正文更新。
