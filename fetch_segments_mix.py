#!/usr/bin/env python3
"""주요제품 매출구성(정기보고서 기준) 수집 — navercomp.wisereport c1020001 chartData1.
사용: python3 fetch_segments_mix.py  → segments_mix.json {code: {"period":"2026/06","items":[[name,pct],...]}}"""
import json,os,re,urllib.request,concurrent.futures as cf
B=os.path.dirname(os.path.abspath(__file__))
codes=sorted({d['code'] for d in json.load(open(os.path.join(B,'parsed_disclosures.json')))['disclosures']})
def get(c):
    try:
        r=urllib.request.Request(f'https://navercomp.wisereport.co.kr/v2/company/c1020001.aspx?cmp_cd={c}',headers={'User-Agent':'Mozilla/5.0'})
        s=urllib.request.urlopen(r,timeout=15).read().decode('utf-8','ignore')
        m=re.search(r'var chartData1 = (\[.*?\]);',s); p=re.search(r'주요제품 매출구성\((\d{4} / \d{2})\)',s)
        items=json.loads(m.group(1)) if m else []
        return c,{'period':p.group(1).replace(' ','') if p else '','items':items}
    except Exception as e: return c,{'period':'','items':[],'error':str(e)[:80]}
with cf.ThreadPoolExecutor(8) as ex: out=dict(ex.map(get,codes))
json.dump(out,open(os.path.join(B,'segments_mix.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
ok=sum(1 for v in out.values() if v['items']); print(f'[segments] ✓ {ok}/{len(out)} 매출구성 확보')
print('미확보:',[c for c,v in out.items() if not v['items']])
