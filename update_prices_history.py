#!/usr/bin/env python3
"""
prices_history.json 매일 갱신 스크립트

매일 빌드 직후 호출:
    python3 update_prices_history.py YYYY-MM-DD

동작:
1. outputs/AWAKE_v11.html 또는 reports/AWAKE_{DATE}.html에서 종목별 close/chg 추출
   - 우선순위 1: data-close/data-chg 속성 (build_report_v11.py가 최근 추가)
   - 우선순위 2: <div class="price-close">N원</div> + 같은 섹션 data-chg
2. 기존 prices_history.json을 읽어 머지
3. AWAKE 디렉토리 + /tmp/awake-disclosure-fresh 둘 다 저장 (배포 단계가 사용)

종속성: 표준 라이브러리만
"""
import os, re, json, sys, pathlib

def find_awake_dir():
    """AWAKE 디렉토리를 찾는다 — 실행 위치 무관"""
    here = pathlib.Path(__file__).resolve().parent
    if (here / 'build_report_v11.py').exists():
        return here
    # /sessions/*/mnt 안에서 검색
    for s in pathlib.Path('/sessions').iterdir() if pathlib.Path('/sessions').exists() else []:
        mnt = s / 'mnt'
        if mnt.is_dir():
            for d in mnt.iterdir():
                if d.is_dir() and 'AWAKE' in d.name:
                    return d
    raise RuntimeError('AWAKE 디렉토리 못 찾음')

def extract_from_html(content):
    """리포트 HTML 1개에서 {code: {close, chg}} 딕셔너리 추출"""
    by_code = {}

    # ① 우선: data-close/data-chg 속성 (build_report_v11.py가 fav-star 버튼에 넣음)
    pattern_dc = re.compile(
        r'data-code="(\d+)"[^>]*?data-close="(-?\d+(?:\.\d+)?)"[^>]*?data-chg="(-?\d+(?:\.\d+)?)"',
        re.DOTALL
    )
    for code, close, chg in pattern_dc.findall(content):
        try:
            cn, gn = float(close), float(chg)
            if cn > 0:
                by_code[code] = {'close': cn, 'chg': gn}
        except: pass

    # ② fallback: <tr data-code="..." data-chg="..."> 인덱스 row + <div class="price-close">
    if not by_code:
        chg_map = {}
        for m in re.finditer(r'<tr[^>]*?data-chg="(-?\d+(?:\.\d+)?)"[^>]*?data-code="(\d+)"', content, re.DOTALL):
            chg_map[m.group(2)] = float(m.group(1))
        for m in re.finditer(r'<tr[^>]*?data-code="(\d+)"[^>]*?data-chg="(-?\d+(?:\.\d+)?)"', content, re.DOTALL):
            if m.group(1) not in chg_map:
                chg_map[m.group(1)] = float(m.group(2))

        # stock-CODE-ID 섹션별 price-close 추출
        sections = re.split(r'(<div class="page" id="stock-(\d{6})-)', content)
        i = 1
        while i < len(sections):
            if sections[i].startswith('<div class="page" id="stock-'):
                code = sections[i+1]
                chunk = sections[i+2] if i+2 < len(sections) else ''
                m_pc = re.search(r'<div class="price-close">([\d,]+)\s*원', chunk[:8000])
                if m_pc:
                    try:
                        cn = float(m_pc.group(1).replace(',',''))
                        if cn > 0:
                            by_code[code] = {'close': cn, 'chg': chg_map.get(code, 0)}
                    except: pass
                i += 3
            else:
                i += 1
    return by_code

def main():
    if len(sys.argv) < 2:
        print('사용법: python3 update_prices_history.py YYYY-MM-DD')
        sys.exit(1)

    date = sys.argv[1]
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        print(f'잘못된 날짜 형식: {date}')
        sys.exit(1)

    awake = find_awake_dir()

    # 1) 오늘 빌드된 HTML 찾기
    candidates = [
        awake / f'AWAKE_{date}.html',
        # outputs 디렉토리도 시도
        pathlib.Path('/sessions') / pathlib.Path(__file__).parent.name / 'mnt' / 'outputs' / 'AWAKE_v11.html'
            if pathlib.Path('/sessions').exists() else None,
    ]
    # outputs 디렉토리 추가 탐색 (권한 에러 무시)
    sessions_root = pathlib.Path('/sessions')
    if sessions_root.exists():
        try:
            for s in sessions_root.iterdir():
                try:
                    op = s / 'mnt' / 'outputs' / 'AWAKE_v11.html'
                    if op.exists():
                        candidates.append(op)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

    html_path = None
    for c in candidates:
        if c and c.exists():
            html_path = c
            break

    if not html_path:
        print(f'❌ AWAKE_{date}.html / AWAKE_v11.html 둘 다 없음')
        sys.exit(1)

    print(f'📄 입력: {html_path}')
    content = html_path.read_text(encoding='utf-8')
    new_prices = extract_from_html(content)
    print(f'✓ 추출: {len(new_prices)}개 종목')

    if not new_prices:
        print('⚠️  추출된 가격 없음. 리포트 HTML에 data-close 또는 price-close가 없을 수 있음.')
        sys.exit(2)

    # 2) 기존 prices_history.json 머지
    history_path = awake / 'prices_history.json'
    if history_path.exists():
        with history_path.open(encoding='utf-8') as f:
            history = json.load(f)
    else:
        history = {}

    history[date] = new_prices

    # 3) 저장 (AWAKE 디렉토리)
    with history_path.open('w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False)
    total = sum(len(v) for v in history.values())
    print(f'💾 저장: {history_path} ({len(history)}개 날짜, 총 {total}개 (날짜,종목) 쌍)')

    # 4) /tmp/awake-disclosure-fresh 에도 복사 (배포 단계가 사용)
    fresh = pathlib.Path('/tmp/awake-disclosure-fresh')
    if fresh.exists():
        target = fresh / 'prices_history.json'
        target.write_text(history_path.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'💾 배포본 복사: {target}')

    print('✅ 완료')

if __name__ == '__main__':
    main()
