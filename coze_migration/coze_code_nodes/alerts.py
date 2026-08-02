# 煤船快跑 · 扣子代码节点 · 预警计算（移植 inventory.py + transport.py）
# 仅用 Python 标准库。入口函数 main(shipments, inventory) -> 三类预警 + 统计
# shipments: 运单列表；inventory: inventory_simple 列表（含 safety_stock, expiry_date, shipment_id）

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


def get_delay_warnings(shipments):
    """调整到港日期 < 今天 且 状态=已下单。"""
    from datetime import date
    today = date.today()
    out = []
    for r in shipments:
        if r.get("status") != "已下单":
            continue
        adj = _to_date(r.get("adjusted_arrival_date"))
        if adj and adj < today:
            out.append({
                "vessel_name": r.get("vessel_name"),
                "adjusted_arrival_date": r.get("adjusted_arrival_date"),
                "planned_arrival_date": r.get("planned_arrival_date"),
                "quantity": r.get("quantity"),
                "level": "error",
                "type": "运输逾期",
                "message": f"{r.get('vessel_name')} 调整到港 {r.get('adjusted_arrival_date')} 已逾期",
            })
    return out


def get_per_shipment_warnings(inventory):
    """低库存(<安全库存*0.8) 与 效期(距效期<=30天)。"""
    from datetime import date, timedelta
    today = date.today()
    out = []
    for r in inventory:
        qty = _to_float(r.get("quantity"))
        safety = _to_float(r.get("safety_stock"))
        if safety > 0 and qty < safety * (1 - 0.2):
            out.append({
                "shipment_id": r.get("shipment_id"),
                "quantity": qty,
                "safety_stock": safety,
                "level": "warning",
                "type": "低库存",
                "message": f"运单{r.get('shipment_id')} 库存 {qty} 万吨 < 安全库存 {safety}×0.8",
            })
        exp = _to_date(r.get("expiry_date"))
        if exp:
            left = (exp - today).days
            if left <= 30:
                level = "error" if left < 0 else "warning"
                out.append({
                    "shipment_id": r.get("shipment_id"),
                    "expiry_date": r.get("expiry_date"),
                    "days_left": left,
                    "level": level,
                    "type": "效期",
                    "message": f"运单{r.get('shipment_id')} 距效期剩 {left} 天（{r.get('expiry_date')}）",
                })
    return out


def main(shipments, inventory):
    delay = get_delay_warnings(shipments or [])
    others = get_per_shipment_warnings(inventory or [])
    return {
        "delay": delay,
        "others": others,
        "all": delay + others,
        "delay_count": len(delay),
        "other_count": len(others),
        "total_count": len(delay) + len(others),
    }
