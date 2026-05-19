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
    
    # --- 2. 제목 ---
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

    # 사진 대지 2페이지
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
        
        # 🌟 빈칸/누락 에러 방지를 위해 55개 열 강제 생성 및 패딩 (이 부분이 핵심 해결책!)
        cols = [f"Col_{i}" for i in range(55)] 
        cols[1] = "설치일" # B
        cols[2] = "AS기간" # C
        cols[3] = "고객명" # D
        cols[4] = "대표자" # E
        cols[5] = "연락처" # F
        cols[6] = "주소" # G
        cols[7] = "사육어종" # H
        
        # QM TEST (I~U)
        cols[8], cols[9], cols[10] = "용량(RT)", "냉매", "냉매량(kg)" # I, J, K
        cols[11], cols[12], cols[13] = "오일량(ℓ)", "기동전류(A)", "기동압력(저/고)" # L, M, N
        cols[14], cols[15], cols[16], cols[17] = "압력-저", "압력-고", "OCR-COMP", "OCR-PUMP" # O, P, Q, R
        cols[18], cols[19], cols[20] = "센서이상", "점검자", "QM비고" # S, T, U
        
        # 설치공사 (W~AE)
        cols[22], cols[23], cols[24], cols[25] = "메인전원(SQ)", "열원/규격", "부하/규격", "펌프비고" # W, X, Y, Z
        cols[26], cols[27], cols[28], cols[29], cols[30] = "순환방식", "배관재질", "사용조건", "시공대리점", "설치비고" # AA, AB, AC, AD, AE
        
        # 시운전 (AF~AL)
        cols[31], cols[32], cols[33], cols[34] = "가동시간", "시운전압력-저", "시운전압력-고", "시운전전류" # AF, AG, AH, AI
        cols[35], cols[36], cols[37] = "물온도-부하", "물온도-열원", "시운전비고" # AJ, AK, AL
        
        # 기타 정보
        cols[39] = "사업명" # AN
        cols[40] = "낙찰업체명" # AO
        cols[42] = "대리점" # AQ
        cols[44] = "제조프로젝트" # AS
        cols[45] = "제조오더" # AT
        cols[46] = "SERVICE No." # AU
        cols[47] = "QM사진" # AV
        cols[48] = "설치사진" # AW
        cols[49] = "시운전사진" # AX
        
        # 🌟 데이터 행 길이를 55열로 똑같이 강제 맞춤 (에러 완벽 차단)
        padded_data = []
        for row in data[5:]:
            padded_row = row + [""] * (55 - len(row))
            padded_data.append(padded_row[:55])
            
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
        edited_target = st.data_editor(target_df[show_cols], hide_index=True, use_container_width=True, disabled=['상태','제조프로젝트','제조오더','고객명','설치일','용량(RT)'])
        selected_rows = edited_target[edited_target['선택']]
        
        if not selected_rows.empty:
            default_capacity = " / ".join(selected_rows['용량(RT)'].astype(str).unique().tolist())
            
            with st.form("qm_form"):
                st.write(f"**QM TEST 결과 입력 (선택된 장비: {len(selected_rows)}대 일괄 적용)**")
                c1, c2, c3 = st.columns(3)
                qm_cap = c1.text_input("용량(RT)", value=default_capacity)
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
                qm_manager = c12.text_input("점검자(필수)", value="")
                qm_note = st.text_input("비고")
                
                st.markdown("**📷 QM TEST 현장 사진 업로드 (선택 / 여러 장 가능)**")
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

                            update_data = [safe_text(x) for x in [qm_cap, qm_ref, qm_ref_amt, qm_oil, qm_amp, qm_press, qm_plow, qm_phigh, qm_ocr_c, qm_ocr_p, qm_sensor, qm_manager, qm_note]]
                            for idx in selected_rows.index:
                                r_idx = target_df.loc[idx, 'row_index']
                                ws_equip.update(f"I{r_idx}:U{r_idx}", [update_data]) 
                                if qm_photo_urls:
                                    qm_photo_str = " \n ".join(qm_photo_urls) 
                                    ws_equip.update(f"AV{r_idx}", [[f"'{qm_photo_str}"]])
                                    
                            st.success(f"✅ {len(selected_rows)}대의 장비에 QM 데이터가 성공적으로 저장되었습니다.")
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
                        if auth_level in ["AS팀", "영업팀", "하이에어공조"]:
                            st.session_state['nav_agency'] = ag
                        st.rerun()
else:
    if st.button("🔙 목록으로 돌아가기"):
        st.session_state['nav_customer'] = "선택하세요"
        st.rerun()
        
    c_df = f_df[f_df['고객명'] == sel_cust]
    c_info = c_df.iloc[0]
    
    st.markdown(f"### 🏢 [{sel_cust}] 상세 내역")
    info_str = f"- **대표자:** {c_info['대표자']}\n- **연락처:** {c_info['연락처']}\n- **주소:** {c_info['주소']}"
    if equipment_type in ["해수열", "해수용 칠러"]: info_str += f"\n- **사육어종:** {c_info['사육어종']}"
    st.info(info_str)
    
    st.markdown("#### 📊 등록 장비 상세 제원 및 이력")
    
    df_as = load_as_data()
    cust_as = pd.DataFrame()
    if not df_as.empty and len(df_as.columns) > 1:
        cust_col_name = df_as.columns[1] 
        cust_as = df_as[df_as[cust_col_name] == sel_cust]
            
    st.markdown("**■ QM TEST 진행 내역**")
    qm_cols = ['SERVICE No.', '설치일', '제조오더', '용량(RT)', '냉매', '냉매량(kg)', '점검자', 'QM비고']
    existing_qm = [c for c in qm_cols if c in c_df.columns]
    st.dataframe(c_df[existing_qm], hide_index=True)
    
    st.markdown("**■ 대리점 설치공사 내역**")
    inst_cols = ['SERVICE No.', '설치일', '시공대리점', '메인전원(SQ)', '열원/규격', '부하/규격', '순환방식', '배관재질', '사용조건', '설치비고']
    existing_inst = [c for c in inst_cols if c in c_df.columns]
    st.dataframe(c_df[existing_inst], hide_index=True)
    
    st.markdown("**■ 시운전 내역**")
    test_cols = ['SERVICE No.', '가동시간', '시운전압력-저', '시운전압력-고', '시운전전류', '물온도-부하', '물온도-열원', '시운전비고']
    existing_test = [c for c in test_cols if c in c_df.columns]
    st.dataframe(c_df[existing_test], hide_index=True)
    
    st.markdown("**■ 장비 AS 및 시운전 리포트 (생성된 PDF 링크 클릭 시 열립니다)**")
    if not cust_as.empty:
        url_cols = {col: st.column_config.LinkColumn(col) for col in cust_as.columns if "url" in str(col).lower() or "사진" in str(col) or "pdf" in str(col).lower()}
        st.dataframe(cust_as, hide_index=True, use_container_width=True, column_config=url_cols)
    else:
        st.write("해당 업체의 AS/시운전 이력이 없습니다.")

    st.write("---")
    
    disp_df = c_df.copy()
    disp_df['AS만료일'] = disp_df.apply(lambda x: calc_expiry(x['설치일'], x['AS기간']), axis=1)
    
    disp_df['QM'] = disp_df['점검자'].apply(lambda x: "✅" if str(x).replace("'", "").strip() else "❌")
    disp_df['설치공사'] = disp_df['시공대리점'].apply(lambda x: "✅" if str(x).replace("'", "").strip() else "❌")
    
    def check_history(row, report_kind):
        if cust_as.empty: return "❌"
        cap = str(row.get('용량(RT)', '')).replace("'", "").strip()
        if not cap: return "✅" 
        if len(cust_as.columns) > 3:
            for summary in cust_as[cust_as.columns[3]]:
                if cap in str(summary) and report_kind in str(summary):
                    return "✅"
        return "❌"
        
    disp_df['AS이력'] = disp_df.apply(lambda r: check_history(r, "[SERVICE REPORT]"), axis=1)
    disp_df['시운전'] = disp_df.apply(lambda r: check_history(r, "[시운전 보고서]"), axis=1)
    disp_df.insert(0, "선택", False)
    
    st.markdown("#### ▶ **SERVICE/설치공사/시운전 대상 장비 선택**")
    st.caption("※ 표 안의 'SERVICE No.'를 더블클릭하여 수정 후 아래 [저장] 버튼을 누르면 일괄 반영됩니다. (장비 체크박스를 선택하면 하단에 갤러리와 폼이 열립니다.)")
    
    show_cols = ['선택', 'SERVICE No.', 'QM', '설치공사', '시운전', 'AS이력', '설치일', 'AS만료일', '용량(RT)', '냉매', '냉매량(kg)', '제조오더']
    edited_equip = st.data_editor(
        disp_df[show_cols], 
        hide_index=True, 
        use_container_width=True,
        disabled=['QM', '설치공사', '시운전', 'AS이력', '설치일', 'AS만료일', '용량(RT)', '냉매', '냉매량(kg)', '제조오더']
    )
    sel_equips = edited_equip[edited_equip['선택']]
    equip_info_str = " / ".join(sel_equips['용량(RT)'].astype(str).unique().tolist()) if not sel_equips.empty else ""

    if st.button("💾 수정한 SERVICE No. 일괄 저장"):
        with st.spinner("번호를 구글 시트에 업데이트 중입니다..."):
            update_count = 0
            for idx in disp_df.index:
                old_val = disp_df.loc[idx, 'SERVICE No.']
                new_val = edited_equip.loc[idx, 'SERVICE No.']
                if old_val != new_val:
                    r_idx = c_df.loc[idx, 'row_index']
                    ws_equip.update(f"AU{r_idx}", [[safe_text(new_val)]])
                    update_count += 1
            st.success(f"{update_count}건의 장비번호가 저장되었습니다!")
            st.cache_data.clear()
            st.rerun()
            
    if not sel_equips.empty:
        st.markdown("#### 📸 선택한 장비의 현장 사진 갤러리")
        tabs = st.tabs([f"장비 {row['SERVICE No.'] if row['SERVICE No.'] else '(번호없음)'}" for idx, row in sel_equips.iterrows()])
        for i, (idx, row) in enumerate(sel_equips.iterrows()):
            orig_row = c_df.loc[idx]
            with tabs[i]:
                qm_urls = [u.strip() for u in str(orig_row.get('QM사진', '')).replace('\n', ',').split(',') if 'http' in u]
                inst_urls = [u.strip() for u in str(orig_row.get('설치사진', '')).replace('\n', ',').split(',') if 'http' in u]
                test_urls = [u.strip() for u in str(orig_row.get('시운전사진', '')).replace('\n', ',').split(',') if 'http' in u]
                
                col_q, col_i, col_t = st.columns(3)
                with col_q:
                    st.markdown("**✔️ QM TEST 사진**")
                    if qm_urls:
                        with st.expander("📸 사진 보기"):
                            for u in qm_urls: st.image(u, use_container_width=True)
                    else: st.caption("등록된 사진 없음")
                with col_i:
                    st.markdown("**✔️ 설치공사 사진**")
                    if inst_urls:
                        with st.expander("📸 사진 보기"):
                            for u in inst_urls: st.image(u, use_container_width=True)
                    else: st.caption("등록된 사진 없음")
                with col_t:
                    st.markdown("**✔️ 시운전 사진**")
                    if test_urls:
                        with st.expander("📸 사진 보기"):
                            for u in test_urls: st.image(u, use_container_width=True)
                    else: st.caption("등록된 사진 없음")

    # --- 설치공사 입력 폼 ---
    if auth_level not in ["AS팀", "영업팀", "하이에어공조"] and not sel_equips.empty:
        with st.expander("🛠️ 설치공사 내역 입력 (대리점 전용)", expanded=False):
            with st.form("install_form"):
                ic1, ic2, ic3, ic4 = st.columns(4)
                i_main = ic1.text_input("메인전원(SQ)")
                i_heat = ic2.text_input("열원/규격")
                i_load = ic3.text_input("부하/규격")
                i_pump_note = ic4.text_input("비고(펌프)")
                
                ic5, ic6, ic7 = st.columns(3)
                i_circ = ic5.text_input("순환방식")
                i_pipe = ic6.text_input("배관재질(규격)")
                i_cond = ic7.text_input("사용조건(냉/난방)")
                
                ic8, ic9, ic10 = st.columns(3)
                i_installer = ic8.text_input("시공대리점(필수)", value=user_company)
                i_worker = ic9.text_input("시공자명(필수)")
                i_note2 = ic10.text_input("비고(설치)")
                
                st.markdown("**📷 설치공사 현장 사진 업로드 (선택 / 여러 장 가능)**")
                inst_photo_files = st.file_uploader("현장 사진 (JPG, PNG)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                
                if st.form_submit_button("설치공사 데이터 저장"):
                    if not i_installer.strip() or not i_worker.strip():
                        st.error("🚨 시공대리점과 시공자명을 모두 입력해야 저장할 수 있습니다.")
                    else:
                        with st.spinner("사진 및 데이터를 클라우드에 업로드 중입니다..."):
                            safe_wo = str(sel_equips['제조오더'].iloc[0]).replace("/", "_") if not sel_equips.empty else "미상"
                            inst_photo_urls = []
                            if inst_photo_files:
                                for f in inst_photo_files:
                                    try:
                                        res = cloudinary.uploader.upload(f, folder=f"INSTALL_PHOTOS/{safe_wo}", resource_type="image")
                                        inst_photo_urls.append(res.get("secure_url"))
                                    except: pass
                            
                            combined_installer = f"{i_installer.strip()} / {i_worker.strip()}"
                            update_data = [safe_text(x) for x in [i_main, i_heat, i_load, i_pump_note, i_circ, i_pipe, i_cond, combined_installer, i_note2]]
                            for idx in sel_equips.index:
                                r_idx = c_df.loc[idx, 'row_index']
                                ws_equip.update(f"W{r_idx}:AE{r_idx}", [update_data])
                                if inst_photo_urls:
                                    inst_photo_str = " \n ".join(inst_photo_urls)
                                    ws_equip.update(f"AW{r_idx}", [[f"'{inst_photo_str}"]]) 
                                    
                            st.success("설치공사 내역이 성공적으로 저장되었습니다.")
                            st.cache_data.clear()
                            st.rerun()

        # 🌟 시운전 입력 폼 신설
        with st.expander("⚙️ 시운전 내역 입력 (대리점 전용)", expanded=False):
            with st.form("testrun_form"):
                tc1, tc2, tc3, tc4 = st.columns(4)
                t_time = tc1.text_input("가동시간")
                t_plow = tc2.text_input("압력셋팅(저압)")
                t_phigh = tc3.text_input("압력셋팅(고압)")
                t_amp = tc4.text_input("기동전류(A)")
                
                tc5, tc6, tc7 = st.columns(3)
                t_tload = tc5.text_input("입출수 물온도(부하)")
                t_theat = tc6.text_input("입출수 물온도(열원)")
                t_note = tc7.text_input("비고")
                
                st.markdown("**📷 시운전 현장 사진 업로드 (선택 / 여러 장 가능)**")
                test_photo_files = st.file_uploader("시운전 사진 (JPG, PNG)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                
                if st.form_submit_button("시운전 데이터 저장"):
                    with st.spinner("데이터를 업로드 중입니다..."):
                        safe_wo = str(sel_equips['제조오더'].iloc[0]).replace("/", "_") if not sel_equips.empty else "미상"
                        test_photo_urls = []
                        if test_photo_files:
                            for f in test_photo_files:
                                try:
                                    res = cloudinary.uploader.upload(f, folder=f"TESTRUN_PHOTOS/{safe_wo}", resource_type="image")
                                    test_photo_urls.append(res.get("secure_url"))
                                except: pass
                        
                        update_data = [safe_text(x) for x in [t_time, t_plow, t_phigh, t_amp, t_tload, t_theat, t_note]]
                        for idx in sel_equips.index:
                            r_idx = c_df.loc[idx, 'row_index']
                            ws_equip.update(f"AF{r_idx}:AL{r_idx}", [update_data])
                            if test_photo_urls:
                                test_photo_str = " \n ".join(test_photo_urls)
                                ws_equip.update(f"AX{r_idx}", [[f"'{test_photo_str}"]])
                                
                        st.success("시운전 내역이 성공적으로 저장되었습니다.")
                        st.cache_data.clear()
                        st.rerun()

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).time()

    # --- AS/시운전 보고서 폼 (PDF) ---
    if auth_level in ["AS팀", "영업팀", "하이에어공조"] and not sel_equips.empty:
        with st.expander("📝 보고서 작성하기 (PDF 저장)", expanded=True):
            
            report_type = st.radio("보고서 종류 선택", ["SERVICE REPORT", "시운전 보고서"], horizontal=True)
            st.divider()
            
            with st.form("service_report_form", clear_on_submit=False):
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

                wk_1 = wk_2 = wk_3 = wk_4 = False
                charge_type = ""
                po_no = ""
                
                if report_type == "SERVICE REPORT":
                    st.markdown("**작업구분**")
                    work_cols = st.columns(6)
                    wk_1 = work_cols[0].checkbox("하자처리(전장)")
                    wk_2 = work_cols[1].checkbox("기계")
                    wk_3 = work_cols[2].checkbox("설비")
                    wk_4 = work_cols[3].checkbox("기타")

                    st.markdown("**요금청구 (단일 선택)**")
                    charge_type = st.radio("요금구분", ["고객", "유상", "무상"], horizontal=True, label_visibility="collapsed")
                    po_no = st.text_input("PO No 입력 (고객 선택 시)") if charge_type == "고객" else ""
                else:
                    st.markdown("**작업구분**")
                    st.checkbox("☑ 시운전 (자동 선택됨)", value=True, disabled=True)

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

                st.markdown("**📷 작업 사진 대지 업로드 (선택 사항)**")
                c_p1, c_p2 = st.columns(2)
                before_files = c_p1.file_uploader("작업 전 사진 (최대 2장)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                after_files = c_p2.file_uploader("완료 및 작업 후 사진 (최대 4장)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)

                st.divider()

                sig_col1, sig_col2 = st.columns(2)
                with sig_col1:
                    st.markdown("**담당직원 (이름 입력 시 자동 서명)**")
                    emp_name = st.text_input("담당직원 이름(필수)", value=user_info.get('이름', ''))
                        
                with sig_col2:
                    st.markdown("**확인자(소비자) 서명** (마우스/터치로 서명)")
                    agree_check = st.checkbox("**(필수) 본인은 A/S 및 시운전 작업에 대한 설명을 듣고 그 내용을 충분히 이해하였음을 확인합니다.**")
                    canvas_customer = st_canvas(
                        stroke_width=3, stroke_color="#000000", background_color="#FFFFFF",
                        height=150, width=350, drawing_mode="freedraw", key="customer_sig_canvas_v2",
                    )

                submit_report = st.form_submit_button(f"[{report_type}] 저장 및 전송")
                
            if submit_report:
                if not constructor.strip():
                    st.error("🚨 영업자/시공자 이름을 필수로 입력해야 저장할 수 있습니다.")
                elif not emp_name.strip():
                    st.error("🚨 담당직원 이름을 필수로 입력해야 저장할 수 있습니다.")
                elif edited_work.empty:
                    st.error("🚨 작업 내용을 1개 이상 입력해 주세요.")
                elif before_files and len(before_files) > 2:
                    st.error("🚨 작업 전 사진은 최대 2장까지만 가능합니다.")
                elif after_files and len(after_files) > 4:
                    st.error("🚨 작업 후 사진은 최대 4장까지만 가능합니다.")
                elif not agree_check:
                    st.error("🚨 필수 확인란(설명 이해 확인)에 체크해 주셔야 저장할 수 있습니다.")
                else:
                    edited_work.insert(0, "No", range(1, len(edited_work) + 1))
                    
                    with st.spinner("데이터 처리 및 PDF 생성 중입니다... (10~20초 소요)"):
                        sig_path = None
                        if canvas_customer.image_data is not None:
                            img_data = canvas_customer.image_data.astype('uint8')
                            if np.sum(img_data) > 0: 
                                img = Image.fromarray(img_data, 'RGBA')
                                sig_path = "temp_sig.png"
                                img.save(sig_path)

                        safe_report_type = report_type.replace(" ", "_")
                        safe_sel_cust = sel_cust.replace(" ", "_")
                        file_wo_str = str(sel_equips['제조오더'].iloc[0]).replace("/", "_") if not sel_equips.empty else "미상"
                        
                        def save_tmp(f):
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                img = Image.open(f)
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                img.thumbnail((800, 800))
                                img.save(tmp.name, format="JPEG", quality=70)
                                return tmp.name
                                
                        b_paths = [save_tmp(f) for f in before_files] if before_files else []
                        a_paths = [save_tmp(f) for f in after_files] if after_files else []

                        work_checked = []
                        if wk_1: work_checked.append("하자처리(전장)")
                        if wk_2: work_checked.append("기계")
                        if wk_3: work_checked.append("설비")
                        if wk_4: work_checked.append("기타")

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
                        
                        try:
                            pdf_bytes = create_service_report_pdf(report_type, report_data, edited_work, sig_path, b_paths, a_paths)
                            
                            all_photo_urls = []
                            if b_paths:
                                for path in b_paths:
                                    res = cloudinary.uploader.upload(path, folder=f"AS_PHOTOS/{file_wo_str}/Before", resource_type="image")
                                    all_photo_urls.append(res.get("secure_url"))
                            if a_paths:
                                for path in a_paths:
                                    res = cloudinary.uploader.upload(path, folder=f"AS_PHOTOS/{file_wo_str}/After", resource_type="image")
                                    all_photo_urls.append(res.get("secure_url"))
                            
                            photo_urls_str = "\n".join(all_photo_urls) if all_photo_urls else "첨부없음"

                            cloud_report_prefix = "SR" if report_type == "SERVICE REPORT" else "TR"
                            pdf_name_cloud = f"{cloud_report_prefix}_{file_wo_str}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            pdf_name_local = f"{report_type}_{sel_cust}_{file_wo_str}_{datetime.now().strftime('%Y%m%d')}.pdf"

                            upload_res_pdf = cloudinary.uploader.upload(
                                pdf_bytes, folder="SERVICE_REPORTS", resource_type="raw",
                                public_id=pdf_name_cloud
                            )
                            pdf_url = upload_res_pdf.get("secure_url")
                            
                            ws_as = sh.worksheet("AS내역")
                            summary_text = f"[{report_type}] 장비: {equip_info_str} / 내용: {edited_work.iloc[0]['작업내용']} 외"
                            new_row = [
                                datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
                                sel_cust,
                                ref_type, 
                                summary_text,
                                emp_name,
                                user_info['업체명'],
                                photo_urls_str,
                                pdf_url
                            ]
                            safe_new_row = [safe_text(item) for item in new_row]
                            ws_as.append_row(safe_new_row)
                            
                            st.success(f"✅ [{report_type}] 담당직원[{emp_name}] 명의로 클라우드에 완벽하게 저장되었습니다!")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                st.download_button(
                                    label="📥 내 PC/스마트폰으로 PDF 파일 다운로드", data=pdf_bytes,
                                    file_name=pdf_name_local, mime="application/pdf", use_container_width=True
                                )
                            with col_btn2:
                                st.link_button("☁️ 구글시트용 클라우드 PDF 링크 열기", pdf_url, use_container_width=True)
                            
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f"🚨 PDF 생성 또는 서버 저장에 실패했습니다. 관리자에게 문의하세요: {e}")