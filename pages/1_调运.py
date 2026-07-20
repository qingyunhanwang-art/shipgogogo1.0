"""
调运入口页 — 选择管理或计划模块 / 数据导入
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from db.init_db import init_db
from db import data_service as ds
from business import transport as tpt
from config import SHIPMENT_STATUS_OPTIONS
from utils.excel_io import parse_excel

st.set_page_config(page_title="调运管理", page_icon="🚚", layout="wide")

init_db()

# ==================== 页面标题 ====================
st.title("🚚 调运管理")

st.divider()

# --- 延迟 toast（跨 st.rerun 弹窗提示）---
if st.session_state.get("_show_success_toast"):
    st.toast("数据导入已成功", icon="✅")
    st.balloons()
    st.session_state["_show_success_toast"] = False

# ==================== 概览统计 ====================
status_counts = tpt.get_all_status_counts()
planned = status_counts.get("计划", 0)
ordered = status_counts.get("已下单", 0)
total = planned + ordered

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("全部运单", f"{total} 条")
with col2:
    st.metric("计划运单", f"{planned} 条")
with col3:
    st.metric("已下单运单", f"{ordered} 条")

st.divider()

# ==================== 两个大按钮入口 ====================
st.subheader("请选择要进入的模块")

btn_col1, btn_col2 = st.columns(2)

with btn_col1:
    with st.container(border=True):
        st.markdown("### 📊 管理模块")
        st.caption("已下单运单的查看、编辑与管理")
        st.caption(f"当前共 **{ordered}** 条已下单运单")
        st.markdown("")
        if st.button("进入管理模块", type="primary", use_container_width=True, key="goto_manage"):
            st.switch_page("pages/1_调运_管理.py")

with btn_col2:
    with st.container(border=True):
        st.markdown("### 📋 计划模块")
        st.caption("计划运单的查看、编辑与管理")
        st.caption(f"当前共 **{planned}** 条计划运单")
        st.markdown("")
        if st.button("进入计划模块", type="primary", use_container_width=True, key="goto_plan"):
            st.switch_page("pages/1_调运_计划.py")

st.divider()

# ==================== 数据导入 ====================
with st.expander("📥 Excel 批量导入（根据「状态」字段自动匹配模块）", expanded=False):
    st.info(
        "上传的 Excel 必须包含以下必填列：\n\n"
        "**船名\*、数量（万吨）\*、热值（大卡）\*、计划到港日期\*、状态\***\n\n"
        "状态列填写 **已下单** 或 **计划**，系统会自动分流到对应模块。"
    )

    # --- 初始化 session_state ---
    imp_key = "landing_import"
    if f"{imp_key}_new" not in st.session_state:
        st.session_state[f"{imp_key}_new"] = None
        st.session_state[f"{imp_key}_existing"] = None
        st.session_state[f"{imp_key}_parsed"] = None
        st.session_state[f"{imp_key}_filename"] = None

    # --- 重复检测警告 ---
    if st.session_state[f"{imp_key}_new"]:
        dup_new = st.session_state[f"{imp_key}_new"]
        dup_existing = st.session_state[f"{imp_key}_existing"]
        st.error(f"⚠️ 检测到 {len(dup_new)} 条数据可能已导入，请比对后再确定是否导入")

        comp_a, comp_b = st.columns(2)
        with comp_a:
            st.markdown("### 📥 待导入的重复数据")
            to_import = []
            for idx, row in dup_new:
                to_import.append({
                    "序号": idx + 1,
                    "船名": row.get("vessel_name", ""),
                    "计划到港": row.get("planned_arrival_date", ""),
                    "数量（万吨）": row.get("quantity", 0),
                    "热值": row.get("calorific_value", 0),
                    "状态": row.get("status", ""),
                })
            st.dataframe(pd.DataFrame(to_import), use_container_width=True, hide_index=True, height=250)
        with comp_b:
            st.markdown("### 🗄️ 系统中已有数据")
            ex_show = []
            for ex in dup_existing:
                ex_show.append({
                    "ID": ex.get("id"),
                    "船名": ex.get("vessel_name", ""),
                    "计划到港": ex.get("planned_arrival_date", ""),
                    "数量（万吨）": ex.get("quantity", 0),
                    "热值": ex.get("calorific_value", 0),
                    "状态": ex.get("status", ""),
                })
            st.dataframe(pd.DataFrame(ex_show), use_container_width=True, hide_index=True, height=250)

        st.divider()
        btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
        with btn_c1:
            if st.button("📥 确认导入（仍要导入）", type="primary", use_container_width=True, key="force_imp_landing"):
                ds.bulk_import_shipments(st.session_state[f"{imp_key}_parsed"])
                parsed = st.session_state[f"{imp_key}_parsed"]
                g_ordered = sum(1 for r in parsed if r.get("status") == "已下单")
                g_planned = sum(1 for r in parsed if r.get("status") == "计划")
                st.success(
                    f"成功导入 {len(parsed)} 条运单！"
                    f"（管理-已下单: {g_ordered} 条，计划-计划: {g_planned} 条）"
                )
                st.session_state["_show_success_toast"] = True
                st.session_state["upload_landing"] = None
                st.session_state[f"{imp_key}_new"] = None
                st.session_state[f"{imp_key}_existing"] = None
                st.session_state[f"{imp_key}_parsed"] = None
                st.rerun()
        with btn_c2:
            if st.button("❌ 取消", use_container_width=True, key="cancel_imp_landing"):
                for k in [f"{imp_key}_new", f"{imp_key}_existing", f"{imp_key}_parsed"]:
                    st.session_state[k] = None
                st.rerun()
        with btn_c3:
            st.button("📋 报告管理员", disabled=True, use_container_width=True,
                      key="report_imp_landing", help="此功能待开发")

    uploaded_file = st.file_uploader(
        "选择 Excel 文件",
        type=["xlsx", "xls"],
        key="upload_landing",
    )

    if uploaded_file:
        # 新文件上传时清除旧状态
        if st.session_state[f"{imp_key}_filename"] != uploaded_file.name:
            for k in [f"{imp_key}_new", f"{imp_key}_existing", f"{imp_key}_parsed"]:
                st.session_state[k] = None
            st.session_state[f"{imp_key}_filename"] = uploaded_file.name
            st.rerun()

        try:
            parsed_rows = parse_excel(uploaded_file)

            # ============ 状态校验与统计 ============
            status_errors = []
            managed_count = 0
            planned_count = 0
            for i, row in enumerate(parsed_rows):
                s = row.get("status", "")
                if s == "已下单" or s == "管理":
                    row["status"] = "已下单"
                    managed_count += 1
                elif s == "计划":
                    row["status"] = "计划"
                    planned_count += 1
                elif not s or s == "待装货":
                    status_errors.append((i + 2, "状态列为空，请填写「已下单」或「计划」"))
                elif s not in SHIPMENT_STATUS_OPTIONS:
                    status_errors.append(
                        (i + 2, f"状态值「{s}」无效，请填写「已下单」或「计划」")
                    )

            # ============ 必填字段校验 ============
            invalid_rows = []
            required_fields_map = {
                "vessel_name": "船名",
                "quantity": "数量（万吨）",
                "calorific_value": "热值（大卡）",
                "planned_arrival_date": "计划到港日期",
            }
            for i, row in enumerate(parsed_rows):
                missing = []
                for field, label in required_fields_map.items():
                    val = row.get(field)
                    if val is None or val == "" or val == 0 or val == 0.0:
                        missing.append(label)
                if missing:
                    invalid_rows.append((i + 2, missing))

            # ============ 显示解析结果 ============
            all_errors = status_errors + [
                (r, f"第 {r} 行缺少: {', '.join(f)}") for r, f in invalid_rows
            ]

            if all_errors:
                st.error(f"解析成功，但存在 {len(all_errors)} 个问题：")
                for row_num, msg in all_errors:
                    st.caption(f"- 第 {row_num} 行: {msg}")
            else:
                st.success(
                    f"✅ 解析成功，共识别 {len(parsed_rows)} 条运单记录。"
                    f"自动分流：已下单 → 管理模块 **{managed_count}** 条，"
                    f"计划 → 计划模块 **{planned_count}** 条"
                )

            if parsed_rows:
                st.dataframe(pd.DataFrame(parsed_rows), use_container_width=True, hide_index=True, height=350)

                if not all_errors:
                    if st.button("📥 确认导入全部", type="primary", use_container_width=True, key="confirm_imp_landing"):
                        # 1. 日期逻辑校验
                        import_errs = tpt.validate_import_rows(parsed_rows)
                        if import_errs:
                            st.error("日期逻辑校验不通过：")
                            for idx, msg in import_errs:
                                st.caption(f"- {msg}")
                        else:
                            # 2. 重复检测
                            dup_new, dup_existing = tpt.check_import_duplicates(parsed_rows)
                            if dup_new:
                                st.session_state[f"{imp_key}_new"] = dup_new
                                st.session_state[f"{imp_key}_existing"] = dup_existing
                                st.session_state[f"{imp_key}_parsed"] = parsed_rows
                                st.rerun()
                            else:
                                ds.bulk_import_shipments(parsed_rows)
                                st.success(
                                    f"成功导入 {len(parsed_rows)} 条运单！"
                                    f"（管理-已下单: {managed_count} 条，计划-计划: {planned_count} 条）"
                                )
                                st.session_state["_show_success_toast"] = True
                                st.session_state["upload_landing"] = None
                                st.rerun()

        except Exception as e:
            st.error(f"解析失败: {e}")
