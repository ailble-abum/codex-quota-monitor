# 五款伴宠表情生成记录

2026-09-20；均使用内置 imagegen，以项目现有角色为身份参考。最终源图位于插件 assets/companions，派生36帧由统一脚本生成。以下保留过程提示；最终人工复查包含 candy/mint 单臂修复和 corgi 去除第三爪。临时生成路径不归档。


## candy

### Candy expression atlas provenance

- Generated with the built-in `tools.image_gen__imagegen` tool.
- Reference image: `plugins/codex-quota-monitor/assets/companions/web/candy.webp`
- Final copied asset: `plugins/codex-quota-monitor/assets/companions/candy-expressions-source.png`
- Generation mode: built-in image generation with `referenced_image_paths`.
- The first draft was rejected because it contained a visible yellow notice symbol and needed a stricter transparent-background constraint; one targeted retry was used.

#### Final prompt

```text
Use case: stylized-concept
Asset type: final transparent plugin companion expression sprite atlas
Primary request: Generate the corrected final atlas at exactly 1536x1024 pixels: six equal 512x512 cells in a strict 3-column by 2-row arrangement, no visible separators. Use the supplied reference as the same soft-candy girl in every cell. Preserve her exact identity, warm brown hair with the same two rounded buns/ponytails and pink ties, star hair clip, large brown eyes, pink hoodie, chibi 3D cute toy-like rendering, face shape, colors, lighting style, and right-side peeking pose. Every cell must contain one same-size character with head and torso aligned identically; anchor her at the right of the cell and end the visible silhouette around x=450, leaving about 60px of transparent space to the right boundary. No pixels cross cell boundaries.
Input images: Image 1 is the character identity and style reference; copy it faithfully.
Scene/backdrop: REAL fully transparent RGBA background. Outside the character in all six cells, alpha must be exactly 0. Do not paint, render, or imply any colored background, gradient, vignette, haze, studio backdrop, floor, ground, shadow, or halo. Transparent pixels must remain empty.
Subject and fixed reading order: six copies, top row left-to-right then bottom row left-to-right: 1 idle calm with both eyes open and a quiet neutral smile; 2 happy bright joyful smile; 3 concerned worried brows and small worried mouth; 4 notice alert expression with exactly one of the girl's own hands raised in a small reminder gesture; 5 waiting patient sleepy half-closed eyes; 6 pet eyes closed with a relaxed blissful smile as if enjoying a head pat, but there is NO hand touching her and no other character.
Style/medium: polished cute 3D chibi companion art, smooth clean edges, consistent soft highlights and material rendering, high-resolution game UI sprite atlas.
Composition/framing: invisible 3x2 placement grid only; absolutely no grid, borders, panel backgrounds, cards, labels, or text. Same scale and right-side placement in all cells. Use only the minimal facial expression or hand change required by each state.
Lighting/mood: soft even studio illumination on the character only, subtle gentle highlights, no cast shadow.
Color palette: preserve the reference's warm brown hair and coral-pink hoodie; do not redesign colors.
Materials/textures: soft plush hoodie, smooth glossy hair and skin, rounded 3D-cute finish.
Text (verbatim): none.
Constraints: preserve original outfit, hairstyle, hair accessory, colors, asymmetrical right-peeking pose, scale, and proportions. The only hand visible is the girl's own hand; use it only for notice and the natural reference pose where required. No external hand.
Avoid: colored or semi-opaque backdrop; any brown/gray/pink background; gradients; cast shadows; glow; halo; smoke; sparkles; exclamation marks; comic lines; icons; symbols; props; text; watermark; logo; any second person; extra arms or fingers; malformed limbs; inconsistent identity; inconsistent size; pixels crossing between cells; cropped borders; accidental repeated faces.
```

#### QA evidence

- Output format/mode/size: PNG, RGBA, 1536x1024.
- Global alpha=0 coverage: 50.23% of pixels.
- Per-cell alpha=0 coverage: 49.23%–50.97%.
- At alpha threshold >128, per-cell non-transparent bounding-box width/height ratios: 0.700, 0.709, 0.699, 0.715, 0.705, 0.703; all are <=1.
- Visual check: six independent cells in the requested fixed order; identity, hairstyle, pink hoodie, right-side peek and 3D-cute rendering are consistent; notice uses the character's own raised hand; pet has closed eyes and no touching hand; no yellow notice symbol, text, grid, or second character.

#### Notice anatomy repair revision

- Repair target: the bottom-left `notice` cell (row 2, column 1; pixel box `(0,512)-(512,1024)`) in the same final asset.
- Base atlas used for exact restoration: `plugins/codex-quota-monitor/assets/companions/candy-expressions-source.png` before repair.
- The candidate's repaired bottom-left cell was composited into the base atlas; the other five 512x512 cells were restored from the base atlas byte-for-byte at pixel level.

##### Repair prompt

```text
Use case: precise-object-edit
Asset type: transparent plugin companion expression sprite atlas
Primary request: Edit the supplied candy six-expression atlas and generate a corrected final atlas at exactly 1536x1024 pixels, with six equal 512x512 cells in a 3-column by 2-row arrangement. Keep the same soft-candy girl identity, warm brown double-bun hairstyle with pink ties, star hair clip, large brown eyes, coral-pink hoodie, glossy cute 3D rendering, right-side peeking framing, scale, and baseline. The required correction is only the bottom-left notice cell (row 2, column 1): it must contain exactly one natural raised index-finger reminder hand. Remove the existing right-side grabbing hand and its bent sleeve/arm from that notice cell, and hide the other arm naturally behind the right cell boundary. Build the remaining visible arm as one anatomically continuous shoulder-to-upper-arm-to-elbow-to-sleeve-cuff-to-wrist-to-hand connection; no branch, no fork, no extra limb. Preserve the notice face, hair, hoodie, and body alignment.
Input images: Image 1 is the current full atlas and edit target; preserve its five non-target cells and overall placement. Image 2 is the original single-character identity reference.
Scene/backdrop: genuinely transparent RGBA background in every cell; pixels outside the character must have alpha exactly 0. No colored backdrop, gradient, vignette, haze, floor, ground shadow, or halo.
Subject and fixed reading order: top row idle, happy, concerned; bottom row notice, waiting, pet. The five non-target expressions and their exact cell positions must remain visually unchanged. Notice is alert with the same face as the current notice cell and one raised index finger only.
Composition/framing: invisible 3x2 grid only for placement, no visible grid lines, borders, panels, cards, labels, or text. Every cell same 512x512 size, same right-side peek and head/body alignment. Keep all cell content inside its own cell.
Lighting/mood: soft even warm candy lighting on the character only, subtle highlights, no cast shadow.
Color palette/materials: preserve warm brown hair, coral-pink hoodie, soft plush fabric, smooth glossy hair and skin, rounded 3D-cute finish.
Text (verbatim): none.
Constraints: change the target anatomy only. In the bottom-left notice cell, exactly one visible arm/hand is allowed and it is the raised index-finger hand; the other arm must be naturally concealed behind the right edge. The single visible arm must connect cleanly without a fork from one shoulder through one sleeve cuff to one wrist and hand. No right-side grabbing hand, no second sleeve branch, no duplicate fingers.
Avoid: another person or hand; extra arm; forked shoulder or sleeve; two hands in notice; props; symbols; comic lines; text; watermark; logo; visible grid; background; ground; shadows; halo; inconsistent identity; inconsistent scale; pixels crossing cell boundaries.
```

##### Repair QA evidence

- Final asset remains PNG RGBA 1536x1024 with alpha extrema 0–254 and 50.23% pixels at alpha=0.
- The close-up shows one raised index-finger hand with a continuous shoulder-to-sleeve-to-wrist connection; the former right-side grabbing hand and bent sleeve are absent, and the other arm is hidden behind the right edge.
- The other five cell SHA-256 pixel hashes remain unchanged: top-left `3deea8ebe29addd52d06627e92d540234c1262e832311c6e9b8df32f29424217`, top-middle `1555ad20077b200d73bd3ce43de68b74a52c5474325085941966d948187c57cd`, top-right `50c117945a80d7b3ab6fa9c47b5d7a8650b703a70341b0a97666fe5a103c007c`, bottom-middle `cb135562134d2254c9dd0abbf71aad91e5e997f5907bc4f90b41cf4e393a7a1d`, bottom-right `b47d69aee75cc271285f7c7c01e91b1ebd42d80b0e5e9e2e0bade1a41c0ec69a`.


## corgi

### Corgi expression sheet provenance

- Final selected asset: plugins/codex-quota-monitor/assets/companions/corgi-expressions-source.png
- Reference image: plugins/codex-quota-monitor/assets/companions/web/corgi.webp
- Reference inspected with: Codex `view_image`
- Reference facts: WEBP, 241x320, RGBA, transparent alpha
- Generation path: built-in `image_gen` with `referenced_image_paths`
- Retry reason: first output had an opaque-looking rendered background and an extra notice symbol; the retry prompt explicitly required RGBA alpha=0 outside silhouettes and no symbols.

#### Final retry prompt

Use case: stylized-concept
Asset type: transparent UI companion sprite sheet
Input image: Image 1 is the only identity reference. Keep the exact same orange-and-white 3D corgi assistant: white forehead blaze and muzzle, orange coat, large upright pink-lined ears, dark round eyes, black nose, cute proportions, and right-side peeking design.

Create ONE 1536x1024 PNG sprite sheet, exactly six equal 512x512 cells in a strict 3 columns x 2 rows grid, row-major order:
1 idle calm eyes open
2 happy smiling
3 concerned worried gentle face
4 notice alert face with one of the corgi's own paws raised
5 waiting half-closed eyes
6 pet eyes closed, relaxed happy enjoyment

CRITICAL TECHNICAL OUTPUT: the PNG must have a real RGBA alpha channel. Every pixel outside each corgi silhouette must be fully transparent alpha=0. There must be no colored, white, gray, brown, blurred, gradient, studio, or checkerboard background at all. Do not draw any background, floor, shadow, halo, vignette, border, separator, or grid line; transparent pixels must remain empty alpha. The six cells must have no visible dividers.

In each cell, the same single corgi peeks in from the right, with the same scale, camera, lighting, head/body anchor, fur markings, and anatomy. Keep the left side mostly transparent. The visible silhouette's rightmost edge should stop around x=450 within each 512px cell, leaving roughly 62px transparent margin to the cell edge. Keep all six cells aligned and uncropped. Vary only the face and minimal pose needed for the six expressions. In notice, raise only one of the corgi's own paws; no symbol or effect.

Polished cute 3D character render with clean cutout edges and consistent soft shading. No text or labels.
Avoid: any second character, human hand, extra hand, props, accessories, clothing changes, yellow rays, icons, symbols, speech bubbles, letters, numbers, logos, watermark, background, ground, scenery, shadow, halo, grid, borders, dividers, duplicated limbs, extra paws, extra eyes, inconsistent size, inconsistent fur, or non-transparent pixels outside the six corgi silhouettes.

#### QA

- Final file: PNG 1536x1024, mode RGBA.
- Final alpha extrema: (0, 254); sampled outer/background pixels have alpha=0.
- Per-cell alpha>128 bounds:
  - idle: (84, 7)-(484, 504)
  - happy: (78, 5)-(473, 504)
  - concerned: (94, 6)-(489, 504)
  - notice: (96, 3)-(483, 501)
  - waiting: (83, 3)-(484, 501)
  - pet: (94, 3)-(491, 501)
- All six non-transparent bounds have width/height <= 1 (approximately 0.80, 0.79, 0.81, 0.80, 0.80, 0.80).
- Visual check: six fixed-order expressions, same orange-white corgi identity, right-side peek, no extra notice symbol, no visible grid or divider.

#### Post-generation local repair

- Parent visual review found three paws in the notice cell (bottom-left): raised left paw, upper right gripping paw, and an unwanted lower right paw.
- Edit target: the same final source PNG above, passed to built-in `image_gen` with `referenced_image_paths`.
- Final assembly: the edited notice cell was retained; original cells 1, 2, 3, 5, and 6 were copied back pixel-for-pixel so the requested local repair does not alter the other five cells.

##### Repair prompt

Edit the provided existing 1536x1024 RGBA corgi expression sprite sheet. This is a precise local repair, not a redesign and not a regeneration.

Preserve the exact original image, identity, style, scale, lighting, transparent cutout, alignment, and pixel appearance of cells 1 idle, 2 happy, 3 concerned, 5 waiting, and 6 pet. Do not alter those five cells at all.

Edit ONLY cell 4, the bottom-left 512x512 notice cell (x=0..511, y=512..1023). The notice cell currently has three visible corgi front paws: (1) the raised paw with paw pads on the left, (2) the upper paw gripping the right edge, and (3) an unwanted extra lower paw on the right below it. Remove ONLY the unwanted extra lower-right paw. Continue/fill the corgi's orange-and-white torso/fur naturally where that paw was, preserving the right-edge peek silhouette. Keep exactly the raised left paw with pads and the upper right gripping paw. Do not add or redraw any other limb, paw, hand, finger, eye, ear, or object. Keep the notice face and all other details unchanged.

Technical requirements: output one PNG exactly 1536x1024 with a real RGBA alpha channel. Pixels outside the six corgi silhouettes must remain alpha=0; no background, grid, divider, shadow, halo, text, symbol, prop, or watermark. Keep the strict 3-column by 2-row 512x512 layout and all six expression order. The final notice cell must show exactly two paws: the raised left paw and the upper right gripping paw.


## mint

### Mint companion expression sheet provenance

#### Source

- Reference image: `plugins/codex-quota-monitor/assets/companions/web/mint.webp`
- Reference role: identity and style reference for the same mint chibi boy.
- Generation mode: built-in `image_gen` with `referenced_image_paths`.
- Final selected sheet after replacing only the bottom-left cell and restoring the other five cells pixel-for-pixel: `plugins/codex-quota-monitor/assets/companions/mint-expressions-source.png`
- Project output: `plugins/codex-quota-monitor/assets/companions/mint-expressions-source.png`

#### Final generation prompt

```text
Use case: background-extraction
Asset type: production transparent RGBA sprite sheet for a desktop companion UI
Input image: Image 1 is the only identity/style reference. Preserve this exact mint chibi boy: same warm brown tousled curly hair, face, mint green hoodie, proportions, 3D chibi render, and right-edge peeking identity.

Create exactly ONE PNG image at 1536x1024 pixels with six equal 512x512 sprite cells in a strict 3-column by 2-row layout, left-to-right then top-to-bottom. No dividers. The output MUST be a genuine RGBA image with a real transparent alpha channel: every pixel outside the character silhouettes has alpha=0, and there is absolutely no simulated background, gradient, glow, halo, floor, shadow, color wash, checkerboard, or matte. Transparent means fully empty pixels, not black, brown, gray, green, or blurred pixels. Keep clean anti-aliased character edges without an opaque fringe.

The same single character appears once in every cell, peeking from the right edge, same overall pose, same scale, same head placement, and same lower-body baseline. Keep a transparent margin to all cell boundaries. Each cell's non-transparent content must have width/height ratio <= 1. Never crop the head; only the intentional right-edge peek is cropped. Preserve consistent proportions and lighting across frames.

Cell order:
1 top-left idle: calm, eyes open.
2 top-middle happy: bright eyes and warm open smile.
3 top-right concerned: subtly worried brows and small concerned mouth.
4 bottom-left notice: alert look, one existing hand lifted in a small reminder/wave gesture; no extra hand.
5 bottom-middle waiting: patient, half-closed eyelids.
6 bottom-right pet: eyes closed, blissful content smile, tiny head tilt suggesting a head pat, but NO hand touching the head.

Style: polished soft 3D chibi render matching Image 1, identical soft lighting on the character only.
Constraints: only one character in six cells; exact six cells; no text, labels, logo, watermark, prop, furniture, scenery, border, grid, floor, background, shadow, halo, or second character. No extra limbs, fingers, eyes, ears, mouths, duplicates, or anatomy errors. Do not add any hand for petting. Keep identity, hair, mint clothing, face, style, palette, scale and alignment fixed.
Final technical requirement: actual transparent RGBA PNG, 1536x1024, 3x2 512px grid, empty areas fully alpha=0.
```

#### Surgical cleanup prompt

```text
Use case: precise-object-edit
Asset type: production transparent RGBA sprite sheet
Input image: Image 1 is the existing final six-cell sprite sheet and is the edit target.

Make exactly one surgical edit: remove the three yellow/orange reminder marks floating to the left of the character in the bottom-left notice cell. Replace those marks with fully transparent pixels. Keep the raised-hand notice pose and alert facial expression unchanged.

Preserve every other pixel and invariant as closely as possible: same 1536x1024 dimensions, strict 3-column by 2-row 512x512 cells, real transparent RGBA alpha, all six cell order and positions, the mint chibi boy's identity, face, brown curly hair, mint hoodie, 3D style, lighting, scale, head placement, baseline, right-edge peeking silhouette, and all other five expressions. Do not add or remove anything else.

Avoid: any text, symbols, marks, icons, labels, watermark, glow, background, shadow, checkerboard, extra hand, extra limbs, new props, regenerated characters, changed expressions, changed anatomy, layout changes, or opaque pixels where the removed marks were. The notice cell must contain only the character with the raised existing hand and transparent empty space around it. Output one PNG with actual transparency.
```

#### QA

- Final file reports as `PNG image data, 1536 x 1024, 8-bit/color RGBA, non-interlaced`.
- PIL inspection of the final cleanup: mode `RGBA`, size `(1536, 1024)`, alpha extrema `(0, 254)`.
- All sampled outer corners have alpha `0`; alpha `0` pixel count is `869698` of `1572864`.
- At alpha threshold `128`, per-cell bounding boxes and content ratios are: top row `(153,9)-(499,509)` 346x500 (0.692), `(121,9)-(467,509)` 346x500 (0.692), `(89,9)-(435,509)` 346x500 (0.692); bottom row `(155,7)-(499,504)` 344x497 (0.692), `(120,8)-(466,504)` 346x496 (0.698), `(90,6)-(436,504)` 346x498 (0.695). All width/height ratios are <= 1.
- Visual inspection confirmed six ordered expressions and that the bottom-left notice cell contains only the raised-hand character with no yellow reminder marks.

#### Anatomy cleanup prompt

```text
Use case: precise-object-edit
Asset type: one 512x512 transparent sprite cell for a larger 3x2 companion sheet
Input image: Image 1 is the cropped bottom-left notice sprite cell and is the edit target. Preserve this exact mint chibi boy's face, brown tousled curly hair, mint hoodie, 3D chibi style, eye expression, mouth, head position, scale, and right-edge peeking framing.

Repair only the anatomy in this one cell. The notice pose must show exactly ONE visible arm and hand: the existing left-side raised hand making a small natural reminder/wave gesture. It must connect naturally through one shoulder, one upper arm, one elbow, one sleeve cuff, and one wrist. Remove the existing right-side grabbing hand and its bent curved sleeve/forearm completely. Let the other arm be naturally hidden behind the right cell boundary/hoodie edge, with no visible hand, sleeve bend, or second arm. The silhouette at the right edge should remain a clean natural peek, with no limb emerging there.

Keep transparent background with real alpha and retain the 512x512 canvas. Keep the head, face, hair, hoodie collar and body placement otherwise unchanged. The raised hand should have clean, plausible anatomy and fingers, with a smooth single-shoulder-to-arm connection; no split shoulder or branching sleeves.

Avoid: any second hand, right-side grabbing hand, curved right sleeve, extra shoulder, branching limb, duplicated arm, extra fingers, malformed wrist, changed face, changed hair, changed clothing color, text, marks, icons, props, background, floor, glow, shadow, checkerboard, opaque matte, or any change outside the single character cell. Output a single transparent RGBA PNG cell.
```

#### Anatomy cleanup assembly and QA

- The generated notice candidate was 1254x1254 RGBA and was resized to exactly 512x512 with Pillow LANCZOS for cell placement.
- Final output remains `1536x1024`, `8-bit/color RGBA`, with alpha extrema `(0,255)` and all four outer corners alpha `0`.
- Final alpha-threshold-128 cell bounding boxes: top row `(153,9)-(499,509)`, `(121,9)-(467,509)`, `(89,9)-(435,509)`; bottom row notice `(154,6)-(500,506)`, waiting `(120,8)-(466,504)`, pet `(90,6)-(436,504)`. All cell content width/height ratios are <= 1.


## frost

### Frost expression atlas provenance

- Generated with the built-in `tools.image_gen__imagegen` tool.
- Reference image: `plugins/codex-quota-monitor/assets/companions/web/frost.webp`
- Final copied asset: `plugins/codex-quota-monitor/assets/companions/frost-expressions-source.png`
- Generation mode: built-in image generation with `referenced_image_paths`.
- The first draft was rejected because the notice cell added an extra pointing hand; one targeted retry was used to preserve only the reference's single visible glove in all six cells.

#### Final prompt

```text
Use case: stylized-concept
Asset type: final transparent plugin companion expression sprite atlas
Primary request: Correct the prior atlas by removing the extra pointing hand that appeared in the notice cell, while preserving all other successful details. Generate exactly 1536x1024 pixels: six equal 512x512 cells in a strict 3-column by 2-row arrangement. Use the supplied Frost reference as the same character in every cell, preserving his exact identity, silver-white swept layered hair with dark roots and long fringe, cool blue eyes, pale skin, black high-collar coat, the single black glove visible at the right edge, right-side peeking pose, cool palette, and polished serious 3D-cute rendering. Every cell must have the same scale, head position, shoulder baseline, and camera distance; anchor him at the right side with a transparent gap before the cell boundary, and keep all pixels inside their own 512x512 cell.
Input images: Image 1 is the identity, hairstyle, outfit, pose, and style reference; copy it faithfully.
Scene/backdrop: genuinely transparent RGBA background. Outside the character in every cell alpha must be exactly 0. No colored background, gradient, vignette, haze, floor, ground shadow, or halo.
Subject and fixed reading order: exactly six copies, top row left-to-right then bottom row left-to-right: 1 idle calm, eyes open and composed neutral mouth; 2 happy, a clearly warmer confident smile; 3 concerned, visibly worried brows, slightly widened eyes and tense small mouth; 4 notice, alert brows and attentive eyes with a small alert mouth, expressed by face only; 5 waiting, patient and tired with genuinely half-closed eyes and a subtle waiting pout; 6 pet, eyes closed and a peaceful satisfied smile as if enjoying a head pat, but no touching hand.
Hand constraint: in every cell show exactly the same one visible right-side black-gloved hand from the reference, holding the coat edge in the natural reference pose. Do not add any second visible hand, raised hand, pointing hand, extra arm, fingers, person, prop, or hand touching his head. The notice state must not raise or invent a hand; use facial expression only.
Style/medium: polished cool-toned 3D chibi companion art, smooth clean edges, realistic soft hair strands, matte black fabric and glove, restrained premium game UI character render, consistent soft highlights and cool steel-blue lighting.
Composition/framing: invisible 3x2 placement grid only for placement; no visible grid lines, borders, cards, panels, labels, or text. Same right-side peek and consistent body alignment in all six cells. Expressions must be genuinely distinct and readable at icon size while retaining one unchanged hand silhouette.
Lighting/mood: soft even cool illumination on the character only, subtle controlled highlights, no cast shadow.
Color palette: preserve silver-white hair, cool blue eyes, pale skin, and charcoal-black clothing; no warm redesign.
Materials/textures: smooth layered hair, soft skin, matte black high-collar coat, one black glove, refined 3D-cute finish.
Text (verbatim): none.
Constraints: preserve original outfit, hairstyle, hair color, eye color, glove, collar, right-peeking asymmetrical pose, scale, proportions, and the exact one-hand silhouette. Keep the six states in the exact requested order.
Avoid: any colored or semi-opaque backdrop; any gray/blue/black painted background; gradients; cast shadows; glow; halo; smoke; snow; ice; sparkles; comic lines; icons; symbols; props; weapons; text; watermark; logo; another character; another person's hand; any second visible hand; extra arms or fingers; duplicated limbs; malformed hands; inconsistent identity; inconsistent size; cell-crossing pixels; cropping artifacts; repeated identical expression.
```

#### QA evidence

- Output format/mode/size: PNG, RGBA, 1536x1024.
- Global alpha=0 coverage: 49.05% of pixels.
- Per-cell alpha=0 coverage: 48.84%–49.28%.
- At alpha threshold >128, per-cell non-transparent bounding-box width/height ratios: 0.733, 0.735, 0.733, 0.735, 0.735, 0.735; all are <=1.
- Visual check: six independent cells in the requested fixed order; idle, happy, concerned, notice, waiting, and pet have visibly distinct expressions; Frost's silver-white hair, blue eyes, black high-collar coat, cool serious 3D identity, right-side peek, and one visible glove remain consistent; no extra hand, props, text, grid, or second character.


## tea

### Tea expression sheet provenance

- Final selected asset: plugins/codex-quota-monitor/assets/companions/tea-expressions-source.png
- Reference image: plugins/codex-quota-monitor/assets/companions/web/tea.webp
- Reference inspected with: Codex `view_image`
- Reference facts: WEBP, 229x320, RGBA, transparent alpha
- Generation path: built-in `image_gen` with `referenced_image_paths`

#### Prompt

Use case: stylized-concept
Asset type: transparent UI companion sprite sheet
Input image: Image 1 is the only identity reference. Preserve the exact same tea-colored female assistant: long flowing wavy burgundy hair, warm fair skin, red-brown eyes, delicate anime-inspired face, burgundy blazer, gold hoop earrings, and the same right-edge peeking character design. Keep her identity, hair silhouette, facial proportions, clothing, jewelry, and polished illustration finish unchanged.

Create ONE finished PNG sprite sheet, exactly 1536x1024 pixels, with six equal 512x512 cells in a strict 3 columns x 2 rows layout. Fixed row-major order:
1 idle — calm, eyes open
2 happy — cheerful warm smile
3 concerned — worried, gentle concerned expression
4 notice — alert reminder expression, with at most one of her existing hands raised slightly
5 waiting — patient waiting expression with half-closed eyes
6 pet — eyes closed, relaxed enjoyment

CRITICAL TECHNICAL OUTPUT: the PNG must have a real RGBA alpha channel. Every pixel outside each character silhouette must be fully transparent alpha=0. There must be no colored, white, gray, brown, blurred, gradient, studio, or checkerboard backdrop at all. Do not draw a background, floor, ground, shadow, halo, vignette, border, separator, or grid line. Transparent pixels must remain empty alpha. The six cells must have no visible dividers.

In every cell, the same single tea assistant peeks from the right side, with identical head and body scale, camera, lighting, hair/clothing silhouette, and anchor. Keep the left side mostly transparent. The visible silhouette should end around x=450 within each 512px cell, leaving roughly 62px transparent breathing room at the cell's right edge. Keep all six cells aligned and uncropped. Vary only the facial expression and the minimal pose needed for the expression. For notice, use only one hand that belongs to the same character if a hand gesture is needed; never add a new hand or limb.

Style/medium: polished cute semi-realistic anime character render, clean cutout edges, consistent soft shading, consistent warm lighting, same camera and framing across all six cells.
No text or labels.
Avoid: another character, another person, human hand, extra hands, extra arms, extra fingers, props, tea cup, accessories beyond the reference jewelry, clothing changes, symbols, icons, speech bubbles, letters, numbers, logos, watermark, background, floor, scenery, cast shadow, halo, grid, borders, dividers, duplicated anatomy, extra eyes, inconsistent hair, inconsistent outfit, cropped face, or any non-transparent pixels outside the six character silhouettes.

#### QA

- Final file: PNG 1536x1024, mode RGBA.
- Final alpha extrema: (0, 254); full-image corners and every cell corner have alpha=0.
- Per-cell alpha>128 bounds:
  - idle: (115, 6)-(465, 493)
  - happy: (117, 6)-(470, 493)
  - concerned: (123, 6)-(474, 493)
  - notice: (112, 6)-(452, 495)
  - waiting: (117, 7)-(471, 495)
  - pet: (123, 6)-(475, 495)
- All six non-transparent bounds have width/height <= 1 (approximately 0.72, 0.73, 0.72, 0.70, 0.73, 0.72).
- Visual check: checkerboard alpha composite shows only the six fixed-order character silhouettes with no rendered background, grid, or extra object; identity, scale, right-side peek, and expression variations are consistent.
