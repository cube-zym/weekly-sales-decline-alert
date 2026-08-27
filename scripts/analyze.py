#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""周度销量环比分析：从 listing_p*.json 计算下跌 ASIN，聚合负责人，生成 HTML 报告。
用法:
  analyze.py <data_dir> --threshold 0.1 --out decline.json          # 计算下跌清单
  analyze.py <data_dir> --html --deep deep.json --out report.html   # 生成 HTML（需先有 decline.json）
"""
import json, glob, os, sys, html

def to_num(v, default=0):
    try:
        if v in (None, ''):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default

def load_listing(path):
    raw = open(path, encoding='utf-8').read().strip()
    if raw.startswith('{'):
        resp = json.loads(raw)
    else:
        data = [l[5:] for l in raw.splitlines() if l.startswith('data: ')]
        resp = json.loads(data[-1])
    return json.loads(resp['result']['content'][0]['text'])['data']['data']['list']

def compute(data_dir, threshold=0.0):
    rows = []
    for p in sorted(glob.glob(os.path.join(data_dir, 'listing_p*.json'))):
        rows.extend(load_listing(p))
    seen = {}
    for r in rows:
        a = r.get('asin')
        if a and a not in seen:
            seen[a] = r
    rows = list(seen.values())

    out = []
    for r in rows:
        avg7 = to_num(r.get('average_seven_volume'))
        seven = round(avg7 * 7)
        prev = round(to_num(r.get('fourteen_volume'))) - seven
        if seven <= 0 or prev <= 0:
            continue
        pct = (prev - seven) / prev
        if pct <= 0:          # 只保留环比下跌（上涨/持平剔除）
            continue
        if threshold and pct < threshold:
            continue
        out.append({
            'asin': r['asin'],
            'item': r.get('item_name') or '',
            'local': r.get('local_name') or '',
            'msku': r.get('msku') or '',
            'principal': r.get('principal_realname') or '',
            'price': to_num(r.get('price')),
            'seven': seven,
            'prev': prev,
            'seven_amt': round(to_num(r.get('seven_amount'))),
            'prev_amt': round(to_num(r.get('fourteen_amount')) - to_num(r.get('seven_amount'))),
            'seven_spend': round(to_num(r.get('seven_spend'))),
        })
    out.sort(key=lambda d: (d['prev'] - d['seven']) / d['prev'], reverse=True)
    return out

def by_owner(declined):
    from collections import defaultdict
    agg = defaultdict(lambda: {'count': 0, 'loss': 0, 'asins': []})
    for d in declined:
        loss = d['prev'] - d['seven']
        owners = [o.strip() for o in (d['principal'] or '').split(',') if o.strip()]
        for o in owners or ['未分配']:
            agg[o]['count'] += 1
            agg[o]['loss'] += loss
            agg[o]['asins'].append((d['asin'], loss, d['local'] or d['item']))
    result = []
    for o, v in agg.items():
        v['asins'].sort(key=lambda x: -x[1])
        result.append({'owner': o, 'count': v['count'], 'loss': v['loss'], 'top': v['asins'][:3]})
    result.sort(key=lambda x: -x['loss'])
    return result

def gen_html(declined, owners, deep=None, out_path='report.html'):
    esc = lambda s: html.escape(str(s or ''))
    def pct_class(pct):
        return 'sev' if pct >= 30 else 'hi' if pct >= 20 else 'mid' if pct >= 10 else 'low'

    rows = []
    for d in declined:
        pct = (d['prev'] - d['seven']) / d['prev'] * 100
        name = (d['local'] or d['item'])[:34]
        rows.append(f"<tr><td class='mono'>{d['asin']}</td><td>{esc(name)}<div class='sub'>{esc(d['item'][:58])}</div></td><td class='mono'>{esc(d['msku'])}</td><td class='num'>${d['price']:.2f}</td><td class='num'>{d['prev']}</td><td class='num'>{d['seven']}</td><td class='num'>{d['prev']-d['seven']}</td><td class='num'><span class='pill {pct_class(pct)}'>-{pct:.0f}%</span></td><td>{esc(d['principal'])}</td></tr>")
    owner_rows = []
    total_loss = sum(d['prev'] - d['seven'] for d in declined)
    for o in owners:
        top3 = '、'.join(f"{a} -{l}件" for a, l, _ in o['top'])
        owner_rows.append(f"<tr><td><b>{esc(o['owner'])}</b></td><td class='num'>{o['count']}</td><td class='num'>{o['loss']:,}</td><td class='num'>{o['loss']/total_loss*100:.0f}%</td><td class='mono'>{esc(top3)}</td></tr>")

    deep_rows = ''
    if deep:
        INFO = deep.get('info', {})
        TRAF = deep.get('traffic', {})
        TOP = deep.get('order', [])
        def attr(a):
            d = next((x for x in declined if x['asin'] == a), None)
            if not d:
                return ''
            pct = (d['prev'] - d['seven']) / d['prev'] * 100
            i, t = INFO.get(a, {}), TRAF.get(a, {})
            price = i.get('price'); stars = i.get('stars')
            org = t.get('organic'); ad = t.get('ad'); orp = t.get('or_pos')
            price_s = f"{price[0]} → {price[1]}" if price and price[0] else '持平'
            stars_s = f"{stars[0]}→{stars[1]}" if stars else '—'
            org_s = f"{org[0]} → {org[1]}" if org else '—'
            ad_s = f"{ad[0]} → {ad[1]}" if ad else '—'
            or_s = f"{orp[0]} → {orp[1]}" if orp else '—'
            reasons = []
            if price and price[0] and price[1]:
                try:
                    diff = float(price[1]) - float(price[0])
                    if diff > 0: reasons.append(f'<span class="pill sev">涨价 ${diff:.2f}</span>')
                    elif diff < 0: reasons.append('<span class="pill warn2">降价仍跌</span>')
                except ValueError:
                    pass
            if org:
                if org[1] < org[0] * 0.8: reasons.append(f'<span class="pill sev">自然流量 -{(1-org[1]/org[0])*100:.0f}%</span>')
                if ad and ad[1] < ad[0] * 0.6: reasons.append(f'<span class="pill hi">广告流量 -{(1-ad[1]/ad[0])*100:.0f}%</span>')
            if not reasons: reasons.append('<span class="pill mid">流量平稳，查转化/竞争</span>')
            return f"<tr><td class='mono'>{a}</td><td>{esc((d['local'] or d['item'])[:22])}</td><td class='num'><span class='pill {pct_class(pct)}'>-{pct:.0f}%</span></td><td>{price_s}</td><td>{stars_s}</td><td class='num'>{org_s}<div class='sub'>自然位 {or_s}</div></td><td class='num'>{ad_s}</td><td>{' '.join(reasons)}</td></tr>"
        deep_rows = ''.join(attr(a) for a in TOP)

    over30 = sum(1 for d in declined if (d['prev']-d['seven'])/d['prev'] >= 0.30)
    over20 = sum(1 for d in declined if 0.20 <= (d['prev']-d['seven'])/d['prev'] < 0.30)

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>周度销量下跌 ASIN 预警</title>
<style>
:root {{ --red:#dc2626; --red-bg:#fef2f2; --amber:#d97706; --amber-bg:#fffbeb; --line:#e2e8f0; --bg:#f5f7fb; --card:#fff; --ink:#1e293b; --muted:#64748b; --primary:#1d4ed8; --primary-light:#dbeafe; --primary-dark:#1e3a8a; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink); background:var(--bg); font-size:14px; line-height:1.7; }}
.hero {{ background:linear-gradient(135deg,#0f172a,#1e3a8a 55%,#1d4ed8); color:#fff; padding:40px 24px; }}
.hero-inner {{ max-width:1180px; margin:0 auto; }}
.hero h1 {{ font-size:26px; }} .hero .sub {{ color:#c7d8f7; font-size:14px; margin-top:6px; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 24px; }}
.kpi-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:-30px 0 10px; position:relative; z-index:2; }}
.kpi {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px 14px; box-shadow:0 1px 3px rgba(15,23,42,.08); }}
.kpi .k {{ font-size:12px; color:var(--muted); }} .kpi .v {{ font-size:20px; font-weight:700; color:var(--primary-dark); }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:12px 0; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th,td {{ border:1px solid var(--line); padding:6px 9px; text-align:left; }}
th {{ background:#f1f5f9; position:sticky; top:0; }}
tr:nth-child(even) td {{ background:#fafbfd; }}
.num {{ text-align:right; }} .mono {{ font-family:ui-monospace,Menlo,monospace; font-size:12px; }}
.sub {{ color:var(--muted); font-size:11px; }}
.pill {{ display:inline-block; font-size:11.5px; font-weight:700; padding:1px 8px; border-radius:999px; }}
.pill.sev {{ background:var(--red-bg); color:var(--red); }} .pill.hi {{ background:#fff7ed; color:#ea580c; }}
.pill.mid {{ background:var(--amber-bg); color:var(--amber); }} .pill.low {{ background:#f1f5f9; color:var(--muted); }}
.pill.warn2 {{ background:#f0fdf4; color:var(--amber); }}
.table-wrap {{ overflow-x:auto; max-height:60vh; overflow-y:auto; border:1px solid var(--line); border-radius:10px; }}
.note {{ font-size:12px; color:var(--muted); margin-top:10px; border-top:1px dashed var(--line); padding-top:8px; }}
@media print {{ .table-wrap {{ max-height:none; }} }}
</style></head><body>
<header class="hero"><div class="hero-inner">
  <h1>周度销量下跌 ASIN 预警</h1>
  <p class="sub">数据源：领星 ERP · 生成时间 {esc(__import__('datetime').date.today())}</p>
</div></header>
<div class="wrap">
  <div class="kpi-row">
    <div class="kpi"><div class="k">下跌 ASIN</div><div class="v">{len(declined)}</div></div>
    <div class="kpi"><div class="k">跌幅 ≥30%</div><div class="v">{over30}</div></div>
    <div class="kpi"><div class="k">跌幅 20-30%</div><div class="v">{over20}</div></div>
    <div class="kpi"><div class="k">周损失合计</div><div class="v">{total_loss:,} 件</div></div>
  </div>
  {f"<div class='card'><h3 style='font-size:15px'>跌幅 Top10 归因</h3><table><tr><th>ASIN</th><th>品名</th><th class='num'>跌幅</th><th>价格</th><th>评分</th><th class='num'>自然流量</th><th class='num'>广告流量</th><th>归因</th></tr>{deep_rows}</table></div>" if deep_rows else ""}
  <div class="card"><h3 style="font-size:15px">按负责人汇总</h3>
    <div class="table-wrap" style="max-height:40vh"><table>
      <tr><th>负责人</th><th class="num">下跌数</th><th class="num">周损失</th><th class="num">占比</th><th>TOP3 ASIN</th></tr>
      {''.join(owner_rows)}
    </table></div>
  </div>
  <div class="card"><h3 style="font-size:15px">完整下跌清单（{len(declined)} 条）</h3>
    <div class="table-wrap"><table>
      <tr><th>ASIN</th><th style="min-width:190px">品名</th><th>MSKU</th><th class="num">售价</th><th class="num">上上周</th><th class="num">上周</th><th class="num">周差</th><th class="num">跌幅</th><th>负责人</th></tr>
      {''.join(rows)}
    </table></div>
  </div>
  <p class="note">* 上周 = average_seven_volume×7；上上周 = fourteen_volume − 上周；仅统计两周均有销量的 ASIN。</p>
</div>
</body></html>"""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(doc)
    return out_path

if __name__ == '__main__':
    data_dir = sys.argv[1]
    args = sys.argv[2:]
    threshold = 0.0
    out = None
    html_mode = False
    deep_path = None
    if '--threshold' in args:
        threshold = float(args[args.index('--threshold') + 1])
    if '--out' in args:
        out = args[args.index('--out') + 1]
    if '--html' in args:
        html_mode = True
    if '--deep' in args:
        deep_path = args[args.index('--deep') + 1]

    declined = compute(data_dir, threshold)
    if html_mode:
        owners = by_owner(declined)
        deep = json.load(open(deep_path)) if deep_path and os.path.exists(deep_path) else None
        out = gen_html(declined, owners, deep, out or os.path.join(data_dir, 'report.html'))
        print(f"HTML 已生成: {out}（{len(declined)} 条下跌）")
    else:
        out = out or os.path.join(data_dir, 'decline.json')
        json.dump(declined, open(out, 'w'), ensure_ascii=False)
        print(f"下跌 ASIN: {len(declined)} 个 → {out}")
