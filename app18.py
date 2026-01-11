import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from shapely.geometry import shape
from pyproj import Geod
from geopy.geocoders import Nominatim
import plotly.graph_objects as go
from io import BytesIO

# ==========================================
# 1. 核心配置
# ==========================================
st.set_page_config(page_title="工商业分布式光伏评估系统 v13", layout="wide")

if 'confirmed_area' not in st.session_state: st.session_state.confirmed_area = 0.0
if 'active_scheme' not in st.session_state: st.session_state.active_scheme = "A"

TECH_ATTR = {
    "A": {"name": "TOPCON", "density": 225, "deg_1": 0.01, "deg_lin": 0.004, "price": 0.80},
    "B": {"name": "BC", "density": 240, "deg_1": 0.01, "deg_lin": 0.0035, "price": 0.92}
}
STRUCTURE_DB = {"彩钢瓦": 0.15, "水泥屋顶": 0.25, "钢结构棚": 0.45}
INV_DB = {"50kW": 0.16, "110kW": 0.13, "150kW": 0.12, "250kW": 0.11, "300kW": 0.10, "320kW": 0.09}
VOLTAGE_DB = {"400V": 0.05, "10kV": 0.25, "35kV": 0.45}
GUANGDONG_GRID_PRICE = 0.453  # 广东标杆价

def calculate_area(geojson):
    geod = Geod(ellps="WGS84")
    poly = shape(geojson)
    return abs(geod.geometry_area_perimeter(poly)[0])

@st.cache_data
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="solar_v13")
        loc = geolocator.geocode(address)
        return [loc.latitude, loc.longitude] if loc else [23.13, 113.26]
    except: return [23.13, 113.26]

# ==========================================
# 2. 左侧输入面板
# ==========================================
with st.sidebar:
    st.header("⚙️ 财务与技术核心参数")
    
    with st.expander("📍 1. 项目定位与效率", expanded=True):
        addr = st.text_input("项目详细地址", "广东省广州市黄埔区")
        map_center = get_coords(addr)
        full_hours = st.number_input("年利用小时数 (h)", 500, 2500, 1100)
    
    with st.expander("🏗️ 2. 软成本与管理费", expanded=True):
        fee_dev = st.number_input("开发费用 (元/W)", 0.0, 1.0, 0.10, step=0.01)
        fee_manage = st.number_input("管理费/咨询费 (元/W)", 0.0, 0.5, 0.12, step=0.01)
        elec_part = 0.12 
        install_fee = 0.35 
        
    with st.expander("💰 3. 商务联动与风险", expanded=True):
        elec_p = st.number_input("综合电价 (元/kWh)", 0.0, 2.0, 0.55, step=0.01)
        self_use = st.slider("自用比例 (%)", 0, 100, 70) / 100
        collection_rate = st.slider("电费收缴率 (%)", 80, 100, 98) / 100
        
        loan_ratio = st.slider("融资比例 (%)", 0, 90, 70) / 100
        loan_rate = st.number_input("贷款利率 (%)", 1.0, 8.0, 3.2) / 100
        loan_term = st.number_input("贷款年限", 1, 20, 10)

    with st.expander("⚖️ 4. 压力测试基准", expanded=True):
        target_project_irr = st.number_input("目标 Project IRR (%)", 0.0, 20.0, 6.50, step=0.01, format="%.2f")

# ==========================================
# 3. 深度财务核算引擎
# ==========================================
def run_finance_engine_v13(cap, bom_total, inv_unit_price, tech_key):
    tech = TECH_ATTR[tech_key]
    total_inv = cap * 1000 * bom_total
    input_vat = total_inv / 1.13 * 0.13 
    equity = total_inv * (1 - loan_ratio)
    loan_amt = total_inv * loan_ratio
    pmt = npf.pmt(loan_rate, loan_term, -loan_amt) if loan_amt > 0 else 0
    
    proforma = []
    rem_loan = loan_amt
    accum_vat = input_vat 
    
    for y in range(1, 26):
        deg = (1-tech['deg_1']) if y==1 else (1-tech['deg_1']-(y-1)*tech['deg_lin'])
        gen = cap * full_hours * deg
        
        gross_rev = gen * (elec_p * self_use + GUANGDONG_GRID_PRICE * (1 - self_use))
        actual_rev = gross_rev * collection_rate 
        
        output_vat = actual_rev / 1.13 * 0.13
        payable_vat = max(0, output_vat - accum_vat)
        accum_vat = max(0, accum_vat - output_vat)
        surcharge = payable_vat * 0.12 
        
        opex = cap * 1000 * 0.05 * (1.02**(y-1)) 
        inv_replace = (cap * 1000 * inv_unit_price) if y == 10 else 0 
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
    p_irr = npf.irr([-total_inv] + df["CFADS"].tolist()) * 100
    e_irr = npf.irr([-equity] + df["净现金流"].tolist()) * 100
    return {"p_irr": p_irr, "e_irr": e_irr, "min_dscr": df["DSCR"].min(), "data": df, "total_inv": total_inv}

# ==========================================
# 4. 界面渲染
# ==========================================
st.title("☀️ 工商业分布式光伏系统评估系统 v13")

# --- 需求1：测绘明细强化 ---
st.header("一、卫星测绘与面积确定")
c_m, c_a = st.columns([3, 1])
with c_m:
    m = folium.Map(location=map_center, zoom_start=18)
    folium.TileLayer(tiles='http://webst02.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}', attr='高德', overlay=True).add_to(m)
    Draw().add_to(m)
    map_res = st_folium(m, height=450, use_container_width=True)
with c_a:
    st.subheader("📐 测绘面积明细")
    drawing_data = []
    if map_res and map_res['all_drawings']:
        for i, d in enumerate(map_res['all_drawings']):
            a_val = calculate_area(d['geometry'])
            drawing_data.append({"区域": f"区域 {i+1}", "面积 (m²)": round(a_val, 2)})
        
        # 实时显示明细表
        df_areas = pd.DataFrame(drawing_data)
        st.dataframe(df_areas, hide_index=True, use_container_width=True)
        
        total_m2 = sum([d["面积 (m²)"] for d in drawing_data])
    else:
        st.info("请在地图上点击工具栏进行框选")
        total_m2 = 0.0

    st.divider()
    st.metric("实时测绘合计", f"{total_m2:,.2f} m²")
    final_a = st.number_input("确认计算面积 (m²)", value=total_m2)
    if st.button("📌 锁定并同步面积", use_container_width=True): 
        st.session_state.confirmed_area = final_a
        st.success("数据已透传至下方方案对比")

st.divider()

# --- 方案对比区 ---
st.header("二、技术选型与造价配置")
col_a, col_b = st.columns(2)
schemes = {}

def render_scheme_v13(sid, container):
    with container:
        t_info = TECH_ATTR[sid]
        st.subheader(f"方案 {sid}: {t_info['name']}")
        st.info(f"📍 目标区域最终安装面积: **{st.session_state.confirmed_area:,.2f}** m²")
        
        with st.container(border=True):
            r1, r2 = st.columns(2)
            with r1:
                mp = st.number_input(f"组件单价 (元/W)", value=t_info['price'], key=f"mp{sid}")
                st_type = st.selectbox(f"支架方案", list(STRUCTURE_DB.keys()), key=f"st{sid}")
                sp = st.number_input(f"支架单价", value=STRUCTURE_DB[st_type], key=f"sp{sid}")
            with r2:
                inv_spec = st.selectbox(f"逆变器规格", list(INV_DB.keys()), index=2, key=f"is{sid}")
                ip = st.number_input(f"逆变器单价", value=INV_DB[inv_spec], key=f"ip{sid}")
                vol_type = st.selectbox(f"电压等级", list(VOLTAGE_DB.keys()), key=f"vt{sid}")
                grid_fee = st.number_input(f"并网单价", value=VOLTAGE_DB[vol_type], key=f"gf{sid}")
        
        bom = mp + ip + sp + grid_fee + elec_part + install_fee + fee_dev + fee_manage
        cap = (st.session_state.confirmed_area * t_info['density']) / 1000
        res = run_finance_engine_v13(cap, bom, ip, sid)
        
        st.markdown(f"**装机容量: {cap:,.1f} kW | 系统造价: {bom:.2f} 元/W**")
        st.markdown(f"**Project IRR: {res['p_irr']:.2f}% | 最低 DSCR: {res['min_dscr']:.2f}**")
        
        if st.button(f"✅ 选用方案 {sid}", use_container_width=True): st.session_state.active_scheme = sid
        return {**res, "cap": cap, "bom": bom, "sid": sid, "mp": mp, "ip": ip, "sp": sp, "st": st_type, "inv": inv_spec, "vt": vol_type, "gf": grid_fee}

schemes["A"] = render_scheme_v13("A", col_a)
schemes["B"] = render_scheme_v13("B", col_b)

# --- 深度展示区 ---
st.divider()
active = schemes[st.session_state.active_scheme]
st.header(f"三、{active['sid']} 方案深度财务测算 (广东版)")



fig = go.Figure()
fig.add_trace(go.Bar(x=active['data']["年份"], y=active['data']["净现金流"], name="股东净现金流", marker_color='#0F172A'))
fig.add_trace(go.Scatter(x=active['data']["年份"], y=active['data']["DSCR"], name="DSCR 趋势", yaxis="y2", line=dict(color='#F43F5E', width=3)))
fig.update_layout(
    xaxis=dict(tickmode='linear', tick0=1, dtick=1, title="运营年份"),
    yaxis=dict(title="金额 (元)"),
    yaxis2=dict(title="DSCR Ratio", overlaying='y', side='right', range=[0, 4]),
    legend=dict(orientation="h", y=1.1),
    hovermode="x unified", height=500
)
st.plotly_chart(fig, use_container_width=True)

# 压力测试
st.subheader("⚖️ 基于目标 Project IRR 的报价压力测试")
ratio = active['p_irr'] / target_project_irr if target_project_irr > 0 else 1
p_ceiling = active['bom'] * ratio
soft_ceiling = p_ceiling - (active['bom'] - fee_dev)

k1, k2, k3 = st.columns(3)
k1.metric("设定目标 Project IRR", f"{target_project_irr:.2f}%")
k2.metric("最高 EPC 造价极限", f"{p_ceiling:.2f} 元/W", f"{p_ceiling-active['bom']:.2f}")
k3.metric("最高开发费极限", f"{soft_ceiling:.2f} 元/W", f"{soft_ceiling-fee_dev:.2f}")

st.info("财务合规性：已计入广东 0.453 标杆价、第10年大修成本、全额增值税抵扣流及电费收缴风险计提。")