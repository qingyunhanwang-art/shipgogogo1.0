"""
煤船快跑——火电厂燃料调运、管理智能体 — 导航入口
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from db.init_db import init_db
from business import transport as tpt
from business import inventory as inv

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="煤船快跑——火电厂燃料调运、管理智能体",
    page_icon="⛴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_db()


def home_page():
    """首页内容"""
    # ==================== 标题 ====================
    st.title("⛴ 煤船快跑——火电厂燃料调运、管理智能体")

    # ==================== 概览指标卡 ====================
    col1, col2, col3, col4 = st.columns(4)

    inv_status = inv.get_inventory_status()
    total_qty = inv_status.get("quantity", 0)
    safety_qty = inv_status.get("safety_stock", 0)

    cal_breakdown = inv.get_inventory_by_calorific()
    arrived_total = cal_breakdown.get("总量", 0)

    total_shipments = sum(tpt.get_all_status_counts().values())

    with col1:
        st.metric("当前库存", f"{total_qty:.2f} 万吨")
    with col2:
        st.metric("安全库存", f"{safety_qty:.2f} 万吨")
    with col3:
        st.metric("总运单", f"{total_shipments} 条")
    with col4:
        st.metric("有效库存(已下单)", f"{arrived_total:.2f} 万吨")

    st.divider()

    # ==================== 预警速览 ====================
    all_warnings = inv.get_all_warnings()
    delay_warnings = tpt.get_delay_warnings()
    total_alert_count = len(all_warnings) + len(delay_warnings)

    if total_alert_count > 0:
        alert_texts = []
        for w in all_warnings:
            icon = "🔴" if w["level"] == "error" else "🟡"
            alert_texts.append(f"{icon} **{w['type']}**: {w['detail']}")
        if delay_warnings:
            alert_texts.append(f"🟡 **运输逾期**: {len(delay_warnings)} 票运单已超调整到港日期")

        for t in alert_texts:
            st.warning(t)
    else:
        st.success("✅ 当前无预警，一切正常")

    st.divider()

    # ==================== 快捷入口卡片 ====================
    st.subheader("快捷功能")

    card_col1, card_col2, card_col3, card_col4 = st.columns(4)

    with card_col1:
        with st.container(border=True):
            st.markdown("### 📋 调运管理")
            st.caption("查看、新增、编辑运单台账")
            st.caption(f"总运单: **{total_shipments}** 条")
            st.page_link("pages/1_调运.py", label="🚚 进入调运管理")

    with card_col2:
        with st.container(border=True):
            st.markdown("### 📦 库存管理")
            st.caption("入库、出库、库存监控")
            st.caption(f"当前库存: **{total_qty:.2f}** 万吨")
            st.caption(f"安全库存: **{safety_qty:.2f}** 万吨")
            # 热值分类概览
            for cat in ["高卡", "中卡", "低卡"]:
                q = cal_breakdown.get(cat, 0)
                if q > 0:
                    st.caption(f"{cat}煤: **{q:.2f}** 万吨")

    with card_col3:
        with st.container(border=True):
            st.markdown("### ⚠️ 预警中心")
            st.caption("逾期、低库存、效期预警")
            st.caption(f"待处理预警: **{total_alert_count}** 条")

    with card_col4:
        with st.container(border=True):
            st.markdown("### 💬 AI 问答")
            st.caption("自然语言查询库存和运输")


# ==================== 导航配置（隐藏原生侧边栏，仅用做路由） ====================
page_home = st.Page(home_page, title="主页", icon="⛴")
page_transport = st.Page("pages/1_调运.py", title="调运", icon="🚚")
page_manage = st.Page("pages/1_调运_管理.py", title="管理", icon="📊")
page_plan = st.Page("pages/1_调运_计划.py", title="计划", icon="📋")
page_inventory = st.Page("pages/2_库存.py", title="库存", icon="📦")
page_alert = st.Page("pages/3_预警.py", title="预警", icon="⚠️")
page_qa = st.Page("pages/4_问答.py", title="问答", icon="💬")

pages = [page_home, page_transport, page_manage, page_plan,
         page_inventory, page_alert, page_qa]

pg = st.navigation(pages, position="hidden")

# ==================== 自定义侧边栏导航 ====================
with st.sidebar:
    st.markdown("### 🧭 导航")

    # 主页 — 平铺，无下拉
    st.page_link(page_home, label="主页")

    # 调运 — 折叠二级菜单
    with st.expander("🚚 调运", expanded=False):
        st.page_link(page_transport, label="总览")
        st.page_link(page_manage, label="管理")
        st.page_link(page_plan, label="计划")

    # 库存 — 平铺，无下拉
    st.page_link(page_inventory, label="库存")

    # 预警 — 平铺，无下拉
    st.page_link(page_alert, label="预警")

    # 问答 — 平铺，无下拉
    st.page_link(page_qa, label="问答")

pg.run()
