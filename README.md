# 🌍 Issuse_collecter — 해외 경제 뉴스 수집 & 국내 증시 영향 분석

미국 국채금리 · 금리 · 경제상황 · 세계 증시 · 세계 전쟁 · 원유가격 관련
해외 뉴스를 무료 RSS에서 모아 **한국어 번역**과 함께 보여주고,
수집된 뉴스로 **국내 증시에 미칠 영향**을 자동 분석하는 Streamlit 앱입니다.

## 주요 기능
- 📰 6개 경제 주제 뉴스만 자동 수집·분류 (무료 RSS, API 키 불필요)
- 🇰🇷 뉴스 제목 한국어 자동 번역
- ⏱️ 자동 새로고침 (1~60분 주기) + 수동 새로고침
- 📅 날짜 필터 (오늘 / 최근 24시간 / 3일 / 7일 / 직접 지정)
- 🔍 카테고리 · 키워드 필터
- 📊 **국내 증시 영향 분석** 탭
  - 종합 영향 판정(매우 긍정 ~ 매우 부정) 및 지수
  - 카테고리별 호재/악재 신호
  - 국내 업종별 전망(반도체·은행·성장주·방산·항공·정유 등)
  - 영향이 큰 주요 호재/악재 뉴스

## 설치 및 실행

### 1) 가상환경 생성 + 패키지 설치
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
> 회사/학교망 등에서 SSL 인증서 오류가 나면:
> ```
> .venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
> ```

### 2) 실행
```powershell
.venv\Scripts\python.exe -m streamlit run newsapp.py
```
또는 **run.bat 더블클릭**, 또는 VS Code에서 **F5**.

브라우저에서 `http://localhost:8501` 이 열립니다.

## 기술 스택
- Python 3.11 / Streamlit
- feedparser (RSS 파싱)
- Google 번역 공개 엔드포인트 (키 불필요)

## ⚠️ 면책
국내 증시 영향 분석은 뉴스 키워드 기반 자동 추정으로 **참고용**입니다.
투자 판단의 근거가 아니며, 투자 책임은 본인에게 있습니다.
