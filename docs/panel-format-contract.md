# V2 数值显示替换

2026-09-20，接续 `38446be`。固定来源生成器移除外部 `n`、`token`、`pct` 函数，注入本仓库 `quota_monitor/panel_format.js`；偏好初始化和单位读取暂时保留。生成器仍校验全部外部输入摘要，候选继续携带原 LICENSE/NOTICE。

## 行为与复用

依据既有显示契约实现，使用 JavaScript 标准库 Intl.NumberFormat / Number.toFixed，不增加格式化依赖。原始值采用浏览器默认数字分组和精度；自动单位按未舍入绝对值在 1000、1000000 切换 K/M，整数最多零位小数，带单位最多一位；K 在原值 100000、1000000 门槛分别使用固定一位、零位小数，门槛以下固定两位。M 在 10000000 以下固定两位，其余一位。M 和百分比继续使用小数点、不分组；百分比固定一位，不额外乘 100。

输入必须为有限 number；null、undefined、NaN、正负无穷、数字字符串、布尔、对象、数组显示 `-`。这是明确的收紧：旧 token 会接受数字字符串，旧百分比会显示 NaN/Infinity。V2 数值投影不依赖字符串强制转换。有限负数保留符号，显示层不承担业务范围校验。

复用范围是语言标准库及项目已有单位偏好接口；来源和剩余工作见 [来源审计](source-audit.md) 与 [样式边界](panel-css-contract.md)。没有将短函数替换等同于整份 renderer 独立实现。保留的 applyHud、布局、偏好、伴宠展示及视觉资产仍需后续审计和替换。

## 验证

- `node tools/verify_format.cjs`：en-US、de-DE、zh-CN 三种地区，单位门槛、正负号、舍入、固定精度和所有非数值输入。测试在实现文件缺失时先失败，实现后通过。
- `tools/verify_mount.cjs`：Chromium/WebKit 中点击 K/M/auto/raw，检查实际上下文显示，同时回归宿主样式、键盘、控件、单实例和他人节点保护。
- Python 3.9.6 / 3.14.3 全套各 120 项通过。
- 完整 Chromium/WebKit 明暗主题的数值、任务切换、缺失、过期和单实例探针通过；已目视核对 WebKit 明暗截图。
- 生成候选已核对无旧 n 且 token/pct 各仅一份，LICENSE/NOTICE 与固定输入字节一致。

临时候选 `/tmp/quota-format-candidate`，截图 `/tmp/quota-format-panel-evidence`。本轮仅合成浏览器验收，没有真实原生窗口、真实账户、Windows 或发行验收；现用安装未修改。
