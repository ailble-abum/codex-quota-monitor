# 固定停靠面板的折叠往返

2026-09-20，接续 2c94c2a。上轮直接点击停靠布局中的隐藏面板不能证明布局错误：初始 edge:left/right 会将面板收起至视口外，伴宠负责悬停/聚焦展开。实际复现路径必须先展开并固定。

新 verify_docking.cjs 通过可见伴宠 focus + click 固定展开，然后发布双窗口数据，执行折叠→展开。旧候选在返回 expanded 停靠布局时 data-dock-pinned=true 但 data-revealed=false；后续设置按钮移出视口，点击超时。增加状态断言后旧候选稳定失败在 false !== true。

原因：expanded 有 edge，而新建 compact 仅保存 x/y；临时浮动布局清除 revealed，恢复停靠时默认隐藏。V2 panel_mount 的 toggle 在模式位置切换结束后，对仍为 docked 且 pinned 的面板调用现有 revealDock(true)。不改变初始收起、未固定面板的自动隐藏或保存的边缘位置，不复制或重写保留布局算法。

## 验证

- 新候选 Chromium/WebKit 左右两侧均通过初始收起、键盘聚焦展开、真实点击固定、双窗口内容增长、真实点击折叠往返及视口从 1280×1200 缩到 900×700。
- 设置按钮在缩小视口后仍可实际点击，设置展开时面板边界落在视口内；没有 force click 或直接改可见状态。
- 完整右侧停靠面板 WebKit 明暗截图已目视核验，证据 /tmp/quota-docking-evidence（也包含左侧和 Chromium）。这次是完整面板，不是上轮独立卡片夹具。
- 既有 verify_mount 和 verify_dispose 双浏览器回归通过，包含所有权和卸载资源检查。Python 3.9.6 / 3.14.3 全套各 120 项通过。

候选 /tmp/quota-docking-candidate，保留 LICENSE/NOTICE。本轮仅验证上述视口和合成数据，未承诺任意极小视口/全部布局组合。现用安装和真实会话未动，真实账户、原生窗口、Windows 和发行未验收。下一步返回账户聚合正文与附加用量的来源替换。
