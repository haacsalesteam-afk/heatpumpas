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
import requests

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
            except: pass
            
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
        if y_curr > tbl_bottom - 10: break 
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
# 🌟 데이터 전처리 유틸리티 함수
# ==========================================
def safe_text(val):
    val_str = str(val).strip()
    if val_str.startswith(('=', '+', '-', '@')): return f"'{val_str}"
    return val_str

def parse_urls_safe(val):
    val_str = str(val).strip()
    if not val_str or val_str == 'nan': return []
    val_str = val_str.replace("'", "").replace('"', "")
    urls = []
    for token in val_str.replace('\n', ' ').replace(',', ' ').split():
        if token.startswith('http'): urls.append(token.strip())
    return urls

def calc_expiry(install_date, years):
    try:
        dt = datetime.strptime(str(install_date).replace('.', '-').strip(), "%Y-%m-%d")
        return dt.replace(year=dt.year + int(str(years).replace('년','').strip())).strftime("%Y-%m-%d")
    except: return "정보없음"

def enrich_as_requests_display(df):
    """AS접수현황 목록용 표시 컬럼 추가."""
    if df.empty:
        return df
    out = df.copy()
    out['접수사진'] = out['사진링크'].apply(lambda v: "✅" if parse_urls_safe(v) else "❌")
    out['증상요약'] = out['증상'].apply(
        lambda x: (str(x)[:50] + "…") if len(str(x).strip()) > 50 else str(x).strip()
    )
    return out

def default_ref_index(equip_ref, ref_options):
    """장비 시트 냉매 값 → REPORT 냉매구분 기본 선택 인덱스."""
    val = str(equip_ref).replace("'", "").strip()
    if not val:
        return len(ref_options) - 1
    norm = val.upper().replace(" ", "").replace("-", "")
    for i, opt in enumerate(ref_options):
        if opt == "기타/선택안함":
            continue
        if opt.upper().replace("-", "") == norm or val == opt:
            return i
    return len(ref_options) - 1

def render_as_request_summary_card(row):
    """선택된 AS 접수 건 요약."""
    has_photo = bool(parse_urls_safe(row.get('사진링크', '')))
    st.markdown("#### 📋 선택한 접수 건")
    st.markdown(
        f"**접수사진** {'✅' if has_photo else '❌'} · **접수** {row.get('접수일시', '')} · "
        f"**연락처** {row.get('연락처', '')} · **고객** {row.get('고객명', '')} · "
        f"**장비** {row.get('제조오더', '')} · **담당** {row.get('담당자명', '')} ({row.get('직함', '')})"
    )
    with st.expander("증상 / 요청사항 전체 보기", expanded=True):
        st.write(row.get('증상', '') or "(내용 없음)")

# ==========================================
# 1. 초기 설정 및 클라우드 연결
# ==========================================
st.set_page_config(page_title="히트펌프 장비 관리 시스템", layout="wide")

try:
    try: service_info = json.load(open('hallowed-winter-493604-k9-234626bef11e.json'))
    except FileNotFoundError:
        secret_data = st.secrets["gcp_service_account"]
        service_info = json.loads(secret_data) if isinstance(secret_data, str) else dict(secret_data)
        
    gc = gspread.service_account_from_dict(service_info)
    global sh 
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
# 2. 세션 상태 관리 및 데이터 로드
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = None
if 'nav_agency' not in st.session_state: st.session_state['nav_agency'] = "전체"
if 'nav_customer' not in st.session_state: st.session_state['nav_customer'] = "선택하세요"
if 'nav_sido' not in st.session_state: st.session_state['nav_sido'] = "전체"
if 'nav_sigungu' not in st.session_state: st.session_state['nav_sigungu'] = "전체"

@st.cache_data(ttl=3600)
def load_sheet_data(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_values()
        if len(data) < 5: return pd.DataFrame()
        
        cols = [f"Col_{i}" for i in range(60)] 
        cols[1], cols[2], cols[3], cols[4], cols[5], cols[6], cols[7] = "설치일", "AS기간", "고객명", "대표자", "연락처", "주소", "사육어종"
        cols[8], cols[9], cols[10] = "용량(RT)", "냉매", "냉매량(kg)"
        cols[11], cols[12], cols[13], cols[14] = "오일량(ℓ)", "기동전류(A)", "가동압력(저압)", "가동압력(고압)"
        cols[15], cols[16], cols[17], cols[18] = "압력-저", "압력-고", "OCR-COMP", "OCR-PUMP"
        cols[19], cols[20], cols[21] = "센서이상", "점검자", "검사 완료일"
        cols[22] = "비고(QM)"
        cols[23], cols[24], cols[25], cols[26] = "메인전원(SQ)", "열원/규격", "부하/규격", "비고(펌프)"
        cols[27], cols[28], cols[29], cols[30], cols[31] = "순환방식", "배관재질", "사용조건", "시공대리점", "비고(설치)"
        cols[32], cols[33], cols[34], cols[35] = "가동시간", "시운전압력-저", "시운전압력-고", "시운전전류"
        cols[36], cols[37], cols[38] = "물온도-부하", "물온도-열원", "비고(시운전)"
        cols[40], cols[41], cols[42], cols[44], cols[45], cols[46], cols[47], cols[48], cols[49] = "사업명", "낙찰업체명", "대리점", "제조프로젝트", "제조오더", "SERVICE No.", "QM사진", "설치사진", "시운전사진"
        
        padded_data = [row + [""] * (60 - len(row)) for row in data[5:]]
        df = pd.DataFrame(padded_data, columns=cols)
        df['row_index'] = range(6, 6 + len(df))
        df['SERVICE No.'] = df['SERVICE No.'].astype(str).str.replace(r"^'", "", regex=True)
        
        df['대리점'] = df['대리점'].apply(lambda x: "미정" if not str(x).strip() or str(x).lower() == "nan" else str(x).strip())
        df['고객명'] = df['고객명'].apply(lambda x: "미정" if not str(x).strip() or str(x).lower() == "nan" else str(x).strip())
        df['시/도'] = df['주소'].apply(lambda x: str(x).split()[0] if str(x).strip() else "미상")
        df['시/군/구'] = df['주소'].apply(lambda x: str(x).split()[1] if len(str(x).split()) > 1 else "미상")
        return df  
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_as_data():
    try:
        ws_as = sh.worksheet("AS내역")
        data = ws_as.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        header_names = ["일시", "고객명", "냉매", "작업내용", "담당자", "업체명", "사진링크", "PDF링크"]
        start_idx = 1
        for i, r in enumerate(data):
            if "일시" in str(r) or "고객명" in str(r):
                start_idx = i + 1
                break
        return pd.DataFrame([row + [""]*(8-len(row)) for row in data[start_idx:]], columns=header_names)
    except: return pd.DataFrame()

@st.cache_data(ttl=30)
def load_as_requests():
    try:
        ws = sh.worksheet("AS접수현황")
        data = ws.get_all_values()
        if len(data) < 2: return pd.DataFrame(columns=["접수일시", "제조오더", "고객명", "담당자명", "직함", "연락처", "증상", "사진링크", "처리상태"])
        return pd.DataFrame([row + [""]*(9-len(row)) for row in data[1:]], columns=["접수일시", "제조오더", "고객명", "담당자명", "직함", "연락처", "증상", "사진링크", "처리상태"])
    except: return pd.DataFrame(columns=["접수일시", "제조오더", "고객명", "담당자명", "직함", "연락처", "증상", "사진링크", "처리상태"])

KST = timezone(timedelta(hours=9))

# ==========================================
# 📱 [QR 화면] 고객 AS 접수 및 메뉴얼 (라우팅 1)
# ==========================================
def show_qr_customer_view(wo_number):
    st.title("🛠 하이에어공조 장비 지원 센터")
    
    found_sheet = None
    target_machine = pd.DataFrame()
    df_equip = pd.DataFrame()
    
    clean_wo = str(wo_number).replace("'", "").replace('"', "").strip().upper()
    
    for s_name in ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"]:
        temp_df = load_sheet_data(s_name)
        if not temp_df.empty:
            sheet_wos = temp_df['제조오더'].astype(str).str.replace(r"^'", "", regex=True).str.replace('"', "").str.strip().str.upper()
            match = temp_df[sheet_wos == clean_wo]
            if not match.empty:
                found_sheet = s_name
                df_equip = temp_df
                target_machine = match
                break
                
    if target_machine.empty:
        st.error("❌ 시스템에 등록되지 않은 장비입니다.")
        st.info("💡 방금 시트에 입력하셨다면 아래 [최신 데이터 동기화] 버튼을 눌러주세요.")
        if st.button("🔄 최신 데이터 동기화 (캐시 강제 초기화)", type="primary"):
            st.cache_data.clear()
            st.rerun()
            
        # 3. 관리자만 디버깅용 시트 데이터 조회가 가능하도록 수정
        # 2. 하드코딩되었던 "폐수열" 대신 전체 시트를 스캔하도록 로직 수정
        if st.session_state.get('logged_in', False):
            with st.expander("🔍 (관리자용) 원인 파악을 위한 시트 데이터 확인"):
                st.write(f"👉 **현재 찾고 있는 번호:** `{clean_wo}`")
                for debug_sheet_name in ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"]:
                    debug_df = load_sheet_data(debug_sheet_name)
                    if not debug_df.empty:
                        debug_wos = debug_df['제조오더'].astype(str).str.replace(r"^'", "", regex=True).str.strip().tolist()
                        valid_wos = [w for w in debug_wos if w and w != "nan" and w != "None"]
                        st.write(f"👉 **현재 앱이 인식한 [{debug_sheet_name}] 시트의 제조오더 목록:**")
                        st.write(valid_wos)
                st.caption("※ 만약 위 목록에 찾으시는 번호가 없다면, 구글 시트에 데이터가 올바르게 저장되지 않은 것입니다.")
        return
        
    machine_info = target_machine.iloc[0]
    customer_name = str(machine_info.get('고객명', '')).strip()
    if not customer_name or customer_name.lower() == "nan": customer_name = "미정"
        
    st.success(f"✅ 납품처: **{customer_name}** | 장비번호: {wo_number}")
    st.divider()
    
    if 'qr_menu' not in st.session_state: 
        st.session_state['qr_menu'] = 'main'

    if st.session_state['qr_menu'] == 'main':
        st.markdown("### 👆 원하시는 메뉴를 선택하세요")
        c1, c2, c3 = st.columns(3)
        if c1.button("📖 장비 메뉴얼 조회", use_container_width=True): 
            st.session_state['qr_menu'] = 'manual'
            st.rerun()
        if c2.button("📝 신규 AS 접수", use_container_width=True): 
            st.session_state['qr_menu'] = 'as'
            st.rerun()
        if c3.button("⚙️ 관리자 모드", use_container_width=True): 
            st.query_params.clear()
            st.session_state['qr_menu'] = 'main'
            st.rerun()

    elif st.session_state['qr_menu'] == 'manual':
        if st.button("⬅️ 뒤로 가기"): 
            st.session_state['qr_menu'] = 'main'
            st.rerun()
        st.subheader("📚 장비별 메뉴얼 다운로드")
        col1, col2, col3 = st.columns(3)
        with col1: 
            st.link_button("📥 해수열 메뉴얼", "https://drive.google.com/file/d/1nOr2r4lanpq2BZ6Krtxy5khypFysNpr_/view?usp=drive_link", use_container_width=True)
        with col2: 
            st.link_button("📥 폐수열 메뉴얼", "https://drive.google.com/file/d/1dWaLqDrhfUXFGeCKXwGSIaW-2enQc8Ls/view?usp=drive_link", use_container_width=True)
        with col3: 
            st.link_button("📥 김공장 메뉴얼", "https://drive.google.com/file/d/1QlXJuk3ltj7tWLaqvjx4yHPOJJOwlG87/view?usp=drive_link", use_container_width=True)

    elif st.session_state['qr_menu'] == 'as':
        if st.button("⬅️ 뒤로 가기"): 
            st.session_state['qr_menu'] = 'main'
            st.rerun()
        
        all_wo = []
        if customer_name == "미정":
            all_wo = [wo_number]
        else:
            for s_name in ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"]:
                t_df = load_sheet_data(s_name)
                if not t_df.empty:
                    cust_wos = t_df[t_df['고객명'] == customer_name]['제조오더'].tolist()
                    all_wo.extend(cust_wos)
            all_wo = list(set(all_wo))
            if wo_number not in all_wo: all_wo.insert(0, wo_number)
        
        st.subheader("📝 신규 AS 접수 신청")
        with st.form("as_request_form"):
            selected_wos = st.multiselect("대상 장비 선택", options=all_wo, default=[wo_number])
            req_cust_name = st.text_input("고객명 (수정가능)", value=customer_name)
            req_manager = st.text_input("담당자명 (필수)")
            req_title = st.text_input("담당자 직함 (선택)")
            req_phone = st.text_input("담당자 연락처 (필수)")
            
            # 1. 문제 증상 선택 및 추가 기입으로 기능 분리
            st.markdown("**문제 증상 및 요청사항**")
            issue_type = st.radio(
                "주요 증상 선택", 
                ["고압", "압축기 과전류", "펌프이상", "물흐름이상", "기타"], 
                horizontal=True
            )
            req_issue_detail = st.text_area("추가 상세내용 기입")
            
            # 4. 사진 첨부 문구에 에러 화면 첨부 필수 안내 추가
            req_photos = st.file_uploader("📸 현장 사진 첨부 (최대 5장) ※ 장비 에러 화면 첨부 필수", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
            
            if st.form_submit_button("AS 접수 완료하기"):
                if not req_manager.strip() or not req_phone.strip() or not selected_wos: 
                    st.error("필수 입력사항을 확인해주세요.")
                elif req_photos and len(req_photos) > 5: 
                    st.error("사진은 최대 5장까지 가능합니다.")
                else:
                    with st.spinner("접수 중..."):
                        photo_urls = []
                        if req_photos:
                            folder_path = f"AS_REQUESTS/{req_cust_name}_{datetime.now(KST).strftime('%Y%m%d')}/BEFORE_AS"
                            for f in req_photos:
                                try: photo_urls.append(cloudinary.uploader.upload(f, folder=folder_path, resource_type="image").get("secure_url"))
                                except: pass
                        
                        try: ws_req = sh.worksheet("AS접수현황")
                        except: ws_req = sh.add_worksheet("AS접수현황", 100, 9); ws_req.append_row(["접수일시", "제조오더", "고객명", "담당자명", "직함", "연락처", "증상", "사진링크", "처리상태"])
                        
                        # 라디오 버튼 선택값과 텍스트 내용을 합쳐서 DB에 저장
                        req_issue_combined = f"[{issue_type}] {req_issue_detail}".strip()
                        
                        ws_req.append_row([safe_text(x) for x in [
                            datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), 
                            ", ".join(selected_wos), 
                            req_cust_name, 
                            req_manager, 
                            req_title, 
                            req_phone, 
                            req_issue_combined, 
                            " \n ".join(photo_urls), 
                            "접수대기"
                        ]])
                        st.success("🎉 AS 접수가 정상 완료되었습니다!")
# ==========================================
# 🔲 [관리자] 통합 대시보드 화면 (라우팅 2)
# ==========================================
def show_admin_view():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    if 'user_info' not in st.session_state: st.session_state['user_info'] = {}
    if 'nav_agency' not in st.session_state: st.session_state['nav_agency'] = "전체"
    if 'nav_sido' not in st.session_state: st.session_state['nav_sido'] = "전체"
    if 'nav_sigungu' not in st.session_state: st.session_state['nav_sigungu'] = "전체"
    if 'nav_customer' not in st.session_state: st.session_state['nav_customer'] = "선택하세요"

    if not st.session_state['logged_in']:
        st.markdown("### 🔲 하이에어공조 장비 관리 시스템")
        with st.form("login_form"):
            user_id, user_pw = st.text_input("아이디"), st.text_input("비밀번호", type="password")
            if st.form_submit_button("Login"):
                try:
                    df_acc = pd.DataFrame(sh.worksheet("계정관리").get_all_values()[2:], columns=sh.worksheet("계정관리").get_all_values()[1])
                    user_row = df_acc[(df_acc['ID'].str.strip() == user_id.strip()) & (df_acc['PW'].str.strip() == user_pw.strip())]
                    if not user_row.empty:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user_row.iloc[0].to_dict()
                        st.rerun()
                    else: st.error("🚨 계정 정보가 일치하지 않습니다.")
                except Exception as e: st.error(f"연결 실패: {e}")
        st.stop()

    user_info = st.session_state['user_info']
    auth_level, user_company = user_info.get('구분', user_info.get('권한', '')), user_info.get('업체명', '')

    col1, col2 = st.columns([8, 2])
    col1.markdown(f"### 🔲 장비 관리 시스템 (접속: {user_company})")
    if col2.button("로그아웃"):
        for key in ['logged_in', 'user_info', 'nav_agency', 'nav_customer', 'nav_sido', 'nav_sigungu', 'active_filtered_wo']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

    # -----------------------------------------------------------------
    # 🌟 🚨 화면 모드 분리 (영업팀은 무조건 전체 내역)
    # -----------------------------------------------------------------
    as_view_roles = ["AS팀", "하이에어공조"]
    if auth_level in as_view_roles:
        as_view_mode = st.radio(
            "화면 모드",
            ["🚨 AS 접수 내역 (신규 처리)", "📋 전체 장비 내역 (조회 및 검색)"],
            horizontal=True,
            help="접수 내역: 고객 QR 접수 건 확인·처리 | 전체 내역: 장비 검색·보고서 작성",
        )
    else:
        as_view_mode = "📋 전체 장비 내역 (조회 및 검색)"

    equipment_type = "해수열"
    sel_cust = "선택하세요"
    show_detail = False
    f_df = pd.DataFrame()
    staff_roles = ["AS팀", "영업팀", "하이에어공조"]

    # ==========================================
    # 모드 1: AS 접수 내역 (신규 처리)
    # ==========================================
    if as_view_mode == "🚨 AS 접수 내역 (신규 처리)":
        st.markdown("### 🚨 실시간 고객 AS 접수 현황")
        st.info(
            "**처리 순서** ① 목록에서 **처리선택** 체크 → ② **증상** 확인 → "
            "③ 하단 **보고서 작성** → ④ 저장 시 **처리완료**"
        )
        req_df = load_as_requests()
        if not req_df.empty:
            pending = enrich_as_requests_display(req_df[req_df['처리상태'] == '접수대기'].copy())
            completed = enrich_as_requests_display(req_df[req_df['처리상태'] == '처리완료'].copy())
            
            if not pending.empty:
                st.caption(f"접수 대기 **{len(pending)}건**")
                pending.insert(0, "선택", False)
                display_cols = [
                    "선택", "접수사진", "접수일시", "제조오더", "고객명",
                    "담당자명", "연락처", "증상요약", "처리상태",
                ]
                edited_req = st.data_editor(
                    pending[display_cols],
                    hide_index=True,
                    use_container_width=True,
                    key="dashboard_as_req_table",
                    column_config={
                        "선택": st.column_config.CheckboxColumn(
                            "처리선택",
                            help="체크하면 아래에 접수 상세·장비 정보·보고서 폼이 열립니다",
                            default=False,
                        ),
                        "접수사진": st.column_config.TextColumn("접수사진", disabled=True, width="small"),
                        "접수일시": st.column_config.TextColumn("접수일시", disabled=True),
                        "제조오더": st.column_config.TextColumn("제조오더", disabled=True),
                        "고객명": st.column_config.TextColumn("고객명", disabled=True),
                        "담당자명": st.column_config.TextColumn("담당자", disabled=True),
                        "연락처": st.column_config.TextColumn("연락처", disabled=True),
                        "증상요약": st.column_config.TextColumn("증상(요약)", disabled=True),
                        "처리상태": st.column_config.TextColumn("상태", disabled=True),
                    },
                )
                
                selected_req = edited_req[edited_req['선택']]
                if not selected_req.empty:
                    orig_idx = selected_req.index[-1]
                    req_row = pending.loc[orig_idx]
                    render_as_request_summary_card(req_row)
                    st.session_state['linked_as_request'] = req_row.to_dict()

                    req_info = selected_req.iloc[-1]
                    raw_wos = [w.strip() for w in str(req_info['제조오더']).split(',') if w.strip()]
                    if raw_wos:
                        target_wo = raw_wos[0]
                        found_sheet = None
                        for s_name in ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"]:
                            test_df = load_sheet_data(s_name)
                            if not test_df.empty and target_wo in test_df['제조오더'].astype(str).values:
                                found_sheet = s_name
                                break
                        
                        if found_sheet:
                            equipment_type = found_sheet
                            df_equip = load_sheet_data(equipment_type)
                            ws_equip = sh.worksheet(equipment_type)
                            f_df = df_equip
                            m_row = df_equip[df_equip['제조오더'] == target_wo].iloc[0]
                            sel_cust = m_row['고객명']
                            show_detail = True
                            
                            if st.session_state.get('last_clicked_req') != target_wo:
                                st.session_state['last_clicked_req'] = target_wo
                                st.session_state['active_filtered_wo'] = target_wo
                        else:
                            st.warning("해당 장비번호를 전체 시트에서 찾을 수 없습니다.")
                else:
                    st.session_state['last_clicked_req'] = None
                    st.session_state['active_filtered_wo'] = None
                    st.session_state.pop('linked_as_request', None)
            else:
                st.success("🎉 현재 대기 중인 AS 접수 건이 없습니다.")
                st.session_state['active_filtered_wo'] = None
            
            with st.expander("✅ 완료 처리된 건 보기", expanded=False):
                if not completed.empty:
                    done_cols = ["접수사진", "접수일시", "제조오더", "고객명", "담당자명", "증상요약", "처리상태"]
                    st.dataframe(completed[done_cols], hide_index=True, use_container_width=True)
                else:
                    st.caption("완료된 접수 내역이 없습니다.")
        else:
            st.info("AS 접수 데이터가 없습니다.")

    # ==========================================
    # 모드 2: 전체 장비 내역 (조회 및 검색)
    # ==========================================
    elif as_view_mode == "📋 전체 장비 내역 (조회 및 검색)":
        st.write("---")
        equipment_type = st.radio("장비 구분", ["해수열", "폐수열", "공기열", "건조기(김공장)", "어선용"], horizontal=True, key='admin_equip_type')
        df_equip = load_sheet_data(equipment_type)
        if df_equip.empty:
            st.warning("⚠️ 데이터를 가져오지 못했습니다. 새로고침 해주세요.")
            st.stop()
        ws_equip = sh.worksheet(equipment_type)

        if auth_level == "QM팀":
            st.markdown("#### 🛠️ QM TEST 결과 입력")
            ref_options = ["R-134A", "R-407C", "R-22", "A-507"]
            proj_list = sorted([x for x in df_equip['제조프로젝트'].unique() if str(x).strip()])
            sel_proj = st.selectbox("제조프로젝트 선택", ["전체"] + proj_list)
            target_df = df_equip.copy() if sel_proj == "전체" else df_equip[df_equip['제조프로젝트'] == sel_proj].copy()
            
            if not target_df.empty:
                target_df.insert(0, "선택", False)
                target_df.insert(1, "상태", target_df['점검자'].apply(lambda x: "✅ 완료" if str(x).replace("'", "").strip() else "❌ 미입력"))
                show_cols = ['선택', '상태', '제조프로젝트', '제조오더', '고객명', '검사 완료일', '용량(RT)', '점검자']
                edited_target = st.data_editor(target_df[show_cols], hide_index=True, use_container_width=True, disabled=['상태','제조프로젝트','제조오더','고객명','검사 완료일','용량(RT)', '점검자'])
                selected_rows = edited_target[edited_target['선택']]
                
                if not selected_rows.empty:
                    tabs = st.tabs([f"장비 {row['제조오더']}" for idx, row in selected_rows.iterrows()])
                    for i, (idx, row) in enumerate(selected_rows.iterrows()):
                        orig_row = target_df.loc[idx].to_dict()
                        with tabs[i]:
                            qm_urls, inst_urls, test_urls = parse_urls_safe(orig_row.get('QM사진', '')), parse_urls_safe(orig_row.get('설치사진', '')), parse_urls_safe(orig_row.get('시운전사진', ''))
                            cq, ci, ct = st.columns(3)
                            with cq:
                                st.markdown("**✔️ QM TEST 사진**")
                                if qm_urls:
                                    with st.expander("📸 보기"):
                                        for u in qm_urls: st.image(u, use_container_width=True)
                                else: st.caption("사진 없음")
                            with ci:
                                st.markdown("**✔️ 설치공사 사진**")
                                if inst_urls:
                                    with st.expander("📸 보기"):
                                        for u in inst_urls: st.image(u, use_container_width=True)
                                else: st.caption("사진 없음")
                            with ct:
                                st.markdown("**✔️ 시운전 사진**")
                                if test_urls:
                                    with st.expander("📸 보기"):
                                        for u in test_urls: st.image(u, use_container_width=True)
                                else: st.caption("사진 없음")
                    st.write("---")
                    first_row = target_df.loc[selected_rows.index[0]].to_dict()
                    is_done = str(first_row.get('점검자', '')).replace("'", "").strip() != ""
                    sel_key = "-".join(selected_rows.index.astype(str))
                    if st.session_state.get('qm_sel_key') != sel_key:
                        st.session_state['qm_sel_key'] = sel_key; st.session_state['qm_edit_mode'] = False
                    
                    if is_done and not st.session_state.get('qm_edit_mode', False):
                        st.success("✅ 이미 QM TEST 결과가 입력된 장비입니다.")
                        c1, c2, c3 = st.columns(3)
                        c1.text_input("용량(RT)", value=str(first_row.get('용량(RT)', '')), disabled=True)
                        c2.text_input("냉매", value=str(first_row.get('냉매', '')), disabled=True)
                        c3.text_input("냉매량(kg)", value=str(first_row.get('냉매량(kg)', '')), disabled=True)
                        c4, c5, c6, c7 = st.columns(4)
                        c4.text_input("오일량(ℓ)", value=str(first_row.get('오일량(ℓ)', '')), disabled=True)
                        c5.text_input("기동전류(A)", value=str(first_row.get('기동전류(A)', '')), disabled=True)
                        c6.text_input("가동압력(저압)", value=str(first_row.get('가동압력(저압)', '')), disabled=True)
                        c7.text_input("가동압력(고압)", value=str(first_row.get('가동압력(고압)', '')), disabled=True)
                        c8, c9, c10, c11 = st.columns(4)
                        c8.text_input("압력셋팅-저압", value=str(first_row.get('압력-저', '')), disabled=True)
                        c9.text_input("압력셋팅-고압", value=str(first_row.get('압력-고', '')), disabled=True)
                        c10.text_input("OCR-COMP", value=str(first_row.get('OCR-COMP', '')), disabled=True)
                        c11.text_input("OCR-PUMP", value=str(first_row.get('OCR-PUMP', '')), disabled=True)
                        c12, c13, c14 = st.columns(3)
                        c12.text_input("센서류 이상유무", value=str(first_row.get('센서이상', '')), disabled=True)
                        c13.text_input("점검자", value=str(first_row.get('점검자', '')), disabled=True)
                        c14.text_input("검사 완료일", value=str(first_row.get('검사 완료일', '')), disabled=True)
                        st.text_input("비고(QM)", value=str(first_row.get('비고(QM)', '')), disabled=True)
                        if st.button("✏️ 결과 수정하기"): st.session_state['qm_edit_mode'] = True; st.rerun()
                    else:
                        with st.form("qm_form"):
                            st.write("**QM TEST 결과 입력**")
                            c1, c2, c3 = st.columns(3)
                            qm_cap = c1.text_input("용량(RT)", value=str(first_row.get('용량(RT)', '')))
                            qm_ref = c2.selectbox("냉매", ref_options, index=ref_options.index(str(first_row.get('냉매', ''))) if str(first_row.get('냉매', '')) in ref_options else 0)
                            qm_ref_amt = c3.text_input("냉매량(kg)", value=str(first_row.get('냉매량(kg)', '')))
                            c4, c5, c6, c7 = st.columns(4)
                            qm_oil = c4.text_input("오일량(ℓ)", value=str(first_row.get('오일량(ℓ)', '')))
                            qm_amp = c5.text_input("기동전류(A)", value=str(first_row.get('기동전류(A)', '')))
                            qm_press_low = c6.text_input("가동압력(저압)", value=str(first_row.get('가동압력(저압)', '')))
                            qm_press_high = c7.text_input("가동압력(고압)", value=str(first_row.get('가동압력(고압)', '')))
                            c8, c9, c10, c11 = st.columns(4)
                            qm_plow = c8.text_input("압력셋팅-저압", value=str(first_row.get('압력-저', '')))
                            qm_phigh = c9.text_input("압력셋팅-고압", value=str(first_row.get('압력-고', '')))
                            qm_ocr_c = c10.text_input("OCR-COMP", value=str(first_row.get('OCR-COMP', '')))
                            qm_ocr_p = c11.text_input("OCR-PUMP", value=str(first_row.get('OCR-PUMP', '')))
                            c12, c13, c14 = st.columns(3)
                            qm_sensor = c12.radio("센서류 이상유무", ["정상", "이상"], horizontal=True, index=0 if str(first_row.get('센서이상', '')) != "이상" else 1)
                            qm_manager = c13.text_input("점검자(필수)", value="")
                            qm_date = c14.date_input("검사 완료일", value=datetime.now(KST).date())
                            qm_note = st.text_input("비고(QM)", value=str(first_row.get('비고(QM)', '')))
                            qm_photo_files = st.file_uploader("📷 추가 현장 사진 업로드", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                            if st.form_submit_button("QM 데이터 저장"):
                                if not qm_manager.strip(): st.error("🚨 점검자를 입력해 주세요.")
                                else:
                                    with st.spinner("처리 중..."):
                                        qm_photo_urls = []
                                        safe_wo = str(selected_rows['제조오더'].iloc[0]).replace("/", "_") if not selected_rows.empty else "미상"
                                        if qm_photo_files:
                                            for f in qm_photo_files:
                                                try: qm_photo_urls.append(cloudinary.uploader.upload(f, folder=f"QM_PHOTOS/{safe_wo}", resource_type="image").get("secure_url"))
                                                except: pass
                                        update_data = [safe_text(x) for x in [qm_cap, qm_ref, qm_ref_amt, qm_oil, qm_amp, qm_press_low, qm_press_high, qm_plow, qm_phigh, qm_ocr_c, qm_ocr_p, qm_sensor, qm_manager, qm_date.strftime("%Y-%m-%d"), qm_note]]
                                        for idx in selected_rows.index:
                                            ws_equip.update(f"I{target_df.loc[idx, 'row_index']}:W{target_df.loc[idx, 'row_index']}", [update_data]) 
                                            final = parse_urls_safe(str(target_df.loc[idx, 'QM사진']))
                                            if qm_photo_urls: final.extend(qm_photo_urls)
                                            if final: ws_equip.update(f"AU{target_df.loc[idx, 'row_index']}", [[f"'{' \n '.join(final)}'"]])
                                        st.success("데이터 저장 완료!"); st.session_state['qm_edit_mode'] = False; st.cache_data.clear(); st.rerun()
            st.stop()

        # --- 대리점 / AS팀 / 영업팀 조회 화면 필터링 ---
        search_c1, search_c2, search_c3, search_c4 = st.columns([2, 2, 2, 3])
        if auth_level in staff_roles:
            agencies = sorted([a for a in df_equip['대리점'].unique() if str(a).strip()])
            ag_idx = agencies.index(st.session_state['nav_agency']) + 1 if st.session_state['nav_agency'] in agencies else 0
            sel_agency = search_c1.selectbox("대리점", ["전체"] + agencies, index=ag_idx)
            if st.session_state['nav_agency'] != sel_agency:
                st.session_state['nav_agency'] = sel_agency; st.session_state['nav_sido'] = st.session_state['nav_sigungu'] = "전체"; st.session_state['nav_customer'] = "선택하세요"; st.rerun()
            f_df = df_equip[df_equip['대리점'] == sel_agency] if sel_agency != "전체" else df_equip
            
            sido_list = sorted([x for x in f_df['시/도'].unique() if x != "미상"])
            sel_sido = search_c2.selectbox("시/도", ["전체"] + sido_list, index=sido_list.index(st.session_state['nav_sido'])+1 if st.session_state['nav_sido'] in sido_list else 0)
            if st.session_state['nav_sido'] != sel_sido:
                st.session_state['nav_sido'] = sel_sido; st.session_state['nav_sigungu'] = "전체"; st.session_state['nav_customer'] = "선택하세요"; st.rerun()
            f_df = f_df[f_df['시/도'] == sel_sido] if sel_sido != "전체" else f_df
            
            sigungu_list = sorted([x for x in f_df['시/군/구'].unique() if x != "미상"])
            sel_sigungu = search_c3.selectbox("시/군/구", ["전체"] + sigungu_list, index=sigungu_list.index(st.session_state['nav_sigungu'])+1 if st.session_state['nav_sigungu'] in sigungu_list else 0)
            if st.session_state['nav_sigungu'] != sel_sigungu:
                st.session_state['nav_sigungu'] = sel_sigungu; st.session_state['nav_customer'] = "선택하세요"; st.rerun()
            f_df = f_df[f_df['시/군/구'] == sel_sigungu] if sel_sigungu != "전체" else f_df
        else:
            search_c1.text_input("대리점", value=user_company, disabled=True)
            search_c2.text_input("시/도", value="전체", disabled=True)
            search_c3.text_input("시/군/구", value="전체", disabled=True)
            f_df = df_equip[df_equip['대리점'] == user_company]

        customers = sorted([c for c in f_df['고객명'].unique() if str(c).strip()])
        sel_cust = search_c4.selectbox("고객명", ["선택하세요"] + customers, index=customers.index(st.session_state['nav_customer'])+1 if st.session_state['nav_customer'] in customers else 0)
        
        if st.session_state['nav_customer'] != sel_cust:
            st.session_state['nav_customer'] = sel_cust
            if sel_cust != "선택하세요" and auth_level in staff_roles:
                c_row = f_df[f_df['고객명'] == sel_cust].iloc[0]
                st.session_state['nav_agency'], st.session_state['nav_sido'], st.session_state['nav_sigungu'] = c_row['대리점'], c_row['시/도'], c_row['시/군/구']
            st.rerun()

        if sel_cust == "선택하세요":
            st.markdown("### 📋 업체 목록")
            disp_agencies = [sel_agency] if (auth_level in staff_roles and sel_agency != "전체") else (agencies if auth_level in staff_roles else [user_company])
            for ag in disp_agencies:
                c_list = sorted([c for c in f_df[f_df['대리점'] == ag]['고객명'].unique() if str(c).strip()])
                if c_list:
                    with st.expander(f"🏢 {ag} ({len(c_list)})", expanded=True):
                        cols = st.columns(4)
                        for i, c in enumerate(c_list):
                            if cols[i%4].button(f"🔍 {c}", key=f"b_{ag}_{c}", use_container_width=True):
                                st.session_state['nav_customer'] = c
                                if auth_level in staff_roles: st.session_state['nav_agency'] = ag
                                st.rerun()
        else:
            show_detail = True
            if st.button("🏠 전체 목록으로 돌아가기"):
                st.session_state['nav_agency'] = st.session_state['nav_sido'] = st.session_state['nav_sigungu'] = "전체"
                st.session_state['nav_customer'] = "선택하세요"
                st.session_state['active_filtered_wo'] = None
                st.rerun()

    # ==========================================
    # 공통: 선택된 고객 장비 상세 렌더링 화면
    # ==========================================
    if show_detail and sel_cust != "선택하세요":
        c_df = f_df[f_df['고객명'] == sel_cust]
        c_info = c_df.iloc[0]
        st.write("---")
        st.markdown(f"### 🏢 [{sel_cust}] 상세 내역 및 이력 폼")
        info_str = f"- **대표자:** {c_info['대표자']}\n- **연락처:** {c_info['연락처']}\n- **주소:** {c_info['주소']}"
        if equipment_type in ["해수열", "해수용 칠러"]: info_str += f"\n- **사육어종:** {c_info['사육어종']}"
        st.info(info_str)

        req_alert_df = load_as_requests()
        if not req_alert_df.empty:
            cust_pending = enrich_as_requests_display(
                req_alert_df[(req_alert_df['고객명'] == sel_cust) & (req_alert_df['처리상태'] == '접수대기')]
            )
            if not cust_pending.empty:
                st.markdown("##### 🔔 이 고객사 — AS 접수 대기")
                alert_cols = ["접수사진", "접수일시", "제조오더", "담당자명", "연락처", "증상요약"]
                st.dataframe(
                    cust_pending[alert_cols],
                    hide_index=True,
                    use_container_width=True,
                )
                if auth_level not in staff_roles:
                    st.caption("※ 접수 처리·보고서 작성은 AS팀·영업팀·본사 계정에서 진행합니다.")
        
        st.markdown("#### 📊 등록 장비 상세 제원 및 이력")
        df_as = load_as_data()
        cust_as = pd.DataFrame()
        if not df_as.empty and '고객명' in df_as.columns: cust_as = df_as[df_as['고객명'] == sel_cust]
                
        st.markdown("**■ QM TEST 진행 내역**")
        st.dataframe(c_df[[c for c in ['검사 완료일', '설치일', '제조오더', '용량(RT)', '냉매', '냉매량(kg)', '점검자', '비고(QM)'] if c in c_df.columns]], hide_index=True, column_config={"비고(QM)": "비고"})
        st.markdown("**■ 대리점 설치공사 내역**")
        st.dataframe(c_df[[c for c in ['SERVICE No.', '설치일', '시공대리점', '메인전원(SQ)', '열원/규격', '부하/규격', '순환방식', '배관재질', '사용조건', '비고(설치)'] if c in c_df.columns]], hide_index=True, column_config={"비고(설치)": "비고"})
        st.markdown("**■ 시운전 내역**")
        st.dataframe(c_df[[c for c in ['SERVICE No.', '가동시간', '시운전압력-저', '시운전압력-고', '시운전전류', '물온도-부하', '물온도-열원', '비고(시운전)'] if c in c_df.columns]], hide_index=True, column_config={"비고(시운전)": "비고"})
        
        st.markdown("**■ 장비 AS 및 시운전 리포트**")
        if not cust_as.empty:
            st.dataframe(cust_as.drop(columns=["사진링크", "PDF링크"], errors='ignore'), hide_index=True, use_container_width=True)
            st.markdown("##### 📸 AS 상세 내역 및 갤러리")
            for idx, row in cust_as.iterrows():
                with st.expander(f"📌 {row.get('일시', '')} | 담당자: {row.get('담당자', '')} | 작업: {str(row.get('작업내용', ''))[:20]}..."):
                    if row.get('PDF링크', '') and "http" in str(row.get('PDF링크')): st.link_button("📄 생성된 PDF 리포트 원본 열기", row.get('PDF링크'))
                    p_urls = parse_urls_safe(row.get('사진링크', ''))
                    if p_urls:
                        cols = st.columns(min(len(p_urls), 4))
                        for i, u in enumerate(p_urls): cols[i%4].image(u, use_container_width=True)
                    else: st.caption("첨부된 작업 사진이 없습니다.")
        else: st.write("해당 업체의 AS/시운전 이력이 없습니다.")

        st.write("---")
        disp_df = c_df.copy()
        disp_df['AS만료일'] = disp_df.apply(lambda x: calc_expiry(x['설치일'], x['AS기간']), axis=1)
        disp_df['QM'] = disp_df['점검자'].apply(lambda x: "✅" if str(x).replace("'", "").strip() else "❌")
        disp_df['설치공사'] = disp_df['시공대리점'].apply(lambda x: "✅" if str(x).replace("'", "").strip() else "❌")
        disp_df['AS이력'] = disp_df.apply(lambda r: "✅" if not cust_as.empty and any(str(r.get('용량(RT)', '')) in str(s) and "[SERVICE REPORT]" in str(s) for s in cust_as['작업내용']) else "❌", axis=1)
        disp_df['시운전'] = disp_df.apply(lambda r: "✅" if not cust_as.empty and any(str(r.get('용량(RT)', '')) in str(s) and "[시운전 보고서]" in str(s) for s in cust_as['작업내용']) else "❌", axis=1)
        disp_df.insert(0, "선택", False)
        
        st.markdown("#### ▶ **SERVICE/설치공사/시운전 대상 장비 선택**")
        
        if 'active_filtered_wo' not in st.session_state: st.session_state['active_filtered_wo'] = None

        if st.session_state['active_filtered_wo']:
            disp_df_to_show = disp_df[disp_df['제조오더'] == st.session_state['active_filtered_wo']].copy()
            disp_df_to_show['선택'] = True
            st.button("🔄 다른 동일 고객사 장비 리스트도 함께 보기 (선택 해제 및 숨김 풀기)", on_click=lambda: st.session_state.update({'active_filtered_wo': None}))
        else:
            disp_df_to_show = disp_df.copy()

        show_cols = ['선택', 'SERVICE No.', 'QM', '설치공사', '시운전', 'AS이력', '검사 완료일', '설치일', 'AS만료일', '용량(RT)', '냉매', '냉매량(kg)', '제조오더']
        edited_equip = st.data_editor(disp_df_to_show[show_cols], hide_index=True, use_container_width=True, key="admin_panel_equip_editor", disabled=['QM', '설치공사', '시운전', 'AS이력', '검사 완료일', '설치일', 'AS만료일', '용량(RT)', '냉매', '냉매량(kg)', '제조오더'])
        
        sel_equips = edited_equip[edited_equip['선택']]
        
        if len(sel_equips) == 1 and st.session_state['active_filtered_wo'] is None:
            st.session_state['active_filtered_wo'] = sel_equips.iloc[0]['제조오더']
            st.rerun()
        elif sel_equips.empty and st.session_state['active_filtered_wo'] is not None:
            st.session_state['active_filtered_wo'] = None
            st.rerun()

        equip_info_str = " / ".join(sel_equips['용량(RT)'].astype(str).unique().tolist()) if not sel_equips.empty else ""

        if st.button("💾 수정한 SERVICE No. 일괄 저장"):
            with st.spinner("저장 중..."):
                update_count = 0
                for idx in disp_df_to_show.index:
                    if disp_df_to_show.loc[idx, 'SERVICE No.'] != edited_equip.loc[idx, 'SERVICE No.']:
                        ws_equip.update(f"AU{disp_df_to_show.loc[idx, 'row_index']}", [[safe_text(edited_equip.loc[idx, 'SERVICE No.'])]])
                        update_count += 1
                st.success(f"{update_count}건 저장 완료!"); st.cache_data.clear(); st.rerun()
                
        if not sel_equips.empty:
            st.markdown("#### 📸 선택한 장비의 현장 사진 갤러리")
            tabs = st.tabs([f"장비 {row['SERVICE No.'] if row['SERVICE No.'] else '(번호없음)'}" for idx, row in sel_equips.iterrows()])
            for i, (idx, row) in enumerate(sel_equips.iterrows()):
                orig_row = c_df.loc[idx].to_dict()
                with tabs[i]:
                    qm_urls, inst_urls, test_urls = parse_urls_safe(orig_row.get('QM사진', '')), parse_urls_safe(orig_row.get('설치사진', '')), parse_urls_safe(orig_row.get('시운전사진', ''))
                    col_q, col_i, col_t = st.columns(3)
                    with col_q:
                        st.markdown("**✔️ QM TEST 사진**")
                        if qm_urls:
                            with st.expander("📸 보기"):
                                for u in qm_urls: st.image(u, use_container_width=True)
                        else: st.caption("사진 없음")
                    with col_i:
                        st.markdown("**✔️ 설치공사 사진**")
                        if inst_urls:
                            with st.expander("📸 보기"):
                                for u in inst_urls: st.image(u, use_container_width=True)
                        else: st.caption("사진 없음")
                    with col_t:
                        st.markdown("**✔️ 시운전 사진**")
                        if test_urls:
                            with st.expander("📸 보기"):
                                for u in test_urls: st.image(u, use_container_width=True)
                        else: st.caption("사진 없음")

        # --- 설치공사 & 시운전 내역 입력 폼 ---
        if auth_level not in staff_roles and not sel_equips.empty:
            with st.expander("🛠️ 설치공사 내역 입력 (대리점 전용)", expanded=False):
                with st.form("install_form"):
                    ic1, ic2, ic3, ic4 = st.columns(4)
                    i_main, i_heat, i_load, i_pump_note = ic1.text_input("메인전원(SQ)"), ic2.text_input("열원/규격"), ic3.text_input("부하/규격"), ic4.text_input("비고(펌프)")
                    ic5, ic6, ic7 = st.columns(3)
                    i_circ, i_pipe, i_cond = ic5.text_input("순환방식"), ic6.text_input("배관재질(규격)"), ic7.text_input("사용조건(냉/난방)")
                    ic8, ic9, ic10 = st.columns(3)
                    i_installer, i_worker, i_note2 = ic8.text_input("시공대리점(필수)", value=user_company), ic9.text_input("시공자명(필수)"), ic10.text_input("비고(설치)")
                    inst_photo_files = st.file_uploader("현장 사진", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                    if st.form_submit_button("설치공사 데이터 저장"):
                        if not i_installer.strip() or not i_worker.strip(): st.error("필수 값을 입력하세요.")
                        else:
                            with st.spinner("업로드 중..."):
                                safe_wo = str(sel_equips['제조오더'].iloc[0]).replace("/", "_")
                                inst_photo_urls = [cloudinary.uploader.upload(f, folder=f"INSTALL_PHOTOS/{safe_wo}", resource_type="image").get("secure_url") for f in inst_photo_files] if inst_photo_files else []
                                update_data = [safe_text(x) for x in [i_main, i_heat, i_load, i_pump_note, i_circ, i_pipe, i_cond, f"{i_installer.strip()} / {i_worker.strip()}", i_note2]]
                                for idx in sel_equips.index:
                                    ws_equip.update(f"X{c_df.loc[idx, 'row_index']}:AF{c_df.loc[idx, 'row_index']}", [update_data])
                                    if inst_photo_urls: ws_equip.update(f"AV{c_df.loc[idx, 'row_index']}", [[f"'\n'.join(inst_photo_urls)"]])
                                st.success("설치 내역 저장 완료!"); st.cache_data.clear(); st.rerun()

            with st.expander("⚙️ 시운전 내역 입력 (대리점 전용)", expanded=False):
                with st.form("testrun_form"):
                    tc1, tc2, tc3, tc4 = st.columns(4)
                    t_time, t_plow, t_phigh, t_amp = tc1.text_input("가동시간"), tc2.text_input("압력셋팅(저압)"), tc3.text_input("압력셋팅(고압)"), tc4.text_input("기동전류(A)")
                    tc5, tc6, tc7 = st.columns(3)
                    t_tload, t_theat, t_note = tc5.text_input("입출수 물온도(부하)"), tc6.text_input("입출수 물온도(열원)"), tc7.text_input("비고(시운전)")
                    test_photo_files = st.file_uploader("시운전 사진", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                    if st.form_submit_button("시운전 데이터 저장"):
                        with st.spinner("저장 중..."):
                            safe_wo = str(sel_equips['제조오더'].iloc[0]).replace("/", "_")
                            test_photo_urls = [cloudinary.uploader.upload(f, folder=f"TESTRUN_PHOTOS/{safe_wo}", resource_type="image").get("secure_url") for f in test_photo_files] if test_photo_files else []
                            update_data = [safe_text(x) for x in [t_time, t_plow, t_phigh, t_amp, t_tload, t_theat, t_note]]
                            for idx in sel_equips.index:
                                ws_equip.update(f"AG{c_df.loc[idx, 'row_index']}:AM{c_df.loc[idx, 'row_index']}", [update_data])
                                if test_photo_urls: ws_equip.update(f"AW{c_df.loc[idx, 'row_index']}", [[f"'\n'.join(test_photo_urls)"]])
                            st.success("시운전 내역 저장 완료!"); st.cache_data.clear(); st.rerun()

        # --- AS 및 시운전 레포트 작성 영역 ---
        if auth_level in staff_roles and not sel_equips.empty:
            with st.expander("📝 보고서 작성하기 (PDF 저장)", expanded=True):
                report_type = st.radio("보고서 종류 선택", ["SERVICE REPORT", "시운전 보고서"], horizontal=True)
                st.divider()
                
                wo_list = sel_equips['제조오더'].tolist()
                customer_photo_urls = []
                req_idx_to_update = None
                
                linked_req = st.session_state.get('linked_as_request')
                try:
                    req_df = load_as_requests()
                    if not req_df.empty:
                        pending_reqs = req_df[
                            req_df['제조오더'].apply(lambda x: any(w in str(x) for w in wo_list))
                            & (req_df['처리상태'] == '접수대기')
                        ]
                        if not pending_reqs.empty:
                            match_row = pending_reqs.iloc[0]
                            req_idx_to_update = pending_reqs.index[0] + 2
                            if linked_req:
                                for idx, row in pending_reqs.iterrows():
                                    if str(row.get('접수일시', '')) == str(linked_req.get('접수일시', '')):
                                        match_row = row
                                        req_idx_to_update = idx + 2
                                        break
                                else:
                                    match_row = pd.Series(linked_req)
                            customer_photo_urls = parse_urls_safe(match_row.get('사진링크', ''))
                            if str(match_row.get('증상', '')).strip():
                                st.caption(f"**접수 증상:** {match_row.get('증상', '')}")
                except Exception:
                    pass

                equip_ref_default = ""
                if not sel_equips.empty:
                    equip_ref_default = str(c_df.loc[sel_equips.index[0], '냉매']).replace("'", "").strip()
                        
                with st.form("service_report_form"):
                    use_cust_photos = False
                    if customer_photo_urls:
                        use_cust_photos = st.checkbox(
                            "고객 접수 사진을 '작업 전 사진'으로 PDF에 포함",
                            value=True,
                            help="체크 해제 시 접수 사진 없이 새로 촬영한 사진만 사용합니다.",
                        )
                    
                    col1, col2 = st.columns(2)
                    site_name, rcv_date = col1.text_input("현장명(주소)", value=c_info['주소']), col2.date_input("접수일자")
                    manager_info, end_date = col1.text_input("담당자(연락처)", value=f"{c_info['대표자']} / {c_info['연락처']}"), col2.date_input("완료일자")
                    equip_info = st.text_input("장비정보 (용량)", value=equip_info_str)

                    equip_map = {"해수열": "해수열 HP", "폐수열": "폐수열 HP", "공기열": "공기열 HP", "건조기(김공장)": "제습기/건조기", "어선용": "기타"}
                    default_eq_val = equip_map.get(equipment_type, "기타")
                    eq_options = ["해수열 HP", "해수용 칠러", "폐수열 HP", "공기열 HP", "제습기/건조기", "수소", "기타"]
                    report_equip = st.radio("장비구분 선택", eq_options, index=eq_options.index(default_eq_val) if default_eq_val in eq_options else 6, horizontal=True, label_visibility="collapsed")

                    wk_1 = wk_2 = wk_3 = wk_4 = False
                    charge_type = po_no = ""
                    if report_type == "SERVICE REPORT":
                        st.markdown("**작업구분**")
                        work_cols = st.columns(6)
                        wk_1, wk_2, wk_3, wk_4 = work_cols[0].checkbox("하자처리(전장)"), work_cols[1].checkbox("기계"), work_cols[2].checkbox("설비"), work_cols[3].checkbox("기타")
                        charge_type = st.radio("요금구분", ["고객", "유상", "무상"], horizontal=True)
                        po_no = st.text_input("PO No 입력") if charge_type == "고객" else ""
                    else: st.checkbox("☑ 시운전 (자동 선택됨)", value=True, disabled=True)

                    ref_options = ["R-22", "R-407C", "R-134A", "A-507", "기타/선택안함"]
                    ref_type = st.radio(
                        "냉매구분",
                        ref_options,
                        index=default_ref_index(equip_ref_default, ref_options),
                        horizontal=True,
                        help=f"장비 등록 냉매: {equip_ref_default or '미등록'} (필요 시 변경 가능)",
                    )
                    df_work = pd.DataFrame(columns=["구분", "작업내용"])
                    edited_work = st.data_editor(df_work, num_rows="dynamic", use_container_width=True)

                    bot_col1, bot_col2 = st.columns(2)
                    engineer_cnt = bot_col1.text_input("방문한 서비스 엔지니어 인원 (인원/시간)")
                    start_time, end_time = bot_col1.time_input("작업 시작시간", value=datetime.now(KST).time()), bot_col1.time_input("작업 종료시간", value=datetime.now(KST).time())
                    satisfaction = bot_col2.radio("서비스만족도 조사", ["불만족", "보통", "만족"], horizontal=True)
                    constructor = bot_col2.text_input("영업자/시공자(필수)", value=user_info.get('업체명', ''))
                    requests_text = st.text_area("고객 요청사항")

                    c_p1, c_p2 = st.columns(2)
                    before_files = c_p1.file_uploader("작업 전 사진 (최대 2장)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)
                    after_files = c_p2.file_uploader("완료 및 작업 후 사진 (최대 4장)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)

                    sig_col1, sig_col2 = st.columns(2)
                    with sig_col1: emp_name = st.text_input("담당직원 이름(필수)", value=user_info.get('이름', ''))
                    with sig_col2:
                        agree_check = st.checkbox("**(필수) 작업 설명을 듣고 이해하였음을 확인합니다.**")
                        canvas_customer = st_canvas(stroke_width=3, stroke_color="#000000", background_color="#FFFFFF", height=150, width=350, drawing_mode="freedraw", key="as_sig_canvas_admin")

                    submit_report = st.form_submit_button(f"[{report_type}] 저장 및 전송")
                
                if submit_report:
                    if not constructor.strip() or not emp_name.strip() or edited_work.empty or not agree_check: st.error("필수값을 모두 채워주세요.")
                    else:
                        edited_work.insert(0, "No", range(1, len(edited_work) + 1))
                        with st.spinner("PDF 리포트 생성 및 사진 데이터 이관 중..."):
                            sig_path = "temp_sig.png" if canvas_customer.image_data is not None and np.sum(canvas_customer.image_data.astype('uint8')) > 0 else None
                            if sig_path: Image.fromarray(canvas_customer.image_data.astype('uint8'), 'RGBA').save(sig_path)

                            def save_tmp(f):
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                    f.seek(0); Image.open(f).convert("RGB").save(tmp.name, format="JPEG", quality=70)
                                    return tmp.name
                                    
                            b_paths = [save_tmp(f) for f in before_files] if before_files else []
                            a_paths = [save_tmp(f) for f in after_files] if after_files else []

                            if use_cust_photos and customer_photo_urls:
                                for u in customer_photo_urls:
                                    try:
                                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                            tmp.write(requests.get(u).content); b_paths.append(tmp.name)
                                    except: pass

                            work_checked = ["하자처리(전장)" if wk_1 else "", "기계" if wk_2 else "", "설비" if wk_3 else "", "기타" if wk_4 else ""]
                            report_data = {
                                "site_name": site_name, "rcv_date": rcv_date, "manager_info": manager_info, "end_date": end_date, 
                                "equip_info": equip_info, "report_equip": report_equip, "work_checked": [w for w in work_checked if w], 
                                "charge_type": charge_type, "po_no": po_no, "ref_type": ref_type, "engineer_cnt": engineer_cnt,
                                "start_time": start_time.strftime("%H:%M"), "end_time": end_time.strftime("%H:%M"),
                                "satisfaction": satisfaction, "constructor": constructor, "requests": requests_text, "emp_name": emp_name
                            }
                            
                            try:
                                pdf_bytes = create_service_report_pdf(report_type, report_data, edited_work, sig_path, b_paths, a_paths)
                                all_photo_urls = []
                                file_wo_str = str(sel_equips['제조오더'].iloc[0]).replace("/", "_")
                                if b_paths:
                                    for p in b_paths: all_photo_urls.append(cloudinary.uploader.upload(p, folder=f"AS_PHOTOS/{file_wo_str}/Before", resource_type="image").get("secure_url"))
                                if a_paths:
                                    for p in a_paths: all_photo_urls.append(cloudinary.uploader.upload(p, folder=f"AS_PHOTOS/{file_wo_str}/After", resource_type="image").get("secure_url"))
                                
                                pdf_name_cloud = f"{'SR' if report_type == 'SERVICE REPORT' else 'TR'}_{file_wo_str}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                pdf_url = cloudinary.uploader.upload(pdf_bytes, folder="SERVICE_REPORTS", resource_type="raw", public_id=pdf_name_cloud).get("secure_url")
                                
                                new_row = [datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), sel_cust, ref_type, f"[{report_type}] 장비: {equip_info_str} / 내용: {edited_work.iloc[0]['작업내용']} 외", emp_name, user_info['업체명'], "\n".join(all_photo_urls), pdf_url]
                                sh.worksheet("AS내역").append_row([safe_text(i) for i in new_row])
                                if req_idx_to_update: sh.worksheet("AS접수현황").update_cell(req_idx_to_update, 9, "처리완료")
                                
                                st.success("✅ 클라우드 동기화 및 리포트 전송이 완료되었습니다!")
                                c_btn1, c_btn2 = st.columns(2)
                                with c_btn1: st.download_button("📥 로컬 장치로 다운로드 (PDF)", pdf_bytes, f"{pdf_name_cloud}.pdf", "application/pdf", use_container_width=True)
                                with c_btn2: st.link_button("☁️ 클라우드 원본 문서 조회", pdf_url, use_container_width=True)
                                st.balloons()
                            except Exception as e: st.error(f"저장 오류: {e}")

# ==========================================
# 🌟 라우팅 (길잡이) - URL 파라미터로 화면 분기
# ==========================================
params = st.query_params
if "wo" in params:
    show_qr_customer_view(params["wo"])
else:
    show_admin_view()