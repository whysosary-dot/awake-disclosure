#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_naver_finance.py  v2  — 네이버 금융 기업실적분석 수집
  - __file__ 기반 경로 자동감지 (하드코딩 세션경로 없음)
  - 배치 25건씩 처리 (타임아웃 방지)
  - 리츠/신규상장 등 실적표 없는 종목은 정상 처리
"""
import json, re, time, sys, urllib.request, os, pathlib

_HERE  = pathlib.Path(__file__).resolve().parent
OUTDIR = str(_HERE)
PARSED = os.path.join(OUTDIR, "parsed_disclosures.json")
OUT    = os.path.join(OUTDIR, "naver_finance.json")

def fetch(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ["utf-8", "euc-kr", "cp949"]:
        try: return raw.decode(enc)
        except: pass
    return raw.decode("utf-8", errors="ignore")

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip().strip(">").strip()

def parse(html):
    m = re.search(r'<table[^>]+summary="[^"]*기업실적[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not m: return None
    tbl = m.group(0)
    periods = []
    hm = re.search(r"<thead.*?</thead>", tbl, re.DOTALL)
    if hm:
        for th in re.finditer(r"<th[^>]*>(.*?)</th>", hm.group(0), re.DOTALL):
            pm = re.search(r"(\d{4}[./]\d{2})", clean(th.group(1)))
            if pm: periods.append(pm.group(1))
    rows = {}
    bm = re.search(r"<tbody.*?</tbody>", tbl, re.DOTALL)
    if bm:
        for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", bm.group(0), re.DOTALL):
            tm = re.search(r"<th[^>]*>(.*?)</th>", tr.group(1), re.DOTALL)
            if not tm: continue
            metric = clean(tm.group(1))
            if not metric or "주요재무" in metric: continue
            rows[metric] = [clean(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), re.DOTALL)]
    return {"periods": periods, "rows": rows} if (periods or rows) else None

with open(PARSED, encoding="utf-8") as f:
    parsed = json.load(f)
codes = sorted({d["code"] for d in parsed["disclosures"] if d.get("code")})
print(f"[naver] 총 {len(codes)}종목", file=sys.stderr)

out = {}
if os.path.exists(OUT):
    try: out = json.load(open(OUT, encoding="utf-8"))
    except: out = {}

# rows 없는 종목만 재수집 (에러 포함, no_table 제외)
remaining = [c for c in codes
             if c not in out
             or (out[c] and out[c].get("error") and "no_table" not in str(out[c].get("note","")))]
print(f"[naver] 수집 필요: {len(remaining)}건", file=sys.stderr)

# 배치 사이즈: 인자로 받거나 기본 25
batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 25
batch = remaining[:batch_size]

ok, fail = 0, 0
for code in batch:
    try:
        html = fetch(f"https://finance.naver.com/item/main.naver?code={code}")
        r = parse(html)
        if r and r.get("rows"):
            out[code] = r; ok += 1
        else:
            out[code] = {"error": "no_table", "note": "재무표 없음(리츠/신규상장 등)"}; fail += 1
    except Exception as e:
        out[code] = {"error": str(e)}; fail += 1
    time.sleep(0.1)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

done = sum(1 for v in out.values() if v and "rows" in v and v["rows"])
print(f"[naver] ✓ 이번 배치 {ok}/{len(batch)} | 누적 {done}/{len(codes)}", file=sys.stderr)
if len(remaining) > batch_size:
    print(f"[naver] 잔여 {len(remaining)-batch_size}건 — 재실행 필요", file=sys.stderr)
