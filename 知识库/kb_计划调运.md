# 知识库：计划调运（煤船快跑 · 燃料调运域）

> 用途：供 AI / 大模型在「计划调运」相关任务中检索规则与口径，包括运单录入、CSV 批量导入、运单查询与统计。
> 适用范围：火电厂进口煤船运单管理。合并到团队时，本知识库与数据库表 shipment_ledger 共同作为「计划调运」域的唯一真相源。
> 关联模块：库存管理、预警中心、AI 问答（均读 shipment_ledger）。

## 1. 业务概述
计划调运负责进口煤船运单的全生命周期：录入 → 导入 → 在途跟踪 → 到港 → 通关 → 卸货 → 入库存。
每条运单代表一艘船一批煤，核心字段为船名、计划到港日期、热值、数量。

## 2. 运单数据结构（表 shipment_ledger）
（21 个业务字段 + 平台自动 id；含 2 个派生字段 status / calorific_class）

| 字段(英文) | 中文名 | 类型 | 必填 | 规则与校验 |
|---|---|---|---|---|
| load_month | 装货月份 | 文本 | 否 | |
| supplier | 供货方 | 文本 | 否 | |
| vessel_name | 船名 | 文本 | 是 | 去重三要素之一 |
| arrive_load_port_date | 到装港日期 | 日期 | 否 | |
| load_start_date | 装货日期 | 日期 | 否 | |
| load_end_date | 完货日期 | 日期 | 否 | 后续多个日期不可早于它 |
| planned_arrival_date | 计划到港日期 | 日期 | 是 | 去重三要素之一；驱动 status 归类 |
| adjusted_arrival_date | 调整到港日期 | 日期 | 否 | 逾期预警依据 |
| actual_arrival_date | 实际到港日期 | 日期 | 否 | 入库存依据之一 |
| customs_clearance_date | 通关完成日期 | 日期 | 否 | |
| discharge_complete_date | 卸完日期 | 日期 | 否 | 入库存依据之一 |
| discharge_port | 卸货港 | 文本 | 否 | |
| coal_type | 煤种 | 文本 | 否 | |
| sulfur_content | 硫份 | 数字 | 否 | |
| calorific_value | 热值（大卡） | 数字 | 是 | 去重三要素之一；驱动 calorific_class |
| quantity | 数量（万吨） | 数字 | 是 | 去重三要素之一；≥0 |
| fob_price | FOB价格 | 数字 | 否 | |
| freight_cost | 海运费 | 数字 | 否 | |
| standard_unit_price | 标准单价 | 数字 | 否 | |
| status | 状态 | 文本(枚举) | 是 | 见规则 R2 |
| calorific_class | 热值分类 | 文本(派生) | 否 | 见规则 R1 |

## 3. 核心业务规则
R1 热值分类 calorific_class：
- calorific_value ≤ 4000 → 低卡
- 4000 < calorific_value < 5000 → 中卡
- calorific_value ≥ 5000 → 高卡
（实现：classify.py classify_calorific）

R2 状态自动归类 status：
- 若记录已带 status ∈ {已下单, 计划}，保留原值；
- 否则：planned_arrival_date ≤ 今天 → 已下单；否则 → 计划。
（实现：classify.py auto_classify_shipment）

R3 去重规则（写入前必检）：
vessel_name + planned_arrival_date + quantity 三者同时相等，视为重复运单，跳过不写入。

R4 日期校验（validate_shipment_dates）：
- quantity < 0 → 错误「数量不能为负」；
- planned_arrival_date / actual_arrival_date / customs_clearance_date 任一早于 load_end_date（完货日期）→ 错误「{字段} 不能早于完货日期」。
校验未通过的行不写入，进入错误明细。

R5 日期格式归一化：
支持 YYYY-MM-DD、YYYY/MM/DD、YYYY.MM.DD、YYYYMMDD；统一归一化为 YYYY-MM-DD。无法解析的保持原值交由校验报错。

## 4. 运单录入与批量导入
### 4.1 单条录入
输入：用户口语化描述（如「录入一条运单：神华轮，供货方神华，计划到港2026-08-01，热值4800，数量12万吨」）。
处理：大模型节点抽取为 JSON 字段（字段集见 4.3）→ 代码 classify 计算 calorific_class/status → 写 shipment_ledger。

### 4.2 批量导入（CSV）
输入：粘贴 CSV 全文，首行为中文表头，与 Excel 一致。
流程：csv_io（解析+映射）→ classify（归类）→ 数据库查 existing（去重）→ validate（校验+去重）→ 批量写 valid_rows。
CSV 中文表头 → 字段映射（共 19 列，含「状态」）：
装货月份→load_month, 供货方→supplier, 船名→vessel_name, 到装港日期→arrive_load_port_date, 装货日期→load_start_date, 完货日期→load_end_date, 计划到港日期→planned_arrival_date, 调整到港日期→adjusted_arrival_date, 实际到港日期→actual_arrival_date, 通关完成日期→customs_clearance_date, 卸完日期→discharge_complete_date, 卸货港→discharge_port, 煤种→coal_type, 硫份→sulfur_content, 热值（大卡）→calorific_value, 数量（万吨）→quantity, FOB价格→fob_price, 海运费→freight_cost, 标准单价→standard_unit_price, 状态→status

### 4.3 字段抽取 JSON 字段集（未知留空字符串；日期 YYYY-MM-DD；数量/热值/价格/硫份为数字或数字字符串）
load_month, supplier, vessel_name, arrive_load_port_date, load_start_date, load_end_date, planned_arrival_date, adjusted_arrival_date, actual_arrival_date, customs_clearance_date, discharge_complete_date, discharge_port, coal_type, sulfur_content, calorific_value, quantity, fob_price, freight_cost, standard_unit_price

### 4.4 录入工作流（cola_transport）
开始输入 text；选择器：text 含表头/换行为 CSV → 批量分支，否则单条分支。输出 inserted_count + 卡片（成功/重复/错误明细）。

## 5. 运单查询与统计口径（供 AI 问答、预警中心引用）
以 query_date（默认今天）与 grade（全部/高卡/中卡/低卡）为参数：
- 有效库存 effective_inventory：status=已下单 且 actual_arrival_date ≤ query_date 且 customs_clearance_date ≤ query_date 的数量之和。
- 某日到港量 arrived_qty：actual_arrival_date == query_date 的数量之和。
- 某日计划到港量 planned_qty：planned_arrival_date == query_date 的数量之和。
- 某日在途量 in_transit_qty：planned_arrival_date ≤ query_date 且（actual_arrival_date 为空 或 > query_date）的数量之和。
- 总运输量 total_transport：所有运单 quantity 之和。
- 逾期 delay：status=已下单 且 adjusted_arrival_date < 今天。
（实现：query.py main；逾期同时被预警中心使用 alerts.py）

## 6. 合并约定
- 表 shipment_ledger 为公共数据层，字段名/类型/枚举不可私自变更。
- 工作流命名建议 cola_transport；变量 snake_case；大模型节点仅输出 JSON。
- 若其他成员模块也写 shipment_ledger，去重（R3）天然覆盖，无需改本模块逻辑。
