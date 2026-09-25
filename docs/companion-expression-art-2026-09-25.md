# 六款伴宠六表情资源记录（2026-09-25）

本轮使用内置 imagegen，以仓库既有五款 WebP 为各自身份参考。用户明确允许本地 Python 图片处理。逐格目视检查每款每帧只有一只可见手或爪；自动透明度测试不能代替手部检查。五款最终原图和处理结果如下，均为仓库文件：

| 皮肤 | 最终图集 | 输入/处理 | 最终 SHA-256 |
| --- | --- | --- | --- |
| Candy | `assets/companions/sources/candy-atlas.png` | `candy-generated-rgb.png` 黑底去背、清除两个悬浮符号 | `ad492a4a7806c8f9c6db8bda10f3de076e32f3e7512aafc0c14844a0e0a62580` |
| Corgi | `assets/companions/sources/corgi-atlas.png` | imagegen 真 RGBA，无需去背 | `d355c1f77d12c17ccbaf327270657e4480822852e5a900b70fa215678b7be2ea` |
| Frost | `assets/companions/sources/frost-atlas.png` | `frost-generated-rgb.png` 黑底去背，低阈值保留黑外套，补小面积衣服内部孔洞 | `7a8019e26cd224384cd9e33403eb6b0cfcd551615086e9b113f7f69f9fb5d409` |
| Mint | `assets/companions/sources/mint-atlas.png` | `mint-generated-rgb.png` 黑底去背 | `dbb4b3d1827caeab38ecd112726b35691bcb05a21ff7a039c0c0c515381d0cef` |
| Tea | `assets/companions/sources/tea-atlas.png` | `tea-generated-rgb.png` 黑底去背 | `e0281c90f2f823fc683cd834e4035b2cff9a8e079471afaf6319faa37878bb4d` |

所有最终图集经 `tools/validate_companion_atlas.py` 校验为 1536×1024 RGBA、六帧非空互异且左侧背景透明；`tools/build_companion_expressions.py` 导出各款六张 320×320 WebP。黑底源图 SHA-256 依次为 Candy `305c369cb5003a069f4fcf212c7f7046aa5218f46d9010e164d85e792a3c7121`、Frost `155aef690b0103ca2f8768805957494084f8900e62c0f5e5afed7f62e87feb38`、Mint `7ef58bc66f27be10c1fdfa8b2a28e2c3f89690d0909f7ca20c93f6164a8504b6`、Tea `8d011485f6a5c18b3acffc7d8c0ef9e3721c4617dd6e2336997d40e49d6150bb`。

复建命令使用 Pillow 11.3.0：

```sh
python tools/prepare_companion_atlas.py assets/companions/sources/candy-generated-rgb.png assets/companions/sources/candy-atlas.png --clear 3:450:45:511:155 --clear 5:0:245:100:345
python tools/prepare_companion_atlas.py assets/companions/sources/frost-generated-rgb.png assets/companions/sources/frost-atlas.png --threshold 5 --alpha-range 8 --fill-dark-holes 220:270:511:511
python tools/prepare_companion_atlas.py assets/companions/sources/mint-generated-rgb.png assets/companions/sources/mint-atlas.png
python tools/prepare_companion_atlas.py assets/companions/sources/tea-generated-rgb.png assets/companions/sources/tea-atlas.png
python tools/build_companion_expressions.py
```

曾产生的 RGB 棋盘格候选全部弃用；没有把烘焙棋盘格视为透明。Frost 另一次透明尝试仍为棋盘格，也弃用。图像生成记录与源图 SHA 说明工程链路，不是权属鉴定；发行继续携带现有 LICENSE/NOTICE。

## Candy

- 身份参考：`assets/companions/web/candy.webp`；原始生成文件：`assets/companions/sources/candy-generated-rgb.png`。
- 最终提示词：

> Use case: stylized-concept. Edit target: supplied candy girl identity reference. Create a six-cell transparent sprite atlas, 3 columns x 2 rows, same single brown-haired girl with two buns, yellow star hairclip and pink hoodie, peeking from the right edge in every cell. Expressions in reading order: idle, happy, concerned, notice, waiting, pet. Anatomy invariant for EVERY cell: EXACTLY ONE visible hand total, on the same side gripping the right edge; other arm and hand entirely hidden behind the edge. No raised second hand even in notice. Keep body silhouette and pose the same, vary only facial expression, eyes and brows. No extra hands, fingers, arms, paws, limbs, duplicate heads or people. Genuine alpha transparency outside silhouette, no checkerboard/background/border/text. Consistent scale and alignment; readable at 48 CSS pixels.

## Corgi

- 参考原皮肤：`/Users/ailble/Desktop/季二六软件项目/assets/companions/web/corgi.webp`
- imagegen 原始输出：`/Users/ailble/.codex/generated_images/01a0d909-1e46-7443-aef0-b274e6602fde/exec-e75a5b92-e8b8-4a76-8485-e9a89949846c.png`
- `/tmp` 候选副本：`/tmp/companion-atlas-candidates-2026-09-25/corgi-atlas-raw.png`
- 48px 接触图（144x96，每格严格 48x48）：`/tmp/companion-atlas-candidates-2026-09-25/corgi-atlas-contact-48px.png`
- 放大预览（Nearest 4x，仅供目视）：`/tmp/companion-atlas-candidates-2026-09-25/corgi-atlas-contact-48px-preview.png`
- 验收：1536x1024 PNG，RGBA；alpha 范围 0–254，alpha=0 像素 817,784；逐格目视只有一只白色前爪，没有第二爪或多余肢体。48px 下脸部与六种表情可辨。建议候选通过。
- 提示词：

> Use case: stylized-concept. Asset type: six-frame transparent desktop companion sprite atlas.
> Input image: Image 1 is the identity and style reference; preserve this exact corgi character design.
> Primary request: create one PNG atlas exactly 1536x1024 with six equal 512x512 cells in a strict 3-column, 2-row grid, read left-to-right then top-to-bottom. Each cell shows the same orange-and-white fluffy corgi peeking from the right edge, matching Image 1: huge upright ears with pink interiors, round brown eyes, black nose, white muzzle/chest, small pink tongue, warm soft 3D toy illustration.
> Composition: keep the same right-edge peeking pose, character scale, camera, crop and lighting in every cell. Leave ample empty transparent space on the left of every cell. Show exactly ONE visible front paw total per cell, gripping the right edge in the same position; hide all other paws and limbs completely.
> Expressions, in reading order: idle curious and attentive; happy bright smile; concerned gentle worried brows; notice alert wide eyes; waiting sleepy half-closed eyes; pet blissfully closed eyes. Change only face expression between cells; do not animate or raise the paw.
> Background: genuinely transparent RGBA, alpha exactly zero everywhere outside the character silhouette. No background color, no floor, no cast shadow, no glow, no checkerboard, no separators or borders.
> Constraints: strict six-cell grid; one identical corgi per cell; exactly one visible paw in every cell. No extra paws, hands, arms, duplicated limbs, duplicated faces, additional characters, symbols, punctuation marks, text, watermark, collar, clothing, props, or scene.

## Frost 黑底版

- 参考原皮肤：`/Users/ailble/Desktop/季二六软件项目/assets/companions/web/frost.webp`
- imagegen 原始输出：`/Users/ailble/.codex/generated_images/01a0d909-1e46-7443-aef0-b274e6602fde/exec-84ac81ed-681d-4e74-8b6a-f50fa769a5c3.png`
- 候选副本：`/tmp/companion-atlas-candidates-2026-09-25/frost-atlas-black.png`
- 验收：1536x1024 PNG，RGB（无 alpha）；四角采样纯黑，底边个别近黑像素 `(1,1,0)`，非棋盘格；逐格目视每格一只黑手套手，没有第二只手或重复肢体。
- 提示词：

> Use case: stylized-concept. Asset type: six-frame desktop companion sprite atlas for later local background removal.
> Input image: Image 1 is the character identity and style reference; preserve the same character.
> Create exactly one 1536x1024 PNG atlas, six equal 512x512 cells in a strict 3-column by 2-row grid, read left-to-right then top-to-bottom. The same pale young anime person peeks from the right edge in every cell: tousled silver-lavender hair, blue eyes, black high-neck jacket with small dark hardware, polished soft 3D anime-toy rendering.
> Keep character pose, scale, crop, camera, lighting and costume identical in all six cells. Leave empty space on the left. Exactly ONE visible hand per cell: the same single black-gloved hand gripping the right edge in the same position; all other hands and limbs hidden.
> Only change the facial expression in reading order: idle curious and attentive; happy warm smile; concerned gentle worried brows; notice alert wide eyes; waiting sleepy half-closed eyes; pet blissfully closed eyes.
> Background MUST be a perfectly flat, uniform, pure solid black RGB #000000 across the entire canvas, including gaps and all cell edges. No transparency or alpha channel, no gradients, no texture, no shadows, no glow, and absolutely no checkerboard pattern.
> Strictly six cells. No grid lines, dividers, borders, extra hands, extra arms, extra fingers, duplicated limbs or faces, additional characters, symbols, punctuation, text, watermark, new accessories or props.

## Mint 黑底版

- 参考原皮肤：`/Users/ailble/Desktop/季二六软件项目/assets/companions/web/mint.webp`
- imagegen 原始输出：`/Users/ailble/.codex/generated_images/01a0d909-1e46-7443-aef0-b274e6602fde/exec-26b876f4-f5ad-416a-ad47-c9e97a03f968.png`
- 候选副本：`/tmp/companion-atlas-candidates-2026-09-25/mint-atlas-black.png`
- 验收：1536x1024 PNG，RGB（无 alpha）；四角采样纯黑，底边个别近黑像素 `(1,1,0)`，非棋盘格；逐格目视每格一只裸手和绿袖口，没有第二只手或重复肢体。
- 提示词：

> Use case: stylized-concept. Asset type: six-frame desktop companion sprite atlas for later local background removal.
> Input image: Image 1 is the character identity and style reference; preserve the same character.
> Create exactly one 1536x1024 PNG atlas, six equal 512x512 cells in a strict 3-column by 2-row grid, read left-to-right then top-to-bottom. The same cheerful youthful anime boy peeks from the right edge in every cell: tousled dark brown hair, warm brown eyes, fair peach skin, mint-green hoodie, polished soft 3D anime-toy rendering.
> Keep character pose, scale, crop, camera, lighting and costume identical in all six cells. Leave empty space on the left. Exactly ONE visible hand per cell: the same single bare hand with green cuff gripping the right edge in the same position; all other hands and limbs hidden.
> Only change the facial expression in reading order: idle curious and attentive; happy bright smile; concerned gentle worried brows; notice alert wide eyes; waiting sleepy half-closed eyes; pet blissfully closed eyes.
> Background MUST be a perfectly flat, uniform, pure solid black RGB #000000 across the entire canvas, including gaps and all cell edges. No transparency or alpha channel, no gradients, no texture, no shadows, no glow, and absolutely no checkerboard pattern.
> Strictly six cells. No grid lines, dividers, borders, extra hands, extra arms, extra fingers, duplicated limbs or faces, additional characters, symbols, punctuation, text, watermark, new accessories or props.

## Tea 黑底版

- 参考原皮肤：`/Users/ailble/Desktop/季二六软件项目/assets/companions/web/tea.webp`
- imagegen 原始输出：`/Users/ailble/.codex/generated_images/01a0d909-1e46-7443-aef0-b274e6602fde/exec-6ec778da-1272-4881-adc1-2c9947e4d033.png`
- 候选副本：`/tmp/companion-atlas-candidates-2026-09-25/tea-atlas-black.png`
- 验收：1536x1024 PNG，RGB（无 alpha）；四角采样纯黑，底边个别近黑像素 `(0,1,0)`，非棋盘格；逐格目视每格一只裸手，没有第二只手或重复肢体。
- 提示词：

> Use case: stylized-concept. Asset type: six-frame desktop companion sprite atlas for later local background removal.
> Input image: Image 1 is the character identity and style reference; preserve the same character.
> Create exactly one 1536x1024 PNG atlas, six equal 512x512 cells in a strict 3-column by 2-row grid, read left-to-right then top-to-bottom. The same elegant young woman peeks from the right edge in every cell: long wavy deep burgundy hair, warm reddish-brown eyes, fair skin, wine-red blazer with tiny gold buttons and small gold hoop earrings, polished soft 3D anime-toy rendering.
> Keep character pose, scale, crop, camera, lighting and costume identical in all six cells. Leave empty space on the left. Exactly ONE visible hand per cell: the same single bare hand gripping the right edge in the same position; all other hands and limbs hidden.
> Only change the facial expression in reading order: idle composed and attentive; happy warm smile; concerned gentle worried brows; notice alert wide eyes; waiting sleepy half-closed eyes; pet blissfully closed eyes.
> Background MUST be a perfectly flat, uniform, pure solid black RGB #000000 across the entire canvas, including gaps and all cell edges. No transparency or alpha channel, no gradients, no texture, no shadows, no glow, and absolutely no checkerboard pattern.
> Strictly six cells. No grid lines, dividers, borders, extra hands, extra arms, extra fingers, duplicated limbs or faces, additional characters, symbols, punctuation, text, watermark, new jewelry or props.

备注：第一次 Frost/Mint/Tea 候选是 RGB 棋盘格背景，不选用；最终交接以本文件标出的黑底版为准。生成子任务未改仓库文件。

上段为生成阶段的原始交接记录；随后已按文首流程将合格素材入库。2026-09-25 隔离 renderer 大小 1.44 MiB，Chromium/WebKit 中六款皮肤的招呼表情都完成实际换图、图片解码为 320×320；白底接触图与浏览器截图已目检。此为合成浏览器验收，不替代真实 macOS UI、Windows 真机或发行包检查。
