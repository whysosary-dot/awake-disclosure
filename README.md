# 📑 AWAKE 일일 공시 리포트

매일 평일 오후 8시(장 종료 후), 텔레그램 AWAKE 채널의 당일 공시를 수집하고 종목별 1페이지 매매 리포트로 자동 발행합니다.

🌐 **[Live: whysosary-dot.github.io/awake-disclosure](https://whysosary-dot.github.io/awake-disclosure/)**

## 구성
- **사업 BM·매출 구성**: 한국 상장사 사전 지식 + DART 사업보고서
- **종가·등락률**: yfinance (.KS/.KQ 자동 판별, 가장 최신 거래일 우선)
- **공시 본문**: AWAKE 채널 텔레그램 메시지 정리
- **재무 한 줄**: DART 전자공시 2025 연결재무제표 (CFS 우선, OFS fallback)
- **매매 시그널**: 공시 유형별 분류(강매수/매수/중립/매도/위험회피)
- **투자 인사이트**: 종목 본질·BM 함의·향후 트래킹 포인트 통합 1-2문단

## 자동화
Cowork 스케줄 작업 `awake-daily-disclosure-report` (cron: `0 20 * * 1-5`)이 매일 평일 20시에 실행되어 `reports/`에 새 HTML을 추가하고 `index.html` 목록을 갱신한 뒤 자동 commit/push 합니다.

## 디렉토리
```
/
├── index.html                  # 날짜 인덱스 페이지
├── reports/
│   ├── AWAKE_2026-04-28.html   # 종목별 1페이지 리포트 (커버+인덱스+58개 종목)
│   └── ...
└── README.md
```

## 데이터 소스
- [AWAKE 채널](https://t.me/awakemarkets) — 실시간 주식 공시 정리 채널
- [DART 전자공시시스템](https://opendart.fss.or.kr) — 사업·재무 데이터
- [Yahoo Finance](https://finance.yahoo.com) (yfinance) — 종가·등락률·거래량

## 면책
본 자료는 투자 참고용이며 매수/매도를 권유하지 않습니다. 사업 BM·매출 구성은 공개 자료 + 일반 지식 기반의 정리이며, 매매 시그널은 공시 유형 + 실적/지분 흐름의 단기 해석입니다. 투자의 최종 판단·책임은 투자자 본인에게 있습니다.
