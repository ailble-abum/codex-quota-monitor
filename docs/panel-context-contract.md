# V2 上下文正文投影

2026-09-20，接续 6921f67。生成器将旧 applyHud 的 selected 正文分支整体替换为 renderSessionDetails 与 renderContext 两个调用。新 panel_context.js 负责本地会话标签、百分比、进度条和 Token 数值；会话选择、快照有效性、根节点缓存和伴宠更新仍沿用已有链路。

使用标准 DOM API 构建正文，复用既有 token/pct、翻译接口及视觉类名，不增加依赖。有限百分比钳制到 0–100；70 以下 safe、70 至 85 以下 watch、85 起 low。缺失或非有限数值显示 unknown/占用暂不可用，不生成进度条。无会话显示无记录。进度条保留 role=meter、双语 aria-label、0/100 范围和当前值。正常内容保持原有布局及 Token 单位切换。

内容以文字节点展示；有实际变化才更新正文子节点。重复快照不替换同样的已挂载节点。样式仍为归因资产；其他位置使用的 contextTone/contextMeterValue 以及账户、健康提示、伴宠、布局实现本轮未替换。完整 renderer 来源替换及法律审计未完成。

## 验证

- 新 verify_context.cjs 在 Chromium/WebKit 直接运行 V2 展示代码，覆盖负数、0、69.9、70、85、超 100、null、数字字符串、NaN、Infinity，中英标签、重复更新节点身份与无记录清空。先在新实现文件不存在时失败，完成后通过。
- 完整候选通过既有挂载/单位/语言/存储异常/详情/节点所有权回归，以及 Chromium/WebKit 明暗主题数值、任务切换、缺失、过期、单实例探针。
- Python 3.9.6 / 3.14.3 全套各 120 项通过；WebKit 明暗主题截图已目视核验。
- 临时候选 /tmp/quota-context-candidate，截图 /tmp/quota-context-panel-evidence。生成器仍校验固定输入摘要并携带原 LICENSE/NOTICE。

仅为隔离合成浏览器证据；现用安装及真实会话未修改。未执行原生窗口、Windows 或发行验收。下一步可继续拆分本地健康提示正文及其输入边界。
