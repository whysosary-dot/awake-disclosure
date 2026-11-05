#!/usr/bin/env python3
"""증권사 컨센서스·밸류에이션·최근 리포트 수집 — m.stock.naver.com integration API.
사용: python3 fetch_consensus.py → consensus.json
{code: {target_mean, recomm_mean(1~5, 높을수록 매수), cns_date, per, cns_per, pbr, eps, cns_eps, div_yield, reports:[{broker,title,date}]}}"""
import json,os,urllib.request,concurrent.futures as cf
B=os.path.dirname(os.path.abspath(__file__))
codes=sorted({d['code'] for d in json.load(open(os.path.join(B,'parsed_disclosures.json')))['disclosures']})
K={'per':'per','cnsPer':'cns_per','pbr':'pbr','eps':'eps','cnsEps':'cns_eps','dividendYieldRatio':'div_yield'}
def get(c):
    try:
        r=urllib.request.Request(f'https://m.stock.naver.com/api/stock/{c}/integration',headers={'User-Agent':'Mozilla/5.0'})
        d=json.loads(urllib.request.urlopen(r,timeout=15).read())
        ci=d.get('consensusInfo') or {}
        o={'target_mean':ci.get('priceTargetMean'),'recomm_mean':ci.get('recommMean'),'cns_date':ci.get('createDate')}
        for t in d.get('totalInfos') or []:
            if t.get('code') in K: o[K[t['code']]]=t.get('value')+(f" ({t['valueDesc']})" if t.get('valueDesc') else '')
        o['reports']=[{'broker':x.get('bnm'),'title':x.get('tit'),'date':x.get('wdt')} for x in (d.get('researches') or [])[:5]]
        return c,o
    except Exception as e: return c,{'error':str(e)[:80],'reports':[]}
with cf.ThreadPoolExecutor(8) as ex: out=dict(ex.map(get,codes))
json.dump(out,open(os.path.join(B,'consensus.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f"[consensus] 목표주가 {sum(1 for v in out.values() if v.get('target_mean'))}/{len(out)} | 리포트 {sum(1 for v in out.values() if v.get('reports'))}/{len(out)} | PER {sum(1 for v in out.values() if v.get('per'))}/{len(out)}")
