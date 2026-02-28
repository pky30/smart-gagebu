import streamlit as st
import pandas as pd
import plotly.express as px
import io
import streamlit.components.v1 as components
from sqlalchemy import create_engine

# --- 1. 기본 페이지 설정 ---
st.set_page_config(page_title="스마트 가계부", page_icon="💰", layout="wide")

# --- 2. 데이터베이스 연결 (Supabase) ---
# 🚨 아래 주소의 [본인비밀번호] 부분을 지우고 진짜 비밀번호를 넣어주세요!
DB_URL = "postgresql://postgres.bvuvpldyifeficrfontn:eodud69rldud71dudtnr73@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"

@st.cache_resource
def init_connection():
    return create_engine(DB_URL)

engine = init_connection()

# 데이터 불러오기 함수
@st.cache_data(ttl=10) # 10초마다 데이터 갱신
def load_data():
    df = pd.read_sql("SELECT * FROM ledger ORDER BY date DESC, id DESC", engine)
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"데이터베이스 연결에 실패했습니다: {e}")
    st.stop()

# --- 3. 사이드바 (검색 필터 및 계산기) ---
st.sidebar.header("🔍 검색 필터")
start_date = st.sidebar.date_input("시작일", pd.to_datetime("2026-01-01"))
end_date = st.sidebar.date_input("종료일", pd.to_datetime("today"))

category_list = ["전체"] + list(df['category'].dropna().unique())
selected_category = st.sidebar.selectbox("카테고리 선택", category_list)

search_keyword = st.sidebar.text_input("🛍️ 품목명 검색", "")

st.sidebar.markdown("---")
st.sidebar.header("🧮 빠른 계산기")
calc_input = st.sidebar.text_input("수식 입력 (예: 15000*10%)")
if calc_input:
    try:
        calc_expr = calc_input.replace('%', '/100')
        result = eval(calc_expr)
        st.sidebar.success(f"결과: {result:,.0f}")
    except:
        st.sidebar.error("올바른 수식을 입력해주세요.")

# --- 4. 데이터 필터링 적용 ---
mask = (df['date'] >= start_date) & (df['date'] <= end_date)
filtered_df = df.loc[mask]

if selected_category != "전체":
    filtered_df = filtered_df[filtered_df['category'] == selected_category]
    
if search_keyword:
    filtered_df = filtered_df[filtered_df['item'].str.contains(search_keyword, na=False)]

# --- 5. 메인 화면 (요약 통계) ---
st.title("💰 스마트 가계부 웹 버전")
st.markdown("안전한 클라우드 DB(Supabase)가 연동된 정식 웹 버전입니다.")

st.subheader("📊 요약 통계")
col1, col2, col3 = st.columns(3)

total_income = filtered_df[filtered_df['type'] == '수입']['amount'].sum()
total_expense = filtered_df[filtered_df['type'] == '지출']['amount'].sum()
net_income = total_income - total_expense

col1.metric("총 수입", f"{total_income:,.0f} 원")
col2.metric("총 지출", f"{total_expense:,.0f} 원")
col3.metric("순수익 (수입-지출)", f"{net_income:,.0f} 원")

# --- 6. 차트 영역 ---
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("**🍩 카테고리별 지출 비율**")
    expense_df = filtered_df[filtered_df['type'] == '지출']
    if not expense_df.empty:
        pie_fig = px.pie(expense_df, values='amount', names='category', hole=0.4)
        st.plotly_chart(pie_fig, use_container_width=True)
    else:
        st.info("해당 기간에 지출 내역이 없습니다.")

with col_chart2:
    st.markdown("**📈 일자별 지출 흐름**")
    if not expense_df.empty:
        daily_expense = expense_df.groupby('date')['amount'].sum().reset_index()
        bar_fig = px.bar(daily_expense, x='date', y='amount')
        st.plotly_chart(bar_fig, use_container_width=True)
    else:
        st.info("해당 기간에 지출 내역이 없습니다.")

st.markdown("---")

# --- 7. 전체 거래 내역 및 출력/다운로드 버튼 ---
st.markdown("### 📋 전체 거래 내역 (최근 기록순)")

# 엑셀 다운로드 & 인쇄 버튼 나란히 배치
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    # 엑셀 파일 생성용 버퍼
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        filtered_df.to_excel(writer, index=False, sheet_name='가계부내역')
    
    # 다운로드 버튼
    st.download_button(
        label="📥 엑셀(Excel)로 다운로드",
        data=buffer.getvalue(),
        file_name="smart_ledger_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col_btn2:
    # 화면 인쇄 (PDF 저장) 버튼
    components.html(
        """
        <button onclick="window.parent.print()" style="
            background-color: #FF4B4B; 
            color: white; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 16px; 
            font-weight: bold;
            width: 100%;
            height: 48px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
        🖨️ 화면 인쇄 / PDF 출력
        </button>
        """,
        height=50
    )

# 필터링된 데이터 표 출력 (인덱스 숨김)
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# (참고: 입력 폼이나 달력 보기 등 추가 탭 기능이 있었다면 이 아래에 이어서 작성하시면 됩니다!)