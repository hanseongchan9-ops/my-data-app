import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# 웹 페이지 기본 설정 (제목, 레이아웃 넓게)
st.set_page_config(page_title="어제 박스오피스 순위", layout="wide")

# 1. 한국 표준시(KST: UTC+9) 기준으로 '어제' 날짜 계산하기
# 배포 서버의 시계가 해외 기준이어도 한국 시간 기준으로 계산합니다.
kst_timezone = timezone(timedelta(hours=9))
now_kst = datetime.now(kst_timezone)
yesterday_kst = now_kst - timedelta(days=1)
target_date = yesterday_kst.strftime("%Y%m%d")  # API 요구 형식: YYYYMMDD
formatted_date_display = yesterday_kst.strftime("%Y년 %m월 %d일")

st.title(f"어제({formatted_date_display}) 박스오피스 순위")

# 2. secrets에서 인증키 불러오기 및 검증
if "KOBIS_KEY" not in st.secrets:
    st.error("인증키 설정이 필요합니다.")
    st.info(
        "Streamlit Cloud의 [Settings] -> [Secrets] 메뉴 또는 로컬의 .streamlit/secrets.toml 파일에\n"
        'KOBIS_KEY = "발급받은키" 형태로 입력했는지 확인해 주세요.'
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 3. KOBIS API 데이터 호출 함수 (캐싱 적용)
# ttl=3600으로 설정하여 동일한 날짜 요청은 1시간(3600초) 동안 캐시된 결과를 사용합니다.
@st.cache_data(ttl=3600)
def fetch_daily_boxoffice(key: str, date_str: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": key, "targetDt": date_str}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        # HTTP 응답 상태 코드가 200이 아닌 경우 예외 발생
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"네트워크 통신 오류가 발생했습니다: {e}"

# API 호출 실행
data, error_message = fetch_daily_boxoffice(api_key, target_date)

# 4. 예외 및 오류 처리
if error_message:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.write(error_message)
    st.info("인터넷 연결 상태나 KOBIS API 서버 상태를 확인해 주세요.")
    st.stop()

# API에서 faultInfo 상자가 온 경우 (인증키 오류 등)
if "faultInfo" in data:
    st.error("KOBIS API 응답 오류가 발생했습니다.")
    st.write(f"오류 메시지: {data['faultInfo'].get('message', '알 수 없는 오류')}")
    st.info("secrets에 등록된 KOBIS_KEY가 올바른지, API 사용 기한이 만료되지 않았는지 확인해 주세요.")
    st.stop()

# 응답 내 박스오피스 목록 추출
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어있는 경우
if not daily_list:
    st.warning("조회된 박스오피스 데이터가 없습니다.")
    st.info("KOBIS API의 집계가 아직 완료되지 않았거나 해당 날짜의 데이터가 존재하지 않을 수 있습니다.")
    st.stop()

# 5. 데이터 전처리 (문자열 -> 숫자 변환)
df = pd.DataFrame(daily_list)

# 필요한 컬럼 정수형 변환
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 순위 기준으로 정렬
df = df.sort_values(by="rank", ascending=True).reset_index(drop=True)

# 6. UI 출력: 1위 영화 지표 카드 (st.metric)
top_1 = df.iloc[0]

st.subheader(f"1위 영화: {top_1['movieNm']}")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="일일 관객수", value=f"{top_1['audiCnt']:,} 명")
with col2:
    st.metric(label="누적 관객수", value=f"{top_1['audiAcc']:,} 명")
with col3:
    st.metric(label="스크린 수", value=f"{top_1['scrnCnt']:,} 개")

st.divider()

# 7. UI 출력: 관객수 상위 5편 막대그래프
st.subheader("관객수 상위 5개 영화")
top_5_df = df.head(5)[["movieNm", "audiCnt"]].set_index("movieNm")
st.bar_chart(top_5_df)

st.divider()

# 8. UI 출력: 전체 순위 표
st.subheader("전체 순위 표")

# 화면 표시용 컬럼명 변경 및 가독성을 위한 숫자 포맷팅
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

st.dataframe(
    display_df,
    column_config={
        "관객수": st.column_config.NumberColumn(format="%d 명"),
        "누적관객": st.column_config.NumberColumn(format="%d 명"),
        "스크린수": st.column_config.NumberColumn(format="%d 개"),
    },
    use_container_width=True,
    hide_index=True
)
