# 独立替换剩余上游实现

2026-09-20；核查基线 `335a7dc`。用户已明确：暂不考虑官方插件接入，独立替换继承的上游代码，保留现有功能与 Codex 内嵌界面。该方向不解除真实宿主操作限制。

## 当前事实

`tools/build_panel_candidate.py` 仍读取旧仓库固定提交 `2705f32a6f080ee1bdbecdc5b43f5fe0f9045eed` 的四个 Python 文件及 LICENSE/NOTICE；摘要校验后提取常量、裁剪函数、插入 V2 模块。构建产物仍标记为 `derived-isolated-candidate`。分模块改写已完成许多数据/控件职责，但最终 renderer 仍依赖旧源码。

本次从旧仓库 Git 对象读取固定输入到临时目录，通过现有构建器的全部 SHA256 校验，仅在内存生成候选，未执行 renderer。候选 UTF-8 大小 384824 字节。用具名函数声明扫描并排除 V2 JS 已定义函数，检出 59 个残留名称（含通用局部函数）；该清单用于定位，不是 AST 审计、上游归属判定或原创证明。旧文件同时含本项目新增部分，需要分别追溯。

## 剩余模块与实施顺序

阶段 1 已完成：[时间展示独立替换](panel-time-contract.md)移除四个旧时间辅助定义；`panel_metrics.js` 按数据契约独立实现双语标签、额度/上下文色阶、余量与伴宠仪表读数，构建器明确删除对应旧定义。最终构建仍依赖冻结旧源码，下一步为阶段 2 布局交互。

| 阶段 | 当前残留定位 | 替换方式与验收 |
| --- | --- | --- |
| 1. 展示文案与指标辅助 | tr、shortDuration、durationPhrase、windowLabel、nearestResetText、quotaTone、accountTone、contextTone、contextMeterValue、remainingContext、toneLabel、gaugeReading/gaugeColor | 从已记录的数据契约与双语展示需求独立实现；覆盖未知值、零值、过期、边界及文案，不逐行改写旧函数 |
| 2. 布局交互 | hudMode/hudBase、presetWidth、applyStoredHudPosition、clampHud、installHudDrag、resizeGeometry、dockCandidate、applyDockPosition、undockHud、revealDock、scheduleDockHide 等 | 保留展开/折叠、拖动、缩放、停靠和偏好兼容；以指针操作、视口变化、卸载清理的合成验证驱动独立实现 |
| 3. 模板、样式与伴宠装配 | panelCSS、panelHeader、panelBodyTemplate 的旧模板提取；createRetainedMascot、mascotMarkup/mascotSvg、applyMascotSkin、companionStep/companionReact 等 | 按产品规格独立创建 DOM/CSS 与装配；保留用户功能与视觉方向，深浅主题 Chromium/WebKit 验证。先追溯自有插画与新增伴宠代码；不得把它们误删为上游贡献 |
| 4. 独立构建和发行清单 | applyHud、updateHudTitle、字符串裁剪链、外部四文件输入及旧候选状态 | 直接组合仓库内模块和来源明确的资源；在缺少旧仓库/冻结输入的临时环境构建并验证。更新安装清单和测试，逐项审查发行文件后才决定归因调整 |

已有 V2 日志读取、身份核对、快照时效、额度读取、页面桥及控件模块优先复用。布局使用浏览器标准 DOM/CSS/Pointer Events 能力；不为来源替换引入新的 UI 框架。具体模块开工时按 AGENTS.md 完成针对性复用核查，不预先声称某个库能完整覆盖。

每阶段按行为规格实现、测试、复核并提交。不要以更名、压缩、换语言、复制后改写或相似度阈值作为替换完成标准。既有旧候选只作为带归因的过渡与行为对照。

## 完成条件与边界

- 发布用构建不再读取旧仓库脚本或从旧源码提取 HTML/CSS/函数；资源来源逐项可追溯。
- 现有功能清单逐项对照；已开放的健康/历史/通知、消息级展示等缺口仍单独记录，不能因移除旧代码静默删减或改记通过。
- 单元、合成浏览器、真实 macOS、Windows 与发行分别验收。离线重写可以推进；真实 Codex 操作仍受交接安全限制。
- 内嵌额度条保持目标，不改为独立窗口。普通启动自动跟随与独立实现是两条验收线，前者未完成不阻止允许范围内的源码替换，但后者也不能证明前者可用。
- 仍包含旧实质性代码或资源的产物继续携带原许可与归因；不提前删除旧历史声明，不宣称法律审计通过。

本次仅完成最新依赖盘点和接续范围更新，没有产品行为改动。构建探针仅生成内存候选并由临时目录自动清理；没有修改现用安装，没有新原生 UI 验收。
