"""
运单管理页面 — 管理/计划双模块（公共渲染模块）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import date as dt_date

from db.init_db import init_db
from db import data_service as ds
from business import transport as tpt
from config import SHIPMENT_STATUS_OPTIONS


def render_transport_page(current_status: str):
    """
    渲染调运管理页面。

    Parameters
    ----------
    current_status : str
        当前模块对应的状态，"已下单"（管理）或 "计划"（计划）。
    """
    if current_status not in ("已下单", "计划"):
        raise ValueError("current_status 必须是 '已下单' 或 '计划'")

    init_db()

    # 注入全局 CSS：强制数据表支持横向滚动
    st.markdown("""
    <style>
    [data-testid="stDataFrame"] > div:first-child {
        overflow: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 标题带模块后缀
    module_label = "管理" if current_status == "已下单" else "计划"
    st.title(f"📋 调运管理 -- {module_label}")

    # --- 延迟 toast（跨 st.rerun 弹窗提示）---
    if st.session_state.get("_show_success_toast"):
        st.toast("数据导入已成功", icon="✅")
        st.balloons()
        st.session_state["_show_success_toast"] = False

    st.divider()

    # ==================== 数据统计总览 ====================
    stats = tpt.get_stats_by_status(current_status)
    if stats["total_count"] > 0:
        with st.expander("📊 数据统计总览", expanded=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("运单总数", f"{stats['total_count']} 条")
            with c2:
                st.metric("总吨数", f"{stats['total_qty']:.2f} 万吨")
            with c3:
                st.metric("平均热值", f"{stats['avg_calorific']:.0f} 大卡")
            with c4:
                st.metric("供货方", f"{stats['supplier_count']} 家")
            with c5:
                st.metric("🔥 高卡", f"{stats['high_qty']:.2f} 万吨")
            c6, c7, _ = st.columns([1, 1, 3])
            with c6:
                st.metric("🟠 中卡", f"{stats['medium_qty']:.2f} 万吨")
            with c7:
                st.metric("🔵 低卡", f"{stats['low_qty']:.2f} 万吨")
            if stats["suppliers"]:
                st.caption(f"供货方: {', '.join(stats['suppliers'])}")

    # ==================== Tab: 列表 / 新增 / 导入 ====================
    tab_list, tab_add, tab_import = st.tabs(["📋 运单列表", "➕ 新增运单", "📥 批量导入"])

    # ============ TAB 1: 运单列表 ============
    with tab_list:
        # --- 搜索栏 ---
        filter_col1, filter_col2 = st.columns([3, 1])
        with filter_col1:
            keyword = st.text_input(
                "关键词搜索（供货方/船名/卸货港/煤种）",
                key=f"list_keyword_{current_status}",
            )
        with filter_col2:
            st.write("")
            st.write("")
            search_clicked = st.button("🔍 搜索", use_container_width=True, key=f"search_{current_status}")

        # --- 分页参数 ---
        page_key = f"ship_page_{current_status}"
        if page_key not in st.session_state:
            st.session_state[page_key] = 1
        page = st.session_state[page_key]
        page_size = 15

        # --- 查询：按当前模块 status 筛选 ---
        rows, total = tpt.search_shipments(
            status=current_status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )

        total_pages = max(1, (total + page_size - 1) // page_size)

        # --- 数据显示 ---
        if rows:
            df = pd.DataFrame(rows)
            # 添加热值分类计算列
            if "calorific_value" in df.columns and "calorific_category" not in df.columns:
                df["calorific_category"] = df["calorific_value"].apply(
                    lambda v: tpt.classify_calorific(v)[0] if v and v > 0 else ""
                )

            # ===== 全部字段定义 =====
            ALL_COLUMNS = [
                ("id", "ID"),
                ("status", "状态"),
                ("vessel_name", "船名"),
                ("supplier", "供货方"),
                ("coal_type", "煤种"),
                ("discharge_port", "卸货港"),
                ("load_month", "装货月份"),
                ("quantity", "数量（万吨）"),
                ("calorific_value", "热值（大卡）"),
                ("calorific_category", "热值分类"),
                ("sulfur_content", "硫份(%)"),
                ("arrive_load_port_date", "到装港日期"),
                ("load_start_date", "装货日期"),
                ("load_end_date", "完货日期"),
                ("planned_arrival_date", "计划到港日期"),
                ("adjusted_arrival_date", "调整到港日期"),
                ("actual_arrival_date", "实际到港日期"),
                ("customs_clearance_date", "通关完成日期"),
                ("discharge_complete_date", "卸完日期"),
                ("fob_price", "FOB价格"),
                ("freight_cost", "海运费"),
                ("standard_unit_price", "标准单价"),
            ]
            # 只保留 df 中存在的列
            available_all = [(c, l) for c, l in ALL_COLUMNS if c in df.columns]
            all_key_map = {c: l for c, l in available_all}
            all_keys = [c for c, _ in available_all]

            # ===== 列选择器 =====
            default_keys = [
                "id", "status", "vessel_name", "supplier", "coal_type", "discharge_port",
                "quantity", "calorific_value", "calorific_category", "sulfur_content",
                "planned_arrival_date", "adjusted_arrival_date",
                "actual_arrival_date", "customs_clearance_date", "discharge_complete_date",
            ]
            default_keys = [k for k in default_keys if k in all_key_map]

            col_flt_1, col_flt_2 = st.columns([3, 1])
            with col_flt_1:
                selected_col_keys = st.multiselect(
                    "选择显示的列（可多选/搜索）",
                    options=all_keys,
                    default=default_keys,
                    format_func=lambda c: all_key_map.get(c, c),
                    key=f"col_select_{current_status}",
                )
            with col_flt_2:
                st.write("")
                st.write("")
                if st.button("📋 全部", use_container_width=True, key=f"show_all_{current_status}"):
                    st.session_state[f"col_select_{current_status}"] = all_keys
                    st.rerun()

            if not selected_col_keys:
                selected_col_keys = default_keys

            selected_labels = [all_key_map[c] for c in selected_col_keys if c in df.columns]
            df_display = df[selected_col_keys].copy()
            df_display.columns = selected_labels

            # 高亮热值列
            def color_calorific(val):
                if val == "高卡":
                    return "background-color: #d4edda; color: #155724"
                elif val == "中卡":
                    return "background-color: #fff3cd; color: #856404"
                elif val == "低卡":
                    return "background-color: #f8d7da; color: #721c24"
                return ""

            # 高亮状态列
            def color_status(val):
                if val == "已下单":
                    return "background-color: #cce5ff; color: #004085; font-weight: bold"
                elif val == "计划":
                    return "background-color: #e2e3e5; color: #383d41; font-weight: bold"
                return ""

            styled = df_display.style
            if "热值分类" in df_display.columns:
                styled = styled.applymap(color_calorific, subset=["热值分类"])
            if "状态" in df_display.columns:
                styled = styled.applymap(color_status, subset=["状态"])

            st.dataframe(styled, use_container_width=True, hide_index=True, height=450)

            # --- 分页控件 ---
            st.markdown("")
            pg_col1, pg_col2, pg_col3, pg_col4, pg_col5 = st.columns([1, 1, 2, 1, 1])
            with pg_col1:
                if st.button("◀ 首页", disabled=(page <= 1), key=f"first_{current_status}", use_container_width=True):
                    st.session_state[page_key] = 1
                    st.rerun()
            with pg_col2:
                if st.button("◀ 上一页", disabled=(page <= 1), key=f"prev_{current_status}", use_container_width=True):
                    st.session_state[page_key] = page - 1
                    st.rerun()
            with pg_col3:
                st.markdown(
                    f"<div style='text-align:center;font-size:16px;padding:4px 0;'>"
                    f"共 {total} 条 &nbsp; {page}/{total_pages} 页"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with pg_col4:
                if st.button("下一页 ▶", disabled=(page >= total_pages), key=f"next_{current_status}", use_container_width=True):
                    st.session_state[page_key] = page + 1
                    st.rerun()
            with pg_col5:
                if st.button("末页 ▶", disabled=(page >= total_pages), key=f"last_{current_status}", use_container_width=True):
                    st.session_state[page_key] = total_pages
                    st.rerun()

            # --- 批量管理 ---
            batch_key = f"batch_{current_status}"
            with st.expander("🔧 批量管理（选择多条运单进行操作）", expanded=False):
                if f"batch_selected_{current_status}" not in st.session_state:
                    st.session_state[f"batch_selected_{current_status}"] = set()
                if f"batch_pending_{current_status}" not in st.session_state:
                    st.session_state[f"batch_pending_{current_status}"] = False

                current_ids = [r["id"] for r in rows]
                selected_set = st.session_state[f"batch_selected_{current_status}"]

                ba, bb, bc = st.columns([1, 1, 4])
                with ba:
                    if st.button("☑ 全选当前页", use_container_width=True, key=f"b_all_{current_status}"):
                        selected_set.update(current_ids)
                        st.rerun()
                with bb:
                    if st.button("☐ 取消全选", use_container_width=True, key=f"b_none_{current_status}"):
                        for cid in current_ids:
                            selected_set.discard(cid)
                        st.rerun()
                with bc:
                    st.caption(f"已选中 **{len([x for x in current_ids if x in selected_set])}** / {len(current_ids)} 条（当前页）")

                st.markdown("---")
                cols_per_row = 5
                for i in range(0, len(rows), cols_per_row):
                    chunk = rows[i : i + cols_per_row]
                    chunk_cols = st.columns(cols_per_row)
                    for j, r in enumerate(chunk):
                        rid = r["id"]
                        label = f"#{rid} {r.get('vessel_name','')}"
                        with chunk_cols[j]:
                            ck = st.checkbox(label, value=(rid in selected_set), key=f"b_ck_{current_status}_{rid}")
                            if ck:
                                selected_set.add(rid)
                            else:
                                selected_set.discard(rid)

                st.markdown("---")
                btn1, btn2, btn3 = st.columns([1, 1, 2])
                selected_ids = [x for x in current_ids if x in selected_set]

                with btn1:
                    delete_disabled = len(selected_ids) == 0
                    if st.button(
                        f"🗑 删除选中（{len(selected_ids)}条）",
                        type="secondary",
                        disabled=delete_disabled,
                        use_container_width=True,
                        key=f"b_del_{current_status}",
                    ):
                        st.session_state[f"batch_pending_{current_status}"] = True
                        st.rerun()

                with btn2:
                    # 批量切换状态
                    can_move = len(selected_ids) > 0
                    target_status = "计划" if current_status == "已下单" else "已下单"
                    if st.button(
                        f"🔄 转为「{target_status}」",
                        disabled=not can_move,
                        use_container_width=True,
                        key=f"b_move_{current_status}",
                        help=f"将选中运单的状态改为「{target_status}」",
                    ):
                        for sid in selected_ids:
                            ds.update_shipment_status(sid, target_status)
                        st.success(f"已将 {len(selected_ids)} 条运单转为「{target_status}」")
                        for sid in selected_ids:
                            selected_set.discard(sid)
                        st.rerun()

                with btn3:
                    st.button(
                        "🔒 管理员权限",
                        disabled=True,
                        use_container_width=True,
                        key=f"b_admin_{current_status}",
                        help="管理员权限功能预留，暂未开放",
                    )

                # --- 二次确认 ---
                if st.session_state[f"batch_pending_{current_status}"] and selected_ids:
                    st.error(f"⚠️ 确认删除 **{len(selected_ids)}** 条运单？此操作不可撤销！")
                    del_preview = [r for r in rows if r["id"] in selected_ids]
                    st.dataframe(
                        pd.DataFrame([{
                            "ID": r["id"], "船名": r.get("vessel_name"),
                            "计划到港": r.get("planned_arrival_date"), "数量（万吨）": r.get("quantity"),
                        } for r in del_preview]),
                        use_container_width=True, hide_index=True, height=150,
                    )
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        if st.button("✅ 确认删除", type="primary", use_container_width=True, key=f"b_confirm_{current_status}"):
                            deleted = ds.bulk_delete_shipments(selected_ids)
                            st.success(f"已删除 {deleted} 条运单")
                            for sid in selected_ids:
                                selected_set.discard(sid)
                            st.session_state[f"batch_pending_{current_status}"] = False
                            st.rerun()
                    with c2:
                        if st.button("❌ 取消", use_container_width=True, key=f"b_cancel_{current_status}"):
                            st.session_state[f"batch_pending_{current_status}"] = False
                            st.rerun()

            # --- 查看运单详情 ---
            with st.expander("🔍 查看运单详情（输入ID查看完整信息）", expanded=False):
                view_id_col, view_btn_col, _ = st.columns([1, 1, 2])
                with view_id_col:
                    view_id = st.number_input(
                        "输入运单 ID", min_value=1, step=1,
                        key=f"view_id_{current_status}",
                    )
                with view_btn_col:
                    st.write("")
                    view_btn = st.button(
                        "🔍 查看详情", key=f"view_btn_{current_status}",
                        use_container_width=True,
                    )

                if view_btn:
                    shipment = ds.get_shipment_by_id(view_id)
                    if shipment:
                        cat, _ = tpt.classify_calorific(shipment.get("calorific_value"))
                        shipment["calorific_category"] = cat
                        st.session_state[f"view_shipment_{current_status}"] = shipment
                    else:
                        st.session_state[f"view_shipment_{current_status}"] = None
                        st.error("未找到该运单")

                view_shipment = st.session_state.get(f"view_shipment_{current_status}")
                if view_shipment:
                    s = view_shipment
                    cat = s.get("calorific_category", "")
                    cat_emoji = {"高卡": "🔥", "中卡": "🟠", "低卡": "🔵"}.get(cat, "")
                    st.markdown(f"### {cat_emoji} 运单 #{s['id']} — {s.get('vessel_name', '')}")
                    st.divider()

                    v1, v2, v3 = st.columns(3)
                    fields_c1 = [
                        ("状态", s.get("status")),
                        ("装货月份", s.get("load_month")),
                        ("供货方", s.get("supplier")),
                        ("船名", s.get("vessel_name")),
                        ("到装港日期", s.get("arrive_load_port_date")),
                        ("装货日期", s.get("load_start_date")),
                        ("完货日期", s.get("load_end_date")),
                    ]
                    fields_c2 = [
                        ("计划到港日期", s.get("planned_arrival_date")),
                        ("调整到港日期", s.get("adjusted_arrival_date")),
                        ("实际到港日期", s.get("actual_arrival_date")),
                        ("通关完成日期", s.get("customs_clearance_date")),
                        ("卸完日期", s.get("discharge_complete_date")),
                        ("卸货港", s.get("discharge_port")),
                        ("煤种", s.get("coal_type")),
                    ]
                    fields_c3 = [
                        ("硫份(%)", f"{(s.get('sulfur_content') or 0):.2f}"),
                        ("热值（大卡）", f"{s.get('calorific_value') or 0}"),
                        ("热值分类", f"{cat_emoji} {cat}"),
                        ("数量（万吨）", f"{(s.get('quantity') or 0):.2f}"),
                        ("FOB价格", f"{(s.get('fob_price') or 0):.2f}"),
                        ("海运费", f"{(s.get('freight_cost') or 0):.2f}"),
                        ("标准单价", f"{(s.get('standard_unit_price') or 0):.2f}"),
                    ]
                    with v1:
                        for label, val in fields_c1:
                            st.caption(f"**{label}**")
                            st.write(str(val) if val is not None else "-")
                    with v2:
                        for label, val in fields_c2:
                            st.caption(f"**{label}**")
                            st.write(str(val) if val is not None else "-")
                    with v3:
                        for label, val in fields_c3:
                            st.caption(f"**{label}**")
                            st.write(str(val) if val is not None else "-")

            # --- 编辑运单 ---
            with st.expander("✏️ 编辑运单（输入ID加载）", expanded=False):
                edit_id_col, load_col, _ = st.columns([1, 1, 2])
                with edit_id_col:
                    edit_id = st.number_input("输入运单 ID", min_value=1, step=1, key=f"edit_id_{current_status}")
                with load_col:
                    st.write("")
                    load_btn = st.button("📂 加载运单", key=f"load_edit_{current_status}", use_container_width=True)

                if load_btn:
                    shipment = ds.get_shipment_by_id(edit_id)
                    if shipment:
                        cat, label = tpt.classify_calorific(shipment.get("calorific_value"))
                        shipment["calorific_category"] = cat
                        st.session_state[f"edit_shipment_{current_status}"] = shipment
                        st.session_state[f"edit_id_{current_status}"] = edit_id
                    else:
                        st.session_state[f"edit_shipment_{current_status}"] = None
                        st.error("未找到该运单")

                edit_shipment = st.session_state.get(f"edit_shipment_{current_status}")
                if edit_shipment:
                    s = edit_shipment
                    cat_emoji = {"高卡": "🔥", "中卡": "🟠", "低卡": "🔵"}.get(s.get("calorific_category", ""), "")
                    st.markdown(f"### {cat_emoji} 编辑运单 #{s['id']} — {s.get('vessel_name', '')}")

                    e1, e2, e3 = st.columns(3)
                    with e1:
                        e_status = st.selectbox(
                            "状态", SHIPMENT_STATUS_OPTIONS,
                            index=SHIPMENT_STATUS_OPTIONS.index(s.get("status")) if s.get("status") in SHIPMENT_STATUS_OPTIONS else 0,
                            key=f"ed_status_{current_status}",
                        )
                        e_load_month = st.text_input("装货月份", value=s.get("load_month") or "", key=f"ed_load_{current_status}")
                        e_supplier = st.text_input("供货方", value=s.get("supplier") or "", key=f"ed_sup_{current_status}")
                        e_vessel = st.text_input("船名", value=s.get("vessel_name") or "", key=f"ed_vsl_{current_status}")
                        e_arr_load = st.text_input("到装港日期", value=str(s.get("arrive_load_port_date") or ""), key=f"ed_arr_{current_status}")
                        e_load_start = st.text_input("装货日期", value=str(s.get("load_start_date") or ""), key=f"ed_ls_{current_status}")
                        e_load_end = st.text_input("完货日期", value=str(s.get("load_end_date") or ""), key=f"ed_le_{current_status}")
                    with e2:
                        e_plan_arr = st.text_input("计划到港日期", value=str(s.get("planned_arrival_date") or ""), key=f"ed_pa_{current_status}")
                        e_adj_arr = st.text_input("调整到港日期", value=str(s.get("adjusted_arrival_date") or ""), key=f"ed_aa_{current_status}")
                        e_act_arr = st.text_input("实际到港日期", value=str(s.get("actual_arrival_date") or ""), key=f"ed_act_{current_status}")
                        e_customs = st.text_input("通关完成日期", value=str(s.get("customs_clearance_date") or ""), key=f"ed_cc_{current_status}")
                        e_disc_complete = st.text_input("卸完日期", value=str(s.get("discharge_complete_date") or ""), key=f"ed_dc_{current_status}")
                        e_port = st.text_input("卸货港", value=s.get("discharge_port") or "", key=f"ed_port_{current_status}")
                        e_coal = st.text_input("煤种", value=s.get("coal_type") or "", key=f"ed_coal_{current_status}")
                    with e3:
                        e_sulfur = st.number_input("硫份(%)", value=float(s.get("sulfur_content") or 0), step=0.01, key=f"ed_sul_{current_status}")
                        e_calor = st.number_input("热值（大卡）", value=int(s.get("calorific_value") or 0), step=10, key=f"ed_cal_{current_status}")
                        e_qty = st.number_input("数量（万吨）", value=float(s.get("quantity") or 0), step=0.01, key=f"ed_qty_{current_status}")
                        e_fob = st.number_input("FOB价格", value=float(s.get("fob_price") or 0), step=0.01, key=f"ed_fob_{current_status}")
                        e_freight = st.number_input("海运费", value=float(s.get("freight_cost") or 0), step=0.01, key=f"ed_frt_{current_status}")
                        e_unit_price = st.number_input("标准单价", value=float(s.get("standard_unit_price") or 0), step=0.01, key=f"ed_up_{current_status}")

                    st.divider()
                    btn_save, btn_del, _ = st.columns([1, 1, 2])
                    with btn_save:
                        if st.button("💾 保存修改", type="primary", use_container_width=True, key=f"save_{current_status}"):
                            updated = {
                                "status": e_status,
                                "load_month": e_load_month or None,
                                "supplier": e_supplier or None,
                                "vessel_name": e_vessel or None,
                                "arrive_load_port_date": e_arr_load or None,
                                "load_start_date": e_load_start or None,
                                "load_end_date": e_load_end or None,
                                "planned_arrival_date": e_plan_arr or None,
                                "adjusted_arrival_date": e_adj_arr or None,
                                "actual_arrival_date": e_act_arr or None,
                                "customs_clearance_date": e_customs or None,
                                "discharge_complete_date": e_disc_complete or None,
                                "discharge_port": e_port or None,
                                "coal_type": e_coal or None,
                                "sulfur_content": e_sulfur,
                                "calorific_value": e_calor,
                                "quantity": e_qty,
                                "fob_price": e_fob,
                                "freight_cost": e_freight,
                                "standard_unit_price": e_unit_price,
                            }
                            errs = tpt.validate_shipment_dates(updated)
                            if errs:
                                for err in errs:
                                    st.error(err)
                            else:
                                ds.update_shipment(s["id"], updated)
                                st.success(f"运单 #{s['id']} 已更新！")
                                st.session_state[f"edit_shipment_{current_status}"] = None
                                st.rerun()
                    with btn_del:
                        if st.button("🗑 删除运单", type="secondary", use_container_width=True, key=f"del_edit_{current_status}_{s['id']}"):
                            ds.delete_shipment(s["id"])
                            st.success("运单已删除")
                            st.session_state[f"edit_shipment_{current_status}"] = None
                            st.rerun()
        else:
            st.info(f"暂无「{current_status}」状态的运单，请在「新增运单」或「批量导入」中添加")

    # ============ TAB 2: 新增运单 ============
    with tab_add:
        st.subheader("➕ 新增运单 — 系统根据计划到港日期自动归类")
        st.caption("带 * 号的为必填项")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            add_status = st.selectbox(
                "状态（提交时自动归类）",
                SHIPMENT_STATUS_OPTIONS,
                index=SHIPMENT_STATUS_OPTIONS.index(current_status),
                key=f"add_status_{current_status}",
                disabled=True,
            )
            st.caption("系统将根据「计划到港日期」自动判断：已到期 → 已下单｜未到期 → 计划调运")
            load_month = st.text_input("装货月份", key=f"add_lm_{current_status}")
            supplier = st.text_input("供货方", key=f"add_sup_{current_status}")
            vessel_name = st.text_input("船名 *", key=f"add_vsl_{current_status}")
            arrive_load_port_date = st.date_input("到装港日期", value=None, key=f"add_al_{current_status}")
            load_start_date = st.date_input("装货日期", value=None, key=f"add_ls_{current_status}")
            load_end_date = st.date_input("完货日期", value=None, key=f"add_le_{current_status}")

        with col_b:
            planned_arrival_date = st.date_input("计划到港日期 *", value=None, key=f"add_pa_{current_status}")
            adjusted_arrival_date = st.date_input("调整到港日期", value=None, key=f"add_aa_{current_status}")
            actual_arrival_date = st.date_input("实际到港日期", value=None, key=f"add_act_{current_status}")
            customs_clearance_date = st.date_input("通关完成日期", value=None, key=f"add_cc_{current_status}")
            discharge_complete_date = st.date_input("卸完日期", value=None, key=f"add_dc_{current_status}")
            discharge_port = st.text_input("卸货港", key=f"add_dp_{current_status}")
            coal_type = st.text_input("煤种", key=f"add_ct_{current_status}")

        with col_c:
            sulfur_content = st.number_input("硫份(%)", min_value=0.0, step=0.01, key=f"add_sul_{current_status}")
            calorific_value = st.number_input("热值（大卡） *", min_value=0, step=10, key=f"add_cal_{current_status}")
            quantity = st.number_input("数量（万吨） *", min_value=0.0, step=0.01, key=f"add_qty_{current_status}")
            fob_price = st.number_input("FOB价格", min_value=0.0, step=0.01, key=f"add_fob_{current_status}")
            freight_cost = st.number_input("海运费", min_value=0.0, step=0.01, key=f"add_frt_{current_status}")
            standard_unit_price = st.number_input("标准单价", min_value=0.0, step=0.01, key=f"add_up_{current_status}")

        # 热值分类实时预览
        if calorific_value > 0:
            cat, label = tpt.classify_calorific(calorific_value)
            emoji = {"高卡": "🔥", "中卡": "🟠", "低卡": "🔵"}.get(cat, "")
            st.caption(f"{emoji} 热值分类：**{cat}煤**（{calorific_value} 大卡）")

        st.divider()

        # --- 重复检测状态 ---
        dup_key = f"add_dup_{current_status}"
        if dup_key not in st.session_state:
            st.session_state[f"{dup_key}_data"] = None
            st.session_state[f"{dup_key}_existing"] = None

        if st.session_state[f"{dup_key}_data"]:
            dup_data = st.session_state[f"{dup_key}_data"]
            dup_existing = st.session_state[f"{dup_key}_existing"]

            st.error(f"⚠️ 检测到该数据可能已导入，请比对后再确定是否提交")

            cmp_a, cmp_b = st.columns(2)
            with cmp_a:
                st.markdown("### 📥 待提交数据")
                st.dataframe(
                    pd.DataFrame([{
                        "船名": dup_data.get("vessel_name"),
                        "计划到港": dup_data.get("planned_arrival_date"),
                        "数量（万吨）": dup_data.get("quantity"),
                        "热值": dup_data.get("calorific_value"),
                        "供货方": dup_data.get("supplier"),
                    }]),
                    use_container_width=True, hide_index=True,
                )
            with cmp_b:
                st.markdown("### 🗄️ 系统中已有数据")
                ex_show = []
                for ex in dup_existing:
                    ex_show.append({
                        "ID": ex.get("id"),
                        "船名": ex.get("vessel_name"),
                        "计划到港": ex.get("planned_arrival_date"),
                        "数量（万吨）": ex.get("quantity"),
                        "热值": ex.get("calorific_value"),
                        "状态": ex.get("status"),
                    })
                st.dataframe(pd.DataFrame(ex_show), use_container_width=True, hide_index=True)

            st.divider()
            btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
            with btn_c1:
                if st.button("✅ 确认提交（仍要添加）", type="primary", use_container_width=True, key=f"force_{current_status}"):
                    tpt.auto_classify_shipment(dup_data)
                    ds.add_shipment(dup_data)
                    classified = dup_data.get("status", "计划")
                    ordered = 1 if classified == "已下单" else 0
                    planned_count = 0 if classified == "已下单" else 1
                    st.success(
                        f"1条订单已导入，其中{ordered}条已下单，"
                        f"{planned_count}条为计划调运，已自动归类"
                    )
                    st.session_state["_show_success_toast"] = True
                    st.session_state[f"{dup_key}_data"] = None
                    st.session_state[f"{dup_key}_existing"] = None
                    st.rerun()
            with btn_c2:
                if st.button("❌ 取消", use_container_width=True, key=f"cancel_{current_status}"):
                    st.session_state[f"{dup_key}_data"] = None
                    st.session_state[f"{dup_key}_existing"] = None
                    st.rerun()
            with btn_c3:
                st.button("📋 报告管理员", disabled=True, use_container_width=True,
                          key=f"report_{current_status}", help="此功能待开发")

        else:
            if st.button("✅ 提交新增", type="primary", use_container_width=True, key=f"submit_{current_status}"):
                errors = []
                if not vessel_name:
                    errors.append("船名为必填项")
                if not planned_arrival_date:
                    errors.append("计划到港日期为必填项")
                if quantity <= 0:
                    errors.append("数量（煤量）必须大于0")
                if calorific_value <= 0:
                    errors.append("热值必须大于0")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    data = {
                        "status": add_status,
                        "load_month": load_month or None,
                        "supplier": supplier or None,
                        "vessel_name": vessel_name,
                        "arrive_load_port_date": str(arrive_load_port_date) if arrive_load_port_date else None,
                        "load_start_date": str(load_start_date) if load_start_date else None,
                        "load_end_date": str(load_end_date) if load_end_date else None,
                        "planned_arrival_date": str(planned_arrival_date) if planned_arrival_date else None,
                        "adjusted_arrival_date": str(adjusted_arrival_date) if adjusted_arrival_date else None,
                "actual_arrival_date": str(actual_arrival_date) if actual_arrival_date else None,
                "customs_clearance_date": str(customs_clearance_date) if customs_clearance_date else None,
                "discharge_complete_date": str(discharge_complete_date) if discharge_complete_date else None,
                        "discharge_port": discharge_port or None,
                        "coal_type": coal_type or None,
                        "sulfur_content": sulfur_content,
                        "calorific_value": calorific_value,
                        "quantity": quantity,
                        "fob_price": fob_price,
                        "freight_cost": freight_cost,
                        "standard_unit_price": standard_unit_price,
                    }

                    # --- 日期逻辑校验 ---
                    date_errs = tpt.validate_shipment_dates(data)
                    if date_errs:
                        for err in date_errs:
                            st.error(err)
                    else:
                        # --- 自动归类：根据计划到港日期判断状态 ---
                        tpt.auto_classify_shipment(data)

                        # --- 重复检测 ---
                        is_dup, existing = tpt.check_single_duplicate(data)
                        if is_dup:
                            st.session_state[f"{dup_key}_data"] = data
                            st.session_state[f"{dup_key}_existing"] = existing
                            st.rerun()
                        else:
                            ds.add_shipment(data)
                            classified = data.get("status", "计划")
                            ordered = 1 if classified == "已下单" else 0
                            planned_count = 0 if classified == "已下单" else 1
                            st.success(
                                f"1条订单已导入，其中{ordered}条已下单，"
                                f"{planned_count}条为计划调运，已自动归类"
                            )
                            st.session_state["_show_success_toast"] = True
                            st.rerun()

    # ============ TAB 3: 批量导入 ============
    with tab_import:
        st.subheader("📥 Excel 批量导入 — 系统根据计划到港日期自动归类")

        # --- 初始化 session_state ---
        imp_dup_key = f"imp_dup_{current_status}"
        if f"{imp_dup_key}_new" not in st.session_state:
            st.session_state[f"{imp_dup_key}_new"] = None
            st.session_state[f"{imp_dup_key}_existing"] = None
            st.session_state[f"{imp_dup_key}_parsed"] = None

        # --- 重复检测警告 ---
        if st.session_state[f"{imp_dup_key}_new"]:
            dup_new = st.session_state[f"{imp_dup_key}_new"]
            dup_existing = st.session_state[f"{imp_dup_key}_existing"]
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
                        "供货方": row.get("supplier", ""),
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
                if st.button("📥 确认导入（仍要导入）", type="primary", use_container_width=True, key=f"force_imp_{current_status}"):
                    parsed = st.session_state[f"{imp_dup_key}_parsed"]
                    ordered, planned_count = tpt.classify_batch(parsed)
                    ds.bulk_import_shipments(parsed)
                    st.success(
                        f"{len(parsed)}条订单已导入，其中{ordered}条已下单，"
                        f"{planned_count}条为计划调运，已自动归类"
                    )
                    st.session_state["_show_success_toast"] = True
                    st.session_state[f"upload_{current_status}"] = None
                    st.session_state[f"{imp_dup_key}_new"] = None
                    st.session_state[f"{imp_dup_key}_existing"] = None
                    st.session_state[f"{imp_dup_key}_parsed"] = None
                    st.rerun()
            with btn_c2:
                if st.button("❌ 取消", use_container_width=True, key=f"cancel_imp_{current_status}"):
                    st.session_state[f"{imp_dup_key}_new"] = None
                    st.session_state[f"{imp_dup_key}_existing"] = None
                    st.session_state[f"{imp_dup_key}_parsed"] = None
                    st.rerun()
            with btn_c3:
                st.button("📋 报告管理员", disabled=True, use_container_width=True,
                          key=f"report_imp_{current_status}", help="此功能待开发")

        st.info("上传的 Excel 必须包含以下必填列：\n\n**船名*、数量（万吨）*、热值（大卡）*、计划到港日期***")

        uploaded_file = st.file_uploader(
            "选择 Excel 文件",
            type=["xlsx", "xls"],
            key=f"upload_{current_status}",
        )

        if uploaded_file:
            from utils.excel_io import parse_excel

            # 新文件上传时清除旧状态
            up_name_key = f"last_up_{current_status}"
            if up_name_key not in st.session_state:
                st.session_state[up_name_key] = None
            if uploaded_file.name != st.session_state[up_name_key]:
                st.session_state[f"{imp_dup_key}_new"] = None
                st.session_state[f"{imp_dup_key}_existing"] = None
                st.session_state[f"{imp_dup_key}_parsed"] = None
                st.session_state[up_name_key] = uploaded_file.name

            try:
                parsed_rows = parse_excel(uploaded_file)

                # 自动为每条导入数据附加当前模块的 status
                for row in parsed_rows:
                    if "status" not in row or not row["status"]:
                        row["status"] = current_status

                # 校验必填字段
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

                if invalid_rows:
                    st.error(f"解析成功，但以下行缺少必填字段：")
                    for row_num, fields in invalid_rows:
                        st.caption(f"- 第 {row_num} 行缺少: {', '.join(fields)}")
                else:
                    st.success(f"解析成功，共识别 {len(parsed_rows)} 条运单记录，必填字段校验通过（导入时将根据计划到港日期自动归类）")

                if parsed_rows:
                    st.dataframe(pd.DataFrame(parsed_rows), use_container_width=True, hide_index=True, height=350)

                    if not invalid_rows:
                        if st.button("📥 确认导入", type="primary", use_container_width=True, key=f"confirm_imp_{current_status}"):
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
                                    st.session_state[f"{imp_dup_key}_new"] = dup_new
                                    st.session_state[f"{imp_dup_key}_existing"] = dup_existing
                                    st.session_state[f"{imp_dup_key}_parsed"] = parsed_rows
                                    st.rerun()
                                else:
                                    ordered, planned_count = tpt.classify_batch(parsed_rows)
                                    ds.bulk_import_shipments(parsed_rows)
                                    st.success(
                                        f"{len(parsed_rows)}条订单已导入，其中{ordered}条已下单，"
                                        f"{planned_count}条为计划调运，已自动归类"
                                    )
                                    st.session_state["_show_success_toast"] = True
                                    st.session_state[f"upload_{current_status}"] = None
                                    st.rerun()

            except Exception as e:
                st.error(f"解析失败: {e}")
