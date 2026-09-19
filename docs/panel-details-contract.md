# V2 会话详情正文投影

2026-09-20，接续 32f35d7。本轮从固定来源 applyHud 中移除 data-metrics / data-explanation 的 HTML 拼接和清空逻辑，接入 panel_details.js 的 renderSessionDetails(body, selected)。上下文进度条、健康提示、账户、伴宠及正文容器初始化仍由保留实现负责。

## 行为与复用

复用已替换的 token/pct、既有翻译接口及视觉类名，使用标准 DOM createElement/textContent/createTextNode，不引入依赖。保留最近请求、会话累计卡片和四行说明的布局与文案。模型及推理强度只接受非空字符串，否则显示破折号；字符串内容一律作为文字，不能创建元素。

缓存占比仅在输入量为有限正数、缓存量为有限非负数时计算；大于输入量时显示上限 100%，不据此推断数据真实。零输入、负缓存及非数值显示破折号。先除再乘降低大数乘法溢出的可能。没有会话时清空两处内容，重复无变化更新通过 isEqualNode 比较后保留原子节点，避免更新循环持续重建同样的已挂载内容。

生成器仍验证固定外部文件摘要，限制替换在 selected 分支到 errorLabels 的明确边界；不是通用 JavaScript 重写器。保留文案/样式及其余 renderer 继续携带 LICENSE/NOTICE，本轮不意味着整份 renderer 独立来源审计完成。

## 验证

增强 verify_mount.cjs：旧候选将合成模型/推理字符串解析成 b/i 元素，先得到预期失败；新候选 Chromium/WebKit 均显示原始文字且无这些元素。探针覆盖 25% 正常比例、负缓存、零输入、超量缓存、零缓存、数字字符串拒绝、无记录清空及重复更新保留卡片节点。既有语言/单位切换、存储异常、控件与节点所有权回归仍通过。

Python 3.9.6 / 3.14.3 全套各 120 项通过。最终候选完整 Chromium/WebKit 明暗主题数值、切换、缺失、过期和单实例探针通过，WebKit 明暗截图已目视核验。候选 /tmp/quota-details-candidate-final，截图 /tmp/quota-details-panel-final，均为隔离合成浏览器验收材料。

未修改现用安装或真实会话；未执行原生窗口、Windows 或发行验收。下一步继续拆分上下文进度条的正文投影，保持快照/任务身份由 V2 bridge 负责。
