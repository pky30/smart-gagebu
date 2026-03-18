import streamlit as st
import psycopg2
from sqlalchemy import create_engine
import pandas as pd
import os
import datetime
import plotly.express as px
import calendar
import holidays
from supabase import create_client

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="스마트 가계부", page_icon="💰", layout="wide")

# 🌟 [매우 중요!] Supabase 접속 주소 
DB_URL = st.secrets["DB_URL"]
# --- [회원가입 및 로그인 화면 시작] ---
# 1. Supabase 클라이언트 초기화 (금고에서 열쇠 꺼내기)
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# 2. 세션(로그인 상태) 관리
if 'user' not in st.session_state:
    st.session_state.user = None

# 3. 로그인 화면 띄우기 (로그인이 안 되어 있을 때만)
if st.session_state.user is None:
    st.title("🔐 스마트 가계부 로그인")
    st.markdown("나만의 가계부를 안전하게 관리하세요.")
    
    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
    
    with tab_login:
        login_email = st.text_input("이메일", key="login_email")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", use_container_width=True):
            try:
                response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_pw})
                st.session_state.user = response.user
                st.success("로그인 성공!")
                st.rerun()
            except Exception as e:
                st.error("로그인 실패: 이메일이나 비밀번호를 확인해주세요.")

    with tab_signup:
        st.info("비밀번호는 6자리 이상으로 설정해주세요.")
        signup_email = st.text_input("가입할 이메일", key="signup_email")
        signup_pw = st.text_input("비밀번호 (6자리 이상)", type="password", key="signup_pw")
        if st.button("회원가입", use_container_width=True):
            try:
                response = supabase.auth.sign_up({"email": signup_email, "password": signup_pw})
                st.success("🎉 회원가입 성공! 이제 옆의 [로그인] 탭에서 로그인해주세요.")
            except Exception as e:
                st.error(f"회원가입 실패: {e}")
                
    st.stop() # 로그인이 안 되어 있으면 여기서 화면을 멈추고 가계부를 보여주지 않음

# 4. 로그인 성공 시 사이드바에 환영 인사와 로그아웃 버튼 표시
user_email = st.session_state.user.email
st.sidebar.markdown(f"**👤 {user_email}** 님 환영합니다!")
if st.sidebar.button("로그아웃"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()
st.sidebar.markdown("---")
# --- [회원가입 및 로그인 화면 끝] ---

# ==========================================
# 🛠️ 클라우드 DB 초기화 (테이블 자동 생성)
# ==========================================
@st.cache_resource
def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id SERIAL PRIMARY KEY,
                date DATE,
                type VARCHAR(10),
                category VARCHAR(50),
                item VARCHAR(100),
                unit_price INTEGER,
                discount INTEGER,
                quantity INTEGER,
                amount INTEGER,
                memo TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_memos (
                date DATE PRIMARY KEY,
                memo TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"DB 연결 실패! 비밀번호나 주소를 다시 확인해주세요. (에러: {e})")

init_db()

# ==========================================
# 🎨 UI/UX 디자인 커스텀
# ==========================================
st.markdown("""
<style>
div.stButton > button {
    border-radius: 8px !important;
    border: 1px solid #cccccc !important;
    background-color: #ffffff !important;
    color: #31333f !important;
    font-weight: bold !important;
    box-shadow: 0px 5px 0px 0px #b4b8c0 !important; 
    transition: all 0.1s ease !important;
    margin-bottom: 5px !important; 
    padding: 0.2rem 0.5rem !important; 
}
div.stButton > button:active {
    box-shadow: 0px 0px 0px 0px #b4b8c0 !important; 
    transform: translateY(5px) !important; 
}
div.stButton > button[kind="primary"] {
    background-color: #ff4b4b !important;
    border: 1px solid #ff4b4b !important;
    color: white !important;
    box-shadow: 0px 5px 0px 0px #b02727 !important; 
}
div.stButton > button[kind="primary"]:active {
    box-shadow: 0px 0px 0px 0px #b02727 !important;
    transform: translateY(5px) !important;
}
.cal-date { font-weight: bold; font-size: 1.3em; } 
.cal-holiday { color: #ff7676; font-size: 0.85em; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;} 
.cal-expense { color: #ff4b4b; font-weight: bold; font-size: 1.0em; text-align: right; margin-top: 8px; margin-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

st.title("💰 스마트 가계부 웹 버전")
st.write("안전한 클라우드 DB(Supabase)가 연동된 정식 웹 버전입니다.")

# --- 세션 상태 초기화 ---
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "none"
if 'selected_cal_date' not in st.session_state:
    st.session_state.selected_cal_date = None

def toggle_tab(tab_name):
    if st.session_state.active_tab == tab_name:
        st.session_state.active_tab = "none"
    else:
        st.session_state.active_tab = tab_name

# 2. 클라우드 DB 연동 및 데이터 불러오기 함수
def load_data():
    try:
        engine = create_engine(DB_URL)
        df = pd.read_sql_query(f"SELECT * FROM ledger WHERE user_email = '{st.session_state.user.email}' ORDER BY date DESC", engine)
        return df
    except Exception as e:
        return pd.DataFrame()

def load_memo_data():
    try:
        engine = create_engine(DB_URL)
        df = pd.read_sql_query(f"SELECT * FROM daily_memos WHERE user_email = '{st.session_state.user.email}' ORDER BY date DESC", engine)
        return df
    except Exception as e:
        return pd.DataFrame()

df_ledger = load_data()
df_memos = load_memo_data()

if df_ledger.empty and len(df_ledger.columns) == 0:
    st.info("클라우드 DB가 비어있습니다. 첫 번째 거래 내역을 등록해 보세요!")
    df_ledger = pd.DataFrame(columns=['id', 'date', 'type', 'category', 'item', 'unit_price', 'discount', 'quantity', 'amount', 'memo'])

df_ledger = df_ledger.rename(columns={
    'id': '번호', 'date': '날짜', 'type': '구분', 'category': '카테고리',
    'item': '내역', 'unit_price': '단가', 'discount': '할인',
    'quantity': '수량', 'amount': '금액', 'memo': '메모'
})

if not df_ledger.empty:
    df_ledger['날짜_dt'] = pd.to_datetime(df_ledger['날짜'])
    df_ledger['연월'] = df_ledger['날짜_dt'].dt.strftime('%Y-%m')
    df_ledger['월'] = df_ledger['날짜_dt'].dt.strftime('%m월')
    df_ledger['연도'] = df_ledger['날짜_dt'].dt.year
    df_ledger['날짜'] = df_ledger['날짜_dt'].dt.date 

# ==========================================
# 사이드바 설정
# ==========================================
st.sidebar.header("🔍 검색 필터")
min_date = df_ledger['날짜'].min() if not df_ledger.empty and not pd.isna(df_ledger['날짜'].min()) else datetime.date.today()
max_date = df_ledger['날짜'].max() if not df_ledger.empty and not pd.isna(df_ledger['날짜'].max()) else datetime.date.today()

start_date = st.sidebar.date_input("시작일", min_date)
end_date = st.sidebar.date_input("종료일", max_date)

categories = ["전체"] + list(df_ledger['카테고리'].unique()) if not df_ledger.empty else ["전체"]
selected_category = st.sidebar.selectbox("카테고리 선택", categories)

st.sidebar.markdown("---")
search_keyword = st.sidebar.text_input("🔍 품목명 검색", placeholder="일부 단어 입력 후 Enter")

if not df_ledger.empty:
    filtered_df = df_ledger[(df_ledger['날짜'] >= start_date) & (df_ledger['날짜'] <= end_date)]
    if selected_category != "전체":
        filtered_df = filtered_df[filtered_df['카테고리'] == selected_category]
    if search_keyword.strip() != "":
        filtered_df = filtered_df[filtered_df['내역'].str.contains(search_keyword.strip(), case=False, na=False)]
else:
    filtered_df = df_ledger

st.sidebar.markdown("---")
st.sidebar.header("🧮 빠른 계산기")
calc_input = st.sidebar.text_input("수식 입력", placeholder="예: 15000*10%")
if calc_input.strip() != "":
    try:
        calc_result = eval(calc_input.replace('%', '/100'), {"__builtins__": None}, {})
        st.sidebar.success(f"**결과: {calc_result:,.2f}**".replace(".00", ""))
    except Exception:
        st.sidebar.error("⚠️ 올바른 수식이 아닙니다.")

st.sidebar.markdown("---")
if st.sidebar.button("🔓 로그아웃 하기", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# ==========================================
# 통계 대시보드
# ==========================================
st.markdown("---")
st.subheader("📊 요약 통계")

total_income = filtered_df[filtered_df['구분'] == '수입']['금액'].sum() if not filtered_df.empty else 0
total_expense = filtered_df[filtered_df['구분'] == '지출']['금액'].sum() if not filtered_df.empty else 0
net_income = total_income - total_expense

col1, col2, col3 = st.columns(3)
col1.metric("총 수입", f"{int(total_income):,} 원")
col2.metric("총 지출", f"{int(total_expense):,} 원")
col3.metric("순수익 (수입-지출)", f"{int(net_income):,} 원")

if not filtered_df.empty:
    expense_df = filtered_df[filtered_df['구분'] == '지출']
    if not expense_df.empty:
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            category_sum = expense_df.groupby('카테고리')['금액'].sum().reset_index()
            fig_pie = px.pie(category_sum, values='금액', names='카테고리', title='🍩 카테고리별 지출 비율', hole=0.3)
            fig_pie.update_traces(hovertemplate='<b>%{label}</b><br>금액: %{value:,.0f}원<br>비율: %{percent}')
            st.plotly_chart(fig_pie, use_container_width=True)
        with chart_col2:
            daily_sum = expense_df.groupby('날짜')['금액'].sum().reset_index()
            fig_bar = px.bar(daily_sum, x='날짜', y='금액', title='📉 일자별 지출 흐름')
            fig_bar.update_traces(hovertemplate='<b>날짜</b>: %{x}<br><b>금액</b>: %{y:,.0f}원')
            st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# 🎯 메인 액션 버튼 모음
# ==========================================
st.markdown("---")
btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)

btn_col1.button("🆕 거래내역 작성", on_click=toggle_tab, args=("new",), use_container_width=True, type="primary" if st.session_state.active_tab == "new" else "secondary")
btn_col2.button("📝 수정 / 삭제", on_click=toggle_tab, args=("edit",), use_container_width=True, type="primary" if st.session_state.active_tab == "edit" else "secondary")
btn_col3.button("📝 일일 메모장", on_click=toggle_tab, args=("memo",), use_container_width=True, type="primary" if st.session_state.active_tab == "memo" else "secondary")
btn_col4.button("📆 월별 달력 보기", on_click=toggle_tab, args=("calendar",), use_container_width=True, type="primary" if st.session_state.active_tab == "calendar" else "secondary")
btn_col5.button("📈 상세 통계 보기", on_click=toggle_tab, args=("detail_stats",), use_container_width=True, type="primary" if st.session_state.active_tab == "detail_stats" else "secondary")

st.markdown("<br>", unsafe_allow_html=True)

# --- 1. 새로운 거래 내역 작성 폼 ---
if st.session_state.active_tab == "new":
    with st.container(border=True): 
        st.markdown("#### ✍️ 새로운 거래 내역 추가")
        with st.form("input_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_date = st.date_input("날짜", datetime.date.today())
                new_type = st.selectbox("구분", ["지출", "수입"])
                existing_cats = list(df_ledger['카테고리'].unique()) if not df_ledger.empty else []
                sel_cat = st.selectbox("카테고리 (기존 목록)", existing_cats) if existing_cats else ""
                new_cat_input = st.text_input("새 카테고리 (※직접 입력시 여기에 작성)")
            with col2:
                existing_items = list(df_ledger['내역'].dropna().unique()) if not df_ledger.empty else []
                sel_item = st.selectbox("내역 (기존 목록에서 자동완성 검색)", ["(새로 작성)"] + existing_items)
                new_item_input = st.text_input("새 내역 (※위에서 '새로 작성' 선택 시)")
                new_unit_price = st.number_input("단가", min_value=0, step=1000)
                new_discount = st.number_input("할인 금액", min_value=0, step=100)
            with col3:
                new_quantity = st.number_input("수량", min_value=1, step=1)
                new_memo = st.text_input("메모")
            
            submitted = st.form_submit_button("저장하기", type="primary")
            if submitted:
                final_category = new_cat_input if new_cat_input.strip() != "" else sel_cat
                final_item = new_item_input if sel_item == "(새로 작성)" else sel_item
                if final_item.strip() == "":
                    st.warning("⚠️ '내역'을 선택하거나 입력해 주세요!")
                else:
                    new_amount = (new_unit_price * new_quantity) - new_discount
                    conn = psycopg2.connect(DB_URL)
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO ledger (date, type, category, item, unit_price, discount, quantity, amount, memo, user_email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_date.strftime("%Y-%m-%d"), new_type, final_category, final_item, new_unit_price, new_discount, new_quantity, new_amount, new_memo, st.session_state.user.email))
                    conn.commit()
                    conn.close()
                    st.success("✅ 성공적으로 저장되었습니다!")
                    load_data.clear()
                    st.rerun()
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬆️ 창 닫기", key="close_new"): toggle_tab("new"); st.rerun()

# --- 2. 기존 내역 수정 / 삭제 폼 ---
elif st.session_state.active_tab == "edit":
    with st.container(border=True):
        st.markdown("#### 📝 기존 내역 수정 / 삭제")
        if not filtered_df.empty:
            edit_options = filtered_df.apply(lambda x: f"[{x['번호']}] {x['날짜']} - {x['내역']} ({int(x['금액']):,}원)", axis=1).tolist()
            selected_edit_str = st.selectbox("수정 또는 삭제할 내역을 아래에서 선택하세요", edit_options)
            
            if selected_edit_str:
                target_id = int(selected_edit_str.split(']')[0][1:])
                target_data = df_ledger[df_ledger['번호'] == target_id].iloc[0]
                with st.form("edit_form"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        edit_date = st.date_input("수정할 날짜", target_data['날짜'])
                        edit_type = st.selectbox("구분", ["지출", "수입"], index=0 if target_data['구분'] == "지출" else 1)
                        existing_cats = list(df_ledger['카테고리'].unique())
                        cat_idx = existing_cats.index(target_data['카테고리']) if target_data['카테고리'] in existing_cats else 0
                        edit_cat = st.selectbox("카테고리", existing_cats, index=cat_idx)
                    with col2:
                        edit_item = st.text_input("내역", str(target_data['내역']))
                        edit_unit_price = st.number_input("단가", min_value=0, step=1000, value=int(target_data['단가']))
                        edit_discount = st.number_input("할인 금액", min_value=0, step=100, value=int(target_data['할인']))
                    with col3:
                        edit_quantity = st.number_input("수량", min_value=1, step=1, value=int(target_data['수량']))
                        memo_val = "" if pd.isna(target_data['메모']) else str(target_data['메모'])
                        edit_memo = st.text_input("메모", memo_val)
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1: btn_update = st.form_submit_button("🔄 수정 내용 저장")
                    with col_btn2: btn_delete = st.form_submit_button("❌ 이 내역 삭제")
                        
                    if btn_update:
                        new_amount = (edit_unit_price * edit_quantity) - edit_discount
                        conn = psycopg2.connect(DB_URL)
                        cur = conn.cursor()
                        cur.execute("UPDATE ledger SET date=%s, type=%s, category=%s, item=%s, unit_price=%s, discount=%s, quantity=%s, amount=%s, memo=%s WHERE id=%s", 
                                    (edit_date.strftime("%Y-%m-%d"), edit_type, edit_cat, edit_item, edit_unit_price, edit_discount, edit_quantity, new_amount, edit_memo, target_id))
                        conn.commit()
                        conn.close()
                        st.success("✅ 성공적으로 수정되었습니다!")
                        load_data.clear()
                        st.rerun()
                    if btn_delete:
                        conn = psycopg2.connect(DB_URL)
                        cur = conn.cursor()
                        cur.execute("DELETE FROM ledger WHERE id=%s", (target_id,))
                        conn.commit()
                        conn.close()
                        st.success("🗑️ 성공적으로 삭제되었습니다!")
                        load_data.clear()
                        st.rerun()
        else: st.info("조건에 맞는 거래 내역이 없어 수정/삭제할 수 없습니다.")
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬆️ 창 닫기", key="close_edit"): toggle_tab("edit"); st.rerun()

# --- 3. 일일 메모장 폼 ---
elif st.session_state.active_tab == "memo":
    with st.container(border=True):
        st.markdown("#### 📅 일일 메모장")
        memo_col1, memo_col2 = st.columns([1, 1.5])
        with memo_col1:
            st.markdown("**새 메모 작성 및 수정**")
            target_date = st.date_input("메모 날짜 선택", datetime.date.today(), key="memo_date")
            target_date_str = target_date.strftime("%Y-%m-%d")
            existing_memo_text = ""
            if not df_memos.empty:
                match_memo = df_memos[df_memos['date'] == target_date_str]
                if not match_memo.empty: existing_memo_text = match_memo.iloc[0]['memo']
            new_memo = st.text_area("메모 내용", value=existing_memo_text, height=100)
            if st.button("메모 저장하기", type="primary"):
                conn = psycopg2.connect(DB_URL)
                cur = conn.cursor()
                cur.execute("SELECT * FROM daily_memos WHERE date=%s", (target_date_str,))
                if cur.fetchone(): cur.execute("UPDATE daily_memos SET memo=%s WHERE date=%s", (new_memo, target_date_str))
                else: cur.execute("INSERT INTO daily_memos (date, memo) VALUES (%s, %s)", (target_date_str, new_memo))
                conn.commit()
                conn.close()
                st.success(f"{target_date_str} 메모가 저장되었습니다!")
                load_memo_data.clear() 
                st.rerun()
        with memo_col2:
            st.markdown(f"**[{start_date} ~ {end_date}] 기간의 메모 목록**")
            if not df_memos.empty:
                df_memos['date_obj'] = pd.to_datetime(df_memos['date']).dt.date
                filtered_memos = df_memos[(df_memos['date_obj'] >= start_date) & (df_memos['date_obj'] <= end_date)]
                if not filtered_memos.empty:
                    for _, row in filtered_memos.sort_values(by='date', ascending=False).iterrows():
                        st.info(f"**🗓️ {row['date']}** \n\n {row['memo']}")
                else: st.write("해당 기간에 작성된 메모가 없습니다.")
            else: st.write("저장된 일일 메모가 없습니다.")
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬆️ 창 닫기", key="close_memo"): toggle_tab("memo"); st.rerun()

# --- 4. 📆 인터랙티브 대한민국 달력 폼 ---
elif st.session_state.active_tab == "calendar":
    with st.container(border=True):
        st.markdown("#### 📆 월별 가계부 달력")
        cal_sel_col1, cal_sel_col2, _ = st.columns([1, 1, 3])
        
        cur_year = datetime.date.today().year
        cur_month = datetime.date.today().month
        sel_year = cal_sel_col1.selectbox("연도", range(cur_year - 5, cur_year + 5), index=5)
        sel_month = cal_sel_col2.selectbox("월", range(1, 13), index=cur_month - 1)
        
        kr_holidays = holidays.KR(years=sel_year)
        cal = calendar.Calendar(firstweekday=6) 
        month_days = cal.monthdatescalendar(sel_year, sel_month)
        
        header_cols = st.columns(7)
        day_names = ["일", "월", "화", "수", "목", "금", "토"]
        day_colors = ["#ff4b4b", "inherit", "inherit", "inherit", "inherit", "inherit", "#4b8bff"]
        for col, name, color in zip(header_cols, day_names, day_colors):
            col.markdown(f"<div style='text-align: center; color: {color}; border-bottom: 2px solid #ccc; padding-bottom: 5px; margin-bottom: 10px;'><b>{name}</b></div>", unsafe_allow_html=True)
        
        for week in month_days:
            cols = st.columns(7)
            for i, date_obj in enumerate(week):
                with cols[i]:
                    if date_obj.month == sel_month:
                        hol_name = kr_holidays.get(date_obj)
                        is_sun = (i == 0)
                        is_sat = (i == 6)
                        t_color = "#ff4b4b" if (is_sun or hol_name) else ("#4b8bff" if is_sat else "inherit")
                        
                        daily_exp = df_ledger[(df_ledger['날짜'] == date_obj) & (df_ledger['구분'] == '지출')]['금액'].sum() if not df_ledger.empty else 0
                        
                        with st.container(border=True):
                            st.markdown(f"<span class='cal-date' style='color: {t_color};'>{date_obj.day}</span>", unsafe_allow_html=True)
                            if hol_name: st.markdown(f"<div class='cal-holiday'>{hol_name}</div>", unsafe_allow_html=True)
                            else: st.markdown("<div style='height: 0.85em;'></div>", unsafe_allow_html=True)
                            
                            if daily_exp > 0: st.markdown(f"<div class='cal-expense'>-{int(daily_exp):,}</div>", unsafe_allow_html=True)
                            else: st.markdown("<div style='height: 1.5em;'></div>", unsafe_allow_html=True)
                                
                            if st.button("내역", key=f"cal_btn_{date_obj}", use_container_width=True):
                                st.session_state.selected_cal_date = date_obj
                                st.session_state.active_tab = "cal_detail"
                                st.rerun()
                    else: st.write("") 
                        
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬆️ 달력 닫기", key="close_cal"): toggle_tab("calendar"); st.rerun()

# --- 4-1. 달력 상세 내역 ---
elif st.session_state.active_tab == "cal_detail" and st.session_state.selected_cal_date:
    sel_date = st.session_state.selected_cal_date
    with st.container(border=True):
        st.markdown(f"### 🔎 {sel_date} 상세 내역")
        day_df = df_ledger[df_ledger['날짜'] == sel_date]
        if day_df.empty: st.info("해당 날짜에 기록된 거래 내역이 없습니다.")
        else:
            day_inc = day_df[day_df['구분'] == '수입']['금액'].sum()
            day_exp = day_df[day_df['구분'] == '지출']['금액'].sum()
            d_col1, d_col2 = st.columns(2)
            d_col1.metric("해당 일 수입", f"{int(day_inc):,} 원")
            d_col2.metric("해당 일 지출", f"{int(day_exp):,} 원")
            
            if day_exp > 0:
                day_expense_df = day_df[day_df['구분'] == '지출']
                fig_day_pie = px.pie(day_expense_df, values='금액', names='내역', title=f"{sel_date} 지출 품목 비율", hole=0.4)
                st.plotly_chart(fig_day_pie, use_container_width=True)
            
            st.dataframe(day_df.drop(columns=['날짜_dt', '연월', '월', '연도'], errors='ignore'), width='stretch')
            
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬅️ 달력으로 돌아가기", key="close_cal_detail"):
                st.session_state.active_tab = "calendar"
                st.rerun()

# --- 5. 📈 상세 통계 그래프 폼 ---
elif st.session_state.active_tab == "detail_stats":
    with st.container(border=True):
        st.markdown("#### 📈 상세 통계 분석 (품목별 추세)")
        expense_df = filtered_df[filtered_df['구분'] == '지출'] if not filtered_df.empty else pd.DataFrame()
        
        if expense_df.empty:
            st.info("해당 기간/조건에 지출 내역이 없어 통계를 표시할 수 없습니다.")
        else:
            st.markdown("##### 1️⃣ 특정 품목 연간 지출 추이 (1월~12월)")
            trend_col1, trend_col2 = st.columns([1, 2])
            with trend_col1:
                available_years = sorted(df_ledger['연도'].dropna().unique(), reverse=True)
                if not available_years: available_years = [datetime.date.today().year]
                selected_year = st.selectbox("조회할 연도", available_years)
            with trend_col2:
                item_list = expense_df['내역'].dropna().unique()
                selected_trend_item = st.selectbox("추세를 확인할 품목을 선택하세요", item_list)
            
            months_str = [f"{m:02d}월" for m in range(1, 13)]
            
            if selected_trend_item:
                base_df = pd.DataFrame({'월': months_str})
                item_df = expense_df[(expense_df['내역'] == selected_trend_item) & (expense_df['연도'] == selected_year)]
                trend_df = item_df.groupby('월')['금액'].sum().reset_index()
                
                merged_df = pd.merge(base_df, trend_df, on='월', how='left').fillna(0)
                merged_df['품목'] = selected_trend_item 
                
                fig_trend1 = px.line(merged_df, x='월', y='금액', markers=True, 
                                     title=f"{selected_year}년 '{selected_trend_item}' 지출 추이")
                fig_trend1.update_traces(hovertemplate='<b>%{customdata[0]}</b><br><b>기간</b>: %{x}<br><b>금액</b>: %{y:,.0f}원',
                                         customdata=merged_df[['품목']])
                fig_trend1.update_layout(xaxis_title="월", yaxis_title="금액 (원)", yaxis_rangemode="tozero")
                st.plotly_chart(fig_trend1, use_container_width=True)

            st.markdown("---")
            
            st.markdown(f"##### 2️⃣ {selected_year}년 비용 상위 10개 품목의 월별 추세")
            year_expense_df = expense_df[expense_df['연도'] == selected_year]
            
            if not year_expense_df.empty:
                top_10_items = year_expense_df.groupby('내역')['금액'].sum().nlargest(10).index
                
                if not top_10_items.empty:
                    top10_df = year_expense_df[year_expense_df['내역'].isin(top_10_items)]
                    top10_trend = top10_df.groupby(['월', '내역'])['금액'].sum().reset_index()
                    
                    base_top10_data = []
                    for m in months_str:
                        for item in top_10_items:
                            base_top10_data.append({'월': m, '내역': item})
                    base_top10_df = pd.DataFrame(base_top10_data)
                    
                    merged_top10_df = pd.merge(base_top10_df, top10_trend, on=['월', '내역'], how='left').fillna(0)
                    
                    fig_trend2 = px.line(merged_top10_df, x='월', y='금액', color='내역', markers=True,
                                         title=f"{selected_year}년 비용 상위 10개 품목 지출 추이")
                    fig_trend2.update_traces(hovertemplate='<b>품목</b>: %{customdata[0]}<br><b>월</b>: %{x}<br><b>금액</b>: %{y:,.0f}원',
                                             customdata=merged_top10_df[['내역']])
                    fig_trend2.update_layout(xaxis_title="월", yaxis_title="금액 (원)", legend_title="상위 품목", yaxis_rangemode="tozero")
                    st.plotly_chart(fig_trend2, use_container_width=True)
            else:
                st.info(f"{selected_year}년에 지출 내역이 없습니다.")
                
        col_empty, col_close = st.columns([6, 1])
        with col_close:
            if st.button("⬆️ 창 닫기", key="close_stats"): toggle_tab("detail_stats"); st.rerun()

# ==========================================
# 화면 아래쪽: 전체 표 형태로 출력하기
# ==========================================
st.markdown("---")
st.subheader(f"📋 전체 거래 내역 (최근 기록순)")

# --- [새로 추가할 출력/다운로드 버튼 코드 시작] ---
import io
import pandas as pd
import streamlit.components.v1 as components

# 버튼을 나란히 두기 위해 화면을 반으로 나눔
col_btn1, col_btn2 = st.columns(2) 

with col_btn1:
    # 1. 엑셀 다운로드 버튼
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # 🚨 주의: 만약 본인 코드에서 표를 그릴 때 쓰는 데이터 이름이 'df'라면 아래 filtered_df를 df로 바꿔주세요!
        filtered_df.to_excel(writer, index=False, sheet_name='가계부내역') 
    
    st.download_button(
        label="📥 엑셀(Excel)로 다운로드",
        data=buffer.getvalue(),
        file_name="smart_ledger_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col_btn2:
    # 2. 화면 인쇄 / PDF 저장 버튼
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
# --- [새로 추가할 출력/다운로드 버튼 코드 끝] ---
if not filtered_df.empty:
    display_df = filtered_df.drop(columns=['날짜_dt', '연월', '월', '연도'], errors='ignore')
    search_text = f" | **검색어:** '{search_keyword}'" if search_keyword.strip() != "" else ""
    st.write(f"**조회 기간:** {start_date} ~ {end_date} | **카테고리:** {selected_category}{search_text}")
    styled_df = display_df.style.set_properties(**{'text-align': 'center'})
    st.dataframe(styled_df, width='stretch')
else:
    st.info("데이터가 없습니다. 새로운 거래 내역을 작성해 보세요!")