#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AWAKE v11 빌더 — v9 풀템플릿 + 네이버금융 표 + 산업 모멘텀 차트."""
import json, html, urllib.parse, re, os
from collections import defaultdict, Counter

TODAY = "2026-04-29"
TODAY_DISP = "2026년 4월 29일 (수)"

with open("/sessions/pensive-awesome-meitner/mnt/outputs/parsed_disclosures.json", encoding="utf-8") as f:
    parsed = json.load(f)
with open("/sessions/pensive-awesome-meitner/mnt/outputs/prices_all.json", encoding="utf-8") as f:
    prices = json.load(f)
with open("/sessions/pensive-awesome-meitner/mnt/outputs/company_info.json", encoding="utf-8") as f:
    company_info = json.load(f)
with open("/sessions/pensive-awesome-meitner/mnt/outputs/naver_finance.json", encoding="utf-8") as f:
    naver = json.load(f)

# 한글 큐레이션된 overrides (WebSearch + 사용자 지식 기반)
ENRICHED = {}
override_path = "/sessions/pensive-awesome-meitner/mnt/outputs/enriched_overrides.json"
if os.path.exists(override_path):
    with open(override_path, encoding="utf-8") as f:
        ENRICHED = json.load(f)

# Aggregates (cumulative)
AGG_PATH = "/sessions/pensive-awesome-meitner/mnt/outputs/daily_aggregates.json"
agg_data = {"by_date": {}}
if os.path.exists(AGG_PATH):
    with open(AGG_PATH, encoding="utf-8") as f:
        agg_data = json.load(f)

DISCLOSURES = parsed["disclosures"]
BIG_TRADES = parsed["big_trades"]
WARNINGS = parsed["warnings"]


# ============= INDUSTRY CLASSIFICATION =============
INDUSTRY_KEYWORDS = [
    ("반도체", ["반도체", "장비", "패키징", "DRAM", "NAND", "HBM", "포토", "에칭", "CVD", "ALD", "비메모리", "SoC", "Semiconductor", "Foundry"]),
    ("디스플레이", ["디스플레이", "OLED", "LCD", "패널", "Display"]),
    ("조선/엔진", ["조선", "엔진", "선박", "마린엔진", "Marine", "Shipbuild"]),
    ("자동차/모빌리티", ["자동차", "차량", "모터스", "타이어", "변속", "Motor", "Auto", "현대차", "기아"]),
    ("배터리/2차전지", ["배터리", "2차전지", "양극재", "음극재", "전해", "분리막", "전구체", "리튬", "ESS", "Battery"]),
    ("연료전지/수소", ["연료전지", "수소", "퓨얼셀", "Hydrogen", "FuelCell"]),
    ("바이오/제약", ["바이오", "제약", "치료제", "백신", "신약", "CAR-T", "오가노이드", "임상", "면역", "항체", "Pharma", "Bio"]),
    ("의료기기", ["의료", "진단", "기기", "Medical", "Diagnos"]),
    ("화장품/뷰티", ["화장품", "뷰티", "코스메", "아모레", "Cosm", "Beauty"]),
    ("게임", ["게임", "Game", "Studio", "넷마블", "엔씨", "크래프톤", "넥슨", "위메이드", "데브시스터즈"]),
    ("엔터/콘텐츠", ["엔터", "콘텐츠", "드라마", "음악", "아이돌", "K-POP", "HYBE", "JYP", "SM", "Entertainment", "스튜디오드래곤"]),
    ("미디어/방송", ["방송", "미디어", "CGV", "CJ ENM", "방송통신"]),
    ("로봇/AI", ["로봇", "Robot", "AI", "인공지능", "자동화"]),
    ("화학/소재", ["화학", "Polymer", "석유", "유화", "소재", "Chemical", "Materials"]),
    ("철강/금속", ["철강", "Steel", "금속", "전선", "동", "알루미늄", "Cable", "Wire", "비철"]),
    ("건설/건축", ["건설", "건축", "토목", "시공", "Construction", "건자재", "주택"]),
    ("금융", ["증권", "금융지주", "Bank", "보험", "운용", "Asset", "Holdings", "Finance", "은행", "Securities"]),
    ("IT/SW", ["플랫폼", "소프트웨어", "Software", "클라우드", "Cloud", "보안", "인터넷", "디지털"]),
    ("전기/전자", ["전기", "전자", "Electric", "Electron"]),
    ("식품/유통", ["식품", "음료", "Food", "유통", "편의", "마트", "백화", "호텔", "리츠", "Beverage", "F&B"]),
    ("방산/항공", ["방산", "국방", "항공", "드론", "Defense", "Aero", "MRO"]),
    ("에너지/유틸리티", ["에너지", "Energy", "전력", "Power", "Utility", "발전", "신재생"]),
]


def classify_industry(d):
    ci = company_info.get(d["code"], {})
    parts = [d["company"]]
    if ci.get("dart"):
        parts.append(ci["dart"].get("corp_name", ""))
    if ci.get("yf"):
        parts.append(ci["yf"].get("name_en", ""))
        parts.append(ci["yf"].get("industry", ""))
        parts.append((ci["yf"].get("summary") or "")[:300])
    parts.append(d["report"])
    parts.append(d["body_full"][:300])
    blob = " ".join(parts).lower()
    for label, kws in INDUSTRY_KEYWORDS:
        for kw in kws:
            if kw.lower() in blob:
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


# ============= AUTO SIGNAL REASON =============
def signal_reason(d):
    rep, body = d["report"], d["body_full"]
    co = d["company"]
    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        m = re.search(r"매출액\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        op = re.search(r"영업익\s*[:：]\s*([\d,]+억)\s*\(예상치\s*[:：]\s*([\d,]+억)\s*\/\s*([+\-]?\d+)%\)", body)
        chunks = []
        if m:
            chunks.append(f"매출 {m.group(1)} (컨센 {m.group(3)}%)")
        if op:
            chunks.append(f"영업익 {op.group(1)} (컨센 {op.group(3)}%)")
        return f"잠정실적 발표 — {', '.join(chunks)}." if chunks else "분기 잠정실적 발표 — 컨센 대비 상회/미스 여부 확인."
    if "단일판매" in rep and "체결" in rep:
        m = re.search(r"계약금액\s*[:：]\s*([^\n]+)", body)
        m2 = re.search(r"매출대비\s*[:：]\s*([+\-]?[\d.]+)\s*%", body)
        amt = m.group(1).strip() if m else "-"
        pct = m2.group(1) if m2 else "-"
        return f"신규 공급계약 체결 — 계약금액 {amt}, 매출대비 {pct}%."
    if "공급계약해지" in rep:
        m = re.search(r"해지금액\s*[:：]\s*([^\n]+)", body)
        m2 = re.search(r"매출대비\s*[:：]\s*([^\n]+)", body)
        return f"기존 계약 해지 — 해지금액 {m.group(1).strip() if m else '-'}, 매출대비 {m2.group(1).strip() if m2 else '-'}."
    if "자기주식취득" in rep:
        return f"자기주식 취득 결정 — 발행주식수 감소·EPS 제고 효과."
    if "주식소각" in rep:
        return f"주식 소각 결정 — 발행주식수 영구 감소로 가장 강력한 주주환원."
    if "자기주식처분" in rep:
        return f"자기주식 처분 결정 — 처분목적·중개업자 본문 확인."
    if "현금" in rep and "배당" in rep:
        return f"배당 결정 — 시가배당률·배당기준일 본문 확인."
    if "기업가치제고" in rep:
        return f"기업가치 제고 계획 공시 — 주주환원 정책 강화."
    if "전환사채" in rep and "발행" in rep:
        m = re.search(r"발행금액\s*[:：]\s*([^\n(]+)", body)
        return f"CB 발행 결정 — 발행금액 {m.group(1).strip() if m else '-'}. 향후 전환 시 잠재 희석."
    if "유상증자" in rep:
        return f"유상증자 결정 — 발행구조·인수처·자금사용처 본문 확인."
    if "전환청구" in rep:
        return f"기발행 CB·BW의 전환청구 — 신주 상장으로 잠재 매물 출회."
    if "회사합병" in rep:
        m = re.search(r"대상회사\s*[:：]\s*([^\n]+)", body)
        return f"회사 합병 결정 — 대상사 {m.group(1).strip() if m else '-'}. 합병기일·매수청구권 확인."
    if "타법인주식" in rep and "취득" in rep:
        m = re.search(r"취득회사\s*[:：]\s*([^\n]+)", body)
        m2 = re.search(r"취득금액\s*[:：]\s*([^\n]+)", body)
        return f"타법인 주식 취득 — 대상사 {m.group(1).strip() if m else '-'}, 취득금액 {m2.group(1).strip() if m2 else '-'}."
    if "대량보유" in rep:
        m = re.search(r"보고전\s*[:：]\s*([\d.]+%)", body)
        m2 = re.search(r"보고후\s*[:：]\s*([\d.]+%)", body)
        return f"대량보유 보고 — 지분율 {m.group(1) if m else '-'} → {m2.group(1) if m2 else '-'}."
    if "경영권분쟁" in rep or "소송" in rep:
        return f"법적 분쟁 발생 — 가처분 결정·주총 진행 양상에 따라 변동성 확대."
    if "투자판단" in rep:
        if "허가" in body or "승인" in body:
            return f"투자판단 관련 — 규제기관 허가/승인. 매출 인식·후속 사업화 가능."
        if "취소" in body and "가압류" in body:
            return f"투자판단 관련 — 가압류 취소 호재."
        return f"투자판단 관련 주요 경영사항 — 본문 내용에 따라 호재/악재 판별."
    if "IR" in rep or "기업설명회" in rep:
        return f"IR 개최 안내 — 발표 자료의 가이던스·신사업 코멘트가 시장 예상 부합 여부 확인."
    return f"{co} 일반 공시 — 본문 내용 기반 호재/악재 판별 필요."


# ============= AUTO INSIGHT =============
def auto_insight(d):
    rep, body, co = d["report"], d["body_full"], d["company"]
    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        return f"{co}의 분기 잠정실적은 단기 주가 방향을 결정하는 핵심 변수. 컨센 상회 시 어닝 서프라이즈 모멘텀, 미스 시 외국인·기관 차익실현 가능. 다음 분기 가이던스와 4Q 추이를 함께 확인."
    if "단일판매" in rep and "체결" in rep:
        return f"신규 공급계약은 매출 가시성을 높이지만, 수익성·계약기간·해지 리스크를 함께 봐야 함. 동종 업계의 다른 수주와 비교해 시장점유율·수주잔고 추이 모니터링 필요."
    if "공급계약해지" in rep:
        return f"기존 계약 해지는 단기 매출·실적 모멘텀에 부정적. 대체 수주·재계약 가능성과 경영진 대응을 추적. 1회성 vs 구조적 문제 여부 판단이 핵심."
    if "자기주식취득" in rep or "주식소각" in rep:
        return f"주주환원 정책 강화 시그널. 시총 대비 규모, 정기성·반복성, 향후 추가 발표 여부가 정책의 진정성을 좌우. 단기 수급보다 장기 가치 평가 관점."
    if "자기주식처분" in rep:
        return f"임직원 보상이라면 영향 미미, 시장 매도라면 단기 수급 부담. 처분 목적과 중개 방식 본문 확인 필수."
    if "현금" in rep and "배당" in rep:
        return f"배당은 안정적 현금 창출 능력의 증빙. 시가배당률, 배당성향, 정기성을 트랙킹. ESG·국내 배당주 펀드 자금 유입 가능."
    if "기업가치제고" in rep:
        return f"정부의 밸류업 프로그램 호응. 구체적 ROE 목표·자사주 매입·배당정책이 핵심. 실행력에 따라 재평가 가능."
    if "전환사채" in rep and "발행" in rep:
        return f"CB는 자금조달 수단이나 1년 후 전환 시 잠재 희석. 인수자(코스닥벤처투자신탁 등)·전환가·최저조정가 분석 필요. 주가 하락 시 추가 희석 위험."
    if "유상증자" in rep:
        return f"유증은 단기 희석 부담. 자금 사용처가 신사업·M&A·재무구조 개선이면 중장기 호재 가능. 발행구조·할인율·인수자 검토."
    if "전환청구" in rep:
        return f"이미 발행된 CB·BW의 전환은 신주 상장 시점 매물 출회 부담. 전환 비중·이미 행사된 차익 여부로 단기 수급 압력 추정."
    if "회사합병" in rep:
        return f"합병은 통합 시너지 vs 매수청구권 부담의 균형. 신주발행 여부·EPS 영향·CEO 메시지 중요. 자회사 흡수면 영향 제한, 동등 합병이면 영향 큼."
    if "타법인주식" in rep and "취득" in rep:
        return f"타법인 출자는 신사업·해외 진출 의지의 표명. 자본대비 비중·시너지 검증·인수 후 PMI 진행상황 모니터링."
    if "대량보유" in rep:
        return f"대량보유 보고는 수급 시그널. 보유목적(경영권 영향·단순투자·자산운용)과 증감 방향이 시장 해석의 핵심. 5% 신규 진입(국민연금) vs 5% 매도(피델리티) 의미 다름."
    if "경영권분쟁" in rep or "소송" in rep:
        return f"분쟁 종목은 단기 변동성이 매우 큼. 가처분 결정·표 대결 결과에 따라 양극단 시나리오. 보유자는 리스크 관리, 투기적 진입은 신중."
    if "투자판단" in rep:
        if "허가" in body or "승인" in body:
            return f"규제기관 허가/승인은 매출 인식·사업화 출발점. 보험 등재·해외 인허가·생산 capacity 등 후속 일정이 실제 매출로 연결되는 핵심 트리거."
        return f"투자판단 관련 본문을 정독하고 호재/악재 판별 후 관련 일정 트래킹. 시장 반응과 수급 변화 모니터링."
    if "IR" in rep or "기업설명회" in rep:
        return f"IR은 가이던스·신사업·실적 코멘트가 시장 예상에 부합하는지 확인하는 자리. 발표 후 주가 반응이 가장 신뢰할만한 시그널."
    if "풍문" in rep or "해명" in rep:
        return f"미확정·사실무근 답변은 단기 변동성을 잠시 진정시키나, 근본적 의문은 후속 공시로 해소되어야 함."
    return f"{co}의 일반 공시. 본문 내용 기반 호재/악재 판별, 후속 일정과 시장 반응 모니터링."


# ============= AUTO WATCH (Monitoring checkpoints) =============
def auto_watch(d):
    rep = d["report"]
    co = d["company"]
    if "영업(잠정)실적" in rep or "잠정실적" in rep:
        return ["다음 분기 가이던스 발표", "외국인·기관 수급 변화", "동종업계 어닝 비교"]
    if "단일판매" in rep and "체결" in rep:
        return ["계약 진행 상황 (분기 IR)", "후속 수주 발표", "수주잔고 누적 추이"]
    if "공급계약해지" in rep:
        return ["대체 수주 발표", "1Q26 매출 실제 영향", "해당 사업부 다각화 진척"]
    if "자기주식취득" in rep or "주식소각" in rep:
        return ["취득·소각 완료 공시", "추가 자사주 정책 발표", "EPS·BPS 변화"]
    if "자기주식처분" in rep:
        return ["처분 진행 상황", "처분 목적별 용도 자금 사용", "추가 처분 가능성"]
    if "전환사채" in rep and "발행" in rep:
        return ["주가 vs 전환가 추이", "최저조정가 트리거 여부", "1년 후 전환청구 시점"]
    if "유상증자" in rep:
        return ["발행가 확정 공시", "청약률·실권주 비중", "자금 사용 진척"]
    if "전환청구" in rep:
        return ["신주 상장일", "추가 전환청구 잔여 물량", "차익 실현 매물"]
    if "회사합병" in rep:
        return ["주주총회 일정", "매수청구권 행사 규모", "합병 후 통합 시너지"]
    if "타법인주식" in rep and "취득" in rep:
        return ["출자 자회사 첫 매출", "PMI 진척", "추가 출자 가능성"]
    if "대량보유" in rep:
        return ["다음 분기 변동 보고", "보유목적 변경 여부", "수급 동향"]
    if "경영권분쟁" in rep or "소송" in rep:
        return ["가처분 결정문 공시", "임시주총 개최 여부", "최대주주 vs 청구측 지분율"]
    if "기업가치제고" in rep:
        return ["구체적 KPI 발표(ROE·배당성향)", "자사주 매입·소각 실행", "분기 IR 가이던스"]
    if "투자판단" in rep:
        return ["보험 등재·매출 인식 시점", "해외 진출 발표", "후속 임상·R&D"]
    if "IR" in rep or "기업설명회" in rep:
        return ["IR 발표 자료 검토", "가이던스 vs 컨센 비교", "분기 실적 발표일"]
    return ["분기 IR 발표", "DART 후속 공시", "외국인·기관 수급"]


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
    d["bm"] = ov.get("bm") or auto_bm(d)
    # segments override는 dict list 형태 ({name, pct, note}), auto는 list[str]
    d["segments"] = ov.get("segments") or extract_segments(d)
    d["customers"] = ov.get("customers") or extract_customers(d)
    d["strength"] = ov.get("strength") or extract_strength(d)
    d["signal_reason"] = signal_reason(d)
    d["insight"] = auto_insight(d)
    d["watch"] = auto_watch(d)
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
.idx-anchor {{ color:var(--c-dark); text-decoration:none; }}
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
<div style="font-size:14px; color:var(--c-mute); margin-bottom:10px;">{TODAY} · 시간순 정렬 · 종가 yfinance · 종목명 클릭 시 상세 페이지로 이동</div>
<table class="index-table"><thead>
<tr><th>시각</th><th>종목</th><th>코드</th><th>공시</th><th>등락률</th><th>시그널</th></tr></thead><tbody>""")

for d in DISCLOSURES:
    sig_class = {"up":"sig-buy","down":"sig-sell","neutral":"sig-neutral"}.get(d["signal_kind"],"sig-neutral")
    parts_html.append(f"""<tr>
<td><strong>{html.escape(d["time"][:5])}</strong></td>
<td><a class="idx-anchor" href="#stock-{html.escape(d["code"])}-{d["id"]}"><strong>{html.escape(d["company"])}</strong></a></td>
<td style="font-family:Inter,sans-serif;font-size:12px;color:var(--c-mute);">A{html.escape(d["code"])}</td>
<td class="disc">{html.escape(d["report"][:80])}</td>
<td>{chg_pill(d["chg_pct"])}</td>
<td><span class="{sig_class}">{html.escape(short_signal(d["signal"]))}</span></td>
</tr>""")
parts_html.append("</tbody></table>")

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
    <div class="co-name">{html.escape(company)}</div>
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
        src_label = "수동 큐레이션" if d["code"] in ENRICHED else "yfinance 자동 추출"
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
        parts_html.append(f"""<div class="disc-card">
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
  <a class="ext-link" href="https://finance.naver.com/item/main.naver?code={code}" target="_blank">📈 네이버 금융</a>
  <a class="ext-link" href="https://dart.fss.or.kr/dsab007/main.do?autoSearch=Y&option=corp&textCrpNm={name_enc}" target="_blank">🏛 DART 공시</a>
  <a class="ext-link" href="https://www.google.com/search?q={name_enc}+{code}&tbm=nws" target="_blank">🌐 Google 뉴스</a>
</div>
</div></div>""")
    page_idx += 1

parts_html.append("</body></html>")

html_out = "".join(parts_html)
out_path = "/sessions/pensive-awesome-meitner/mnt/outputs/AWAKE_v11.html"
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
