import streamlit as st
import pandas as pd

# ==========================================
# 0. 介面優化：白底黑字輸入框 + 高對比
# ==========================================
st.set_page_config(page_title="射出報價", page_icon="🏭", layout="centered")

# CSS 樣式表
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            
            /* 卡片背景 */
            .apple-card {
                background-color: #ffffff;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                margin-bottom: 25px;
                border: 2px solid #d1d1d6;
            }
            
            /* 價格大字 */
            .price-tag {
                font-family: sans-serif;
                font-size: 56px;
                font-weight: 800;
                color: #000000;
                text-align: center;
                margin: 15px 0;
            }
            
            /* 列表項目 */
            .list-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 0;
                border-bottom: 2px solid #e5e5ea;
                color: #000000;
            }
            .list-item:last-child {
                border-bottom: none;
            }
            
            /* 項目名稱 */
            .item-label-main {
                font-size: 20px;
                font-weight: 700;
                color: #000000;
            }
            .item-label-sub {
                font-size: 14px;
                color: #555555;
                margin-top: 4px;
                font-weight: 500;
            }
            
            /* 項目數值 */
            .item-value {
                font-size: 24px;
                font-weight: 700;
                color: #000000;
            }
            
            /* 輸入框強制白底黑字 */
            .stNumberInput input {
                background-color: #ffffff !important;
                color: #000000 !important;
                border: 1px solid #cccccc !important;
                font-weight: bold !important;
                font-size: 18px !important;
            }
            div[data-baseweb="select"] > div {
                background-color: #ffffff !important;
                color: #000000 !important;
                border: 1px solid #cccccc !important;
                font-weight: bold !important;
                font-size: 18px !important;
            }
            div[data-baseweb="select"] span {
                color: #000000 !important;
            }
            
            /* 背景與標籤 */
            .stApp { background-color: #f0f0f2; }
            label p {
                font-size: 18px !important;
                color: #000000 !important;
                font-weight: 700 !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 1. 系統參數與資料庫 (v3.3 更新版)
# ==========================================
ELEC_RATE = 5.0      
LOSS_RATE = 0.05     

# 更新機台資料庫：加入 400T ~ 1000T
# 費率來源：您的CSV檔案
# 馬達/週期/最大載重：依噸數比例推算的工程估計值
MACHINE_DB = {
    (50, 99):     {"rate": 8,  "motor_kw": 15, "dry_cycle": 3.0, "max_weight": 80},
    (100, 199):   {"rate": 13, "motor_kw": 30, "dry_cycle": 4.5, "max_weight": 250},
    (200, 299):   {"rate": 15, "motor_kw": 45, "dry_cycle": 5.5, "max_weight": 450},
    (300, 399):   {"rate": 17, "motor_kw": 60, "dry_cycle": 6.0, "max_weight": 800},
    # --- 新增區段 ---
    (400, 499):   {"rate": 20, "motor_kw": 75, "dry_cycle": 7.0, "max_weight": 1200},
    (500, 599):   {"rate": 25, "motor_kw": 90, "dry_cycle": 8.0, "max_weight": 1800},
    (600, 699):   {"rate": 25, "motor_kw": 110, "dry_cycle": 9.0, "max_weight": 2500},
    (700, 999):   {"rate": 28, "motor_kw": 130, "dry_cycle": 10.0, "max_weight": 3500}, # 涵蓋至999T
    (1000, 3000): {"rate": 35, "motor_kw": 160, "dry_cycle": 12.0, "max_weight": 8000},
}

MATERIAL_DB = {
    "PP":   {"price": 54,   "factor": 1.0, "dryer_kw": 3, "dry_time": 2, "high_temp": False},
    "PPG":  {"price": 72.5, "factor": 1.8, "dryer_kw": 3, "dry_time": 2, "high_temp": False},
    "PPC":  {"price": 258.1,"factor": 1.8, "dryer_kw": 3, "dry_time": 2, "high_temp": False},
    "ETFE": {"price": 2300, "factor": 2.3, "dryer_kw": 5, "dry_time": 4, "high_temp": True},
    "ETFE+CF": {"price": 1961, "factor": 2.5, "dryer_kw": 5, "dry_time": 4, "high_temp": True},
    "PPS":  {"price": 600,  "factor": 1.8, "dryer_kw": 4, "dry_time": 4, "high_temp": True},
}

THICKNESS_OPTIONS = {"一般 (<5mm)": 1.0, "中厚 (5~8mm)": 1.8, "特厚 (>8mm)": 3.0}

PACKING_OPTIONS = {
    "A級-工業散裝": {"rate": 2.0, "base": 0, "name": "A級(工業散裝)"},
    "B級-獨立盒裝": {"rate": 8.0, "base": 0, "name": "B級(獨立盒裝)"},
    "C級-外銷木箱": {"rate": 5.0, "base": 1200, "name": "C級(外銷木箱)"},
}

# 輔助函式
def get_auto_tonnage(weight):
    # 自動選機邏輯更新：若超過所有設定，預設選最大台
    for r, data in MACHINE_DB.items():
        if weight <= data["max_weight"]: return int((r[0] + r[1]) / 2)
    return 1000 # 超過 3500g 預設選 1000T

def get_machine_data(t):
    for r, data in MACHINE_DB.items():
        if r[0] <= t <= r[1]: return data
    # 若找不到(例如輸入8000噸)，回傳最大值參數避免報錯
    return {"rate": 35, "motor_kw": 160, "dry_cycle": 12.0}

def estimate_cycle(weight, mat_key, thickness_key, machine_data):
    mat_data = MATERIAL_DB.get(mat_key, {})
    thick_factor = THICKNESS_OPTIONS.get(thickness_key, 1.0)
    if not mat_data: return 0
    base_cool = (weight / 100) * 15.0
    mat_temp_factor = 1.4 if mat_data["high_temp"] else 1.0
    cycle = machine_data["dry_cycle"] + ((weight/100)*4.0) + (base_cool * mat_temp_factor * thick_factor)
    return int(cycle)

# ==========================================
# 2. 運算邏輯核心
# ==========================================
class SmartInjectionQuote:
    def __init__(self, weight_g, material, batch_size, thickness, packing, tonnage, cycle_sec):
        self.weight = weight_g
        self.material = material
        self.batch = batch_size
        self.thickness = thickness
        self.packing = packing
        self.tonnage = tonnage
        self.cycle_sec = cycle_sec
        self.machine_data = get_machine_data(tonnage)
        self.mat_data = MATERIAL_DB.get(material, {})
        self.pack_data = PACKING_OPTIONS.get(packing, {"rate": 2.0, "base": 0, "name": "未知"})

    def compute(self):
        if not self.mat_data: return None
        
        # 1. 材料費
        unit_mat_cost = (self.weight / 1000) * self.mat_data["price"] * (1 + LOSS_RATE)
        
        # 2. 射出費
        rate = self.machine_data["rate"]
        m_factor = self.mat_data["factor"]
        unit_process_cost = rate * m_factor * (self.cycle_sec / 60)
        
        # 3. 基本費
        preheat_cost = (self.mat_data["dryer_kw"]*0.8) * self.mat_data["dry_time"] * ELEC_RATE
        unit_basic_cost = (1500 + preheat_cost) / self.batch
        
        # 4. 包裝費
        w_kg = self.weight / 1000
        unit_pack_cost = (w_kg * self.pack_data["rate"]) + (self.pack_data["base"] / self.batch)
        
        # 5. 運費
        total_w = w_kg * self.batch
        ship_total = max(500, total_w * 2.0)
        unit_ship_cost = ship_total / self.batch
        
        final_price = unit_mat_cost + unit_process_cost + unit_basic_cost + unit_pack_cost + unit_ship_cost

        return {
            "Meta": {"機台": f"{self.tonnage}T", "週期": f"{self.cycle_sec}s"},
            "Cost_Structure": [
                {"name": "1.材料費", "sub": "成品重量*原料單價(公斤/元)", "val": unit_mat_cost},
                {"name": "2.射出費", "sub": "機台費用(分/元)*材料加成係數*射出時間(分)", "val": unit_process_cost},
                {"name": "3.基本費", "sub": "(烘料費用+洗料費用+調機費用+上下模+暖機)/批量", "val": unit_basic_cost},
                {"name": "4.包裝費", "sub": self.pack_data["name"], "val": unit_pack_cost},
                {"name": "5.運費", "sub": "國內回頭車", "val": unit_ship_cost}
            ],
            "Total_Price": final_price
        }

# ==========================================
# 3. 前端介面設計
# ==========================================

st.markdown("<h2 style='text-align: center; color: #000000; font-weight: 800; font-size: 32px;'>射出成本計算 v3.3</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #333333; font-size: 18px; font-weight: bold;'>無軸封泵浦品技課專用</p>", unsafe_allow_html=True)

# 輸入卡片
st.markdown('<div class="apple-card">', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    weight_g = st.number_input("產品重量 (g)", value=200.0, step=10.0)
    batch_size = st.number_input("批量 (pcs)", value=50, step=50)
    packing_labels = list(PACKING_OPTIONS.keys())
    packing = st.selectbox("包裝", packing_labels)
with col2:
    material = st.selectbox("材料", list(MATERIAL_DB.keys()), index=4)
    thickness = st.selectbox("壁厚", list(THICKNESS_OPTIONS.keys()), index=1)

suggested_tonnage = get_auto_tonnage(weight_g)
temp_machine = get_machine_data(suggested_tonnage)
suggested_cycle = estimate_cycle(weight_g, material, thickness, temp_machine)

st.divider()

with st.expander("🛠️ 進階設定 (手動輸入機台/週期)"):
    use_manual = st.toggle("開啟手動模式", value=False)
    if use_manual:
        final_tonnage = st.number_input("機台噸數 (Ton)", value=suggested_tonnage)
        final_cycle = st.number_input("成形週期 (秒)", value=suggested_cycle)
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"<p style='color:#333; font-size:16px;'>建議機台</p><p style='color:#000; font-size:24px; font-weight:bold;'>{suggested_tonnage} 噸</p>", unsafe_allow_html=True)
        with col_b:
            st.markdown(f"<p style='color:#333; font-size:16px;'>預估週期</p><p style='color:#000; font-size:24px; font-weight:bold;'>{suggested_cycle} 秒</p>", unsafe_allow_html=True)
        final_tonnage = suggested_tonnage
        final_cycle = suggested_cycle
        
st.markdown('</div>', unsafe_allow_html=True)

# 執行計算
calculator = SmartInjectionQuote(weight_g, material, batch_size, thickness, packing, final_tonnage, final_cycle)
res = calculator.compute()

if res:
    final_total_int = int(round(res['Total_Price']))
    
    st.markdown(f"""
    <div class="apple-card">
        <p style="text-align: center; color: #000000; font-size: 20px; font-weight: bold; margin-bottom: 0;">預估單價 (NTD)</p>
        <div class="price-tag">${final_total_int}</div>
        <hr style="border: 0; border-top: 2px solid #e5e5ea; margin: 20px 0;">
    """, unsafe_allow_html=True)
    
    for item in res["Cost_Structure"]:
        val_int = int(round(item['val']))
        
        st.markdown(f"""
        <div class="list-item">
            <div style="flex: 3;">
                <div class="item-label-main">{item['name']}</div>
                <div class="item-label-sub">{item['sub']}</div>
            </div>
            <div class="item-value" style="flex: 1; text-align: right;">${val_int}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
        <div style="margin-top: 25px; text-align: center; font-size: 16px; color: #333333; font-weight: bold;">
            機台: {res['Meta']['機台']} | 週期: {res['Meta']['週期']}
        </div>
    </div>
    """, unsafe_allow_html=True)

st.button("更新報價 ↻", type="primary", use_container_width=True)
