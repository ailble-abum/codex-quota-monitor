# 独立替换剩余上游实现

2026-09-20；核查基线 `335a7dc`。用户已明确：暂不考虑官方插件接入，独立替换继承的上游代码，保留现有功能与 Codex 内嵌界面。该方向不解除真实宿主操作限制。

## 当前事实

旧的 `tools/build_panel_candidate.py` 仍保留为带归因的行为对照。发布路线新增 `tools/build_panel.py`：它从仓库内 V2 shell、模块和 `assets/companions` 视觉资源直接装配 renderer，不再读取旧仓库的四个 Python 文件，产物标记为 `independent-v2-candidate`。构建继续携带原 LICENSE/NOTICE；视觉资源的逐项来源复核尚未完成。

本次从旧仓库 Git 对象读取固定输入到临时目录，通过现有构建器的全部 SHA256 校验，仅在内存生成候选，未执行 renderer。候选 UTF-8 大小 384824 字节。用具名函数声明扫描并排除 V2 JS 已定义函数，检出 59 个残留名称（含通用局部函数）；该清单用于定位，不是 AST 审计、上游归属判定或原创证明。旧文件同时含本项目新增部分，需要分别追溯。

## 剩余模块与实施顺序

阶段 1 已完成：[时间展示独立替换](panel-time-contract.md)移除四个旧时间辅助定义；`panel_metrics.js` 按数据契约独立实现双语标签、额度/上下文色阶、余量与伴宠仪表读数，构建器明确删除对应旧定义。最终构建仍依赖冻结旧源码，下一步为阶段 2 布局交互。

阶段 2 的源码替换已完成：`panel_geometry.js` 独立实现展开/折叠尺寸、视口限制、伴宠拖动阈值、左右停靠候选、预设宽度、缩放与提示位置；`panel_layout_runtime.js` 独立实现停靠显隐、位置应用、解除停靠、指针/键盘缩放、折叠锚点及四项全局监听的注册/卸载。构建器已删除对应旧定义。Node 探针覆盖几何边界、视口约束、停靠展开/解除、预设和 timer 清理；Python 3.9 候选回归通过。本机 Playwright 安装不完整，Chromium headless shell 与 WebKit 可执行文件均缺失，因此本轮不将源码替换记为 Chromium/WebKit 完整停靠验收；浏览器验收须在运行时可用后补跑。

阶段 3 已开始：`panel_templates.js` 以 V2 控件合约独立建立面板静态外壳和正文模板，包含标题、刷新/设置/折叠控件、单位组、账户/上下文/健康/会话挂载点、布局/语言/伴宠设置、交接、位置重置与诊断挂载点。配额通知在新模板中明确禁用并标注尚未接通。`panel_styles.js` 只使用原生 CSS 定义面板/伴宠 ID 作用域、深浅主题系统色、折叠/缩放/停靠可见状态、焦点边框与 reduced-motion，不包含宿主侧栏或消息选择器。构建器不再从旧 `ensureHud`/`applyHud` 提取 HTML，也不再从 `ensureStyle` 提取 CSS。伴宠装配仍保留来源归因，待后续替换。

`panel_companion_view.js` 已独立实现伴宠手动/自动缩放、素材选择与缺失回退、双语皮肤按钮、皮肤应用、配额仪表和上下文环装配。构建器已删除对应旧函数。现有 `MASCOT_ART`/`MASCOT_EXPRESSIONS` 常量仍作为已归档的项目插画与表情素材使用，本轮不改记其来源或权属结论。伴宠 DOM 事件与反应/提醒状态机仍待替换。

`panel_companion_behavior.js` 已独立实现表情选择、任务健康数据归属、点击/抚摸/拖动手势分类，以及配额阈值、恢复、上下文高压和压缩事件的去重/重置状态。构建器不再读取或注入冻结 `COMPANION_FEEDBACK_JS`；该外部文件仍在输入摘要中，待阶段 4 移除整个冻结输入契约。伴宠 DOM 事件装配及反应展示仍待替换。

`panel_companion_runtime.js` 已独立实现伴宠 DOM 创建、焦点/指针/点击事件、竖向拖动、抚摸与短时表情、提醒偏好过滤和文本提示挂载。反应、抚摸和提示计时器继续暴露给 `disposePanel` 同步清理；提示样式由已独立的 CSS 负责，不写行内 `cssText`。配额提醒优先附加可用时长估算，缺少数据时明示不可用。至此阶段 3 的模板、CSS、伴宠视图/行为/DOM 装配源码替换完成；Chromium/WebKit 视觉与真实指针验收仍受本机 Playwright 运行时缺失限制，不记为已通过。

阶段 4 已开始：`panel_shell.js` 独立拥有运行时常量、双语基础词典、皮肤元数据、快照投影入口、折叠标题及时长估算展示和提示定位。新构建器只按固定顺序拼装仓库模块，把仓库内 WebP 资源编码为 data URI；Python 3.9 全套 146 项、非浏览器 Node 探针和最终产物语法检查通过。Playwright 仍缺失，因此不能把本轮记录为完整挂载、视觉或真实指针验收；旧候选构建器也暂不删除，供行为对照使用。

产品展示口径：完整面板继续显示每个配额窗口的百分比和进度条；折叠条与伴宠悬浮说明显示 `windowBudgetText` 给出的可用时长估算。若缺少速率数据则明示“时间估算暂不可用”，不回退成配额百分比；CTX 没有可靠时长模型，继续显示已用百分比。

| 阶段 | 当前残留定位 | 替换方式与验收 |
| --- | --- | --- |
| 1. 展示文案与指标辅助 | tr、shortDuration、durationPhrase、windowLabel、nearestResetText、quotaTone、accountTone、contextTone、contextMeterValue、remainingContext、toneLabel、gaugeReading/gaugeColor | 从已记录的数据契约与双语展示需求独立实现；覆盖未知值、零值、过期、边界及文案，不逐行改写旧函数 |
| 2. 布局交互 | hudMode/hudBase、presetWidth、applyStoredHudPosition、clampHud、installHudDrag、resizeGeometry、dockCandidate、applyDockPosition、undockHud、revealDock、scheduleDockHide 等 | 保留展开/折叠、拖动、缩放、停靠和偏好兼容；以指针操作、视口变化、卸载清理的合成验证驱动独立实现 |
| 3. 模板、样式与伴宠装配 | panelCSS、panelHeader、panelBodyTemplate 的旧模板提取；createRetainedMascot、mascotMarkup/mascotSvg、applyMascotSkin、companionStep/companionReact 等 | 按产品规格独立创建 DOM/CSS 与装配；保留用户功能与视觉方向，深浅主题 Chromium/WebKit 验证。先追溯自有插画与新增伴宠代码；不得把它们误删为上游贡献 |
| 4. 独立构建和发行清单 | 发行清单、资源来源复核、浏览器/原生验收未完成 | 已移除新构建对旧仓库脚本和字符串裁剪链的依赖，并内建现有 WebP 资源；下一步更新安装清单，逐项审查发行文件后才决定归因调整 |

已有 V2 日志读取、身份核对、快照时效、额度读取、页面桥及控件模块优先复用。布局使用浏览器标准 DOM/CSS/Pointer Events 能力；不为来源替换引入新的 UI 框架。具体模块开工时按 AGENTS.md 完成针对性复用核查，不预先声称某个库能完整覆盖。

每阶段按行为规格实现、测试、复核并提交。不要以更名、压缩、换语言、复制后改写或相似度阈值作为替换完成标准。既有旧候选只作为带归因的过渡与行为对照。

## 完成条件与边界

- 发布用构建不再读取旧仓库脚本或从旧源码提取 HTML/CSS/函数；资源来源逐项可追溯。
- 现有功能清单逐项对照；已开放的健康/历史/通知、消息级展示等缺口仍单独记录，不能因移除旧代码静默删减或改记通过。
- 单元、合成浏览器、真实 macOS、Windows 与发行分别验收。离线重写可以推进；真实 Codex 操作仍受交接安全限制。
- 内嵌额度条保持目标，不改为独立窗口。普通启动自动跟随与独立实现是两条验收线；`host_app` opt-in 跟随代码已加入，但真实 Codex 退出重开和下次启动恢复仍未通过，不能把合成命令测试记为原生验收。
- 仍包含旧实质性代码或资源的产物继续携带原许可与归因；不提前删除旧历史声明，不宣称法律审计通过。

本阶段新增独立 shell 与直接模块构建路径，没有修改现用安装，也没有新原生 UI 验收。折叠条继续显示配额可用时长估算，完整面板继续显示百分比。

## 后续验证记录（2026-09-23）

当前 Playwright 运行时已可用：V2 独立候选已完成 Chromium/WebKit 明暗主题的挂载隔离回归，以及 Chromium 的真实 CDP 运行循环回归；这只提升了行为证据，不改变视觉资源来源和归因仍待复核的结论。`beta-20260923-r20` 的安装目录审查通过，稳定版安装和真实宿主退出重开仍未切换或宣称通过。
