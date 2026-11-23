"""Codex-style rail + overview tree. Cost lives on zoomed nodes and edges."""
from __future__ import annotations

from html import escape

from svg_overview import svg_overview


CSS = (
    'body{margin:0;background:#111411;color:#d7ddd8;font:13px/1.4 ui-sans-serif,system-ui}'
    '.shell{display:grid;grid-template-columns:28px 1fr;min-height:100vh}'
    '.wrap.architecture{display:grid;grid-template-columns:1fr 280px;min-height:100vh}'
    '.rail{padding:16px 8px;border-right:1px solid #2a302c}'
    '.rail ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:14px;align-items:center}'
    '.dot{position:relative;width:8px;height:8px;border-radius:50%;background:#4b554e;cursor:default}'
    '.dot.done{background:#4ade63}'
    '.dot.running,.dot.waiting_choice{background:#5ee06a}'
    '.dot .tip{display:none;position:absolute;left:16px;top:-6px;width:180px;padding:8px;background:#171b18;border:1px solid #2f3832;border-radius:8px;z-index:2}'
    '.dot:hover .tip,.dot:focus .tip{display:block}'
    '.main,.overview{padding:16px 20px 40px}'
    '.board{background:#ffffff;border:1px solid #2a302c;border-radius:10px;overflow:auto;margin:8px 0 20px}'
    '.members{list-style:none;margin:0;padding:0;display:grid;gap:8px}'
    '.member{padding:8px 10px;border:1px solid #2f3832;border-radius:8px;display:flex;justify-content:space-between;gap:12px}'
    '.member.billable{border-color:#2AA8A4}'
    '.zoom{padding:16px;border-left:1px solid #2a302c}'
    '.finder{padding:16px 20px 40px;grid-column:1 / -1;border-top:1px solid #2a302c}'
    '.finder ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}'
    '.finder a{color:#d7ddd8}'
    '.board-toolbar{display:flex;gap:8px;align-items:center;margin:0 0 8px}'
    '.board-toolbar button{border:1px solid #2f3832;background:#171b18;color:#d7ddd8;border-radius:8px;padding:6px 10px;cursor:pointer}'
    '.board-toolbar button[aria-pressed="true"]{border-color:#2AA8A4}'
    '.board-legend{display:flex;gap:14px;align-items:center;margin-left:auto}'
    '.board-legend i{display:inline-block;width:14px;height:14px;margin-right:4px;vertical-align:middle}'
    '.board-legend .agent{border-radius:5px;width:18px;height:12px}'
    '.board-legend .local{border-radius:50%}'
    '.board-legend .subagent{width:0;height:0;border:7px solid transparent;border-bottom-color:currentColor;transform:rotate(45deg)}'
    '.board-stage{height:min(72vh,740px);overflow:hidden;background:#f7f4ee;border:1px solid #2a302c;border-radius:10px;position:relative;cursor:grab}'
    '.board-pan{transform-origin:0 0;will-change:transform}'
    '.board-stage[data-lod="preview"] .board-detail{display:none}'
    '.option-popup{position:fixed;right:24px;bottom:24px;width:280px;background:#171b18;color:#d7ddd8;border:1px solid #2f3832;border-radius:10px;padding:12px 14px}'
    '.option-popup.wide{width:min(420px,calc(100vw - 48px));max-height:min(80vh,640px);overflow:auto}'
    '.option-popup h2{margin:0 0 8px;font-size:13px}'
    '.option-hint{margin:0 0 10px;color:#b7c0b8;font-size:12px}'
    '.web-groups{display:grid;gap:10px;margin:0 0 12px}'
    '.web-group .label{display:block;margin:0 0 4px;color:#9aa59c}'
    '.chips{display:flex;flex-wrap:wrap;gap:6px}'
    '.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid #2f3832;background:#111411;color:inherit;border-radius:999px;padding:4px 10px}'
    '.chip[aria-pressed="true"]{border-color:#2AA8A4}'
    '.chip[disabled]{opacity:.55;cursor:not-allowed}'
    '.gem{display:inline-block;width:8px;height:8px;background:#e8c547;transform:rotate(45deg)}'
    '.chip[hidden]{display:none}'
    '.quote-confirm{margin:8px 0 0;border:0;border-radius:999px;background:#2AA8A4;color:#111411;padding:8px 12px;font-weight:600}'
    '.options{display:grid;gap:8px}'
    '.option{text-align:left;background:#111411;color:inherit;border:1px solid #2f3832;border-radius:8px;padding:8px}'
    '.member a{color:#d7ddd8}'
)


def html_document(view, *, title='时间轴+画板思维'):
    if view.get('schema') == 'pcg.board.v1':
        return html_board(view, title=title)
    if view.get('schema') != 'pcg.view.v1':
        raise ValueError('html requires pcg.view.v1 or pcg.board.v1')
    catalog = view.get('credit_catalog') or {}
    rail = []
    for step in view.get('rail') or []:
        action = 'resume' if step.get('resume_allowed') else 'confirm'
        rail.append(
            '<li class="dot %s" data-id="%s" data-action="%s" title="%s">'
            '<span class="tip"><b>%s</b><br/>%s</span></li>'
            % (
                escape(step.get('state') or ''),
                escape(step['id']),
                action,
                escape(step['say']),
                escape(step['say']),
                '可回退续跑' if step.get('resume_allowed') else '不可逆，仅确认后提交',
            )
        )
    detail = _zoomed_detail(view)
    members = []
    for item in (detail or {}).get('members') or []:
        cost = item.get('cost') or {}
        hint = _cost_text(cost) or '无计费提交'
        members.append(
            '<li class="member %s" data-id="%s"><b>%s</b><span>%s</span></li>'
            % (
                escape(str(item.get('tone') or '')),
                escape(item['id']),
                escape(item.get('say') or item['id']),
                escape(hint),
            )
        )
    popup = view.get('option_popup') or {}
    options = []
    for item in popup.get('choices') or []:
        if item.get('kind') == 'rollback':
            cost = '回退到可逆检查点，不撤销已提交计费'
        else:
            cost = 'Hi3D 提交 × %s；MDF × %s（公开参考非实扣）' % (
                item.get('hi3d_submit_count', 0), item.get('mdf_invoke_count', 0))
        options.append(
            '<button type="button" class="option" data-kind="%s" data-target="%s">'
            '<b>%s</b><span>%s</span></button>'
            % (
                escape(str(item.get('kind') or '')),
                escape(str(item.get('target') or '')),
                escape(str(item.get('title') or item.get('id') or '')),
                escape(cost),
            )
        )
    dialog = ''
    if popup.get('visible') and (options or popup.get('web_options')):
        web_html, wide = _web_options_html(popup.get('web_options'))
        dialog = (
            '<dialog class="option-popup %s" open data-surface="popup" data-role="%s">'
            '<h2>请选择</h2>%s<div class="options">%s</div></dialog>'
            % (
                'wide' if wide else '',
                escape(str(popup.get('role') or 'option')),
                web_html,
                ''.join(options),
            )
        )
    hints = catalog.get('hints') or {}
    hint_text = '；'.join('%s %s' % (key, value) for key, value in hints.items())
    zoom_title = (detail or {}).get('label') or '当前节点'
    return """<!DOCTYPE html>
<html lang="zh-Hans"><head><meta charset="utf-8"/>
<title>%s</title>
<style>%s</style></head>
<body>
<div class="shell">
<nav class="rail" aria-label="任务步骤"><ol>%s</ol></nav>
<section class="main">
<h1>%s</h1>
<p class="note">Overview 为检查点路线投影，不是 skill 执行拆解。耗分写在进入该区的连线，以及放大后的节点上。额度方案走既有 option 弹窗。</p>
<div class="board overview">%s</div>
<h2>放大 · %s</h2>
<ul class="members">%s</ul>
%s
<p class="note">%s · %s</p>
<p class="note">%s</p>
</section>
</div>
</body></html>
""" % (
        escape(title),
        CSS,
        ''.join(rail),
        escape(title),
        svg_overview(view),
        escape(zoom_title),
        ''.join(members),
        dialog,
        escape(str(catalog.get('source') or '')),
        escape(str(catalog.get('as_of') or '')),
        escape(hint_text),
    )


BOARD_ZOOM_JS = (
    '(function(){var s=document.querySelector(".board-stage");if(!s)return;'
    'var p=s.querySelector(".board-pan"),v=s.querySelector("svg");if(!p||!v)return;'
    'var z=1,x=0,y=0,THRESHOLD=96;'
    'function apply(){p.style.transform="translate("+x+"px,"+y+"px) scale("+z+")";'
    'var lod=(168*z)>=THRESHOLD?"detail":"preview";s.setAttribute("data-lod",lod);'
    'var root=s.parentElement;root.querySelectorAll("[data-lod-btn]").forEach(function(b){b.setAttribute("aria-pressed",String(b.getAttribute("data-lod-btn")===lod));});}'
    'function fit(){var b=v.viewBox.baseVal,r=s.getBoundingClientRect();'
    'z=Math.min(r.width/Math.max(b.width,1),r.height/Math.max(b.height,1),0.95);'
    'x=(r.width-b.width*z)/2;y=(r.height-b.height*z)/2;apply();}'
    's.addEventListener("wheel",function(e){e.preventDefault();'
    'z=Math.max(0.12,Math.min(4,z*(e.deltaY<0?1.12:1/1.12)));apply();},{passive:false});'
    'var root=s.parentElement;'
    'var preview=root.querySelector("[data-lod-btn=preview]");'
    'var detail=root.querySelector("[data-lod-btn=detail]");'
    'if(preview)preview.onclick=fit;'
    'if(detail)detail.onclick=function(){z=Math.max(z,1.15);apply();};'
    'window.addEventListener("resize",fit);fit();})();'
)


def html_board(view, *, title='任务拆解架构'):
    if view.get('schema') != 'pcg.board.v1':
        raise ValueError('html_board requires pcg.board.v1')
    layout = (view.get('overview') or {}).get('layout') or 'tree'
    if layout == 'linear':
        heading = '线形进程'
        lead = '检查点从左到右前进；虚线回退到更早步骤。产物目录记录最后已知路径。cache 可按语义清理，keep 不清。'
        figure = '<div class="board">%s</div>' % svg_overview(view)
        script = ''
    else:
        heading = '任务拆解'
        lead = '总览只显示图形与色相；滚轮拉近后出现阶段名、spawn 入口与耗分。cache 可按语义清理，keep 不清。'
        figure = (
            '<div class="board-toolbar">'
            '<button type="button" data-lod-btn="preview" aria-pressed="true">总览</button>'
            '<button type="button" data-lod-btn="detail" aria-pressed="false">细节</button>'
            '<span class="board-legend" aria-hidden="true">'
            '<i class="agent" style="background:#9A8F7A"></i>'
            '<i class="local" style="background:#9A8F7A"></i>'
            '<i class="subagent" style="color:#2AA8A4"></i>'
            '</span></div>'
            '<div class="board-stage" data-lod="preview"><div class="board-pan">%s</div></div>'
            % svg_overview(view)
        )
        script = '<script>%s</script>' % BOARD_ZOOM_JS
    zoomed = _zoomed_detail(view)
    members = []
    zoom_title = '产物留痕'
    if zoomed:
        if zoomed.get('role') == 'artifact':
            zoom_title = (zoomed.get('say') or '') + ' · ' + str(zoomed.get('status') or 'pending')
        elif zoomed.get('role') == 'subagent':
            zoom_title = (zoomed.get('say') or '') + ' · subagent · ' + str(zoomed.get('entry') or '')
        else:
            zoom_title = (zoomed.get('say') or zoomed.get('id') or '') + ' · 本地阶段'
        for member in zoomed.get('members') or []:
            label = escape(member.get('say') or member.get('id') or '')
            href = member.get('href')
            if href:
                label = '<a href="%s">%s</a>' % (escape(href, quote=True), label)
            members.append(
                '<li class="member %s" data-id="%s">%s'
                '<small>%s</small></li>'
                % (
                    escape(member.get('tone') or 'reversible'),
                    escape(member.get('id') or ''),
                    label,
                    escape(_cost_text(member.get('cost') or {}) or (zoomed.get('path') or '待产物')),
                )
            )
    return (
        '<!doctype html><html lang="zh"><head><meta charset="utf-8"/>'
        '<title>%s</title><style>%s</style></head><body>'
        '<main class="wrap architecture">'
        '<section class="overview"><h1>%s</h1>'
        '<p class="lead">%s</p>'
        '%s</section>'
        '<aside class="zoom"><h2>%s</h2><ul class="members">%s</ul></aside>'
        '<section class="finder"><h2>产物目录</h2><ul>%s</ul></section>'
        '</main>%s</body></html>'
        % (
            escape(title),
            CSS,
            escape(heading),
            escape(lead),
            figure,
            escape(zoom_title),
            ''.join(members),
            ''.join(_finder_items(view)),
            script,
        )
    )


def _zoomed_detail(view):
    overview = view.get('overview') or {}
    root = overview.get('root')
    nodes = [node for node in overview.get('nodes') or [] if node.get('id') != root]
    artifacts = [node for node in nodes if node.get('role') == 'artifact']
    for node in artifacts:
        if node.get('status') == 'ready':
            return node
    if artifacts:
        return artifacts[0]
    for node in nodes:
        if node.get('state') in ('waiting_choice', 'running'):
            return node
    return nodes[0] if nodes else None


def _finder_items(view):
    items = []
    for entry in (view.get('catalog') or {}).get('artifacts') or []:
        locator = entry.get('href') or entry.get('path') or ''
        label = escape(entry.get('label') or entry.get('id') or '')
        meta = '%s · %s · %s' % (
            entry.get('status') or 'pending',
            entry.get('retain') or 'keep',
            '+'.join(entry.get('semantics') or []) or '无语义',
        )
        if locator and entry.get('status') != 'purged':
            label = '<a href="%s">%s</a>' % (escape(locator, quote=True), label)
        elif locator:
            label = '%s <small>%s</small>' % (label, escape(locator))
        items.append(
            '<li class="member" data-id="%s">%s<small>%s</small></li>'
            % (escape(entry.get('id') or ''), label, escape(meta))
        )
    return items


def _cost_text(cost):
    parts = []
    if cost.get('hi3d_submit_count'):
        parts.append('Hi3D × %s' % cost['hi3d_submit_count'])
    if cost.get('mdf_invoke_count'):
        parts.append('MDF × %s' % cost['mdf_invoke_count'])
    return '；'.join(parts)


def _popup_prompt(_web):
    return '请选择您要使用的 Hi3D 生成参数'


def _web_options_html(web):
    if not isinstance(web, dict) or not web.get('groups'):
        return '', False
    groups = []
    for group in web['groups']:
        chips = []
        for option in group.get('options') or []:
            is_gem = option.get('badge') == 'diamond' or option.get('member')
            show_gem = is_gem and web.get('identity') != 'member'
            gem = '<i class="gem" title="会员"></i>' if show_gem else ''
            pressed = 'true' if option.get('selected') else 'false'
            disabled = ' disabled' if not option.get('enabled') else ''
            extra = ' title="%s"' % escape(str(option.get('id') or option.get('label') or ''))
            label = str(option.get('description') or option.get('label') or option.get('id') or '')
            chips.append(
                '<button type="button" class="chip" data-group="%s" data-id="%s" '
                'aria-pressed="%s"%s%s>%s%s</button>'
                % (
                    escape(str(group.get('id') or '')),
                    escape(str(option.get('id') or '')),
                    pressed,
                    disabled,
                    extra,
                    gem,
                    escape(label),
                )
            )
        groups.append(
            '<div class="web-group" data-id="%s"><span class="label">%s</span>'
            '<div class="chips">%s</div></div>'
            % (
                escape(str(group.get('id') or '')),
                escape(str(group.get('label') or group.get('id') or '')),
                ''.join(chips),
            )
        )
    hint = '<p class="option-hint">%s</p>' % escape(_popup_prompt(web))
    body = '<div class="web-groups">%s</div>' % ''.join(groups)
    return hint + body, True
