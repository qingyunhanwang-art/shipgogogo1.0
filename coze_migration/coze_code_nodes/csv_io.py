# 煤船快跑 · 扣子代码节点 · 批量导入 CSV 解析
# 仅用 Python 标准库。入口函数 main(csv_text) -> {"rows": [dict,...]}
# 输入：用户粘贴的 CSV 文本，首行为中文表头（与 Excel 一致）。
# 输出：已映射到 DB 字段、日期/数值已规整的待导入行。

import csv
import io

# Excel 中文表头 -> DB 字段（与 utils/excel_io.py 的 COLUMN_MAP 完全一致）
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

_DATE_FIELDS = {v for k, v in COLUMN_MAP.items() if k.endswith("日期")}


def _parse_date_str(val):
    from datetime import datetime
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # 无法解析则原样返回，交由校验节点报错


def main(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text or ""))
    rows = []
    for raw in reader:
        item = {}
        for zh, fld in COLUMN_MAP.items():
            val = raw.get(zh)
            if val is None or str(val).strip() == "":
                item[fld] = None
            elif fld in _DATE_FIELDS:
                item[fld] = _parse_date_str(val)
            else:
                item[fld] = str(val).strip()
        rows.append(item)
    return {"rows": rows}
