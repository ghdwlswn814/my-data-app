import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 기본 화면 설정
# =========================================================
st.set_page_config(
    page_title="KOBIS 일일 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 KOBIS 일일 박스오피스")


# =========================================================
# 한국 시간 기준 오늘 날짜
# =========================================================
def get_korea_today():
    # 배포 서버의 시간이 아니라 한국 시간으로 계산합니다.
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


# =========================================================
# 숫자 변환 함수
# KOBIS API는 숫자도 문자열로 보내므로 정수로 바꿉니다.
# =========================================================
def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# =========================================================
# KOBIS API 호출
#
# 같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를
# 사용하므로 API를 다시 호출하지 않습니다.
# =========================================================
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    response = requests.get(
        url,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# 날짜 설정
# =========================================================
today_kst = get_korea_today()

# 오늘은 아직 집계 전이므로 어제까지만 선택할 수 있습니다.
yesterday_kst = today_kst - timedelta(days=1)


# =========================================================
# 날짜 선택 달력
# =========================================================
selected_date = st.date_input(
    "📅 조회 날짜",
    value=yesterday_kst,
    max_value=yesterday_kst,
    help="오늘은 아직 집계 전이므로 어제까지의 날짜만 선택할 수 있습니다.",
)


# KOBIS API는 YYYYMMDD 형식을 사용합니다.
target_dt = selected_date.strftime("%Y%m%d")
display_date = selected_date.strftime("%Y-%m-%d")


# =========================================================
# Secrets에서 KOBIS 인증키 가져오기
# =========================================================
try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 Settings → Secrets에서 "
        "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
    )
    st.stop()


# =========================================================
# KOBIS API 호출
# =========================================================
try:
    data = get_boxoffice(
        target_dt,
        api_key,
    )

except requests.exceptions.Timeout:
    st.error(
        "KOBIS API 응답 시간이 초과되었습니다.\n\n"
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "KOBIS API 요청에 실패했습니다.\n\n"
        "다음을 확인해 주세요:\n"
        "• 인터넷 연결 상태\n"
        "• KOBIS API 서버 상태\n"
        "• KOBIS API 주소\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except ValueError:
    st.error(
        "KOBIS API의 응답을 읽을 수 없습니다.\n\n"
        "KOBIS API 응답 상태를 확인해 주세요."
    )
    st.stop()


# =========================================================
# faultInfo 확인
#
# KOBIS는 인증키가 틀려도 HTTP 200을 반환할 수 있으므로
# faultInfo를 별도로 확인해야 합니다.
# =========================================================
if "faultInfo" in data:

    fault_info = data["faultInfo"]

    message = fault_info.get(
        "message",
        "KOBIS API에서 오류가 발생했습니다.",
    )

    st.error(
        "KOBIS API에서 오류가 발생했습니다.\n\n"
        f"오류 내용: {message}\n\n"
        "다음을 확인해 주세요:\n"
        "• Streamlit Cloud Secrets의 KOBIS_KEY\n"
        "• 인증키 앞뒤의 불필요한 공백\n"
        "• KOBIS에서 발급한 인증키의 유효 여부"
    )

    st.stop()


# =========================================================
# API 결과 확인
# =========================================================
boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.warning(
        f"📅 {display_date}\n\n"
        "그날은 아직 집계 전입니다."
    )
    st.stop()


movie_list = boxoffice_result.get(
    "dailyBoxOfficeList",
    [],
)


# 영화 목록이 비어 있으면 안내합니다.
if not movie_list:
    st.warning(
        f"📅 {display_date}\n\n"
        "그날은 아직 집계 전입니다."
    )
    st.stop()


# =========================================================
# 영화 데이터 정리
# =========================================================
movies = []

for movie in movie_list:

    # 숫자 문자열을 정수로 변환합니다.
    rank = to_int(movie.get("rank"))
    rank_inten = to_int(movie.get("rankInten"))
    audi_cnt = to_int(movie.get("audiCnt"))
    audi_acc = to_int(movie.get("audiAcc"))
    scrn_cnt = to_int(movie.get("scrnCnt"))

    movie_name = movie.get("movieNm", "")

    # 누적관객이 100만 명을 넘으면 트로피를 붙입니다.
    if audi_acc > 1_000_000:
        movie_name = "🏆 " + movie_name

    # 순위 변동 표시
    if rank_inten > 0:
        change_text = f"↑ {rank_inten}"

    elif rank_inten < 0:
        change_text = f"↓ {abs(rank_inten)}"

    else:
        change_text = "—"

    movies.append(
        {
            "순위": rank,
            "순위변동": change_text,
            "순위변동값": rank_inten,
            "영화명": movie_name,
            "개봉일": movie.get("openDt", ""),
            "관객수": audi_cnt,
            "누적관객": audi_acc,
            "스크린수": scrn_cnt,
        }
    )


# 순위순으로 정렬합니다.
movies.sort(
    key=lambda movie: movie["순위"]
)


# =========================================================
# 조회 날짜
# =========================================================
st.caption(
    f"조회 날짜: {display_date} · 한국 시간 기준"
)


# =========================================================
# 1위 영화
# =========================================================
first_movie = movies[0]

st.subheader(
    f"🥇 1위 · {first_movie['영화명']}"
)


# =========================================================
# 1위 지표 카드
# =========================================================
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )


# =========================================================
# 관객수 상위 5편
# =========================================================
st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]


# 영화명과 관객수를 데이터프레임으로 만듭니다.
chart_data = pd.DataFrame(
    {
        "영화명": [movie["영화명"] for movie in top5],
        "관객수": [movie["관객수"] for movie in top5],
    }
)

chart_data = chart_data.set_index("영화명")

st.bar_chart(
    chart_data,
    horizontal=True,
)


# =========================================================
# 전체 박스오피스 표
# =========================================================
st.subheader("🎞️ 전체 순위")


# 화면에 보여줄 데이터만 따로 만듭니다.
# '순위변동값'은 색상 처리에만 사용하고 화면에는 표시하지 않습니다.
table_data = pd.DataFrame(
    [
        {
            "순위": movie["순위"],
            "순위변동": movie["순위변동"],
            "영화명": movie["영화명"],
            "개봉일": movie["개봉일"],
            "관객수": movie["관객수"],
            "누적관객": movie["누적관객"],
            "스크린수": movie["스크린수"],
            "_순위변동값": movie["순위변동값"],
        }
        for movie in movies
    ]
)


# ---------------------------------------------------------
# 순위 변동 화살표 색상을 정하는 함수
# ---------------------------------------------------------
def color_rank_change(row):

    value = row["_순위변동값"]

    if value > 0:
        return [
            "color: red; font-weight: bold;"
            if column == "순위변동"
            else ""
            for column in row.index
        ]

    elif value < 0:
        return [
            "color: blue; font-weight: bold;"
            if column == "순위변동"
            else ""
            for column in row.index
        ]

    return [""] * len(row)


# 색상을 적용합니다.
styled_table = (
    table_data.style
    .apply(color_rank_change, axis=1)
    .format(
        {
            "관객수": "{:,}",
            "누적관객": "{:,}",
            "스크린수": "{:,}",
        }
    )
)


# ---------------------------------------------------------
# 실제 표를 Streamlit 데이터프레임으로 표시합니다.
#
# 이전 코드처럼 HTML을 직접 만들지 않기 때문에
# '코드가 그대로 보이는 문제'를 피할 수 있습니다.
# ---------------------------------------------------------
st.dataframe(
    styled_table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            width="small",
        ),
        "순위변동": st.column_config.TextColumn(
            "순위 변동",
            width="small",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
            width="large",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
            width="medium",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개",
        ),
        "_순위변동값": None,
    },
)
