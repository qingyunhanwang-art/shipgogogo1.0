"""
Excel 导入工具 — 解析运单 Excel，映射到18列
"""
import pandas as pd
from datetime import datetime, date


# 列名映射：Excel 列名 → DB 字段名
COLUMN_MAP = {
    "装货月份": "load_month",
    "供货方": "supplier",
    "船名": "vessel_name",
    "到装港日期": "arrive_load_port_date",
    "装货日期": "load_start_date",
    "完货日期": "load_end_date",
    "计划到港日期": "planned_arrival_date",
    "调整到港日期": "adjusted_arrival_date",
    "实际到港日期": "actual_arrival_date",
    "通关完成日期": "customs_clearance_date",
    "卸完日期": "discharge_complete_date",
    "卸货港": "discharge_port",
    "煤种": "coal_type",
    "硫份": "sulfur_content",
    "热值（大卡）": "calorific_value",
    "数量（万吨）": "quantity",
    "FOB价格": "fob_price",
    "海运费": "freight_cost",
    "标准单价": "standard_unit_price",
    "状态": "status",
}


def _parse_date(val):
    """安全解析日期"""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d") if hasattr(val, "strftime") else str(val)[:10]
    # 尝试解析字符串
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def parse_excel(file) -> list[dict]:
    """
    解析上传的 Excel 文件，返回运单数据列表
    """
    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception:
        df = pd.read_excel(file, engine="xlrd")  # 兼容旧 .xls

    # 列名清洗
    df.columns = [str(c).strip() for c in df.columns]

    # 兼容旧版列名 → 新列名（确保旧模板也能正常导入）
    _OLD_TO_NEW = {
        "数量": "数量（万吨）",
        "数量(万吨)": "数量（万吨）",
        "热值": "热值（大卡）",
        "热值(kcal/kg)": "热值（大卡）",
        "硫含量": "硫份",
        "运费": "海运费",
        "确认到港日期": "调整到港日期",
        "抵达装货港日期": "到装港日期",
        "装货开始日期": "装货日期",
        "装货完成日期": "完货日期",
    }
    for old, new in _OLD_TO_NEW.items():
        df.rename(columns={old: new}, inplace=True)

    # 列名映射
    reverse_map = {k: v for k, v in COLUMN_MAP.items()}
    df.rename(columns=reverse_map, inplace=True)

    rows = []
    db_fields = list(COLUMN_MAP.values())

    for _, row in df.iterrows():
        item = {"status": None}  # 默认无状态，由调用方按模块赋值
        for f in db_fields:
            if f in df.columns:
                val = row[f]
                if f.endswith("_date"):
                    item[f] = _parse_date(val)
                elif pd.isna(val):
                    item[f] = None
                else:
                    item[f] = val
        rows.append(item)

    return rows


def get_import_template_columns():
    """返回导入模板列名列表"""
    return list(COLUMN_MAP.keys())
