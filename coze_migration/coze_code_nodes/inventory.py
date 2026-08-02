# 煤船快跑 · 扣子代码节点 · 库存计算（移植 inventory.py / data_service.py）
# 仅用 Python 标准库。
# 三个入口，按工作流需要分别选用：
#   sync_filter(shipments)        -> 应入库存的 shipment_id 列表
#   apply_txn(quantity, qty, t)   -> 出入库后的新库存数量
#   stats_by_calorific(inv_rows)  -> 按热值分类的库存统计

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


def classify_calorific(cv):
    cv = _to_float(cv)
    if cv <= 4000:
        return "低卡"
    elif cv < 5000:
        return "中卡"
    return "高卡"


def sync_filter(shipments):
    """返回应同步进库存的 shipment_id 列表：实际到港<=今天 或 卸完<=今天。"""
    from datetime import date
    today = date.today()
    ids = []
    for s in shipments:
        act = _to_date(s.get("actual_arrival_date"))
        dis = _to_date(s.get("discharge_complete_date"))
        if (act and act <= today) or (dis and dis <= today):
            ids.append(s.get("id"))
    return ids


def apply_txn(quantity, qty, txn_type):
    """出入库后库存：入加出减，不小于0。"""
    base = _to_float(quantity)
    delta = _to_float(qty)
    new = base + delta if txn_type == "入" else base - delta
    return max(new, 0.0)


def stats_by_calorific(inv_rows):
    """inv_rows: 已 JOIN 运单的库存行（含 calorific_value）。
    返回 {分类: {"qty": 总库存, "count": 条数}}。"""
    stats = {}
    for r in inv_rows:
        g = classify_calorific(r.get("calorific_value"))
        d = stats.setdefault(g, {"qty": 0.0, "count": 0})
        d["qty"] += _to_float(r.get("quantity"))
        d["count"] += 1
    for g in stats:
        stats[g]["qty"] = round(stats[g]["qty"], 2)
    return stats


def main(shipments=None, inv_rows=None, quantity=None, qty=None, txn_type=None, action="stats"):
    if action == "sync":
        return {"sync_ids": sync_filter(shipments or [])}
    if action == "txn":
        return {"new_quantity": apply_txn(quantity, qty, txn_type)}
    return {"stats": stats_by_calorific(inv_rows or [])}
