# 伴宠动作与互动核查及升级方案

核查日期：2026-09-25。范围是 V2 源码、仓库资源和合成测试；未操作现用安装、真实认证或会话。初查结论是互动入口基本存在，但六款可见表情不完整；后续已补齐六款各六帧及隔离浏览器换帧验收。真实宿主和发行包仍须分别验收。

| 场景 | 当前检测与反馈 | 核查结果 |
| --- | --- | --- |
| 悬停 | `pointerenter` 展开面板，`hello` 映射为开心 | 有；仅指针可触发，键盘聚焦只展开 |
| 点击 | 切换面板固定状态，尝试开心反馈 | 有；同一反应期间重复触发不会重播 |
| 长按头部 | 350 ms 后抚摸，松开抑制点击 | 有；本轮修复已进入抚摸状态后移动变拖动、拖动后计时器误触发抚摸 |
| 竖向拖动 | 更新位置，松开触发 `land` | 本轮补落地弹跳；仍没有专属表情图 |
| 额度/上下文提醒 | 阈值、恢复、压缩事件与提示文案 | 有状态机和开关；真实宿主、系统通知须独立验收 |
| 六款皮肤表情 | 六款各有 idle/happy/concerned/notice/waiting/pet 六帧 | 2026-09-25 后续轮次已补其余五款资源；来源及手部核查见[六款表情资源记录](companion-expression-art-2026-09-25.md) |

现有 `verify_companion_behavior.cjs` 覆盖纯函数阈值，`verify_companion_runtime.cjs` 覆盖反应投影。首次执行浏览器回归时普通 Node 环境找不到 `playwright`；后续通过 Codex 工作区自带的运行时加载，重新构建隔离候选，在 Chromium 与 WebKit 验证了真实鼠标悬停、长按抚摸、抚摸中移动、竖向拖动、落地弹跳、抑制误点、点击固定、键盘焦点、动作关闭与系统降低动效。指针取消另以合成 `pointercancel` 检查清理。未验证真实触控设备。真实 macOS UI、Windows 真机、发行包尚未在本轮验证。

本轮最终验证：隔离候选的 Chromium/WebKit `verify_mount.cjs` 通过，两个伴宠 Node 探针通过，使用独立临时虚拟环境及仓库锁定的 `websockets==15.0.1` 后 Python 全套 210 项通过。系统 Python 缺少该依赖时曾失败，属于测试环境问题；未改仓库依赖或现用安装。

续轮验证：合成账户与任务快照在 Chromium/WebKit 经发布链触发 `quota-watch`、`quota-low`、`quota-empty`、`quota-restored`、`ctx-high`、`ctx-critical` 和 `compacted` 提示。六款皮肤的独立表情画面及招呼/提醒动效已在浏览器检查，系统降低动效时关闭。这里证明的是合成数据到页面提示的链路；不等于系统通知或真实宿主数据已验收。

## 后续实施顺序

1. 已建立 Chromium/WebKit 合成浏览器动作矩阵；2026-09-26 补多指归属和取消拖动回滚。后续仍需真实触控设备、重复触发与更复杂的取消时序。检查实际 `data-expression`、位置、固定状态、计时器清理和无重复点击。发现失败时修共同入口。
2. 六款六表情已入库并通过 48 CSS px 与隔离 Chromium/WebKit 换帧检查；五款补充资源的生成和每格手部核查见独立记录。落地已有原生 CSS 弹跳反馈，仍需在真实 UI 检查可辨认度。
3. 合成会话与隔离候选中的提醒链路已验证。后续分别做真实 macOS UI、Windows 真机和发行验收；每层单独记录结果。

2026-09-26 续轮：多指归属与取消拖动的合成触控回归通过，正式包已随 [v2.0.10](https://github.com/ailble-abum/codex-quota-monitor/releases/tag/v2.0.10) 发布并校验。真实 Codex UI 的计算机操作接口不允许访问该应用，因此本轮未将其计为通过；Windows 与真实触控设备仍待验收。

## 复用选型

现有 Pointer Events、CSS、六帧 WebP 和项目状态机直接满足本轮修复，不增加运行时依赖。[MDN Pointer Events](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events) 文档说明捕获及取消语义；[MDN reduced motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion) 提供系统降低动效入口。两者是文档核对，项目内指针链路已按源码核对及纯函数测试验证，真实 macOS UI 未验证。

候选动画运行时 [Rive WASM](https://github.com/rive-app/rive-wasm)（仓库文档称 MIT）和 [dotLottie Web](https://github.com/LottieFiles/dotlottie-web)（包清单称 MIT）均可支持更丰富动画，但需要新素材格式、包体和嵌入兼容性验证；本轮未集成，也未做场景验证。只有在静态帧与原生 CSS 无法达到批准的动作规格时，才对候选做最小宿主探针。保留现有资源来源与 LICENSE/NOTICE；不以新素材或新目录推断独立著作权。

## 六表情素材小样与入库门槛

2026-09-25 使用内置 imagegen，以现有 candy WebP 为身份参考生成六格小样，要求每格仅一只可见的手、同一右侧探出姿势、六种表情、透明背景。第一张候选 SHA-256 `305c369cb5003a069f4fcf212c7f7046aa5218f46d9010e164d85e792a3c7121`：目视未见多手，但有悬浮符号，且文件为 RGB 黑底。第二次用内置编辑要求去除符号及背景，候选 SHA-256 `d7a341f7cd51f5edc45f6588092ce2f64700d303894d55af0742d78dffab451b`：仍为 RGB，棋盘格已烘焙进像素。该编辑图被弃用；第一张原图后来经过明确记录的去背和符号清理流程入库，见[六款表情资源记录](companion-expression-art-2026-09-25.md)。

素材先通过 `tools/validate_companion_atlas.py` 的 1536×1024 RGBA、六格非空、透明角、六帧互异检查，再由人逐格检查手/爪的数量和连接关系、脸部一致性、无悬浮符号、48 CSS px 可辨认度。自动脚本**不能**识别多手，人工复核不通过的图不导出。五款正式入库图集和六种导出帧均通过这一流程；原图、提示、处理参数与哈希见资源记录。
