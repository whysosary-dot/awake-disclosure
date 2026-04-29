#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
신규 종목 자동 검출 — 매일 스케줄 실행 시 첫 단계로 호출.

기존 enriched_overrides.json에 없는 종목들을 식별하고,
각각에 대해 WebSearch가 필요한 쿼리를 생성한 후
LLM 에이전트가 후속 작성하도록 가이드.
"""
import json
import os
import sys
import re

PARSED = "/sessions/{SESSION}/mnt/outputs/parsed_disclosures.json"
OVERRIDES = "/sessions/{SESSION}/mnt/outputs/enriched_overrides.json"

# Auto-detect session path
import glob
candidates = glob.glob("/sessions/*/mnt/outputs/parsed_disclosures.json")
if candidates:
    PARSED = candidates[0]
    OVERRIDES = candidates[0].replace("parsed_disclosures.json", "enriched_overrides.json")
    # Override path may be in desktop folder for first run
    if not os.path.exists(OVERRIDES):
        desk_overrides = "/Users/songsangho/Desktop/Claude/AWAKE 전자 공시/enriched_overrides.json"
        if os.path.exists(desk_overrides):
            OVERRIDES = desk_overrides

# Resolve session path or use environment override
if "{SESSION}" in PARSED:
    print(f"❌ Session path not resolved. Set PARSED env var.")
    sys.exit(1)


def main():
    with open(PARSED, encoding="utf-8") as f:
        parsed = json.load(f)

    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as f:
            overrides = json.load(f)

    # Existing custom-analyzed codes
    enriched_codes = set(k for k, v in overrides.items()
                          if not k.startswith("_") and "custom_signal_reason" in v)

    # All codes in today's disclosures
    today_codes = {}  # code -> {company, reports[]}
    for d in parsed.get("disclosures", []):
        c = d["code"]
        if c not in today_codes:
            today_codes[c] = {"company": d["company"], "reports": []}
        today_codes[c]["reports"].append(d["report"])

    # New companies that need full v9 analysis
    new_codes = []
    for code, info in today_codes.items():
        if code not in enriched_codes:
            new_codes.append((code, info["company"], info["reports"]))

    print(f"📊 신규 종목 검출 결과:")
    print(f"  - 오늘 공시 종목: {len(today_codes)}")
    print(f"  - 기존 큐레이션됨: {len(today_codes) - len(new_codes)}")
    print(f"  - **신규 v9 분석 필요: {len(new_codes)}**")
    print()

    if new_codes:
        print("=" * 60)
        print("🚨 다음 종목들에 대해 즉시 v9 풀 분석 작성 필요:")
        print("=" * 60)
        for code, company, reports in new_codes:
            primary_rep = reports[0]
            print(f"\n[{code}] {company}")
            print(f"  공시 ({len(reports)}건): {', '.join(set(reports))[:100]}")
            print(f"  WebSearch 권장 쿼리:")
            print(f"    1. \"{company} {code} 사업영역 매출구성 한국\"")
            print(f"    2. \"{company} 2026 1분기 실적 애널리스트 목표주가\"")
            if "잠정실적" in primary_rep:
                print(f"    3. \"{company} 1Q26 어닝 컨센서스 시장 반응\"")
            elif "단일판매" in primary_rep:
                print(f"    3. \"{company} 신규 수주 계약상대 매출대비\"")
            elif "전환사채" in primary_rep or "유상증자" in primary_rep:
                print(f"    3. \"{company} 자금조달 사용처 희석 영향\"")
            elif "회사합병" in primary_rep:
                print(f"    3. \"{company} 합병 시너지 매수청구권\"")
            elif "투자판단" in primary_rep:
                print(f"    3. \"{company} 신약 허가 임상 진척\"")
            elif "기업가치제고" in primary_rep:
                print(f"    3. \"{company} 자사주 배당 ROE 가이드\"")

        print("\n" + "=" * 60)
        print("📝 다음 단계 (LLM 에이전트):")
        print("=" * 60)
        print("1. 위 신규 종목별로 WebSearch 호출")
        print("2. 각 종목에 다음 필드를 enriched_overrides.json에 추가:")
        print("   - bm (한 줄 한글)")
        print("   - segments (3개 카드 dict: name, pct, note)")
        print("   - strength (한 줄 핵심 경쟁력)")
        print("   - customers (구체적 거래처)")
        print("   - custom_signal_reason (본문 정량 + 컨센 + 분기 추이)")
        print("   - custom_insight (단기·중기·장기 시나리오 + 산업 사이클 + 위험 요인)")
        print("   - custom_watch (5-7개 구체 일정·수치)")
        print()
        print("3. 작성 완료 후 build_report_v11.py 재실행")
        print()
        print("★ 사용자 명시 정책: 토큰 무관, 절대 단축 금지, 수억원 투자 집행용")
    else:
        print("✅ 모든 종목이 이미 v9 큐레이션 완료. 추가 작업 불필요.")

    return new_codes


if __name__ == "__main__":
    main()
