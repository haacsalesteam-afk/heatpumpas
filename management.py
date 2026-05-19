import streamlit as st
import gspread
import pandas as pd
import numpy as np
import json
import cloudinary
import cloudinary.uploader
from streamlit_drawable_canvas import st_canvas
from datetime import datetime, timezone, timedelta
import os
import tempfile
from fpdf import FPDF
from PIL import Image

# ==========================================
# 🌟 PDF 양식 구현 (사진 대지 2페이지 포함)
# ==========================================
def create_service_report_pdf(report_type, data, work_details, customer_sig_path=None, before_photos=None, after_photos=None):
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
            try:
                pdf.add_font("Nanum", "", f)
                base_font = "Nanum"
                break
            except:
                pass
            
    # --- 1. 헤더 ---
    pdf.set_font(base_font, "", 16)
    pdf.cell(0, 8, "하 이 에 어 공 조 (주)", ln=True, align='C')
    pdf.set_font(base_font, "", 10)
    pdf.cell(0, 5, "경상남도 김해시 진례면 고모로 324번길 204", ln=True, align='C')
    pdf.cell(0, 5, "Tel) 055-340-5072 Fax) 055-346-3884 E-Mail) hiairas@hiairkorea.co.kr", ln=True, align='C')
    pdf.line(10, 28, 200, 28)
    
    # --- 2. 제목 (선택된 보고서 종류 반영) ---
    pdf.set_xy(10, 32)
    pdf.set_font(base_font, "", 22) 
    pdf.cell(0, 10, report_type, ln=True, align='C')
    if report_type == "SERVICE REPORT":
        pdf.line(75, 41, 135, 41)
    else:
        pdf.line(78, 41, 132, 41)
    
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
    pdf.cell(55, 6, "(용량)", align='R')

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

    if report_type == "SERVICE REPORT":
        y_chk = 74
        pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "작업구분 :")
        wk_list = ["하자처리(전장)", "기계", "설비", "기타"]
        x_pos = [32, 60, 85, 105]
        for i, wk in enumerate(wk_list):
            draw_chk(x_pos[i], y_chk, wk, wk in data.get('work_checked', []))

        y_chk = 81
        pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "요금청구 :")
        is_cust = "고객" in data.get('charge_type', '')
        draw_chk(32, y_chk, f"고객(PO No: {data.get('po_no','') if is_cust else '                '})", is_cust)
        draw_chk(90, y_chk, "유상", data.get('charge_type') == "유상")
        draw_chk(110, y_chk, "무상", data.get('charge_type') == "무상")
    else:
        y_chk = 74
        pdf.set_xy(10, y_chk-1.5); pdf.cell(20, 6, "작업구분 :")
        draw_chk(32, y_chk, "시운전", True)
    
    ref_list = ["R-22", "R-407C", "R-134A", "A-507"]
    x_pos = [128, 145, 165, 185]
    for i, ref in enumerate(ref_list):
        draw_chk(x_pos[i], 81, ref, data.get('ref_type') == ref)

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
    
    constructor_val = str(data.get('constructor', '')).strip()
    emp_val = str(data.get('emp_name', '')).strip()
    constructor_text = f"{constructor_val} / {emp_val}" if constructor_val and emp_val else (constructor_val or emp_val)
    pdf.set_xy(50, y_ft+17); pdf.cell(150, 6, constructor_text, align='C')
    
    pdf.rect(10, y_ft+25, 40, 10)
    pdf.set_xy(10, y_ft+27); pdf.cell(40, 6, "고객 요청사항", align='C')
    pdf.rect(50, y_ft+25, 150, 10)
    pdf.set_xy(51, y_ft+27); pdf.cell(148, 6, str(data.get('requests','')))

    pdf.rect(10, y_ft+35, 40, 20)
    pdf.set_xy(10, y_ft+42); pdf.cell(40, 6, "담당직원 :", align='C')
    pdf.rect(50, y_ft+35, 150, 20)
    
    pdf.set_font(base_font, "", 9)
    pdf.rect(52, y_ft+38, 3, 3)
    pdf.set_xy(52, y_ft+36.5); pdf.cell(3, 6, "v", align='C')
    pdf.set_xy(56, y_ft+36.5); pdf.cell(140, 6, "(필수) 본인은 A/S 및 시운전 작업에 대한 설명을 듣고 그 내용을 충분히 이해하였음을 확인합니다.")
    
    pdf.set_font(base_font, "", 10)
    pdf.set_xy(65, y_ft+46); pdf.cell(30, 6, str(data.get('emp_name','')), align='C')
    pdf.set_xy(95, y_ft+46); pdf.cell(10, 6, "(서명)")
    pdf.line(55, y_ft+52, 115, y_ft+52)
    
    pdf.set_xy(125, y_ft+46); pdf.cell(30, 6, "확인자(소비자) :", align='R')
    if customer_sig_path:
        pdf.image(customer_sig_path, x=165, y=y_ft+41, w=25) 
    pdf.set_xy(185, y_ft+46); pdf.cell(10, 6, "(서명)")
    pdf.line(125, y_ft+52, 195, y_ft+52)

    pdf.rect(10, y_ft+55, 40, 15)
    pdf.set_font(base_font, "", 12)
    pdf.set_xy(10, y_ft+59.5); pdf.cell(40, 6, "※ Remark ※", align='C')
    
    pdf.rect(50, y_ft+55, 150, 15)
    pdf.set_font(base_font, "", 9)
    pdf.set_xy(50, y_ft+56); pdf.cell(150, 4.5, "Spare Parts Sales & Service Team", align='C')
    pdf.set_xy(50, y_ft+60.5); pdf.cell(150, 4.5, "Spare direct call : +82-55-340-5182  /  E-mail : spare@hiairkorea.co.kr", align='C')
    pdf.set_xy(50, y_ft+65); pdf.cell(150, 4.5, "Service direct call : +82-55-340-5072  /  E-mail : hiairas@hiairkorea.co.kr", align='C')

    if (before_photos and len(before_photos) > 0) or (after_photos and len(after_photos) > 0):
        pdf.add_page()
        pdf.set_font(base_font, "", 18)
        pdf.cell(0, 12, "작 업 사 진 대 지", border=0, ln=True, align='C')
        pdf.set_font(base_font, "", 11)
        
        y_start = pdf.get_y()
        pdf.cell(0, 8, "작업전 상태 및 확인", border=1, ln=True, align='C')
        box_y = pdf.get_y()
        pdf.rect(10, box_y, 95, 80)
        pdf.rect(105, box_y, 95, 80)
        
        if before_photos and len(before_photos) > 0:
            pdf.image(before_photos[0], x=12, y=box_y+2, w=91, h=76)
        if before_photos and len(before_photos) > 1:
            pdf.image(before_photos[1], x=107, y=box_y+2, w=91, h=76)
            
        pdf.set_y(box_y + 80)
        
        pdf.cell(0, 8, "완료 사진 및 작업 사진", border=1, ln=True, align='C')
        box_y = pdf.get_y()
        
        pdf.rect(10, box_y, 95, 75)
        pdf.rect(105, box_y, 95, 75)
        if after_photos and len(after_photos) > 0:
            pdf.image(after_photos[0], x=12, y=box_y+2, w=91, h=71)
        if after_photos and len(after_photos) > 1:
            pdf.image(after_photos[1], x=107, y=box_y+2, w=91, h=71)
            
        box_y += 75
        pdf.rect(10, box_y, 95, 75)
        pdf.rect(105, box_y, 95, 75)
        if after_photos and len(after_photos) > 2:
            pdf.image(after_photos[2], x=12, y=box_y+2, w=91, h=71)
        if after_photos and len(after_photos) > 3:
            pdf.image(after_photos[3], x=107, y=box_y+2, w=91, h=71)

    return bytes(pdf.output())

# ==========================================
# 🌟 따옴표 및 데이터 안전 처리 함수
# ==========================================
def safe_text(val):
    val_str = str(val).strip()
    if val_str.startswith(('=', '+', '-', '@')):
        return f"'{val_str}"
    return val_str

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
if 'nav_sido' not in st.session_state: st.session_state['nav_sido'] = "전체"
if 'nav_sigungu' not in st.session_state: st.session_state['nav_sigungu'] = "전체"

@st.cache_data(ttl=60)
def load_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) < 5: return pd.DataFrame()
        
        # 🌟 60열 패딩 및 전면 재배치 반영 
        cols = [f"Col_{i}" for i in range(60)] 
        cols[1] = "설치일" # B
        cols[2] = "AS기간" # C
        cols[3] = "고객명" # D
        cols[4] = "대표자" # E
        cols[5] = "연락처" # F
        cols[6] = "주소" # G
        cols[7] = "사육어종" # H
        
        # QM TEST (I~V)
        cols[8], cols[9], cols[10] = "용량(RT)", "냉매", "냉매량(kg)" # I, J, K
        cols[11], cols[12], cols[13], cols[14] = "오일량(ℓ)", "기동전류(A)", "가동압력(저압)", "가동압력(고압)" # L, M, N, O
        cols[15], cols[16], cols[17], cols[18] = "압력-저", "압력-고", "OCR-COMP", "OCR-PUMP" # P, Q, R, S
        cols[19], cols[20], cols[21] = "센서이상", "점검자", "비고" # T, U, V (QM비고 -> 비고)
        cols[22] = "검사완료일" # W (신규 추가)
        
        # 설치공사 (X~AF)
        cols[23], cols[24], cols[25], cols[26] = "메인전원(SQ)", "열원/규격", "부하/규격", "펌프비고" # X, Y, Z, AA
        cols[27], cols[28], cols[29], cols[30], cols[31] = "순환방식", "배관재질", "사용조건", "시공대리점", "비고" # AB, AC, AD, AE, AF (설치비고 -> 비고)
        
        # 시운전 (AG~AM)
        cols[32], cols[33], cols[34], cols[35] = "가동시간", "시운전압력-저", "시운전압력-고", "시운전전류" # AG, AH, AI, AJ
        cols[36], cols[37], cols[38] = "물온도-부하", "물온도-열원", "시운전비고" # AK, AL, AM
        
        # 기타 정보
        cols[40] = "사업명" # AO
        cols[41] = "낙찰업체명" # AP
        cols[42] = "대리점" # AQ
        cols[44] = "제조프로젝트" # AS
        cols[45] = "제조오더" # AT
        cols[46] = "SERVICE No." # AU
        cols[47] = "QM사진" # AV
        cols[48] = "설치사진" # AW
        cols[49] = "시운전사진" # AX
        
        padded_data = []
        for row in data[5:]:
            padded_row = row + [""] * (60 - len(row))
            padded_data.append(padded_row[:60])
            
        df = pd.DataFrame(padded_data, columns=cols)
        df['row_index'] = range(6, 6 + len(df))
        
        df['SERVICE No.'] = df['SERVICE No.'].astype(str).str.replace(r"^'", "", regex=True)
        df['QM사진'] = df['QM사진'].astype(str).str.replace(r"^'", "", regex=True)
        df['설치사진'] = df['설치사진'].astype(str).str.replace(r"^'", "", regex=True)
        df['시운전사진'] = df['시운전사진'].astype(str).str.replace(r"^'", "", regex=True)
        
        def get_sido(addr):
            return str(addr).split()[0] if str(addr).strip() else "미상"
        def get_sigungu(addr):
            parts = str(addr).split()
            return parts[1] if len(parts) > 1 else "미상"
            
        df['시/도'] = df['주소'].apply(get_sido)
        df['시/군/구'] = df['주소'].apply(get_sigungu)
        
        return df  
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_as_data():
    try:
        ws_as = sh.worksheet("AS내역")
        data = ws_as.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        
        raw_cols = data[0]
        unique_cols = []
        seen = set()
        for i, col in enumerate(raw_cols):
            c = str(col).strip()
            if not c: c = f"빈칸_{i}"
            original_c = c
            counter = 1
            while c in seen:
                c = f"{original_c}_{counter}"
                counter += 1
            seen.add(c)
            unique_cols.append(c)
            
        return pd.DataFrame(data[1:], columns=unique_cols)
    except Exception as e:
        return pd.DataFrame()

def calc_expiry(install_date, years):
    try:
        dt = datetime.strptime(str(install_date).replace('.', '-').strip(), "%Y-%m-%d")
        return dt.replace(year=dt.year + int(str(years).replace('년','').strip())).strftime("%Y-%m-%d")
    except:
        return "정보없음"

KST = timezone(timedelta(hours=9))

# ==========================================
# 3. 로그인 화면 
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
                    headers = raw_data[1] 
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
                    st.error("🚨 계정관리 시트에 데이터가 부족합니다.")
            except Exception as e: 
                st.error(f"🚨 계정 데이터 로드 실패: {e}")
    st.stop()

# ==========================================
# 4. 메인 화면
# ==========================================
user_info = st.session_state['user_info']
auth_level = user_info.get('구분', user_info.get('권한', '')) 
user_company = user_info.get('업체명', '')

col1, col2 = st.columns([8, 2])
col1.markdown(f"### 🔲 장비 관리 시스템 (접속: {user_company})")
if col2.button("로그아웃"):
    for key in ['logged_in', 'user_info', 'nav_agency', 'nav_customer', 'nav_sido', 'nav_sigungu']:
        if key in st.session_state: del st.session_state[key]
    st.rerun()

st.write("---")

equipment_type = st.radio("장비 구분", ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"], horizontal=True)

df_equip = load_sheet_data(equipment_type)
if df_equip.empty: 
    st.stop()
ws_equip = sh.worksheet(equipment_type)

# ==========================================
# QM팀 전용 화면 
# ==========================================
if auth_level == "QM팀":
    st.markdown("#### 🛠️ QM TEST 결과 입력")
    
    proj_list = sorted([x for x in df_equip['제조프로젝트'].unique() if str(x).strip()])
    sel_proj = st.selectbox("제조프로젝트 선택", ["전체"] + proj_list)
    
    if sel_proj == "전체":
        target_df = df_equip.copy()
    else:
        target_df = df_equip[df_equip['제조프로젝트'] == sel_proj].copy()
    
    if not target_df.empty:
        target_df.insert(0, "선택", False)
        target_df.insert(1, "상태", target_df['점검자'].apply(lambda x: "✅ 완료" if str(x).replace("'", "").strip() else "❌ 미입력"))
        
        st.write(f"**입력 대상 장비 선택 (조회된 장비: 총 {len(target_df)}대) - 다중 체크 가능**")
        show_cols = ['선택', '상태', 'SERVICE No.', '제조프로젝트', '제조오더', '고객명', '설치일', '용량(RT)']
        edited_target = st.data_editor(target_df[show_cols], hide_index=True, use_container_width=True, disabled=['상태','SERVICE No.','제조프로젝트','제조오더','고객명','설치일','용량(RT)'])
        selected_rows = edited_target[edited_target['선택']]
        
        if not selected_rows.empty:
            sel_key = "-".join(selected_rows.index.astype(str))
            if st.session_state.get('qm_sel_key') != sel_key:
                st.session_state['qm_sel_key'] = sel_key
                st.session_state['qm_edit_mode'] = False
            
            first_row = target_df.loc[selected_rows.index[0]]
            is_done = str(first_row.get('점검자', '')).replace("'", "").strip() != ""
            
            if is_done and not st.session_state.get('qm_edit_mode', False):
                st.success("✅ 이미 QM TEST 결과가 입력된 장비입니다. (아래에서 내역 확인 및 수정 가능)")
                
                # 🌟 읽기 전용 (View) 모드
                st.markdown("### 🔍 입력된 QM TEST 결과")
                v1, v2, v3 = st.columns(3)
                v1.text_input("용량(RT)", value=first_row.get('용량(RT)',''), disabled=True, key="v1")
                v2.text_input("냉매", value=first_row.get('냉매',''), disabled=True, key="v2")
                v3.text_input("냉매량(kg)", value=first_row.get('냉매량(kg)',''), disabled=True, key="v3")
                
                v4, v5, v6, v7 = st.columns(4)
                v4.text_input("오일량(ℓ)", value=first_row.get('오일량(ℓ)',''), disabled=True, key="v4")
                v5.text_input("기동전류(A)", value=first_row.get('기동전류(A)',''), disabled=True, key="v5")
                v6.text_input("가동압력(저압)", value=first_row.get('가동압력(저압)',''), disabled=True, key="v6")
                v7.text_input("가동압력(고압)", value=first_row.get('가동압력(고압)',''), disabled=True, key="v7")
                
                v8, v9, v10, v11 = st.columns(4)
                v8.text_input("압력셋팅-저압", value=first_row.get('압력-저',''), disabled=True, key="v8")
                v9.text_input("압력셋팅-고압", value=first_row.get('압력-고',''), disabled=True, key="v9")
                v10.text_input("OCR-COMP", value=first_row.get('OCR-COMP',''), disabled=True, key="v10")
                v11.text_input("OCR-PUMP", value=first_row.get('OCR-PUMP',''), disabled=True, key="v11")
                
                v12, v13, v14 = st.columns([1, 1, 1])
                v12.text_input("센서류 이상유무", value=first_row.get('센서이상',''), disabled=True, key="v12")
                v13.text_input("점검자", value=first_row.get('점검자',''), disabled=True, key="v13")
                v14.text_input("검사완료일", value=first_row.get('검사완료일',''), disabled=True, key="v14")
                
                st.text_input("비고", value=first_row.get('비고',''), disabled=True, key="v15")
                
                qm_urls = [u.strip() for u in str(first_row.get('QM사진', '')).replace('\n', ',').split(',') if 'http' in u]
                if qm_urls:
                    st.markdown("**📷 등록된 현장 사진**")
                    cols = st.columns(min(len(qm_urls), 4))
                    for i, u in enumerate(qm_urls):
                        cols[i%4].image(u, use_container_width=True)
                
                if st.button("✏️ 결과 수정하기"):
                    st.session_state['qm_edit_mode'] = True
                    st.rerun()

            else:
                # 🌟 입력 및 수정 폼
                default_capacity = " / ".join(selected_rows['용량(RT)'].astype(str).unique().tolist())
                
                d_cap = first_row.get('용량(RT)','') if is_done else default_capacity
                d_ref = first_row.get('냉매','') if is_done and first_row.get('냉매','') in ["R-134A", "R-407C", "R-22", "A-507"] else "R-134A"
                d_ref_amt = first_row.get('냉매량(kg)','') if is_done else ""
                d_oil = first_row.get('오일량(ℓ)','') if is_done else ""
                d_amp = first_row.get('기동전류(A)','') if is_done else ""
                d_plow_run = first_row.get('가동압력(저압)','') if is_done else ""
                d_phigh_run = first_row.get('가동압력(고압)','') if is_done else ""
                d_plow_set = first_row.get('압력-저','') if is_done else ""
                d_phigh_set = first_row.get('압력-고','') if is_done else ""
                d_ocr_c = first_row.get('OCR-COMP','') if is_done else ""
                d_ocr_p = first_row.get('OCR-PUMP','') if is_done else ""
                d_sensor = first_row.get('센서이상','') if is_done and first_row.get('센서이상','') in ["정상", "이상"] else "정상"
                d_note = first_row.get('비고','') if is_done else ""
                
                try:
                    parsed_date = datetime.strptime(str(first_row.get('검사완료일','')).strip(), "%Y-%m-%d").date() if is_done else datetime.now(KST).date()
                except:
                    parsed_date = datetime.now(KST).date()
                
                with st.form("qm_form"):
                    st.write(f"**QM TEST 결과 입력 (선택된 장비: {len(selected_rows)}대 일괄 적용)**")
                    c1, c2, c3 = st.columns(3)
                    qm_cap = c1.text_input("용량(RT)", value=d_cap)
                    
                    ref_options = ["R-134A", "R-407C", "R-22", "A-507"]
                    ref_idx = ref_options.index(d_ref) if d_ref in ref_options else 0
                    qm_ref = c2.selectbox("냉매", ref_options, index=ref_idx)
                    qm_ref_amt = c3.text_input("냉매량(kg)", value=d_ref_amt)
                    
                    c4, c5, c6, c7 = st.columns(4)
                    qm_oil = c4.text_input("오일량(ℓ)", value=d_oil)
                    qm_amp = c5.text_input("기동전류(A)", value=d_amp)
                    qm_press_low = c6.text_input("가동압력(저압)", value=d_plow_run)
                    qm_press_high = c7.text_input("가동압력(고압)", value=d_phigh_run)
                    
                    c8, c9, c10, c11 = st.columns(4)
                    qm_plow = c8.text_input("압력셋팅-저압", value=d_plow_set)
                    qm_phigh = c9.text_input("압력셋팅-고압", value=d_phigh_set)
                    qm_ocr_c = c10.text_input("OCR-COMP", value=d_ocr_c)
                    qm_ocr_p = c11.text_input("OCR-PUMP", value=d_ocr_p)
                    
                    c12, c13, c14 = st.columns([1, 1, 1])
                    sensor_idx = 0 if d_sensor == "정상" else 1
                    qm_sensor = c12.radio("센서류 이상유무", ["정상", "이상"], horizontal=True, index=sensor_idx)
                    
                    # 🌟 점검자 비워두기 (수정 시 새로 입력 강제)
                    qm_manager = c13.text_input("점검자(필수 - 새로 입력)", value="")
                    qm_date = c14.date_input("검사완료일", value=parsed_date)
                    
                    qm_note = st.text_input("비고", value=d_note)
                    
                    st.markdown("**📷 QM TEST 현장 사진 업로드 (선택 / 여러 장 가능)**")
                    st.caption("새로 업로드 시 기존 사진 목록에 추가됩니다.")
                    qm_photo_files = st.file_uploader("현장 사진 (JPG, PNG)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                    
                    if st.form_submit_button("QM 데이터 저장"):
                        if not qm_manager.strip():
                            st.error("🚨 점검자 이름을 필수로 입력해야 저장할 수 있습니다.")
                        else:
                            with st.spinner("데이터를 처리하고 클라우드 서버에 전송 중입니다..."):
                                qm_photo_urls = []
                                safe_wo = str(selected_rows['제조오더'].iloc[0]).replace("/", "_") if not selected_rows.empty else "미상"
                                if qm_photo_files:
                                    for f in qm_photo_files:
                                        try:
                                            res = cloudinary.uploader.upload(f, folder=f"QM_PHOTOS/{safe_wo}", resource_type="image")
                                            qm_photo_urls.append(res.get("secure_url"))
                                        except: pass

                                update_data = [safe_text(x) for x in [qm_cap, qm_ref, qm_ref_amt, qm_oil, qm_amp, qm_press_low, qm_press_high, qm_plow, qm_phigh, qm_ocr_c, qm_ocr_p, qm_sensor, qm_manager, qm_date.strftime("%Y-%m-%d"), qm_note]]
                                for idx in selected_rows.index:
                                    r_idx = target_df.loc[idx, 'row_index']
                                    ws_equip.update(f"I{r_idx}:W{r_idx}", [update_data]) 
                                    
                                    existing_photo = str(target_df.loc[idx, 'QM사진']).replace("'", "").strip()
                                    final_urls = []
                                    if existing_photo: final_urls.extend([u.strip() for u in existing_photo.replace('\n', ',').split(',') if 'http' in u])
                                    if qm_photo_urls: final_urls.extend(qm_photo_urls)
                                    
                                    if final_urls:
                                        qm_photo_str = " \n ".join(final_urls) 
                                        ws_equip.update(f"AV{r_idx}", [[f"'{qm_photo_str}"]])
                                        
                                st.success(f"✅ {len(selected_rows)}대의 장비에 QM 데이터가 성공적으로 저장되었습니다.")
                                st.session_state['qm_edit_mode'] = False
                                st.cache_data.clear()
                                st.rerun()
    else:
        st.info("해당 프로젝트에 등록된 장비가 없습니다.")
        
    st.stop()

# ==========================================
# 대리점 / AS팀 / 영업팀 화면
# ==========================================
search_c1, search_c2, search_c3, search_c4 = st.columns([2, 2, 2, 3])

if auth_level in ["AS팀", "영업팀", "하이에어공조"]:
    agencies = sorted([a for a in df_equip['대리점'].unique() if str(a).strip()])
    ag_idx = agencies.index(st.session_state['nav_agency']) + 1 if st.session_state['nav_agency'] in agencies else 0
    sel_agency = search_c1.selectbox("대리점", ["전체"] + agencies, index=ag_idx)
    
    if st.session_state['nav_agency'] != sel_agency:
        st.session_state['nav_agency'] = sel_agency
        st.session_state['nav_sido'] = "전체"
        st.session_state['nav_sigungu'] = "전체"
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    f_df = df_equip[df_equip['대리점'] == sel_agency] if sel_agency != "전체" else df_equip
    
    sido_list = sorted([x for x in f_df['시/도'].unique() if x != "미상"])
    sido_idx = sido_list.index(st.session_state['nav_sido']) + 1 if st.session_state['nav_sido'] in sido_list else 0
    sel_sido = search_c2.selectbox("시/도", ["전체"] + sido_list, index=sido_idx)
    
    if st.session_state['nav_sido'] != sel_sido:
        st.session_state['nav_sido'] = sel_sido
        st.session_state['nav_sigungu'] = "전체"
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    f_df = f_df[f_df['시/도'] == sel_sido] if sel_sido != "전체" else f_df
    
    sigungu_list = sorted([x for x in f_df['시/군/구'].unique() if x != "미상"])
    sigungu_idx = sigungu_list.index(st.session_state['nav_sigungu']) + 1 if st.session_state['nav_sigungu'] in sigungu_list else 0
    sel_sigungu = search_c3.selectbox("시/군/구", ["전체"] + sigungu_list, index=sigungu_idx)
    
    if st.session_state['nav_sigungu'] != sel_sigungu:
        st.session_state['nav_sigungu'] = sel_sigungu
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    f_df = f_df[f_df['시/군/구'] == sel_sigungu] if sel_sigungu != "전체" else f_df
else:
    search_c1.text_input("대리점", value=user_company, disabled=True)
    search_c2.text_input("시/도", value="전체", disabled=True)
    search_c3.text_input("시/군/구", value="전체", disabled=True)
    f_df = df_equip[df_equip['대리점'] == user_company]

customers = sorted([c for c in f_df['고객명'].unique() if str(c).strip()])
cu_idx = customers.index(st.session_state['nav_customer']) + 1 if st.session_state['nav_customer'] in customers else 0
sel_cust = search_c4.selectbox("고객명", ["선택하세요"] + customers, index=cu_idx)

if st.session_state['nav_customer'] != sel_cust:
    st.session_state['nav_customer'] = sel_cust
    if sel_cust != "선택하세요" and auth_level in ["AS팀", "영업팀", "하이에어공조"]:
        c_row = f_df[f_df['고객명'] == sel_cust].iloc[0]
        st.session_state['nav_agency'] = c_row['대리점']
        st.session_state['nav_sido'] = c_row['시/도']
        st.session_state['nav_sigungu'] = c_row['시/군/구']
    st.rerun()

if sel_cust == "선택하세요":
    st.markdown("### 📋 업체 목록")
    disp_agencies = [sel_agency] if (auth_level in ["AS팀", "영업팀", "하이에어공조"] and sel_agency != "전체") else (agencies if auth_level in ["AS팀", "영업팀", "하이에어공조"] else [user_company])
    
    for ag in disp_agencies:
        c_list = sorted([c for c in f_df[f_df['대리점'] == ag]['고객명'].unique() if str(c).strip()])
        if c_list:
            with st.expander(f"🏢 {ag} ({len(c_list)})", expanded=True):
                cols = st.columns(4)
                for i, c in enumerate(c_list):
                    if cols[i%4].button(f"🔍 {c}", key=f"b_{ag}_{c}", use_container_width=True):
                        st.session_state['nav_customer'] = c