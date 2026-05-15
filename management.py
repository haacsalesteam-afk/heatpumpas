import streamlit as st
import gspread
import pandas as pd
import json
import cloudinary
import cloudinary.uploader
from streamlit_drawable_canvas import st_canvas
import io
from datetime import datetime, timezone, timedelta
import os
from fpdf import FPDF

# ==========================================
# 🌟 변경된 부분: PDF 양식 완벽 구현 (A4 사이즈 좌우 대칭 여백, Remark 표 내부 포함)
# ==========================================
def create_service_report_pdf(data, work_details, customer_sig_path=None):
    # A4 사이즈 명시
    pdf = FPDF(format='A4')
    # 자동 페이지 넘김을 비활성화하여 1장에 무조건 맞춰지도록 설정
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    
    # 폰트 로드 (GitHub 업로드된 폰트 4종 중 하나 자동 선택)
    font_files = [
        "CJNXLA0W_D7IILTV5NZ2CSJIEBQ.TTF", "JJZOJE3V0Y1GRVTQZAC2DOFDIS8.TTF", 
        "QVZDLSH8A7MXUCRR2UZEXE8SZKY.TTF", "NanumGothic.ttf"
    ]
    base_font = "helvetica"
    for f in font_files:
        if os.path.exists(f):
            pdf.add_font("Nanum", "", f)
            base_font = "Nanum"
            break
            
    # --- 1. 헤더 (전체 가로폭 190, X: 10 ~ 200) ---
    pdf.set_font(base_font, "", 16)
    pdf.cell(0, 8, "하 이 에 어 공 조 (주)", ln=True, align='C')
    pdf.set_font(base_font, "", 10)
    pdf.cell(0, 5, "경상남도 김해시 진례면 고모로 324번길 204", ln=True, align='C')
    pdf.cell(0, 5, "Tel) 055-340-5072 Fax) 055-346-3884 E-Mail) hiairas@hiairkorea.co.kr", ln=True, align='C')
    pdf.line(10, 28, 200, 28)
    
    # --- 2. 제목 ---
    pdf.set_xy(10, 32)
    pdf.set_font(base_font, "", 22) 
    pdf.cell(0, 10, "SERVICE REPORT", ln=True, align='C')
    pdf.line(75, 41, 135, 41) # 제목 밑줄 (중앙 정렬 유지)
    
    # --- 3. 기본 정보 ---
    pdf.set_font(base_font, "", 10)
    
    def draw_field(title, value, x1, y, w1, w2):
        pdf.set_xy(x1, y)
        pdf.cell(w1, 6, title)
        pdf.cell(w2, 6, str(value))
        pdf.line(x1+w1, y+5, x1+w1+w2, y+5) # 밑줄
        
    draw_field("현장명(주소) :", data.get('site_name', ''), 10, 45, 25, 95)
    draw_field("접수일자 :", data.get('rcv_date', ''), 140, 45, 20, 40)
    draw_field("담당자(연락처) :", data.get('manager_info', ''), 10, 52, 28, 92)
    draw_field("완료일자 :", data.get('end_date', ''), 140, 52, 20, 40)
    draw_field("장비정보 :", data.get('equip_info', ''), 10, 59, 20, 110)
    pdf.set_xy(145, 59)
    pdf.cell(55, 6, "(용량/수량/제어/냉매/기타)", align='R')

    # --- 4. 체크박스 영역 ---
    def draw_chk(x, y, label, is_checked):
        pdf.rect(x, y, 3, 3)
        pdf.set_xy(x+4, y-1.5)
        pdf.cell(20, 6, label)
        if is_checked:
            pdf.set_xy(x, y-1.5)
            pdf.cell(3, 6, "v", align='C')

    # 장비구분
    y_chk = 67
    pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "장비구분 :")
    eq_list = ["해수열 HP", "해수용 칠러", "폐수열 HP", "공기열 HP", "제습기/건조기", "수소"]
    x_pos = [32, 55, 82, 105, 130, 165]
    for i, eq in enumerate(eq_list):
        draw_chk(x_pos[i], y_chk, eq, data.get('report_equip') == eq)

    # 작업구분
    y_chk = 74
    pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "작업구분 :")
    wk_list = ["시운전", "하자처리(전장)", "기계", "설비", "기타"]
    x_pos = [32, 55, 90, 110, 130]
    for i, wk in enumerate(wk_list):
        draw_chk(x_pos[i], y_chk, wk, wk in data.get('work_checked', []))

    # 요금청구 및 냉매 (공간 분배 최적화)
    y_chk = 81
    pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "요금청구 :")
    is_cust = "고객" in data.get('charge_type', '')
    draw_chk(32, y_chk, f"고객(PO No: {data.get('po_no','') if is_cust else '                '})", is_cust)
    draw_chk(90, y_chk, "유상", data.get('charge_type') == "유상")
    draw_chk(110, y_chk, "무상", data.get('charge_type') == "무상")
    
    ref_list = ["R-22", "R-407C", "R-134A", "A-507"]
    x_pos = [128, 145, 165, 185]
    for i, ref in enumerate(ref_list):
        draw_chk(x_pos[i], y_chk, ref, data.get('ref_type') == ref)

    # --- 5. 작업내용 테이블 ---
    y_tbl = 88
    pdf.set_xy(10, y_tbl)
    # 총 너비 190 (15 + 25 + 150) -> 우측 여백 10으로 딱 맞아떨어짐
    pdf.cell(15, 6, "No", border=1, align='C')
    pdf.cell(25, 6, "구분", border=1, align='C')
    pdf.cell(150, 6, "작업내용", border=1, align='C')
    
    # 뼈대(테두리) 그리기 (Y: 94 ~ 205 로 축소하여 하단 여백 및 Remark 공간 완벽 확보)
    tbl_bottom = 205
    pdf.rect(10, 94, 15, tbl_bottom - 94)
    pdf.rect(25, 94, 25, tbl_bottom - 94)
    pdf.rect(50, 94, 150, tbl_bottom - 94)
    
    # 내용 채우기
    y_curr = 95
    for index, row in work_details.iterrows():
        if y_curr > tbl_bottom - 10:
            break # 데이터가 길어 표를 벗어나면 방지
        pdf.set_xy(10, y_curr)
        pdf.cell(15, 6, str(row['No']), align='C')
        pdf.cell(25, 6, str(row.get('구분','')), align='C')
        pdf.cell(150, 6, " " + str(row.get('작업내용','')))
        y_curr += 6

    # --- 6. 하단 정보 테이블 ---
    y_ft = tbl_bottom # 205 위치에서 시작
    
    # [1행] 인원/시간 영역 & 만족도 조사
    pdf.rect(10, y_ft, 40, 15)
    pdf.set_xy(10, y_ft+4.5); pdf.cell(40, 6, "(인원 / 시간)", align='C')
    
    pdf.rect(50, y_ft, 90, 15)
    pdf.set_xy(51, y_ft+1); pdf.cell(30, 6, "방문한 서비스 엔지니어 인원 :")
    pdf.set_xy(100, y_ft+1); pdf.cell(40, 6, str(data.get('engineer_cnt','')))
    
    pdf.set_xy(51, y_ft+8); pdf.cell(20, 6, "작업 시작시간 :")
    pdf.set_xy(75, y_ft+8); pdf.cell(20, 6, str(data.get('start_time','')))
    pdf.set_xy(100, y_ft+8); pdf.cell(20, 6, "종료시간 :")
    pdf.set_xy(120, y_ft+8); pdf.cell(20, 6, str(data.get('end_time','')))

    # 만족도 영역
    pdf.rect(140, y_ft, 60, 15)
    pdf.set_xy(140, y_ft); pdf.cell(60, 6, "서비스만족도 조사", align='C')
    pdf.line(140, y_ft+6, 200, y_ft+6)
    pdf.line(160, y_ft+6, 160, y_ft+15)
    pdf.line(180, y_ft+6, 180, y_ft+15)
    pdf.set_xy(140, y_ft+6); pdf.cell(20, 5, "불만족", align='C')
    pdf.set_xy(160, y_ft+6); pdf.cell(20, 5, "보통", align='C')
    pdf.set_xy(180, y_ft+6); pdf.cell(20, 5, "만족", align='C')
    
    sat = data.get('satisfaction', '')
    draw_chk(148, y_ft+11, "", sat=="불만족")
    draw_chk(168, y_ft+11, "", sat=="보통")
    draw_chk(188, y_ft+11, "", sat=="만족")

    # [2행] 영업자 / 시공자
    pdf.rect(10, y_ft+15, 40, 10)
    pdf.set_xy(10, y_ft+17); pdf.cell(40, 6, "영업자/시공자", align='C')
    pdf.rect(50, y_ft+15, 150, 10)
    pdf.set_xy(50, y_ft+17); pdf.cell(150, 6, str(data.get('constructor','')), align='C')
    
    # [3행] 고객 요청사항
    pdf.rect(10, y_ft+25, 40, 10)
    pdf.set_xy(10, y_ft+27); pdf.cell(40, 6, "고객 요청사항", align='C')
    pdf.rect(50, y_ft+25, 150, 10)
    pdf.set_xy(51, y_ft+27); pdf.cell(148, 6, str(data.get('requests','')))

    # [4행] 서명란
    pdf.rect(10, y_ft+35, 40, 15)
    pdf.set_xy(10, y_ft+39.5); pdf.cell(40, 6, "담당직원 :", align='C')
    pdf.rect(50, y_ft+35, 150, 15)
    
    pdf.set_xy(65, y_ft+42); pdf.cell(30, 6, str(data.get('emp_name','')), align='C')
    pdf.set_xy(95, y_ft+42); pdf.cell(10, 6, "(서명)")
    pdf.line(55, y_ft+48, 115, y_ft+48)
    
    pdf.set_xy(125, y_ft+42); pdf.cell(30, 6, "확인자(소비자) :", align='R')
    if customer_sig_path:
        pdf.image(customer_sig_path, x=165, y=y_ft+36, w=25) # 서명 이미지
    pdf.set_xy(185, y_ft+42); pdf.cell(10, 6, "(서명)")
    pdf.line(125, y_ft+48, 195, y_ft+48)

    # [5행] ※ Remark ※ (표 안으로 편입)
    pdf.rect(10, y_ft+50, 40, 15)
    pdf.set_font(base_font, "", 12)
    pdf.set_xy(10, y_ft+54.5); pdf.cell(40, 6, "※ Remark ※", align='C')
    
    pdf.rect(50, y_ft+50, 150, 15)
    pdf.set_font(base_font, "", 9)
    pdf.set_xy(50, y_ft+51); pdf.cell(150, 4.5, "Spare Parts Sales & Service Team", align='C')
    pdf.set_xy(50, y_ft+55.5); pdf.cell(150, 4.5, "Spare direct call : +82-55-340-5182  /  E-mail : spare@hiairkorea.co.kr", align='C')
    pdf.set_xy(50, y_ft+60); pdf.cell(150, 4.5, "Service direct call : +82-55-340-5072  /  E-mail : hiairas@hiairkorea.co.kr", align='C')

    return bytes(pdf.output())

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
        cloud_name = "ddwd7fy4g", 
        api_key = "549425249691295", 
        api_secret = "WH7o8t-Em-TyRUJZXCTNlqeCG6U",
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
    
    # --- 장비 납품 내역 (요약본) ---
    st.markdown("▶ **장비 납품 내역 (요약)**")
    history_df = filtered_df[filtered_df['업체명'] == selected_customer].copy()
    
    if auth_level == "하이에어공조":
        display_cols = ['설치 날짜', 'AS기간', '규격', '수량', '사업명', '계약금액', '대리점']
    else:
        display_cols = ['규격', '수량', '사업명', '설치 날짜', 'AS기간']
    
    existing_cols = [col for col in display_cols if col in history_df.columns]
    st.dataframe(history_df[existing_cols], hide_index=True, use_container_width=True)
    
    # --- 장비 납품 내역 (1대씩 상세 보기 및 수리 장비 선택) ---
    st.markdown("▶ **수리 대상 장비 선택 (선택 시 해당 장비의 AS 이력이 아래에 표시됩니다)**")
    
    # 수량을 1대씩 쪼개어 새로운 데이터프레임 생성
    detailed_rows = []
    for _, row in history_df.iterrows():
        try:
            qty = int(row.get('수량', 1))
        except:
            qty = 1
        
        for i in range(max(1, qty)):
            new_row = row.copy()
            new_row['수량'] = 1  # 수량을 1로 통일
            detailed_rows.append(new_row)
            
    detailed_df = pd.DataFrame(detailed_rows)
    detailed_df.insert(0, "선택", False) # 체크박스 열 추가
    
    with st.expander("🔍 여기를 눌러 개별 장비를 확인하고 수리할 장비를 체크하세요", expanded=False):
        edited_history = st.data_editor(
            detailed_df[['선택'] + existing_cols],
            hide_index=True,
            use_container_width=True,
            disabled=existing_cols # '선택' 열만 수정 가능하도록 설정
        )
    
    selected_equips = edited_history[edited_history['선택'] == True]
    
    # 선택된 장비들의 규격을 결합 (SERVICE REPORT 반영용)
    if not selected_equips.empty:
        equip_info_str = " / ".join(selected_equips['규격'].astype(str).unique().tolist())
    else:
        equip_info_str = ""

    # --- 장비 AS 이력 ---
    st.markdown("▶ **장비 AS 이력**")
    df_as = load_sheet_data("AS내역")
    if not df_as.empty and '업체명' in df_as.columns:
        cust_as_history = df_as[df_as['업체명'] == selected_customer]
        
        if not cust_as_history.empty:
            # 장비를 선택한 경우, 선택한 장비(규격) 키워드가 포함된 AS 이력만 필터링
            if not selected_equips.empty:
                selected_keywords = selected_equips['규격'].astype(str).unique().tolist()
                # 각 행의 텍스트 데이터 중 선택된 장비 규격이 하나라도 포함되어 있는지 검사
                mask = cust_as_history.astype(str).apply(lambda x: any(kw in x.to_string() for kw in selected_keywords), axis=1)
                display_as_history = cust_as_history[mask]
                st.info(f"선택한 장비({equip_info_str})와 관련된 AS 이력만 표시 중입니다.")
            else:
                display_as_history = cust_as_history
                
            if auth_level == "하이에어공조":
                as_disp_cols = ['접수시간', '업체명', 'AS 항목', '담당자', '입력자', '상세 내용']
            else:
                as_disp_cols = ['접수시간', '업체명', 'AS 항목', '담당자', '상세 내용']
            
            as_exist_cols = [col for col in as_disp_cols if col in display_as_history.columns]
            
            if not display_as_history.empty:
                st.dataframe(display_as_history[as_exist_cols], hide_index=True, use_container_width=True)
            else:
                st.write("선택한 장비에 대한 AS 이력이 없습니다.")
        else:
            st.write("해당 업체의 전체 AS 이력이 없습니다.")
    else:
        st.write("AS 이력 데이터를 불러올 수 없습니다.")

    # 한국 시간 설정
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).time()

# --- AS 내역 추가 (Form) ---
    with st.expander("📝 SERVICE REPORT 작성하기 (PDF 저장)", expanded=True):
        with st.form("service_report_form", clear_on_submit=False):
            st.markdown("### SERVICE REPORT")
            
            # 1. 기본 정보
            col1, col2 = st.columns(2)
            site_name = col1.text_input("현장명(주소)", value=cust_data.get('주소', ''))
            rcv_date = col2.date_input("접수일자")
            
            manager_info = col1.text_input("담당자(연락처)", value=f"{cust_data.get('대표자', '')} / {cust_data.get('연락처', '')}")
            end_date = col2.date_input("완료일자")
            
            equip_info = st.text_input("장비정보 (용량/수량/제어/냉매/기타)", value=equip_info_str)

            st.divider()

            # 2. 체크시트
            st.markdown("**장비구분 (단일 선택)**")
            equip_map = {
                "해수열": "해수열 HP", "폐수열": "폐수열 HP", "공기열": "공기열 HP",
                "건조기(김공장)": "제습기/건조기", "어선용": "기타"
            }
            default_eq_val = equip_map.get(equipment_type, "기타")
            eq_options = ["해수열 HP", "해수용 칠러", "폐수열 HP", "공기열 HP", "제습기/건조기", "수소", "기타"]
            default_idx = eq_options.index(default_eq_val) if default_eq_val in eq_options else 6
            report_equip = st.radio("장비구분 선택", eq_options, index=default_idx, horizontal=True, label_visibility="collapsed")

            st.markdown("**작업구분**")
            work_cols = st.columns(6)
            wk_1 = work_cols[0].checkbox("시운전")
            wk_2 = work_cols[1].checkbox("하자처리(전장)")
            wk_3 = work_cols[2].checkbox("기계")
            wk_4 = work_cols[3].checkbox("설비")
            wk_5 = work_cols[4].checkbox("기타")

            # 요금청구와 냉매 분리 및 라디오 버튼 적용 (중복 방지)
            st.markdown("**요금청구 (단일 선택)**")
            charge_type = st.radio("요금구분", ["고객", "유상", "무상"], horizontal=True, label_visibility="collapsed")
            po_no = st.text_input("PO No 입력 (고객 선택 시)") if charge_type == "고객" else ""

            st.markdown("**냉매 (단일 선택)**")
            ref_type = st.radio("냉매구분", ["R-22", "R-407C", "R-134A", "A-507", "기타/선택안함"], horizontal=True, label_visibility="collapsed")

            st.divider()

            # 3. 작업내용
            st.markdown("**작업내용** (제출 시 'No.'가 자동 부여됩니다.)")
            df_work = pd.DataFrame(columns=["구분", "작업내용"])
            edited_work = st.data_editor(df_work, num_rows="dynamic", use_container_width=True)

            st.divider()

            # 4. 하단 상세 정보
            bot_col1, bot_col2 = st.columns(2)
            engineer_cnt = bot_col1.text_input("방문한 서비스 엔지니어 인원 (인원/시간)")
            
            start_time = bot_col1.time_input("작업 시작시간", value=now_kst)
            end_time = bot_col1.time_input("작업 종료시간", value=now_kst)
            
            satisfaction = bot_col2.radio("서비스만족도 조사", ["불만족", "보통", "만족"], horizontal=True)
            constructor = bot_col2.text_input("영업자/시공자", value=user_info.get('업체명', ''))
            
            requests = st.text_area("고객 요청사항")

            st.divider()

            # 🌟 [추가된 부분] 현장 사진 업로드
            st.markdown("**📷 현장 사진 업로드 (선택 사항)**")
            photo_file = st.file_uploader("현장 사진 (JPG, PNG)", type=['jpg', 'png', 'jpeg'])

            st.divider()

            # 5. 서명란
            sig_col1, sig_col2 = st.columns(2)
            with sig_col1:
                st.markdown("**담당직원 (이름 입력 시 자동 서명)**")
                emp_name = st.text_input("담당직원 이름(필수)", value=user_info.get('이름', ''))
                    
            with sig_col2:
                st.markdown("**확인자(소비자) 서명** (마우스/터치로 서명)")
                canvas_customer = st_canvas(
                    stroke_width=3, stroke_color="#000000", background_color="#FFFFFF",
                    height=150, width=350, drawing_mode="freedraw", key="customer_sig_canvas_v2",
                )

            submit_report = st.form_submit_button("리포트 저장 및 전송")
            
            if submit_report:
                if not emp_name.strip():
                    st.error("🚨 담당직원 이름을 입력해야 리포트를 저장할 수 있습니다.")
                elif edited_work.empty:
                    st.error("🚨 작업 내용을 1개 이상 입력해 주세요.")
                else:
                    edited_work.insert(0, "No", range(1, len(edited_work) + 1))
                    
                    with st.spinner("데이터를 처리하고 클라우드 서버에 전송 중입니다..."):
                        
                        # 1. 서명 이미지 추출
                        sig_path = None
                        if canvas_customer.image_data is not None:
                            from PIL import Image
                            import numpy as np
                            img_data = canvas_customer.image_data.astype('uint8')
                            if np.sum(img_data) > 0: # 서명이 비어있지 않은 경우만 저장
                                img = Image.fromarray(img_data, 'RGBA')
                                sig_path = "temp_sig.png"
                                img.save(sig_path)

                        # 2. 현장 사진 클라우드 업로드 (선택 사항)
                        photo_url = "첨부없음"
                        if photo_file is not None:
                            try:
                                upload_res_photo = cloudinary.uploader.upload(
                                    photo_file, folder="AS_PHOTOS", resource_type="image"
                                )
                                photo_url = upload_res_photo.get("secure_url")
                            except Exception as e:
                                photo_url = f"사진업로드 오류: {e}"

                        # 3. 작업구분 체크박스 데이터 수집
                        work_checked = []
                        if wk_1: work_checked.append("시운전")
                        if wk_2: work_checked.append("하자처리(전장)")
                        if wk_3: work_checked.append("기계")
                        if wk_4: work_checked.append("설비")
                        if wk_5: work_checked.append("기타")

                        # 4. PDF 생성 데이터 준비
                        report_data = {
                            "site_name": site_name, 
                            "rcv_date": rcv_date, 
                            "manager_info": manager_info,
                            "end_date": end_date,
                            "equip_info": equip_info, 
                            "report_equip": report_equip,
                            "work_checked": work_checked,
                            "charge_type": charge_type, 
                            "po_no": po_no,
                            "ref_type": ref_type, 
                            "engineer_cnt": engineer_cnt,
                            "start_time": start_time.strftime("%H:%M") if start_time else "",
                            "end_time": end_time.strftime("%H:%M") if end_time else "",
                            "satisfaction": satisfaction,
                            "constructor": constructor,
                            "requests": requests,
                            "emp_name": emp_name
                        }
                        
                        pdf_bytes = create_service_report_pdf(report_data, edited_work, sig_path)
                        
                        try:
                            # 5. PDF 클라우드 업로드
                            upload_res_pdf = cloudinary.uploader.upload(
                                pdf_bytes,
                                folder="SERVICE_REPORTS",
                                resource_type="raw",
                                public_id=f"Report_{selected_customer}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
                            )
                            pdf_url = upload_res_pdf.get("secure_url")
                            
                            # 6. 구글 시트에 기록 (기존 7번째 열에 사진 링크 추가)
                            ws_as = sh.worksheet("AS내역")
                            summary_text = f"장비: {equip_info_str} / 내용: {edited_work.iloc[0]['작업내용']} 외"
                            new_row = [
                                datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                                selected_customer,
                                ref_type, 
                                summary_text,
                                emp_name,
                                user_info['업체명'],
                                photo_url,  # 🌟 현장사진 링크 (없으면 '첨부없음')
                                pdf_url     # PDF 리포트 링크
                            ]
                            ws_as.append_row(new_row)
                            
                            st.success(f"✅ 담당직원[{emp_name}] 명의로 SERVICE REPORT가 클라우드에 저장되었습니다!")
                            
                            # 버튼 출력
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                st.download_button(
                                    label="📥 내 PC/스마트폰으로 PDF 다운로드",
                                    data=pdf_bytes,
                                    file_name=f"SERVICE_REPORT_{selected_customer}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            with col_btn2:
                                st.link_button("☁️ 구글시트용 PDF 링크 확인", pdf_url, use_container_width=True)
                            
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"클라우드 서버 전송에 실패했습니다: {e}")