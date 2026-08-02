# 煤船快跑 · 扣子代码节点 · 日期校验与重复检测
# 仅用 Python 标准库。入口函数 main(rows, existing) -> 结构化结果
# rows: 待导入/新增行；existing: 库内已有运单（用于跨库去重）

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


def validate_shipment_dates(data):
    """返回错误信息列表，空表示通过。"""
    errs = []
    if _to_float(data.get("quantity")) < 0:
        errs.append("数量不能为负")
    load_end = _to_date(data.get("load_end_date"))
    for fld in ("planned_arrival_date", "actual_arrival_date", "customs_clearance_date"):
        d = _to_date(data.get(fld))
        if load_end and d and d < load_end:
            errs.append(f"{fld} 不能早于完货日期")
    return errs


def _dup(rows, vessel, planned, qty):
    for r in rows:
        if (str(r.get("vessel_name", "")).strip() == str(vessel).strip()
                and str(r.get("planned_arrival_date", "")).strip() == str(planned).strip()
                and _to_float(r.get("quantity")) == _to_float(qty)):
            return True
    return False


def main(rows, existing=None):
    existing = existing or []
    valid_rows, errors, dup_rows = [], [], []
    for idx, r in enumerate(rows):
        r = dict(r)
        msgs = validate_shipment_dates(r)
        is_dup = _dup(existing, r.get("vessel_name"), r.get("planned_arrival_date"), r.get("quantity")) \
            or _dup(valid_rows, r.get("vessel_name"), r.get("planned_arrival_date"), r.get("quantity"))
        if is_dup:
            msgs.append("与已有运单重复（船名+计划到港+数量）")
            dup_rows.append({"index": idx + 1, "vessel_name": r.get("vessel_name")})
        if msgs:
            errors.append({"index": idx + 1, "vessel_name": r.get("vessel_name"), "messages": msgs})
        else:
            valid_rows.append(r)
    return {
        "valid_rows": valid_rows,
        "errors": errors,
        "dup_rows": dup_rows,
        "valid_count": len(valid_rows),
        "error_count": len(errors),
    }
