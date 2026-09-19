# 伴宠反馈与素材来源

2026-09-20。用户明确授权升级本插件伴宠，不修改 Codex 自定义宠物目录。

## 行为

额度使用既有 app-server 只读读数，按账户、窗口 key、重置时间去重。20% / 10% / 0% 是本地展示阈值，账户明确 blocked 同样触发等待。真实读数恢复才给恢复反馈。CTX 只绑定当前侧栏活动任务；70% 改变环，85% / 95% 给文字轻提醒。CTX 为最近请求输入 / 上报窗口，非精确实时剩余容量。数据采集超过120秒后将当前 CTX视为未知。healthThreadId 不随当前 UI 任务切换而变化，防止压缩记录串任务。

轻提示7秒，不启用系统通知，不调用模型。头部保持350ms并在14px范围内移动进入摸头；短点击保留固定展开；超过移动门槛进入拖动。关闭动作时保留单击与拖动。系统 reduced-motion 禁止动画，但保留静态状态和数值。摸头后回到当前额度/CTX对应的表情。

六款原有静态素材导出提升到320px、WebP质量90，覆盖48 CSS px × 最大2倍尺寸 × 3倍屏幕像素。薄荷黑猫额外使用统一384px高画布的六表情，其他角色仍使用姿态反馈，不声称有重绘表情。

## 复用选择

保留现有数据读取和 UI 宿主，没有新增渲染框架、模型请求或桌面进程。2026-09-20 核对官方文档 https://developers.openai.com/zh-Hans/docs/app-server：account/rateLimits/read、thread/tokenUsage/updated 与 contextCompaction 可用。此版本使用现有本地 JSONL 观测压缩，不假定新的 app-server 连接能订阅桌面已有任务。

## 图像生成来源

使用内置 imagegen，以本项目 assets/companions/web/cat.webp 为身份参考。原始输出归档为 assets/companions/cat-expressions-source.png，派生表情构建由 build_companion_expressions.py 可重复生成；未使用外部下载的角色素材。

完整生成提示：

> Use case: identity-preserve. Asset type: UI companion expression sprite sheet, NOT Codex pet atlas. Reference image is the exact identity: cute charcoal black plush cat with mint cyan inner ears, mint oval eyes, tiny mint nose and whiskers, peeking from the right edge with one rounded paw near lower right. Create ONE transparent-background PNG sprite sheet with exactly 3 columns and 2 rows, six equally-sized square cells, no text no borders no shadows no background. Every cell has same cat size and aligned head, ears and paw, same right-edge peeking silhouette. Crisp high definition soft 3D toy render, preserve mint black palette. Row1 left to right: neutral awake with oval eyes; happy with smiling curved closed eyes; worried with gently drooping eyebrows and round eyes. Row2 left to right: attentive reminder with one paw raised slightly; sleepy waiting with half closed eyes; being petted with both eyes peacefully closed and head slightly tilted. Cat occupies most of each cell, tiny 3% margin, identical framing in all six, no additional hands touching cat, no symbols, no extra limbs. Real alpha transparency required. 1536x1024 canvas preferred.

## 验收

- Python 3.9.6：146项测试全部通过，含提醒去重、身份缺失、账户恢复、任务隔离、表情选择和美术 alpha/尺寸检查。
- Swift 菜单栏 typecheck 通过。
- 独立审阅发现的 health 串任务、跨窗口重复提示、缺身份 blocked 重复提示均已修并增加回归。
- Chromium 左侧贴边真实指针曾被动画命中循环干扰；固定按钮命中区域、图片 pointer-events:none 后重新验证。
- 本机安装：build codex.20260920034708 / runtime 34；doctor exit 0，Service/Menu running、Display True、Injector ok、Quota live。只读检查确认真实桌面 renderer runtime 34、cat 表情模块已启用。
- Chromium 与 WebKit 隔离合成页面全项通过：真实 pointer 长按/拖动/固定、额度20/10/0/恢复、CTX86/96、切任务清提示、health身份隔离、过期快照、深浅主题、减少动画、48px与2倍尺寸、六表情实际图片源和固定几何。两引擎 JS/console 错误均为0。
- 可复跑：`NODE_PATH=<Playwright所在node_modules> node plugins/codex-quota-monitor/scripts/verify_companion_ui.cjs`；输出到 `/tmp/companion-qa/`。仅使用隔离域名与合成数据，不连接真实账户。
- 布局重绘曾覆盖即时表情，已修为仅必要时重建并恢复当前表情；六个唯一图片源切换回归通过。
- 合成额度不是实际消耗。未进行 Windows 真机和真实 Retina 多显示器验收。

合成验收截图：[浅色](assets/companion-feedback-light.png) · [深色双倍大小](assets/companion-feedback-dark.png)。
