# V2 账户默认状态与底部文字

2026-09-20，接续 4a71c39。V2 当前 Python 投影没有账户 quota 生产者，故缺失 payload.quota 时改用 unavailable，而非 loading。保留真实传入 loading 的显示语义；本轮没有添加账户接口或模拟后台读取。

生成器移除旧 data-freshness 的 HTML 拼接和错误字典，接入 panel_account_status.js。使用标准 textContent 写入中英状态、套餐名、更新时间及错误说明；未知错误只按原始文字显示，非字符串错误/套餐字段忽略。已知 cli_missing/timeout/app_server/account_unavailable 使用对应双语标签。重复相同状态保留已有文字节点。

live/age 仍由调用方既有逻辑传入，本轮不重定义时间有效性。配额窗口和账户标题、伴宠使用的时效判断仍为保留实现，尚需统一校验，不能据此宣称整个账户通路已经安全或完整。复用现有 DOM 和标准库，不增加依赖。完整候选继续附带 LICENSE/NOTICE。

## 验证

- verify_account_status.cjs 在缺少实现时先失败，完成后 Chromium/WebKit 通过中英状态、9/10 秒文案切换、套餐大小写、已知/未知错误、HTML 字符作为文字、非字符串拒绝及不变节点身份。
- verify_mount.cjs 的账户缺失状态断言在旧候选失败，新候选通过；其他单位、语言、健康、详情、存储异常及节点所有权回归保持通过。
- 完整 Chromium/WebKit 明暗主题数值、任务切换、缺失、过期、单实例探针通过；已目视核验 WebKit 明暗截图，确认账户缺失不再显示读取中。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-status-candidate；截图 /tmp/quota-status-panel-evidence。仅为隔离合成浏览器验证，现用安装与真实会话未修改。真实账户、原生窗口、Windows 和发行验收未完成。下一步优先统一账户数据时效判断，再继续替换其余账户正文。
