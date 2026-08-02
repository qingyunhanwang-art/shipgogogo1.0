# 煤船快跑 · 扣子代码节点 · 问答辅助（移植 ai/qa.py）
# 仅用 Python 标准库。提供：日期解析、热值抽取、上下文拼装、回答拼装。
# 入口：main(question) -> {date_str, date_label, grade, intent_hint}

import re
from datetime import date, timedelta


def _parse_date(question, today=None):
    """解析中文/数字日期。返回 (date对象, 标签) 或 (None, None)。"""
    today = today or date.today()
    # 今天/昨天/前天
    for kw, off in (("大前天", 3), ("前天", 2), ("昨天", 1), ("今天", 0), ("今日", 0)):
        if kw in question:
            d = today - timedelta(days=off)
            return d, kw
    # YYYY-MM-DD / YYYY/MM/DD
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", question)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            dt = date(y, mo, d)
            return dt, f"{y}年{mo}月{d}日"
        except ValueError:
            pass
    # X月X日
    m = re.search(r"(\d{1,2})月(\d{1,2})日", question)
    if m:
        mo, d = map(int, m.groups())
        y = today.year
        if mo > today.month:
            y -= 1
        try:
            return date(y, mo, d), f"{y}年{mo}月{d}日"
        except ValueError:
            pass
    # X/X 或 X.X
    for pat in (r"(\d{1,2})/(\d{1,2})", r"(\d{1,2})\.(\d{1,2})"):
        m = re.search(pat, question)
        if m:
            mo, d = map(int, m.groups())
            y = today.year
            if mo > today.month:
                y -= 1
            try:
                return date(y, mo, d), f"{y}年{mo}月{d}日"
            except ValueError:
                pass
    return None, None


def extract_grade(question):
    if "高卡" in question:
        return "高卡"
    if "中卡" in question:
        return "中卡"
    if "低卡" in question:
        return "低卡"
    m = re.search(r"(\d{3,4})\s*(?:大卡|kcal)", question)
    if m:
        v = int(m.group(1))
        return "高卡" if v > 5000 else ("中卡" if v >= 4000 else "低卡")
    return "全部"


def intent_hint(question):
    q = question
    if any(k in q for k in ("逾期", "迟到", "没到")):
        return "逾期查询"
    if any(k in q for k in ("在途", "海上", "还没到", "未到港")):
        return "在途查询"
    if any(k in q for k in ("到港", "抵达", "到货")):
        return "到港查询"
    if any(k in q for k in ("库存", "堆存", "存煤", "有多少煤")):
        return "库存查询"
    if any(k in q for k in ("高卡", "中卡", "低卡", "热值")):
        return "热值分类"
    if any(k in q for k in ("船", "运单", "供货")):
        return "运单查询"
    return "通用"


def build_context(shipments, inventory):
    """拼装给大模型做通用问答的精简上下文。"""
    lines = [f"运单总数：{len(shipments)}"]
    inv_total = sum(float(r.get("quantity") or 0) for r in inventory)
    lines.append(f"当前库存总量（万吨）：{round(inv_total, 2)}")
    recent = sorted(shipments, key=lambda r: str(r.get("planned_arrival_date") or ""), reverse=True)[:15]
    for r in recent:
        lines.append(
            f"- {r.get('vessel_name')} | 状态{r.get('status')} | 计划到港{r.get('planned_arrival_date')} "
            f"| 热值{r.get('calorific_value')} | 数量{r.get('quantity')}万吨"
        )
    return "\n".join(lines)


def main(question):
    d, label = _parse_date(question)
    return {
        "date_str": d.strftime("%Y-%m-%d") if d else "",
        "date_label": label or "",
        "grade": extract_grade(question),
        "intent_hint": intent_hint(question),
    }
