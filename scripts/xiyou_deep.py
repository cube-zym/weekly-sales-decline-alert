#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""西柚跌幅 Top N 归因：两周价格/评分/评论 + 自然/广告流量对比（凭证从 config.json 读取）。
用法: xiyou_deep.py <data_dir> --top 10 [--decline decline.json]
输出: <data_dir>/deep.json  {info:{asin:{...}}, traffic:{asin:{...}}, order:[asins]}
"""
import json, os, sys, glob, subprocess
from datetime import date, timedelta

def week_range():
    """返回 (上上周一, 上周日) 与 (上上周一, 上周日) 的日期字符串——按最近两个完整自然周计算"""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    last_start = this_monday - timedelta(days=7)   # 上周一
    prev_start = last_start - timedelta(days=7)    # 上上周一
    last_end = this_monday - timedelta(days=1)     # 上周日
    return str(prev_start), str(last_end), str(last_start), str(last_end)

def load_cfg():
    cfg = json.load(open(os.path.expanduser('~/.zcode/cli/config.json')))
    s = cfg['mcp']['servers']['xydc-mcp']
    return s['url'], s['headers']['Authorization']

def call_tool(url, auth, name, args):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": name, "arguments": args}})
    r = subprocess.run(['curl', '-s', '-m', '45', '-X', 'POST', url,
                        '-H', 'Content-Type: application/json',
                        '-H', 'Accept: application/json, text/event-stream',
                        '-H', 'Authorization: ' + auth,
                        '-d', payload], capture_output=True, text=True)
    raw = r.stdout.strip()
    if raw.startswith('{'):
        resp = json.loads(raw)
    else:
        data = [l[5:] for l in raw.splitlines() if l.startswith('data: ')]
        resp = json.loads(data[-1])
    return json.loads(resp['result']['content'][0]['text'])

def main():
    data_dir = sys.argv[1]
    args = sys.argv[2:]
    top = 10
    if '--top' in args:
        top = int(args[args.index('--top') + 1])
    decline_path = args[args.index('--decline') + 1] if '--decline' in args else os.path.join(data_dir, 'decline.json')

    declined = json.load(open(decline_path))
    top_asins = [d['asin'] for d in declined[:top]]
    url, auth = load_cfg()

    USER_TASK = "分析上周环比上上周销量下跌的ASIN，深挖跌幅Top原因（价格/评分/流量变化）"
    prev_start, last_end, last_start, _ = week_range()
    info, traffic = {}, {}
    for a in top_asins:
        try:
            obj = call_tool(url, auth, 'get_asin_info_trends', {
                'asin': a, 'country': 'US', 'start_date': prev_start, 'end_date': last_end,
                'user_task': USER_TASK, 'intent_summary': '查询该ASIN两周内价格评分评论数变化'})
            t = obj.get('data', {}).get('trends') or []
            if t:
                f, l = t[0], t[-1]
                def disp(x):
                    return (x.get('priceDistribution') or {}).get('display')
                info[a] = {'price': (disp(f), disp(l)), 'stars': (f.get('stars'), l.get('stars')),
                           'ratings': (f.get('ratings'), l.get('ratings'))}
        except Exception as e:
            info[a] = {'error': str(e)}
        try:
            obj = call_tool(url, auth, 'get_asin_traffic_trends_weekly', {
                'asin': a, 'country': 'US', 'start_week': prev_start, 'end_week': last_end,
                'user_task': USER_TASK, 'intent_summary': '查询该ASIN近两周自然与广告流量变化'})
            t = obj.get('data', {}).get('trends') or []
            if t:
                f, l = t[0], t[-1]
                traffic[a] = {
                    'organic': (f['summaryTrafficScore']['organic'], l['summaryTrafficScore']['organic']),
                    'ad': (f['summaryTrafficScore']['advertising'], l['summaryTrafficScore']['advertising']),
                    'or_pos': (f['positionTrafficScore']['or'], l['positionTrafficScore']['or']),
                    'sp_pos': (f['positionTrafficScore']['sp'], l['positionTrafficScore']['sp']),
                }
        except Exception as e:
            traffic[a] = {'error': str(e)}
        print(f"  {a} done")

    out = {'info': info, 'traffic': traffic, 'order': top_asins}
    out_path = os.path.join(data_dir, 'deep.json')
    json.dump(out, open(out_path, 'w'), ensure_ascii=False)
    print(f"归因完成: {len(top_asins)} 个 ASIN → {out_path}")

if __name__ == '__main__':
    main()
