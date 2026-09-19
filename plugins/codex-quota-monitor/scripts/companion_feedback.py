"""Local companion feedback. Pure reducer and pointer classification, no model calls."""
COMPANION_FEEDBACK_JS = r"""
  function companionExpression(reaction,mood) {
    if(reaction==='pet')return 'pet';
    if(reaction==='happy'||reaction==='hello')return 'happy';
    if(reaction==='notice')return 'notice';
    return mood==='waiting'?'waiting':mood==='concerned'||mood==='unknown'?'concerned':'idle';
  }
  function companionHealth(payload,id) {
    const normalize=value=>String(value||'').replace(/^local:/,'');
    return id&&normalize(id)===normalize(payload.healthThreadId)?payload.health||null:null;
  }
  function companionGesture(start,x,y,now) {
    if(start.mode==='drag')return 'drag';
    const distance=Math.hypot(x-start.x,y-start.y);
    if(start.head && distance<14 && now-start.at>=350)return 'pet';
    return distance>=4?'drag':'click';
  }
  function companionStep(previous,input,now) {
    const valid=n=>typeof n==='number'&&Number.isFinite(n)&&n>=0&&n<=100;
    const state={...previous,threads:{...(previous.threads||{})}};
    const events=[];
    const sameAccount=!!input.account&&state.account===input.account;
    const priorLast=state.quotaLast;
    if(input.live){
      if(state.account!==input.account)state.quotaLast=null;
      state.account=input.account;
    }
    state.windows={...(state.windows||{})};
    const level=n=>!valid(n)?null:n<=0?3:n<=10?2:n<=20?1:0;
    const quotaLevel=!input.live?null:input.blocked?3:level(input.remaining);
    if(quotaLevel!==null){
      const windows=input.windows?.length?input.windows:[{key:'all',resetsAt:input.cycle,remaining:input.remaining}];
      let highest=0;
      for(const w of windows){
        const key=JSON.stringify([input.account,w.key,w.resetsAt]);
        const current=level(w.remaining);
        const old=state.windows[key]||{seen:0};
        if(current!==null){
          if(current>old.seen)highest=Math.max(highest,current);
          state.windows[key]={seen:Math.max(old.seen,current),at:now};
        }
      }
      if(input.blocked&&state.quotaLast!==3)highest=3;
      if(highest)events.push(['','quota-watch','quota-low','quota-empty'][highest]);
      else if(sameAccount&&priorLast===3&&quotaLevel===0)events.push('quota-restored');
      state.quotaLast=quotaLevel;
      state.windows=Object.fromEntries(Object.entries(state.windows).sort((a,b)=>b[1].at-a[1].at).slice(0,100));
    }
    const ctxLevel=!input.thread||!valid(input.ctx)?0:input.ctx>=95?3:input.ctx>=85?2:input.ctx>=70?1:0;
    if(input.thread){
      const old=state.threads[input.thread];
      const thread={...(old||{seen:0,last:0}),at:now};
      // Rearm only after a clear fall and a 30-minute cooldown.
      if(valid(input.ctx)&&input.ctx<65&&now-thread.last>1800000)thread.seen=0;
      if(ctxLevel>=2&&ctxLevel>thread.seen){events.push(ctxLevel===3?'ctx-critical':'ctx-high');thread.seen=ctxLevel;thread.last=now;}
      if(old&&input.compaction&&input.compaction!==old.compaction)events.push('compacted');
      thread.compaction=input.compaction||old?.compaction||null;
      state.threads[input.thread]=thread;
      state.threads=Object.fromEntries(Object.entries(state.threads).sort((a,b)=>b[1].at-a[1].at).slice(0,100));
    }
    return {state,quotaLevel,ctxLevel,event:events.length?events.join('+'):null};
  }
"""
