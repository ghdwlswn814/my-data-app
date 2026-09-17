import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 화면 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")


# ---------------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜를 계산하는 함수
# 배포 서버가 어느 나라 시간인지와 관계없이 동작합니다.
# ---------------------------------------------------------
def get_yesterday_kst():
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now - timedelta(days=1)
    return yesterday.strftime("%Y%m%d"), yesterday.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# 문자열로 받은 숫자를 실제 숫자로 바꾸는 함수
# API가 숫자를 문자열로 보내기 때문에 사용합니다.
# ---------------------------------------------------------
def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------
# KOBIS API에서 박스오피스 데이터를 가져옵니다.
#
# ttl=3600:
# 같은 날짜에 다시 요청하면 약 1시간 동안 캐시된 결과를
# 사용해서 KOBIS API를 다시 호출하지 않습니다.
# ---------------------------------------------------------
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

    response = requests.get(url, params=params, timeout=10)

    # HTTP 오류가 있으면 예외를 발생시킵니다.
    response.raise_for_status()

    return response.json()


# ---------------------------------------------------------
# 날짜 계산
# ---------------------------------------------------------
target_dt, display_date = get_yesterday_kst()


# ---------------------------------------------------------
# Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
#
# 실제 인증키는 코드에 넣지 않습니다.
# Streamlit Cloud에서는 Settings > Secrets에
# KOBIS_KEY = "발급받은_키"
# 형태로 등록하세요.
# ---------------------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다. "
        "Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지 확인하세요."
    )
    st.stop()


# ---------------------------------------------------------
# API 호출
# ---------------------------------------------------------
try:
    data = get_boxoffice(target_dt, api_key)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS API 응답 시간이 초과되었습니다. "
        "잠시 후 다시 실행하거나 KOBIS API 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "KOBIS API 요청에 실패했습니다.\n\n"
        "다음을 확인해 주세요:\n"
        "- 인터넷 연결 상태\n"
        "- KOBIS API 주소가 정상인지\n"
        "- KOBIS API 서버 상태\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except ValueError:
    st.error(
        "KOBIS API의 응답을 JSON으로 읽을 수 없습니다. "
        "KOBIS API 응답 상태를 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 인증키 오류 등을 확인합니다.
#
# KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있고,
# 이 경우 faultInfo가 들어올 수 있습니다.
# ---------------------------------------------------------
if "faultInfo" in data:
    fault_info = data["faultInfo"]

    fault_message = fault_info.get(
        "message",
        "KOBIS API에서 오류가 반환되었습니다.",
    )

    st.error(
        "KOBIS API에서 오류가 반환되었습니다.\n\n"
        f"오류 내용: {fault_message}\n\n"
        "다음을 확인해 주세요:\n"
        "- Streamlit Cloud Secrets의 KOBIS_KEY가 정확한지\n"
        "- 인증키 앞뒤에 불필요한 공백이나 따옴표가 없는지\n"
        "- KOBIS에서 발급한 API 키가 유효한지"
    )
    st.stop()


# ---------------------------------------------------------
# boxOfficeResult와 영화 목록을 확인합니다.
# ---------------------------------------------------------
boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.error(
        "박스오피스 결과가 없습니다.\n\n"
        "다음을 확인해 주세요:\n"
        "- 조회 날짜가 정상적으로 계산되었는지\n"
        "- KOBIS API가 정상적으로 응답했는지\n"
        "- KOBIS API의 일일 박스오피스 데이터가 존재하는지"
    )
    st.stop()


movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(
        f"{display_date}의 영화 목록이 없습니다.\n\n"
        "KOBIS에서 해당 날짜의 일일 박스오피스 집계가 "
        "아직 제공되지 않았거나 API 응답을 확인할 필요가 있습니다."
    )
    st.stop()


# ---------------------------------------------------------
# API의 문자열 숫자를 실제 숫자로 변환합니다.
# ---------------------------------------------------------
movies = []

for movie in movie_list:
    movies.append(
        {
            "순위": to_int(movie.get("rank")),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int(movie.get("audiCnt")),
            "누적관객": to_int(movie.get("audiAcc")),
            "스크린수": to_int(movie.get("scrnCnt")),
            "상영횟수": to_int(movie.get("showCnt")),
        }
    )


# 순위를 기준으로 다시 정렬합니다.
movies.sort(key=lambda x: x["순위"])


# ---------------------------------------------------------
# 조회 날짜 표시
# ---------------------------------------------------------
st.caption(
    f"조회 날짜: {display_date} · 한국 시간 기준 '어제' · "
    "KOBIS 일일 박스오피스"
)


# ---------------------------------------------------------
# 1위 영화의 주요 지표를 크게 보여줍니다.
# ---------------------------------------------------------
first_movie = movies[0]

st.subheader(f"🥇 1위 · {first_movie['영화명']}")

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


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["관객수"],
    reverse=True,
)[:5]

chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}

st.bar_chart(chart_data, horizontal=True)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎞️ 전체 순위")

table_data = [
    {
        "순위": movie["순위"],
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": movie["관객수"],
        "누적관객": movie["누적관객"],
        "스크린수": movie["스크린수"],
    }
    for movie in movies
]

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d",
        ),
    },
)
