"""
库存管理页面 — 与调运单一对一
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import date

from db.init_db import init_db
from db import data_service as ds
from business import inventory as inv_mod
from business import transport as tpt

st.set_page_config(page_title="库存管理", page_icon="📦", layout="wide")
init_db()

st.markdown("""
<style>
[data-testid="stDataFrame"] > div:first-child {
    overflow: auto !important;
}
</style>
""", unsafe_allow_html=True)

st.title("📦 库存管理")

# ==================== 库存概览卡片 ====================
all_inv = inv_mod.get_all_inventory()
total_qty = sum((row.get("inventory_quantity") or 0) for row in all_inv)
total_count = len(all_inv)
with_safety = sum(1 for r in all_inv if (r.get("safety_stock") or 0) > 0)
with_exp = sum(1 for r in all_inv if r.get("inventory_expiry_date"))

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("库存总吨数", f"{total_qty:.2f} 万吨")
with col2:
    st.metric("库存运单数", f"{total_count} 条")
with col3:
    st.metric("已设安全库存", f"{with_safety} 条")
with col4:
    st.metric("已设效期", f"{with_exp} 条")

# ==================== 同步按钮 + 清除空白 ====================
st.markdown("---")
sc1, sc2, sc3 = st.columns([3, 1, 1])
with sc1:
    st.caption("库存与调运单一对一。入库标准：实际到港日期或卸完日期 ≤ 今日。")
with sc2:
    if st.button("🔄 从调运单同步库存", type="primary", use_container_width=True):
        with st.spinner("清空并按到港/卸完日期同步中..."):
            synced, not_synced = inv_mod.sync_from_transport()
        st.success(f"同步完成！已到港/已卸完运单导入 {synced} 条")
        if not_synced > 0:
            st.info(f"另有 {not_synced} 条运单未到港/未卸完，暂不入库。")
        st.rerun()
with sc3:
    empty_count = sum(1 for r in all_inv if (r.get("inventory_quantity") or 0) == 0)
    if st.button(f"🗑️ 清除空白库存 ({empty_count})",
                 use_container_width=True, help="删除库存数量为 0 的空白记录"):
        if empty_count == 0:
            st.info("没有空白库存可清除")
        else:
            deleted = inv_mod.clear_empty()
            st.success(f"已清除 {deleted} 条空白库存！")
            st.rerun()

# ==================== Tabs ====================
tab_detail, tab_edit, tab_inout, tab_settings, tab_history, tab_calorific = st.tabs([
    "📋 库存明细", "✏️ 编辑库存单", "📥📤 出入库", "⚙️ 参数设置", "📜 操作记录", "🔥 热值分类",
])

# ---- 列定义（复用） ----
ALL_COLS = [
    ("id", "运单ID"), ("status", "状态"), ("vessel_name", "船名"),
    ("supplier", "供货方"), ("coal_type", "煤种"), ("discharge_port", "卸货港"),
    ("load_month", "装货月份"), ("quantity", "运单数量(万吨)"),
    ("inventory_quantity", "库存数量(万吨)"), ("safety_stock", "安全库存(万吨)"),
    ("calorific_value", "热值(大卡)"), ("calorific_category", "热值分类"),
    ("sulfur_content", "硫份(%)"),
    ("planned_arrival_date", "计划到港日期"),
    ("adjusted_arrival_date", "调整到港日期"),
    ("actual_arrival_date", "实际到港日期"),
    ("discharge_complete_date", "卸完日期"),
    ("customs_clearance_date", "通关完成日期"),
    ("fob_price", "FOB价格"), ("freight_cost", "海运费"),
    ("standard_unit_price", "标准单价"),
    ("inventory_expiry_date", "效期"),
    ("inventory_remark", "库存备注"),
]


def _prepare_df(data_rows):
    """将库存行列表转为 DataFrame 并补上热值分类"""
    if not data_rows:
        return pd.DataFrame()
    df = pd.DataFrame(data_rows)
    if "calorific_value" in df.columns and "calorific_category" not in df.columns:
        df["calorific_category"] = df["calorific_value"].apply(
            lambda v: tpt.classify_calorific(v)[0] if v and v > 0 else ""
        )
    return df


def _render_df(df, key_prefix):
    """通用渲染：列选择 + 多彩色表格"""
    available_cols = [(c, l) for c, l in ALL_COLS if c in df.columns]
    col_map = {c: l for c, l in available_cols}
    col_keys = [c for c, _ in available_cols]

    default_keys = [
        "id", "status", "vessel_name", "supplier", "coal_type",
        "inventory_quantity", "quantity", "safety_stock",
        "calorific_value", "calorific_category",
        "planned_arrival_date", "actual_arrival_date",
        "discharge_complete_date",
        "inventory_expiry_date",
    ]
    default_keys = [k for k in default_keys if k in col_map]

    cl1, cl2 = st.columns([3, 1])
    with cl1:
        sel_keys = st.multiselect(
            "选择显示的列",
            options=col_keys,
            default=default_keys,
            format_func=lambda c: col_map.get(c, c),
            key=f"{key_prefix}_cols",
        )
    with cl2:
        st.write("")
        st.write("")
        if st.button("📋 全部列", use_container_width=True, key=f"{key_prefix}_all"):
            st.session_state[f"{key_prefix}_cols"] = col_keys
            st.rerun()

    if not sel_keys:
        sel_keys = default_keys

    sel_labels = [col_map[c] for c in sel_keys if c in df.columns]
    df_d = df[[c for c in sel_keys if c in df.columns]].copy()
    df_d.columns = sel_labels

    def _color_cat(val):
        if val == "高卡":
            return "background-color: #d4edda; color: #155724"
        elif val == "中卡":
            return "background-color: #fff3cd; color: #856404"
        elif val == "低卡":
            return "background-color: #f8d7da; color: #721c24"
        return ""

    styled = df_d.style
    if "热值分类" in df_d.columns:
        styled = styled.applymap(_color_cat, subset=["热值分类"])

    st.dataframe(styled, use_container_width=True, hide_index=True, height=450)
    st.caption(f"共 {len(df)} 条")


# ==================== Tab 1: 库存明细 ====================
with tab_detail:
    if all_inv:
        df = _prepare_df(all_inv)
        _render_df(df, "inv_detail")
    else:
        st.info("暂无库存数据，请点击上方「从调运单同步库存」按钮")


# ==================== Tab 2: 编辑库存单 ====================
with tab_edit:
    st.subheader("✏️ 编辑库存单（含库存数量）")

    if all_inv:
        edit_opts = {
            f"#{r.get('id')} | {r.get('vessel_name','?')} | {r.get('coal_type','?')} | "
            f"{r.get('supplier','?')} | 库存 {r.get('inventory_quantity') or 0} 万吨": r.get("id")
            for r in all_inv
        }
        edit_label = st.selectbox(
            "选择要编辑的运单",
            options=list(edit_opts.keys()),
            key="edit_shipment",
        )
        e_sid = edit_opts[edit_label]

        # 获取当前库存信息
        cur = ds.get_inventory_by_shipment(e_sid)
        cur_qty = cur.get("quantity", 0) or 0 if cur else 0
        cur_safety = cur.get("safety_stock", 0) or 0 if cur else 0
        cur_expiry = cur.get("expiry_date") if cur else None
        cur_remark = cur.get("remark", "") if cur else ""

        ec1, ec2 = st.columns(2)
        with ec1:
            new_qty = st.number_input(
                "库存数量（万吨）", min_value=0.0,
                value=float(cur_qty), step=0.1, key="edit_qty"
            )
            new_safety = st.number_input(
                "安全库存（万吨）", min_value=0.0,
                value=float(cur_safety), step=0.1, key="edit_safety"
            )
        with ec2:
            exp_str = str(cur_expiry) if cur_expiry else ""
            new_expiry_str = st.text_input(
                "效期（YYYY-MM-DD）", value=exp_str, key="edit_expiry"
            )
            new_expiry_val = None
            if new_expiry_str:
                try:
                    new_expiry_val = date.fromisoformat(new_expiry_str)
                except ValueError:
                    st.error("日期格式错误，请用 YYYY-MM-DD")

        new_remark = st.text_area("备注", value=cur_remark, key="edit_remark", height=68)

        btn_col1, btn_col2 = st.columns([1, 3])
        with btn_col1:
            if st.button("💾 保存编辑", type="primary", use_container_width=True):
                ds.update_inventory_by_shipment(
                    shipment_id=e_sid,
                    quantity=new_qty,
                    safety_stock=new_safety,
                    expiry_date=new_expiry_val,
                    remark=new_remark,
                )
                st.success(f"运单 #{e_sid} 库存已更新！")
                st.rerun()
    else:
        st.info("暂无库存数据")


# ==================== Tab 2: 出入库 ====================
with tab_inout:
    st.subheader("出入库操作（按运单）")

    # 选择运单
    if all_inv:
        ship_opts = {
            f"#{r.get('id')} | {r.get('vessel_name','?')} | {r.get('coal_type','?')} | "
            f"{r.get('supplier','?')} | 库存 {r.get('inventory_quantity') or 0} 万吨": r.get("id")
            for r in all_inv
        }
        selected_label = st.selectbox(
            "选择要操作的运单",
            options=list(ship_opts.keys()),
            key="io_shipment",
        )
        selected_sid = ship_opts[selected_label]
    else:
        st.warning("请先同步库存")
        st.stop()

    io_col1, io_col2 = st.columns(2)

    with io_col1:
        with st.container(border=True):
            st.markdown("#### 📥 入库")
            in_qty = st.number_input("入库数量（万吨）", min_value=0.01, step=0.1, key="in_qty")
            in_operator = st.text_input("操作人", key="in_op")
            in_remark = st.text_area("备注", key="in_remark", height=68)

            if st.button("✅ 确认入库", type="primary", key="btn_in", use_container_width=True):
                try:
                    inv_mod.stock_in(selected_sid, in_qty, in_operator, in_remark)
                    cur = ds.get_inventory_by_shipment(selected_sid)
                    st.success(f"运单 #{selected_sid} 入库 {in_qty} 万吨成功！当前库存: {cur['quantity']:.2f} 万吨")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with io_col2:
        with st.container(border=True):
            st.markdown("#### 📤 出库")
            out_qty = st.number_input("出库数量（万吨）", min_value=0.01, step=0.1, key="out_qty")
            out_operator = st.text_input("操作人", key="out_op")
            out_remark = st.text_area("备注", key="out_remark", height=68)

            if st.button("✅ 确认出库", type="primary", key="btn_out", use_container_width=True):
                try:
                    inv_mod.stock_out(selected_sid, out_qty, out_operator, out_remark)
                    cur = ds.get_inventory_by_shipment(selected_sid)
                    st.success(f"运单 #{selected_sid} 出库 {out_qty} 万吨成功！剩余库存: {cur['quantity']:.2f} 万吨")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


# ==================== Tab 3: 参数设置 ====================
with tab_settings:
    st.subheader("库存参数设置（按运单）")

    if all_inv:
        set_opts = {
            f"#{r.get('id')} | {r.get('vessel_name','?')} | {r.get('coal_type','?')}": r.get("id")
            for r in all_inv
        }
        set_label = st.selectbox(
            "选择运单",
            options=list(set_opts.keys()),
            key="set_shipment",
        )
        set_sid = set_opts[set_label]

        cur_inv = ds.get_inventory_by_shipment(set_sid)
        cur_safety = cur_inv.get("safety_stock", 0) or 0 if cur_inv else 0
        cur_expiry = cur_inv.get("expiry_date") if cur_inv else None
        cur_remark = cur_inv.get("remark", "") if cur_inv else ""

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            new_safety = st.number_input(
                "安全库存（万吨）", min_value=0.0,
                value=float(cur_safety), step=0.1, key="set_safety"
            )
        with sc2:
            exp_str = str(cur_expiry) if cur_expiry else ""
            new_expiry_str = st.text_input(
                "效期（如 2026-12-31）",
                value=exp_str, key="set_expiry"
            )
            new_expiry_val = None
            if new_expiry_str:
                try:
                    new_expiry_val = date.fromisoformat(new_expiry_str)
                except ValueError:
                    st.error("日期格式错误，请用 YYYY-MM-DD")
        with sc3:
            new_remark = st.text_area("备注", value=cur_remark, key="set_remark")

        if st.button("💾 保存参数", type="primary", use_container_width=True):
            ds.update_inventory_by_shipment(
                shipment_id=set_sid,
                safety_stock=new_safety,
                expiry_date=new_expiry_val,
                remark=new_remark,
            )
            st.success(f"运单 #{set_sid} 参数已保存")
            st.rerun()
    else:
        st.info("暂无库存数据")


# ==================== Tab 4: 操作记录 ====================
with tab_history:
    st.subheader("出入库记录")
    txns = inv_mod.get_recent_txns(limit=100)
    if txns:
        df_txn = pd.DataFrame(txns)
        if "type" in df_txn.columns:
            df_txn["操作类型"] = df_txn["type"].map({"入": "📥 入库", "出": "📤 出库"})
        if "qty" in df_txn.columns:
            df_txn["数量（万吨）"] = df_txn["qty"]
        if "shipment_id" in df_txn.columns:
            df_txn["运单ID"] = df_txn["shipment_id"]
        if "operator" in df_txn.columns:
            df_txn["操作人"] = df_txn["operator"]
        if "time" in df_txn.columns:
            df_txn["时间"] = df_txn["time"]
        if "remark" in df_txn.columns:
            df_txn["备注"] = df_txn["remark"]

        show_cols = ["时间", "运单ID", "操作类型", "数量（万吨）", "操作人", "备注"]
        available = [c for c in show_cols if c in df_txn.columns]
        st.dataframe(df_txn[available], use_container_width=True, hide_index=True, height=450)
    else:
        st.info("暂无出入库记录")


# ==================== Tab 5: 热值分类 ====================
with tab_calorific:
    st.subheader("🔥 有效库存按热值分类")
    st.caption("统计已到港 + 已通关的运单，按热值标准自动分类")

    cal_data = inv_mod.get_inventory_by_calorific()

    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        st.metric("高卡煤 (>5000)", f"{cal_data.get('高卡', 0):.2f} 万吨")
    with cc2:
        st.metric("中卡煤 (4000-5000)", f"{cal_data.get('中卡', 0):.2f} 万吨")
    with cc3:
        st.metric("低卡煤 (≤4000)", f"{cal_data.get('低卡', 0):.2f} 万吨")
    with cc4:
        st.metric("有效库存总量", f"{cal_data.get('总量', 0):.2f} 万吨")

    with st.expander("📐 热值分类标准", expanded=False):
        st.markdown("""
        | 分类 | 热值范围 | 说明 |
        |------|----------|------|
        | 高卡煤 | > 5000 大卡 | 优质煤 |
        | 中卡煤 | 4000 ~ 5000 大卡 | 中等煤 |
        | 低卡煤 | ≤ 4000 大卡 | 低质煤 |
        """)
