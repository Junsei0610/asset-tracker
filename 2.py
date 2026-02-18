import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 설정: 페이지 기본 세팅 ---
st.set_page_config(page_title="Junsei's Asset Tracker V8", page_icon="💸", layout="centered")

# --- 스타일: 다크 모드 & 폰트 ---
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #ff4b4b; }
    .sub-font { font-size:18px !important; font-weight: bold; color: #ff8c00; }
    .google-font { font-size:18px !important; font-weight: bold; color: #4285F4; } 
    .dividend-font { font-size:18px !important; font-weight: bold; color: #4caf50; }
    .warning-box { border: 2px solid #ff4b4b; padding: 20px; border-radius: 10px; background-color: #262730; margin-bottom: 20px; }
    .dividend-box { border: 2px solid #4caf50; padding: 20px; border-radius: 10px; background-color: #262730; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 기능 1: 구글 시트 연결 (DB) ---
@st.cache_resource
def init_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_data():
    client = init_connection()
    sheet_url = st.secrets["private_gsheets_url"]["spreadsheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    data = sheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["date", "item", "amount", "month"])
    return pd.DataFrame(data)

def add_expense_to_sheet(date, item, amount, month):
    client = init_connection()
    sheet_url = st.secrets["private_gsheets_url"]["spreadsheet_url"]
    sheet = client.open_by_url(sheet_url).sheet1
    sheet.append_row([date, item, amount, month])

# --- 기능 3: 주가 데이터 ---
@st.cache_data(ttl=60)
def get_market_data():
    tickers = ["PLTR", "GOOGL", "NVDA", "O"]
    data = {}
    exchange_rate = 150.0
    defaults = {"PLTR": 30.0, "GOOGL": 175.0, "NVDA": 135.0, "O": 53.0}
    yields = {"NVDA": 0.0003, "O": 0.055}

    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="1d")
            price = hist['Close'].iloc[-1] if not hist.empty else defaults[t]
            data[t] = {"price": price * exchange_rate, "yield": yields.get(t, 0)}
        except:
            data[t] = {"price": defaults[t] * exchange_rate, "yield": yields.get(t, 0)}
    return data

market = get_market_data()

# --- 기능 4: 복리 계산 함수 ---
def calculate_future_value(principal, rate, years):
    return principal * ((1 + rate) ** years)

# --- UI: 헤더 ---
today = datetime.now()
st.title(f"🛡️ Asset Defense V8 (Cloud)")
st.caption(f"☁️ Google Sheets Connected | 1$ = 150¥")

# --- UI: 데이터 로드 ---
try:
    df = get_data()
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
except Exception as e:
    # 로컬에서 실행 시 secrets가 없으면 에러가 날 수 있음. 배포 후에는 정상 작동.
    st.warning("⚠️ 로컬 실행 중: Google Sheets 연결 대기 (배포 시 정상 작동)")
    df = pd.DataFrame(columns=["date", "item", "amount", "month"])

# --- UI: 월별 필터링 ---
st.sidebar.header("📅 월별 장부")
selected_date = st.sidebar.date_input("날짜 이동", today)
view_month_str = selected_date.strftime("%Y-%m")

if not df.empty and 'month' in df.columns:
    df_current = df[df['month'] == view_month_str]
else:
    df_current = pd.DataFrame()

# --- UI: 예산 설정 ---
if 'budget' not in st.session_state:
    st.session_state.budget = 50000

new_budget = st.sidebar.number_input(f"{view_month_str} 예산", value=st.session_state.budget, step=1000)
if new_budget != st.session_state.budget:
    st.session_state.budget = new_budget
    st.rerun()

# --- UI: 통계 ---
total_spent = df_current['amount'].sum() if not df_current.empty else 0
remaining = new_budget - total_spent
progress = min(max(total_spent / new_budget, 0.0), 1.0) if new_budget > 0 else 1.0

st.write(f"### 💰 남은 돈: {remaining:,.0f} 엔")
if new_budget > 0:
    st.progress(progress)
if remaining < 0:
    st.error("⚠️ 파산 경보! 구글 시트에 '적자'가 기록됩니다.")

# --- UI: 입력 폼 ---
with st.expander("💸 지출 추가하기", expanded=True):
    with st.form("add_form", clear_on_submit=True):
        col_a, col_b = st.columns([3, 1])
        item = col_a.text_input("내역", placeholder="예: 택시비")
        amount = col_b.number_input("금액", min_value=1, step=100)
        date_val = st.date_input("날짜", today)
        
        if st.form_submit_button("등록"):
            month_str = date_val.strftime("%Y-%m")
            date_str = date_val.strftime("%Y-%m-%d")
            add_expense_to_sheet(date_str, item, amount, month_str)
            st.toast("☁️ 구글 시트에 저장되었습니다!")
            st.rerun()

# --- UI: 내역 표시 ---
if not df_current.empty:
    st.divider()
    st.subheader("📋 지출 내역")
    st.dataframe(df_current[['date', 'item', 'amount']], use_container_width=True)

# --- UI: 자산 손실 보고서 ---
if total_spent > 0:
    st.divider()
    st.subheader("☠️ 자산 손실 보고서 (Total Damage)")
    
    lost_pltr = total_spent / market["PLTR"]["price"]
    lost_nvda = total_spent / market["NVDA"]["price"]
    lost_googl = total_spent / market["GOOGL"]["price"]
    
    st.markdown(f"""
    <div class='warning-box'>
        <div>💸 <b>이번 달 지출: {total_spent:,.0f} 엔</b></div>
        <br>
        <div class='big-font'>📉 PLTR {lost_pltr:.2f}주 증발</div>
        <div class='sub-font'>📉 NVIDIA {lost_nvda:.2f}주 증발</div>
        <div class='google-font'>📉 Google {lost_googl:.2f}주 증발</div>
    </div>
    """, unsafe_allow_html=True)
    
    shares_o = total_spent / market["O"]["price"]
    monthly_div_o = (shares_o * market["O"]["price"] * market["O"]["yield"]) / 12

    st.markdown(f"""
    <div class='dividend-box'>
        <div class='dividend-font'>💰 이 돈이면 Realty Income(O)에서</div>
        <div class='dividend-font'>매달 {monthly_div_o:,.0f} 엔씩 평생 받습니다.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### ⏳ 타임 머신")
    years = [5, 10, 20, 30]
    growth_data = [calculate_future_value(total_spent, 0.15, y) for y in years]
    snp_data = [calculate_future_value(total_spent, 0.08, y) for y in years]
    
    df_future = pd.DataFrame({
        "기간": [f"{y}년 후" for y in years],
        "S&P 500 (8%)": [f"{v:,.0f} 엔" for v in snp_data],
        "성장주 (15%)": [f"{v:,.0f} 엔" for v in growth_data],
        "배수": [f"{v/total_spent:.1f}배" for v in growth_data]
    })
    st.table(df_future)
