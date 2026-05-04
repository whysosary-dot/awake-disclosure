#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AWAKE v11 빌더 — v9 풀템플릿 + 네이버금융 표 + 산업 모멘텀 차트."""
import json, html, urllib.parse, re, os
from collections import defaultdict, Counter

TODAY = "2026-05-04"
TODAY_DISP = "2026년 5월 4일 (월)"

with open("/sessions/funny-wizardly-keller/mnt/outputs/parsed_disclosures.json", encoding="utf-8") as f:
    parsed = json.load(f)
with open("/sessions/funny-wizardly-keller/mnt/outputs/prices_all.json", encoding="utf-8") as f:
    prices = json.load(f)
with open("/sessions/funny-wizardly-keller/mnt/outputs/company_info.json", encoding="utf-8") as f:
    company_info = json.load(f)
with open("/sessions/funny-wizardly-keller/mnt/outputs/naver_finance.json", encoding="utf-8") as f:
    naver = json.load(f)

# 한글 큐레이션된 overrides (WebSearch + 사용자 지식 기반)
ENRICHED = {}
override_path = "/sessions/funny-wizardly-keller/mnt/outputs/enriched_overrides.json"
if os.path.exists(override_path):
    with open(override_path, encoding="utf-8") as f:
        ENRICHED = json.load(f)

# Aggregates (cumulative)
AGG_PATH = "/sessions/funny-wizardly-keller/mnt/outputs/daily_aggregates.json"
agg_data = {"by_date": {}}
if os.path.exists(AGG_PATH):
    with open(AGG_PATH, encoding="utf-8") as f:
        agg_data = json.load(f)


# ★ 매일 새 분석 (daily_analyses_DATE.json) — 최우선 적용
DAILY_ANALYSES = {}
daily_path = f"/sessions/funny-wizardly-keller/mnt/outputs/daily_analyses_{TODAY}.json"
if os.path.exists(daily_path):
    with open(daily_path, encoding='utf-8') as f:
        DAILY_ANALYSES = json.load(f)
    print(f'✓ Loaded daily_analyses_{TODAY}.json: {len(DAILY_ANALYSES)} companies')

# Merge: daily_analyses가 ENRICHED custom_*를 오버라이드 (BM 필드 포함)
for code, data in DAILY_ANALYSES.items():
    if code not in ENRICHED:
        ENRICHED[code] = {}
    ENRICHED[code]['custom_signal_reason'] = data.get('custom_signal_reason', '')
    ENRICHED[code]['custom_insight'] = data.get('custom_insight', '')
    ENRICHED[code]['custom_watch'] = data.get('custom_watch', [])
    # ★ 방안A: daily_analyses BM 필드 — enriched 없을 때 우선 사용
    if data.get('bm_kr'):
        ENRICHED[code]['bm_daily'] = data['bm_kr']
    if data.get('segments_kr'):
        ENRICHED[code]['segments_daily'] = data['segments_kr']
    if data.get('strength_kr'):
        ENRICHED[code]['strength_daily'] = data['strength_kr']
    if data.get('customers_kr'):
        ENRICHED[code]['customers_daily'] = data['customers_kr']

DISCLOSURES = parsed["disclosures"]
BIG_TRADES = parsed["big_trades"]
WARNINGS = parsed["warnings"]


# ============= INDUSTRY CLASSIFICATION =============
# ── yfinance industry → 한국어 산업 분류 (1차: 가장 정확) ──────────────
YF_INDUSTRY_MAP = {
    # 반도체
    "Semiconductors": "반도체", "Semiconductor Equipment & Materials": "반도체",
    # 디스플레이
    "Electronic Components": "디스플레이/전자부품",
    # 자동차
    "Auto Manufacturers": "자동차/모빌리티", "Auto Parts": "자동차/모빌리티",
    "Auto Manufacturers - Domestic": "자동차/모빌리티",
    # 배터리/소재
    "Electrical Equipment & Parts": "배터리/소재",
    # 조선
    "Marine Shipping": "조선/해운", "Shipbuilding": "조선/해운",
    # 바이오/제약
    "Biotechnology": "바이오/제약",
    "Drug Manufacturers - General": "바이오/제약",
    "Drug Manufacturers - Specialty & Generic": "바이오/제약",
    "Medical Devices": "의료기기",
    "Medical Instruments & Supplies": "의료기기",
    "Diagnostics & Research": "의료기기",
    "Medical Care Facilities": "의료기기",
    "Medical Distribution": "바이오/제약",
    # 화장품
    "Household & Personal Products": "화장품/뷰티",
    # 게임
    "Electronic Gaming & Multimedia": "게임",
    # 엔터
    "Entertainment": "엔터/콘텐츠",
    # 방산/항공
    "Aerospace & Defense": "방산/항공",
    # 화학
    "Chemicals": "화학/소재", "Specialty Chemicals": "화학/소재",
    # 철강/금속
    "Steel": "철강/금속", "Copper": "철강/금속", "Aluminum": "철강/금속",
    "Metal Fabrication": "철강/금속", "Other Industrial Metals & Mining": "철강/금속",
    # 건설
    "Engineering & Construction": "건설/건축", "Building Products & Equipment": "건설/건축",
    # 금융
    "Capital Markets": "금융", "Banks - Regional": "금융", "Banks - Diversified": "금융",
    "Insurance - Property & Casualty": "금융", "Insurance - Life": "금융",
    "Insurance - Diversified": "금융", "Financial Data & Stock Exchanges": "금융",
    "REIT - Office": "금융", "REIT - Diversified": "금융", "REIT - Retail": "금융",
    # IT/SW
    "Software - Application": "IT/SW", "Software - Infrastructure": "IT/SW",
    "Information Technology Services": "IT/SW",
    "Internet Content & Information": "IT/SW",
    "Internet Retail": "IT/SW",
    # 통신
    "Telecom Services": "통신",
    # 물류/유통
    "Integrated Freight & Logistics": "물류/유통",
    "Grocery Stores": "물류/유통", "Discount Stores": "물류/유통",
    "Department Stores": "물류/유통", "Food Distribution": "물류/유통",
    "Specialty Retail": "물류/유통",
    # 식품
    "Packaged Foods": "식품", "Beverages - Wineries & Distilleries": "식품",
    # 에너지
    "Oil & Gas Refining & Marketing": "에너지/유틸리티",
    "Utilities - Regulated Electric": "에너지/유틸리티",
    "Specialty Industrial Machinery": "기계/장비",
    "Farm & Heavy Construction Machinery": "기계/장비",
    "Security & Protection Services": "IT/SW",
    "Advertising Agencies": "미디어/광고",
    "Broadcasting": "미디어/광고",
    "Publishing": "미디어/광고",
    "Education & Training Services": "교육",
    "Resorts & Casinos": "레저/관광",
    "Conglomerates": "지주/복합",
    "Apparel Manufacturing": "섬유/패션",
    "Footwear & Accessories": "섬유/패션",
    "Paper & Paper Products": "화학/소재",
    "Packaging & Containers": "화학/소재",
    "Communication Equipment": "IT/SW",
    "Computer Hardware": "IT/SW",
    "Scientific & Technical Instruments": "기계/장비",
}

# ── 회사명 기반 키워드 (본문·summary 절대 사용 안 함) ───────────────────
# 형식: (산업, [회사명에 포함될 때 매칭되는 고유 키워드])
NAME_KEYWORDS = [
    ("반도체",       ["반도체", "하이닉스", "DB하이텍", "매그나칩", "어보브반도체", "LX세미콘", "코나아이", "HPSP", "파크시스템스", "피에스케이", "오로스테크", "이수페타시스", "해성디에스"]),
    ("디스플레이/전자부품", ["디스플레이", "OLED", "삼성SDI", "LG디스플레이"]),
    ("배터리/소재",  ["양극재", "음극재", "배터리", "2차전지", "엘앤에프", "에코프로", "포스코퓨처엠", "롯데에너지머티리얼즈", "한솔케미칼"]),
    ("조선/해운",    ["조선", "중공업", "삼성중공업", "한화오션", "HD현대중공업", "팬오션"]),
    ("자동차/모빌리티", ["자동차", "기아", "현대모비스", "현대위아", "한온시스템", "SNT모티브", "넥센타이어", "한국타이어", "모트렉스", "오텍"]),
    ("방산/항공",    ["방산", "한화에어로", "한국항공우주", "KAI", "SNT다이내믹스", "LIG넥스원", "현대로템", "풍산", "SNT에너지", "루미르"]),
    ("로봇/AI",      ["로봇", "제닉스로보틱스", "코윈테크", "라온로보틱스"]),
    ("바이오/제약",  ["바이오", "제약", "셀트리온", "유한양행", "한미약품", "HLB", "메지온", "에스티팜", "차백신", "셀레믹스", "바이오니아", "에스디바이오", "엑세스바이오", "대웅제약", "대웅", "보령", "한독", "JW중외제약", "제일파마", "더존비즈온"]),
    ("의료기기",     ["디오", "하이로닉", "인바이츠", "케어젠", "휴온스", "휴젤"]),
    ("화장품/뷰티",  ["화장품", "코스메", "아모레", "LG생활건강", "달바글로벌", "오가닉티코스메틱"]),
    ("게임",         ["게임", "카카오게임즈", "골프존", "넥슨", "넷마블", "크래프톤", "위메이드"]),
    ("엔터/콘텐츠",  ["엔터테인먼트", "스튜디오", "콘텐츠", "위지윅", "SOOP", "버킷스튜디오", "티쓰리"]),
    ("연료전지/수소",["연료전지", "수소", "퓨얼셀", "범한퓨얼셀"]),
    ("화학/소재",    ["화학", "LG화학", "DL", "국도화학", "효성화학", "현대바이오랜드"]),
    ("철강/금속",    ["철강", "스틸", "포스코스틸리온", "포스코엠텍", "고려아연"]),
    ("건설/건축",    ["건설", "DL이앤씨", "자이에스앤디", "GS건설", "동원시스템즈"]),
    ("금융",         ["증권", "금융지주", "금융그룹", "은행", "보험", "리츠", "키움증권", "삼성증권", "BNK금융", "케이뱅크", "신한알파", "신한서부", "미래에셋증권", "에이플러스에셋", "SV인베스트먼트"]),
    ("IT/SW",        ["소프트웨어", "시스템", "클라우드", "IT", "NAVER", "카카오", "현대오토에버", "포스코DX", "LG씨엔에스", "더존비즈온", "KG이니시스", "쿠콘", "케이아이엔엑스", "아이티센", "윈스테크", "롯데이노베이트", "슈프리마", "시큐레터", "차이커뮤니케이션", "에스원", "파인테크닉스"]),
    ("통신",         ["통신", "SK텔레콤", "LG유플러스", "KT", "인스코비"]),
    ("물류/유통",    ["물류", "이마트", "신세계", "BGF리테일", "CJ프레시웨이", "GS"]),
    ("식품",         ["식품", "F&F", "신세계푸드", "무학", "인산가", "두올"]),
    ("에너지/유틸리티", ["에너지", "발전", "전력", "수소"]),
    ("미디어/광고",  ["미디어", "방송", "PS일렉트로닉스"]),
    ("기계/장비",    ["기계", "자비스", "KG에이"]),
    ("지주/복합",    ["홀딩스", "지주", "포스코인터내셔널", "현대지에프홀딩스", "풍산홀딩스", "SNT홀딩스", "JW홀딩스", "한미사이언스", "지구홀딩스", "피에스케이홀딩스"]),
    ("섬유/패션",    ["제이에스코퍼레이션", "패션", "섬유"]),
    ("교육",         ["메가스터디"]),
    ("레저/관광",    ["강원랜드", "호텔"]),
]

def classify_industry(d):
    code = d.get("code", "")
    company = d.get("company", "")
    ci = company_info.get(code, {})
    yf = ci.get("yf") or {}

    # 1순위: yfinance industry 필드 (가장 정확)
    yf_industry = yf.get("industry", "")
    if yf_industry and yf_industry in YF_INDUSTRY_MAP:
        return YF_INDUSTRY_MAP[yf_industry]

    # 2순위: 회사명에서 키워드 매칭 (본문/summary 절대 사용 안 함)
    for label, kws in NAME_KEYWORDS:
        for kw in kws:
            if kw in company:
                return label

    # 3순위: DART 업종코드 (KSIC 대분류)
    dart = ci.get("dart") or {}
    induty = dart.get("induty_code", "") or ""
    ksic_map = {
        "C": "제조업", "26": "반도체/전자", "27": "전기장비", "28": "기계/장비",
        "29": "자동차/모빌리티", "30": "조선/해운", "21": "바이오/제약",
        "20": "화학/소재", "24": "철강/금속", "41": "건설/건축",
        "62": "IT/SW", "63": "IT/SW", "64": "금융", "65": "금융", "66": "금융",
        "46": "물류/유통", "47": "물류/유통",
    }
    if induty:
        for prefix, label in ksic_map.items():
            if induty.startswith(prefix):
                return label

    return "기타"


# ============= SIGNAL CLASSIFIER =============
def classify_signal(report, body):
    r, b = report or "", body or ""
    if "영업(잠정)실적" in r or "잠정실적" in r:
        m = re.search(r"매출액\s*[:：]\s*[\d,]+억\s*\(예상치\s*[:：]\s*[\d,]+억\s*\/\s*([+\-]?\d+)%\)", b)
        if m:
            chg = int(m.group(1))
            if chg >= 10: return ("강매수", "up")
            if chg >= 3: return ("매수", "up")
            if chg <= -10: return ("매도⚠", "down")
            if chg <= -3: return ("매도", "down")
            return ("중립", "neutral")
        return ("중립~매수", "neutral")
    if "단일판매" in r and "체결" in r:
        m = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", b)
        if m:
            pct = float(m.group(1))
            if pct >= 30: return ("강매수", "up")
            if pct >= 5: return ("매수", "up")
            return ("중립~매수", "neutral")
        return ("중립~매수", "neutral")
    if "공급계약해지" in r: return ("매도⚠", "down")
    if "자기주식취득" in r or "주식소각" in r: return ("매수", "up")
    if "자기주식처분" in r:
        if any(w in b for w in ["근무", "상여", "임직원"]): return ("중립", "neutral")
        return ("중립~매도", "neutral")
    if "현금" in r and "배당" in r: return ("매수", "up")
    if "기업가치제고" in r: return ("매수", "up")
    if "전환사채" in r and "발행" in r: return ("중립~매도", "neutral")
    if "유상증자" in r: return ("매도", "down")
    if "전환청구" in r: return ("중립~매도", "neutral")
    if "회사합병" in r: return ("중립", "neutral")
    if "타법인주식" in r and "취득" in r: return ("중립~매수", "neutral")
    if "대량보유" in r: return ("중립~확인", "neutral")
    if "경영권분쟁" in r or "소송" in r: return ("매도⚠", "down")
    if "관리종목" in r or "감사거절" in r: return ("매도⚠", "down")
    if "IR" in r or "기업설명회" in r: return ("중립", "neutral")
    if "투자판단" in r:
        if "취소" in b and "가압류" in b: return ("매수", "up")
        if "허가" in b or "승인" in b: return ("강매수", "up")
        if any(w in b for w in ["체결", "선정"]): return ("매수", "up")
        return ("중립~매수", "neutral")
    if "풍문" in r or "해명" in r: return ("중립", "neutral")
    return ("중립", "neutral")


# ============= KSIC 5자리 → 한글 산업 (앞 2자리 기준) =============
KSIC_PREFIX_LABEL = {
    "10": "식료품 제조업", "11": "음료 제조업", "12": "담배 제조업",
    "13": "섬유 제조업", "14": "의복 제조업", "15": "가죽·신발 제조업",
    "16": "목재 제조업", "17": "펄프·종이 제조업", "18": "인쇄업",
    "19": "코크스·석유정제업", "20": "화학물질·화학제품 제조업",
    "21": "의약품 제조업", "22": "고무·플라스틱 제조업",
    "23": "비금속광물 제조업", "24": "1차 금속 제조업",
    "25": "금속가공제품 제조업", "26": "전자부품·통신장비 제조업",
    "27": "의료·정밀·광학 제조업", "28": "전기장비 제조업",
    "29": "기계·장비 제조업", "30": "자동차 제조업",
    "31": "기타 운송장비 제조업", "32": "가구 제조업",
    "33": "기타 제품 제조업", "34": "산업용 기계 수리업",
    "35": "전기·가스 공급업", "36": "수도사업",
    "41": "종합 건설업", "42": "전문직별 공사업",
    "46": "도매업", "47": "소매업", "49": "육상운송업",
    "50": "수상운송업", "51": "항공운송업", "52": "물류업",
    "55": "숙박업", "56": "음식점업",
    "58": "출판업", "59": "영상·방송 제작업",
    "60": "방송업", "61": "통신업",
    "62": "컴퓨터프로그래밍·시스템통합", "63": "정보서비스업",
    "64": "금융업", "65": "보험업", "66": "금융 부수서비스",
    "68": "부동산업", "70": "연구개발업",
    "71": "전문 과학·기술 서비스", "72": "건축·엔지니어링",
    "73": "광고업", "74": "사업지원 서비스",
    "85": "교육 서비스업", "86": "보건업",
    "90": "창작·예술업", "91": "스포츠·오락",
}


# ============= 산업 키워드 → 한글 라벨 (yfinance industry 영문 매핑) =============
def korean_industry_label(yf_industry_en):
    if not yf_industry_en:
        return None
    s = yf_industry_en.lower()
    mp = [
        ("semiconductor", "반도체"),
        ("electrical equipment", "전기장비"),
        ("electronic component", "전자부품"),
        ("electronic", "전자"),
        ("communication equipment", "통신장비"),
        ("auto parts", "자동차부품"),
        ("auto manufacturers", "자동차"),
        ("industrial machinery", "산업기계"),
        ("specialty chemical", "정밀화학"),
        ("chemical", "화학"),
        ("biotechnology", "바이오"),
        ("drug manufacturers", "제약"),
        ("medical device", "의료기기"),
        ("software", "소프트웨어"),
        ("internet content", "인터넷서비스"),
        ("entertainment", "엔터테인먼트"),
        ("apparel", "의류"),
        ("personal services", "개인서비스"),
        ("personal products", "개인용품"),
        ("household & personal", "생활용품"),
        ("household", "생활용품"),
        ("packaged foods", "식품"),
        ("beverages", "음료"),
        ("retail", "유통"),
        ("real estate services", "부동산서비스"),
        ("banks", "은행"),
        ("insurance", "보험"),
        ("capital markets", "자본시장/증권"),
        ("asset management", "자산운용"),
        ("specialty industrial", "산업특화"),
        ("conglomerate", "복합기업"),
        ("steel", "철강"),
        ("metals", "금속"),
        ("electrical components", "전기부품"),
        ("oil & gas", "석유·가스"),
        ("utilities", "유틸리티"),
        ("construction", "건설"),
        ("engineering", "엔지니어링"),
        ("aerospace", "방산·항공"),
    ]
    for kw, ko in mp:
        if kw in s:
            return ko
    return None


# ============= AUTO BM (Business Model) — 한글 우선 =============
def auto_bm(d):
    ci = company_info.get(d["code"], {})
    yf = ci.get("yf") or {}
    dart = ci.get("dart") or {}
    co = d["company"]
    sector = classify_industry(d)

    # 1) DART KSIC induty_code → 한글 라벨
    induty = dart.get("induty_code") or ""
    ksic_kr = KSIC_PREFIX_LABEL.get(induty[:2]) if induty else None

    # 2) yfinance industry → 한글 라벨
    yf_kr = korean_industry_label(yf.get("industry") or "")

    # 3) 한글 한 줄 BM 생성
    sub_industry = yf_kr or ksic_kr or sector
    # 보고서/본문에서 사업 단서 추출
    body = d.get("body_full", "")
    rep = d.get("report", "")
    business_hint = ""
    # "주요사업 :" 패턴 (회사합병결정 등에서 자주 나옴)
    m_main = re.search(r"주요사업\s*[:：]\s*([^\n]+)", body)
    if m_main:
        business_hint = m_main.group(1).strip()[:60]
    # "계약내용 :" (단일판매)
    if not business_hint:
        m_sub = re.search(r"계약내용\s*[:：]\s*([^\n]+)", body)
        if m_sub:
            business_hint = m_sub.group(1).strip()[:60]

    if business_hint:
        return f"[{sector}] {co}는 {sub_industry} 업종. 주요 활동: {business_hint}."
    return f"[{sector}] {co}는 {sub_industry} 업종 상장사. 자세한 사업 내용은 외부 링크의 회사 홈페이지·DART 사업보고서 참조."


# ============= 매출 구성 / 핵심 경쟁력 / 주요 고객 자동 추출 =============
def extract_segments(d):
    """yfinance summary에서 3개 사업 부문 추출. 영문 → 한글 키워드 변환."""
    ci = company_info.get(d["code"], {})
    yf = ci.get("yf") or {}
    summary = yf.get("summary") or ""
    if not summary:
        return None

    # Pattern: "products, such as X, Y, and Z"
    # Pattern: "offers X for Y"
    # Pattern: "operates in segments A, B, C"
    products = []
    m_segs = re.search(r"(?:operates in (?:the\s+)?(?:following\s+)?(?:segments?|business segments)|business is divided into|divisions?\s*[:：])(.+?)(?:\.|;|$)", summary, re.IGNORECASE)
    if m_segs:
        seg_text = m_segs.group(1)
        items = re.split(r",|;|\sand\s", seg_text)
        for it in items:
            it = re.sub(r"[\(\)]", "", it).strip()
            if it and len(it) > 3:
                products.append(it[:40])

    if not products:
        # Find "such as A, B, C, and D" pattern
        m_such = re.search(r"such as\s+(.+?)(?:\.|;)", summary, re.IGNORECASE)
        if m_such:
            seg_text = m_such.group(1)
            items = re.split(r",|;|\sand\s", seg_text)
            for it in items:
                it = it.strip()
                if it and len(it) > 3:
                    products.append(it[:40])

    if not products:
        # Find "offers X, Y, Z" near beginning
        m_off = re.search(r"offers\s+(.+?)(?:\.|;|to\s)", summary, re.IGNORECASE)
        if m_off:
            seg_text = m_off.group(1)
            items = re.split(r",|;|\sand\s", seg_text)
            for it in items:
                it = it.strip()
                if it and len(it) > 3:
                    products.append(it[:40])

    return products[:3] if products else None


def extract_customers(d):
    """yfinance summary에서 주요 고객 추출."""
    ci = company_info.get(d["code"], {})
    yf = ci.get("yf") or {}
    summary = yf.get("summary") or ""
    if not summary:
        return None
    # Pattern: "customers include X, Y, Z" or "customers, such as X, Y"
    m = re.search(r"(?:customers?\s+include|its customers|client(?:s)?\s+include|major (?:customers?|clients?))\s*(?:,?\s*such\s+as)?\s+([^.]+?)(?:\.|;)", summary, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:200]
    # Pattern: "to companies such as X, Y"
    m2 = re.search(r"to\s+(?:companies\s+)?such\s+as\s+([^.]+?)(?:\.|;)", summary, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()[:200]
    return None


def extract_strength(d):
    """yfinance summary에서 핵심 경쟁력 추출 — 첫 의미있는 문장 + 한글 변환."""
    ci = company_info.get(d["code"], {})
    yf = ci.get("yf") or {}
    summary = yf.get("summary") or ""
    if not summary:
        return None
    sents = re.split(r"\.\s+", summary)
    # Pick first informative sentence
    first = next((s.strip() for s in sents if 30 < len(s.strip()) < 250), None)
    if not first:
        return None
    # Trim trailing
    if not first.endswith("."):
        first = first[:200]
    # Translate common keywords (light heuristic)
    repl = [
        ("manufactures", "제조"),
        ("provides", "제공"),
        ("supplies", "공급"),
        ("develops", "개발"),
        ("operates", "운영"),
        ("designs", "설계"),
        ("produces", "생산"),
        ("worldwide", "글로벌"),
        ("South Korea", "한국"),
        (" and ", " · "),
    ]
    out = first
    for en, ko in repl:
        out = re.sub(en, ko, out, flags=re.IGNORECASE)
    return out


# ============= AUTO SIGNAL REASON — 강화 (회사 컨텍스트 + 본문 정량 + 시장 견해) =============
def _ctx(d):
    """Return overrides info (segments, customers, sector) for context."""
    ov = ENRICHED.get(d["code"], {})
    return ov

def _pct_to_int(s):
    try:
        return int(re.sub(r"[+,%]", "", s))
    except Exception:
        return None

def signal_reason(d):
    rep, body = d["report"], d["body_full"]
    co = d["company"]
    ctx = _ctx(d)
    sector = d.get("industry") or classify_industry(d)

    # ===== 영업(잠정)실적 =====
    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        m_rev = re.search(r"매출액\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        m_op = re.search(r"영업익\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        m_ni = re.search(r"순이익\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        # 분기 추이
        recent = re.findall(r"(202[3-6]\.\d+Q)\s*([\d,]+억)\/\s*([\d,\-]+억)\/\s*([\d,\-]+억)", body)
        chunks = []
        verdict = "중립"
        if m_rev:
            chg = _pct_to_int(m_rev.group(3)) or 0
            chunks.append(f"매출 {m_rev.group(1)} (컨센 {m_rev.group(3)}%, {chg:+d}p {'상회' if chg>=0 else '미스'})")
        if m_op:
            chg = _pct_to_int(m_op.group(3)) or 0
            chunks.append(f"영업익 {m_op.group(1)} (컨센 {m_op.group(3)}%, {chg:+d}p {'상회' if chg>=0 else '미스'})")
            if chg >= 10:
                verdict = "어닝 서프라이즈"
            elif chg <= -10:
                verdict = "어닝 쇼크"
        if m_ni:
            chg = _pct_to_int(m_ni.group(3)) or 0
            chunks.append(f"순익 {m_ni.group(1)} (컨센 {m_ni.group(3)}%)")
        trend_str = ""
        if len(recent) >= 2:
            ops = [f"{q}: 영업익 {op}" for q, _, op, _ in recent[:3]]
            trend_str = f" 분기추이: {' → '.join(reversed(ops))}."
        head = f"{co} 1Q26 잠정실적 — {verdict}: " if verdict in ("어닝 서프라이즈", "어닝 쇼크") else f"{co} 1Q26 잠정실적 — "
        return head + ", ".join(chunks) + "." + trend_str

    # ===== 단일판매 ㆍ공급계약체결 =====
    if "단일판매" in rep and "체결" in rep:
        m_amt = re.search(r"계약금액\s*[:：]\s*([^\n]+)", body)
        m_pct = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", body)
        m_party = re.search(r"계약상대\s*[:：]\s*([^\n]+)", body)
        m_period = re.search(r"계약(?:기간|시작일|시작)\s*[:：]\s*([^\n]+)", body)
        m_content = re.search(r"계약내용\s*[:：]\s*([^\n]+)", body)
        amt = m_amt.group(1).strip() if m_amt else "-"
        pct_raw = m_pct.group(1) if m_pct else "0"
        try:
            pct_f = float(pct_raw)
        except Exception:
            pct_f = 0
        party = m_party.group(1).strip()[:50] if m_party else "-"
        content = m_content.group(1).strip()[:60] if m_content else ""
        size_lbl = "대형" if pct_f >= 30 else ("중형" if pct_f >= 10 else ("소형" if pct_f >= 5 else "마이너"))
        return f"신규 공급계약 체결 — {party} 향 {amt} 규모 ({size_lbl}, 매출대비 {pct_raw}%). 계약내용: {content}."

    # ===== 공급계약해지 =====
    if "공급계약해지" in rep:
        m_amt = re.search(r"해지금액\s*[:：]\s*([^\n]+)", body)
        m_pct = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", body)
        m_party = re.search(r"계약상대\s*[:：]\s*([^\n]+)", body)
        m_reason = re.search(r"해지사유\s*[:：]\s*([^\n]+)", body)
        amt = m_amt.group(1).strip() if m_amt else "-"
        pct = m_pct.group(1) if m_pct else "-"
        party = m_party.group(1).strip()[:60] if m_party else "-"
        reason = m_reason.group(1).strip()[:80] if m_reason else "-"
        return f"기존 공급계약 해지 — {party} 측 {amt} 규모 (매출대비 {pct}%). 해지사유: {reason}."

    # ===== 자기주식 취득·소각 =====
    if "자기주식취득" in rep:
        m_qty = re.search(r"취득예정\s*주식\(주\)\s*[:：]\s*([\d,]+)", body)
        m_amt = re.search(r"취득예정\s*금액\(원\)\s*[:：]\s*([\d,]+)", body) or re.search(r"예정금액\s*[:：]\s*([^\n]+)", body)
        m_pct = re.search(r"시총대비\s*[:：]\s*([\d.]+)%", body)
        return f"자기주식 취득 결정 — {m_qty.group(1) + '주' if m_qty else ''} {m_amt.group(1) if m_amt else ''} (시총대비 {m_pct.group(1) + '%' if m_pct else '-'}). 발행주식수 감소·EPS 제고 효과."
    if "주식소각" in rep:
        m = re.search(r"우선주\s*[:：]\s*([\d,]+)\s*주", body)
        m2 = re.search(r"보통주\s*[:：]\s*([\d,]+)\s*주", body)
        m_amt = re.search(r"예정금액\s*[:：]\s*([^\n]+)", body)
        m_pct = re.search(r"시총대비\s*[:：]\s*([\d.]+)\s*%", body)
        chunks = []
        if m2 and m2.group(1) != "":
            chunks.append(f"보통주 {m2.group(1)}주")
        if m:
            chunks.append(f"우선주 {m.group(1)}주")
        return f"주식 소각 결정 — {', '.join(chunks)} {m_amt.group(1) if m_amt else ''} (시총대비 {m_pct.group(1) + '%' if m_pct else '-'}). 발행주식수 영구 감소로 주주환원의 가장 강력한 형태."

    # ===== 자기주식처분 =====
    if "자기주식처분" in rep:
        m_qty = re.search(r"처분수량\s*[:：]\s*([^\n]+)", body)
        m_purpose = re.search(r"처분목적\s*[:：]\s*([^\n]+)", body)
        purpose = m_purpose.group(1).strip()[:80] if m_purpose else ""
        is_emp = any(w in purpose for w in ["근무", "상여", "임직원", "스톡옵션", "RSU", "ESOP"])
        kind = "임직원 보상(시장 영향 미미)" if is_emp else "현금 회수 또는 매각(시장 매물 출회 가능)"
        return f"자기주식 처분 결정 — {m_qty.group(1).strip() if m_qty else '-'}, 목적: {purpose} → {kind}."

    # ===== 현금배당 =====
    if "현금" in rep and "배당" in rep:
        m_yld = re.search(r"시가배당률\s*[:：]\s*([\d.]+)\s*%", body)
        m_per = re.search(r"1주당\s*배당금\s*[:：]?\s*([^\n]+)", body)
        return f"배당 결정 — 1주당 {m_per.group(1).strip() if m_per else '-'}, 시가배당률 {m_yld.group(1) + '%' if m_yld else '-'}. 정기성·배당성향이 주주환원의 진정성 척도."

    # ===== 기업가치제고 (밸류업) =====
    if "기업가치제고" in rep:
        return f"{co} 기업가치제고 계획 공시 — 정부 밸류업 프로그램 호응. 구체적 ROE 목표·자사주 매입·배당정책의 실행력이 재평가의 관건."

    # ===== CB 발행 =====
    if "전환사채" in rep and "발행" in rep:
        m_amt = re.search(r"발행금액\s*[:：]\s*([\d,]+)억\s*\(전체대비\s*[:：]\s*([\d.]+)%\)", body) or re.search(r"발행금액\s*[:：]\s*([^\n(]+)", body)
        m_method = re.search(r"발행방법\s*[:：]\s*([^\n]+)", body)
        m_conv = re.search(r"전환가액\s*[:：]\s*([\d,]+)원\s*\(현재가\s*[:：]\s*([\d,]+)원\)", body) or re.search(r"전환가액\s*[:：]\s*([^\n]+)", body)
        m_min = re.search(r"최저조정\s*[:：]\s*([\d,]+)원", body)
        m_rate = re.search(r"표면이율\s*[:：]\s*([\d.]+)%", body)
        m_inv = re.search(r"\*\s*투자자\s*\n((?:.+?\n)+?)\n", body)
        amt_txt = m_amt.group(0).split(":")[1].strip() if m_amt else "-"
        details = []
        if m_amt and len(m_amt.groups()) >= 2:
            details.append(f"전체대비 {m_amt.group(2)}%")
        if m_conv and len(m_conv.groups()) >= 2:
            details.append(f"전환가 {m_conv.group(1)}원 (현재가 {m_conv.group(2)}원, {((int(m_conv.group(1).replace(',',''))/int(m_conv.group(2).replace(',',''))-1)*100):+.1f}%)")
        if m_min:
            details.append(f"최저조정가 {m_min.group(1)}원")
        if m_rate:
            details.append(f"표면이율 {m_rate.group(1)}%")
        return f"전환사채(CB) 발행 결정 — {amt_txt}. " + ", ".join(details) + ". 1년 후 전환청구 시점부터 잠재 희석 가능."

    # ===== 유증 =====
    if "유상증자" in rep:
        m_amt = re.search(r"발행금액\s*[:：]\s*([^\n]+)", body)
        m_method = re.search(r"발행방법\s*[:：]\s*([^\n]+)", body)
        m_purpose = re.search(r"자금사용\s*목적\s*[:：]\s*([^\n]+)", body) or re.search(r"자금조달\s*목적\s*[:：]\s*([^\n]+)", body)
        amt = m_amt.group(1).strip() if m_amt else "-"
        method = m_method.group(1).strip() if m_method else "-"
        purpose = m_purpose.group(1).strip()[:80] if m_purpose else "-"
        return f"유상증자 결정 — {amt}, 방식: {method}. 자금 사용처: {purpose}. 단기 희석 부담 vs 신사업 자금 조달 의지."

    # ===== 전환청구 =====
    if "전환청구" in rep:
        m_qty = re.search(r"청구주식수[^\n]*?\s*([\d,]+)\s*주", body)
        m_pr = re.search(r"전환가액\s*[:：]\s*([\d,]+)\s*원", body)
        m_listing = re.search(r"신주상장(?:예정일)?\s*[:：]\s*([^\n]+)", body)
        return f"기발행 CB·BW의 전환청구 — {m_qty.group(1) + '주' if m_qty else '-'} (전환가 {m_pr.group(1) + '원' if m_pr else '-'}). 신주 상장 후 잠재 매물 출회 부담."

    # ===== 합병 =====
    if "회사합병" in rep:
        m_target = re.search(r"대상회사\s*[:：]\s*([^\n]+)", body)
        m_main = re.search(r"주요사업\s*[:：]\s*([^\n]+)", body)
        m_perf = re.search(r"영업실적\s*[:：]\s*([^\n]+)", body)
        m_close = re.search(r"합병기일\s*[:：]\s*([^\n]+)", body)
        m_ratio = re.search(r"합병비율\s*[:：]\s*([^\n]+)", body)
        return f"회사 합병 결정 — 대상사: {m_target.group(1).strip() if m_target else '-'} (주요사업: {m_main.group(1).strip()[:50] if m_main else '-'}, 실적: {m_perf.group(1).strip()[:50] if m_perf else '-'}). 합병기일: {m_close.group(1).strip() if m_close else '-'}. 신주발행·매수청구권 규모가 EPS 영향의 핵심."

    # ===== 타법인주식 취득 =====
    if "타법인주식" in rep and "취득" in rep:
        m_target = re.search(r"취득회사\s*[:：]\s*([^\n]+)", body)
        m_main = re.search(r"주요사업\s*[:：]\s*([^\n]+)", body)
        m_amt = re.search(r"취득금액\s*[:：]\s*([^\n]+)", body)
        m_pct = re.search(r"자본대비\s*[:：]\s*([\d.]+)%", body)
        m_after = re.search(r"취득\s*후\s*지분율\s*[:：]\s*([\d.]+)%", body)
        m_purpose = re.search(r"취득목적\s*[:：]\s*([^\n]+)", body)
        return f"타법인 주식 취득 — {m_target.group(1).strip() if m_target else '-'} (사업: {m_main.group(1).strip()[:40] if m_main else '-'}). 취득금액 {m_amt.group(1).strip() if m_amt else '-'} (자본대비 {m_pct.group(1) + '%' if m_pct else '-'}, 취득 후 지분 {m_after.group(1) + '%' if m_after else '-'}). 목적: {m_purpose.group(1).strip()[:60] if m_purpose else '-'}."

    # ===== 대량보유 =====
    if "대량보유" in rep:
        m_rep = re.search(r"대표보고\s*[:：]\s*([^\n]+)", body)
        m_purp = re.search(r"보유목적\s*[:：]\s*([^\n]+)", body)
        m_bef = re.search(r"보고전\s*[:：]\s*([\d.]+%)", body)
        m_aft = re.search(r"보고후\s*[:：]\s*([\d.]+%)", body)
        m_reason = re.search(r"보고사유\s*[:：]\s*([^\n]+)", body)
        bef = m_bef.group(1) if m_bef else "-"
        aft = m_aft.group(1) if m_aft else "-"
        try:
            delta = float(aft.replace("%", "")) - float(bef.replace("%", ""))
            direction = "지분 증가" if delta > 0 else "지분 감소"
            delta_str = f"{delta:+.2f}%p"
        except Exception:
            direction = "변동"
            delta_str = "-"
        purp = m_purp.group(1).strip() if m_purp else "-"
        rep_name = m_rep.group(1).strip()[:40] if m_rep else "-"
        is_pension = any(w in rep_name for w in ["국민연금", "공무원연금", "사학연금", "우정사업본부"])
        is_fund = any(w in rep_name for w in ["피델리티", "블랙록", "Vanguard", "JP Morgan", "Capital", "Fidelity", "BlackRock"])
        actor = "(국내 연기금)" if is_pension else ("(외국계 자산운용)" if is_fund else "")
        return f"대량보유 보고 — {rep_name}{actor} 지분율 {bef} → {aft} ({direction} {delta_str}). 보유목적: {purp}. 사유: {m_reason.group(1).strip()[:50] if m_reason else '-'}."

    # ===== 경영권 분쟁 / 소송 =====
    if "경영권분쟁" in rep or "소송" in rep:
        m_court = re.search(r"관할법원\s*[:：]\s*([^\n]+)", body)
        m_case = re.search(r"사건명칭\s*[:：]\s*([^\n]+)", body)
        return f"법적 분쟁 발생 — 사건: {m_case.group(1).strip()[:50] if m_case else '-'} ({m_court.group(1).strip() if m_court else '-'}). 가처분 결정·표 대결 결과에 따라 단기 변동성 극단적."

    # ===== 투자판단 관련 =====
    if "투자판단" in rep:
        body_low = body.lower()
        if "허가" in body or "승인" in body:
            m_item = re.search(r"품목명\s*[:：]\s*([^\n]+)", body)
            m_indication = re.search(r"대상질환[^:]*[:：]\s*([^\n]+)", body)
            m_agency = re.search(r"품목허가기관\s*[:：]\s*([^\n]+)", body)
            return f"규제기관 허가/승인 — 품목: {m_item.group(1).strip()[:50] if m_item else '-'} (적응증: {m_indication.group(1).strip()[:50] if m_indication else '-'}, 기관: {m_agency.group(1).strip() if m_agency else '-'}). 매출 인식·사업화 출발점."
        if "취소" in body and "가압류" in body:
            return f"투자판단 관련 — 가압류 취소. 대주주 보유주식 안정화 호재."
        if "선정" in body:
            m = re.search(r"제목\s*[:：]\s*([^\n]+)", body)
            return f"투자판단 관련 — 국책 과제·신사업 선정 호재. 제목: {m.group(1).strip()[:80] if m else '-'}."
        return f"투자판단 관련 주요 경영사항 — 본문 내용에 따라 호재/악재 판별 후 후속 일정 트래킹."

    # ===== 풍문/해명 =====
    if "풍문" in rep or "해명" in rep:
        return f"{co} 풍문에 대한 회사 해명 (미확정/사실무근). 후속 공시 또는 시간 경과로 사실 확인 필요."

    # ===== IR =====
    if "IR" in rep or "기업설명회" in rep:
        m_when = re.search(r"개최일시\s*[:：]\s*([^\n]+)", body)
        m_topic = re.search(r"개최목적\s*[:：]\s*([^\n]+)", body) or re.search(r"주요내용\s*[:：]\s*([^\n]+)", body)
        return f"IR 개최 안내 — {m_when.group(1).strip() if m_when else '-'} ({m_topic.group(1).strip()[:60] if m_topic else '실적 발표 / 가이던스'}). 발표 후 시장 반응이 가장 신뢰할만한 시그널."

    return f"{co} {rep} 공시 — 본문 내용 기반 호재/악재 판별 필요."


# ============= AUTO INSIGHT — 강화 (수억원 투자 관점, 단기·중기·장기 시나리오) =============
def auto_insight(d):
    rep, body, co = d["report"], d["body_full"], d["company"]
    sector = d.get("industry") or classify_industry(d)
    ctx = _ctx(d)
    customers = ctx.get("customers", "")
    strength = ctx.get("strength", "")

    # 잠정실적
    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        m_op = re.search(r"영업익\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        chg = _pct_to_int(m_op.group(3)) if m_op else 0
        chg = chg or 0
        if chg >= 15:
            tone = f"강한 어닝 서프라이즈로 외국인·기관 추가 매수 가능성. 다음 분기 가이던스 상향 시 모멘텀 지속."
        elif chg >= 5:
            tone = f"컨센 상회로 단기 모멘텀. 동종업계 동조화 매수 + 애널리스트 목표가 상향 가능."
        elif chg <= -15:
            tone = f"심각한 어닝 쇼크. 외국인·기관 차익실현 + 투자의견 하향 가능. 연간 가이던스 재검토 필수."
        elif chg <= -5:
            tone = f"컨센 미스로 단기 매도 압력. 다만 일회성 비용·환율 등 1Q 특수요인 여부 점검."
        else:
            tone = f"컨센 부합 수준. 큰 변동 없이 다음 분기 가이던스가 핵심 변수."
        sector_views = {
            "반도체": "HBM·AI 서버 수요 증가가 메모리·장비주 전반 수혜",
            "디스플레이": "OLED 전환 가속·중국 캐파 증설 경쟁 심화",
            "배터리/2차전지": "EV 수요 둔화·LFP 가격 경쟁이 양극재·전구체 마진에 부담",
            "바이오/제약": "신약 임상 진척과 R&D 비용이 가치평가 좌우",
            "자동차/모빌리티": "EV 전환·미국 IRA 수혜·관세 리스크가 핵심 변수",
            "조선/엔진": "LNG·암모니아 친환경 발주 증가로 수주잔고 확대",
            "엔터/콘텐츠": "K-콘텐츠 글로벌 OTT 동시방영 확대로 매출 가시성 향상",
            "게임": "신작 출시 + 글로벌 매출 비중 + IP 라이선스",
            "철강/금속": "건설·자동차 수요 회복과 중국 철강 수출 변수",
            "화학/소재": "유가·원료 가격 + 글로벌 다운스트림 수요 균형",
            "방산/항공": "K-방산 수출 확대 + 미국·유럽 방위비 증가 수혜",
            "에너지/유틸리티": "신재생 정책 + 전력기기 글로벌 수요",
            "연료전지/수소": "RPS·CHPS 정책 + 글로벌 수소 인프라 수혜",
            "건설/건축": "주택 시장 회복 + 해외 인프라·플랜트 수주",
            "금융": "금리 사이클 + 자기자본 비율·배당 정책",
            "IT/SW": "AI·클라우드 SaaS 매출 비중 + 해외 진출",
            "화장품/뷰티": "K-뷰티 글로벌 + 면세·중국 회복",
            "식품/유통": "내수 소비 회복 + 원가 전가력 + 면세점",
            "의료기기": "글로벌 출시 진척 + 보험 등재",
        }
        sector_view = sector_views.get(sector, f"{sector} 업황과 글로벌 매크로 변수 함께 점검")
        return f"{co} ({sector}) — {tone} {sector} 산업 사이클상 {sector_view}."

    # 단일판매 계약
    if "단일판매" in rep and "체결" in rep:
        m_pct = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", body)
        try:
            pct_f = float(m_pct.group(1)) if m_pct else 0
        except Exception:
            pct_f = 0
        if pct_f >= 30:
            return f"매출대비 {pct_f:.1f}%의 초대형 수주는 향후 1-2년 매출 가시성을 크게 높임. 계약 진행상황 (제품 인도·수금) 분기 IR로 추적. {co}의 ({sector}) 수주잔고 누적 추이를 동종업계와 비교해 시장점유율 변화 확인. 후속 추가 수주 발표 여부가 고객 만족도·확장 가능성의 시그널. 주요 고객: {customers[:80] if customers else '본문 참조'}."
        elif pct_f >= 10:
            return f"매출대비 {pct_f:.1f}% 규모의 의미있는 수주. {co}의 {sector} 사업 구조에서 안정적 매출 기여. 계약 수익성(영업이익률 기여), 인도 일정, 후속 옵션·연장 가능성을 함께 봐야 함. 분기 실적 발표 시 매출 인식 시점 확인 필요."
        elif pct_f >= 5:
            return f"매출대비 {pct_f:.1f}% 수준의 정기 수주. 단기 임팩트는 제한적이나 누적 수주잔고 추이가 더 중요. {co}의 ({sector}) 메인 거래선({customers[:50] if customers else '주요 고객'})과의 관계 안정성 시그널."
        else:
            return f"매출대비 {pct_f:.1f}% 소형 수주로 단일 임팩트는 크지 않음. {co}의 일상적 영업 활동의 일부. 주가 영향은 제한적이나 후속 누적 수주가 의미 있는 매출 기여로 연결되는지 분기 IR로 점검."

    # 공급계약 해지
    if "공급계약해지" in rep:
        m_pct = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", body)
        try:
            pct_f = float(m_pct.group(1)) if m_pct else 0
        except Exception:
            pct_f = 0
        sev = "심각" if pct_f >= 10 else ("중간" if pct_f >= 5 else "제한적")
        return f"공급계약 해지는 단기 매출 손실 + 신뢰도 타격으로 {sev} 임팩트 (매출대비 {pct_f:.1f}%). 핵심 점검 포인트: ① 해지 사유가 1회성(상대측 정책 변경) vs 구조적 문제(품질·가격 경쟁력 상실)인지, ② {co}의 ({sector}) 다른 거래선({customers[:60] if customers else '주요 고객'}) 안정성, ③ 대체 수주·재계약 가능성, ④ 영업/운전자본 영향. 1Q26 실적 발표 시 가이던스 재조정 여부가 추가 시그널."

    # 자사주 매입·소각
    if "자기주식취득" in rep or "주식소각" in rep:
        is_burn = "소각" in rep
        kind = "소각(영구 발행주식수 감소)" if is_burn else "취득(향후 소각·매각 가능성 모두 존재)"
        return f"{co} 자사주 {kind} — {sector} 업종에서 주주환원 의지 명확한 시그널. 핵심 점검: ① 시총 대비 규모(클수록 EPS 제고 효과 큼), ② 자사주 정책의 정기성·반복성(일회성 vs 연례), ③ 후속 추가 발표 여부, ④ ROE·배당성향 등 종합 주주환원 정책. 단기 수급 효과보다 장기 밸류에이션 재평가 관점에서 접근. 단, 경영권 방어 성격이면 의미 다름."

    # 자사주 처분
    if "자기주식처분" in rep:
        m_purpose = re.search(r"처분목적\s*[:：]\s*([^\n]+)", body)
        purpose = m_purpose.group(1).strip()[:80] if m_purpose else ""
        is_emp = any(w in purpose for w in ["근무", "상여", "임직원", "스톡옵션", "RSU", "ESOP"])
        if is_emp:
            return f"{co}의 자사주 처분이 임직원 보상 목적으로, 시장에 매도 매물로 유출되지 않아 주가 영향 미미. 다만 임직원 인센티브가 주가 연동이라 향후 책임경영 메시지로 해석. 동종업계 ({sector}) 보상 정책과 비교."
        else:
            return f"{co} 자사주 처분 — 시장 매도 가능성 또는 M&A·자금조달 목적. 단기 수급 부담. 처분 진행 상황과 자금 사용처({purpose})를 분기 IR로 추적. {sector} 업종 사이클상 자금 조달 시점이 적절한지 검토."

    # 배당
    if "현금" in rep and "배당" in rep:
        return f"{co} 배당 결정 — {sector} 업종에서 안정적 현금 창출 능력의 증빙. 핵심 점검: ① 시가배당률(2-4%면 안정적, 4%↑면 고배당주), ② 배당성향(15-30% 일반, 50%↑면 적극적 환원), ③ 정기성(분기·중간배당 vs 일회성). 국내 배당주 ETF·ESG 펀드 자금 유입 모멘텀. 동종업계 배당 트렌드와 비교."

    # 기업가치제고 (밸류업)
    if "기업가치제고" in rep:
        return f"{co} 기업가치 제고 계획 공시 — 정부 밸류업 프로그램에 대한 회사의 공식 호응. 핵심 평가 기준: ① 구체적 ROE 목표(8-12% 일반, 15%↑면 적극적), ② 자사주 매입·소각 일정과 규모, ③ 배당성향 가이드라인, ④ 사업구조조정·자회사 정리 등. 공시문에 그치지 않고 실행력 발휘 시 PBR 재평가 가능. 코리아 디스카운트 해소 정책 직접 수혜. {sector} 업종 PBR 평균과 비교."

    # CB 발행
    if "전환사채" in rep and "발행" in rep:
        m_amt = re.search(r"발행금액\s*[:：]\s*([\d,]+)억\s*\(전체대비\s*[:：]\s*([\d.]+)%\)", body)
        m_conv = re.search(r"전환가액\s*[:：]\s*([\d,]+)원\s*\(현재가\s*[:：]\s*([\d,]+)원\)", body)
        m_min = re.search(r"최저조정\s*[:：]\s*([\d,]+)원", body)
        try:
            dilution = float(m_amt.group(2)) if m_amt else 0
        except Exception:
            dilution = 0
        sev = "큰 희석 부담" if dilution >= 15 else ("중간 희석" if dilution >= 7 else "제한적 희석")
        return f"{co} CB 발행은 자금조달 수단이나 1년 후 전환청구 시점부터 {sev} (전체대비 {dilution:.1f}%). 점검 포인트: ① 인수자(코스닥벤처투자신탁이면 만기 보유 후 전환 가능성, 헤지펀드면 즉시 청산 가능), ② 전환가 vs 현재가 갭 (premium·discount), ③ 최저조정가 트리거 가능성(주가 하락 시 추가 희석), ④ 자금 사용처. {sector} 업종에서 자금조달 사이클 적절성. 표면이율 0%·만기이율 1% 등 낮은 이자는 발행 측에 유리하나 주주에 불리."

    # 유증
    if "유상증자" in rep:
        return f"{co} 유상증자 — 단기 주주 희석 부담. 핵심 평가: ① 자금 사용처가 신사업·M&A·재무구조 개선이면 중장기 호재 가능, ② 발행구조(주주배정·제3자배정·일반공모), ③ 발행가 할인율 (일반 25-30%), ④ 대주주·관계사 인수 비중. {sector} 사이클상 자금조달 시점이 적절한지 점검. 청약률·실권주 비중이 시장 신뢰도 시그널."

    # 전환청구 (기발행 CB·BW)
    if "전환청구" in rep:
        return f"{co} 기발행 CB·BW의 전환청구 — 신주 상장 시점부터 매물 출회 부담. 핵심 점검: ① 전환된 비중과 미전환 잔량, ② 차익 실현 vs 장기 보유 의도, ③ 기존 발행 시 인수자(전략 투자자 vs 헤지펀드), ④ 신주 상장 후 하락 압력 + 단기 유동성 증가. 신주가 시장에 본격 풀리는 1-2주가 단기 변동성 정점."

    # 회사 합병
    if "회사합병" in rep:
        m_target = re.search(r"대상회사\s*[:：]\s*([^\n]+)", body)
        m_perf = re.search(r"영업실적\s*[:：]\s*([^\n]+)", body)
        target = m_target.group(1).strip() if m_target else "-"
        perf = m_perf.group(1).strip() if m_perf else "-"
        is_subsidiary = "자회사" in target or "100%" in body
        kind = "100% 자회사 흡수합병으로 신주발행·매수청구권 미발생, EPS 영향 제한적, 페이퍼컴퍼니 정리 차원" if is_subsidiary else "동등합병 또는 일부 지분 합병으로 합병비율·신주발행·매수청구권 모두 영향. EPS·BPS 변화 정밀 검증 필요"
        return f"{co} 합병 결정 — 대상사 {target}, 실적 {perf}. {kind}. 합병기일까지 거래정지 + 매수청구권 행사 규모가 단기 수급 변수. {sector} 업종 통합 시너지 (R&D 효율·영업·생산 통합)가 중장기 가치 결정. 합병 후 사업 확장 vs 단순 정리 여부 분기 IR로 추적."

    # 타법인 주식 취득
    if "타법인주식" in rep and "취득" in rep:
        m_target = re.search(r"취득회사\s*[:：]\s*([^\n]+)", body)
        m_pct_cap = re.search(r"자본대비\s*[:：]\s*([\d.]+)%", body)
        m_after = re.search(r"취득\s*후\s*지분율\s*[:：]\s*([\d.]+)%", body)
        target = m_target.group(1).strip()[:60] if m_target else "-"
        try:
            cap_pct = float(m_pct_cap.group(1)) if m_pct_cap else 0
            after = float(m_after.group(1)) if m_after else 0
        except Exception:
            cap_pct, after = 0, 0
        if after >= 90:
            scale = "100% 자회사화 (완전 통제·연결 편입)"
        elif after >= 50:
            scale = "지배지분 확보 (경영권 행사 가능)"
        elif after >= 20:
            scale = "관계회사 (지분법 평가)"
        else:
            scale = "단순 투자 지분"
        return f"{co} 타법인 주식 취득 — {target}, 자본대비 {cap_pct:.1f}%, 취득 후 {after:.0f}% ({scale}). {sector} 사업 영역 확장·신사업 진출·해외 거점 확보 의지. 핵심 점검: ① 인수 대상사 BM·매출·이익 (주요사업·실적 본문), ② PMI(인수후 통합) 진행, ③ 첫 매출 인식 시점, ④ ROIC 회수 기간. 인수 가격이 적정 vs 고가인지는 동종 M&A 사례와 비교."

    # 대량보유 보고
    if "대량보유" in rep:
        m_rep = re.search(r"대표보고\s*[:：]\s*([^\n]+)", body)
        m_purp = re.search(r"보유목적\s*[:：]\s*([^\n]+)", body)
        m_bef = re.search(r"보고전\s*[:：]\s*([\d.]+%)", body)
        m_aft = re.search(r"보고후\s*[:：]\s*([\d.]+%)", body)
        try:
            delta = float(m_aft.group(1).replace("%", "")) - float(m_bef.group(1).replace("%", ""))
        except Exception:
            delta = 0
        rep_name = m_rep.group(1).strip()[:40] if m_rep else "-"
        purp = m_purp.group(1).strip() if m_purp else "-"
        is_pension = any(w in rep_name for w in ["국민연금", "공무원연금", "사학연금", "우정사업본부"])
        is_fund = any(w in rep_name for w in ["피델리티", "블랙록", "Vanguard", "JP Morgan", "Capital", "Fidelity", "BlackRock"])
        if is_pension and delta > 0:
            tone = "국내 최대 연기금의 신규 진입·확대는 강한 매수 시그널 (장기 보유·정책적 매수)"
        elif is_pension and delta < 0:
            tone = "연기금 비중 축소는 정기 리밸런싱 vs 의도적 매도 구분 필요"
        elif is_fund and delta > 0:
            tone = "외국계 자산운용사 신규 진입은 글로벌 가치투자 인정 신호"
        elif is_fund and delta < 0:
            tone = "외국계 자산운용사 매도는 단기 수급 부담, 외국인 보유율 추이 점검"
        elif "경영권" in purp:
            tone = "경영권 영향 보유는 향후 적극적 행동주의 가능성 (이사 추천·배당 요구·자사주 매입 압박)"
        elif delta > 0:
            tone = "지분 확대는 주가 상승 기대감 또는 경영 개입 의지 시그널"
        else:
            tone = "지분 축소는 차익 실현 또는 포트폴리오 재조정"
        return f"{co} 대량보유 보고 ({rep_name}) — {tone}. 보유목적 '{purp}' + 지분 변동 {delta:+.2f}%p이 단기 수급의 핵심. {sector} 업종 외국인·기관 보유율 동향과 함께 추적. 경영권 영향 시 후속 주주제안·이사회 변화 모니터링."

    # 경영권 분쟁·소송
    if "경영권분쟁" in rep or "소송" in rep:
        return f"{co} 법적 분쟁은 단기 변동성 극대화 종목. 보유자는 즉시 리스크 관리 필요, 신규 진입은 매우 신중. 핵심 시나리오: ① 가처분 인용 시 주총 무산·경영권 변경 가능성, ② 가처분 기각 시 기존 경영진 안정·다음 라운드 분쟁 지속, ③ 합의 시 단기 안정. {sector} 업종 평균 변동성보다 2-3배 높을 수 있음. 분쟁 결과까지 베팅 성격, 펀더멘털 분석 의미 약화."

    # 투자판단 관련
    if "투자판단" in rep:
        if "허가" in body or "승인" in body:
            m_item = re.search(r"품목명\s*[:：]\s*([^\n]+)", body)
            return f"{co} 규제기관 허가/승인은 매출 인식·사업화 출발점. 핵심 후속 마일스톤: ① 보험 등재(약가 협상 6-12개월 소요), ② 첫 처방·매출 인식 시점, ③ 해외 인허가(미국 FDA·유럽 EMA) 신청·승인, ④ 생산 capacity 확보, ⑤ 의료기관 처방 의사 채택률. {sector} 업종 동종 신약/제품의 출시 후 매출 곡선과 비교해 본격 매출은 통상 출시 후 6-12개월. 글로벌 라이선스 아웃 협상 가능성도 추가 모멘텀."
        if "취소" in body and "가압류" in body:
            return f"{co} 가압류 취소는 대주주 보유주식 안정화 호재. 단기 수급 안정 + 향후 추가 분쟁 가능성 해소. 다만 가압류 발생 원인(대주주 채무·소송)이 완전히 해결됐는지 본문 정독 필요. {sector} 업종 평균보다 변동성 정상화 기대."
        if "선정" in body:
            return f"{co} 국책 과제·신사업 선정은 정부·공공 자금 확보 + 기술 검증 신호. 본격 매출 인식까지는 통상 1-3년 소요. {sector} 업종에서 R&D 우위 확보 + 후속 상용화 단계 모니터링."
        return f"{co} 투자판단 관련 본문을 정독하고 호재/악재 판별 후 관련 일정·수치 트래킹. 본문 단서 + 시장 반응(주가·거래량)이 가장 신뢰할만한 시그널."

    # 풍문/해명
    if "풍문" in rep or "해명" in rep:
        return f"{co} 풍문 해명 (미확정/사실무근) — 단기 변동성 일시적 진정. 그러나 풍문이 발생한 근본 원인(루머·내부자 정보·시장 기대)은 후속 공시 또는 시간 경과로만 해소. {sector} 업종에서 유사 사례 관찰 필요."

    # IR 안내
    if "IR" in rep or "기업설명회" in rep:
        return f"{co} IR 개최 — 가이던스·신사업·실적 코멘트가 시장 컨센서스에 부합하는지 확인. 발표 후 24-48시간 주가 반응이 가장 신뢰할만한 시그널. 주요 점검: ① 분기 가이던스 vs 컨센, ② 신사업 진척도, ③ R&D 파이프라인 업데이트, ④ M&A·자본정책. {sector} 업종 동시기 다른 IR과 비교해 상대적 모멘텀 판단."

    return f"{co} ({sector}) 일반 공시 — 본문 내용 기반 호재/악재 판별, 후속 일정과 시장 반응 모니터링."


# ============= AUTO WATCH — 강화 (구체 일정·수치·임계점) =============
def auto_watch(d):
    rep = d["report"]
    co = d["company"]
    body = d.get("body_full", "")
    sector = d.get("industry") or classify_industry(d)

    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        return [
            "1Q26 확정실적 발표 (감사보고서 시점, 잠정 vs 확정 차이 0% 이상이면 신뢰도 높음)",
            "2Q26 가이던스 발표 — 컨센서스 vs 회사 가이던스 갭 모니터링",
            f"외국인·기관 보유율 변화 (분기말 vs 발표 후 1주일)",
            f"동종업계 ({sector}) 잠정실적 비교 — 상대적 모멘텀 판단",
            "애널리스트 목표주가·투자의견 변경 (어닝콜 후 24-48시간 내)",
        ]
    if "단일판매" in rep and "체결" in rep:
        m_period = re.search(r"계약(?:기간|시작일|시작)\s*[:：]\s*([^\n]+)", body)
        m_end = re.search(r"계약종료일?\s*[:：]\s*([^\n]+)", body)
        return [
            f"계약 인도·매출 인식 시작 시점 ({m_period.group(1).strip() if m_period else '본문 참조'})",
            "후속 추가 수주 발표 — 동일 고객사 반복 수주는 강한 시그널",
            f"분기 수주잔고 누적 추이 (분기 IR 자료의 backlog 항목)",
            "해당 사업부 영업이익률 기여도 (세그먼트별 손익)",
            f"동종업계 ({sector}) 다른 회사들의 동시기 수주 동향과 비교",
        ]
    if "공급계약해지" in rep:
        return [
            "대체 수주 발표 — 해지 후 1-3개월 내 회복 vs 장기화 여부",
            "1Q26·2Q26 실적 가이던스 재조정 발표 (컨센 하향 가능성)",
            f"해당 사업부 다각화 진척 ({sector} 업종 신규 거래선 확보)",
            "해지 사유 추가 설명 — 재계약 가능성 vs 구조적 단절",
            "주요 거래선의 회사 정책 변화 (해당 거래선 추가 해지 도미노 가능성)",
        ]
    if "자기주식취득" in rep:
        m_end = re.search(r"취득(?:종료|예정)일?\s*[:：]\s*([^\n]+)", body)
        return [
            f"취득 진행 상황 — 매주 기 취득 수량 공시 (예정일: {m_end.group(1).strip() if m_end else '본문 참조'})",
            "취득 완료 후 후속 소각 결정 여부 (취득만 vs 소각으로 EPS 영구 제고)",
            "추가 자사주 정책 발표 (분기 IR 자료)",
            f"동종업계 ({sector}) 주주환원 정책 비교 - 트렌드 추적",
            "EPS·BPS·ROE 변화 추정 (취득량 확정 후)",
        ]
    if "주식소각" in rep:
        m_close = re.search(r"예정일자\s*[:：]\s*([^\n]+)", body)
        return [
            f"소각 완료 공시 ({m_close.group(1).strip() if m_close else '본문 참조'})",
            "발행주식수 감소 → EPS·BPS 변화 정량 추정",
            "추가 소각 정책 (정기적 소각 vs 일회성)",
            "동종업계 소각 사례와 PER·PBR 변화 비교",
        ]
    if "자기주식처분" in rep:
        m_purpose = re.search(r"처분목적\s*[:：]\s*([^\n]+)", body)
        purpose = m_purpose.group(1).strip()[:80] if m_purpose else ""
        is_emp = any(w in purpose for w in ["근무", "상여", "임직원", "스톡옵션", "RSU", "ESOP"])
        if is_emp:
            return [
                "임직원 수령 후 매도 시점 (보호예수 종료 후 매물화)",
                "주가 연동 보상 정책의 효과 (임직원 책임경영 메시지)",
                "유사 보상 추가 처분 가능성",
            ]
        return [
            "처분 진행 상황 — 시장 매도 매물 출회 여부",
            f"처분 자금 사용처 ({purpose}) 진척",
            "추가 처분 가능성 + 자사주 정책 변화",
            "외국인·기관 매수가 처분 매물 흡수 여부",
        ]
    if "전환사채" in rep and "발행" in rep:
        m_min = re.search(r"최저조정\s*[:：]\s*([\d,]+)원", body)
        m_conv_start = re.search(r"청구시작\s*[:：]\s*([^\n]+)", body)
        return [
            f"주가 vs 전환가 추이 — 전환가 위 유지 시 매물 출회 압박",
            f"최저조정가 {m_min.group(1) + '원' if m_min else '본문 참조'} 근접 여부 — 트리거 시 추가 희석",
            f"전환청구 시작일 ({m_conv_start.group(1).strip() if m_conv_start else '약 1년 후'}) — 첫 전환청구 시점",
            "인수자(코스닥벤처투자신탁 등)의 보유 의도 변화",
            "발행 자금의 실제 사용처 진척 (분기 IR)",
        ]
    if "유상증자" in rep:
        return [
            "발행가 확정 공시 (발행가 = 시가 - 할인율, 통상 25-30%)",
            "청약률·실권주 비중 — 90%↑면 시장 신뢰, 70%↓면 부담",
            "주주배정 시 신주인수권 거래 시작/종료일",
            "자금 사용 진척 — 분기 IR로 실제 집행 여부 점검",
            "유상증자 직전·직후 1개월 주가 패턴 (할인율 메우기)",
        ]
    if "전환청구" in rep:
        m_listing = re.search(r"신주상장(?:예정일)?\s*[:：]\s*([^\n]+)", body)
        return [
            f"신주 상장일 ({m_listing.group(1).strip() if m_listing else '본문 참조'}) — 매물 출회 정점",
            "추가 전환청구 잔여 물량 (미전환 잔량)",
            "차익 실현 매물 (전환가 vs 시장가 갭)",
            "전환 후 발행주식수 변동 → EPS 희석 정량",
        ]
    if "회사합병" in rep:
        m_close = re.search(r"합병기일\s*[:：]\s*([^\n]+)", body)
        m_oppose = re.search(r"반대기한\s*[:：]\s*([^\n]+)", body)
        return [
            f"매수청구권 반대 기한 ({m_oppose.group(1).strip() if m_oppose else '본문 참조'}) — 행사 규모가 단기 수급 영향",
            f"합병기일 ({m_close.group(1).strip() if m_close else '본문 참조'}) — 거래정지 기간",
            "주주총회 통과 여부 (대주주·반대측 표 대결)",
            "합병 후 통합 시너지 — R&D 효율·영업·생산 통합 진척",
            "합병 신주 상장 후 1-3개월 주가 패턴 (합병프리미엄 해소)",
        ]
    if "타법인주식" in rep and "취득" in rep:
        m_close = re.search(r"예정일자\s*[:：]\s*([^\n]+)", body)
        return [
            f"출자 납입 ({m_close.group(1).strip() if m_close else '본문 참조'}) 완료",
            "출자 자회사 첫 매출 인식 시점",
            "PMI(인수후 통합) 진척 — 인사·시스템·고객 통합",
            "추가 출자·M&A 가능성 (한 번의 인수가 아닌 시리즈 매수)",
            "ROIC 회수 기간 (통상 3-5년)",
        ]
    if "대량보유" in rep:
        return [
            "다음 분기 변동 보고 (지분 +/- 1%p 이상 시)",
            "보유목적 변경 여부 (단순투자 → 경영권 영향)",
            "외국인·기관 보유율 추이 (보유자별 누적 변화)",
            "연기금·블록딜 매수 시 추종 매수 가능성",
            "주주명부 폐쇄·주총 의안 안건 추적",
        ]
    if "경영권분쟁" in rep or "소송" in rep:
        return [
            "가처분 결정문 공시 (인용·기각·일부인용)",
            "임시주총 개최 여부 (기각 시 진행, 인용 시 무산)",
            "최대주주 vs 청구측 지분율 변화 (대량보유 보고)",
            "표 대결 결과 vs 합의 도출 가능성",
            "분쟁 종결 후 회사 정책 변화 (배당·자사주·신사업)",
        ]
    if "기업가치제고" in rep:
        return [
            "구체적 KPI 발표 (ROE·배당성향·자사주 비중) — 정량적 가이드",
            "자사주 매입·소각 실행 시점 (말로만 vs 실행)",
            "분기 IR 가이던스 — 추진 진척",
            "주주환원 정책 트렌드 (반복성 vs 일회성)",
            "PBR 재평가 여부 (코리아 디스카운트 해소)",
        ]
    if "투자판단" in rep:
        if "허가" in body or "승인" in body:
            return [
                "보험 등재 신청·결정 (약가 협상 6-12개월)",
                "첫 처방·매출 인식 시점 (출시 후 1-3개월 내 첫 매출)",
                "해외 인허가 (미국 FDA·유럽 EMA·일본 PMDA)",
                "생산 capacity 확보 (CMO 계약·자체 생산설비)",
                "글로벌 라이선스 아웃 협상 진척",
            ]
        return [
            "후속 공시 (구체 수치·일정 추가 공시)",
            "주가·거래량 시장 반응",
            "동종업계 유사 사례와 비교",
            "애널리스트 코멘트·리포트 발표",
        ]
    if "IR" in rep or "기업설명회" in rep:
        m_when = re.search(r"개최일시\s*[:：]\s*([^\n]+)", body)
        return [
            f"IR 발표 자료 검토 ({m_when.group(1).strip() if m_when else '본문 참조'}) — 가이던스·신사업·R&D 코멘트",
            "가이던스 vs 컨센 비교 (상회·미스 갭)",
            "발표 후 24-48시간 주가 반응 (가장 신뢰할만한 시그널)",
            "분기 실적 발표일까지 외국인·기관 수급",
            "동시기 동종업계 IR 비교 (상대적 모멘텀)",
        ]
    return [
        "분기 IR 발표 — 가이던스·실적 코멘트",
        "DART 후속 공시 (구체 수치·일정 추가)",
        "외국인·기관 수급 변화",
        "동종업계 트렌드와 비교",
    ]


# ============= 빈값 정규화 (&nbsp; → "-") =============
def clean_val(v):
    if v is None:
        return "-"
    s = str(v).strip()
    # Remove HTML entities and whitespace artifacts
    s = re.sub(r"&nbsp;|&#160;|&#xa0;|\xa0", "", s)
    s = s.strip()
    if not s or s in {"-", "—"}:
        return "-"
    return s


# ============= FIN ONE-LINE =============
def fin_oneline(d):
    nf = naver.get(d["code"], {})
    if not nf or "rows" not in nf or not nf["rows"]:
        return f"{d['company']} (시총 {d['mcap']}) — 네이버 금융 데이터 조회 실패"
    rows = nf["rows"]
    periods = nf.get("periods", [])
    rev_y = [clean_val(v) for v in rows.get("매출액", [])]
    op_y = [clean_val(v) for v in rows.get("영업이익", [])]
    if len(rev_y) >= 4 and len(periods) >= 4:
        rev_cur = rev_y[2] if len(rev_y) > 2 else "-"
        op_cur = op_y[2] if len(op_y) > 2 else "-"
        rev_fwd = rev_y[3] if len(rev_y) > 3 else "-"
        op_fwd = op_y[3] if len(op_y) > 3 else "-"
        # If forecast missing → only show realized
        if rev_fwd == "-" and op_fwd == "-":
            return f"매출 {rev_cur}억 · 영업익 {op_cur}억 (2025 실적)"
        return f"매출 {rev_cur}억(2025) → {rev_fwd}억(2026E) · 영업익 {op_cur}억(2025) → {op_fwd}억(2026E)"
    if rev_y:
        return f"매출 {rev_y[-1]}억 · 영업익 {op_y[-1] if op_y else '-'}억"
    return f"{d['company']} (시총 {d['mcap']})"


# Pre-process all disclosures
for d in DISCLOSURES:
    sig_t, sig_k = classify_signal(d["report"], d["body_full"])
    d["signal"] = sig_t
    d["signal_kind"] = sig_k
    d["industry"] = classify_industry(d)
    # 한글 큐레이션된 overrides 우선
    ov = ENRICHED.get(d["code"], {})
    # ★ 우선순위: daily_analyses BM > enriched_overrides BM > auto_bm
    d["bm"] = ov.get("bm") or ov.get("bm_daily") or auto_bm(d)
    # segments: dict list({name,pct,note}) or list[str] from daily
    d["segments"] = ov.get("segments") or ov.get("segments_daily") or extract_segments(d)
    d["customers"] = ov.get("customers") or ov.get("customers_daily") or extract_customers(d)
    d["strength"] = ov.get("strength") or ov.get("strength_daily") or extract_strength(d)
    # Custom override가 있으면 그것 사용, 없으면 강화된 자동 분석
    d["signal_reason"] = ov.get("custom_signal_reason") or signal_reason(d)
    d["insight"] = ov.get("custom_insight") or auto_insight(d)
    d["watch"] = ov.get("custom_watch") or auto_watch(d)
    d["fin"] = fin_oneline(d)
    p = prices.get(d["code"])
    d["price"] = p
    d["chg_pct"] = p.get("chg_pct") if p else None


# Group by company
by_company = defaultdict(list)
for d in DISCLOSURES:
    by_company[d["code"]].append(d)
companies = sorted(by_company.items(), key=lambda kv: kv[1][0]["time"])

TOTAL_PAGES = 3 + len(companies)  # cover + industry + index + per-company

# ============= Helpers =============
def url_quote(s): return urllib.parse.quote(s, safe="")
def chg_pill(chg):
    if chg is None: return '<span style="color:#666">-</span>'
    if chg > 0.05: return f'<span style="color:#dc2626;font-weight:700">▲ {chg:+.2f}%</span>'
    if chg < -0.05: return f'<span style="color:#2563eb;font-weight:700">▼ {chg:+.2f}%</span>'
    return f'<span style="color:#6b7280;font-weight:700">■ {chg:+.2f}%</span>'
def signal_color(kind): return {"up":"#dc2626","down":"#2563eb","neutral":"#6b7280"}.get(kind,"#6b7280")
def short_signal(s):
    return s.replace("강매수","강매").replace("매도⚠","매도⚠").replace("중립~매수","중매").replace("중립~매도","중매도").replace("중립~확인","중확인")


# ============= Industry/momentum analysis =============
today_agg = agg_data["by_date"].get(TODAY, {})
all_dates = sorted(agg_data["by_date"].keys())
# Last 7 days for chart
chart_dates = all_dates[-7:] if len(all_dates) >= 7 else all_dates
# Top 8 industries today
top_inds = sorted(today_agg.get("by_industry", {}).items(), key=lambda x: -x[1])[:8]
top_ind_labels = [k for k, _ in top_inds]

# Build chart data: stacked bar by industry over last 7 days
chart_payload = []
for dt in chart_dates:
    day = agg_data["by_date"].get(dt, {})
    ind_map = day.get("by_industry", {})
    chart_payload.append({
        "date": dt,
        "total": day.get("total", 0),
        "industries": {k: ind_map.get(k, 0) for k in top_ind_labels}
    })

# Tipping point insight
def tipping_insight():
    if len(all_dates) < 2:
        return f"📊 오늘 ({TODAY}) 누적 데이터 시작. 7일치 누적 후부터 산업 모멘텀 추이가 의미있는 시그널을 제공합니다. 현재 상위 산업은 {', '.join([f'{k}({v})' for k,v in top_inds[:5]])}."
    # Compare today vs avg of previous days
    prev_avg = defaultdict(float)
    n_prev = len(all_dates) - 1
    for dt in all_dates[:-1]:
        for ind, cnt in agg_data["by_date"][dt].get("by_industry", {}).items():
            prev_avg[ind] += cnt / max(n_prev, 1)
    surges = []
    for ind, cnt in today_agg.get("by_industry", {}).items():
        prev = prev_avg.get(ind, 0)
        if prev > 0:
            ratio = cnt / prev
            if ratio >= 1.5 and cnt >= 3:
                surges.append((ind, cnt, prev, ratio))
        elif cnt >= 5:
            surges.append((ind, cnt, 0, 999))
    surges.sort(key=lambda x: -x[3])
    parts = []
    if surges:
        parts.append("📈 오늘 모멘텀 급등 산업:")
        for ind, cnt, prev, ratio in surges[:3]:
            if prev > 0:
                parts.append(f" {ind} {cnt}건 (직전 평균 {prev:.1f}건 대비 {ratio:.1f}×)")
            else:
                parts.append(f" {ind} {cnt}건 (신규)")
    return "\n".join(parts) if parts else f"오늘 산업별 분포: {', '.join([f'{k}({v})' for k,v in top_inds[:5]])}."


# ============= HTML Build =============
parts_html = []
parts_html.append(f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AWAKE 전자공시 일일 리포트 — {TODAY}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;900&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{ --c-darkest:#0c1445; --c-dark:#1e3a8a; --c-mid:#3b82f6; --c-light:#93c5fd;
  --c-paper:#f7faff; --c-text:#0f172a; --c-mute:#475569; --c-line:#e2e8f0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
  background:#e5e7eb; color:var(--c-text); font-size:17px; line-height:1.85; }}
.page {{ width:210mm; min-height:297mm; margin:12px auto; background:white; overflow:visible;
  page-break-after:always; box-shadow:0 4px 18px rgba(15,23,42,0.12); position:relative; }}
.cover {{ background:linear-gradient(135deg,var(--c-darkest) 0%,var(--c-dark) 50%,var(--c-mid) 100%);
  color:white; padding:60px 64px; display:flex; flex-direction:column; justify-content:space-between; }}
.cover h1 {{ font-size:84px; font-weight:900; letter-spacing:-2px; line-height:1.05; margin:32px 0 12px 0; }}
.cover .subtitle {{ font-size:26px; font-weight:400; opacity:0.92; }}
.cover .date {{ font-size:22px; font-weight:600; margin-top:18px; opacity:0.96; }}
.cover .stat-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin-top:50px; }}
.cover .stat {{ background:rgba(255,255,255,0.10); border:1px solid rgba(255,255,255,0.20);
  border-radius:14px; padding:20px; backdrop-filter:blur(6px); }}
.cover .stat .num {{ font-family:'Inter',sans-serif; font-size:46px; font-weight:800; line-height:1; }}
.cover .stat .lbl {{ font-size:16px; opacity:0.86; margin-top:6px; }}
.cover .footer {{ font-size:15px; opacity:0.78; margin-top:28px; }}

.page-header {{ background:var(--c-darkest); color:white; padding:14px 40px;
  display:flex; justify-content:space-between; align-items:center;
  font-size:14px; font-weight:600; }}
.page-body {{ padding:24px 40px 30px 40px; }}

.stock-meta {{ display:flex; justify-content:space-between; align-items:flex-start; gap:20px;
  margin-bottom:22px; padding-bottom:18px; border-bottom:2px solid var(--c-line); }}
.co-block {{ flex:1; }}
.co-name {{ font-size:42px; font-weight:900; letter-spacing:-1px; color:var(--c-darkest); line-height:1.1; }}
.co-code {{ font-size:18px; color:var(--c-mute); font-family:'Inter',sans-serif; font-weight:600; margin-top:4px; }}
.co-sector {{ display:inline-block; background:#eff6ff; color:var(--c-dark); padding:4px 12px;
  border-radius:14px; font-size:14px; font-weight:600; margin-top:8px; margin-right:8px; }}
.signal-pill {{ display:inline-block; color:white; padding:6px 16px; border-radius:20px;
  font-size:20px; font-weight:800; margin-top:8px; }}
.price-card {{ background:linear-gradient(135deg,#1e3a8a 0%,#3b82f6 100%); color:white;
  border-radius:14px; padding:18px 22px; min-width:220px; text-align:right; }}
.price-close {{ font-family:'Inter',sans-serif; font-size:24px; font-weight:800; line-height:1; }}
.price-chg {{ font-size:18px; margin-top:8px; font-weight:700; }}
.co-mcap {{ font-size:26px; font-weight:700; color:var(--c-darkest); margin-top:12px; }}

.section-title {{ font-size:23px; font-weight:800; color:var(--c-darkest);
  border-left:4px solid var(--c-mid); padding-left:14px; margin:26px 0 12px 0; }}
.bm-text {{ font-size:18px; font-weight:500; line-height:1.7; color:var(--c-text); padding:14px 18px;
  background:#f8fafc; border-radius:8px; border-left:4px solid var(--c-light); }}

.disc-card {{ border:1px solid var(--c-line); border-left:5px solid var(--c-mid);
  border-radius:8px; margin-top:14px; background:#f8fafc; overflow:hidden; }}
.disc-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px;
  padding:14px 18px; background:#eff6ff; border-bottom:1px solid var(--c-line); }}
.disc-meta {{ flex:1; }}
.disc-time {{ font-size:14px; color:var(--c-mute); font-family:'Inter',sans-serif; font-weight:600; }}
.disc-title {{ font-size:19px; font-weight:700; color:var(--c-darkest); margin-top:4px; }}
.dart-orig-link {{ background:#1e3a8a; color:#fff; padding:6px 12px; border-radius:6px;
  font-size:14px; font-weight:600; text-decoration:none; flex-shrink:0; white-space:nowrap; }}
.disc-body {{ font-size:17px; line-height:1.75; white-space:pre-wrap;
  font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif; padding:16px 20px; color:var(--c-text); }}

.signal-reason-box {{ font-size:18px; line-height:1.8; padding:14px 18px; background:#fff7ed;
  border-left:4px solid #fb923c; border-radius:8px; margin-top:12px; }}
.insight-card {{ background:#eff6ff; border:1px solid #dbeafe; border-radius:10px;
  padding:16px 20px; margin-top:14px; }}
.insight-title {{ font-size:20px; font-weight:800; color:var(--c-darkest); margin-bottom:8px; }}
.insight-text {{ font-size:18px; line-height:1.85; color:var(--c-text); }}
.watch-list {{ background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px;
  padding:14px 20px; margin-top:14px; }}
.watch-list h4 {{ font-size:18px; margin:0 0 8px 0; color:#166534; font-weight:800; }}
.watch-list ul {{ margin:0; padding-left:20px; }}
.watch-list li {{ font-size:17px; line-height:1.85; color:#14532d; }}

.fin-line {{ font-size:17px; padding:12px 16px; background:#f1f5f9; border-radius:8px; margin-top:14px;
  font-family:'Inter','Noto Sans KR',sans-serif; }}

/* Naver Finance table — high readability */
.nf-wrap {{ margin-top:14px; overflow-x:auto; border:1px solid var(--c-line); border-radius:8px; }}
.nf-table {{ width:100%; border-collapse:collapse; font-size:13px; background:white; }}
.nf-table thead th {{ background:#1e3a8a; color:white; padding:10px 8px; text-align:center; font-weight:700; font-size:13px; border:1px solid #1e3a8a; }}
.nf-table thead th.grp-label {{ background:#0c1445; font-size:12px; padding:6px; }}
.nf-table thead th.metric-head {{ text-align:left; min-width:120px; }}
.nf-table tbody td {{ padding:8px 8px; border-bottom:1px solid var(--c-line); border-right:1px solid #f1f5f9; text-align:right; font-family:'Inter',sans-serif; font-size:13px; color:var(--c-text); white-space:nowrap; }}
.nf-table tbody td.metric {{ text-align:left; font-weight:700; color:var(--c-darkest); font-family:'Noto Sans KR',sans-serif; font-size:14px; background:#f1f5f9 !important; }}
.nf-table tbody tr:hover td {{ background:#fef3c7; }}
.nf-table tbody td.cell-annual {{ background:#f0f9ff; }}
.nf-table tbody td.cell-quarterly {{ background:#f0fdf4; }}
.nf-table tbody td.cell-empty {{ color:#cbd5e1; }}
.nf-table tbody td.cell-neg {{ color:#dc2626; font-weight:600; }}
.nf-table tbody td.cell-fwd {{ background:#fffbeb; font-weight:600; }}

.ext-links {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }}
.ext-link {{ background:white; border:1.5px solid var(--c-mid); color:var(--c-dark);
  padding:8px 14px; border-radius:8px; font-size:14px; font-weight:600; text-decoration:none; }}

/* Industry chart page */
.industry-chart-wrap {{ background:white; border:1px solid var(--c-line); border-radius:12px; padding:20px; margin-top:18px; }}
.industry-insight {{ background:#fef3c7; border:1px solid #fde68a; border-radius:10px;
  padding:18px 22px; margin-top:18px; font-size:17px; line-height:1.85; white-space:pre-line; }}
.industry-stat-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:18px; }}
.industry-stat {{ background:#eff6ff; border:1px solid #dbeafe; border-radius:10px; padding:14px 16px; }}
.industry-stat .lbl {{ font-size:13px; color:var(--c-mute); font-weight:600; }}
.industry-stat .num {{ font-family:'Inter',sans-serif; font-size:28px; font-weight:800; color:var(--c-darkest); }}

/* Index */
.index-table {{ width:100%; border-collapse:collapse; margin-top:14px; font-size:14px; }}
.index-table th {{ background:var(--c-darkest); color:white; padding:9px 6px; text-align:left; font-size:13px; font-weight:700; }}
.index-table td {{ padding:8px 6px; border-bottom:1px solid var(--c-line); white-space:nowrap; vertical-align:middle; }}
.index-table td.disc {{ white-space:normal; max-width:300px; }}
.index-table tr:hover {{ background:#f1f5f9; }}
.fav-star-idx,.fav-star-page {{
  background:none; border:none; cursor:pointer; font-size:18px;
  padding:2px 4px; border-radius:6px; transition:transform .15s;
  line-height:1; color:#94a3b8;
}}
.fav-star-idx:hover,.fav-star-page:hover {{ transform:scale(1.3); color:#f59e0b; }}
.fav-star-idx.fav-on,.fav-star-page.fav-on {{ color:#f59e0b; }}
.fav-star-page {{
  font-size:22px; padding:4px 6px; background:rgba(245,158,11,.08);
  border:1.5px solid rgba(245,158,11,.25); border-radius:8px;
}}
.idx-anchor {{ color:var(--c-dark); text-decoration:none; }}
.idx-btn {{ background:#f1f5f9; border:1px solid #cbd5e1; border-radius:6px; padding:5px 12px; font-size:13px; font-weight:600; cursor:pointer; color:var(--c-dark); transition:all 0.15s; }}
.idx-btn:hover {{ background:#e2e8f0; }}
.idx-btn.active {{ background:var(--c-darkest); color:white; border-color:var(--c-darkest); }}
.sig-buy,.sig-sell,.sig-neutral {{ color:white; padding:3px 8px; border-radius:10px; font-size:12px; font-weight:700; }}
.sig-buy {{ background:#dc2626; }}
.sig-sell {{ background:#2563eb; }}
.sig-neutral {{ background:#6b7280; }}

@media print {{ body {{background:white;}} .page {{margin:0; box-shadow:none;}} }}
@media (max-width:900px) {{ .page {{width:100%; min-height:auto;}}
  .stock-meta {{flex-direction:column;}} .price-card {{width:100%; text-align:left;}}
  .cover h1 {{font-size:56px;}} .cover .stat-grid,.industry-stat-grid {{grid-template-columns:repeat(2,1fr);}}
  .index-table {{font-size:12px;}} }}
</style>
</head>
<body>
""")

# Stats
n_total_msgs = len(DISCLOSURES) + len(BIG_TRADES) + len(WARNINGS)
n_buy = sum(1 for d in DISCLOSURES if d["signal_kind"] == "up")
n_sell = sum(1 for d in DISCLOSURES if d["signal_kind"] == "down")

# === COVER ===
parts_html.append(f"""<div class="page cover">
<div>
  <div class="subtitle">AWAKE 전자공시 일일 리포트</div>
  <h1>매매를 위한<br>오늘의 공시</h1>
  <div class="date">{TODAY_DISP} · KST</div>
</div>
<div>
  <div class="stat-grid">
    <div class="stat"><div class="num">{n_total_msgs}</div><div class="lbl">전체 메시지</div></div>
    <div class="stat"><div class="num">{len(DISCLOSURES)}</div><div class="lbl">DART 공시</div></div>
    <div class="stat"><div class="num">{len(by_company)}</div><div class="lbl">분석 종목</div></div>
    <div class="stat"><div class="num">{n_buy}</div><div class="lbl">매수 시그널</div></div>
  </div>
  <div class="footer">자료: AWAKE 텔레그램 채널(Telethon) · DART · yfinance · 네이버 금융 · 본 리포트는 매매 권유가 아님</div>
</div>
</div>""")

# === INDUSTRY MOMENTUM PAGE ===
chart_data_json = json.dumps({
    "labels": [c["date"] for c in chart_payload],
    "industries": top_ind_labels,
    "values": [[c["industries"][ind] for ind in top_ind_labels] for c in chart_payload],
    "totals": [c["total"] for c in chart_payload],
}, ensure_ascii=False)
insight_text = tipping_insight()

# Today's industry breakdown
ind_break_rows = ""
for ind, cnt in top_inds:
    cos = today_agg.get("industry_companies", {}).get(ind, [])
    ind_break_rows += f"""<tr><td class="metric">{html.escape(ind)}</td><td>{cnt}</td><td style="text-align:left; font-size:12px;">{html.escape(', '.join(cos[:8]))}{'...' if len(cos)>8 else ''}</td></tr>"""

parts_html.append(f"""<div class="page">
<div class="page-header">
  <div>AWAKE Daily Disclosure Report — Industry Momentum</div>
  <div>Page 2 / {TOTAL_PAGES}</div>
</div>
<div class="page-body">
<h2 style="font-size:32px; font-weight:900; color:var(--c-darkest); margin:6px 0 4px 0;">📊 산업별 공시 모멘텀</h2>
<div style="font-size:15px; color:var(--c-mute); margin-bottom:14px;">최근 {len(chart_payload)}일 누적 · 상위 8개 산업 · 산업 변화의 티핑 포인트 추적</div>

<div class="industry-stat-grid">
  <div class="industry-stat"><div class="lbl">오늘 공시</div><div class="num">{len(DISCLOSURES)}</div></div>
  <div class="industry-stat"><div class="lbl">분석 종목</div><div class="num">{len(by_company)}</div></div>
  <div class="industry-stat"><div class="lbl">최다 산업</div><div class="num" style="font-size:20px;">{html.escape(top_inds[0][0]) if top_inds else '-'}</div></div>
  <div class="industry-stat"><div class="lbl">매수 시그널</div><div class="num">{n_buy}</div></div>
</div>

<div class="industry-chart-wrap">
  <canvas id="industryChart" style="max-height:340px;"></canvas>
</div>

<div class="industry-insight">{html.escape(insight_text)}</div>

<h3 class="section-title">🏭 오늘 산업별 분포 (Top 8)</h3>
<table class="nf-table"><thead><tr>
<th style="text-align:left;">산업</th><th>건수</th><th style="text-align:left;">참여 종목</th>
</tr></thead><tbody>
{ind_break_rows}
</tbody></table>

</div>
<script>
const chartData = {chart_data_json};
const ctx = document.getElementById('industryChart').getContext('2d');
const palette = ['#1e3a8a','#3b82f6','#dc2626','#16a34a','#f59e0b','#9333ea','#0891b2','#db2777'];
const datasets = chartData.industries.map((ind, i) => ({{
  label: ind,
  data: chartData.values.map(row => row[i]),
  backgroundColor: palette[i % palette.length],
  borderRadius: 4,
}}));
new Chart(ctx, {{
  type: 'bar',
  data: {{ labels: chartData.labels, datasets: datasets }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'right', labels: {{ font: {{ size: 12 }} }} }},
      title: {{ display: true, text: '일자별 산업별 공시 건수 (Top 8)', font: {{ size: 16, weight: 'bold' }} }} }},
    scales: {{ x: {{ stacked: true }}, y: {{ stacked: true, beginAtZero: true,
      title: {{ display: true, text: '공시 건수' }} }} }}
  }}
}});
</script>
</div>""")

# === INDEX PAGE ===
parts_html.append(f"""<div class="page">
<div class="page-header">
  <div>AWAKE Daily Disclosure Report — Index</div>
  <div>Page 3 / {TOTAL_PAGES}</div>
</div>
<div class="page-body">
<h2 style="font-size:30px; font-weight:900; color:var(--c-darkest); margin:6px 0 4px 0;">📋 오늘의 공시 인덱스 ({len(DISCLOSURES)}건)</h2>
<div style="font-size:14px; color:var(--c-mute); margin-bottom:10px;">{TODAY} · 종가 yfinance · 종목명 클릭 시 상세 페이지로 이동 · <span id="idx-count-lbl">{len(DISCLOSURES)}건 표시</span></div>
<div id="idx-controls" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px;">
  <span style="font-size:12px;font-weight:700;color:var(--c-darkest);">시그널</span>
  <button class="idx-btn active" data-group="sig" onclick="idxFilter(this,'sig','all')">전체</button>
  <button class="idx-btn" data-group="sig" onclick="idxFilter(this,'sig','up')">매수▲</button>
  <button class="idx-btn" data-group="sig" onclick="idxFilter(this,'sig','down')">매도▼</button>
  <button class="idx-btn" data-group="sig" onclick="idxFilter(this,'sig','neutral')">중립</button>
  <span style="font-size:12px;font-weight:700;color:var(--c-darkest);margin-left:6px;">공시유형</span>
  <button class="idx-btn active" data-group="cat" onclick="idxFilter(this,'cat','all')">전체</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','earnings')">잠정실적</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','ir')">IR/밸류업</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','contract')">공급계약</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','block')">대량보유</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','cb')">CB/사채</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','rights')">유상증자</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','buyback')">자사주</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','dividend')">배당</button>
  <button class="idx-btn" data-group="cat" onclick="idxFilter(this,'cat','ma')">합병/분할</button>
</div>
<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:10px;">
  <span style="font-size:12px;font-weight:700;color:var(--c-darkest);">정렬</span>
  <button class="idx-btn active" data-group="sort" onclick="idxSort('time')">시간순</button>
  <button class="idx-btn" data-group="sort" onclick="idxSort('chg_desc')">등락률↓</button>
  <button class="idx-btn" data-group="sort" onclick="idxSort('chg_asc')">등락률↑</button>
  <button class="idx-btn" data-group="sort" onclick="idxSort('signal')">시그널순</button>
  <button class="idx-btn" data-group="sort" onclick="idxSort('cat')">공시유형순</button>
  <span style="font-size:12px;font-weight:700;color:var(--c-darkest);margin-left:10px;">즐겨찾기</span>
  <button class="idx-btn" data-group="fav" id="fav-filter-btn" onclick="idxToggleFav(this)">⭐ 즐겨찾기만</button>
  <button class="idx-btn" style="font-size:11px;color:#ef4444;" onclick="clearAllFav()">초기화</button>
</div>
<table class="index-table" id="idx-table"><thead>
<tr><th style="width:32px;text-align:center;">⭐</th><th>시각</th><th>종목</th><th>코드</th><th>공시</th><th style="cursor:pointer;" onclick="idxSort(idxSortState==='chg_desc'?'chg_asc':'chg_desc')">등락률 ⇅</th><th>시그널</th></tr></thead><tbody id="idx-tbody">""")

for d in DISCLOSURES:
    sig_class = {"up":"sig-buy","down":"sig-sell","neutral":"sig-neutral"}.get(d["signal_kind"],"sig-neutral")
    _chg_val = d.get("chg_pct") or 0
    _sig_ord = {"up":"0","down":"1","neutral":"2"}.get(d["signal_kind"],"2")
    _rep = d.get("report","")
    if "단일판매" in _rep or "공급계약" in _rep: _cat = "contract"
    elif "잠정실적" in _rep or "영업실적" in _rep or "실적" in _rep: _cat = "earnings"
    elif "IR" in _rep or "기업설명회" in _rep or "기업가치제고" in _rep or "밸류업" in _rep: _cat = "ir"
    elif "대량보유" in _rep or "5%" in _rep: _cat = "block"
    elif "유상증자" in _rep: _cat = "rights"
    elif "전환사채" in _rep or "사채" in _rep or "CB" in _rep: _cat = "cb"
    elif "자기주식" in _rep or "주식소각" in _rep: _cat = "buyback"
    elif "합병" in _rep or "분할" in _rep or "M&A" in _rep: _cat = "ma"
    elif "스톡옵션" in _rep or "주식매수선택권" in _rep: _cat = "stock_option"
    elif "배당" in _rep: _cat = "dividend"
    else: _cat = "other"
    parts_html.append(f"""<tr data-signal="{d["signal_kind"]}" data-chg="{_chg_val:.4f}" data-time="{html.escape(d["time"][:5])}" data-sigord="{_sig_ord}" data-cat="{_cat}" data-code="{html.escape(d["code"])}">
<td style="text-align:center;"><button class="fav-star-idx" data-code="{html.escape(d["code"])}" onclick="toggleFavFromIdx(this,'{html.escape(d["code"])}')">☆</button></td>
<td><strong>{html.escape(d["time"][:5])}</strong></td>
<td><a class="idx-anchor" href="#stock-{html.escape(d["code"])}-{d["id"]}"><strong>{html.escape(d["company"])}</strong></a></td>
<td style="font-family:Inter,sans-serif;font-size:12px;color:var(--c-mute);">A{html.escape(d["code"])}</td>
<td class="disc">{html.escape(d["report"][:80])}</td>
<td>{chg_pill(d["chg_pct"])}</td>
<td><span class="{sig_class}">{html.escape(short_signal(d["signal"]))}</span></td>
</tr>""")
parts_html.append("""</tbody></table>
<script>
var idxState = { sig: 'all', cat: 'all', sort: 'time', fav: false };
function idxFilter(btn, group, val) {
  idxState[group] = val;
  document.querySelectorAll('.idx-btn[data-group="'+group+'"]').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyIdxFilter();
}
function getFavs() { try { return JSON.parse(localStorage.getItem('awake_favs')||'{}'); } catch(e){return {};} }
function saveFavs(f) { try { localStorage.setItem('awake_favs', JSON.stringify(f)); } catch(e){} }
function toggleFavFromIdx(btn, code) {
  var f = getFavs();
  if (f[code]) { delete f[code]; btn.textContent='☆'; btn.classList.remove('fav-on'); }
  else { f[code]=1; btn.textContent='⭐'; btn.classList.add('fav-on'); }
  saveFavs(f);
  // 기업 페이지 별도 업데이트
  var sp = document.getElementById('fav-btn-'+code);
  if(sp) { sp.textContent = f[code]?'⭐':'☆'; sp.classList.toggle('fav-on', !!f[code]); }
  applyIdxFilter();
}
function toggleFavFromPage(code) {
  var f = getFavs();
  var m = getFavMeta();
  if (f[code]) {
    delete f[code];
    delete m[code];
  } else {
    f[code] = 1;
    var btn = document.getElementById('fav-btn-'+code);
    m[code] = {
      name: btn ? btn.dataset.name : code,
      date: btn ? btn.dataset.date : '',
      signal: btn ? btn.dataset.signal : 'neutral',
      report: btn ? btn.dataset.report : '',
      anchor: 'stock-'+code+'-'+(btn ? btn.dataset.code : code)
    };
  }
  saveFavs(f);
  saveFavMeta(m);
  var sp = document.getElementById('fav-btn-'+code);
  if(sp) { sp.textContent = f[code]?'⭐':'☆'; sp.classList.toggle('fav-on', !!f[code]); }
  // 인덱스 행 별도 업데이트
  document.querySelectorAll('.fav-star-idx[data-code="'+code+'"]').forEach(function(b){
    b.textContent = f[code]?'⭐':'☆'; b.classList.toggle('fav-on', !!f[code]);
  });
  applyIdxFilter();
}
function idxToggleFav(btn) {
  idxState.fav = !idxState.fav;
  btn.classList.toggle('active', idxState.fav);
  applyIdxFilter();
}
function clearAllFav() {
  if(!confirm('즐겨찾기를 모두 초기화할까요?')) return;
  saveFavs({});
  document.querySelectorAll('.fav-star-idx,.fav-star-page').forEach(function(b){
    b.textContent='☆'; b.classList.remove('fav-on');
  });
  idxState.fav=false;
  var fb=document.getElementById('fav-filter-btn'); if(fb) fb.classList.remove('active');
  applyIdxFilter();
}
function initFavStars() {
  var f = getFavs();
  document.querySelectorAll('.fav-star-idx').forEach(function(b){
    var c=b.dataset.code; if(f[c]){b.textContent='⭐';b.classList.add('fav-on');}
  });
  document.querySelectorAll('.fav-star-page').forEach(function(b){
    var c=b.dataset.code; if(f[c]){b.textContent='⭐';b.classList.add('fav-on');}
  });
}
window.addEventListener('load', initFavStars);
function idxSort(mode) {
  idxState.sort = mode;
  document.querySelectorAll('.idx-btn[data-group="sort"]').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.idx-btn[data-group="sort"]').forEach(b => {
    if(b.getAttribute('onclick') && b.getAttribute('onclick').includes("'"+mode+"'")) b.classList.add('active');
  });
  var tbody = document.getElementById('idx-tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a,b) {
    if (mode==='chg_desc') return parseFloat(b.dataset.chg||0)-parseFloat(a.dataset.chg||0);
    if (mode==='chg_asc')  return parseFloat(a.dataset.chg||0)-parseFloat(b.dataset.chg||0);
    if (mode==='signal')   return (a.dataset.sigord||'2').localeCompare(b.dataset.sigord||'2');
    if (mode==='cat')      return (a.dataset.cat||'').localeCompare(b.dataset.cat||'');
    return (a.dataset.time||'').localeCompare(b.dataset.time||'');
  });
  rows.forEach(r => tbody.appendChild(r));
  applyIdxFilter();
}
function applyIdxFilter() {
  var rows = document.querySelectorAll('#idx-tbody tr');
  var sigF = idxState.sig, catF = idxState.cat;
  var visible = 0;
  var favs = getFavs();
  rows.forEach(function(r) {
    var sigOk = sigF==='all' || r.dataset.signal===sigF;
    var catOk = catF==='all' || r.dataset.cat===catF;
    var favOk = !idxState.fav || !!favs[r.dataset.code];
    r.style.display = (sigOk && catOk && favOk) ? '' : 'none';
    if(sigOk && catOk && favOk) visible++;
  });
  var lbl = document.getElementById('idx-count-lbl');
  if(lbl) lbl.textContent = visible + '건 표시';
}
</script>""")

parts_html.append(f"""<h3 style="font-size:18px; margin-top:24px; color:var(--c-darkest);">📈 시간외 대량매매 ({len(BIG_TRADES)}건)</h3>
<ul style="font-size:13px; line-height:1.7; columns:2;">""")
for bt in BIG_TRADES:
    parts_html.append(f'<li><strong>{html.escape(bt["company"])}</strong> · {html.escape(bt["amt"])} ({html.escape(bt["trade_type"])})</li>')
parts_html.append(f"""</ul>
<h3 style="font-size:18px; margin-top:18px; color:var(--c-darkest);">⚠️ 단기과열/투자경고 ({len(WARNINGS)}건)</h3>
<ul style="font-size:13px; line-height:1.7; columns:2;">""")
for w in WARNINGS:
    parts_html.append(f'<li><strong>{html.escape(w["company"])}</strong> · {html.escape(w["warning_type"])}</li>')
parts_html.append("</ul></div></div>")

# === PER-COMPANY PAGES ===
page_idx = 4
for code, recs in companies:
    first = recs[0]
    company = first["company"]
    industry = first["industry"]
    mcap = first["mcap"]
    p = first.get("price")
    name_enc = url_quote(company)
    nf = naver.get(code, {}) or {}

    if p:
        chg = p.get("chg_pct", 0) or 0
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "■")
        price_html = f"""<div class="price-card">
<div style="font-size:13px;opacity:0.85;margin-bottom:4px;">종가 ({p.get("last_dt","")})</div>
<div class="price-close">{p["close"]:,.0f}원</div>
<div class="price-chg">{arrow} {chg:+.2f}%</div></div>
<div class="co-mcap">시총 {html.escape(mcap)}</div>"""
    else:
        price_html = f'<div class="price-card"><div class="price-close">- </div></div><div class="co-mcap">시총 {html.escape(mcap)}</div>'

    sig_priority = {"up":2,"down":2,"neutral":1}
    chosen = max(recs, key=lambda r: sig_priority.get(r["signal_kind"],0))

    # Naver Finance table — high readability
    nf_html = ""
    if nf and "rows" in nf and nf["rows"]:
        periods = nf.get("periods", [])
        if len(periods) >= 10:
            ann_idx = list(range(4))
            fwd_idx = {3}  # 2026.12(E)
            qfwd_idx = {9}  # 2026.03(E)
        else:
            ann_idx = list(range(min(4, len(periods))))
            fwd_idx = set()
            qfwd_idx = set()
        # Two-row header: group label + period
        head_grp = '<th class="grp-label metric-head" rowspan="2">주요재무정보</th>'
        ann_count = sum(1 for i in range(len(periods)) if i in ann_idx)
        qtr_count = len(periods) - ann_count
        if ann_count > 0:
            head_grp += f'<th class="grp-label" colspan="{ann_count}">최근 연간 실적 (억원/원)</th>'
        if qtr_count > 0:
            head_grp += f'<th class="grp-label" colspan="{qtr_count}">최근 분기 실적 (억원/원)</th>'

        head_periods = ""
        for i, p_ in enumerate(periods):
            label = clean_val(p_)
            if i in fwd_idx or i in qfwd_idx:
                label += " (E)"
            head_periods += f'<th>{html.escape(label)}</th>'

        nf_html = f"""<div class="nf-wrap"><table class="nf-table"><thead>
<tr>{head_grp}</tr>
<tr>{head_periods}</tr>
</thead><tbody>"""
        # Rows
        for metric, vals in nf["rows"].items():
            metric_cl = clean_val(metric)
            if not metric_cl or metric_cl == "-":
                continue
            nf_html += f'<tr><td class="metric">{html.escape(metric_cl)}</td>'
            for i, v in enumerate(vals):
                v_str = clean_val(v)
                cell_cls = "cell-annual" if i in ann_idx else "cell-quarterly"
                if i in fwd_idx or i in qfwd_idx:
                    cell_cls = "cell-fwd"
                if v_str == "-":
                    cell_cls += " cell-empty"
                # Negative number coloring (e.g. "-1,234" or "-7.45")
                if v_str.startswith("-") and any(ch.isdigit() for ch in v_str):
                    cell_cls += " cell-neg"
                nf_html += f'<td class="{cell_cls}">{html.escape(v_str)}</td>'
            nf_html += "</tr>"
        nf_html += "</tbody></table></div>"
    else:
        nf_html = '<div style="font-size:14px; color:var(--c-mute);">네이버 금융 데이터 조회 실패. 외부 링크에서 직접 확인하세요.</div>'

    parts_html.append(f"""<div class="page" id="stock-{html.escape(code)}-{first['id']}">
<div class="page-header">
  <div>AWAKE — {html.escape(company)}</div>
  <div>Page {page_idx} / {TOTAL_PAGES}</div>
</div>
<div class="page-body">
<div class="stock-meta">
  <div class="co-block">
    <div style="display:flex;align-items:center;gap:10px;">
      <div class="co-name">{html.escape(company)}</div>
      <button id="fav-btn-{html.escape(code)}" class="fav-star-page" data-code="{html.escape(code)}" data-name="{html.escape(company)}" data-date="{TODAY}" data-signal="{chosen['signal_kind']}" data-report="{html.escape(first['report'])}" onclick="toggleFavFromPage('{html.escape(code)}')" title="즐겨찾기">☆</button>
    </div>
    <div class="co-code">A{html.escape(code)}</div>
    <div>
      <span class="co-sector">{html.escape(industry)}</span>
      <span class="signal-pill" style="background:{signal_color(chosen['signal_kind'])};">{html.escape(chosen['signal'])}</span>
    </div>
  </div>
  <div style="text-align:right;">{price_html}</div>
</div>

<h3 class="section-title">🏢 사업 BM</h3>
<div class="bm-text">{html.escape(first['bm'])}</div>""")

    # 매출 구성 cards (v9 스타일 — % + 부문명 + 부가설명)
    segs = first.get("segments") or []
    if segs:
        seg_cards = ""
        for i, seg in enumerate(segs):
            # Support both dict {name, pct, note} and string formats
            if isinstance(seg, dict):
                pct = seg.get("pct") or "-"
                name = seg.get("name") or f"사업 {i+1}"
                note = seg.get("note") or ""
                pct_disp = f"{html.escape(pct)}%" if pct and pct != "-" else "-"
            else:
                pct_disp = "-"
                name = f"사업 {i+1}"
                note = str(seg)
            seg_cards += f'''<div style="flex:1; min-width:170px; background:#eff6ff; border:1px solid #dbeafe; border-radius:10px; padding:18px 14px; text-align:center;">
                <div style="font-family:Inter,sans-serif; font-size:30px; font-weight:800; color:var(--c-dark); line-height:1;">{pct_disp}</div>
                <div style="font-size:16px; font-weight:700; color:var(--c-darkest); margin-top:8px;">{html.escape(name)}</div>
                <div style="font-size:13px; color:var(--c-mute); margin-top:6px; line-height:1.4;">{html.escape(note)}</div>
            </div>'''
        # Source label
        ov_c = ENRICHED.get(d["code"], {})
        if ov_c.get("segments"):
            src_label = "수동 큐레이션"
        elif ov_c.get("segments_daily"):
            src_label = "WebSearch 분석"
        else:
            src_label = "yfinance 자동 추출"
        parts_html.append(f"""<div style="margin-top:14px;">
        <div style="font-size:14px; color:var(--c-mute); font-weight:700; margin-bottom:8px;">매출 구성 <span style="font-weight:400; opacity:0.7;">({src_label})</span></div>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">{seg_cards}</div>
        </div>""")

    # 핵심 경쟁력
    strength = first.get("strength")
    if strength:
        parts_html.append(f"""<div style="margin-top:12px; font-size:15px;">
        <strong style="color:var(--c-dark);">핵심 경쟁력</strong> &nbsp; {html.escape(strength)}
        </div>""")

    # 주요 고객
    customers = first.get("customers")
    if customers:
        parts_html.append(f"""<div style="margin-top:6px; font-size:15px;">
        <strong style="color:var(--c-dark);">주요 고객</strong> &nbsp; {html.escape(customers)}
        </div>""")

    parts_html.append(f"""<h3 class="section-title">📌 오늘의 공시 ({len(recs)}건)</h3>""")

    for rec in recs:
        parts_html.append(f"""<div class="disc-card" id="stock-{html.escape(code)}-{rec['id']}">
  <div class="disc-head">
    <div class="disc-meta">
      <div class="disc-time">{html.escape(rec["time"])} · 접수 {html.escape(rec["rcpNo"] or "-")}</div>
      <div class="disc-title">{html.escape(rec["report"])}</div>
    </div>
    {'<a class="dart-orig-link" href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + html.escape(rec["rcpNo"]) + '" target="_blank">📄 DART 원문 ▶</a>' if rec["rcpNo"] else ''}
  </div>
  <div class="disc-body">{html.escape(rec["body_full"])}</div>
</div>

<h3 class="section-title">🎯 시그널 근거</h3>
<div class="signal-reason-box">{html.escape(rec['signal_reason'])}</div>

<div class="insight-card">
  <div class="insight-title">💡 투자 인사이트 (종합 관점)</div>
  <div class="insight-text">{html.escape(rec['insight'])}</div>
</div>

<div class="watch-list">
  <h4>👁 모니터링 체크포인트</h4>
  <ul>{''.join('<li>' + html.escape(w) + '</li>' for w in rec['watch'])}</ul>
</div>""")

    parts_html.append(f"""<h3 class="section-title">📊 재무 한 줄</h3>
<div class="fin-line">{html.escape(first['fin'])}</div>

<h3 class="section-title">📈 네이버 금융 — 기업실적분석</h3>
{nf_html}

<h3 class="section-title">🔗 외부 링크</h3>
<div class="ext-links">
  <a class="ext-link" href="https://search.naver.com/search.naver?where=news&query={name_enc}&sort=1" target="_blank">📰 네이버 뉴스</a>
  <a class="ext-link" href="https://m.stock.naver.com/domestic/stock/{code}/overview" target="_blank">📈 네이버 금융</a>
  <a class="ext-link" href="https://dart.fss.or.kr/dsab007/main.do?autoSearch=Y&option=corp&textCrpNm={name_enc}" target="_blank">🏛 DART 공시</a>
  <a class="ext-link" href="https://www.google.com/search?q={name_enc}+{code}&tbm=nws" target="_blank">🌐 Google 뉴스</a>
</div>
</div></div>""")
    page_idx += 1

parts_html.append("</body></html>")

html_out = "".join(parts_html)
out_path = "/sessions/funny-wizardly-keller/mnt/outputs/AWAKE_v11.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_out)
print(f"✓ Wrote {out_path} ({len(html_out):,} chars)")
print(f"  Disclosures: {len(DISCLOSURES)} | Companies: {len(by_company)} | Pages: {TOTAL_PAGES}")
print(f"  Top industries: {[(k,v) for k,v in top_inds[:5]]}")
print(f"  Buy/Sell/Neutral: {n_buy}/{n_sell}/{len(DISCLOSURES)-n_buy-n_sell}")

# ★ 정책 검증: 모든 종목이 큐레이션되어야 함
missing_curation = []
for code in by_company:
    if code not in ENRICHED:
        first = by_company[code][0]
        missing_curation.append((code, first["company"]))
if missing_curation:
    print(f"\n⚠️  큐레이션 누락 종목 {len(missing_curation)}개:")
    for code, name in missing_curation:
        print(f"    {code}\t{name}")
    print("  → enriched_overrides.json에 즉시 추가 필요 (사용자 명시 정책)")
else:
    print(f"\n✅ 큐레이션 정책 준수 — 전 {len(by_company)}개 종목 한글 큐레이션 적용됨")
