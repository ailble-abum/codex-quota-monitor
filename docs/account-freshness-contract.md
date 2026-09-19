# 统一账户数据时效判断

2026-09-20，接续 3243ec8。panel_account_status.js 新增 accountFreshness，正文 applyHud、标题 updateHudTitle 和伴宠 gaugeReading 三处改用同一谓词。伴宠反馈沿用 gaugeReading，随之使用同一规则。

updatedAt 与当前 Unix 秒必须是有限 number，相减必须有限且非负；只有 status === live 且未舍入年龄小于 120 秒才有效。未来时间、缺失/null、数字字符串、NaN/Infinity 均无效。恰好 120 秒失效。显示年龄对合法非负差值向下取整，不再把未来时间钳为零，也不会因 null < 120 的类型转换认定有效。

复用现有 120 秒产品期限和标准 Number/Math/Date，不增加依赖。每个调用使用当前墙钟，未声称在整轮渲染内锁定同一个时刻，也没有改变 V2 数据桥基于单调时钟的快照租约。账户时间校验不等于 windows 等完整载荷结构校验，缺失或异常窗口结构仍是后续边界；真实账户生产者仍未接通。

## 验证

- verify_account_freshness.cjs 先因缺少新函数失败，实现后通过缺失、非法/非有限、未来、精确 120 秒边界、合法非 live 状态与非法当前时间测试。
- verify_mount.cjs 固定合成浏览器时钟，将同一数据发布到完整候选；旧候选在未来时间仍生成账户进度条处失败，新候选 Chromium/WebKit 同时通过正文进度条、根标题状态、伴宠 live/empty 和底部状态的一致性断言。覆盖当前、过期、未来、缺失和字符串时间，并恢复测试时钟。
- 生成候选仅剩三处 accountFreshness 调用及其唯一 updatedAt 读取；原三套时效表达式已移除。
- 完整 Chromium/WebKit 明暗主题探针通过，已目视核验 WebKit 明暗截图；Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-freshness-candidate；截图 /tmp/quota-freshness-panel-evidence。原 LICENSE/NOTICE 保留。现用安装和真实会话未修改；原生窗口、真实账户、Windows 和发行验收未完成。下一步处理账户窗口数据的结构与数值边界，再替换其余账户正文。
