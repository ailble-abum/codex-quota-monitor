# 伴宠视觉资源来源记录

这份记录只描述工程来源，不构成法律意见或单独的著作权鉴定。

## 当前仓库中的资源

`assets/companions` 中的 12 个 WebP 是 V2 构建输入。它们在提交 `ba2ca24` 中被内建到本仓库，构建器随后把它们编码进 `renderer/consumer.js`。每次候选构建都会在 `renderer/manifest.json` 的 `visualResourceSHA256` 中记录相对路径和 SHA-256，避免资源被无记录替换。

这 12 个文件与正式线 `origin/main` 中对应的 WebP 逐字节一致（2026-09-24 核对 SHA-256）。正式线历史补足了部分工程来源：`afe50a2` 加入五款角色源 PNG 和 WebP 构建脚本；`17c5302` 加入黑猫源 PNG；`2705f32` 加入黑猫六表情源图及导出脚本。正式线 `docs/companion-feedback.md` 记录六表情由内置 imagegen 生成，并以已有角色 WebP 为身份参考；该记录及 `docs/companion-expression-provenance.md` 的详细提示词保存在 Git 历史中。它们证明了项目内导出链及记录的生成过程，不证明六款角色原图的最初创作权属，也不构成独立法律审查。

因此发行包继续携带根目录 `LICENSE` 与 `NOTICE`，不把资源标成“全部原创”。

## 复核边界

- 角色原图的最初生成记录和授权材料仍需补齐；裁切/抠图与 WebP 导出脚本、表情生成记录可从正式线历史追溯。
- `tools/build_panel.py` 只读取仓库内 WebP，不读取旧 renderer Python 文件；旧版拼接构建器已从当前 V2 源码移除。
- 资源哈希证明的是当前构建输入可重复，不证明创作权或许可已经转移。

完成复核并取得明确授权记录后，才重新评估发行包的归因范围；在此之前不得删除 Kevin Ke、Ailble 或上游 MIT/NOTICE 文本。
