# V2 语言偏好与设置事件

2026-09-20，接续 2c81cb1。生成器移除固定外部源的 uiLanguage 和正文重建时的语言读取/change 监听。panel_language.js 依据已有 auto/zh/en 接口实现偏好读取与解析；panel_mount.js 在面板根节点绑定一次 change 委托，重建正文不重复绑定。标准 DOM/Storage 即可满足本次替换，无新依赖。

偏好只接受 auto、zh、en。缺失、非法或读取失败按 auto 处理，不主动写入。自动模式优先宿主 documentElement.lang，其次 navigator.language，中文前缀使用中文，其余回退英文。用户写入失败时保留本次挂载的临时选择；后续刷新不被旧持久值覆盖。成功写入后清除临时值，外部偏好改动重新可见。临时值不跨实例。

语言选择器在每次语言控件同步时更新，即使 auto 与指定语言解析结果相同、正文未重建，也不会保留非法空选择。设置区展开状态继续沿用前一轮合约。

## 验证

- verify_language_preference.cjs 实现前缺文件失败，实现后通过有效/非法/缺失值、自动解析、读取拒绝、写入失败、恢复与实例隔离。
- verify_mount 在前一轮候选上复现存储写入失败后仍为 zh-CN，新候选 Chromium/WebKit 通过：失败后切换英文、刷新保留临时值、恢复写入 auto、非法值回退、只拒绝语言键读取时继续刷新、回到中文且无页面异常。
- 完整候选通过 verify_panel --bridge 双浏览器明暗主题、任务切换与过期场景，以及 verify_dispose 卸载、监听清理、重新挂载与所有权保护。既有单位偏好测试继续通过。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-language-candidate；截图 /tmp/quota-language-components 与 /tmp/quota-language-panel-evidence。仅为隔离合成浏览器证据，未进行原生、Windows 或发行验收，现用安装未动。此处仅保障语言偏好；其他保留设置仍有直接 Storage 调用，不能据此声称整个面板支持存储完全禁用。模板、其他事件、布局与伴宠实现继续保留来源归因和 LICENSE/NOTICE。下一步继续替换其他设置事件。
