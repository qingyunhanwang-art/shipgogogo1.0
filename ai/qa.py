"""
DeepSeek AI 问答模块 — 意图识别与自然语言应答
"""
import re
from datetime import date, timedelta

from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

# ==================== 工具函数映射 ====================

# 意图关键词 → 可调用的业务函数
INTENT_MAP = {
    "热值查询": ["高卡", "中卡", "低卡", "热值", "卡数", "发热量"],
    "库存查询": ["库存", "还有多少", "还剩多少", "当前库存", "库存量", "库存情况", "库存状态"],
    "安全库存": ["安全库存", "最低库存"],
    "运单查询": ["运单", "船", "到港", "装货", "发货", "运输", "shipment"],
    "在途查询": ["在途", "运输中", "海上"],
    "逾期预警": ["逾期", "延期", "延迟", "还没到", "没到港"],
    "效期查询": ["效期", "过期", "到期", "有效期", "保质期"],
    "到港统计": ["到港", "已到港", "已通关", "通关"],
    "统计": ["统计", "汇总", "一共", "多少"],
}


def detect_intent(question: str) -> str:
    """
    基于关键词的简单意图识别（仅后台使用，不展示给用户）
    """
    q = question.lower()
    for intent, keywords in INTENT_MAP.items():
        for kw in keywords:
            if kw.lower() in q:
                return intent
    return "通用问答"


# ==================== 自然语言精确解析（本地直接回答） ====================

GRADE_MAP = {
    "高卡": "高卡",
    "中卡": "中卡",
    "低卡": "低卡",
}


def _parse_date(question: str) -> tuple:
    """
    从问题中解析日期，返回 (date_obj, 显示文本)
    支持：今天、昨天、7月15日、2026-07-15、7/15
    """
    today = date.today()
    q = question.lower()

    if "今天" in q or "今日" in q:
        return today, "今天"
    if "昨天" in q or "昨日" in q:
        return today - timedelta(days=1), "昨天"

    # 2026-07-15 / 2026/07/15
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", question)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d), f"{y}年{mo}月{d}日"

    # 7月15日
    m = re.search(r"(\d{1,2})月(\d{1,2})日", question)
    if m:
        mo, d = map(int, m.groups())
        y = today.year
        # 如果月份大于当前月份，推测为去年（例如当前1月问12月）
        if mo > today.month:
            y -= 1
        return date(y, mo, d), f"{y}年{mo}月{d}日"

    # 7/15
    m = re.search(r"(\d{1,2})/(\d{1,2})", question)
    if m:
        mo, d = map(int, m.groups())
        y = today.year
        if mo > today.month:
            y -= 1
        return date(y, mo, d), f"{y}年{mo}月{d}日"

    # 8.15（数字点数字格式）
    m = re.search(r"(\d{1,2})\.(\d{1,2})", question)
    if m:
        mo, d = map(int, m.groups())
        y = today.year
        if mo > today.month:
            y -= 1
        return date(y, mo, d), f"{y}年{mo}月{d}日"

    return None, None


def _parse_grade(question: str) -> str | None:
    """提取热值分类"""
    for kw in GRADE_MAP:
        if kw in question:
            return GRADE_MAP[kw]
    return None


def parse_question(question: str) -> dict:
    """
    解析用户问题，返回结构化信息：
    {
        "intent": str,      # 精确查询意图或通用问答
        "date": date|None,
        "date_str": str|None,
        "grade": str|None,
        "is_exact": bool,   # 是否可直接本地精确查询
    }
    """
    q = question.lower()
    target_date, date_display = _parse_date(question)
    grade = _parse_grade(question)

    # 判断意图
    exact_intent = None

    if "高卡" in question or "中卡" in question or "低卡" in question:
        if "库存" in question:
            exact_intent = "热值库存"
        elif "到港" in question or "到库" in question:
            exact_intent = "热值到港"
        elif "在途" in question:
            exact_intent = "热值在途"
        elif "在港" in question:
            exact_intent = "热值在港"
    elif "库存" in question:
        exact_intent = "库存查询"
    elif "到港" in question or "到库" in question:
        exact_intent = "到港查询"
    elif "在途" in question or "运输中" in question or "海上" in question:
        exact_intent = "在途查询"
    elif "在港" in question:
        exact_intent = "在港查询"
    elif "逾期" in question or "延期" in question or "延迟" in question or "还没到" in question:
        exact_intent = "逾期预警"
    elif "总运输量" in question or "总量" in question or "一共" in question:
        exact_intent = "总运输量"

    if exact_intent:
        return {
            "intent": exact_intent,
            "date": target_date,
            "date_str": date_display or "今天",
            "grade": grade,
            "is_exact": True,
        }

    return {
        "intent": detect_intent(question),
        "date": None,
        "date_str": None,
        "grade": None,
        "is_exact": False,
    }


def build_answer(parsed: dict, qty: float, rows: list) -> str:
    """
    根据解析结果和查询结果，生成精简回答文本
    """
    date_str = parsed.get("date_str") or "今天"
    grade = parsed.get("grade")
    grade_text = f"{grade}煤" if grade else "煤"
    intent = parsed["intent"]

    if intent == "热值库存":
        return f"{date_str}，{grade_text}库存为 **{qty:.2f} 万吨**。"
    if intent == "库存查询":
        return f"{date_str}，库存总量为 **{qty:.2f} 万吨**。"
    if intent == "热值到港":
        return f"{date_str}，计划到港的{grade_text}共 **{qty:.2f} 万吨**。"
    if intent == "到港查询":
        return f"{date_str}，计划到港的煤炭共 **{qty:.2f} 万吨**。"
    if intent == "热值在途":
        return f"{date_str}，在途{grade_text}共 **{qty:.2f} 万吨**。"
    if intent == "在途查询":
        return f"{date_str}，在途煤炭共 **{qty:.2f} 万吨**。"
    if intent == "热值在港":
        return f"{date_str}，在港未通关的{grade_text}共 **{qty:.2f} 万吨**。"
    if intent == "在港查询":
        return f"{date_str}，在港未通关的煤炭共 **{qty:.2f} 万吨**。"
    if intent == "逾期预警":
        return f"当前共有 **{len(rows)} 票** 运单逾期，合计 **{qty:.2f} 万吨**。"
    if intent == "总运输量":
        return f"系统中煤炭总运输量为 **{qty:.2f} 万吨**。"
    return ""


def build_context(inventory_info: dict, shipment_summary: dict, warnings: list, calorific_breakdown: dict = None) -> str:
    """
    构建 AI 上下文：将当前库存、运单、预警和热值分类数据组织成文本
    """
    ctx_parts = []

    # 库存信息
    if inventory_info:
        ctx_parts.append(
            f"【当前库存】{inventory_info['quantity']} 万吨，"
            f"安全库存 {inventory_info['safety_stock']} 万吨，"
            f"效期: {inventory_info['expiry_date'] or '未设置'}。"
        )

    # 热值分类库存
    if calorific_breakdown:
        parts = []
        for cat in ["高卡", "中卡", "低卡"]:
            if calorific_breakdown.get(cat, 0) > 0:
                parts.append(f"{cat}煤: {calorific_breakdown[cat]:.2f} 万吨")
        if parts:
            ctx_parts.append(f"【有效库存（已到港+已通关）按热值分类】\n总量 {calorific_breakdown.get('总量', 0):.2f} 万吨\n" + "\n".join(parts))

    # 运单汇总
    if shipment_summary:
        ctx_parts.append(f"【运单汇总】{shipment_summary}")

    # 预警
    if warnings:
        warn_texts = [f"{w['type']}: {w['detail']}" for w in warnings]
        ctx_parts.append("【当前预警】\n" + "\n".join(warn_texts))

    return "\n".join(ctx_parts)


def ask_deepseek(question: str, context: str) -> str:
    """
    调用 DeepSeek API 进行问答
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your-deepseek-api-key-here":
        # API Key 未配置时，返回本地规则响应
        return local_fallback(question, context)

    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        system_prompt = (
            "你是一个原料库存和运输管理AI助手。"
            "请严格基于提供的业务数据回答用户问题，回答必须简洁、直接，只输出关键数字和结论。"
            "不要回答与库存、运输、运单、到港、在途无关的问题。"
            "如果数据不足，直接说明无法查询到相关记录。"
        )

        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": f"当前业务数据：\n{context}"},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"AI 服务暂时不可用：{str(e)}\n\n以下是根据本地数据的基本回复：\n{local_fallback(question, context)}"


def local_fallback(question: str, context: str) -> str:
    """
    本地兜底应答（API不可用时）
    """
    intent = detect_intent(question)

    # 提取上下文中的关键数据
    responses = {
        "热值查询": f"根据有效库存（已到港+已通关）数据：\n{context}\n\n您可以在「库存管理」页面查看按热值分类的库存明细。",
        "库存查询": f"根据当前数据：\n{context}\n\n您可以通过「库存管理」页面查看实时库存和进行操作。",
        "安全库存": f"根据当前数据：\n{context}\n\n请确认安全库存设置是否合理，可在库存管理页面调整。",
        "运单查询": f"根据当前数据：\n{context}\n\n您可以在「运单管理」页面按关键词筛选具体运单。",
        "在途查询": f"根据当前数据：\n{context}\n\n您可以在「运单管理」页面查看所有运单信息。",
        "逾期预警": f"根据当前数据：\n{context}\n\n请在「预警中心」查看逾期详情并跟进处理。",
        "效期查询": f"根据当前数据：\n{context}\n\n请在库存管理页面关注效期信息。",
        "到港统计": f"根据当前数据：\n{context}\n\n详情请查看运单管理页面。",
        "统计": f"根据当前数据：\n{context}\n\n详细统计请查看各功能页面的数据视图。",
        "通用问答": f"您的问题我已收到。当前业务数据如下：\n\n{context}\n\n如需更具体的分析，请尝试使用以下关键词：\n- 查询库存情况 / 高卡煤有多少\n- 查询运单信息\n- 查看逾期/效期预警",
    }

    return responses.get(intent, responses["通用问答"])
