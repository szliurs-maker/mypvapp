import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import folium
import requests
from streamlit_folium import st_folium
from folium.plugins import Draw
from shapely.geometry import shape
from pyproj import Geod
import plotly.graph_objects as go

# ==========================================
# 1. 核心配置
# ==========================================
st.set_page_config(page_title="工商业分布式光伏评估系统 V2.0", layout="wide")

# 自定义CSS - 统一字体大小
st.markdown("""
<style>
    /* metric数值字体大小 */
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px !important;
    }
    /* 按钮上方文字 */
    div.stButton > button {
        font-size: 16px !important;
    }
</style>
""", unsafe_allow_html=True)

# Session状态初始化
if 'map_center' not in st.session_state: st.session_state.map_center = [23.13, 113.26]
if 'addr_key' not in st.session_state: st.session_state.addr_key = 0
if 'regions' not in st.session_state: st.session_state.regions = []
if 'finalized_schemes' not in st.session_state: st.session_state.finalized_schemes = {}

# ==========================================
# 2. 数据库配置
# ==========================================

# 高德API Key
AMAP_API_KEY = "081498e4c80444c1f89ef480f33f5b54"

# 组件数据库
PANEL_DB = {
    "隆基": {
        "Hi-MO 6 LR5-72HPH": {"power": 585, "efficiency": 22.8, "price": 0.95},
        "Hi-MO 6 LR5-66HPH": {"power": 545, "efficiency": 22.5, "price": 0.92},
        "Hi-MO 5 LR5-72HBD": {"power": 550, "efficiency": 21.3, "price": 0.85},
    },
    "晶科": {
        "N-type Tiger Neo 72HC": {"power": 620, "efficiency": 23.0, "price": 1.05},
        "N-type Tiger Neo 66HC": {"power": 565, "efficiency": 22.8, "price": 1.02},
        "P-type Tiger Pro 72HC": {"power": 545, "efficiency": 21.1, "price": 0.88},
    },
    "通威": {
        "TWMNG-72HD": {"power": 580, "efficiency": 22.5, "price": 0.90},
        "TWMNG-66HD": {"power": 530, "efficiency": 22.2, "price": 0.87},
    },
    "天合": {
        "Vertex S+ N-type 72R": {"power": 615, "efficiency": 23.0, "price": 1.08},
        "Vertex S 72TR": {"power": 565, "efficiency": 21.7, "price": 0.93},
    },
    "阿特斯": {
        "HiKu7 PERC 72": {"power": 555, "efficiency": 21.6, "price": 0.86},
        "BiHiKu7 N-type 72": {"power": 605, "efficiency": 22.8, "price": 1.00},
    },
}

# 逆变器数据库
INV_DB = {
    "华为": {
        "SUN2000-50KTL-M3": {"power": 50, "type": "三相", "price": 0.18},
        "SUN2000-100KTL-M2": {"power": 100, "type": "三相", "price": 0.15},
        "SUN2000-150KTL-M2": {"power": 150, "type": "三相", "price": 0.13},
    },
    "阳光电源": {
        "SG110CX": {"power": 110, "type": "三相", "price": 0.14},
        "SG225CX": {"power": 225, "type": "三相", "price": 0.11},
        "SG320HX": {"power": 320, "type": "三相", "price": 0.09},
    },
    "古瑞瓦特": {
        "Growatt 50KTL3": {"power": 50, "type": "三相", "price": 0.16},
        "Growatt 100KTL3": {"power": 100, "type": "三相", "price": 0.13},
    },
    "锦浪": {
        "GCI-110K-48G": {"power": 110, "type": "三相", "price": 0.14},
        "GCI-150K-48G": {"power": 150, "type": "三相", "price": 0.12},
    },
}

# 支架数据库
STRUCTURE_DB = {
    "彩钢瓦支架": {
        "力诺光伏": {"type": "彩钢瓦", "material": "铝合金", "price": 0.15},
        "阳光新能源": {"type": "彩钢瓦", "material": "热镀锌", "price": 0.12},
    },
    "水泥基础支架": {
        "力诺光伏": {"type": "水泥", "material": "热镀锌", "price": 0.25},
        "阳光新能源": {"type": "水泥", "material": "铝合金", "price": 0.28},
    },
    "钢结构支架": {
        "阳光新能源": {"type": "钢结构", "material": "热镀锌", "price": 0.45},
        "精工钢构": {"type": "钢结构", "material": "热镀锌", "price": 0.42},
    },
}

# 电压等级数据库
VOLTAGE_DB = {
    "400V 低压": {"voltage": "400V", "price": 0.075},
    "10kV 中压": {"voltage": "10kV", "price": 0.25},
    "35kV 高压": {"voltage": "35kV", "price": 0.35},
}

GUANGDONG_GRID_PRICE = 0.453

# ==========================================
# 3. 工具函数
# ==========================================

def calculate_area_geo(geojson):
    """计算GeoJSON面积（平方米）"""
    try:
        geod = Geod(ellps="WGS84")
        poly = shape(geojson)
        return abs(geod.geometry_area_perimeter(poly)[0])
    except:
        return 0

def get_rectangle_dims(geojson):
    """获取矩形的长宽"""
    try:
        poly = shape(geojson)
        bounds = poly.bounds
        width = (bounds[2] - bounds[0]) * 111000 * np.cos(np.radians(st.session_state.map_center[0]))
        height = (bounds[3] - bounds[1]) * 111000
        return max(width, height), min(width, height)
    except:
        return 0, 0

def get_coords_amap(address):
    """高德地图API地址转坐标"""
    if not address or len(address.strip()) < 2 or not AMAP_API_KEY:
        return None
    url = "https://restapi.amap.com/v3/geocode/geo"
    try:
        response = requests.get(url, params={"key": AMAP_API_KEY, "address": address.strip()}, timeout=5)
        data = response.json()
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0].get("location", "")
            if location:
                parts = location.split(",")
                return [float(parts[1]), float(parts[0])]
    except:
        pass
    return None

def run_finance_engine(capacity_kw, bom_cost, inv_unit_price, region_name, region_area):
    """财务核算引擎"""
    fee_dev = st.session_state.get('fee_dev', 0.10)
    fee_manage = st.session_state.get('fee_manage', 0.12)
    elec_part = 0.12
    install_fee = 0.35
    elec_p = st.session_state.get('elec_p', 0.55)
    self_use = st.session_state.get('self_use', 0.70)
    collection_rate = st.session_state.get('collection_rate', 0.98)
    loan_ratio = st.session_state.get('loan_ratio', 0.70)
    loan_rate = st.session_state.get('loan_rate', 0.032)
    loan_term = st.session_state.get('loan_term', 10)
    full_hours = st.session_state.get('full_hours', 1100)

    total_inv = capacity_kw * 1000 * bom_cost
    input_vat = total_inv / 1.13 * 0.13
    equity = total_inv * (1 - loan_ratio)
    loan_amt = total_inv * loan_ratio
    pmt = npf.pmt(loan_rate, loan_term, -loan_amt) if loan_amt > 0 else 0

    proforma = []
    rem_loan = loan_amt
    accum_vat = input_vat

    for y in range(1, 26):
        deg = (1-0.05) if y==1 else (1-0.05-(y-1)*0.004)
        gen = capacity_kw * full_hours * deg
        gross_rev = gen * (elec_p * self_use + GUANGDONG_GRID_PRICE * (1 - self_use))
        actual_rev = gross_rev * collection_rate
        output_vat = actual_rev / 1.13 * 0.13
        payable_vat = max(0, output_vat - accum_vat)
        accum_vat = max(0, accum_vat - output_vat)
        surcharge = payable_vat * 0.12
        opex = capacity_kw * 1000 * 0.05 * (1.02**(y-1))
        inv_replace = (capacity_kw * 1000 * inv_unit_price) if y == 10 else 0
        interest = rem_loan * loan_rate if y <= loan_term else 0
        net_rev_ex_tax = actual_rev - output_vat
        ebt = net_rev_ex_tax - opex - inv_replace - interest - (total_inv/1.13 * 0.0475) - surcharge
        income_tax = max(0, ebt * 0.25)
        cfads = actual_rev - opex - inv_replace - payable_vat - surcharge - income_tax
        dscr = cfads / pmt if (y <= loan_term and pmt > 0) else 3.0
        equity_cf = cfads - (pmt if y <= loan_term else 0)
        proforma.append({"年份": y, "CFADS": cfads, "净现金流": equity_cf, "DSCR": dscr, "发电量": gen})
        if y <= loan_term: rem_loan -= (pmt - interest)

    df = pd.DataFrame(proforma)
    p_irr = npf.irr([-total_inv] + df["CFADS"].tolist()) * 100 if len(df) > 0 else 0
    e_irr = npf.irr([-equity] + df["净现金流"].tolist()) * 100 if len(df) > 0 else 0

    return {"p_irr": p_irr, "e_irr": e_irr, "min_dscr": df["DSCR"].min() if len(df) > 0 else 0,
            "data": df, "total_inv": total_inv, "capacity": capacity_kw, "area": region_area}

# ==========================================
# 4. 侧边栏参数
# ==========================================
with st.sidebar:
    st.header("⚙️ 核心参数配置")

    with st.expander("📍 1. 项目定位", expanded=True):
        col_addr1, col_addr2 = st.columns([3, 1])
        with col_addr1:
            addr = st.text_input("项目地址", placeholder="输入地址搜索", key=f"addr_input_{st.session_state.addr_key}")
        with col_addr2:
            st.write("")
        if st.button("🔍 定位", type="primary"):
            if addr and len(addr.strip()) >= 2:
                with st.spinner("搜索中..."):
                    coords = get_coords_amap(addr)
                    if coords:
                        st.session_state.map_center = coords
                        st.session_state.addr_key += 1
                        st.success("✓ 已定位")
                        st.rerun()
                    else:
                        st.error("未找到地址")
        st.caption(f"坐标: {st.session_state.map_center[0]:.4f}, {st.session_state.map_center[1]:.4f}")
        st.session_state.full_hours = st.number_input("年利用小时数", 500, 2500, 1100, key="fhours")

    with st.expander("💰 2. 财务参数", expanded=True):
        st.session_state.elec_p = st.number_input("综合电价 (元/kWh)", 0.0, 2.0, 0.55, step=0.01)
        st.session_state.self_use = st.slider("自用比例 (%)", 0, 100, 70) / 100
        st.session_state.collection_rate = st.slider("电费收缴率 (%)", 80, 100, 98) / 100

    with st.expander("🏗️ 3. 成本参数", expanded=True):
        st.session_state.fee_dev = st.number_input("开发费 (元/W)", 0.0, 1.0, 0.10, step=0.01)
        st.session_state.fee_manage = st.number_input("管理费 (元/W)", 0.0, 0.5, 0.12, step=0.01)
        st.session_state.loan_ratio = st.slider("融资比例 (%)", 0, 90, 70) / 100
        st.session_state.loan_rate = st.number_input("贷款利率 (%)", 1.0, 8.0, 3.2) / 100
        st.session_state.loan_term = st.number_input("贷款年限", 1, 20, 10)

# ==========================================
# 5. 主界面
# ==========================================
st.title("☀️ 工商业分布式光伏系统评估系统 V2.0")

# --- 模块一：项目测绘与面积确认 ---
st.header("一、项目测绘与面积确认")
st.info("📍 在侧边栏输入地址定位后，在下方地图上框选目标区域")

# 使用folium地图进行框选
m_backup = folium.Map(location=st.session_state.map_center, zoom_start=18, zoom_control=True)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri Satellite'
).add_to(m_backup)
Draw(export=False).add_to(m_backup)
map_res = st_folium(m_backup, height=500, use_container_width=True)

# 处理地图框选数据，自动添加区域
if map_res and map_res.get('all_drawings'):
    for d in map_res['all_drawings']:
        geo = d['geometry']
        area = calculate_area_geo(geo)
        length, width = get_rectangle_dims(geo)
        area_calc = length * width
        if area_calc > 0:
            # 自动添加区域
            new_region = {
                "name": f"区域{len(st.session_state.regions)+1}",
                "length": length,
                "width": width,
                "area": area_calc,
                "geometry": geo,
                "tech_config": None,
                "scheme_result": None
            }
            # 检查是否已存在相同区域
            exists = any(r.get('geometry') == geo for r in st.session_state.regions)
            if not exists:
                st.session_state.regions.append(new_region)
                st.success(f"✓ 已自动添加 {new_region['name']}")

# 显示所有区域信息
if st.session_state.regions:
    st.divider()
    st.subheader("📐 已添加区域列表")
    for i, r in enumerate(st.session_state.regions):
        with st.expander(f"📍 {r['name']} - 面积: {r['area']:,.0f} m²", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("长度", f"{r['length']:.1f} m")
            col2.metric("宽度", f"{r['width']:.1f} m")
            col3.metric("面积", f"{r['area']:,.2f} m²")
            if st.button(f"🗑️ 删除 {r['name']}", key=f"del_{i}"):
                st.session_state.regions.pop(i)
                st.rerun()

    # 确认按钮
    if st.button("✅ 确认并进入技术选型", type="primary", use_container_width=True):
        st.session_state.finalized_schemes = {}
        st.success("区域已确认，可进入技术选型")

# --- 模块二：技术选型与配置 ---
st.divider()
st.header("二、技术选型与造价配置")

if not st.session_state.regions:
    st.info("请先在【项目测绘】模块添加并确认区域")
else:
    # 显示所有区域的技术选型配置
    for idx, region in enumerate(st.session_state.regions):
        with st.expander(f"📍 {region['name']} - 面积: {region['area']:,.0f} m²", expanded=True):
            # 技术选型配置
            col_panel, col_inv, col_other = st.columns(3)

            with col_panel:
                st.subheader("🔆 组件选型")
                panel_mfr = st.selectbox("组件厂家", list(PANEL_DB.keys()), key=f"pmfr_{idx}")
                panel_model = st.selectbox("组件型号", list(PANEL_DB[panel_mfr].keys()), key=f"pmdl_{idx}")
                panel_info = PANEL_DB[panel_mfr][panel_model]
                panel_power = panel_info['power']
                panel_eff = panel_info['efficiency']
                panel_price = st.number_input("组件单价 (元/W)", value=panel_info['price'], min_value=0.0, step=0.01, key=f"pprice_{idx}")
                st.caption(f"功率: {panel_power}W | 效率: {panel_eff}%")

            with col_inv:
                st.subheader("🔌 逆变器选型")
                inv_mfr = st.selectbox("逆变器厂家", list(INV_DB.keys()), key=f"imfr_{idx}")
                inv_model = st.selectbox("逆变器型号", list(INV_DB[inv_mfr].keys()), key=f"imdl_{idx}")
                inv_info = INV_DB[inv_mfr][inv_model]
                inv_power = inv_info['power']
                inv_price = st.number_input("逆变器单价 (元/W)", value=inv_info['price'], min_value=0.0, step=0.01, key=f"iprice_{idx}")
                st.caption(f"功率: {inv_power}kW | 类型: {inv_info['type']}")

            with col_other:
                st.subheader("⚡ 其他设备")
                struct_type = st.selectbox("支架类型", list(STRUCTURE_DB.keys()), key=f"stype_{idx}")
                struct_mfr = st.selectbox("支架厂家", list(STRUCTURE_DB[struct_type].keys()), key=f"smfr_{idx}")
                struct_info = STRUCTURE_DB[struct_type][struct_mfr]
                struct_price = st.number_input("支架单价 (元/W)", value=struct_info['price'], min_value=0.0, step=0.01, key=f"sprice_{idx}")
                st.caption(f"类型: {struct_info['type']} | 材质: {struct_info['material']}")

                voltage = st.selectbox("电压等级", list(VOLTAGE_DB.keys()), key=f"vol_{idx}")
                vol_info = VOLTAGE_DB[voltage]
                vol_price = st.number_input("并网单价 (元/W)", value=vol_info['price'], min_value=0.0, step=0.01, key=f"vprice_{idx}")

            # 计算
            area = region['area']
            capacity = (area * panel_eff / 100) / 1000 * 1000

            # 造价计算
            fee_dev = st.session_state.get('fee_dev', 0.10)
            fee_manage = st.session_state.get('fee_manage', 0.12)
            elec_part = 0.12
            install_fee = 0.35

            bom = panel_price + inv_price + struct_price + vol_price + elec_part + install_fee + fee_dev + fee_manage

            # 财务计算
            res = run_finance_engine(capacity, bom, inv_price, region['name'], area)

            # 显示结果
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("装机容量", f"{capacity:,.1f} kW")
            c2.metric("系统造价", f"{bom:.2f} 元/W")
            c3.metric("Project IRR", f"{res['p_irr']:.2f}%")
            c4.metric("最低DSCR", f"{res['min_dscr']:.2f}")

            # 保存配置
            tech_config = {
                "panel": {"mfr": panel_mfr, "model": panel_model, "power": panel_power, "price": panel_price},
                "inverter": {"mfr": inv_mfr, "model": inv_model, "power": inv_power, "price": inv_price},
                "structure": {"type": struct_type, "mfr": struct_mfr, "price": struct_price},
                "voltage": {"level": voltage, "price": vol_price},
                "bom": bom, "capacity": capacity, "finance_result": res
            }
            st.session_state.regions[idx]['tech_config'] = tech_config

            # 确认按钮
            c_confirm, c_status = st.columns([2, 1])
            with c_confirm:
                if st.button("✅ 确认方案", type="primary", use_container_width=True, key=f"confirm_{idx}"):
                    st.session_state.finalized_schemes[idx] = tech_config
                    st.success(f"✓ {region['name']} 方案已确认")
            with c_status:
                if idx in st.session_state.finalized_schemes:
                    st.info("✓ 已确认")

    # 总体确认进度
    if st.session_state.finalized_schemes:
        st.info(f"已确认 {len(st.session_state.finalized_schemes)}/{len(st.session_state.regions)} 个区域")

# --- 模块三：深度财务测算 ---
st.divider()
st.header("三、深度财务测算")

if not st.session_state.finalized_schemes:
    st.info("请在【技术选型】模块确认至少一个方案")
else:
    finalized_names = [st.session_state.regions[i]['name'] for i in st.session_state.finalized_schemes.keys()]
    view_idx = st.selectbox("选择查看区域", list(st.session_state.finalized_schemes.keys()),
                           format_func=lambda x: finalized_names[x] if x < len(finalized_names) else f"区域{x+1}")

    active = st.session_state.finalized_schemes[view_idx]
    finance_data = active['finance_result']['data']

    fig = go.Figure()
    fig.add_trace(go.Bar(x=finance_data["年份"], y=finance_data["净现金流"], name="股东净现金流", marker_color='#0F172A'))
    fig.add_trace(go.Scatter(x=finance_data["年份"], y=finance_data["DSCR"], name="DSCR", yaxis="y2", line=dict(color='#F43F5E', width=3)))
    fig.update_layout(xaxis=dict(tickmode='linear', tick0=1, dtick=1, title="运营年份"),
                     yaxis=dict(title="金额 (元)"), yaxis2=dict(title="DSCR", overlaying='y', side='right', range=[0, 4]),
                     legend=dict(orientation="h", y=1.1), hovermode="x unified", height=450)
    st.plotly_chart(fig, use_container_width=True)

    c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
    c_kpi1.metric("Project IRR", f"{active['finance_result']['p_irr']:.2f}%")
    c_kpi2.metric("Equity IRR", f"{active['finance_result']['e_irr']:.2f}%")
    c_kpi3.metric("最低DSCR", f"{active['finance_result']['min_dscr']:.2f}")
    c_kpi4.metric("总投资", f"¥{active['finance_result']['total_inv']:,.0f}")

# --- 模块四：BOM清单与报价 ---
st.divider()
st.header("四、BOM清单与报价")

if not st.session_state.finalized_schemes:
    st.info("请在【技术选型】模块确认方案后查看BOM清单")
else:
    # 汇总数据
    all_items = []
    total_capacity = 0
    total_investment = 0

    for idx, scheme in st.session_state.finalized_schemes.items():
        region = st.session_state.regions[idx]
        panel = scheme['panel']
        inverter = scheme['inverter']
        struct = scheme['structure']
        voltage = scheme['voltage']

        capacity = scheme['capacity']
        area = region['area']
        panel_qty = int(capacity * 1000 / panel['power'])
        inv_qty = int(np.ceil(capacity / inverter['power']))

        # 组件
        all_items.append({
            "类别": "组件", "厂家": panel['mfr'], "型号": panel['model'],
            "功率(W)": panel['power'], "数量": panel_qty, "单价(元/W)": panel['price'],
            "总价(元)": round(panel_qty * panel['power'] * panel['price'])
        })
        # 逆变器（功率转换为W，单价按元/W计算）
        all_items.append({
            "类别": "逆变器", "厂家": inverter['mfr'], "型号": inverter['model'],
            "功率(W)": inverter['power'] * 1000, "数量": inv_qty, "单价(元/W)": inverter['price'],
            "总价(元)": round(inv_qty * inverter['power'] * 1000 * inverter['price'])
        })
        # 支架
        all_items.append({
            "类别": "支架", "厂家": struct['mfr'], "型号": f"{struct['type']}-{struct['mfr']}",
            "功率(W)": "-", "数量": 1, "单价(元/W)": struct['price'],
            "总价(元)": round(capacity * 1000 * struct['price'])
        })

        total_capacity += capacity
        total_investment += scheme['finance_result']['total_inv']

    # BOM清单表（按厂家、型号、功率、数量、单价、总价）
    st.subheader("📦 设备清单")
    df_items = pd.DataFrame(all_items)
    df_items_display = df_items[["类别", "厂家", "型号", "功率(W)", "数量", "单价(元/W)", "总价(元)"]]
    st.dataframe(df_items_display.style.format({
        "单价(元/W)": "{:.2f}", "总价(元)": "{:,.0f}"
    }), use_container_width=True)

    # 下载按钮
    col_dl1, _ = st.columns([1, 5])
    with col_dl1:
        csv_items = df_items.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载设备清单", data=csv_items, file_name="BOM设备清单.csv", mime="text/csv", use_container_width=True)

    # 整体报价清单（按分类统计）
    st.divider()
    st.subheader("💰 整体报价清单")

    quote_by_category = {
        "组件": 0, "逆变器": 0, "支架": 0, "电气设备": 0, "安装费": 0, "管理费": 0, "税费": 0
    }

    for idx, scheme in st.session_state.finalized_schemes.items():
        region = st.session_state.regions[idx]
        capacity = scheme['capacity']
        total = scheme['finance_result']['total_inv']
        panel = scheme['panel']
        inverter = scheme['inverter']
        struct = scheme['structure']
        vol = scheme['voltage']

        panel_cost = capacity * 1000 * panel['price']
        inv_cost = capacity * 1000 * inverter['price']
        struct_cost = capacity * 1000 * struct['price']
        vol_cost = capacity * 1000 * vol['price']
        install_cost = capacity * 1000 * 0.35
        fee_total = capacity * 1000 * (st.session_state.get('fee_dev', 0.10) + st.session_state.get('fee_manage', 0.12))
        elec_cost = capacity * 1000 * 0.12

        quote_by_category["组件"] += panel_cost
        quote_by_category["逆变器"] += inv_cost
        quote_by_category["支架"] += struct_cost
        quote_by_category["电气设备"] += vol_cost + elec_cost
        quote_by_category["安装费"] += install_cost
        quote_by_category["管理费"] += fee_total
        quote_by_category["税费"] += total * 0.0475

    df_quote = pd.DataFrame([
        {"项目": k, "金额(元)": v, "占比(%)": v/total_investment*100 if total_investment > 0 else 0}
        for k, v in quote_by_category.items()
    ])
    # 添加汇总行
    total_row = {"项目": "项目总价", "金额(元)": total_investment, "占比(%)": 100.0}
    df_quote = pd.concat([df_quote, pd.DataFrame([total_row])], ignore_index=True)
    st.dataframe(df_quote.style.format({"金额(元)": "¥{:,.0f}", "占比(%)": "{:.1f}"}), use_container_width=True)

    # 下载按钮
    col_dl2, _ = st.columns([1, 5])
    with col_dl2:
        csv_quote = df_quote.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下载报价清单", data=csv_quote, file_name="报价清单.csv", mime="text/csv", use_container_width=True)

    # 计算整体项目IRR（加权平均）
    overall_irr = 0
    if total_investment > 0:
        weighted_irr = sum(scheme['finance_result']['p_irr'] * scheme['finance_result']['total_inv']
                          for scheme in st.session_state.finalized_schemes.values())
        overall_irr = weighted_irr / total_investment if total_investment > 0 else 0

    # 投资汇总（5小块展示）
    st.divider()
    st.subheader("📊 投资汇总")
    c_sum1, c_sum2, c_sum3, c_sum4, c_sum5 = st.columns(5)
    c_sum1.metric("总面积", f"{sum(r['area'] for r in st.session_state.regions):,.0f} m²")
    c_sum2.metric("总装机容量", f"{total_capacity:,.1f} kW")
    c_sum3.metric("总投资额", f"¥{total_investment:,.0f}")
    c_sum4.metric("单位造价", f"¥{total_investment/(total_capacity*1000):,.2f} 元/Wp" if total_capacity > 0 else "¥0")
    c_sum5.metric("Project IRR", f"{overall_irr:.2f}%")
