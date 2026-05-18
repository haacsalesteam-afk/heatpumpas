import streamlit as st
import gspread
import pandas as pd
import json
import cloudinary
import cloudinary.uploader
from streamlit_drawable_canvas import st_canvas
from datetime import datetime, timezone, timedelta
import os
from fpdf import FPDF

# ==========================================
# 🌟 PDF 양식 구현 (A4 사이즈 좌우 대칭 여백, Remark 표 내부 포함)
# ==========================================
def create_service_report_pdf(data, work_details, customer_sig_path=None):
    pdf = FPDF(format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    
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
            
    # --- 1. 헤더 ---
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
    pdf.line(75, 41, 135, 41)
    
    # --- 3. 기본 정보 ---
    pdf.set_font(base_font, "", 10)
    def draw_field(title, value, x1, y, w1, w2):
        pdf.set_xy(x1, y)
        pdf.cell(w1, 6, title)
        pdf.cell(w2, 6, str(value))
        pdf.line(x1+w1, y+5, x1+w1+w2, y+5)
        
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

    y_chk = 67
    pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "장비구분 :")
    eq_list = ["해수열 HP", "해수용 칠러", "폐수열 HP", "공기열 HP", "제습기/건조기", "수소"]
    x_pos = [32, 55, 82, 105, 130, 165]
    for i, eq in enumerate(eq_list):
        draw_chk(x_pos[i], y_chk, eq, data.get('report_equip') == eq)

    y_chk = 74
    pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "작업구분 :")
    wk_list = ["시운전", "하자처리(전장)", "기계", "설비", "기타"]
    x_pos = [32, 55, 90, 110, 130]
    for i, wk in enumerate(wk_list):
        draw_chk(x_pos[i], y_chk, wk, wk in data.get('work_checked', []))

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
    pdf.cell(15, 6, "No", border=1, align='C')
    pdf.cell(25, 6, "구분", border=1, align='C')
    pdf.cell(150, 6, "작업내용", border=1, align='C')
    
    tbl_bottom = 205
    pdf.rect(10, 94, 15, tbl_bottom - 94)
    pdf.rect(25, 94, 25, tbl_bottom - 94)
    pdf.rect(50, 94, 150, tbl_bottom - 94)
    
    y_curr = 95
    for index, row in work_details.iterrows():
        if y_curr > tbl_bottom - 10:
            break 
        pdf.set_xy(10, y_curr)
        pdf.cell(15, 6, str(row['No']), align='C')
        pdf.cell(25, 6, str(row.get('구분','')), align='C')
        pdf.cell(150, 6, " " + str(row.get('작업내용','')))
        y_curr += 6

    # --- 6. 하단 정보 테이블 ---
    y_ft = tbl_bottom 
    
    pdf.rect(10, y_ft, 40, 15)
    pdf.set_xy(10, y_ft+4.5); pdf.cell(40, 6, "(인원 / 시간)", align='C')
    
    pdf.rect(50, y_ft, 90, 15)
    pdf.set_xy(51, y_ft+1); pdf.cell(30, 6, "방문한 서비스 엔지니어 인원 :")
    pdf.set_xy(100, y_ft+1); pdf.cell(40, 6, str(data.get('engineer_cnt','')))
    
    pdf.set_xy(51, y_ft+8); pdf.cell(20, 6, "작업 시작시간 :")
    pdf.set_xy(75, y_ft+8); pdf.cell(20, 6, str(data.get('start_time','')))
    pdf.set_xy(100, y_ft+8); pdf.cell(20, 6, "종료시간 :")
    pdf.set_xy(120, y_ft+8); pdf.cell(20, 6, str(data.get('end_time','')))

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

    pdf.rect(10, y_ft+15, 40, 10)
    pdf.set_xy(10, y_ft+17); pdf.cell(40, 6, "영업자/시공자", align='C')
    pdf.rect(50, y_ft+15, 150, 10)
    pdf.set_xy(50, y_ft+17); pdf.cell(150, 6, str(data.get('constructor','')), align='C')
    
    pdf.rect(10, y_ft+25, 40, 10)
    pdf.set_xy(10, y_ft+27); pdf.cell(40, 6, "고객 요청사항", align='C')
    pdf.rect(50, y_ft+25, 150, 10)
    pdf.set_xy(51, y_ft+27); pdf.cell(148, 6, str(data.get('requests','')))

    pdf.rect(10, y_ft+35, 40, 15)
    pdf.set_xy(10, y_ft+39.5); pdf.cell(40, 6, "담당직원 :", align='C')
    pdf.rect(50, y_ft+35, 150, 15)
    
    pdf.set_xy(65, y_ft+42); pdf.cell(30, 6, str(data.get('emp_name','')), align='C')
    pdf.set_xy(95, y_ft+42); pdf.cell(10, 6, "(서명)")
    pdf.line(55, y_ft+48, 115, y_ft+48)
    
    pdf.set_xy(125, y_ft+42); pdf.cell(30, 6, "확인자(소비자) :", align='R')
    if customer_sig_path:
        pdf.image(customer_sig_path, x=165, y=y_ft+36, w=25) 
    pdf.set_xy(185, y_ft+42); pdf.cell(10, 6, "(서명)")
    pdf.line(125, y_ft+48, 195, y_ft+48)

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
    
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"], 
        api_key = st.secrets["cloudinary"]["api_key"], 
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )
except Exception as e:
    st.error(f"⚠️ 시스템 연결 실패: {e}")
    st.stop()

# ==========================================
# 2. 세션 상태 관리
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'nav_agency' not in st.session_state: st.session_state['nav_agency'] = "전체"
if 'nav_customer' not in st.session_state: st.session_state['nav_customer'] = "선택하세요"

@st.cache_data(ttl=60)
def load_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) < 5: return pd.DataFrame()
        
        cols = [f"Col_{i}" for i in range(40)] 
        cols[1] = "설치일" # B
        cols[2] = "AS기간" # C
        cols[3] = "고객명" # D
        cols[4] = "대표자" # E
        cols[5] = "연락처" # F
        cols[6] = "주소" # G
        cols[7] = "사육어종" # H
        cols[8], cols[9], cols[10] = "용량(RT)", "냉매", "냉매량(kg)" # I, J, K
        cols[31] = "사업명" # AF
        cols[33] = "대리점" # AH
        cols[35] = "제조프로젝트" # AJ (수정됨)
        cols[36] = "제조오더" # AK (수정됨)
        
        df = pd.DataFrame(data[5:], columns=cols[:len(data[0])])
        df['row_index'] = range(6, 6 + len(df))
        return df, ws
    except Exception as e:
        return pd.DataFrame(), None

def calc_expiry(install_date, years):
    try:
        dt = datetime.strptime(str(install_date).replace('.', '-').strip(), "%Y-%m-%d")
        return dt.replace(year=dt.year + int(str(years).replace('년','').strip())).strftime("%Y-%m-%d")
    except:
        return "정보없음"

# ==========================================
# 3. 로그인 화면 (오류 완벽 방지)
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("### 🔲 히트펌프 장비 관리")
    with st.form("login_form"):
        user_id = st.text_input("아이디")
        user_pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("Login"):
            try:
                ws_acc = sh.worksheet("계정관리")
                raw_data = ws_acc.get_all_values()
                
                if len(raw_data) >= 3:
                    headers = raw_data[1] # 2행이 헤더
                    df_acc = pd.DataFrame(raw_data[2:], columns=headers)
                    
                    user_row = df_acc[(df_acc['ID'].astype(str).str.strip() == user_id.strip()) & 
                                      (df_acc['PW'].astype(str).str.strip() == user_pw.strip())]
                    if not user_row.empty:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user_row.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("🚨 아이디 또는 비밀번호가 틀렸습니다.")
                else:
                    st.error("🚨 계정관리 시트에 데이터가 부족합니다. (최소 3행 이상 필요)")
            except Exception as e: 
                st.error(f"🚨 계정 데이터 로드 실패: {e}")
    st.stop()

# ==========================================
# 4. 메인 화면
# ==========================================
user_info = st.session_state['user_info']
# 🌟 시트 B열에 입력된 값을 기준으로 권한 부여 ('구분' 헤더 우선, 없으면 '권한')
auth_level = user_info.get('구분', user_info.get('권한', '')) 
user_company = user_info.get('업체명', '')

col1, col2 = st.columns([8, 2])
col1.markdown(f"### 🔲 장비 관리 시스템 (접속: {user_company})")
if col2.button("로그아웃"):
    for key in ['logged_in', 'user_info', 'nav_agency', 'nav_customer']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

st.write("---")

equipment_type = st.radio("장비 구분", ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"], horizontal=True)
df_equip, ws_equip = load_sheet_data(equipment_type)
if df_equip.empty: st.stop()

# ==========================================
# QM팀 전용 화면
# ==========================================
if auth_level == "QM팀":
    st.markdown("#### 🛠️ QM TEST 결과 입력")
    
    proj_list = sorted([x for x in df_equip['제조프로젝트'].unique() if str(x).strip()])
    # 기본값을 "전체"로 두어 아무것도 안 고르면 전체 리스트가 나오게 함
    sel_proj = st.selectbox("제조프로젝트 선택", ["전체"] + proj_list)
    
    # 🌟 "전체" 선택 시 전체 데이터 복사, 특정 프로젝트 선택 시 해당 데이터만 필터링
    if sel_proj == "전체":
        target_df = df_equip.copy()
    else:
        target_df = df_equip[df_equip['제조프로젝트'] == sel_proj].copy()
    
    if not target_df.empty:
        target_df.insert(0, "선택", False)
        
        st.write(f"**입력 대상 장비 선택 (조회된 장비: 총 {len(target_df)}대) - 다중 체크 가능**")
        # 리스트가 길어질 때를 대비해 표 안에 프로젝트와 오더 항목을 추가로 보여줌
        show_cols = ['선택', '제조프로젝트', '제조오더', '고객명', '설치일', '용량(RT)']
        edited_target = st.data_editor(target_df[show_cols], hide_index=True, use_container_width=True)
        selected_rows = edited_target[edited_target['선택']]
        
        if not selected_rows.empty:
            with st.form("qm_form"):
                st.write(f"**QM TEST 결과 입력 (선택된 장비: {len(selected_rows)}대 일괄 적용)**")
                c1, c2, c3 = st.columns(3)
                qm_cap = c1.text_input("용량(RT)")
                qm_ref = c2.selectbox("냉매", ["R-134A", "R-407C", "R-22", "A-507"])
                qm_ref_amt = c3.text_input("냉매량(kg)")
                
                c4, c5, c6 = st.columns(3)
                qm_oil = c4.text_input("오일량(ℓ)")
                qm_amp = c5.text_input("기동전류(A)")
                qm_press = c6.text_input("기동압력(저/고)")
                
                c7, c8, c9, c10 = st.columns(4)
                qm_plow = c7.text_input("압력셋팅-저압")
                qm_phigh = c8.text_input("압력셋팅-고압")
                qm_ocr_c = c9.text_input("OCR-COMP")
                qm_ocr_p = c10.text_input("OCR-PUMP")
                
                c11, c12 = st.columns(2)
                qm_sensor = c11.radio("센서류 이상유무", ["정상", "이상"], horizontal=True)
                qm_manager = c12.text_input("점검자(필수)", value=user_info.get('이름', user_info.get('ID', '')))
                qm_note = st.text_input("비고")
                
                if st.form_submit_button("QM 데이터 저장"):
                    if not qm_manager.strip():
                        st.error("🚨 점검자 이름을 필수로 입력해야 저장할 수 있습니다.")
                    else:
                        # 수식 에러 방지 조치 (') 적용
                        update_data = [f"'{x}" for x in [qm_cap, qm_ref, qm_ref_amt, qm_oil, qm_amp, qm_press, qm_plow, qm_phigh, qm_ocr_c, qm_ocr_p, qm_sensor, qm_manager, qm_note]]
                        for idx in selected_rows.index:
                            r_idx = target_df.loc[idx, 'row_index']
                            ws_equip.update(f"I{r_idx}:U{r_idx}", [update_data])
                        st.success(f"✅ {len(selected_rows)}대의 장비에 QM 데이터가 성공적으로 저장되었습니다.")
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.info("해당 프로젝트에 등록된 장비가 없습니다.")
        
    st.stop()

# ==========================================
# 대리점 / AS팀 / 영업팀 화면
# ==========================================
search_c1, search_c2 = st.columns(2)

# 🌟 AS팀과 영업팀에게만 전지점 조회 권한 부여
if auth_level in ["AS팀", "영업팀"]:
    agencies = sorted([a for a in df_equip['대리점'].unique() if str(a).strip()])
    ag_idx = agencies.index(st.session_state['nav_agency']) if st.session_state['nav_agency'] in agencies else 0
    sel_agency = search_c1.selectbox("대리점", ["전체"] + agencies, index=ag_idx)
    st.session_state['nav_agency'] = sel_agency
    f_df = df_equip[df_equip['대리점'] == sel_agency] if sel_agency != "전체" else df_equip
else: # 대리점은 본인 업체만 조회
    search_c1.text_input("대리점", value=user_company, disabled=True)
    f_df = df_equip[df_equip['대리점'] == user_company]

customers = sorted([c for c in f_df['고객명'].unique() if str(c).strip()])
cu_idx = customers.index(st.session_state['nav_customer']) if st.session_state['nav_customer'] in customers else 0
sel_cust = search_c2.selectbox("고객명", ["선택하세요"] + customers, index=cu_idx)
st.session_state['nav_customer'] = sel_cust

if sel_cust == "선택하세요":
    st.markdown("### 📋 업체 목록")
    for ag in ([sel_agency] if auth_level in ["AS팀", "영업팀"] and sel_agency != "전체" else agencies if auth_level in ["AS팀", "영업팀"] else [user_company]):
        c_list = sorted([c for c in f_df[f_df['대리점'] == ag]['고객명'].unique() if str(c).strip()])
        if c_list:
            with st.expander(f"🏢 {ag} ({len(c_list)})", expanded=True):
                cols = st.columns(4)
                for i, c in enumerate(c_list):
                    if cols[i%4].button(f"🔍 {c}", key=f"b_{ag}_{c}", use_container_width=True):
                        if auth_level in ["AS팀", "영업팀"]:
                            st.session_state['nav_agency'] = ag
                        st.session_state['nav_customer'] = c
                        st.rerun()
else:
    if st.button("🔙 목록으로"):
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    c_df = f_df[f_df['고객명'] == sel_cust]
    c_info = c_df.iloc[0]
    
    st.markdown(f"### 🏢 [{sel_cust}] 상세 내역")
    info_str = f"- **대표자:** {c_info['대표자']}\n- **연락처:** {c_info['연락처']}\n- **주소:** {c_info['주소']}"
    if equipment_type in ["해수열", "해수용 칠러"]: info_str += f"\n- **사육어종:** {c_info['사육어종']}"
    st.info(info_str)
    
    disp_df = c_df.copy()
    disp_df['AS만료일'] = disp_df.apply(lambda x: calc_expiry(x['설치일'], x['AS기간']), axis=1)
    disp_df.insert(0, "선택", False)
    
    st.markdown("▶ **대상 장비 선택 (QM/설치/AS 확인)**")
    show_cols = ['선택', '설치일', 'AS만료일', '용량(RT)', '냉매', '냉매량(kg)', '사업명', '제조오더']
    edited_equip = st.data_editor(disp_df[show_cols], hide_index=True, use_container_width=True)
    sel_equips = edited_equip[edited_equip['선택']]
    
    equip_info_str = " / ".join(sel_equips['용량(RT)'].astype(str).unique().tolist()) if not sel_equips.empty else ""

    # --- 설치공사 입력 폼 ---
    # 🌟 AS팀, 영업팀이 아니면(즉, 대리점이면) 설치공사 폼 노출
    if auth_level not in ["AS팀", "영업팀"] and not sel_equips.empty:
        with st.expander("🛠️ 설치공사 내역 입력 (대리점 전용)", expanded=False):
            with st.form("install_form"):
                ic1, ic2, ic3 = st.columns(3)
                i_main = ic1.text_input("메인전원(SQ)")
                i_heat = ic2.text_input("열원/규격")
                i_load = ic3.text_input("부하/규격")
                
                ic4, ic5, ic6 = st.columns(3)
                i_circ = ic4.text_input("순환방식")
                i_pipe = ic5.text_input("배관재질")
                i_cond = ic6.text_input("사용조건")
                
                ic7, ic8 = st.columns(2)
                i_installer = ic7.text_input("시공대리점(필수)", value=user_company)
                i_note1 = ic8.text_input("비고")
                
                i_note2 = st.text_input("설치 비고")
                
                if st.form_submit_button("설치공사 데이터 저장"):
                    if not i_installer.strip():
                        st.error("🚨 시공대리점을 필수로 입력해야 저장할 수 있습니다.")
                    else:
                        update_data = [f"'{x}" for x in [i_main, i_heat, i_load, i_note1, i_circ, i_pipe, i_cond, i_installer, i_note2]]
                        for idx in sel_equips.index:
                            r_idx = c_df.loc[idx, 'row_index']
                            ws_equip.update(f"V{r_idx}:AD{r_idx}", [update_data])
                        st.success("설치공사 내역이 성공적으로 저장되었습니다.")
                        st.cache_data.clear()
                        st.rerun()

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).time()

    # --- AS 내역 추가 (Form) ---
    # 🌟 AS팀, 영업팀에게만 SERVICE REPORT 폼 노출
    if auth_level in ["AS팀", "영업팀"]:
        with st.expander("📝 SERVICE REPORT 작성하기 (PDF 저장)", expanded=True):
            with st.form("service_report_form", clear_on_submit=False):
                st.markdown("### SERVICE REPORT")
                
                col1, col2 = st.columns(2)
                site_name = col1.text_input("현장명(주소)", value=c_info['주소'])
                rcv_date = col2.date_input("접수일자")
                manager_info = col1.text_input("담당자(연락처)", value=f"{c_info['대표자']} / {c_info['연락처']}")
                end_date = col2.date_input("완료일자")
                equip_info = st.text_input("장비정보 (용량/수량/제어/냉매/기타)", value=equip_info_str)

                st.divider()

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

                st.markdown("**요금청구 (단일 선택)**")
                charge_type = st.radio("요금구분", ["고객", "유상", "무상"], horizontal=True, label_visibility="collapsed")
                po_no = st.text_input("PO No 입력 (고객 선택 시)") if charge_type == "고객" else ""

                st.markdown("**냉매 (단일 선택)**")
                ref_type = st.radio("냉매구분", ["R-22", "R-407C", "R-134A", "A-507", "기타/선택안함"], horizontal=True, label_visibility="collapsed")

                st.divider()

                st.markdown("**작업내용** (제출 시 'No.'가 자동 부여됩니다.)")
                df_work = pd.DataFrame(columns=["구분", "작업내용"])
                edited_work = st.data_editor(df_work, num_rows="dynamic", use_container_width=True)

                st.divider()

                bot_col1, bot_col2 = st.columns(2)
                engineer_cnt = bot_col1.text_input("방문한 서비스 엔지니어 인원 (인원/시간)")
                start_time = bot_col1.time_input("작업 시작시간", value=now_kst)
                end_time = bot_col1.time_input("작업 종료시간", value=now_kst)
                
                satisfaction = bot_col2.radio("서비스만족도 조사", ["불만족", "보통", "만족"], horizontal=True)
                constructor = bot_col2.text_input("영업자/시공자(필수)", value=user_info.get('업체명', ''))
                requests = st.text_area("고객 요청사항")

                st.divider()

                st.markdown("**📷 현장 사진 업로드 (선택 사항)**")
                photo_file = st.file_uploader("현장 사진 (JPG, PNG)", type=['jpg', 'png', 'jpeg'])

                st.divider()

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
                    if not constructor.strip():
                        st.error("🚨 영업자/시공자 이름을 필수로 입력해야 저장할 수 있습니다.")
                    elif not emp_name.strip():
                        st.error("🚨 담당직원 이름을 필수로 입력해야 저장할 수 있습니다.")
                    elif edited_work.empty:
                        st.error("🚨 작업 내용을 1개 이상 입력해 주세요.")
                    else:
                        edited_work.insert(0, "No", range(1, len(edited_work) + 1))
                        
                        with st.spinner("데이터를 처리하고 클라우드 서버에 전송 중입니다..."):
                            sig_path = None
                            if canvas_customer.image_data is not None:
                                from PIL import Image
                                import numpy as np
                                img_data = canvas_customer.image_data.astype('uint8')
                                if np.sum(img_data) > 0: 
                                    img = Image.fromarray(img_data, 'RGBA')
                                    sig_path = "temp_sig.png"
                                    img.save(sig_path)

                            photo_url = "첨부없음"
                            if photo_file is not None:
                                try:
                                    upload_res_photo = cloudinary.uploader.upload(
                                        photo_file, folder="AS_PHOTOS", resource_type="image"
                                    )
                                    photo_url = upload_res_photo.get("secure_url")
                                except Exception as e:
                                    photo_url = f"사진업로드 오류: {e}"

                            work_checked = []
                            if wk_1: work_checked.append("시운전")
                            if wk_2: work_checked.append("하자처리(전장)")
                            if wk_3: work_checked.append("기계")
                            if wk_4: work_checked.append("설비")
                            if wk_5: work_checked.append("기타")

                            report_data = {
                                "site_name": site_name, "rcv_date": rcv_date, "manager_info": manager_info,
                                "end_date": end_date, "equip_info": equip_info, "report_equip": report_equip,
                                "work_checked": work_checked, "charge_type": charge_type, "po_no": po_no,
                                "ref_type": ref_type, "engineer_cnt": engineer_cnt,
                                "start_time": start_time.strftime("%H:%M") if start_time else "",
                                "end_time": end_time.strftime("%H:%M") if end_time else "",
                                "satisfaction": satisfaction, "constructor": constructor,
                                "requests": requests, "emp_name": emp_name
                            }
                            
                            pdf_bytes = create_service_report_pdf(report_data, edited_work, sig_path)
                            
                            try:
                                upload_res_pdf = cloudinary.uploader.upload(
                                    pdf_bytes, folder="SERVICE_REPORTS", resource_type="raw",
                                    public_id=f"Report_{sel_cust}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
                                )
                                pdf_url = upload_res_pdf.get("secure_url")
                                
                                ws_as = sh.worksheet("AS내역")
                                summary_text = f"장비: {equip_info_str} / 내용: {edited_work.iloc[0]['작업내용']} 외"
                                new_row = [
                                    datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                                    sel_cust,
                                    ref_type, 
                                    summary_text,
                                    emp_name,
                                    user_info['업체명'],
                                    photo_url,
                                    pdf_url
                                ]
                                
                                safe_new_row = [f"'{item}" if isinstance(item, str) else item for item in new_row]
                                ws_as.append_row(safe_new_row)
                                
                                st.success(f"✅ 담당직원[{emp_name}] 명의로 SERVICE REPORT가 클라우드에 저장되었습니다!")
                                
                                col_btn1, col_btn2 = st.columns(2)
                                with col_btn1:
                                    st.download_button(
                                        label="📥 내 PC/스마트폰으로 PDF 다운로드", data=pdf_bytes,
                                        file_name=f"SERVICE_REPORT_{sel_cust}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                        mime="application/pdf", use_container_width=True
                                    )
                                with col_btn2:
                                    st.link_button("☁️ 구글시트용 PDF 링크 확인", pdf_url, use_container_width=True)
                                
                                st.balloons()
                            except Exception as e:
                                st.error(f"클라우드 서버 전송에 실패했습니다: {e}")