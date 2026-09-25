# 伴宠动作与互动核查及升级方案

核查日期：2026-09-25。范围是 V2 源码、仓库资源和合成测试；未操作现用安装、真实认证或会话。结论：**互动入口基本存在，但可见动作并不完整，不能称为六款伴宠都有完整动作。**

| 场景 | 当前检测与反馈 | 核查结果 |
| --- | --- | --- |
| 悬停 | `pointerenter` 展开面板，`hello` 映射为开心 | 有；仅指针可触发，键盘聚焦只展开 |
| 点击 | 切换面板固定状态，尝试开心反馈 | 有；同一反应期间重复触发不会重播 |
| 长按头部 | 350 ms 后抚摸，松开抑制点击 | 有；本轮修复已进入抚摸状态后移动变拖动、拖动后计时器误触发抚摸 |
| 竖向拖动 | 更新位置，松开触发 `land` | 拖动有；`land` 没有专属表情映射，视觉通常回到心情帧 |
| 额度/上下文提醒 | 阈值、恢复、压缩事件与提示文案 | 有状态机和开关；真实宿主、系统通知须独立验收 |
| 六款皮肤表情 | 猫有 idle/happy/concerned/notice/waiting/pet 六帧 | 其余五款各一张静态图，仅通过 CSS 滤镜/位移区分，缺少对应表情资源 |

现有 `verify_companion_behavior.cjs` 覆盖纯函数阈值，`verify_companion_runtime.cjs` 覆盖反应投影与监听器存在。监听器存在性不能证明真实指针动作；本轮先补抚摸与拖动互斥回归。`node tools/verify_companion_behavior.cjs`、`node tools/verify_companion_runtime.cjs`、`python3 -m unittest tests.test_panel_build` 通过。`node tools/verify_mount.cjs` 因本机缺少 `playwright` 模块未启动，不能记为合成浏览器通过；真实 macOS UI、Windows 真机、发行包尚未在本轮验证。

## 后续实施顺序

1. 为悬停、点击、长按、拖动、取消、键盘焦点、动作关闭建立合成浏览器动作矩阵。检查实际 `data-expression`、位置、固定状态、计时器清理和无重复点击。发现失败时修共同入口。
2. 确定六款皮肤的动作规格。先决定其他五款是否需要真正的独立表情；若需要，按每款状态制作有来源记录的资源并做 48 CSS px 可辨认度检查。不要把滤镜变化算作独立动作。为落地定义可见反馈或从动作清单移除该名称。
3. 用合成会话和独立临时目录检查额度、上下文及压缩事件到伴宠提示的完整链路。再分别做真实 macOS UI、Windows 真机和发行验收；每层单独记录结果。

## 复用选型

现有 Pointer Events、CSS、六帧 WebP 和项目状态机直接满足本轮修复，不增加运行时依赖。[MDN Pointer Events](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events) 文档说明捕获及取消语义；[MDN reduced motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion) 提供系统降低动效入口。两者是文档核对，项目内指针链路已按源码核对及纯函数测试验证，真实 macOS UI 未验证。

候选动画运行时 [Rive WASM](https://github.com/rive-app/rive-wasm)（仓库文档称 MIT）和 [dotLottie Web](https://github.com/LottieFiles/dotlottie-web)（包清单称 MIT）均可支持更丰富动画，但需要新素材格式、包体和嵌入兼容性验证；本轮未集成，也未做场景验证。只有在静态帧与原生 CSS 无法达到批准的动作规格时，才对候选做最小宿主探针。保留现有资源来源与 LICENSE/NOTICE；不以新素材或新目录推断独立著作权。
