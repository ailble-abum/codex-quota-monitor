  async function copyHandoff(button) {
    if (button.disabled || !button.isConnected) return;
    const chinese = uiLanguage() === 'zh';
    const prompt = chinese
      ? '请整理当前任务的接续说明，包含目标和约束、已完成工作及文件路径、决策依据、验证证据、待办与风险、下一步操作。明确哪些已确认、哪些仍是假设；省略密钥和完整聊天记录。先输出交接说明，暂停其他工作。'
      : 'Prepare continuation notes for this task: goals and constraints, completed work and file paths, decision rationale, verification evidence, outstanding work and risks, and next actions. Separate confirmed facts from assumptions. Omit secrets and the full chat transcript. Deliver the notes before resuming other work.';
    button.disabled = true;
    let copied = false;
    try { await navigator.clipboard.writeText(prompt); copied = true; }
    catch (_) { /* Unsupported or denied clipboard access is a visible failure. */ }
    if (!button.isConnected) return;
    button.disabled = false;
    button.textContent = copied
      ? (chinese ? '已复制，请粘贴到当前任务生成交接说明' : 'Copied; paste into this task to request a handoff.')
      : (chinese ? '复制失败，请在当前任务要求生成交接说明' : 'Copy failed; request a handoff in this task.');
  }
