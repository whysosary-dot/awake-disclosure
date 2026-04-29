#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘 공시된 모든 종목 일괄 재분석 트리거 스크립트.

사용자 명시 정책 (2026-04-30):
"기존이든 신규든 구분없이 매일 새로 분석해."

매일 스케줄 실행 시 첫 단계로 호출.
오늘 공시된 ALL 종목을 WebSearch + 새 분석 대상으로 출력.
enriched_overrides.json의 BM/segments/strength/customers는 baseline으로 활용,
custom_signal_reason/insight/watch는 매일 새로 작성하여 daily_analyses_YYYY-MM-DD.json에 저장.
"""
import json
import os
import sys
import glob
import datetime as dt

# Auto-detect session path
candidates = glob.glob("/sessions/*/mnt/outputs/parsed_disclosures.json")
if not candidates:
    print("❌ parsed_disclosures.json 미발견. fetch_awake.py + parse_messages.py 먼저 실행하세요.", file=sys.stderr)
    sys.exit(1)

PARSED = candidates[0]
SESSION_OUT = os.path.dirname(PARSED)
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
DAILY_OUT = f"{SESSION_OUT}/daily_analyses_{TODAY}.json"
OVERRIDES = f"{SESSION_OUT}/enriched_overrides.json"


def main():
    with open(PARSED, encoding="utf-8") as f:
        parsed = json.load(f)

    # All disclosure companies today
    today_codes = {}
    for d in parsed.get("disclosures", []):
        c = d["code"]
        if c not in today_codes:
            today_codes[c] = {"company": d["company"], "reports": [], "rcpNos": []}
        today_codes[c]["reports"].append(d["report"])
        today_codes[c]["rcpNos"].append(d.get("rcpNo", ""))

    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as f:
            overrides = json.load(f)

    print(f"📊 오늘 ({TODAY}) 공시 종목 전수 분석 대상:")
    print(f"  - 총 종목: {len(today_codes)}")
    print(f"  - enriched_overrides 베이스 데이터(BM/segments) 보유: "
          f"{sum(1 for c in today_codes if c in overrides and 'bm' in overrides[c])}")
    print(f"  - **모든 종목 매일 새 WebSearch + 새 분석 필요 (사용자 명시 정책)**")
    print()
    print("=" * 70)
    print(f"🔥 사용자 정책 (2026-04-30 명시):")
    print(f"   '기존이든 신규든 구분없이 매일 새로 분석해.'")
    print(f"   ─ 매일 모든 종목 WebSearch + 새 분석 작성")
    print(f"   ─ daily_analyses_{TODAY}.json에 저장")
    print(f"   ─ enriched_overrides.json은 BM/segments/strength/customers")
    print(f"     베이스라인 (정적 데이터)만 유지")
    print(f"   ─ custom_signal_reason/insight/watch는 매일 새 컨텍스트로 작성")
    print("=" * 70)
    print()

    # Group by category for easier batch processing
    from collections import defaultdict
    by_cat = defaultdict(list)
    for code, info in today_codes.items():
        primary_rep = info["reports"][0]
        if "잠정실적" in primary_rep or "영업(잠정)실적" in primary_rep:
            cat = "잠정실적"
        elif "기업설명회" in primary_rep or "IR" in primary_rep:
            cat = "IR"
        elif "단일판매" in primary_rep and "체결" in primary_rep:
            cat = "단일판매"
        elif "공급계약해지" in primary_rep:
            cat = "공급해지"
        elif "회사합병" in primary_rep:
            cat = "합병"
        elif "전환사채" in primary_rep and "발행" in primary_rep:
            cat = "CB발행"
        elif "전환청구" in primary_rep:
            cat = "전환청구"
        elif "유상증자" in primary_rep:
            cat = "유증"
        elif "자기주식취득" in primary_rep or "주식소각" in primary_rep:
            cat = "자사주매입소각"
        elif "자기주식처분" in primary_rep:
            cat = "자사주처분"
        elif "타법인주식" in primary_rep:
            cat = "타법인출자"
        elif "대량보유" in primary_rep:
            cat = "대량보유"
        elif "기업가치제고" in primary_rep:
            cat = "밸류업"
        elif "투자판단" in primary_rep:
            cat = "투자판단"
        elif "현금" in primary_rep and "배당" in primary_rep:
            cat = "배당"
        elif "경영권분쟁" in primary_rep or "소송" in primary_rep:
            cat = "분쟁"
        elif "풍문" in primary_rep or "해명" in primary_rep:
            cat = "해명"
        else:
            cat = "기타"
        by_cat[cat].append((code, info["company"], info["reports"]))

    print(f"📋 카테고리별 종목 분포:")
    for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        print(f"  - {cat}: {len(items)}개")
    print()

    print("📝 LLM 에이전트 작업 가이드:")
    print("=" * 70)
    print("1. 카테고리별 또는 종목별로 진행")
    print("2. 각 종목당 WebSearch 2-4건:")
    print("   - 회사명 + 공시 카테고리 + 2026 1분기 (또는 최신 사이클)")
    print("   - 회사명 + 애널리스트 + 목표주가 + 컨센서스")
    print("   - 회사명 + 동종업계 + 산업 트렌드")
    print("   - (필요 시) 본문 keyword + 최신 정책·뉴스")
    print()
    print("3. 검색 결과 + 본문 정량 + 산업 분류로 풀 v9 분석 작성:")
    print("   {")
    print("     \"custom_signal_reason\": \"...본문 정량 + 컨센 + 분기 추이...\",")
    print("     \"custom_insight\": \"...단기·중기·장기 + 산업 사이클 + 위험요인...\",")
    print("     \"custom_watch\": [...5-7개 구체 일정·수치...]")
    print("   }")
    print()
    print(f"4. daily_analyses_{TODAY}.json에 종목별 저장")
    print("5. build_report_v11.py 재실행 (daily_analyses 우선 사용)")
    print()
    print("★ 사용자 명시: 토큰 무관, 절대 단축 금지, 수억원 투자 집행용")

    # Save the list of companies for the agent to process
    daily_targets = {
        "date": TODAY,
        "policy": "기존이든 신규든 구분없이 매일 새로 분석",
        "total_companies": len(today_codes),
        "companies": [
            {"code": code, "company": info["company"], "reports": info["reports"]}
            for code, info in today_codes.items()
        ]
    }
    with open(f"{SESSION_OUT}/daily_targets_{TODAY}.json", "w", encoding="utf-8") as f:
        json.dump(daily_targets, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved daily targets: daily_targets_{TODAY}.json")
    print(f"✓ daily_analyses_{TODAY}.json (작성 후 build_report에 자동 적용)")


if __name__ == "__main__":
    main()
