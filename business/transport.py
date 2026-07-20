"""
运单业务逻辑 — 预警、统计、查询、热值分类
"""
from datetime import date, timedelta
from db import data_service as ds
from config import SHIPMENT_STATUS_OPTIONS


# ==================== 热值分类 ====================

def classify_calorific(calorific_value):
    """
    热值分类：
    <=4000 → 低卡
    4000~5000 → 中卡
    >5000 → 高卡
    返回 (分类名, 标签)
    """
    if calorific_value is None or calorific_value == 0:
        return "未知", "未知"
    if calorific_value <= 4000:
        return "低卡", "低卡煤"
    elif calorific_value <= 5000:
        return "中卡", "中卡煤"
    else:
        return "高卡", "高卡煤"


def get_calorific_breakdown():
    """
    将已下单的运单按热值汇总（视为有效库存）
    返回 { "高卡": qty, "中卡": qty, "低卡": qty }
    """
    shipments = ds.get_all_shipments(limit=5000)
    breakdown = {"高卡": 0.0, "中卡": 0.0, "低卡": 0.0}
    for s in shipments:
        # 只统计已下单的有效库存
        if s.get("status") == "已下单":
            cat, _ = classify_calorific(s.get("calorific_value"))
            if cat in breakdown:
                breakdown[cat] += (s.get("quantity") or 0)
    return breakdown


# ==================== 按日期/热值精确查询（AI问答用） ====================

def _str_to_date(d):
    """辅助：统一转成 date 对象或 None"""
    if d is None or d == "":
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return date.fromisoformat(d)
        except Exception:
            return None
    return None


def _match_grade(s, grade):
    """辅助：判断运单热值分类是否匹配"""
    if not grade:
        return True
    cat, _ = classify_calorific(s.get("calorific_value"))
    return cat == grade


def get_inventory_by_date(target_date, grade=None):
    """
    查询指定日期前（含）的有效库存：
    已下单 且 实际到港日期 <= target_date 且 通关日期 <= target_date
    实际到港日期为空的不纳入计算（尚未到港，不算库存）
    返回 (总数量, 匹配运单列表)
    """
    target = _str_to_date(target_date)
    if target is None:
        target = date.today()

    shipments = ds.get_all_shipments(limit=5000)
    matched = []
    total = 0.0
    for s in shipments:
        if s.get("status") != "已下单":
            continue
        actual = _str_to_date(s.get("actual_arrival_date"))
        customs = _str_to_date(s.get("customs_clearance_date"))
        # 实际到港日期为空 → 未实际到港，不纳入库存
        if actual is None:
            continue
        # 实际到港日期晚于查询日期 → 尚未到港
        if actual > target:
            continue
        # 通关日期晚于查询日期 → 尚未计入库存
        if customs and customs > target:
            continue
        if not _match_grade(s, grade):
            continue
        matched.append(s)
        total += s.get("quantity") or 0
    return total, matched


def get_arrivals_by_date(target_date, grade=None):
    """
    查询指定日期计划到港的运单
    计划到港日期为空的不纳入计算（数据不完整）
    返回 (总数量, 匹配运单列表)
    """
    target = _str_to_date(target_date)
    if target is None:
        target = date.today()

    shipments = ds.get_all_shipments(limit=5000)
    matched = []
    total = 0.0
    for s in shipments:
        planned = _str_to_date(s.get("planned_arrival_date"))
        # 计划到港日期为空，视为数据不完整，不纳入计算
        if planned is None:
            continue
        if planned != target:
            continue
        if not _match_grade(s, grade):
            continue
        matched.append(s)
        total += s.get("quantity") or 0
    return total, matched


def get_transit_by_date(target_date, grade=None):
    """
    查询指定日期在途的运单：计划到港日期 > target_date 且 实际到港为空
    计划到港日期为空 或 状态为"计划"的运单不纳入计算
    返回 (总数量, 匹配运单列表)
    """
    target = _str_to_date(target_date)
    if target is None:
        target = date.today()

    shipments = ds.get_all_shipments(limit=5000)
    matched = []
    total = 0.0
    for s in shipments:
        planned = _str_to_date(s.get("planned_arrival_date"))
        actual = _str_to_date(s.get("actual_arrival_date"))
        # 计划到港日期为空 → 数据不完整，排除
        if planned is None:
            continue
        # 还在计划阶段，未实际下单，排除
        if s.get("status") == "计划":
            continue
        # 在途：计划到港在未来，且尚未实际到港
        if planned > target and actual is None:
            if not _match_grade(s, grade):
                continue
            matched.append(s)
            total += s.get("quantity") or 0
    return total, matched


def get_in_port_by_date(target_date, grade=None):
    """
    查询指定日期在港未通关的运单：实际到港日期 <= target_date 且 通关日期为空
    返回 (总数量, 匹配运单列表)
    """
    target = _str_to_date(target_date)
    if target is None:
        target = date.today()

    shipments = ds.get_all_shipments(limit=5000)
    matched = []
    total = 0.0
    for s in shipments:
        actual = _str_to_date(s.get("actual_arrival_date"))
        customs = _str_to_date(s.get("customs_clearance_date"))
        if actual and actual <= target and customs is None:
            if not _match_grade(s, grade):
                continue
            matched.append(s)
            total += s.get("quantity") or 0
    return total, matched


def get_total_shipments(grade=None):
    """
    查询系统中全部运单总量
    返回 (总数量, 匹配运单列表)
    """
    shipments = ds.get_all_shipments(limit=5000)
    matched = []
    total = 0.0
    for s in shipments:
        if not _match_grade(s, grade):
            continue
        matched.append(s)
        total += s.get("quantity") or 0
    return total, matched


def get_status_options():
    """获取带"全部"选项的状态列表"""
    return ["全部"] + SHIPMENT_STATUS_OPTIONS


def get_all_status_counts():
    """获取各状态的运单数量，用于仪表盘"""
    summary = ds.get_status_summary()
    return {s: summary.get(s, 0) for s in SHIPMENT_STATUS_OPTIONS}


def search_shipments(status=None, keyword="", page=1, page_size=20):
    """分页查询运单，每条数据附带热值分类"""
    offset = (page - 1) * page_size
    rows = ds.get_all_shipments(status=status, keyword=keyword, offset=offset, limit=page_size)
    total = ds.get_shipment_count(status=status, keyword=keyword)
    # 为每条运单添加热值分类
    for r in rows:
        cat, label = classify_calorific(r.get("calorific_value"))
        r["calorific_category"] = cat
    return rows, total


def get_delay_warnings():
    """
    逾期未到港预警：
    当前日期 > 调整到港日期 且 状态仍为'已下单'
    """
    all_shipments = ds.get_all_shipments(limit=500)
    today = date.today()
    warnings = []
    for s in all_shipments:
        adj_date = s.get("adjusted_arrival_date")
        if adj_date:
            if isinstance(adj_date, str):
                adj_date = date.fromisoformat(adj_date)
            if adj_date < today and s.get("status") == "已下单":
                delays = (today - adj_date).days
                cat, _ = classify_calorific(s.get("calorific_value"))
                warnings.append({
                    "id": s["id"],
                    "vessel_name": s.get("vessel_name", ""),
                    "supplier": s.get("supplier", ""),
                    "coal_type": s.get("coal_type", ""),
                    "discharge_port": s.get("discharge_port", ""),
                    "quantity": s.get("quantity", 0),
                    "calorific_value": s.get("calorific_value", 0),
                    "calorific_category": cat,
                    "sulfur_content": s.get("sulfur_content", ""),
                    "planned_arrival_date": s.get("planned_arrival_date", ""),
                    "adjusted_arrival_date": str(adj_date),
                    "actual_arrival_date": s.get("actual_arrival_date", ""),
                    "customs_clearance_date": s.get("customs_clearance_date", ""),
                    "discharge_complete_date": s.get("discharge_complete_date", ""),
                    "delay_days": delays,
                    "status": s.get("status", ""),
                })
    return warnings


def get_shipment_form_defaults():
    """返回新增运单表单的默认值"""
    return {
        "load_month": "",
        "supplier": "",
        "vessel_name": "",
        "arrive_load_port_date": None,
        "load_start_date": None,
        "load_end_date": None,
        "planned_arrival_date": None,
        "adjusted_arrival_date": None,
        "actual_arrival_date": None,
        "customs_clearance_date": None,
        "discharge_port": "",
        "coal_type": "",
        "sulfur_content": 0.0,
        "calorific_value": 0.0,
        "quantity": 0.0,
        "fob_price": 0.0,
        "freight_cost": 0.0,
        "standard_unit_price": 0.0,
        "status": "计划",
    }


# ==================== 日期逻辑校验 ====================

def _to_date(val):
    """将字符串或 date 对象统一转为 date"""
    from datetime import date as dt_date
    if val is None:
        return None
    if isinstance(val, dt_date):
        return val
    if isinstance(val, str) and val:
        try:
            return dt_date.fromisoformat(val)
        except ValueError:
            return None
    return None


def validate_shipment_dates(data: dict) -> list:
    """
    校验运单数据业务逻辑：
    1. 数量不能低于0
    2. 计划到港/实际到港/通关完成日期不能早于完货日期
    返回错误信息列表，空列表表示校验通过
    """
    errors = []
    from datetime import date as dt_date

    # 数量校验
    quantity = data.get("quantity")
    if quantity is not None and quantity < 0:
        errors.append("数量不能低于0")

    # 日期逻辑：计划到港/实际到港/通关时间 >= 完货日期
    load_end = _to_date(data.get("load_end_date"))
    if load_end is None:
        return errors  # 无完货日期则跳过日期逻辑校验

    date_checks = [
        ("planned_arrival_date", "计划到港日期"),
        ("actual_arrival_date", "实际到港日期"),
        ("customs_clearance_date", "通关完成日期"),
    ]
    for field, label in date_checks:
        val = _to_date(data.get(field))
        if val is not None and val < load_end:
            errors.append(f"{label}（{val}）不能早于完货日期（{load_end}）")

    return errors


def validate_import_rows(rows: list) -> list:
    """
    批量校验导入行，返回错误列表 [(index, error_msg), ...]
    """
    errors = []
    for i, row in enumerate(rows):
        row_errors = validate_shipment_dates(row)
        for e in row_errors:
            errors.append((i + 2, f"第 {i + 2} 行：{e}"))
    return errors


# ==================== 重复检测 ====================

def check_single_duplicate(data: dict):
    """
    检查单条运单是否与已有数据重复
    匹配条件：船名 + 计划到港日期 + 数量 三者同时相等
    返回: (is_dup: bool, existing_rows: list)
    """
    existing = ds.find_duplicate_shipments(
        data.get("vessel_name", ""),
        data.get("planned_arrival_date"),
        data.get("quantity", 0),
    )
    return len(existing) > 0, existing


def get_stats_by_status(status: str) -> dict:
    """
    获取指定状态运单的汇总统计。
    返回 { total_count, total_qty, high_qty, medium_qty, low_qty,
            supplier_count, avg_calorific, suppliers }
    """
    rows = ds.get_all_shipments(status=status, limit=10000)
    total_qty = sum((r.get("quantity") or 0) for r in rows)
    total_count = len(rows)

    high = sum((r.get("quantity") or 0) for r in rows
               if classify_calorific(r.get("calorific_value"))[0] == "高卡")
    medium = sum((r.get("quantity") or 0) for r in rows
                 if classify_calorific(r.get("calorific_value"))[0] == "中卡")
    low = sum((r.get("quantity") or 0) for r in rows
              if classify_calorific(r.get("calorific_value"))[0] == "低卡")

    suppliers = sorted({r.get("supplier", "") for r in rows if r.get("supplier")})
    avg_cal = sum((r.get("calorific_value") or 0) for r in rows) / total_count if total_count > 0 else 0

    return {
        "total_count": total_count,
        "total_qty": total_qty,
        "high_qty": high,
        "medium_qty": medium,
        "low_qty": low,
        "supplier_count": len(suppliers),
        "avg_calorific": round(avg_cal, 0),
        "suppliers": suppliers,
    }


# ==================== 自动状态归类 ====================

def auto_classify_shipment(data: dict) -> dict:
    """
    根据计划到港日期自动归类运单状态，会原地修改 data：
      计划到港日期 ≤ 今天  → '已下单'
      计划到港日期 > 今天 或 缺失 → '计划'
    返回修改后的 data（同时返回新状态方便调用方使用）
    """
    from datetime import date as dt_date
    today = dt_date.today()
    planned = _to_date(data.get("planned_arrival_date"))
    if planned is not None and planned <= today:
        data["status"] = "已下单"
    else:
        data["status"] = "计划"
    return data


def classify_batch(rows: list) -> tuple:
    """
    批量自动归类，返回 (已下单数量, 计划数量)
    """
    ordered = 0
    planned = 0
    for row in rows:
        auto_classify_shipment(row)
        if row.get("status") == "已下单":
            ordered += 1
        else:
            planned += 1
    return ordered, planned


def check_import_duplicates(rows: list) -> tuple:
    """
    批量检查导入数据中的重复项
    返回: (dup_new_list, dup_existing_list)
      dup_new_list: [(index, row_dict), ...]  待导入中的重复行
      dup_existing_list: [row_dict, ...]      数据库中匹配到的已有行
    """
    dup_new = []
    dup_existing = []

    for i, row in enumerate(rows):
        vessel = row.get("vessel_name", "")
        planned = row.get("planned_arrival_date", "")
        qty = row.get("quantity", 0)

        existing = ds.find_duplicate_shipments(vessel, planned, qty)
        if existing:
            dup_new.append((i, row))
            for ex in existing:
                if ex not in dup_existing:
                    dup_existing.append(ex)

    return dup_new, dup_existing
