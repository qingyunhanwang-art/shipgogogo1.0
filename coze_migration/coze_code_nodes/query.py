# 煤船快跑 · 扣子代码节点 · 精确查询与聚合（移植 transport.py）
# 仅用 Python 标准库。入口函数 main(rows, query_date, grade) -> 指标字典
# rows: 数据库读取的全部运单列表；query_date: "YYYY-MM-DD" 或 ""(=今天)；grade: "全部"/"高卡"/"中卡"/"低卡"

def _to_float(v):
    try:
        if v in (None, ""):
            return 0.0
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _to_date(v):
    from datetime import datetime
    if v in (None, ""):
        return None
    if hasattr(v, "strftime"):
        return v if (hasattr(v, "year") and not hasattr(v, "hour")) else v.date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def classify_calorific(calorific_value):
    cv = _to_float(calorific_value)
    if cv <= 4000:
        return "低卡"
    elif cv < 5000:
        return "中卡"
    return "高卡"


def _grade_match(r, grade):
    return grade in ("全部", None, "") or classify_calorific(r.get("calorific_value")) == grade


def main(rows, query_date, grade="全部"):
    from datetime import date
    target = _to_date(query_date) or date.today()

    # 有效库存：已下单 且 实际到港<=target 且 通关<=target
    eff_total = 0.0
    eff_items = []
    for r in rows:
        if r.get("status") != "已下单":
            continue
        act, cus = _to_date(r.get("actual_arrival_date")), _to_date(r.get("customs_clearance_date"))
        if act and act <= target and cus and cus <= target and _grade_match(r, grade):
            eff_total += _to_float(r.get("quantity"))
            eff_items.append(r)

    # 某日到港量
    arrived = sum(_to_float(r.get("quantity")) for r in rows
                 if _to_date(r.get("actual_arrival_date")) == target and _grade_match(r, grade))
    # 某日计划到港量
    planned = sum(_to_float(r.get("quantity")) for r in rows
                  if _to_date(r.get("planned_arrival_date")) == target and _grade_match(r, grade))
    # 某日在途量：计划到港<=target 且 (未到港 或 到港>target)
    intransit = 0.0
    for r in rows:
        p, act = _to_date(r.get("planned_arrival_date")), _to_date(r.get("actual_arrival_date"))
        if p and p <= target and (act is None or act > target) and _grade_match(r, grade):
            intransit += _to_float(r.get("quantity"))
    # 总运输量
    total = sum(_to_float(r.get("quantity")) for r in rows if _grade_match(r, grade))

    # 逾期：状态=已下单 且 调整到港<今天
    today = date.today()
    delay = [r for r in rows
             if r.get("status") == "已下单"
             and _to_date(r.get("adjusted_arrival_date"))
             and _to_date(r.get("adjusted_arrival_date")) < today]

    return {
        "query_date": str(target),
        "grade": grade,
        "effective_inventory": round(eff_total, 2),
        "effective_count": len(eff_items),
        "arrived_qty": round(arrived, 2),
        "planned_qty": round(planned, 2),
        "in_transit_qty": round(intransit, 2),
        "total_transport": round(total, 2),
        "delay_count": len(delay),
        "delay_shipments": [
            {"vessel_name": r.get("vessel_name"), "adjusted_arrival_date": r.get("adjusted_arrival_date"),
             "planned_arrival_date": r.get("planned_arrival_date"), "quantity": r.get("quantity")}
            for r in delay
        ],
    }
