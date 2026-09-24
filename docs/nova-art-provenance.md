# 星瞳诺瓦：V2 伴宠图像来源

2026-09-25，用户要求重新设计更可爱、看起来更智能的猫，并指出首次六宫格的左下角提醒帧多了一只爪子。本轮使用内置 imagegen 从文字生成新角色，没有把旧版 `cat.png` 或旧 WebP 作为输入。最终选用两张本轮原图：

| 原图 | 用途 | SHA-256 |
| --- | --- | --- |
| `assets/companions/sources/nova-atlas.png` | idle、happy、concerned、waiting、pet 五帧 | `e7690812503f47b6916f1fed22999843bd744ea7b6a79295899c282d77183e0e` |
| `assets/companions/sources/nova-notice.png` | 单爪提醒帧 | `ca99d508dd9b3787c12f6724ed6a4d8ab9f253bb40f79f20cc46626fb087ab59` |

两张原图分别为 1536×1024 和 1254×1254 的 RGBA PNG，背景像素 alpha 为 0。首次图的左下角仍有双爪；两次参考图编辑输出出现烘焙棋盘格或未移除第二爪，均未入库。单爪提醒图另以纯文字生成，已目视确认仅一只抬起的前爪。`tools/build_nova_art.py` 用 Pillow 11.3.0 按固定坐标导出 320×320 的 WebP；闲置帧也用作 `web/cat.webp`。复建命令：`python -m pip install Pillow==11.3.0 && python tools/build_nova_art.py`。Pillow 只用于资源构建，不进入运行依赖。运行时保留 `cat` 皮肤键，现有用户偏好不失效；界面名称改为“星瞳诺瓦 / Nova Cat”。

## 最终六宫格生成提示

> Use case: stylized-concept. Asset type: original production sprite atlas for a desktop quota-monitor companion. Create an entirely new character from this text only; do not use or imitate any existing project images, characters, logos, or mascots. Character: a tiny, irresistibly cute but visibly intelligent charcoal-black kitten named Nova, rounded plush head, soft triangular ears, warm expressive teal eyes with crisp highlights, tiny heart-shaped nose, short whiskers, one paw gripping a vertical screen edge. Give it subtle futuristic intelligence cues: a few delicate cyan circuit-like fur markings at the ear tips and a very small luminous star-shaped forehead marking, integrated as natural decorative markings rather than a device. No clothing, no collar, no robot body, no text. Style: polished high-resolution soft 3D toy illustration with clean silhouette, premium desktop UI quality, readable at 48 CSS pixels. Composition: ONE PNG atlas exactly 1536x1024, six equal 512x512 cells in a strict 3-column, 2-row grid, no visible borders. Same single kitten, camera, scale, lighting and right-edge peeking pose in every cell. Leave transparent margin at left and all cell boundaries; kitten occupies the right half to two thirds of each cell, with one paw at the right edge. Cells in reading order: idle curious and attentive; happy bright smile; concerned gentle worried brows; notice alert with one of its own paws slightly raised; waiting sleepy half-closed eyes; pet blissfully closed eyes, no touching hand. Real RGBA transparency: every pixel outside kitten silhouette must have alpha zero. No background, floor, shadows, glow halo, checkerboard, separators, symbols, exclamation marks, extra paws, extra limbs, duplicate faces, writing, watermarks, or second character. Keep six frames anatomically consistent and facial expressions distinct.

## 最终单爪提醒帧生成提示

> Use case: stylized-concept. Create a brand-new single production UI sprite PNG of an original smart kitten called Nova, with a GENUINELY TRANSPARENT RGBA background (alpha=0 outside silhouette). No input image or existing character reference. Square composition with one charcoal-black plush kitten peeking in from the right edge, huge gentle teal eyes, tiny pink nose, delicate cyan circuit-like ear-tip markings and a tiny cyan star-shaped fur marking on forehead. Alert friendly expression. EXACTLY ONE VISIBLE FRONT PAW TOTAL: one raised paw at lower left showing soft pink pads, naturally attached to shoulder; the right foreleg is entirely hidden behind the screen edge, with no paw or rounded bump on the right. Smooth straight torso silhouette at right. Polished soft 3D toy illustration, cute and visibly intelligent, readable at 48px. Empty pixels outside kitten must be alpha=0, not white, not checkerboard, not a studio backdrop, not a gradient. No glow haze, exclamation marks, symbols, text, additional paws, duplicate limbs, clothes, collar, robot parts, ground or shadow.

本记录只固定创作与导出链，不认定 AI 输出在各司法辖区的著作权范围，也不改变其他源码的 MIT 归因。
