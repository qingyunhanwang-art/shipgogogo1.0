"""
AI 问答页面 — DeepSeek 自然语言查询
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st


from db.init_db import init_db
from business import transport as tpt
from business import inventory as inv_mod
from ai.qa import parse_question, build_answer, build_context, ask_deepseek
from config import DEEPSEEK_API_KEY

st.set_page_config(page_title="AI 问答", page_icon="💬", layout="wide")
init_db()

st.title("💬 AI 智能问答")

# ==================== API Key 状态 ====================
api_configured = DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-deepseek-api-key-here"
if api_configured:
    st.success("✅ DeepSeek AI 已连接")
else:
    st.warning("⚠️ DeepSeek API Key 未配置，使用本地规则应答。请在 `config.py` 中设置 `DEEPSEEK_API_KEY`")

# ==================== 快捷问题 ====================
st.subheader("快捷提问")

shortcut_cols = st.columns(4)
shortcuts = [
    ("📊 库存情况", "当前库存情况如何？"),
    ("🔥 高卡煤库存", "高卡煤库存有多少？"),
    ("🚢 在途运单", "有哪些运单在运输中？"),
    ("⚠️ 逾期预警", "有哪些运单逾期未到港？"),
]

selected_shortcut = None
for i, (label, question) in enumerate(shortcuts):
    with shortcut_cols[i]:
        if st.button(label, use_container_width=True, key=f"sc_{i}"):
            selected_shortcut = question

st.divider()

# ==================== 对话历史 ====================
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

# ==================== 输入区域 ====================
with st.form("qa_form", clear_on_submit=True):
    input_col1, input_col2 = st.columns([4, 1])
    with input_col1:
        user_input = st.text_input(
            "请输入您的问题...",
            value=selected_shortcut or "",
            placeholder="例如：当前库存有多少？有哪些运单在途？",
            label_visibility="collapsed",
        )
    with input_col2:
        submitted = st.form_submit_button("🔍 提问", type="primary", use_container_width=True)

# 运行时快捷问题注入
if selected_shortcut and not submitted:
    st.session_state._pending_question = selected_shortcut

if st.session_state.get("_pending_question"):
    user_input = st.session_state._pending_question
    st.session_state._pending_question = None
    submitted = True

if submitted and user_input:
    # 解析意图并准备上下文数据
    parsed = parse_question(user_input)
    inv = inv_mod.get_inventory_status()
    status_counts = tpt.get_all_status_counts()
    summary = ", ".join([f"{k}: {v}票" for k, v in status_counts.items() if v > 0])
    al_warnings = inv_mod.get_all_warnings()
    cal_breakdown = inv_mod.get_inventory_by_calorific()
    context = build_context(inv, summary, al_warnings, cal_breakdown)

    exact_answer = None
    exact_rows = None

    # ========== 精确本地查询（快速回答）==========
    if parsed.get("is_exact"):
        target_date = parsed.get("date")
        grade = parsed.get("grade")
        intent = parsed["intent"]

        if intent in ("热值库存", "库存查询"):
            qty, rows = tpt.get_inventory_by_date(target_date, grade)
        elif intent in ("热值到港", "到港查询"):
            qty, rows = tpt.get_arrivals_by_date(target_date, grade)
        elif intent in ("热值在途", "在途查询"):
            qty, rows = tpt.get_transit_by_date(target_date, grade)
        elif intent in ("热值在港", "在港查询"):
            qty, rows = tpt.get_in_port_by_date(target_date, grade)
        elif intent == "总运输量":
            qty, rows = tpt.get_total_shipments(grade)
        elif intent == "逾期预警":
            rows = tpt.get_delay_warnings()
            qty = sum(r.get("quantity", 0) or 0 for r in rows)
        else:
            qty, rows = 0, []

        exact_answer = build_answer(parsed, qty, rows)
        exact_rows = rows

    # ========== 通用问答走 AI ==========
    else:
        answer = ask_deepseek(user_input, context)

    # 记录对话
    st.session_state.qa_history.append({
        "role": "user",
        "content": user_input,
    })
    st.session_state.qa_history.append({
        "role": "assistant",
        "content": exact_answer if exact_answer is not None else answer,
        "exact": exact_answer is not None,
        "rows": exact_rows if exact_rows is not None else [],
    })

# ==================== 对话展示 ====================
st.divider()
st.subheader("对话记录")

for msg in reversed(st.session_state.qa_history):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            content = msg["content"]
            if msg.get("exact"):
                # 精确回答：绿色背景突出关键数字
                st.success(content)
                # 下拉展示相关明细数据
                rows = msg.get("rows", [])
                if rows:
                    with st.expander("🔍 查看相关数据明细", expanded=False):
                        display_df = pd.DataFrame(rows)
                        keep_cols = [
                            "vessel_name", "supplier", "coal_type", "discharge_port",
                            "quantity", "calorific_value", "sulfur_content",
                            "load_month", "arrive_load_port_date", "load_start_date",
                            "load_end_date", "planned_arrival_date", "adjusted_arrival_date",
                            "actual_arrival_date", "customs_clearance_date",
                            "discharge_complete_date", "status",
                            "fob_price", "freight_cost", "standard_unit_price",
                        ]
                        show_cols = [c for c in keep_cols if c in display_df.columns]
                        display_df = display_df[show_cols]
                        display_df.columns = [{
                            "vessel_name": "船名", "supplier": "供货方",
                            "coal_type": "煤种", "discharge_port": "卸货港",
                            "quantity": "数量（万吨）", "calorific_value": "热值（大卡）",
                            "sulfur_content": "硫份(%)", "load_month": "装货月份",
                            "arrive_load_port_date": "到装港日期", "load_start_date": "装货日期",
                            "load_end_date": "完货日期", "planned_arrival_date": "计划到港日期",
                            "adjusted_arrival_date": "调整到港日期", "actual_arrival_date": "实际到港日期",
                            "customs_clearance_date": "通关完成日期",
                            "discharge_complete_date": "卸完日期",
                            "status": "状态",
                            "fob_price": "FOB价格", "freight_cost": "海运费",
                            "standard_unit_price": "标准单价",
                        }.get(c, c) for c in display_df.columns]
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.write(content)

# 清空按钮
if st.session_state.qa_history:
    if st.button("🧹 清空对话", key="clear_qa"):
        st.session_state.qa_history = []
        st.rerun()
