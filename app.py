import streamlit as st
import pandas as pd

# ==========================================
# 1. 系統參數與資料庫
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
    "PPC":  {"price": 258.1,"factor": 1.8, "dryer_kw": 3, "dry_time": 2, "high_temp": False}, # 新增 PPC
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

# ==========================================
# 2. 運算邏輯核心
# ==========================================
class SmartInjectionQuote:
    def __init__(self, weight_g, material, batch_size, 
                 thickness="一般 (<5mm)", packing="A級-工業散裝", 
                 manual_tonnage=None):
        self.weight = weight_g
        self.material = material
        self.batch = batch_size
        self.thickness = thickness
        self.packing = packing
        
        if manual_tonnage and manual_tonnage > 0:
            self.tonnage = manual_tonnage
            self.auto_selected = False
        else:
            self.tonnage = self._auto_suggest_tonnage(weight_g)
            self.auto_selected = True
            
        self.machine_data = self._get_machine_data(self.tonnage)
        self.mat_data = MATERIAL_DB.get(material, {})
        self.thick_factor = THICKNESS_OPTIONS.get(thickness, 1.0)
        self.pack_data = PACKING_OPTIONS.get(packing, {"rate": 2.0, "base": 0})

    def _auto_suggest_tonnage(self, w):
        for r, data in MACHINE_DB.items():
            if w <= data["max_weight"]:
                return int((r[0] + r[1]) / 2)
        return 350

    def _get_machine_data(self, t):
        for r, data in MACHINE_DB.items():
            if r[0] <= t <= r[1]: return data
        return {"rate": 20, "motor_kw": 50, "dry_cycle": 6.0}

    def compute(self, manual_cycle_sec=None):
        if not self.mat_data: return None

        if manual_cycle_sec and manual_cycle_sec > 0:
            cycle_sec = float(manual_cycle_sec)
            cycle_note = "手動鎖定"
        else:
            base_cool = (self.weight / 100) * 15.0
            mat_temp_factor = 1.4 if self.mat_data["high_temp"] else 1.0
            cycle_sec = self.machine_data["dry_cycle"] + \
                        ((self.weight/100)*4.0) + \
                        (base_cool * mat_temp_factor * self.thick_factor)
            cycle_sec = int(cycle_sec)
            cycle_note = "自動計算"

        # 五大成本
        unit_mat_cost = (self.weight / 1000) * self.mat_data["price"] * (1 + LOSS_RATE)
        formula_mat = f"{self.weight/1000}kg * ${self.mat_data['price']} * 1.05"

        rate = self.machine_data["rate"]
        m_factor = self.mat_data["factor"]
        unit_process_cost = rate * m_factor * (cycle_sec / 60)
        formula_process = f"${rate}/分 * 係數{m_factor} * ({cycle_sec}s/60)"

        preheat_cost = (self.mat_data["dryer_kw"]*0.8) * self.mat_data["dry_time"] * ELEC_RATE
        setup_total = 1500 + preheat_cost
        unit_basic_cost = setup_total / self.batch
        formula_basic = f"(調機$1500+電費${int(preheat_cost)})/{self.batch}"

        w_kg = self.weight / 1000
        unit_pack_cost = (w_kg * self.pack_data["rate"]) + (self.pack_data["base"] / self.batch)
        formula_pack = f"({w_kg}kg*${self.pack_data['rate']}) + (基費/{self.batch})"

        total_w = w_kg * self.batch
        ship_total = max(500, total_w * 2.0)
        unit_ship_cost = ship_total / self.batch
        formula_ship = f"總運費${int(ship_total)} / {self.batch}"

        final_price = unit_mat_cost + unit_process_cost + unit_basic_cost + unit_pack_cost + unit_ship_cost

        return {
            "Meta": {
                "機台": f"{self.tonnage}T ({'自動' if self.auto_selected else '手動'})",
                "週期": f"{cycle_sec}s ({cycle_note})"
            },
            "Cost_Structure": [
                {"項目": "1.材料成本 (含5%損)", "計算式": formula_mat, "金額": round(unit_mat_cost, 2)},
                {"項目": "2.射出加工 (含電費)", "計算式": formula_process, "金額": round(unit_process_cost, 2)},
                {"項目": "3.基本攤提 (含暖機)", "計算式": formula_basic, "金額": round(unit_basic_cost, 2)},
                {"項目": "4.包裝費用", "計算式": formula_pack, "金額": round(unit_pack_cost, 2)},
                {"項目": "5.運費分攤 (國內)", "計算式": formula_ship, "金額": round(unit_ship_cost, 2)}
            ],
            "Total_Price": round(final_price, 2)
        }

# ==========================================
# 3. Streamlit 網頁介面設計
# ==========================================
st.set_page_config(page_title="射出報價計算器", page_icon="🏭")

st.title("🏭 塑膠射出成本計算 v2.0")
st.markdown("無軸封泵浦品技課專用 | 2026/01/11 Update")

# 輸入區塊
with st.container():
    st.subheader("1. 產品參數")
    col1, col2 = st.columns(2)
    with col1:
        weight_g = st.number_input("產品重量 (g)", min_value=1.0, value=200.0, step=10.0)
        batch_size = st.number_input("生產批量 (pcs)", min_value=1, value=50, step=50)
    with col2:
        material = st.selectbox("材料種類", list(MATERIAL_DB.keys()), index=2) # 預設 ETFE+CF
        thickness = st.selectbox("壁厚特徵", list(THICKNESS_OPTIONS.keys()), index=1) # 預設中厚

    st.subheader("2. 後勤設定")
    packing = st.selectbox("包裝等級", list(PACKING_OPTIONS.keys()))
    
    # 進階設定 (用 Expander 收摺起來，保持介面乾淨)
    with st.expander("🛠️ 進階設定 (機台/週期手動調整)"):
        use_manual_tonnage = st.checkbox("手動指定機台噸數?")
        manual_tonnage = st.number_input("機台噸數 (Ton)", value=150, disabled=not use_manual_tonnage)
        
        use_manual_cycle = st.checkbox("手動指定成形週期?")
        manual_cycle = st.number_input("成形週期 (秒)", value=60, disabled=not use_manual_cycle)

# 計算按鈕
if st.button("🚀 開始計算報價", type="primary", use_container_width=True):
    # 執行計算
    calculator = SmartInjectionQuote(
        weight_g=weight_g,
        material=material,
        batch_size=batch_size,
        thickness=thickness,
        packing=packing,
        manual_tonnage=manual_tonnage if use_manual_tonnage else None
    )
    
    res = calculator.compute(manual_cycle_sec=manual_cycle if use_manual_cycle else None)
    
    if res:
        st.divider()
        # 結果顯示區
        st.subheader("💰 報價結果")
        
        # 大字顯示單價
        st.metric(label="預估單價 (NTD)", value=f"${res['Total_Price']}")
        
        # 顯示參數摘要
        st.info(f"機台: {res['Meta']['機台']} | 週期: {res['Meta']['週期']}")
        
        # 顯示五大成本表
        df = pd.DataFrame(res["Cost_Structure"])
        st.table(df)
        
    else:
        st.error("計算錯誤，請檢查輸入參數")
