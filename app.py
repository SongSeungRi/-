import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── 설정 ──────────────────────────────────────────────────────
SALES_SHEET_ID   = "1-ATlZN-VmstKUkuee83nJhW-tAaEmojk0uPuC329ELY"
WEATHER_SHEET_ID = "1TfQTCPs8W14Pb5Nn_KG4WtthtTa4k0XrfXSM_jedqIk"
YEARS = [2023, 2024, 2025, 2026]

st.set_page_config(
    page_title="마르쉐 매출 조회",
    page_icon="🌿",
    layout="centered"
)

# ── 커스텀 CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #F7FBF0; }
    .metric-card {
        background: white;
        border: 0.5px solid #C0DD97;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .best-card {
        background: #EAF3DE;
        border: 1px solid #3B6D11;
        border-radius: 12px;
        padding: 14px 16px;
    }
    .worst-card {
        background: #FAEEDA;
        border: 1px solid #FAC775;
        border-radius: 12px;
        padding: 14px 16px;
    }
    .weather-tag {
        font-size: 12px;
        color: #5F5E5A;
        margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ── 데이터 로드 ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sales():
    """매출 데이터 로드 (연도별 탭)"""
    dfs = []
    for year in YEARS:
        url = (
            f"https://docs.google.com/spreadsheets/d/{SALES_SHEET_ID}"
            f"/gviz/tq?tqx=out:csv&sheet={year}"
        )
        try:
            df = pd.read_csv(url, header=0)
            if df.empty:
                continue

            # 컬럼 위치 기반 매핑
            # 실제 시트: A=표/NA, B=하단에/NA, C=날짜, D=시장명, E=팀분류
            #            F=정규, G=성격, H=속성, I=출점팀명
            #            R=매출총액, S=지속가능기금
            cols = df.columns.tolist()

            rename = {}
            if len(cols) > 2:  rename[cols[2]]  = "날짜"
            if len(cols) > 3:  rename[cols[3]]  = "시장명"
            if len(cols) > 4:  rename[cols[4]]  = "팀분류"
            if len(cols) > 5:  rename[cols[5]]  = "정규"
            if len(cols) > 6:  rename[cols[6]]  = "성격"
            if len(cols) > 7:  rename[cols[7]]  = "속성"
            if len(cols) > 8:  rename[cols[8]]  = "출점팀"
            if len(cols) > 17: rename[cols[17]] = "매출"
            if len(cols) > 18: rename[cols[18]] = "지속가능기금"

            df = df.rename(columns=rename)
            df["연도"] = year

            # 필요한 컬럼만 유지
            keep = [c for c in ["날짜","시장명","팀분류","출점팀","매출","지속가능기금","연도"]
                    if c in df.columns]
            df = df[keep]
            dfs.append(df)

        except Exception as e:
            st.warning(f"{year}년 매출 데이터 로드 실패: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)

    # 타입 변환
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df["매출"] = pd.to_numeric(
        df["매출"].astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("원", "", regex=False)
            .str.strip(),
        errors="coerce"
    )
    df["지속가능기금"] = pd.to_numeric(
        df["지속가능기금"].astype(str)
            .str.replace(",", "", regex=False)
            .str.strip(),
        errors="coerce"
    )
    df["월"] = df["날짜"].dt.month

    # 유효 데이터만
    df = df.dropna(subset=["날짜", "매출", "출점팀"])
    df = df[df["매출"] > 0]
    df = df[~df["출점팀"].astype(str).str.strip().isin(["", "출점팀", "출점팀명", "NA", "nan"])]

    return df.reset_index(drop=True)


@st.cache_data(ttl=300)
def load_weather():
    """시장 날씨/유동인구 데이터 로드"""
    dfs = []
    for year in YEARS:
        url = (
            f"https://docs.google.com/spreadsheets/d/{WEATHER_SHEET_ID}"
            f"/gviz/tq?tqx=out:csv&sheet={year}"
        )
        try:
            df = pd.read_csv(url, header=0)
            if df.empty:
                continue

            # 컬럼명 정리 (실제 헤더 기준)
            # 날짜 | 시장명 | 미세먼지 | 초미세먼지 | 날씨 | 기온 | 최저기온 | 최고기온 | 총방문객 | 시간대...
            df.columns = [c.strip() for c in df.columns]
            df["연도"] = year
            dfs.append(df)

        except Exception as e:
            st.warning(f"{year}년 시장 데이터 로드 실패: {e}")

    if not dfs:
        return pd.DataFrame()

    df = pd.concat(dfs, ignore_index=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜", "시장명"])

    return df.reset_index(drop=True)


# ── 날씨 표시 함수 ─────────────────────────────────────────────
def weather_display(w_row):
    """
    23~25년: 기온 컬럼만 있음 → '🌡 11시 기준 15°C'
    26년~:   최저/최고 컬럼 있음 → '☀️ 맑음 최고18° / 최저6°'
    """
    if w_row is None:
        return ""

    icons = {
        "맑음": "☀️", "구름많음": "⛅", "흐림": "⛅",
        "비": "🌧️", "눈": "❄️", "소나기": "🌦️"
    }

    weather_label = str(w_row.get("날씨", "")).strip()
    icon = icons.get(weather_label, "🌡️")

    hi  = w_row.get("최고기온")
    lo  = w_row.get("최저기온")
    avg = w_row.get("기온")

    try:
        hi_val  = float(hi)  if pd.notna(hi)  and str(hi).strip()  != "" else None
        lo_val  = float(lo)  if pd.notna(lo)  and str(lo).strip()  != "" else None
        avg_val = float(avg) if pd.notna(avg) and str(avg).strip() != "" else None
    except:
        hi_val = lo_val = avg_val = None

    if hi_val is not None and lo_val is not None:
        return f"{icon} {weather_label}  최고 {hi_val:.0f}° / 최저 {lo_val:.0f}°"
    elif avg_val is not None:
        return f"{icon} {weather_label}  11시 기준 {avg_val:.0f}°C"
    elif weather_label:
        return f"{icon} {weather_label}"
    return ""


def get_weather(w_df, date, market):
    """날짜+시장명으로 날씨 데이터 매칭"""
    if w_df.empty or date is None:
        return None
    match = w_df[
        (w_df["날짜"].dt.date == pd.Timestamp(date).date()) &
        (w_df["시장명"] == market)
    ]
    if match.empty:
        # 같은 날짜의 다른 시장이라도 반환 (날씨는 공통)
        match = w_df[w_df["날짜"].dt.date == pd.Timestamp(date).date()]
    return match.iloc[0].to_dict() if not match.empty else None


# ── UI 시작 ───────────────────────────────────────────────────
st.markdown("""
<div style="background:#EAF3DE;border-radius:16px;padding:20px 24px;
            border:0.5px solid #C0DD97;margin-bottom:20px">
  <h2 style="color:#27500A;margin:0;font-size:22px">🌿 마르쉐 매출 조회</h2>
  <p style="color:#3B6D11;margin:4px 0 0;font-size:13px">출점팀별 시장 매출 현황</p>
</div>
""", unsafe_allow_html=True)

# 데이터 로드
with st.spinner("데이터 불러오는 중..."):
    sales_df   = load_sales()
    weather_df = load_weather()

if sales_df.empty:
    st.error("매출 데이터를 불러올 수 없어요. 구글 시트 공유 설정을 확인해주세요.")
    st.stop()

# 출점팀 선택
teams = sorted(sales_df["출점팀"].dropna().unique())
team  = st.selectbox("출점팀을 선택하세요", ["-- 선택 --"] + teams)

if team == "-- 선택 --":
    st.info("위에서 출점팀을 선택하면 매출 현황이 표시됩니다.")
    st.stop()

team_df = sales_df[sales_df["출점팀"] == team].copy()

# ── 탭 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🏠 홈", "📊 분석", "📋 전체 내역"])


# ════════════════════════════════════════════════
# 탭 1: 홈
# ════════════════════════════════════════════════
with tab1:

    # 연도별 요약 테이블
    st.markdown("#### 연도별 요약")
    yr_summary = (
        team_df.groupby("연도")["매출"]
        .agg(총매출="sum", 평균매출="mean", 출점횟수="count")
        .reset_index()
    )
    yr_summary["총매출_표시"]  = yr_summary["총매출"].apply(lambda x: f"{x:,.0f}원")
    yr_summary["평균매출_표시"] = yr_summary["평균매출"].apply(lambda x: f"{x:,.0f}원")
    st.dataframe(
        yr_summary[["연도","총매출_표시","평균매출_표시","출점횟수"]].rename(columns={
            "총매출_표시":"총 매출", "평균매출_표시":"평균 매출", "출점횟수":"출점 횟수"
        }),
        use_container_width=True, hide_index=True
    )

    # 최고 / 최저 매출 + 날씨
    st.markdown("#### 최고 / 최저 매출")
    best_idx  = team_df["매출"].idxmax()
    worst_idx = team_df["매출"].idxmin()
    best  = team_df.loc[best_idx]
    worst = team_df.loc[worst_idx]

    best_w  = get_weather(weather_df, best["날짜"],  best["시장명"])
    worst_w = get_weather(weather_df, worst["날짜"], worst["시장명"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="best-card">
          <div style="font-size:11px;color:#5F5E5A">최고 매출 🏆</div>
          <div style="font-size:22px;font-weight:600;color:#27500A">
            {best['매출']:,.0f}원
          </div>
          <div style="font-size:11px;color:#3B6D11;margin-top:4px">
            {int(best['연도'])}년 {int(best['월'])}월 · {best['시장명']}
          </div>
          <div class="weather-tag">{weather_display(best_w)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="worst-card">
          <div style="font-size:11px;color:#5F5E5A">최저 매출</div>
          <div style="font-size:22px;font-weight:600;color:#633806">
            {worst['매출']:,.0f}원
          </div>
          <div style="font-size:11px;color:#854F0B;margin-top:4px">
            {int(worst['연도'])}년 {int(worst['월'])}월 · {worst['시장명']}
          </div>
          <div class="weather-tag">{weather_display(worst_w)}</div>
        </div>
        """, unsafe_allow_html=True)

    # 연도별 매출 추이
    st.markdown("#### 연도별 매출 추이")
    yr_chart = team_df.groupby("연도").agg(
        총매출=("매출","sum"),
        월평균=("매출","mean")
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=yr_chart["연도"], y=yr_chart["총매출"],
        mode="lines+markers", name="총매출",
        line=dict(color="#3B6D11", width=2),
        marker=dict(size=7, color="#3B6D11"),
        fill="tozeroy", fillcolor="rgba(63,109,17,0.08)"
    ))
    fig.add_trace(go.Scatter(
        x=yr_chart["연도"], y=yr_chart["월평균"],
        mode="lines+markers", name="출점 평균",
        line=dict(color="#C0DD97", width=2, dash="dash"),
        marker=dict(size=5, color="#C0DD97")
    ))
    fig.update_layout(
        yaxis_tickformat=",",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", y=-0.15),
        height=250
    )
    fig.update_xaxes(showgrid=False, tickmode="linear", dtick=1)
    fig.update_yaxes(gridcolor="#EAF3DE")
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════
# 탭 2: 분석
# ════════════════════════════════════════════════
with tab2:

    st.markdown(f"#### {team} 분석")

    team_cat = team_df["팀분류"].dropna().mode()
    team_cat = team_cat.iloc[0] if not team_cat.empty else ""

    my_avg  = team_df["매출"].mean()
    all_avg = sales_df["매출"].mean()
    cat_avg = sales_df[sales_df["팀분류"] == team_cat]["매출"].mean() if team_cat else all_avg

    pct     = round((my_avg - all_avg) / all_avg * 100) if all_avg else 0
    pct_cat = round((my_avg - cat_avg) / cat_avg * 100) if cat_avg else 0

    pct_color     = "#0F6E56" if pct     >= 0 else "#D85A30"
    pct_cat_color = "#0F6E56" if pct_cat >= 0 else "#D85A30"

    st.markdown(f"""
    <div style="background:#E8F0FB;border:0.5px solid #93B4EE;border-radius:10px;
                padding:10px 14px;font-size:13px;color:#2152A3;margin-bottom:16px">
      출점 평균 매출 <strong>{my_avg:,.0f}원</strong> —
      전체 평균 대비 <strong style="color:{pct_color}">{'+' if pct>=0 else ''}{pct}%</strong>
      {f', {team_cat} 평균 대비 <strong style="color:{pct_cat_color}">{chr(43) if pct_cat>=0 else ""}{pct_cat}%</strong>' if team_cat else ''}
    </div>
    """, unsafe_allow_html=True)

    # 시장별 평균 대비 비교
    st.markdown("**시장별 평균 대비 내 매출**")
    markets = team_df["시장명"].dropna().unique()

    for mk in markets:
        my_mk_avg  = team_df[team_df["시장명"] == mk]["매출"].mean()
        all_mk_avg = sales_df[sales_df["시장명"] == mk]["매출"].mean()
        cat_mk_avg = sales_df[
            (sales_df["시장명"] == mk) & (sales_df["팀분류"] == team_cat)
        ]["매출"].mean() if team_cat else all_mk_avg

        diff = round((my_mk_avg - all_mk_avg) / all_mk_avg * 100) if all_mk_avg else 0
        color = "#0F6E56" if diff >= 0 else "#D85A30"
        arrow = "▲" if diff >= 0 else "▼"

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{mk}**")
            st.caption(
                f"내 평균 {my_mk_avg:,.0f}원 | "
                f"전체 평균 {all_mk_avg:,.0f}원 | "
                f"{team_cat} 평균 {cat_mk_avg:,.0f}원"
            )
            pct_bar = min(int(my_mk_avg / max(all_mk_avg, 1) * 100), 200)
            st.progress(min(pct_bar / 200, 1.0))
        with col2:
            st.markdown(
                f"<div style='color:{color};font-weight:600;font-size:14px;"
                f"text-align:right;padding-top:16px'>{arrow}{abs(diff)}%</div>",
                unsafe_allow_html=True
            )

    # 강세 시장 순위
    st.markdown("**강세 시장 순위**")
    mk_strength = []
    for mk in markets:
        my_mk_avg  = team_df[team_df["시장명"] == mk]["매출"].mean()
        all_mk_avg = sales_df[sales_df["시장명"] == mk]["매출"].mean()
        diff = round((my_mk_avg - all_mk_avg) / all_mk_avg * 100) if all_mk_avg else 0
        mk_strength.append({"시장명": mk, "내평균": my_mk_avg, "전체평균": all_mk_avg, "차이": diff})

    mk_strength = sorted(mk_strength, key=lambda x: x["차이"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    for i, r in enumerate(mk_strength):
        diff_color = "#0F6E56" if r["차이"] >= 0 else "#D85A30"
        diff_bg    = "#E0F5EE" if r["차이"] >= 0 else "#FBE9E2"
        medal = medals[i] if i < 3 else "·"
        st.markdown(f"""
        <div style="background:{'#EAF3DE' if i==0 else 'white'};
                    border:0.5px solid {'#3B6D11' if i==0 else '#C0DD97'};
                    border-radius:12px;padding:12px 14px;margin-bottom:8px;
                    display:flex;align-items:center;justify-content:space-between">
          <div>
            <span style="font-size:16px">{medal}</span>
            <strong style="margin-left:8px;color:#27500A">{r['시장명']}</strong>
            <div style="font-size:11px;color:#5F5E5A;margin-top:3px;margin-left:26px">
              내 평균 {r['내평균']:,.0f}원 · 전체 평균 {r['전체평균']:,.0f}원
            </div>
          </div>
          <span style="background:{diff_bg};color:{diff_color};
                       padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600">
            {'+' if r['차이']>=0 else ''}{r['차이']}%
          </span>
        </div>
        """, unsafe_allow_html=True)

    # 날씨별 평균 매출
    if not weather_df.empty:
        st.markdown("**날씨별 평균 매출**")
        merged = team_df.merge(
            weather_df[["날짜","시장명","날씨","기온","최저기온","최고기온"]],
            on=["날짜","시장명"], how="left"
        )
        if "날씨" in merged.columns and merged["날씨"].notna().any():
            w_avg = (
                merged.groupby("날씨")["매출"]
                .agg(평균=("mean"), 횟수=("count"))
                .reset_index()
                .sort_values("평균", ascending=False)
            )
            icons = {"맑음":"☀️","구름많음":"⛅","흐림":"⛅","비":"🌧️","눈":"❄️"}
            cols = st.columns(len(w_avg))
            for idx, (_, row) in enumerate(w_avg.iterrows()):
                with cols[idx]:
                    icon = icons.get(str(row["날씨"]).strip(), "🌡️")
                    is_best = idx == 0
                    st.markdown(f"""
                    <div style="background:{'#EAF3DE' if is_best else 'white'};
                                border:{'1px solid #3B6D11' if is_best else '0.5px solid #C0DD97'};
                                border-radius:12px;padding:12px;text-align:center">
                      <div style="font-size:20px">{icon}</div>
                      <div style="font-size:11px;color:#5F5E5A;margin:4px 0">{row['날씨']}</div>
                      <div style="font-size:15px;font-weight:600;color:#27500A">
                        {row['평균']:,.0f}
                      </div>
                      <div style="font-size:10px;color:#888">{int(row['횟수'])}회 평균</div>
                    </div>
                    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 탭 3: 전체 내역
# ════════════════════════════════════════════════
with tab3:

    # 필터
    col1, col2, col3 = st.columns(3)
    with col1:
        yr_opts = ["전체"] + sorted(team_df["연도"].unique().tolist(), reverse=True)
        yr_f = st.selectbox("연도", yr_opts, key="yr_f")
    with col2:
        mo_f = st.selectbox("월", ["전체"] + list(range(1, 13)), key="mo_f")
    with col3:
        mk_opts = ["전체"] + sorted(team_df["시장명"].dropna().unique().tolist())
        mk_f = st.selectbox("시장", mk_opts, key="mk_f")

    filtered = team_df.copy()
    if yr_f != "전체": filtered = filtered[filtered["연도"] == int(yr_f)]
    if mo_f != "전체": filtered = filtered[filtered["월"]   == int(mo_f)]
    if mk_f != "전체": filtered = filtered[filtered["시장명"] == mk_f]

    # 날씨 합치기
    if not weather_df.empty:
        filtered = filtered.merge(
            weather_df[["날짜","시장명","날씨","기온","최저기온","최고기온","총방문객"]],
            on=["날짜","시장명"], how="left"
        )
        def fmt_weather(row):
            icons = {"맑음":"☀️","구름많음":"⛅","흐림":"⛅","비":"🌧️","눈":"❄️"}
            icon = icons.get(str(row.get("날씨","")).strip(), "")
            try:
                hi  = float(row["최고기온"]) if pd.notna(row.get("최고기온")) else None
                lo  = float(row["최저기온"]) if pd.notna(row.get("최저기온")) else None
                avg = float(row["기온"])     if pd.notna(row.get("기온"))     else None
            except:
                hi = lo = avg = None
            if hi and lo:
                return f"{icon} {row.get('날씨','')} {hi:.0f}°/{lo:.0f}°"
            elif avg:
                return f"{icon} {row.get('날씨','')} {avg:.0f}°C"
            return str(row.get("날씨",""))
        filtered["날씨_표시"] = filtered.apply(fmt_weather, axis=1)
    else:
        filtered["날씨_표시"] = ""

    # 합계 표시
    total_s = filtered["매출"].sum()
    total_f = filtered["지속가능기금"].sum() if "지속가능기금" in filtered.columns else 0
    st.caption(
        f"총 {len(filtered)}건 · "
        f"매출 합계 **{total_s:,.0f}원** · "
        f"지속가능기금 **{total_f:,.0f}원**"
    )

    # 테이블 표시
    show_cols = ["날짜","시장명","날씨_표시","매출","지속가능기금"]
    show_cols = [c for c in show_cols if c in filtered.columns]
    show_df = filtered[show_cols].sort_values("날짜", ascending=False).copy()
    show_df["날짜"] = show_df["날짜"].dt.strftime("%Y-%m-%d")
    show_df["매출"] = show_df["매출"].apply(lambda x: f"{x:,.0f}")
    if "지속가능기금" in show_df.columns:
        show_df["지속가능기금"] = show_df["지속가능기금"].apply(
            lambda x: f"{float(x):,.0f}" if pd.notna(x) else "-"
        )
    show_df = show_df.rename(columns={"날씨_표시": "날씨"})
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    # 다운로드
    col_a, col_b = st.columns(2)
    with col_a:
        csv = filtered.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ CSV 다운로드",
            csv,
            f"마르쉐_{team}_매출내역.csv",
            "text/csv",
            use_container_width=True
        )
    with col_b:
        st.button(
            "🖨️ 출력",
            on_click=lambda: st.markdown(
                "<script>window.print()</script>",
                unsafe_allow_html=True
            ),
            use_container_width=True
        )
