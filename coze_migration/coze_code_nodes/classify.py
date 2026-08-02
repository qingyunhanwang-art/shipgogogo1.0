# 煤船快跑 · 扣子代码节点 · 热值分类与状态自动归类
# 仅用 Python 标准库。入口函数 main(rows) -> {"rows": [...]}
# 用法：把数据库读取的运单列表（或待导入行）传入，输出带 calorific_class 与 status 的行。

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
    if hasattr(v, "strftime"):  # 已是 date/datetime
        return v if hasattr(v, "year") and not hasattr(v, "hour") else v.date()
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def classify_calorific(calorific_value):
    """<=4000 低卡; 4000~5000 中卡; >5000 高卡。返回 (分类名, 标签)"""
    cv = _to_float(calorific_value)
    if cv <= 4000:
        return "低卡", "低"
    elif cv < 5000:
        return "中卡", "中"
    else:
        return "高卡", "高"


def auto_classify_shipment(data, auto=True):
    """按计划到港日期 <= 今天 置 '已下单'，否则 '计划'；已带状态则保留。"""
    if not auto:
        return data
    if data.get("status") in ("已下单", "计划"):
        return data
    from datetime import date
    planned = _to_date(data.get("planned_arrival_date"))
    if planned and planned <= date.today():
        data["status"] = "已下单"
    else:
        data["status"] = "计划"
    return data


def main(rows):
    out = []
    for r in rows:
        r = dict(r)  # 不污染入参
        cat, _ = classify_calorific(r.get("calorific_value"))
        r["calorific_class"] = cat
        auto_classify_shipment(r)
        out.append(r)
    return {"rows": out}
