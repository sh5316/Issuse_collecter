# -*- coding: utf-8 -*-
"""
해외 경제 뉴스 수집 앱 (Streamlit)

미국 국채금리 / 금리 / 경제상황 / 세계 증시 / 세계 전쟁 / 원유가격
관련 뉴스만 무료 RSS 피드에서 모아 한국어 번역과 함께 보여줍니다.

실행:
    streamlit run newsapp.py
또는 (venv):
    Scripts\\streamlit.exe run newsapp.py
"""

import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_OK = True
except Exception:  # noqa: BLE001
    _AUTOREFRESH_OK = False

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:  # noqa: BLE001
    pass

# 번역 기능은 외부 네트워크가 되면 항상 사용 가능 (SSL 검증 우회).
_TRANSLATOR_OK = True


# ---------------------------------------------------------------------------
# 1. 카테고리 정의 (한국어 라벨 + 매칭 키워드)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "미국 국채금리": {
        "emoji": "🏦",
        "keywords": [
            "treasury", "treasuries", "bond yield", "bond yields", "10-year",
            "10 year", "2-year", "30-year", "yield curve", "t-note", "t-bond",
            "sovereign bond", "government bond",
        ],
    },
    "금리": {
        "emoji": "📊",
        "keywords": [
            "interest rate", "interest rates", "rate cut", "rate hike",
            "rate decision", "federal reserve", "the fed", "fomc", "powell",
            "central bank", "monetary policy", "ecb", "boj", "bank of england",
            "basis points", "benchmark rate",
        ],
    },
    "경제상황": {
        "emoji": "🌐",
        "keywords": [
            "gdp", "inflation", "deflation", "cpi", "ppi", "pce",
            "recession", "unemployment", "jobless", "jobs report", "payroll",
            "economic growth", "economic outlook", "consumer spending",
            "retail sales", "manufacturing", "pmi", "trade deficit", "tariff",
            "tariffs", "debt ceiling",
        ],
    },
    "세계 증시": {
        "emoji": "📈",
        "keywords": [
            "stock market", "stocks", "shares", "equities", "s&p 500",
            "s&p500", "nasdaq", "dow jones", "wall street", "ftse", "nikkei",
            "hang seng", "dax", "shanghai composite", "index futures",
            "stock index", "sell-off", "rally", "bull market", "bear market",
        ],
    },
    "세계 전쟁": {
        "emoji": "⚔️",
        "keywords": [
            "war", "conflict", "military", "invasion", "ukraine", "russia",
            "middle east", "israel", "gaza", "iran", "sanctions",
            "geopolitical", "ceasefire", "airstrike", "troops", "nato",
            "taiwan tension",
        ],
    },
    "원유가격": {
        "emoji": "🛢️",
        "keywords": [
            "oil price", "oil prices", "crude", "brent", "wti", "opec",
            "opec+", "petroleum", "barrel", "gasoline", "energy prices",
            "natural gas", "fuel price", "shale",
        ],
    },
}

# ---------------------------------------------------------------------------
# 2. RSS 피드 목록 (무료, API 키 불필요)
# ---------------------------------------------------------------------------
def _gnews(query: str) -> str:
    """Google News RSS 검색 URL 생성 (최근 7일)."""
    from urllib.parse import quote_plus
    q = quote_plus(f"{query} when:7d")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


RSS_FEEDS = [
    # --- 주제별 Google News 검색 피드 (안정적, 최신) ---
    ("미국 국채금리", _gnews("US treasury yield bond")),
    ("금리/연준", _gnews("federal reserve interest rate fed")),
    ("경제상황", _gnews("US economy inflation GDP recession")),
    ("세계 증시", _gnews("stock market S&P 500 Nasdaq Dow")),
    ("세계 전쟁", _gnews("war conflict geopolitical sanctions")),
    ("원유가격", _gnews("oil price crude OPEC brent")),
    # --- 전문 매체 직접 피드 ---
    ("MarketWatch Top", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch Markets", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Guardian Business", "https://www.theguardian.com/business/rss"),
    ("OilPrice.com", "https://oilprice.com/rss/main"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]


# ---------------------------------------------------------------------------
# 3. 뉴스 수집 + 필터링
# ---------------------------------------------------------------------------
def _match_categories(text: str):
    """기사 텍스트가 어떤 카테고리에 속하는지 반환."""
    text_low = text.lower()
    matched = []
    for cat, cfg in CATEGORIES.items():
        for kw in cfg["keywords"]:
            if kw in text_low:
                matched.append(cat)
                break
    return matched


def _parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        tm = entry.get(key)
        if tm:
            try:
                return dt.datetime.fromtimestamp(time.mktime(tm))
            except Exception:  # noqa: BLE001
                pass
    return None


def _fetch_feed(source_name, url):
    items = []
    try:
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            link = entry.get("link", "")
            if not title or not link:
                continue
            cats = _match_categories(f"{title} {summary}")
            if not cats:
                continue  # 경제 관련 없는 기사는 제외
            items.append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source_name,
                "categories": cats,
                "published": _parse_entry_time(entry),
            })
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] {source_name} 수집 실패: {exc}")
    return items


@st.cache_data(ttl=600, show_spinner=False)
def collect_news():
    """모든 피드를 병렬로 수집하고 중복 제거 후 최신순 정렬."""
    all_items = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_fetch_feed, name, url) for name, url in RSS_FEEDS]
        for fut in as_completed(futures):
            all_items.extend(fut.result())

    # 제목 기준 중복 제거
    seen = set()
    unique = []
    for it in all_items:
        key = it["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)

    # 최신순 정렬 (시간 없는 항목은 뒤로)
    unique.sort(key=lambda x: x["published"] or dt.datetime.min, reverse=True)
    return unique


@st.cache_data(ttl=86400, show_spinner=False)
def translate_to_korean(text: str) -> str:
    """Google 번역 공개 엔드포인트 사용 (API 키 불필요, SSL 검증 우회)."""
    if not text:
        return ""
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx", "sl": "auto", "tl": "ko",
                "dt": "t", "q": text[:480],
            },
            verify=False,
            timeout=10,
        )
        data = resp.json()
        return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# 4. 국내 증시 영향 분석 (규칙 기반, API 키 불필요)
# ---------------------------------------------------------------------------
# 각 카테고리별로 "국내 증시에 긍정적(pos) / 부정적(neg)"인 방향 키워드를 정의한다.
# pos = 코스피/코스닥에 호재, neg = 악재.
IMPACT_RULES = {
    "미국 국채금리": {
        "pos": ["fall", "falls", "fell", "drop", "drops", "decline", "declines",
                "ease", "eases", "lower", "slip", "slips", "retreat", "down",
                "sink", "tumble", "slide"],
        "neg": ["rise", "rises", "rose", "rising", "climb", "climbs", "surge",
                "surges", "jump", "jumps", "higher", "soar", "soars", "spike",
                "gain", "gains", "increase", "up"],
        "pos_reason": "미국 국채금리 하락 → 외국인 자금 유입·위험자산 선호로 국내 증시에 긍정적",
        "neg_reason": "미국 국채금리 상승 → 외국인 자금 이탈·원화 약세 압력으로 국내 증시에 부정적",
    },
    "금리": {
        "pos": ["cut", "cuts", "lower", "lowers", "ease", "eases", "easing",
                "dovish", "pause", "pauses", "hold", "holds", "reduce", "reduces"],
        "neg": ["hike", "hikes", "raise", "raises", "higher", "tighten",
                "tightening", "hawkish", "increase", "increases"],
        "pos_reason": "금리 인하·완화 기대 → 유동성 확대로 국내 증시에 긍정적",
        "neg_reason": "금리 인상·긴축 기조 → 유동성 축소로 국내 증시에 부정적",
    },
    "경제상황": {
        "pos": ["growth", "strong", "stronger", "beat", "beats", "robust",
                "recovery", "resilient", "resilience", "expand", "expands",
                "expansion", "improve", "improves", "upbeat", "solid", "boom"],
        "neg": ["recession", "slowdown", "slows", "contraction", "weak",
                "weaker", "miss", "misses", "downturn", "layoff", "layoffs",
                "jobless", "shrink", "stagnation", "crisis", "fears", "warns",
                "warning"],
        "pos_reason": "글로벌 경기 개선 신호 → 수출 비중 높은 국내 증시에 긍정적",
        "neg_reason": "글로벌 경기 둔화·침체 우려 → 수출 의존도 높은 국내 증시에 부정적",
    },
    "세계 증시": {
        "pos": ["rally", "rallies", "gain", "gains", "surge", "surges", "rise",
                "rises", "record", "jump", "jumps", "climb", "climbs", "higher",
                "rebound", "rebounds", "soar", "soars", "advance"],
        "neg": ["sell-off", "selloff", "plunge", "plunges", "fall", "falls",
                "drop", "drops", "crash", "slump", "tumble", "tumbles", "sink",
                "slide", "slides", "lower", "rout", "fears"],
        "pos_reason": "글로벌 증시 강세 → 동조화로 코스피·코스닥에 긍정적",
        "neg_reason": "글로벌 증시 약세 → 동조화로 코스피·코스닥에 부정적",
    },
    "세계 전쟁": {
        "pos": ["ceasefire", "truce", "peace", "deal", "agreement",
                "de-escalate", "diplomacy", "talks", "resolution"],
        "neg": ["war", "attack", "attacks", "invasion", "strike", "strikes",
                "escalate", "escalation", "escalates", "tension", "tensions",
                "conflict", "sanction", "sanctions", "missile", "threat",
                "threats", "clash", "clashes"],
        "pos_reason": "지정학적 긴장 완화 → 위험회피 심리 완화로 국내 증시에 긍정적",
        "neg_reason": "지정학적 긴장 고조 → 안전자산 선호·위험회피로 국내 증시에 부정적",
    },
    "원유가격": {
        "pos": ["fall", "falls", "fell", "drop", "drops", "decline", "declines",
                "plunge", "plunges", "lower", "slide", "slides", "ease", "eases",
                "retreat", "down", "slump"],
        "neg": ["surge", "surges", "jump", "jumps", "rise", "rises", "soar",
                "soars", "spike", "spikes", "higher", "climb", "climbs", "rally",
                "gains", "gain", "up"],
        "pos_reason": "유가 하락 → 수입물가·기업 원가 부담 완화로 국내 증시에 긍정적",
        "neg_reason": "유가 상승 → 수입물가 상승·원가 부담으로 국내 증시에 부정적",
    },
}


def analyze_article(n):
    """기사 한 건에서 (카테고리, 방향, 사유) 신호 목록을 추출. 방향: +1 호재 / -1 악재."""
    text = f"{n['title']} {n.get('summary', '')}".lower()
    signals = []
    for cat in n["categories"]:
        rule = IMPACT_RULES.get(cat)
        if not rule:
            continue
        pos_hits = sum(1 for w in rule["pos"] if w in text)
        neg_hits = sum(1 for w in rule["neg"] if w in text)
        if pos_hits > neg_hits:
            signals.append((cat, 1, rule["pos_reason"]))
        elif neg_hits > pos_hits:
            signals.append((cat, -1, rule["neg_reason"]))
        # 동점/무신호는 중립으로 보고 제외
    return signals


def analyze_market_impact(news_items):
    """전체 뉴스로 국내 증시 영향 종합 지표를 계산."""
    cat_scores = {c: 0 for c in CATEGORIES}
    cat_counts = {c: {"pos": 0, "neg": 0} for c in CATEGORIES}
    pos_total = neg_total = 0
    scored = []  # (기사점수, 기사, 신호들)
    for n in news_items:
        sigs = analyze_article(n)
        if not sigs:
            continue
        art_score = 0
        for cat, d, _reason in sigs:
            cat_scores[cat] += d
            if d > 0:
                cat_counts[cat]["pos"] += 1
                pos_total += 1
            else:
                cat_counts[cat]["neg"] += 1
                neg_total += 1
            art_score += d
        scored.append((art_score, n, sigs))
    total = pos_total + neg_total
    overall = (pos_total - neg_total) / total if total else 0.0
    return {
        "overall": overall,
        "pos_total": pos_total,
        "neg_total": neg_total,
        "cat_scores": cat_scores,
        "cat_counts": cat_counts,
        "scored": scored,
        "analyzed": len(scored),
    }


def impact_label(score):
    """종합 점수(-1~+1)를 라벨과 색으로 변환."""
    if score >= 0.4:
        return "📈 매우 긍정적", "green"
    if score >= 0.15:
        return "↗️ 다소 긍정적", "green"
    if score > -0.15:
        return "➡️ 중립", "gray"
    if score > -0.4:
        return "↘️ 다소 부정적", "red"
    return "📉 매우 부정적", "red"


def sector_outlook(cat_scores):
    """카테고리 순신호를 국내 업종별 전망으로 변환. 반환: [(업종, 점수, 사유)]."""
    t = cat_scores["미국 국채금리"]
    r = cat_scores["금리"]
    e = cat_scores["경제상황"]
    s = cat_scores["세계 증시"]
    w = cat_scores["세계 전쟁"]
    o = cat_scores["원유가격"]
    # 점수 부호: + = 해당 업종에 긍정, - = 부정
    return [
        ("반도체·IT 수출주", s + e, "글로벌 증시·경기 흐름에 동조"),
        ("은행·금융", -(r + t), "시장금리 상승 시 예대마진 확대 수혜"),
        ("성장주·2차전지·바이오", r + t, "금리 상승 시 밸류에이션 부담"),
        ("방산", -w, "지정학적 긴장 고조 시 수혜"),
        ("항공·해운·운송", o, "유가 상승 시 연료비 부담"),
        ("정유·에너지", -o, "유가 상승 시 정제마진·실적 개선"),
    ]


# ---------------------------------------------------------------------------
# 5. 렌더링 헬퍼
# ---------------------------------------------------------------------------
def render_news_cards(items, show_translation, show_summary):
    import re
    for n in items:
        with st.container(border=True):
            badges = " ".join(
                f"{CATEGORIES[c]['emoji']} {c}" for c in n["categories"]
            )
            st.markdown(f"**[{n['title']}]({n['link']})**")
            if show_translation and _TRANSLATOR_OK:
                ko = translate_to_korean(n["title"])
                if ko:
                    st.markdown(f"🇰🇷 {ko}")
            meta = f"`{n['source']}`  ·  {badges}"
            if n["published"]:
                meta += f"  ·  🕒 {n['published']:%Y-%m-%d %H:%M}"
            st.caption(meta)
            if show_summary and n["summary"]:
                clean = re.sub(r"<[^>]+>", "", n["summary"]).strip()
                if clean:
                    st.write(clean[:300] + ("..." if len(clean) > 300 else ""))


def render_analysis(items, show_translation):
    result = analyze_market_impact(items)
    label, color = impact_label(result["overall"])

    st.subheader("🇰🇷 국내 증시 종합 영향")
    st.markdown(
        f"### :{color}[{label}]  "
        f"<span style='font-size:0.6em;color:gray'>(지수 {result['overall']:+.2f})</span>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 호재 신호", f"{result['pos_total']}건")
    c2.metric("🔴 악재 신호", f"{result['neg_total']}건")
    c3.metric("📄 분석 기사", f"{result['analyzed']}건")

    if result["analyzed"] == 0:
        st.info("분석할 수 있는 방향성 뉴스가 없습니다.")
        return

    # 진행 바 형태의 종합 게이지 (0~1)
    st.progress((result["overall"] + 1) / 2)

    st.divider()
    st.subheader("📂 카테고리별 영향")
    for cat, cfg in CATEGORIES.items():
        cnt = result["cat_counts"][cat]
        if cnt["pos"] == 0 and cnt["neg"] == 0:
            continue
        net = result["cat_scores"][cat]
        arrow = "🟢 호재 우세" if net > 0 else ("🔴 악재 우세" if net < 0 else "⚪ 혼조")
        st.markdown(
            f"**{cfg['emoji']} {cat}** — {arrow}  "
            f"(호재 {cnt['pos']} / 악재 {cnt['neg']})"
        )
        rule = IMPACT_RULES[cat]
        st.caption(rule["pos_reason"] if net > 0 else rule["neg_reason"])

    st.divider()
    st.subheader("🏭 국내 업종별 전망 (참고)")
    sectors = sector_outlook(result["cat_scores"])
    cols = st.columns(2)
    for i, (name, score, reason) in enumerate(sectors):
        if score > 0:
            tag, tcolor = "📈 긍정", "green"
        elif score < 0:
            tag, tcolor = "📉 부정", "red"
        else:
            tag, tcolor = "➡️ 중립", "gray"
        with cols[i % 2].container(border=True):
            st.markdown(f"**{name}**  ·  :{tcolor}[{tag}]")
            st.caption(reason)

    st.divider()
    st.subheader("📰 영향이 큰 주요 뉴스")
    scored = result["scored"]
    neg_top = sorted(scored, key=lambda x: x[0])[:3]
    pos_top = sorted(scored, key=lambda x: x[0], reverse=True)[:3]

    st.markdown("**🔴 주요 악재 뉴스**")
    _render_impact_headlines(neg_top, show_translation)
    st.markdown("**🟢 주요 호재 뉴스**")
    _render_impact_headlines(pos_top, show_translation)

    st.divider()
    st.caption(
        "⚠️ 본 분석은 뉴스 키워드 기반의 자동 추정으로, 참고용입니다. "
        "실제 투자 판단의 근거가 아니며 투자 책임은 본인에게 있습니다."
    )


def _render_impact_headlines(scored_items, show_translation):
    for score, n, _sigs in scored_items:
        if score == 0:
            continue
        with st.container(border=True):
            st.markdown(f"[{n['title']}]({n['link']})")
            if show_translation and _TRANSLATOR_OK:
                ko = translate_to_korean(n["title"])
                if ko:
                    st.caption(f"🇰🇷 {ko}")


# ---------------------------------------------------------------------------
# 6. Streamlit UI
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="해외 경제 뉴스", page_icon="🌍", layout="wide")

    st.title("🌍 해외 경제 뉴스 모아보기")
    st.caption(
        "미국 국채금리 · 금리 · 경제상황 · 세계 증시 · 세계 전쟁 · 원유가격 "
        "관련 뉴스를 무료 RSS에서 수집합니다."
    )

    # ---- 사이드바 ----
    with st.sidebar:
        st.header("⚙️ 설정")
        if st.button("🔄 지금 새로고침", use_container_width=True):
            collect_news.clear()
            st.rerun()

        # --- 자동 새로고침 ---
        auto_on = st.checkbox(
            "⏱️ 자동 새로고침", value=False, disabled=not _AUTOREFRESH_OK
        )
        if not _AUTOREFRESH_OK:
            st.caption("streamlit-autorefresh 미설치: 자동 새로고침 비활성화")
        interval_min = st.select_slider(
            "새로고침 주기(분)",
            options=[1, 3, 5, 10, 15, 30, 60],
            value=10,
            disabled=not (auto_on and _AUTOREFRESH_OK),
        )
        if auto_on and _AUTOREFRESH_OK:
            # 지정 주기마다 캐시를 비우고 페이지를 다시 실행
            count = st_autorefresh(interval=interval_min * 60 * 1000, key="auto_rf")
            if count:  # 최초(0)가 아닌 자동 실행 시에만 캐시 초기화
                collect_news.clear()
            st.caption(f"🟢 {interval_min}분마다 자동 갱신 중")

        st.divider()
        # --- 날짜 필터 ---
        st.subheader("📅 날짜 필터")
        date_option = st.radio(
            "기간 선택",
            ["전체", "오늘", "최근 24시간", "최근 3일", "최근 7일", "직접 지정"],
            index=0,
        )
        custom_range = None
        if date_option == "직접 지정":
            today = dt.date.today()
            custom_range = st.date_input(
                "시작일 ~ 종료일",
                value=(today - dt.timedelta(days=7), today),
                max_value=today,
            )

        st.divider()
        st.subheader("카테고리 필터")
        selected_cats = []
        for cat, cfg in CATEGORIES.items():
            if st.checkbox(f"{cfg['emoji']} {cat}", value=True, key=f"cat_{cat}"):
                selected_cats.append(cat)

        st.divider()
        show_translation = st.checkbox(
            "🇰🇷 한국어 번역 표시", value=True, disabled=not _TRANSLATOR_OK
        )
        if not _TRANSLATOR_OK:
            st.warning("번역 기능 비활성화")

        show_summary = st.checkbox("📄 요약 표시", value=False)
        keyword = st.text_input("🔍 제목 내 검색어", "")

    # ---- 뉴스 수집 ----
    with st.spinner("뉴스를 수집하는 중..."):
        news = collect_news()

    # ---- 날짜 범위 계산 ----
    now = dt.datetime.now()
    start_dt = None
    end_dt = None
    if date_option == "오늘":
        start_dt = dt.datetime.combine(now.date(), dt.time.min)
    elif date_option == "최근 24시간":
        start_dt = now - dt.timedelta(hours=24)
    elif date_option == "최근 3일":
        start_dt = now - dt.timedelta(days=3)
    elif date_option == "최근 7일":
        start_dt = now - dt.timedelta(days=7)
    elif date_option == "직접 지정" and custom_range:
        if isinstance(custom_range, (tuple, list)) and len(custom_range) == 2:
            start_dt = dt.datetime.combine(custom_range[0], dt.time.min)
            end_dt = dt.datetime.combine(custom_range[1], dt.time.max)
        elif isinstance(custom_range, dt.date):
            start_dt = dt.datetime.combine(custom_range, dt.time.min)
            end_dt = dt.datetime.combine(custom_range, dt.time.max)

    def in_date_range(n):
        if start_dt is None and end_dt is None:
            return True
        pub = n["published"]
        if pub is None:
            return False  # 날짜 필터 적용 시 날짜 없는 기사는 제외
        if start_dt and pub < start_dt:
            return False
        if end_dt and pub > end_dt:
            return False
        return True

    # ---- 필터링 ----
    filtered = [
        n for n in news
        if any(c in selected_cats for c in n["categories"])
        and (not keyword or keyword.lower() in n["title"].lower())
        and in_date_range(n)
    ]

    date_label = "" if date_option == "전체" else f" · 📅 {date_option}"
    st.success(
        f"총 {len(filtered)}건의 경제 뉴스{date_label} "
        f"(업데이트: {now:%Y-%m-%d %H:%M})"
    )

    if not filtered:
        st.info("조건에 맞는 뉴스가 없습니다. 필터를 조정해 보세요.")
        return

    # ---- 탭: 뉴스 목록 / 국내 증시 영향 분석 ----
    tab_news, tab_analysis = st.tabs(["📰 뉴스 목록", "📊 국내 증시 영향 분석"])

    with tab_news:
        render_news_cards(filtered, show_translation, show_summary)

    with tab_analysis:
        render_analysis(filtered, show_translation)


if __name__ == "__main__":
    main()
