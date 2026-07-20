"""
预警中心页面 — 逾期运单 / 低库存 / 效期预警
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import date

from db.init_db import init_db
from business import transport as tpt
from business import inventory as inv_mod

st.set_page_config(page_title="预警中心", page_icon="⚠️", layout="wide")
init_db()

st.markdown("""
<style>
[data-testid="stDataFrame"] > div:first-child {
    overflow: auto !important;
}
</style>
""", unsafe_allow_html=True)

st.title("⚠️ 预警中心")

# ==================== 综合统计 ====================
delay_warnings = tpt.get_delay_warnings()
all_warnings = inv_mod.get_all_warnings()
total_alerts = len(delay_warnings) + len(all_warnings)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("运输逾期", f"{len(delay_warnings)} 票")
with c2:
    st.metric("库存预警", f"{len(all_warnings)} 项")
with c3:
    status = "🟢 正常" if total_alerts == 0 else "🔴 需关注"
    st.metric("综合状态", status)

st.divider()

# ==================== Tab: 运输逾期 / 库存预警 ====================
tab_transport, tab_inventory = st.tabs(["🚢 运输逾期预警", "📦 库存预警"])

with tab_transport:
    st.subheader("逾期未到港运单")

    if delay_warnings:
        df = pd.DataFrame(delay_warnings)
        col_map = {
            "id": "ID", "vessel_name": "船名", "supplier": "供货方",
            "coal_type": "煤种", "discharge_port": "卸货港",
            "quantity": "运输量(万吨)", "calorific_value": "热值（大卡）",
            "calorific_category": "热值分类", "sulfur_content": "硫份(%)",
            "planned_arrival_date": "计划到港日期", "adjusted_arrival_date": "调整到港日期",
            "actual_arrival_date": "实际到港日期", "customs_clearance_date": "通关完成日期",
            "discharge_complete_date": "卸完日期",
            "delay_days": "逾期天数", "status": "状态",
        }
        show_keys = [k for k in col_map if k in df.columns]
        df_d = df[show_keys].copy()
        df_d.columns = [col_map[k] for k in show_keys]
        st.dataframe(df_d, use_container_width=True, hide_index=True, height=400)

        st.divider()
        st.caption("💡 建议：请跟进上述运单，确认实际位置并及时更新调整到港日期。")

        # 快捷跳转
        st.page_link("pages/1_调运.py", label="→ 前往运单管理", icon="📋")
    else:
        st.success("✅ 当前无逾期运单，所有在途运单均在调整到港日期之前。")

with tab_inventory:
    st.subheader("库存预警详情")

    if all_warnings:
        for w in all_warnings:
            icon = "🔴" if w["level"] == "error" else "🟡"
            with st.container(border=True):
                st.markdown(f"{icon} **{w['type']}**")
                st.caption(w["detail"])
    else:
        st.success("✅ 当前无库存预警")

    # 详情展示
    st.divider()
    st.subheader("当前库存详情")

    inv = inv_mod.get_inventory_status()
    detail_cols = st.columns(3)
    with detail_cols[0]:
        st.metric("库存量", f"{inv['quantity']:.2f} 万吨")
    with detail_cols[1]:
        st.metric("安全库存", f"{inv['safety_stock']:.2f} 万吨")
    with detail_cols[2]:
        expiry = inv.get("expiry_date")
        if expiry:
            if isinstance(expiry, str):
                expiry = date.fromisoformat(expiry)
            remaining = (expiry - date.today()).days
            st.metric("效期剩余", f"{remaining} 天" if remaining >= 0 else "已过期")
        else:
            st.metric("效期", "未设置")

    st.page_link("pages/2_库存.py", label="→ 前往库存管理", icon="📦")
