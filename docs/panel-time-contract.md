# V2 时间展示独立替换

2026-09-20，接续 `5b21dc0`。本批替换 shortDuration、durationPhrase、windowLabel、nearestResetText，接口名称保留以兼容现有视图。规格提取自固定旧版 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed` 的行为和 V2 账户视图调用，不复制旧函数体；新实现位于 `quota_monitor/panel_time.js`。

## 输入输出契约

- 简短时长以秒输入。有限非正值为 0m；不足一分钟为 <1m；分钟四舍五入，满 60 分钟后显示小时，低于 10 小时保留一位小数，其后整数；原始秒数满一天后显示四舍五入天数。保留 3570 秒显示 1.0h、35999 秒显示 10.0h 等既有边界。
- 双语时长以秒输入。有限非正值为“不足 1 分钟”或 under a minute；不足一小时显示四舍五入分钟，低于两天显示一位小数小时，其后显示一位小数天。保留正数不足 30 秒显示 0 分钟，以及 3599 秒显示 60 分钟的既有行为，本轮不混入产品规则调整。
- 配额周期以分钟输入。有效正数优先整天、再整小时、否则分钟；300/10080 分钟自然显示 5h/7d。未知周期用主/次窗口名称；中文固定“剩余”，英文 compact 使用 left，否则 remaining。
- 最近重置选所有有效窗口中最早的 Unix 秒，保留过去时间和 epoch 0，不更改输入顺序。按界面语言选择 zh-CN/en，使用本地时区显示月日时分。
- 明确收紧：时长仅接受有限 number，其他值显示 `-`；周期非法时回退主/次窗口；非数组窗口组或没有有效日期时不显示重置时间。日期必须在 0..8.64e12 秒，避免 Invalid Date。此边界与现有 V2 账户校验一致。

## 复用与来源

复用已有 uiLanguage、账户校验与视图调用；仅使用语言标准库，不增加依赖。核查日期 2026-09-20：[Number.isFinite](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number/isFinite) 明确不做数值强制转换；[Date.toLocaleString](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/toLocaleString) 提供本地化时间且具体排版可能随环境变化。测试因此不跨浏览器硬编码日期字符串。本次为现有辅助函数替换，无新增平台能力或库选型。

生成器在既有预算函数移除后，移除从 shortDuration 到 pressure 前的保留区段，再插入新模块；只处理已校验摘要的固定来源。已生成候选核对四个函数各一份，内容来自新模块。LICENSE/NOTICE 与冻结输入字节相同，候选仍为派生过渡产物。

## 验证与限制

- `node tools/verify_time_format.cjs`：实现缺失时先失败；实现后覆盖双语、舍入门槛、周期单位、严格输入、最早有效日期与输入不变。
- `verify_account_overview.cjs` 改为加载真实新时间模块，不再用时长/重置占位函数；Chromium/WebKit 的预算、失效清空与双语验证通过。
- 完整候选通过 Chromium/WebKit 的挂载与控件回归、明暗主题的任务切换/缺失/过期/单实例测试；WebKit 明暗完整面板已目视核对。
- `verify_mount.cjs` 增加真实 5h/7d 标签与最近重置日期的 DOM 断言，两引擎通过；配额卡片明暗截图已目视核对，证据 `/tmp/quota-time-cards-evidence`。
- Python 3.9.6 / 3.14.3 全套各 136 项通过。纯 JS 新检查另行运行，不把它们混入 Python 数量。
- 同口径具名函数定位从 59 降到 55，仅为残留定位计数，不是原创程度或法律结论。下一批仍需处理指标颜色/读数、文案、布局与模板等。
- 独立复核未发现逻辑错误或裁剪误删；按复核意见补充单独超日期上界拒绝断言，并确认合法上界非空。

候选 `/tmp/quota-time-candidate-v2`；完整面板截图 `/tmp/quota-time-panel-evidence`。只使用合成数据与隔离浏览器，未操作真实 Codex、真实认证/会话、现用安装或官方账户。普通启动跟随、真实 macOS、Windows 与发行验收仍未完成。
