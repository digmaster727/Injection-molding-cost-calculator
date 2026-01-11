import streamlit as st
import pandas as pd

# ==========================================
# 0. Apple UI 風格設定 (CSS魔法區)
# ==========================================
st.set_page_config(page_title="射出報價", page_icon="🍎", layout="centered")

# 隱藏 Streamlit 預設選單與 footer
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            
            /* Apple 風格卡片 */
            .apple-card {
                background-color: #ffffff;
                border-radius: 16px;
                padding: 20px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                margin-bottom: 20px;
                border: 1px solid #f0f0f5;
            }
            
            /* 報價大數字 */
            .price-tag {
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 42px;
                font-weight: 700;
                color: #007AFF; /* Apple Blue */
                text-align: center;
                margin-top: 10px;
                margin-bottom: 10px;
            }
            
            /* 列表項目 */
            .list-item {
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid #f0f0f5;
                font-family: -apple-system, sans-serif;
                color: #1c1c1e;
            }
            .list-item:last-child {
                border-bottom: none;
            }
            .item-label {
                font-size: 15px;
                color: #8e8e93; /* Apple Gray */
            }
            .item-value {
                font-size: 16px;
                font-weight: 600;
            }
            
            /* 輸入區塊背景微調 */
            .stApp {
                background-color: #F2F2F7; /* iOS Settings Background */
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 1. 系統參數與資料庫 (邏輯完全保留)
# ==========================================
ELEC_RATE = 5.0      
LOSS_RATE = 0.05     

MACHINE_DB = {
    (50, 99):   {"rate": 8,  "motor_kw": 15, "dry_cycle": 3.0, "max_weight": 80},
    (100, 199): {"rate": 13, "motor_kw": 30, "dry_cycle": 4.5, "max_weight": 250},
    (200, 299): {"rate": 15, "motor_kw": 45, "dry_cycle": 5.5, "max_weight": 450},
    (300, 399): {"rate": 17, "motor_kw": 60, "dry_cycle": 6.0, "max_weight": 800},
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
    "A級-工業散裝": {"rate": 2.0, "base": 0},
    "B級-獨立盒裝": {"rate": 8.0, "base": 0},
    "C級-外銷木箱": {"rate": 5.0, "base": 1200},
}

# 輔助函式
def get_auto_tonnage(weight):
    for r, data in MACHINE_DB.items():
        if weight <= data["max_weight"]: return int((r[0] + r[1]) / 2)
    return 350

def get_machine_data(t):
    for r, data in MACHINE_DB.items():
        if r[0] <= t <= r[1]: return data
    return {"rate": 20, "motor_kw": 50, "dry_cycle": 6.0}

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
        self.pack_data = PACKING_OPTIONS.get(packing, {"rate": 2.0, "base": 0})

    def compute(self):
        if not self.mat_data: return None
        # 五大成本計算
        unit_mat_cost = (self.weight / 1000) * self.mat_data["price"] * (1 + LOSS_RATE)
        rate = self.machine_data["rate"]
        m_factor = self.mat_data["factor"]
        unit_process_cost = rate * m_factor * (self.cycle_sec / 60)
        preheat_cost = (self.mat_data["dryer_kw"]*0.8) * self.mat_data["dry_time"] * ELEC_RATE
        unit_basic_cost = (1500 + preheat_cost) / self.batch
        w_kg = self.weight / 1000
        unit_pack_cost = (w_kg * self.pack_data["rate"]) + (self.pack_data["base"] / self.batch)
        total_w = w_kg * self.batch
        ship_total = max(500, total_w * 2.0)
        unit_ship_cost = ship_total / self.batch
        final_price = unit_mat_cost + unit_process_cost + unit_basic_cost + unit_pack_cost + unit_ship_cost

        return {
            "Meta": {"機台": f"{self.tonnage}T", "週期": f"{self.cycle_sec}s"},
            "Cost_Structure": [
                {"name": "材料費", "sub": "含5%損耗", "val": unit_mat_cost},
                {"name": "射出費", "sub": "含電費與技術加成", "val": unit_process_cost},
                {"name": "基本費", "sub": "暖機與調機攤提", "val": unit_basic_cost},
                {"name": "包裝費", "sub": self.packing.split('-')[0], "val": unit_pack_cost},
                {"name": "運費", "sub": "國內回頭車", "val": unit_ship_cost}
            ],
            "Total_Price": round(final_price, 2)
        }

# ==========================================
# 3. 前端介面設計 (Apple Style)
# ==========================================

# 標題區
st.markdown("<h2 style='text-align: center; color: #1c1c1e;'>Injection Cost</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8e8e93; font-size: 14px;'>無軸封泵浦報價系統 v3.0</p>", unsafe_allow_html=True)

# 輸入卡片
st.markdown('<div class="apple-card">', unsafe_allow_html=True)
st.markdown('<h4 style="color: #1c1c1e; margin-bottom: 15px;">產品參數</h4>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    weight_g = st.number_input("產品重量 (g)", value=200.0, step=10.0)
    batch_size = st.number_input("批量 (pcs)", value=50, step=50)
    packing = st.selectbox("包裝", list(PACKING_OPTIONS.keys()))
with col2:
    material = st.selectbox("材料", list(MATERIAL_DB.keys()), index=4)
    thickness = st.selectbox("壁厚", list(THICKNESS_OPTIONS.keys()), index=1)

# 即時運算邏輯
suggested_tonnage = get_auto_tonnage(weight_g)
temp_machine = get_machine_data(suggested_tonnage)
suggested_cycle = estimate_cycle(weight_g, material, thickness, temp_machine)

# 進階設定 (收合式)
with st.expander("進階設定 (機台/週期)"):
    use_manual = st.toggle("手動模式", value=False)
    if use_manual:
        final_tonnage = st.number_input("機台 (Ton)", value=suggested_tonnage)
        final_cycle = st.number_input("週期 (Sec)", value=suggested_cycle)
    else:
        st.caption(f"系統自動鎖定: {suggested_tonnage}噸 / {suggested_cycle}秒")
        final_tonnage = suggested_tonnage
        final_cycle = suggested_cycle
        
st.markdown('</div>', unsafe_allow_html=True) # End card

# 執行計算
calculator = SmartInjectionQuote(weight_g, material, batch_size, thickness, packing, final_tonnage, final_cycle)
res = calculator.compute()

if res:
    # 結果顯示區 - 模仿 Apple Wallet 交易明細
    st.markdown(f"""
    <div class="apple-card">
        <p style="text-align: center; color: #8e8e93; font-size: 14px; margin-bottom: 0;">預估單價</p>
        <div class="price-tag">NT$ {res['Total_Price']}</div>
        <hr style="border: 0; border-top: 1px solid #f0f0f5; margin: 20px 0;">
    """, unsafe_allow_html=True)
    
    # 迴圈生成美觀的列表
    for item in res["Cost_Structure"]:
        st.markdown(f"""
        <div class="list-item">
            <div>
                <div style="font-weight: 500;">{item['name']}</div>
                <div class="item-label">{item['sub']}</div>
            </div>
            <div class="item-value">${item['val']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # 底部資訊
    st.markdown(f"""
        <div style="margin-top: 20px; text-align: right; font-size: 12px; color: #c7c7cc;">
            機台: {res['Meta']['機台']} | 週期: {res['Meta']['週期']}
        </div>
    </div>
    """, unsafe_allow_html=True)

# 按鈕美化 (Streamlit 原生按鈕無法完全改 CSS，但可用 primary 藍色)
st.button("更新報價 ↻", type="primary", use_container_width=True)
