# 账户窗口整组校验

2026-09-20，接续 63e14d9。共享 accountFreshness 在时间和状态有效之外，再要求 validAccountWindows 通过，使正文、标题和伴宠采用同一有效性边界。没有修改原始 payload，也不丢弃坏窗口后继续展示好窗口，以免不完整窗口集被误读为账户尚有余量。

windows 必须为数组，空数组允许（可表达未报告窗口）。每项必须为非数组对象，remaining 必须为 0–100 的有限 number。可选值 null/undefined 视为未提供：duration 如提供必须有限且大于零；paceDelta 必须有限，允许负数；exhaustInSec 必须有限非负；resetsAt/projectedExhaustAt 必须是 0 至 8.64e12 的有限 Unix 秒，保证可转换为 JavaScript Date。稀疏项、字符串数字、NaN/Infinity、越界比例及坏日期均使整组失效。

字段范围由保留 renderer 的实际消费点核对：remaining/duration/resetsAt/paceDelta/projectedExhaustAt/exhaustInSec 覆盖其窗口数值读取。使用标准 Array/Number 和普通循环，不引入 schema 库或依赖。窗口以外的 usage/resetCredits/budget 字段现在由账户投影按数值白名单保留，速度估算由本地样本摘要独立完成。现用安装与真实会话未修改。

## 验证

- verify_account_freshness.cjs 先在旧逻辑接受非法窗口组时失败，新实现通过正常/空窗口组、缺失/非数组、空项/稀疏数组、数值类型与范围、时间、预测及混合坏项测试，原时效测试保留。
- verify_mount.cjs 在旧候选上因 null 窗口触发 panel consumer unavailable；新候选 Chromium/WebKit 对全部异常组继续更新本地上下文 50%，账户正文无 meter、标题 unknown、伴宠 empty、底部不可用。后续有效 0%/100% 双窗口恢复显示。
- 完整 Chromium/WebKit 明暗主题、切换、缺失、过期、单实例回归通过，WebKit 明暗截图已目视核验；Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-windows-candidate；截图 /tmp/quota-windows-panel-evidence。仍携带原 LICENSE/NOTICE。原生窗口、真实账户、Windows 和发行验收未执行。下一步替换账户窗口正文构建及其时间/预测展示，继续保留来源归因。
