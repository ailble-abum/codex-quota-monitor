"""Offline, account-scoped HTML view of verified V2 numeric samples."""
from html import escape
from string import Template


def render_report(summary):
    weekly = summary.get('weekly', {})
    days = weekly.get('days', [])
    models = weekly.get('modelCounts', [])
    projects = weekly.get('projectCounts', [])

    def metric(label, value):
        return '<div class="card"><strong>{}</strong><span>{}</span></div>'.format(
            escape(str(value)), escape(label))

    cards = [metric('采样点', summary.get('samples', 0)),
             metric('覆盖时长', '{:.1f}h'.format(summary.get('spanSeconds', 0) / 3600))]
    for label, key in (('期间最低配额', 'minRemaining'), ('上下文峰值', 'peakContext'),
                       ('平均缓存占比', 'averageCachedShare')):
        value = summary.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cards.append(metric(label, '{:.0f}%'.format(value)))

    def ranking(items, field):
        if not isinstance(items, list) or not items:
            return '<p>暂无数据</p>'
        rows = []
        for item in items[:6]:
            if not isinstance(item, dict) or not isinstance(item.get(field), str):
                continue
            count = item.get('samples')
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                continue
            rows.append('<li><span>{}</span><strong>{} 次采样</strong></li>'.format(
                escape(item[field]), count))
        return '<ol>{}</ol>'.format(''.join(rows)) if rows else '<p>暂无数据</p>'

    daily = []
    if isinstance(days, list):
        for day in days[-7:]:
            if not isinstance(day, dict) or not isinstance(day.get('date'), str):
                continue
            count = day.get('samples')
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                continue
            peak = day.get('peakContext')
            peak_text = '{:.0f}%'.format(peak) if isinstance(peak, (int, float)) and not isinstance(peak, bool) else '—'
            daily.append('<tr><th>{}</th><td>{}</td><td>{}</td></tr>'.format(
                escape(day['date']), count, escape(peak_text)))

    return Template('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Codex V2 · 本地七天报告</title><style>'
            'body{max-width:820px;margin:40px auto;padding:0 20px;font:14px/1.6 system-ui;background:#f5f7f6;color:#26342d}'
            'section{background:white;padding:20px;border-radius:14px;margin:18px 0}'
            '.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}'
            '.card{background:#edf4f0;border-radius:9px;padding:12px}.card strong,.card span{display:block}'
            '.card strong{font-size:20px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:7px;border-bottom:1px solid #e7ece9}'
            'ol{padding-left:20px}li{padding:3px 0}li strong{float:right}p{color:#607067}</style>'
            '<h1>本地七天报告</h1><p>UTC 自然日 · 当前采集账户 · 仅记录启用后的本地数值采样。'
            '模型和项目排行是采样次数，不是 Token 消耗或账单。</p>'
            '<section class="cards">$cards</section>'
            '<section><h2>每日采样</h2><table><thead><tr><th>日期</th><th>采样</th><th>上下文峰值</th></tr></thead>'
            '<tbody>$daily</tbody></table></section>'
            '<section><h2>主要模型</h2>$models</section><section><h2>主要项目</h2>$projects</section>'
            '</html>').substitute(cards=''.join(cards), daily=''.join(daily),
                                  models=ranking(models, 'model'), projects=ranking(projects, 'project'))
