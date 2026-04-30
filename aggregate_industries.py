#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘의 disclosures를 산업별로 집계하여 daily_aggregates.json에 누적 저장.

산업 분류:
- 사용자 친화적 라벨로 매핑 (네이버 업종/DART 업종 → 한글 라벨)
- 우선 yfinance industry → 보조로 회사명/사업 키워드 매칭

Output (cumulative): /tmp/awake-disclosure-fresh/daily_aggregates.json
{
  "by_date": {
    "2026-04-29": {
      "total": 116,
      "by_industry": {"반도체": 12, "조선/엔진": 5, ...},
      "by_signal": {"up": 14, "down": 7, "neutral": 95},
      "by_report_type": {"잠정실적": 33, ...}
    },
    ...
  }
}
"""
import json, os, sys, re
from collections import Counter, defaultdict

PARSED_TODAY = "/sessions/peaceful-admiring-mayer/mnt/outputs/parsed_disclosures.json"
COMP_INFO = "/sessions/peaceful-admiring-mayer/mnt/outputs/company_info.json"
AGG_LOCAL = "/sessions/peaceful-admiring-mayer/mnt/outputs/daily_aggregates.json"
AGG_REPO = "/tmp/awake-disclosure-fresh/daily_aggregates.json"

# 산업 분류 (한국어, 사용자 친화적)
# ── yfinance industry → 한국어 (1순위) ──────────────────────────────
YF_INDUSTRY_MAP = {
    "Semiconductors": "반도체", "Semiconductor Equipment & Materials": "반도체",
    "Electronic Components": "디스플레이/전자부품",
    "Auto Manufacturers": "자동차/모빌리티", "Auto Parts": "자동차/모빌리티",
    "Electrical Equipment & Parts": "배터리/소재",
    "Marine Shipping": "조선/해운",
    "Biotechnology": "바이오/제약",
    "Drug Manufacturers - General": "바이오/제약",
    "Drug Manufacturers - Specialty & Generic": "바이오/제약",
    "Medical Devices": "의료기기", "Medical Instruments & Supplies": "의료기기",
    "Diagnostics & Research": "의료기기", "Medical Care Facilities": "의료기기",
    "Medical Distribution": "바이오/제약",
    "Household & Personal Products": "화장품/뷰티",
    "Electronic Gaming & Multimedia": "게임", "Entertainment": "엔터/콘텐츠",
    "Aerospace & Defense": "방산/항공",
    "Chemicals": "화학/소재", "Specialty Chemicals": "화학/소재",
    "Steel": "철강/금속", "Copper": "철강/금속", "Aluminum": "철강/금속",
    "Metal Fabrication": "철강/금속", "Other Industrial Metals & Mining": "철강/금속",
    "Engineering & Construction": "건설/건축", "Building Products & Equipment": "건설/건축",
    "Capital Markets": "금융", "Banks - Regional": "금융", "Banks - Diversified": "금융",
    "Insurance - Property & Casualty": "금융", "Insurance - Life": "금융",
    "Insurance - Diversified": "금융", "REIT - Office": "금융", "REIT - Diversified": "금융",
    "Software - Application": "IT/SW", "Software - Infrastructure": "IT/SW",
    "Information Technology Services": "IT/SW",
    "Internet Content & Information": "IT/SW", "Internet Retail": "IT/SW",
    "Telecom Services": "통신",
    "Integrated Freight & Logistics": "물류/유통", "Grocery Stores": "물류/유통",
    "Discount Stores": "물류/유통", "Department Stores": "물류/유통",
    "Food Distribution": "물류/유통", "Specialty Retail": "물류/유통",
    "Packaged Foods": "식품", "Beverages - Wineries & Distilleries": "식품",
    "Conglomerates": "지주/복합",
    "Specialty Industrial Machinery": "기계/장비",
    "Farm & Heavy Construction Machinery": "기계/장비",
    "Security & Protection Services": "IT/SW",
    "Advertising Agencies": "미디어/광고", "Broadcasting": "미디어/광고",
    "Education & Training Services": "교육", "Resorts & Casinos": "레저",
    "Apparel Manufacturing": "섬유/패션", "Footwear & Accessories": "섬유/패션",
    "Paper & Paper Products": "화학/소재", "Packaging & Containers": "화학/소재",
    "Communication Equipment": "IT/SW", "Computer Hardware": "IT/SW",
    "Scientific & Technical Instruments": "기계/장비",
}

# ── 회사명 기반 키워드 (본문·summary 절대 사용 안 함) ─────────────────
NAME_KEYWORDS = [
    ("반도체",        ["반도체", "하이닉스", "DB하이텍", "어보브반도체", "LX세미콘", "코나아이", "HPSP", "파크시스템스", "피에스케이", "오로스테크", "이수페타시스", "해성디에스"]),
    ("배터리/소재",   ["양극재", "음극재", "배터리", "2차전지", "엘앤에프", "포스코퓨처엠", "롯데에너지머티리얼즈", "한솔케미칼"]),
    ("조선/해운",     ["조선", "중공업", "삼성중공업", "팬오션"]),
    ("자동차/모빌리티",["자동차", "기아", "한온시스템", "SNT모티브", "넥센타이어", "모트렉스", "오텍"]),
    ("방산/항공",     ["방산", "한화에어로", "한국항공우주", "SNT다이내믹스", "풍산", "SNT에너지", "루미르"]),
    ("로봇/AI",       ["제닉스로보틱스", "코윈테크", "라온로보틱스"]),
    ("바이오/제약",   ["바이오", "제약", "셀트리온", "유한양행", "한미약품", "HLB", "메지온", "에스티팜", "차백신", "셀레믹스", "바이오니아", "에스디바이오", "엑세스바이오", "대웅", "보령", "한독", "JW중외제약", "제일파마"]),
    ("의료기기",      ["디오", "하이로닉", "인바이츠", "케어젠", "휴온스", "휴젤"]),
    ("화장품/뷰티",   ["화장품", "코스메", "아모레", "LG생활건강", "달바글로벌", "오가닉티코스메틱"]),
    ("게임",          ["게임", "카카오게임즈", "골프존"]),
    ("엔터/콘텐츠",   ["엔터테인먼트", "스튜디오", "콘텐츠", "위지윅", "SOOP", "버킷스튜디오", "티쓰리"]),
    ("연료전지/수소", ["연료전지", "수소", "범한퓨얼셀"]),
    ("화학/소재",     ["화학", "LG화학", "국도화학", "효성화학"]),
    ("철강/금속",     ["철강", "포스코스틸리온", "포스코엠텍", "고려아연"]),
    ("건설/건축",     ["건설", "DL이앤씨", "자이에스앤디"]),
    ("금융",          ["증권", "금융지주", "금융그룹", "은행", "보험", "리츠", "키움증권", "삼성증권", "BNK금융", "케이뱅크", "신한알파", "신한서부", "에이플러스에셋", "SV인베스트먼트"]),
    ("IT/SW",         ["소프트웨어", "IT", "NAVER", "카카오", "현대오토에버", "포스코DX", "LG씨엔에스", "KG이니시스", "쿠콘", "케이아이엔엑스", "아이티센", "윈스테크", "롯데이노베이트", "슈프리마", "시큐레터", "에스원", "차이커뮤니케이션"]),
    ("통신",          ["통신", "SK텔레콤", "LG유플러스", "인스코비"]),
    ("지주/복합",     ["홀딩스", "지주", "포스코인터내셔널", "현대지에프홀딩스", "풍산홀딩스", "SNT홀딩스", "JW홀딩스", "한미사이언스", "지구홀딩스", "피에스케이홀딩스"]),
    ("섬유/패션",     ["제이에스코퍼레이션", "패션", "F&F"]),
    ("교육",          ["메가스터디"]),
    ("레저",          ["강원랜드"]),
]

def classify_industry(stock_code, company_name, dart_info, yf_info, report, body):
    """yfinance industry 우선 → 회사명 키워드 → DART KSIC 순 (본문 사용 안 함)"""
    # 1순위: yfinance industry 필드
    yf_industry = (yf_info or {}).get("industry", "") if yf_info else ""
    if yf_industry and yf_industry in YF_INDUSTRY_MAP:
        return YF_INDUSTRY_MAP[yf_industry]

    # 2순위: 회사명 키워드 (본문/summary 절대 포함 안 함)
    for label, kws in NAME_KEYWORDS:
        for kw in kws:
            if kw in company_name:
                return label

    # 3순위: DART KSIC 코드
    induty = (dart_info or {}).get("induty_code", "") or ""
    ksic_map = {
        "26": "반도체/전자", "27": "배터리/소재", "28": "기계/장비",
        "29": "자동차/모빌리티", "30": "조선/해운", "21": "바이오/제약",
        "20": "화학/소재", "24": "철강/금속", "41": "건설/건축",
        "62": "IT/SW", "63": "IT/SW", "64": "금융", "65": "금융", "66": "금융",
        "46": "물류/유통", "47": "물류/유통",
    }
    for prefix, label in ksic_map.items():
        if induty.startswith(prefix):
            return label

    return "기타"


def aggregate_today():
    today = "2026-04-30"  # KST today
    with open(PARSED_TODAY, encoding="utf-8") as f:
        parsed = json.load(f)
    with open(COMP_INFO, encoding="utf-8") as f:
        comp_info = json.load(f)

    disclosures = parsed["disclosures"]

    by_industry = Counter()
    by_signal = Counter()
    by_report_type = Counter()
    industry_companies = defaultdict(set)

    # signal classification re-import logic (simplified)
    def quick_signal(rep, body):
        if "영업(잠정)실적" in rep or "잠정실적" in rep:
            m = re.search(r"매출액\s*[:：]\s*[\d,]+억\s*\(예상치\s*[:：]\s*[\d,]+억\s*\/\s*([+\-]?\d+)%\)", body)
            if m:
                chg = int(m.group(1))
                if chg >= 5:
                    return "up"
                if chg <= -5:
                    return "down"
            return "neutral"
        if "단일판매" in rep and "체결" in rep:
            return "up"
        if "공급계약해지" in rep:
            return "down"
        if "자기주식취득" in rep or "주식소각" in rep or "기업가치제고" in rep:
            return "up"
        if "전환사채" in rep and "발행" in rep:
            return "down"
        if "유상증자" in rep:
            return "down"
        if "경영권분쟁" in rep or "관리종목" in rep:
            return "down"
        if "투자판단" in rep and ("허가" in body or "승인" in body or "취소" in body):
            return "up"
        return "neutral"

    for d in disclosures:
        ci = comp_info.get(d["code"], {})
        ind = classify_industry(
            d["code"], d["company"],
            ci.get("dart"), ci.get("yf"),
            d["report"], d["body_full"]
        )
        by_industry[ind] += 1
        by_signal[quick_signal(d["report"], d["body_full"])] += 1
        # Simplify report type
        rep_short = d["report"][:30].split("(")[0]
        by_report_type[rep_short] += 1
        industry_companies[ind].add(d["company"])

    # Single-supply contracts (수주) by industry — important standalone metric
    by_industry_orders = Counter()
    for d in disclosures:
        if "단일판매" in d["report"] and "체결" in d["report"]:
            ci = comp_info.get(d["code"], {})
            ind = classify_industry(
                d["code"], d["company"],
                ci.get("dart"), ci.get("yf"),
                d["report"], d["body_full"]
            )
            by_industry_orders[ind] += 1

    return today, {
        "total": len(disclosures),
        "by_industry": dict(by_industry),
        "by_industry_orders": dict(by_industry_orders),
        "by_signal": dict(by_signal),
        "by_report_type": dict(by_report_type),
        "industry_companies": {k: sorted(v) for k, v in industry_companies.items()},
        "top_buy": [d["company"] for d in disclosures if quick_signal(d["report"], d["body_full"]) == "up"][:10],
    }


def update_aggregates():
    today, today_agg = aggregate_today()

    # Load existing aggregates
    agg_path = AGG_REPO if os.path.exists(os.path.dirname(AGG_REPO)) else AGG_LOCAL
    if os.path.exists(agg_path):
        with open(agg_path, encoding="utf-8") as f:
            agg = json.load(f)
    else:
        agg = {"by_date": {}}

    agg["by_date"][today] = today_agg

    # Save to both
    with open(AGG_LOCAL, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)
    if os.path.exists(os.path.dirname(AGG_REPO)):
        with open(AGG_REPO, "w", encoding="utf-8") as f:
            json.dump(agg, f, ensure_ascii=False, indent=2)

    print(f"✓ Aggregated {today}: total={today_agg['total']}, industries={len(today_agg['by_industry'])}", file=sys.stderr)
    print(f"  Top industries: {sorted(today_agg['by_industry'].items(), key=lambda x: -x[1])[:5]}", file=sys.stderr)
    print(f"  Saved to: {agg_path}", file=sys.stderr)
    return agg


if __name__ == "__main__":
    update_aggregates()
