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

## 🌐 웹사이트로 배포하기 (Streamlit Community Cloud · 무료)

GitHub 저장소를 그대로 연결해 공개 URL로 실행할 수 있습니다.

1. **https://share.streamlit.io** 접속 후 GitHub 계정으로 로그인
2. **Create app → Deploy a public app from GitHub** 선택
3. 아래 정보 입력
   - Repository: `sh5316/Issuse_collecter`
   - Branch: `main`
   - Main file path: `newsapp.py`
4. (선택) **Advanced settings**에서 Python 버전을 `3.11`로 지정
5. **Deploy** 클릭 → 잠시 후 `https://<앱이름>.streamlit.app` 주소가 발급됩니다.

> 저장소에 push할 때마다 배포된 앱이 자동으로 갱신됩니다.
> 필요한 패키지는 `requirements.txt`, 앱 설정은 `.streamlit/config.toml`에서
> 클라우드가 자동으로 읽어갑니다.

## 🧩 두 가지 버전

| 버전 | 파일 | 실행 방식 | 특징 |
|------|------|-----------|------|
| **파이썬 웹앱** | `newsapp.py` | Streamlit 서버 | 가장 안정적 (서버가 RSS 수집) |
| **정적 HTML** | `index.html` | 브라우저만으로 실행 | 서버 불필요, GitHub Pages 호스팅 가능 |

### 정적 HTML 버전 (`index.html`)
- 파이썬·서버 없이 브라우저에서 바로 열립니다 (더블클릭 또는 호스팅).
- 번역은 CORS를 허용하는 Google 엔드포인트를 **직접** 호출합니다.
- RSS는 브라우저 CORS 제약 때문에 **공개 CORS 프록시**를 경유합니다
  (allorigins·codetabs 등 여러 개를 순차 시도).

> ⚠️ 공개 프록시는 간헐적으로 느리거나 실패할 수 있습니다. **100% 안정적으로
> 쓰려면 본인 소유의 무료 프록시(Cloudflare Worker)를 만들어** `index.html` 상단의
> `CUSTOM_PROXY` 에 주소를 넣으세요. 아래 "안정적인 프록시" 참고.

#### GitHub Pages로 호스팅 (무료)
1. GitHub 저장소 → **Settings → Pages**
2. **Source**: `Deploy from a branch`, **Branch**: `main` / `/ (root)` 선택 후 Save
3. 잠시 후 `https://sh5316.github.io/Issuse_collecter/` 에서 열립니다.

#### 안정적인 프록시 (선택, Cloudflare Worker · 무료)
1. https://dash.cloudflare.com → Workers & Pages → Create Worker
2. 아래 코드를 붙여넣고 Deploy:
   ```js
   export default {
     async fetch(request) {
       const url = new URL(request.url).searchParams.get("url");
       if (!url) return new Response("missing url", { status: 400 });
       const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
       const body = await r.text();
       return new Response(body, {
         headers: { "Access-Control-Allow-Origin": "*", "Content-Type": "text/xml; charset=utf-8" },
       });
     },
   };
   ```
3. 발급된 주소를 `index.html` 의 `CUSTOM_PROXY` 에 입력:
   ```js
   const CUSTOM_PROXY = "https://your-worker.your-name.workers.dev/?url=";
   ```

## 기술 스택
- Python 3.11 / Streamlit
- feedparser (RSS 파싱)
- Google 번역 공개 엔드포인트 (키 불필요)

## ⚠️ 면책
국내 증시 영향 분석은 뉴스 키워드 기반 자동 추정으로 **참고용**입니다.
투자 판단의 근거가 아니며, 투자 책임은 본인에게 있습니다.
