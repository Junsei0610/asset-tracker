import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import pytz # 시차 계산용

# --- 설정: 페이지 기본 세팅 ---
st.set_page_config(page_title="Junsei's Asset Tracker V7", page_icon="💸", layout="centered")

# --- 스타일: 다크 모드 & 폰트 (INTJ 스타일) ---
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #ff4b4b; }
    .sub-font { font-size:18px !important; font-weight: bold; color: #ff8c00; }
    .google-font { font-size:18px !important; font-weight: bold; color: #4285F4; } 
    .dividend-font { font-size:18px !important; font-weight: bold; color: #4caf50; }
    .warning-box { border: 2px solid #ff4b4b; padding: 20px; border-radius: 10px; background-color: #262730; margin-bottom: 20px; }
    .dividend-box { border: 2px solid #4caf50; padding: 20px; border-radius: 10px; background-color: #262730; margin-bottom: 20px; }
    .info-text { font-size: 12px; color: #888; }
    </style>
    """, unsafe_allow_html=True)

# --- 기능 1: 데이터베이스(SQLite) 핸들링 ---
DB_FILE = "tracker.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, item TEXT, amount INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS budgets 
                 (month TEXT PRIMARY KEY, amount INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_FILE)

# --- 기능 2: 주가 데이터 (실시간 연동) ---
# 캐싱 시간을 1분(60초)으로 줄여서 장중 실시간성을 높임
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
            # period="1d"로 가져오면 장중에는 현재가, 장마감후엔 종가
            hist = stock.history(period="1d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
            else:
                price = defaults[t]
            
            data[t] = {"price": price * exchange_rate, "yield": yields.get(t, 0)}
        except:
            data[t] = {"price": defaults[t] * exchange_rate, "yield": yields.get(t, 0)}
            
    return data

market = get_market_data()

# --- 기능 3: 날짜 및 이월 계산 로직 ---
today = datetime.now()
current_month_str = today.strftime("%Y-%m")

st.sidebar.header("📅 월별 장부 선택")
selected_date = st.sidebar.date_input("날짜 이동", today)
view_month_str = selected_date.strftime("%Y-%m")

def get_previous_month(month_str):
    date_obj = datetime.strptime(month_str, "%Y-%m")
    prev_month = date_obj.replace(day=1) - timedelta(days=1)
    return prev_month.strftime("%Y-%m")

prev_month_str = get_previous_month(view_month_str)

# --- 기능 4: DB 입출력 함수 ---
def get_monthly_expenses(month):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM expenses WHERE strftime('%Y-%m', date) = '{month}'", conn)
    conn.close()
    return df

def get_budget(month):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT amount FROM budgets WHERE month = ?", (month,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 50000

def set_budget(month, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO budgets (month, amount) VALUES (?, ?)", (month, amount))
    conn.commit()
    conn.close()

def add_expense(item, amount, date_str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO expenses (date, item, amount) VALUES (?, ?, ?)", (date_str, item, amount))
    conn.commit()
    conn.close()

def delete_expenses(ids):
    conn = get_connection()
    c = conn.cursor()
    if len(ids) == 1:
        c.execute(f"DELETE FROM expenses WHERE id = {ids[0]}")
    else:
        c.execute(f"DELETE FROM expenses WHERE id IN {tuple(ids)}")
    conn.commit()
    conn.close()

# --- 기능 5: 복리 계산 함수 ---
def calculate_future_value(principal, rate, years):
    return principal * ((1 + rate) ** years)

# --- UI: 헤더 ---
st.title(f"🛡️ Asset Defense V7 ({view_month_str})")
# 현재 시간 표시 (데이터 갱신 확인용)
now_str = datetime.now().strftime("%H:%M:%S")
st.caption(f"📉 Market Data Updated: {now_str} (JST) | 1$ = 150¥")

# --- UI: 예산 및 이월 계산 ---
current_base_budget = get_budget(view_month_str)
new_budget = st.sidebar.number_input(f"{view_month_str} 기본 예산", value=current_base_budget, step=1000)
if new_budget != current_base_budget:
    set_budget(view_month_str, new_budget)
    st.rerun()

prev_budget = get_budget(prev_month_str)
prev_expenses = get_monthly_expenses(prev_month_str)
prev_spent = prev_expenses['amount'].sum() if not prev_expenses.empty else 0
rollover = prev_budget - prev_spent
final_budget = new_budget + rollover

# --- UI: 대시보드 ---
df_current = get_monthly_expenses(view_month_str)
total_spent = df_current['amount'].sum() if not df_current.empty else 0
remaining = final_budget - total_spent
progress = min(max(total_spent / final_budget, 0.0), 1.0) if final_budget > 0 else 1.0

col1, col2, col3 = st.columns(3)
col1.metric("기본 예산", f"{new_budget:,.0f} 엔")
col2.metric("이월금", f"{rollover:,.0f} 엔", delta_color="normal")
col3.metric("최종 예산", f"{final_budget:,.0f} 엔")

st.write(f"### 💰 남은 돈: {remaining:,.0f} 엔")
if final_budget > 0:
    st.progress(progress)
if remaining < 0:
    st.error("⚠️ 파산 경보! 빚이 늘어나고 있습니다!")

# --- UI: 입력 폼 ---
with st.expander("💸 지출 추가하기", expanded=True):
    with st.form("add_form", clear_on_submit=True):
        col_a, col_b = st.columns([3, 1])
        item = col_a.text_input("내역", placeholder="예: 택시비")
        amount = col_b.number_input("금액", min_value=1, step=100)
        
        default_date = datetime.now()
        if view_month_str != current_month_str:
            default_date = datetime.strptime(view_month_str + "-01", "%Y-%m-%d")
        date_val = st.date_input("날짜", default_date)
        
        if st.form_submit_button("등록"):
            add_expense(item, amount, date_val.strftime("%Y-%m-%d"))
            st.rerun()

# --- UI: 내역 삭제 및 조회 ---
if not df_current.empty:
    st.divider()
    st.subheader("📋 지출 내역")
    st.dataframe(df_current[['date', 'item', 'amount']], use_container_width=True)
    
    all_options = df_current.to_dict('records')
    options_map = {row['id']: f"{row['date']} | {row['item']} | {row['amount']:,}엔" for row in all_options}
    
    delete_selection = st.multiselect("🗑️ 삭제할 내역 선택:", options=options_map.keys(), format_func=lambda x: options_map[x])
    if delete_selection and st.button("선택 삭제"):
        delete_expenses(delete_selection)
        st.success("삭제 완료")
        st.rerun()

# ==============================================================================
# 🔥 [핵심 기능] 종합 손실 보고서 (Google 추가 완료)
# ==============================================================================
if total_spent > 0:
    st.divider()
    st.subheader("☠️ 자산 손실 보고서 (Total Damage)")
    
    # 1. 주식 증발 (수량) - 구글 추가
    lost_pltr = total_spent / market["PLTR"]["price"]
    lost_nvda = total_spent / market["NVDA"]["price"]
    lost_googl = total_spent / market["GOOGL"]["price"]
    
    st.markdown(f"""
    <div class='warning-box'>
        <div>💸 <b>이번 달 지출 합계: {total_spent:,.0f} 엔</b></div>
        <br>
        <div class='big-font'>📉 PLTR {lost_pltr:.2f}주 증발</div>
        <div class='sub-font'>📉 NVIDIA {lost_nvda:.2f}주 증발</div>
        <div class='google-font'>📉 Google {lost_googl:.2f}주 증발</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. 배당금 (Realty Income)
    shares_o = total_spent / market["O"]["price"]
    monthly_div_o = (shares_o * market["O"]["price"] * market["O"]["yield"]) / 12

    st.markdown(f"""
    <div class='dividend-box'>
        <div class='dividend-font'>💰 이 돈이면 Realty Income(O)에서</div>
        <div class='dividend-font'>매달 {monthly_div_o:,.0f} 엔씩 평생 받습니다.</div>
    </div>
    """, unsafe_allow_html=True)

    # 3. 복리 계산기 & S&P 500
    st.markdown("### ⏳ 타임 머신 (미래 가치 환산)")
    st.caption("※ S&P 500 (연 8%) vs 성장주 (연 15%) 복리 비교")
    
    years = [5, 10, 20, 30]
    growth_data = [calculate_future_value(total_spent, 0.15, y) for y in years] # 성장주 15%
    snp_data = [calculate_future_value(total_spent, 0.08, y) for y in years]    # S&P500 8%
    
    df_future = pd.DataFrame({
        "기간": [f"{y}년 후" for y in years],
        "S&P 500 (8%)": [f"{v:,.0f} 엔" for v in snp_data],
        "성장주 (15%)": [f"{v:,.0f} 엔" for v in growth_data],
        "기회비용 배수": [f"{v/total_spent:.1f}배" for v in growth_data]
    })
    
    st.table(df_future)
    st.markdown(f"""
    <div style='text-align: center; color: #ffd700; font-weight: bold;'>
        "30년 뒤의 {growth_data[-1]:,.0f} 엔을 지금 불태우셨습니다."
    </div>
    """, unsafe_allow_html=True)