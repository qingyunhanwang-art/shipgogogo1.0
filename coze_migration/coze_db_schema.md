# 扣子数据库表结构（coze_db_schema）

> 在扣子「数据库」中新建以下 3 张表。扣子会自动为每张表生成 `id`（主键，自增）。
> 字段类型说明：文本 / 数字（整数或小数）/ 日期（格式 `YYYY-MM-DD`）。
> 本结构 1:1 对应原 `db/init_db.py`，保留「运单 ↔ 库存」以 `shipment_id` 关联的一对一关系。

---

## 表 1：`shipment_ledger`（运单台账）

| 字段(英文) | 中文名（Excel 表头） | 类型 | 必填 | 说明 / 校验 |
|---|---|---|---|---|
| `load_month` | 装货月份 | 文本 | 否 | 装货年月 |
| `supplier` | 供货方 | 文本 | 否 | |
| `vessel_name` | 船名 | 文本 | 是 | 去重三要素之一 |
| `arrive_load_port_date` | 到装港日期 | 日期 | 否 | |
| `load_start_date` | 装货日期 | 日期 | 否 | |
| `load_end_date` | 完货日期 | 日期 | 否 | 后续日期不可早于它 |
| `planned_arrival_date` | 计划到港日期 | 日期 | 是 | 去重三要素之一；≤今天→状态自动置「已下单」 |
| `adjusted_arrival_date` | 调整到港日期 | 日期 | 否 | 逾期预警依据 |
| `actual_arrival_date` | 实际到港日期 | 日期 | 否 | |
| `customs_clearance_date` | 通关完成日期 | 日期 | 否 | |
| `discharge_complete_date` | 卸完日期 | 日期 | 否 | 入库存标准之一 |
| `discharge_port` | 卸货港 | 文本 | 否 | |
| `coal_type` | 煤种 | 文本 | 否 | |
| `sulfur_content` | 硫份 | 数字 | 否 | |
| `calorific_value` | 热值（大卡） | 数字 | 是 | 去重三要素之一；驱动热值分类 |
| `quantity` | 数量（万吨） | 数字 | 是 | 去重三要素之一；≥0 |
| `fob_price` | FOB价格 | 数字 | 否 | |
| `freight_cost` | 海运费 | 数字 | 否 | |
| `standard_unit_price` | 标准单价 | 数字 | 否 | |
| `status` | 状态 | 文本(枚举) | 是 | 取值：`已下单` / `计划`（由代码节点自动归类） |
| `calorific_class` | 热值分类 | 文本(派生) | 否 | 取值：`低卡`(≤4000) / `中卡`(4000~5000) / `高卡`(>5000)，写入时由代码节点计算 |

**去重规则**：`vessel_name` + `planned_arrival_date` + `quantity` 三者同时相等视为重复。
**状态自动归类**：`planned_arrival_date ≤ 今天` → `已下单`；否则 → `计划`（Excel 已带状态则保留原值）。

---

## 表 2：`inventory_simple`（库存，与运单一对一）

| 字段(英文) | 中文名 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shipment_id` | 关联运单ID | 文本/数字 | 是 | 关联 `shipment_id`；与 `shipment_ledger` 一对一 |
| `quantity` | 库存数量（万吨） | 数字 | 是 | 初始=运单数量；随出入库变动 |
| `safety_stock` | 安全库存（万吨） | 数字 | 否 | 默认 0；低于 `安全库存×0.8` 触发低库存预警 |
| `expiry_date` | 效期 | 日期 | 否 | 距效期 ≤30 天触发效期预警 |
| `remark` | 备注 | 文本 | 否 | |

**入库存标准**：`actual_arrival_date ≤ 今天` 或 `discharge_complete_date ≤ 今天` 的运单才同步进库存。

---

## 表 3：`inventory_txn`（出入库记录）

| 字段(英文) | 中文名 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `shipment_id` | 关联运单ID | 文本/数字 | 是 | 关联 `shipment_id` |
| `type` | 类型 | 文本(枚举) | 是 | 取值：`入` / `出` |
| `qty` | 数量（万吨） | 数字 | 是 | 本次出入库数量 |
| `operator` | 操作人 | 文本 | 否 | |
| `time` | 时间 | 日期 | 否 | 由写入时赋值 `YYYY-MM-DD` |
| `remark` | 备注 | 文本 | 否 | |

---

## 建表步骤（扣子后台）

1. 进入智能体 → 左侧「数据库」→ 新建数据表。
2. 依次创建 `shipment_ledger` / `inventory_simple` / `inventory_txn`，按上表加字段。
3. 字段类型：日期字段选「日期」，数量/价格/热值选「数字」，其余选「文本」。
4. `status` 可设为文本，"枚举值"填写 `已下单,计划`；`calorific_class` 枚举填 `低卡,中卡,高卡`。
5. 暂不勾选「仅智能体可读写」（调试期可在数据管理中直接查看）。

---

## 测试数据导入

测试 Excel 由你自行通过「调运录入工作流 / 批量导入」灌入（详见 `扣子_煤船快跑_搭建方案.md`）。
Excel 列顺序即 `COLUMN_MAP` 中的 19 个中文表头（含「状态」列），见 `coze_code_nodes/csv_io.py`。
