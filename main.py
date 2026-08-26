import streamlit as st
import pandas as pd
import altair as alt
from datetime import date

# ------------------------------------------------------------
# 기본 설정
# ------------------------------------------------------------
st.set_page_config(
    page_title="서울 기온 - 가장 더웠던 해 찾기",
    page_icon="🌡️",
    layout="wide",
)


@st.cache_data
def load_data():
    # seoul.csv 가 이 app.py 와 같은 깃헙 저장소(같은 폴더)에 있다고 가정합니다.
    df = pd.read_csv("seoul.csv", encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]

    df["날짜"] = df["날짜"].astype(str).str.strip()
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")

    for col in ["평균기온", "최저기온", "최고기온"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["날짜"]).sort_values("날짜")
    df["연도"] = df["날짜"].dt.year
    df["월"] = df["날짜"].dt.month
    df["일"] = df["날짜"].dt.day
    return df


df = load_data()

st.title("🌡️ 서울 기온, 역대 가장 더웠던 해는?")
st.caption("기간(월/일)을 고르면, 그 시기를 기준으로 매년을 비교해서 어느 해가 가장 더웠는지 보여드려요.")

min_date = df["날짜"].min().date()
max_date = df["날짜"].max().date()

st.markdown(f"📅 데이터 범위: **{min_date} ~ {max_date}**")

# ------------------------------------------------------------
# 사용자 입력
# ------------------------------------------------------------
col1, col2, col3 = st.columns([1, 1, 1.2])
with col1:
    start_date = st.date_input(
        "시작일 (월/일 기준)",
        value=date(max_date.year, 7, 1),
        min_value=min_date,
        max_value=max_date,
    )
with col2:
    end_date = st.date_input(
        "종료일 (월/일 기준)",
        value=date(max_date.year, 8, 31),
        min_value=min_date,
        max_value=max_date,
    )
with col3:
    metric_option = st.selectbox(
        "비교 기준",
        ["평균기온의 평균", "최고기온의 평균", "최고기온의 최댓값"],
    )

st.info("💡 연도는 상관없이 **월/일**만 기준으로 비교합니다. (예: 7/1~8/31을 고르면 매년 여름을 비교해요)")

# ------------------------------------------------------------
# 기간(월/일) 필터링 - 연도를 걸치는 경우(예: 12/20~1/5)도 처리
# ------------------------------------------------------------
start_md = start_date.month * 100 + start_date.day
end_md = end_date.month * 100 + end_date.day
md_series = df["월"] * 100 + df["일"]

if start_md <= end_md:
    mask = (md_series >= start_md) & (md_series <= end_md)
else:
    mask = (md_series >= start_md) | (md_series <= end_md)

period_df = df[mask].copy()

if period_df.empty:
    st.warning("선택하신 기간에 해당하는 데이터가 없어요. 다른 날짜를 선택해주세요.")
    st.stop()

metric_map = {
    "평균기온의 평균": ("평균기온", "mean", "평균기온 평균 (°C)"),
    "최고기온의 평균": ("최고기온", "mean", "최고기온 평균 (°C)"),
    "최고기온의 최댓값": ("최고기온", "max", "최고기온 최댓값 (°C)"),
}
src_col, agg_func, unit_label = metric_map[metric_option]

# 연도별 집계
grouped = period_df.groupby("연도")[src_col]
if agg_func == "mean":
    agg = grouped.mean().reset_index(name="값")
else:
    agg = grouped.max().reset_index(name="값")

# 데이터가 부족한(예: 첫 해처럼 기간 일부만 존재) 연도는 제외
counts = period_df.groupby("연도").size()
full_years = counts[counts >= counts.max() - 1].index
agg = agg[agg["연도"].isin(full_years)].dropna(subset=["값"])

if agg.empty:
    st.warning("선택하신 기간에 비교할 수 있는 데이터가 충분하지 않아요.")
    st.stop()

hottest_row = agg.loc[agg["값"].idxmax()]
hottest_year = int(hottest_row["연도"])
hottest_value = float(hottest_row["값"])
overall_mean = float(agg["값"].mean())

top5 = agg.sort_values("값", ascending=False).head(5).reset_index(drop=True)

# ------------------------------------------------------------
# 결과 요약
# ------------------------------------------------------------
st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("🏆 가장 더웠던 해", f"{hottest_year}년", f"{hottest_value - overall_mean:+.1f}°C (평균 대비)")
m2.metric(f"해당 해 {unit_label}", f"{hottest_value:.1f}°C")
m3.metric("비교한 연도 수", f"{len(agg)}개")

period_label = f"{start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')}"
st.subheader(f"📊 {period_label} 기간, 연도별 {unit_label}")

# ------------------------------------------------------------
# 시각화 (Altair - streamlit 기본 내장, 별도 설치 불필요)
# ------------------------------------------------------------
agg["구분"] = agg["연도"].apply(lambda y: "최고 기록" if y == hottest_year else "일반")

color_scale = alt.Scale(domain=["최고 기록", "일반"], range=["#ff4b4b", "#a8c8f0"])

bar = (
    alt.Chart(agg)
    .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
    .encode(
        x=alt.X("연도:O", title="연도", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("값:Q", title=unit_label),
        color=alt.Color("구분:N", scale=color_scale, legend=alt.Legend(title="")),
        tooltip=[
            alt.Tooltip("연도:O", title="연도"),
            alt.Tooltip("값:Q", title=unit_label, format=".1f"),
        ],
    )
)

mean_rule = (
    alt.Chart(pd.DataFrame({"평균": [overall_mean]}))
    .mark_rule(color="#888888", strokeDash=[6, 4], size=1.5)
    .encode(y="평균:Q")
)

mean_text = (
    alt.Chart(pd.DataFrame({"평균": [overall_mean], "라벨": [f"전체 평균 {overall_mean:.1f}°C"]}))
    .mark_text(align="left", dx=5, dy=-6, color="#888888")
    .encode(y="평균:Q", text="라벨:N", x=alt.value(0))
)

chart = (bar + mean_rule + mean_text).properties(height=440).configure_view(strokeWidth=0)

st.altair_chart(chart, use_container_width=True)

# ------------------------------------------------------------
# Top 5 랭킹 + 상세 데이터
# ------------------------------------------------------------
st.subheader("🥇 역대 Top 5")
medals = ["🥇", "🥈", "🥉", "4위", "5위"]
rank_cols = st.columns(len(top5))
for i, row in top5.iterrows():
    with rank_cols[i]:
        st.markdown(f"### {medals[i]}")
        st.markdown(f"**{int(row['연도'])}년**")
        st.markdown(f"{row['값']:.1f}°C")

with st.expander("전체 연도별 데이터 보기"):
    st.dataframe(
        agg[["연도", "값"]]
        .sort_values("값", ascending=False)
        .rename(columns={"값": unit_label})
        .reset_index(drop=True),
        use_container_width=True,
    )

with st.expander("선택 기간의 원본 일별 데이터 보기"):
    st.dataframe(
        period_df[["날짜", "평균기온", "최저기온", "최고기온"]].reset_index(drop=True),
        use_container_width=True,
    )
