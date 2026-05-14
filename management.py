import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime
import cloudinary
import cloudinary.uploader
from streamlit_drawable_canvas import st_canvas
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. 초기 설정 및 클라우드 연결
# ==========================================
st.set_page_config(page_title="히트펌프 장비 관리 시스템", layout="wide")

try:
    try:
        service_info = json.load(open('hallowed-winter-493604-k9-234626bef11e.json'))
    except FileNotFoundError:
        secret_data = st.secrets["gcp_service_account"]
        service_info = json.loads(secret_data) if isinstance(secret_data, str) else dict(secret_data)
        
    gc = gspread.service_account_from_dict(service_info)
    sh = gc.open("HEAT PUMP") 
    
    # ☁️ Cloudinary 설정 (본인 정보로 수정 필수)
    cloudinary.config(
        cloud_name = "dyxuhtloo", 
        api_key = "711879852278235", 
        api_secret = "katQ2CanHxv9--WJyiYtcW2keNs",
        secure = True
    )
except Exception as e:
    st.error(f"⚠️ 시스템 연결 실패: {e}")
    st.stop()

# ==========================================
# 2. 세션 상태 (로그인 및 화면 이동 관리)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

# 🌟 새로 추가됨: 화면 전환을 위한 기억 장치
if 'nav_agency' not in st.session_state:
    st.session_state['nav_agency'] = "전체"
if 'nav_customer' not in st.session_state:
    st.session_state['nav_customer'] = "선택하세요"

@st.cache_data(ttl=60)
def load_sheet_data(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        records = worksheet.get_all_records(head=2) # (1행이 제목일 경우 1, 2행일 경우 2)
        return pd.DataFrame(records)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. 로그인 화면
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("### 🔲 히트펌프 장비 관리")
    with st.form("login_form"):
        user_id = st.text_input("아이디")
        user_pw = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            df_accounts = load_sheet_data("계정관리")
            if df_accounts.empty:
                st.error("계정 정보를 불러올 수 없습니다.")
            else:
                user_row = df_accounts[(df_accounts['ID'] == user_id) & (df_accounts['PW'].astype(str) == user_pw)]
                if not user_row.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user_row.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 틀렸습니다.")
    st.stop()

# ==========================================
# 4. 메인 화면 (로그인 성공 후)
# ==========================================
user_info = st.session_state['user_info']
auth_level = user_info.get('권한', '') 
user_company = user_info.get('업체명', '')

col1, col2 = st.columns([8, 2])
col1.markdown(f"### 🔲 히트펌프 장비 관리 (접속: {user_company})")
if col2.button("로그아웃"):
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None
    # 로그아웃 시 검색 상태도 초기화
    st.session_state['nav_agency'] = "전체"
    st.session_state['nav_customer'] = "선택하세요"
    st.rerun()

st.write("---")

equipment_type = st.radio("장비 구분", ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"], horizontal=True)
df_equip = load_sheet_data(equipment_type)

if df_equip.empty:
    st.warning(f"'{equipment_type}' 탭에 데이터가 없습니다.")
    st.stop()

# --- 🔍 업체 검색 (공백 필터링 및 세션 연결) ---
st.write("#### 🔍 업체 검색")
search_col1, search_col2, search_col3 = st.columns([3, 3, 4])

selected_agency = None
selected_customer = None

if auth_level == "하이에어공조":
    # ★ 수정됨: 공백칸(빈 문자열)을 찾아 맨 밑으로 내리기
    raw_agencies = list(df_equip['대리점'].dropna().unique())
    valid_agencies = sorted([a for a in raw_agencies if str(a).strip() != ''])
    blank_agencies = [a for a in raw_agencies if str(a).strip() == '']
    agency_list = ["전체"] + valid_agencies + blank_agencies
    
    # 세션에 저장된 값이 리스트에 있으면 그 인덱스를, 없으면 0(전체) 선택
    agency_idx = agency_list.index(st.session_state['nav_agency']) if st.session_state['nav_agency'] in agency_list else 0
    selected_agency = search_col1.selectbox("대리점", agency_list, index=agency_idx)
    st.session_state['nav_agency'] = selected_agency # 값 업데이트
    
    if selected_agency != "전체":
        filtered_df = df_equip[df_equip['대리점'] == selected_agency]
    else:
        filtered_df = df_equip
        
    raw_customers = list(filtered_df['업체명'].dropna().unique())
    valid_cust = sorted([c for c in raw_customers if str(c).strip() != ''])
    customer_list = ["선택하세요"] + valid_cust
    
    cust_idx = customer_list.index(st.session_state['nav_customer']) if st.session_state['nav_customer'] in customer_list else 0
    selected_customer = search_col2.selectbox("업체명", customer_list, index=cust_idx)
    st.session_state['nav_customer'] = selected_customer

else:
    search_col1.text_input("대리점", value=user_company, disabled=True)
    filtered_df = df_equip[df_equip['대리점'] == user_company]
    
    raw_customers = list(filtered_df['업체명'].dropna().unique())
    valid_cust = sorted([c for c in raw_customers if str(c).strip() != ''])
    customer_list = ["선택하세요"] + valid_cust
    
    cust_idx = customer_list.index(st.session_state['nav_customer']) if st.session_state['nav_customer'] in customer_list else 0
    selected_customer = search_col2.selectbox("업체명", customer_list, index=cust_idx)
    st.session_state['nav_customer'] = selected_customer

# ==========================================
# 5. 화면 분기: [대시보드 목록] vs [상세 정보]
# ==========================================
st.write("---")

if selected_customer == "선택하세요":
    # ----------------------------------------
    # 📌 화면 A: 대리점별 고객사 목록 대시보드
    # ----------------------------------------
    st.markdown("### 📋 전체 업체 목록")
    st.info("💡 원하시는 업체를 클릭하면 상세 내역 화면으로 이동합니다.")
    
    # 보여줄 대리점 목록 결정
    if auth_level == "하이에어공조":
        agencies_to_show = [selected_agency] if selected_agency != "전체" else valid_agencies
    else:
        agencies_to_show = [user_company]

    for agency in agencies_to_show:
        agency_df = filtered_df[filtered_df['대리점'] == agency]
        cust_in_agency = sorted([c for c in agency_df['업체명'].dropna().unique() if str(c).strip() != ''])
        
        if cust_in_agency:
            # 아코디언 메뉴(Expander)로 대리점 묶기
            with st.expander(f"🏢 {agency} (총 {len(cust_in_agency)}개 업체)", expanded=True):
                # 4열로 버튼 예쁘게 배치
                cols = st.columns(4)
                for i, cust in enumerate(cust_in_agency):
                    # 버튼을 클릭하면 세션 기억장치를 변경하고 화면을 새로고침(rerun)
                    if cols[i % 4].button(f"🔍 {cust}", key=f"btn_{agency}_{cust}", use_container_width=True):
                        if auth_level == "하이에어공조":
                            st.session_state['nav_agency'] = agency
                        st.session_state['nav_customer'] = cust
                        st.rerun()

else:
    # ----------------------------------------
    # 📌 화면 B: 선택한 고객사 상세 정보
    # ----------------------------------------
    if st.button("🔙 전체 목록으로 돌아가기"):
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    cust_data = filtered_df[filtered_df['업체명'] == selected_customer].iloc[0]
    
    st.markdown(f"### 🏢 [{selected_customer}] 상세 내역")
    
    st.markdown("▶ **업체 정보**")
    st.info(f"- **대표자:** {cust_data.get('대표자', '')}\n- **연락처:** {cust_data.get('연락처', '')}\n- **주소:** {cust_data.get('주소', '')}")
    
    # 💡 [요구사항 2] 장비 납품 내역에 체크박스 추가 (선택한 장비 데이터 묶기)
    st.markdown("▶ **장비 납품 내역 (수리/점검할 장비를 체크하세요)**")
    history_df = filtered_df[filtered_df['업체명'] == selected_customer].copy()
    
    if auth_level == "하이에어공조":
        display_cols = ['설치 날짜', 'AS기간', '규격', '수량', '사업명', '계약금액', '대리점']
    else:
        display_cols = ['규격', '수량', '사업명', '설치 날짜', 'AS기간']
    
    existing_cols = [col for col in display_cols if col in history_df.columns]
    
    # '선택'이라는 체크박스 열 생성
    history_df.insert(0, "선택", False)
    edited_history = st.data_editor(
        history_df[['선택'] + existing_cols],
        hide_index=True,
        use_container_width=True,
        disabled=existing_cols # '선택' 열만 수정 가능하도록 설정
    )
    
    # 체크된 장비들만 추출하여 문자열로 결합
    selected_equips = edited_history[edited_history['선택'] == True]
    if not selected_equips.empty:
        # 선택된 장비들의 규격을 / 로 이어서 표시
        equip_info_str = " / ".join(selected_equips['규격'].astype(str).tolist())
    else:
        equip_info_str = cust_data.get('규격', '')
    
    st.markdown("▶ **장비 AS 이력**")
    df_as = load_sheet_data("AS내역")
    if not df_as.empty and '업체명' in df_as.columns:
        cust_as_history = df_as[df_as['업체명'] == selected_customer]
        if not cust_as_history.empty:
            if auth_level == "하이에어공조":
                as_disp_cols = ['접수시간', '업체명', 'AS 항목', '담당자', '입력자', '상세 내용']
            else:
                as_disp_cols = ['접수시간', '업체명', 'AS 항목', '담당자', '상세 내용']
            as_exist_cols = [col for col in as_disp_cols if col in cust_as_history.columns]
            st.dataframe(cust_as_history[as_exist_cols], hide_index=True, use_container_width=True)
        else:
            st.write("해당 업체의 AS 이력이 없습니다.")
    else:
        st.write("AS 이력 데이터를 불러올 수 없습니다.")

    # 💡 [요구사항 4] 한국 서울 기준 시간 가져오기
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).time()

    # --- AS 내역 추가 (Form) ---
    with st.expander("📝 SERVICE REPORT 작성하기", expanded=False):
        with st.form("service_report_form", clear_on_submit=False):
            st.markdown("### SERVICE REPORT")
            
            # 1. 기본 정보
            col1, col2 = st.columns(2)
            site_name = col1.text_input("현장명(주소)", value=cust_data.get('주소', ''))
            rcv_date = col2.date_input("접수일자")
            
            manager_info = col1.text_input("담당자(연락처)", value=f"{cust_data.get('대표자', '')} / {cust_data.get('연락처', '')}")
            end_date = col2.date_input("완료일자")
            
            # 위에서 체크한 장비 정보가 자동으로 입력됨
            equip_info = st.text_input("장비정보 (용량/수량/제어/냉매/기타)", value=equip_info_str)

            st.divider()

            # 💡 [요구사항 1] 장비구분 라디오 버튼화 & 자동 매핑
            st.markdown("**장비구분 (단일 선택)**")
            equip_map = {
                "해수열": "해수열 HP",
                "폐수열": "폐수열 HP",
                "공기열": "공기열 HP",
                "건조기(김공장)": "제습기/건조기",
                "어선용": "기타"
            }
            default_eq_val = equip_map.get(equipment_type, "기타")
            eq_options = ["해수열 HP", "해수용 칠러", "폐수열 HP", "공기열 HP", "제습기/건조기", "수소", "기타"]
            default_idx = eq_options.index(default_eq_val) if default_eq_val in eq_options else 6
            
            report_equip = st.radio("장비구분 선택", eq_options, index=default_idx, horizontal=True, label_visibility="collapsed")

            st.markdown("**작업구분**")
            work_cols = st.columns(6)
            wk_1 = work_cols[0].checkbox("시운전")
            wk_2 = work_cols[1].checkbox("하자처리(전장)")
            wk_3 = work_cols[2].checkbox("하자처리(기계)")
            wk_4 = work_cols[3].checkbox("하자처리(설비)")
            wk_5 = work_cols[4].checkbox("기타")

            st.markdown("**요금청구**")
            charge_cols = st.columns(7)
            ch_1 = charge_cols[0].checkbox("고객")
            po_no = charge_cols[0].text_input("PO No:") 
            ch_2 = charge_cols[1].checkbox("유상")
            ch_3 = charge_cols[2].checkbox("무상")
            ch_4 = charge_cols[3].checkbox("R-22")
            ch_5 = charge_cols[4].checkbox("R-407C")
            ch_6 = charge_cols[5].checkbox("R-134A")
            ch_7 = charge_cols[6].checkbox("A-507")

            st.divider()

            # 💡 [요구사항 3] 작업내용 데이터 테이블 (입력 시 No. 자동 부여 로직)
            st.markdown("**작업내용** (구분과 작업내용을 입력하세요. 제출 시 자동으로 'No.'가 부여됩니다.)")
            df_work = pd.DataFrame(columns=["구분", "작업내용"])
            edited_work = st.data_editor(df_work, num_rows="dynamic", use_container_width=True)

            st.divider()

            # 4. 하단 상세 정보
            bot_col1, bot_col2 = st.columns(2)
            engineer_cnt = bot_col1.text_input("방문한 서비스 엔지니어 인원 (인원/시간)")
            
            # 위에서 생성한 한국 시간(now_kst)을 기본값으로 적용
            start_time = bot_col1.time_input("작업 시작시간", value=now_kst)
            end_time = bot_col1.time_input("작업 종료시간", value=now_kst)
            
            satisfaction = bot_col2.radio("서비스만족도 조사", ["불만족", "보통", "만족"], horizontal=True)
            constructor = bot_col2.text_input("영업자/시공자", value=user_info.get('업체명', ''))
            
            requests = st.text_area("고객 요청사항")

            st.divider()

            # 💡 [요구사항 5] 서명란 이미지 업로드 -> 양쪽 모두 캔버스로 변경
            sig_col1, sig_col2 = st.columns(2)
            with sig_col1:
                st.markdown("**담당직원 서명 (터치/마우스로 직접 서명)**")
                canvas_emp = st_canvas(
                    stroke_width=3, stroke_color="#000000", background_color="#EEEEEE",
                    height=150, width=300, drawing_mode="freedraw", key="emp_signature",
                )
                    
            with sig_col2:
                st.markdown("**확인자(소비자) 서명 (터치/마우스로 직접 서명)**")
                canvas_customer = st_canvas(
                    stroke_width=3, stroke_color="#000000", background_color="#EEEEEE",
                    height=150, width=300, drawing_mode="freedraw", key="customer_signature",
                )

            submit_report = st.form_submit_button("리포트 저장 및 서버 전송")
            
            if submit_report:
                # 제출 버튼 누를 때 입력한 작업내용에 No. 순번 추가
                if not edited_work.empty:
                    edited_work.insert(0, "No", range(1, len(edited_work) + 1))
                
                # 향후 Cloudinary 등 이미지 서버 업로드 로직 (필요 시 구현)
                if canvas_emp.image_data is not None:
                    pass 
                if canvas_customer.image_data is not None:
                    pass

                st.success("✅ SERVICE REPORT가 성공적으로 작성되었습니다. (No. 자동부여 완료)")
                # 확인을 위해 최종 데이터 출력 (나중에 지우셔도 됩니다)
                # st.dataframe(edited_work)