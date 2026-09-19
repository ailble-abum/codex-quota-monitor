"""Bounded local numeric history and a standalone, offline trend page."""
import html
import json
import math
import time
from pathlib import Path
from platform_paths import runtime_root

ROOT = runtime_root()


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(text,encoding='utf-8')
    temp.chmod(0o600)
    temp.replace(path)


def recent_breakdown(summaries, limit=6):
    groups={'models':{},'projects':{}}
    for item in summaries[:100]:
        tokens=item.get('session_total_tokens')
        if not isinstance(tokens,(int,float)) or isinstance(tokens,bool) or not math.isfinite(tokens) or tokens<0:
            continue
        model=item.get('model') or '未知模型'
        cwd=item.get('cwd')
        project=Path(cwd).name if isinstance(cwd,str) and cwd else '未知项目'
        groups['models'][model]=groups['models'].get(model,0)+tokens
        groups['projects'][project]=groups['projects'].get(project,0)+tokens
    return {key:sorted(values.items(),key=lambda pair:pair[1],reverse=True)[:limit] for key,values in groups.items()}


def weekly_report(rows):
    """Compact seven-day summary derived only from the retained local samples."""
    valid=[row for row in rows if isinstance(row,dict)]
    times=[row.get('at') for row in valid if isinstance(row.get('at'),(int,float)) and not isinstance(row.get('at'),bool)]
    spans=max(times)-min(times) if times else 0
    remaining=[];contexts=[];cached=[]
    for row in valid:
        for window in row.get('windows') or []:
            value=window.get('remaining') if isinstance(window,dict) else None
            if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):remaining.append(value)
        context=row.get('context') or {}
        if not isinstance(context,dict):context={}
        value=context.get('latest_context_percent')
        if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):contexts.append(value)
        total=context.get('latest_turn_input_tokens');hit=context.get('latest_turn_cached_input_tokens')
        if isinstance(total,(int,float)) and not isinstance(total,bool) and total>0 and isinstance(hit,(int,float)) and not isinstance(hit,bool):
            cached.append(100*hit/total)
    cards=[(str(len(valid)),'采样点'),(f'{spans/3600:.1f}h','覆盖时长')]
    if remaining:cards.append((f'{min(remaining):.0f}%','期间最低配额'))
    if contexts:cards.append((f'{max(contexts):.1f}%','上下文峰值'))
    if cached:cards.append((f'{sum(cached)/len(cached):.1f}%','平均缓存占比'))
    card_html=''.join(f'<div><strong>{html.escape(value)}</strong><span>{label}</span></div>' for value,label in cards)
    latest=(valid[-1].get('breakdown') or {}) if valid else {}
    if not isinstance(latest,dict):latest={}
    notes=[]
    for label,key in (('主要模型','models'),('主要项目','projects')):
        items=latest.get(key) or []
        if items:notes.append(f'{label}：{html.escape(str(items[0][0]))}')
    note=' · '.join(notes) or '数据不足时仅显示已采集项，不补造历史。'
    return f'<section><h2>本地 7 天周报</h2><div class="cards">{card_html}</div><p>{note}</p><p>基于本机保留的数值快照；配额来自官方账户读取，上下文与缓存来自本地会话日志。</p></section>'


class History:
    def __init__(self, root=ROOT):
        self.root=root
        self.last=0

    def update(self, quota, context=None, health=None, breakdown=None):
        now=time.time()
        snapshot={'at':now,'quota':quota,'context':context,'health':health,'breakdown':breakdown or {}}
        atomic(self.root/'snapshot.json',json.dumps(snapshot))
        if quota.get('status')!='live' or quota.get('updatedAt',0)<=self.last:
            return
        self.last=quota['updatedAt']
        path=self.root/'history.json'
        try: rows=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError): rows=[]
        if not isinstance(rows,list):rows=[]
        rows=[r for r in rows if isinstance(r,dict) and r.get('at',0)>now-7*86400][-10079:]
        rows.append({'at':now,'account':quota.get('accountKey'),'windows':quota.get('windows',[]),
                     'usage':quota.get('usage') or {},'context':context or {},'breakdown':breakdown or {}})
        atomic(path,json.dumps(rows))
        selected=[r for r in rows if r.get('account')==quota.get('accountKey')]
        atomic(self.root/'history.html', self.page(selected))

    @staticmethod
    def page(rows):
        now=time.time()
        start=rows[0]['at'] if rows else now
        end=max(now,start+60)
        charts=[]
        report=weekly_report(rows)
        usage=(rows[-1].get('usage') or {}) if rows else {}
        breakdown=(rows[-1].get('breakdown') or {}) if rows else {}
        summary=usage.get('summary') or {}
        daily=usage.get('dailyUsageBuckets') or []
        cards=[]
        for title,key in [('累计 Token 活动','lifetimeTokens'),('单日峰值','peakDailyTokens'),('连续活跃天数','currentStreakDays')]:
            value=summary.get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):
                cards.append(f'<div><strong>{int(value):,}</strong><span>{title}</span></div>')
        usage_summary=f'<section><h2>账户 Token 活动摘要</h2><div class="cards">{"".join(cards)}</div><p>来自官方 account/usage/read；这是活动统计，不等于账户配额或账单。</p></section>' if cards else ''
        if daily:
            clean=[item for item in daily if isinstance(item,dict) and isinstance(item.get('startDate'),str) and isinstance(item.get('tokens'),(int,float)) and not isinstance(item.get('tokens'),bool)]
            clean=clean[-30:]
            if clean:
                peak=max(float(item['tokens']) for item in clean) or 1
                bars=''.join(f'<div class="bar" style="height:{max(2,100*float(item["tokens"])/peak):.1f}%" title="{html.escape(item["startDate"])} · {int(item["tokens"]):,} Token"></div>' for item in clean)
                usage_summary+=f'<section><h2>最近每日 Token 活动</h2><div class="bars">{bars}</div><p>最近 {len(clean)} 个官方日桶；悬停柱形查看数值。</p></section>'
        breakdown_html=''
        for title,key in [('最近会话按模型','models'),('最近会话按项目','projects')]:
            items=breakdown.get(key) or []
            if items:
                peak=max(float(value) for _,value in items) or 1
                rows_html=''.join(f'<div class="rank"><span>{html.escape(str(name))}</span><b style="width:{100*float(value)/peak:.1f}%"></b><strong>{int(value):,}</strong></div>' for name,value in items)
                breakdown_html+=f'<section><h2>{title}</h2>{rows_html}<p>最近最多 100 个本地会话的累计 Token；用于相对比较，不等于账单。</p></section>'
        actual=(rows[-1].get('windows') or []) if rows else []
        for window in actual:
            key=window['key'];duration=window.get('duration');color='#285dc1' if key=='primary' else '#18734e'
            label=f'{duration//1440} 天' if isinstance(duration,int) and duration>0 and duration%1440==0 else f'{duration//60} 小时' if isinstance(duration,int) and duration>0 and duration%60==0 else f'{duration} 分钟' if isinstance(duration,int) and duration>0 else '主窗口' if key=='primary' else '次窗口'
            title=label+'剩余'
            paths=[];points=[];reset=None;prev=None
            for row in rows:
                item=next((w for w in row['windows'] if w['key']==key),None)
                if not item:continue
                if reset!=item.get('resetsAt') or (prev and row['at']-prev>180):
                    if points:paths.append(points)
                    points=[]
                reset=item.get('resetsAt');prev=row['at']
                points.append((20+(row['at']-start)/(end-start)*720,150-item['remaining']*1.3))
            if points:paths.append(points)
            lines=''.join('<polyline points="'+' '.join(f'{x:.1f},{y:.1f}' for x,y in p)+'"/>' for p in paths)
            dots=''.join(f'<circle cx="{p[-1][0]:.1f}" cy="{p[-1][1]:.1f}" r="3" fill="{color}"/>' for p in paths)
            charts.append(f'<section><h2>{title}</h2><svg viewBox="0 0 760 180" role="img" aria-label="{title}历史"><path d="M20 20H740 M20 85H740 M20 150H740" stroke="#e2e5e4"/><text x="700" y="16">100%</text><text x="708" y="81">50%</text><text x="714" y="146">0%</text><g fill="none" stroke="{color}" stroke-width="2.5">{lines}</g>{dots}<text x="20" y="174">{time.strftime("%m/%d %H:%M",time.localtime(start))}</text><text x="610" y="174">{time.strftime("%m/%d %H:%M",time.localtime(end))}</text></svg></section>')
        def metric_points(field):
            points=[]
            for row in rows:
                context=row.get('context') or {}
                value=context.get(field)
                if field=='cached_share':
                    input_tokens=context.get('latest_turn_input_tokens')
                    cached_tokens=context.get('latest_turn_cached_input_tokens')
                    value=(100*cached_tokens/input_tokens) if isinstance(input_tokens,(int,float)) and not isinstance(input_tokens,bool) and input_tokens>0 and isinstance(cached_tokens,(int,float)) and not isinstance(cached_tokens,bool) else None
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):
                    points.append((row.get('at',now),max(0,min(100,float(value)))))
            return points

        def metric_chart(title, points, color, description):
            if not points:
                return ''
            metric_start=rows[0].get('at',now) if rows else now
            metric_end=max(now,metric_start+60)
            segments=[];segment=[];previous=None
            for timestamp,value in points:
                if previous is not None and (timestamp-previous)>180:
                    if segment:segments.append(segment)
                    segment=[]
                previous=timestamp
                segment.append((20+(timestamp-metric_start)/(metric_end-metric_start)*720,150-value*1.3))
            if segment:segments.append(segment)
            lines=''.join('<polyline points="'+' '.join(f'{x:.1f},{y:.1f}' for x,y in segment)+'"/>' for segment in segments)
            dots=''.join(f'<circle cx="{segment[-1][0]:.1f}" cy="{segment[-1][1]:.1f}" r="3" fill="{color}"/>' for segment in segments)
            return f'<section><h2>{title}</h2><p>{description}</p><svg viewBox="0 0 760 180" role="img" aria-label="{title}历史"><path d="M20 20H740 M20 85H740 M20 150H740" stroke="#e2e5e4"/><text x="700" y="16">100%</text><text x="708" y="81">50%</text><text x="714" y="146">0%</text><g fill="none" stroke="{color}" stroke-width="2.5">{lines}</g>{dots}<text x="20" y="174">{time.strftime("%m/%d %H:%M",time.localtime(metric_start))}</text><text x="610" y="174">{time.strftime("%m/%d %H:%M",time.localtime(metric_end))}</text></svg></section>'

        metric_charts=[]
        context_points=metric_points('latest_context_percent')
        cached_points=metric_points('cached_share')
        if context_points:
            metric_charts.append(metric_chart('上下文占用趋势',context_points,'#285dc1','当前上下文窗口占用；超过 70%／85% 时对应监视器的注意／高压提示。'))
        if cached_points:
            metric_charts.append(metric_chart('缓存输入占比趋势',cached_points,'#18734e','最近请求中缓存输入占全部输入的比例；用于观察复用情况，不代表账户额度。'))
        return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Codex · 本地周报</title><style>body{max-width:850px;margin:40px auto;padding:0 24px;background:#f4f5f4;color:#24312b;font:14px/1.6 system-ui}section{background:white;padding:24px;border-radius:18px;margin:20px 0}h1{font-size:24px}h2{font-size:15px}svg{width:100%}text{font:11px system-ui;fill:#68716e}p{color:#68716e}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.cards div{padding:14px;border-radius:12px;background:#f4f7f6}.cards strong,.cards span{display:block}.cards strong{font-size:20px}.cards span{color:#68716e}.bars{height:150px;display:flex;gap:4px;align-items:end;border-bottom:1px solid #dfe5e2}.bar{flex:1;min-width:3px;background:#285dc1;border-radius:3px 3px 0 0}.rank{display:grid;grid-template-columns:minmax(120px,1fr) 3fr auto;gap:10px;align-items:center;margin:10px 0}.rank b{display:block;height:9px;background:#285dc1;border-radius:9px}.rank strong{font-variant-numeric:tabular-nums}</style><h1>本地用量周报</h1><p>本地记录 · 最近 7 天 · 仅当前采集账户 · '+str(len(rows))+' 个采样点。配额重置与超过 3 分钟的空档分段绘制。只从启用后开始记录，不补造历史。</p>'+report+usage_summary+breakdown_html+''.join(charts)+''.join(metric_charts)+'<p>数据更新时间：'+time.strftime('%Y-%m-%d %H:%M:%S')+'。重新打开本页查看更新。关闭 Codex 时采集暂停。</p></html>'
