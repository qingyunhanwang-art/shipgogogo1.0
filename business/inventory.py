"""
库存业务逻辑 — 与运单一对一对应
"""
from datetime import date, timedelta
from db import data_service as ds
from config import LOW_STOCK_RATIO, EXPIRE_WARNING_DAYS


# ==================== 同步 ====================

def sync_from_transport():
    """清空库存并重新从调运单导入已到港/已卸完的运单（一一对应）
    返回 (已同步条数, 未同步条数)"""
    return ds.clear_and_sync_inventory()


def clear_empty():
    """一键清除库存数量为 0 的空白库存单，返回清除条数"""
    return ds.clear_empty_inventory()


# ==================== 查询 ====================

def get_inventory_status():
    """获取库存汇总（兼容旧接口，汇总全部运单库存）"""
    all_inv = ds.get_all_inventory()
    total_qty = sum((r.get("inventory_quantity") or 0) for r in all_inv)
    total_safety = sum((r.get("safety_stock") or 0) for r in all_inv)
    # 取最早的效期
    min_expiry = None
    for r in all_inv:
        ed = r.get("inventory_expiry_date")
        if ed:
            if min_expiry is None or ed < min_expiry:
                min_expiry = ed
    return {
        "quantity": total_qty,
        "safety_stock": total_safety,
        "expiry_date": str(min_expiry) if min_expiry else None,
        "remark": f"共 {len(all_inv)} 条运单库存",
    }


def get_all_inventory():
    """获取全部库存（含运单完整信息）"""
    return ds.get_all_inventory()


def get_inventory_by_shipment(shipment_id):
    """获取某条运单的库存信息"""
    return ds.get_inventory_by_shipment(shipment_id)


# ==================== 出入库 ====================

def stock_in(shipment_id, qty, operator="", remark=""):
    """入库：针对某条运单"""
    if qty <= 0:
        raise ValueError("入库数量必须大于0")
    # 校验运单存在
    s = ds.get_shipment_by_id(shipment_id)
    if not s:
        raise ValueError(f"运单 #{shipment_id} 不存在")
    ds.add_inventory_txn(shipment_id, "入", qty, operator, remark)


def stock_out(shipment_id, qty, operator="", remark=""):
    """出库：针对某条运单"""
    if qty <= 0:
        raise ValueError("出库数量必须大于0")
    inv = ds.get_inventory_by_shipment(shipment_id)
    if not inv or inv["quantity"] < qty:
        raise ValueError(f"运单 #{shipment_id} 库存不足，当前库存: {inv['quantity'] if inv else 0} 万吨")
    ds.add_inventory_txn(shipment_id, "出", qty, operator, remark)


# ==================== 预警 ====================

def get_per_shipment_warnings():
    """获取每条运单的低库存和效期预警"""
    all_inv = ds.get_all_inventory()
    warnings = []
    for inv in all_inv:
        wid = inv.get("shipment_id") or inv.get("id")
        qty = inv.get("inventory_quantity", 0) or 0
        safe = inv.get("safety_stock", 0) or 0
        exp_date = inv.get("inventory_expiry_date")

        # 低库存：有安全库存且当前库存低于阈值
        if safe > 0 and qty < safe * (1 - LOW_STOCK_RATIO):
            warnings.append({
                "shipment_id": wid,
                "vessel_name": inv.get("vessel_name", ""),
                "type": "低库存",
                "level": "warning",
                "detail": f"库存 {qty} 万吨 < 安全库存 {safe} 万吨，缺口 {safe - qty} 万吨",
            })

        # 效期预警
        if exp_date:
            if isinstance(exp_date, str):
                exp_date = date.fromisoformat(exp_date)
            remaining = (exp_date - date.today()).days
            if remaining <= EXPIRE_WARNING_DAYS:
                level = "error" if remaining < 0 else "warning"
                tag = "已过期" if remaining < 0 else f"剩余 {remaining} 天"
                warnings.append({
                    "shipment_id": wid,
                    "vessel_name": inv.get("vessel_name", ""),
                    "type": "效期",
                    "level": level,
                    "detail": f"效期: {exp_date}（{tag}）",
                })
    return warnings


def get_all_warnings():
    """获取所有告警汇总（兼容旧接口）"""
    return get_per_shipment_warnings()


# ==================== 出入库记录 ====================

def get_recent_txns(limit=30):
    """获取最近出入库记录"""
    return ds.get_inventory_txns(limit=limit)


def get_shipment_txns(shipment_id, limit=20):
    """获取某运单的出入库记录"""
    return ds.get_inventory_txns(shipment_id=shipment_id, limit=limit)


def get_total_inventory():
    """总库存汇总"""
    return ds.get_total_inventory()


# ==================== 热值分类统计 ====================

def get_inventory_by_calorific():
    """
    按热值分类统计库存
    返回 { "高卡": qty, "中卡": qty, "低卡": qty, "总量": qty }
    """
    from business.transport import get_calorific_breakdown
    breakdown = get_calorific_breakdown()
    total = breakdown["高卡"] + breakdown["中卡"] + breakdown["低卡"]
    breakdown["总量"] = total
    return breakdown
