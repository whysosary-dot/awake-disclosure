#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_prices_all.py  v5  — 네이버 polling API (가격+거래량 완전 수집)
  - __file__ 기반 경로 자동감지
  - polling.finance.naver.com/api/realtime/domestic/stock/{code}
  - 가격·등락률·거래량 모두 수집
  - ~15초 / 130종목, 타임아웃 없음
"""
import json, sys, os, pathlib, time, urllib.request

_HERE  = pathlib.Path(__file__).resolve().parent
OUTDIR = str(_HERE)
PARSED = os.path.join(OUTDIR, "parsed_disclosures.json")
OUT    = os.path.join(OUTDIR, "prices_all.json")

with open(PARSED, encoding="utf-8") as f:
    parsed = json.load(f)
codes = sorted({d["code"] for d in parsed["disclosures"] if d.get("code")})
print(f"[prices] 총 {len(codes)}종목", file=sys.stderr)

prices = {}
if os.path.exists(OUT):
    try:
        prices = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        prices = {}
    print(f"[prices] 캐시 {len(prices)}건", file=sys.stderr)

remaining = [c for c in codes if c not in prices or not prices[c]
             or prices[c].get("close", 0) == 0]
if not remaining:
    print("[prices] 전종목 캐시 완료", file=sys.stderr)
    sys.exit(0)
print(f"[prices] 신규 수집: {len(remaining)}건", file=sys.stderr)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://finance.naver.com",
}

def naver_polling(code):
    """polling 엔드포인트: 가격·등락률·거래량 모두 포함."""
    url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.loads(r.read())
        data = d.get("datas", [{}])[0] if d.get("datas") else {}
        close_s = str(data.get("closePrice", "0")).replace(",", "")
        prev_s  = str(data.get("compareToPreviousClosePrice", "0")).replace(",", "")
        chg_s   = str(data.get("fluctuationsRatio", "0")).replace(",", "")
        vol_s   = str(data.get("accumulatedTradingVolumeRaw",
                    data.get("accumulatedTradingVolume", "0"))).replace(",", "")
        sosok   = str(data.get("stockExchangeType", {}).get("code", "KOSPI"))
        sfx     = ".KQ" if sosok in ("KOSDAQ", "KONEX") else ".KS"
        close = float(close_s) if close_s else 0.0
        prev  = close - float(prev_s) if prev_s else close
        chg   = float(chg_s) if chg_s else 0.0
        vol   = int(float(vol_s)) if vol_s and vol_s not in ("", "0") else 0
        if close == 0:
            return None
        return {"symbol": code + sfx, "close": close,
                "prev_close": round(prev, 2), "chg_pct": chg, "volume": vol}
    except Exception:
        pass
    # fallback: /basic 엔드포인트 (거래량 없음)
    try:
        url2 = f"https://m.stock.naver.com/api/stock/{code}/basic"
        req2 = urllib.request.Request(url2, headers=HEADERS)
        with urllib.request.urlopen(req2, timeout=6) as r:
            d2 = json.loads(r.read())
        close_s = str(d2.get("closePrice", "0")).replace(",", "")
        prev_s  = str(d2.get("compareToPreviousClosePrice", "0")).replace(",", "")
        chg_s   = str(d2.get("fluctuationsRatio", "0")).replace(",", "")
        sosok   = str(d2.get("stockExchangeType", {}).get("code", "KOSPI"))
        sfx     = ".KQ" if sosok in ("KOSDAQ", "KONEX") else ".KS"
        close = float(close_s.replace(",","")) if close_s else 0.0
        prev  = close - float(prev_s.replace(",","")) if prev_s else close
        chg   = float(chg_s.replace(",","")) if chg_s else 0.0
        if close == 0:
            return None
        return {"symbol": code + sfx, "close": close,
                "prev_close": round(prev, 2), "chg_pct": chg, "volume": 0}
    except Exception:
        return None

ok_count, fail_list = 0, []
for i, code in enumerate(remaining, 1):
    row = naver_polling(code)
    if row:
        prices[code] = row
        ok_count += 1
    else:
        fail_list.append(code)
    if i % 20 == 0:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(prices, f, ensure_ascii=False)
        print(f"[prices]  [{i}/{len(remaining)}] 성공 {ok_count}  실패 {len(fail_list)}", file=sys.stderr)
    time.sleep(0.08)

if fail_list:
    print(f"[prices] yfinance fallback: {len(fail_list)}건", file=sys.stderr)
    try:
        sys.path.insert(0, "/dev/shm/pypackages")
        import yfinance as yf, pandas as pd
        syms_ks = [f"{c}.KS" for c in fail_list]
        raw = yf.download(tickers=syms_ks, period="5d", auto_adjust=False,
                          progress=False, threads=True, timeout=25)
        if not raw.empty:
            is_multi = isinstance(raw.columns, pd.MultiIndex)
            for c in fail_list:
                sym = f"{c}.KS"
                try:
                    cs = raw["Close"][sym].dropna() if is_multi else raw["Close"].dropna()
                    vs = raw["Volume"][sym].dropna() if is_multi else raw["Volume"].dropna()
                    if len(cs) < 1: continue
                    cl = float(cs.iloc[-1]); pv = float(cs.iloc[-2]) if len(cs)>=2 else cl
                    prices[c] = {"symbol": sym, "close": round(cl,2),
                                 "prev_close": round(pv,2),
                                 "chg_pct": round((cl-pv)/pv*100 if pv else 0, 2),
                                 "volume": int(float(vs.iloc[-1])) if not vs.empty else 0}
                except Exception: pass
    except Exception as e:
        print(f"[prices] yf 실패: {e}", file=sys.stderr)
    for c in fail_list:
        if c not in prices: prices[c] = None

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(prices, f, ensure_ascii=False, indent=2)
ok_t  = sum(1 for v in prices.values() if v and v.get("close",0)>0)
fail_t = len(prices) - ok_t
print(f"[prices] ✓ {ok_t}건 수집  {fail_t}건 수집불가  → {OUT}", file=sys.stderr)
