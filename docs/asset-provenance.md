# 伴宠视觉资源来源记录

这份记录只描述工程来源，不构成法律意见或单独的著作权鉴定。

## 当前仓库中的资源

`assets/companions` 中的 12 个 WebP 是 V2 构建输入。它们在提交 `ba2ca24` 中被内建到本仓库，构建器随后把它们编码进 `renderer/consumer.js`。每次候选构建都会在 `renderer/manifest.json` 的 `visualResourceSHA256` 中记录相对路径和 SHA-256，避免资源被无记录替换。

这些文件与历史 renderer 中的归档视觉字节保持一致，但本 V2 仓库没有保存最初生成/导出的完整源文件链。因此在完成来源和权属复核前，发行包继续携带根目录 `LICENSE` 与 `NOTICE`，不把资源标成“全部原创”。

## 复核边界

- 角色原始图、裁切/抠图、WebP 编码和表情导出的具体创作链需要从历史项目记录或创作者材料补齐。
- `tools/build_panel.py` 只读取仓库内 WebP，不读取旧 renderer Python 文件；`tools/build_panel_candidate.py` 仍是带归因的行为对照工具，不是发行入口。
- 资源哈希证明的是当前构建输入可重复，不证明创作权或许可已经转移。

完成复核并取得明确授权记录后，才重新评估发行包的归因范围；在此之前不得删除 Kevin Ke、Ailble 或上游 MIT/NOTICE 文本。
