import streamlit as st
import pandas as pd

# ==========================================
# 0. 介面優化：大字體 + 純黑高對比 (High Contrast CSS)
# ==========================================
st.set_page_config(page_title="射出報價", page_icon="🏭", layout="centered")

# CSS 樣式表
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            
            /* 卡片背景：維持白色，但邊框加深 */
            .apple-card {
                background-color: #ffffff;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 6px 16px rgba(0,0,0,0.1);
                margin-bottom: 25px;
                border: 2px solid #d1d1d6; /* 邊框加深 */
            }
            
            /* 價格大字：由藍改深藍，字體特大 */
            .price-tag {
                font-family: sans-serif;
                font-size: 56px;  /* 特大 */
                font-weight: 800; /* 特粗 */
                color: #0040DD;   /* 深藍色 (高對比) */
                text-align: center;
                margin: 15px 0;
            }
            
            /* 列表項目容器 */
            .list-item {
                display: flex;
                justify-content: space-between;
                align-items: center; /* 垂直置中 */
                padding: 16px 0;     /* 間距拉大 */
                border-bottom: 2px solid #e5e5ea; /* 分隔線加粗 */
                color: #000000;      /* 純黑 */
            }
            .list-item:last-child {
                border-bottom: none;
            }
            
            /* 項目名稱 (左邊) */
            .item-label-main {
                font-size: 22px;     /* 放大 */
                font-weight: 700;    /* 加粗 */
                color: #000000;      /* 純黑 */
            }
            .item-label-sub {
                font-size: 16px;
                color: #333333;      /* 深灰，不做淺灰 */
                margin-top: 4px;
            }
            
            /* 項目數值 (右邊) */
            .item-value {
                font-size: 24px;     /* 放大 */
                font-weight: 700;    /* 加粗 */
                color: #000000;      /* 純黑 */
            }
            
            /* 調整 Streamlit 原生輸入框字體 */
            .stNumberInput input, .stSelectbox div[data-baseweb="select"] div {
                font-size: 18px !important;
                font-weight: 600 !important;
                color: #000000 !important;
            }
            p, label {
                font-size: 18px !important;
                color: #000000 !important;
                font-weight: 600 !important;
            }
            
            /* 背景設為淺灰，對比白色卡片 */
            .stApp {
                background-color: #f0f0f2;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 1. 系統參數與資料庫 (維持不變)
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
                {"name": "1.材料費", "sub": "含5%損耗", "val": unit_mat_cost},
                {"name": "2.射出費", "sub": "機台+技術+電費", "val": unit_process_cost},
                {"name": "3.基本費", "sub": "暖機電費+調機", "val": unit_basic_cost},
                {"name": "4.包裝費", "sub": self.packing.split('-')[0], "val": unit_pack_cost},
                {"name": "5.運費", "sub": "國內回頭車", "val": unit_ship_cost}
            ],
            "Total_Price": round(final_price, 2)
        }

# ==========================================
# 3. 前端介面設計 (大字體版)
# ==========================================

# 標題區
st.markdown("<h2 style='text-align: center; color: #000000; font-weight: 800; font-size: 32px;'>射出成本計算 v3.1</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #333333; font-size: 18px; font-weight: bold;'>無軸封泵浦品技課專用</p>", unsafe_allow_html=True)

# 輸入卡片
st.markdown('<div class="apple-card">', unsafe_allow_html=True)

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

st.divider() # 分隔線

# 進階設定 (字體加粗)
with st.expander("🛠️ 進階設定 (手動輸入機台/週期)"):
    use_manual = st.toggle("開啟手動模式", value=False)
    if use_manual:
        final_tonnage = st.number_input("機台噸數 (Ton)", value=suggested_tonnage)
        final_cycle = st.number_input("成形週期 (秒)", value=suggested_cycle)
    else:
        # 顯示自動計算結果
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"<p style='color:#333; font-size:16px;'>建議機台</p><p style='color:#000; font-size:24px; font-weight:bold;'>{suggested_tonnage} 噸</p>", unsafe_allow_html=True)
        with col_b:
            st.markdown(f"<p style='color:#333; font-size:16px;'>預估週期</p><p style='color:#000; font-size:24px; font-weight:bold;'>{suggested_cycle} 秒</p>", unsafe_allow_html=True)
        final_tonnage = suggested_tonnage
        final_cycle = suggested_cycle
        
st.markdown('</div>', unsafe_allow_html=True) # End input card

# 執行計算
calculator = SmartInjectionQuote(weight_g, material, batch_size, thickness, packing, final_tonnage, final_cycle)
res = calculator.compute()

if res:
    # 結果顯示區
    st.markdown(f"""
    <div class="apple-card">
        <p style="text-align: center; color: #000000; font-size: 20px; font-weight: bold; margin-bottom: 0;">預估單價 (NTD)</p>
        <div class="price-tag">${res['Total_Price']}</div>
        <hr style="border: 0; border-top: 2px solid #e5e5ea; margin: 20px 0;">
    """, unsafe_allow_html=True)
    
    # 迴圈生成高對比列表
    for item in res["Cost_Structure"]:
        st.markdown(f"""
        <div class="list-item">
            <div>
                <div class="item-label-main">{item['name']}</div>
                <div class="item-label-sub">{item['sub']}</div>
            </div>
            <div class="item-value">${item['val']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # 底部資訊
    st.markdown(f"""
        <div style="margin-top: 25px; text-align: center; font-size: 16px; color: #333333; font-weight: bold;">
            機台: {res['Meta']['機台']} | 週期: {res['Meta']['週期']}
        </div>
    </div>
    """, unsafe_allow_html=True)

# 按鈕
st.button("更新報價 ↻", type="primary", use_container_width=True)
