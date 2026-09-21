import requests
import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 화면 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 KOBIS 일일 박스오피스")


# ---------------------------------------------------------
# 한국 시간 기준으로 오늘 날짜를 가져오는 함수
# ---------------------------------------------------------
def get_korea_today():
    """배포 서버의 시간이 아니라 한국 시간으로 오늘 날짜를 구합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


# ---------------------------------------------------------
# 날짜를 KOBIS API용 문자열(YYYYMMDD)로 바꾸는 함수
# ---------------------------------------------------------
def format_target_date(selected_date):
    """달력에서 선택한 날짜를 KOBIS API 형식으로 변환합니다."""
    return selected_date.strftime("%Y%m%d")


# ---------------------------------------------------------
# API에서 받은 숫자를 정수로 바꾸는 함수
# ---------------------------------------------------------
def to_int(value):
    """KOBIS가 문자열로 보내는 숫자를 실제 정수로 변환합니다."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------
# KOBIS API 호출
#
# ttl=3600:
# 같은 날짜를 다시 선택하면 약 1시간 동안은
# API를 다시 호출하지 않고 캐시된 결과를 사용합니다.
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):
    """선택한 날짜의 KOBIS 일일 박스오피스를 가져옵니다."""

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

    # HTTP 오류가 발생하면 예외를 발생시킵니다.
    response.raise_for_status()

    return response.json()


# ---------------------------------------------------------
# 한국 시간 기준 오늘과 어제를 계산합니다.
# ---------------------------------------------------------
today_kst = get_korea_today()
yesterday_kst = today_kst - timedelta(days=1)


# ---------------------------------------------------------
# 날짜 선택
#
# 가장 늦은 날짜는 반드시 '어제'입니다.
# 따라서 오늘 날짜는 달력에서 선택할 수 없습니다.
# ---------------------------------------------------------
selected_date = st.date_input(
    "조회할 날짜",
    value=yesterday_kst,
    max_value=yesterday_kst,
    help="오늘은 아직 집계 전이므로 어제까지의 날짜만 선택할 수 있습니다.",
)


# ---------------------------------------------------------
# 선택한 날짜를 KOBIS API 형식으로 변환합니다.
# ---------------------------------------------------------
target_dt = format_target_date(selected_date)
display_date = selected_date.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# Streamlit Secrets에서 KOBIS 인증키를 가져옵니다.
#
# 실제 인증키는 코드에 넣지 않습니다.
# Streamlit Cloud의 Secrets에 다음처럼 등록합니다.
#
# KOBIS_KEY = "본인의_인증키"
# ---------------------------------------------------------
try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 Settings → Secrets에서 "
        "KOBIS_KEY가 등록되어 있는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------
try:
    data = get_boxoffice(
        target_dt,
        api_key,
    )

except requests.exceptions.Timeout:
    st.error(
        "KOBIS API 응답 시간이 초과되었습니다.\n\n"
        "잠시 후 다시 시도하거나 KOBIS API 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        "KOBIS API 요청에 실패했습니다.\n\n"
        "다음 내용을 확인해 주세요:\n"
        "- 인터넷 연결 상태\n"
        "- KOBIS API 주소\n"
        "- KOBIS API 서버 상태\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except ValueError:
    st.error(
        "KOBIS API 응답을 JSON으로 읽을 수 없습니다.\n\n"
        "KOBIS API의 응답 상태를 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# KOBIS API의 faultInfo 확인
#
# 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있으므로
# faultInfo가 있는지 별도로 확인합니다.
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
        "- 인증키 앞뒤에 불필요한 공백이 없는지\n"
        "- KOBIS에서 발급한 API 키가 유효한지"
    )
    st.stop()


# ---------------------------------------------------------
# boxOfficeResult 확인
# ---------------------------------------------------------
boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.warning(
        f"{display_date}의 박스오피스 결과가 없습니다.\n\n"
        "그날은 아직 집계 전입니다."
    )
    st.stop()


# ---------------------------------------------------------
# 영화 목록 가져오기
# ---------------------------------------------------------
movie_list = boxoffice_result.get(
    "dailyBoxOfficeList",
    [],
)


# ---------------------------------------------------------
# 영화 목록이 비어 있는 경우
#
# 사용자가 요청한 문구를 그대로 안내합니다.
# ---------------------------------------------------------
if not movie_list:
    st.warning(
        f"📅 {display_date}\n\n"
        "그날은 아직 집계 전입니다."
    )
    st.stop()


# ---------------------------------------------------------
# API의 문자열 데이터를 실제 숫자로 변환합니다.
# ---------------------------------------------------------
movies = []

for movie in movie_list:

    rank_inten = to_int(
        movie.get("rankInten")
    )

    audi_acc = to_int(
        movie.get("audiAcc")
    )

    # -----------------------------------------------------
    # 순위 증감 표시용 문자열을 만듭니다.
    #
    # 양수: 순위가 오른 영화 → 빨간 위 화살표
    # 음수: 순위가 내린 영화 → 파란 아래 화살표
    # 0: 변동 없음
    # -----------------------------------------------------
    if rank_inten > 0:
        rank_change = (
            f'<span style="color:red; font-weight:bold;">'
            f"↑ {rank_inten}"
            f"</span>"
        )

    elif rank_inten < 0:
        rank_change = (
            f'<span style="color:blue; font-weight:bold;">'
            f"↓ {abs(rank_inten)}"
            f"</span>"
        )

    else:
        rank_change = "—"

    # -----------------------------------------------------
    # 누적관객이 100만 명을 넘었으면 트로피를 붙입니다.
    # -----------------------------------------------------
    movie_name = movie.get(
        "movieNm",
        "",
    )

    if audi_acc > 1_000_000:
        movie_name = f"🏆 {movie_name}"

    movies.append(
        {
            "순위": to_int(movie.get("rank")),
            "순위변동": rank_change,
            "영화명": movie_name,
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int(movie.get("audiCnt")),
            "누적관객": audi_acc,
            "스크린수": to_int(movie.get("scrnCnt")),
        }
    )


# ---------------------------------------------------------
# 순위를 기준으로 정렬합니다.
# ---------------------------------------------------------
movies.sort(
    key=lambda movie: movie["순위"]
)


# ---------------------------------------------------------
# 조회 날짜 표시
# ---------------------------------------------------------
st.caption(
    f"조회 날짜: {display_date} · "
    "한국 시간 기준"
)


# ---------------------------------------------------------
# 1위 영화의 주요 정보
# ---------------------------------------------------------
first_movie = movies[0]

st.subheader(
    f"🥇 1위 · {first_movie['영화명']}"
)


# ---------------------------------------------------------
# 1위 영화의 지표 카드 3개
# ---------------------------------------------------------
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
# 관객수 상위 5편
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")


top5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]


# Streamlit의 막대그래프는 데이터프레임 형태로
# 넣으면 영화명과 관객수를 함께 관리하기 편합니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}


st.bar_chart(
    chart_data,
    horizontal=True,
)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎞️ 전체 순위")


# 순위 변동 화살표와 트로피 이모지를 제대로 보여주기 위해
# HTML을 사용할 수 있는 st.markdown 표를 만듭니다.
#
# 숫자는 화면 표시뿐 아니라 위에서 이미 int로 변환했기 때문에
# 그래프와 정렬에도 숫자로 사용할 수 있습니다.
table_rows = []

for movie in movies:
    table_rows.append(
        f"""
        <tr>
            <td>{movie["순위"]}</td>
            <td>{movie["순위변동"]}</td>
            <td>{movie["영화명"]}</td>
            <td>{movie["개봉일"]}</td>
            <td>{movie["관객수"]:,}</td>
            <td>{movie["누적관객"]:,}</td>
            <td>{movie["스크린수"]:,}</td>
        </tr>
        """
    )


table_html = f"""
<style>
.boxoffice-table {{
    width: 100%;
    border-collapse: collapse;
}}

.boxoffice-table th,
.boxoffice-table td {{
    padding: 10px;
    border-bottom: 1px solid #ddd;
    text-align: right;
}}

.boxoffice-table th {{
    font-weight: bold;
    background-color: rgba(128, 128, 128, 0.1);
}}

.boxoffice-table th:nth-child(3),
.boxoffice-table td:nth-child(3) {{
    text-align: left;
}}

.boxoffice-table th:nth-child(4),
.boxoffice-table td:nth-child(4) {{
    text-align: center;
}}
</style>

<table class="boxoffice-table">
    <thead>
        <tr>
            <th>순위</th>
            <th>순위변동</th>
            <th>영화명</th>
            <th>개봉일</th>
            <th>관객수</th>
            <th>누적관객</th>
            <th>스크린수</th>
        </tr>
    </thead>

    <tbody>
        {"".join(table_rows)}
    </tbody>
</table>
"""


st.markdown(
    table_html,
    unsafe_allow_html=True,
)
