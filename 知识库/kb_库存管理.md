# 知识库：库存管理（煤船快跑 · 燃料调运域）

> 用途：供 AI / 大模型在「库存管理」相关任务中检索规则与口径，包括库存同步、出入库、安全库存/效期、按热值分类统计。
> 适用范围：与 shipment_ledger 一对一关联的库存台账，及出入库流水。
> 关联模块：计划调运（提供运单）、预警中心（读取 safety_stock/expiry_date 生成低库存/效期预警）。

## 1. 业务概述
库存管理对「已到港/已卸完」的运单建立库存记录，支持同步、入库、出库、参数设置与统计。库存以「船（shipment_id）」为最小单位。

## 2. 库存数据结构
### 表 inventory_simple（库存，与运单一对一）
| 字段 | 中文名 | 类型 | 必填 | 规则 |
|---|---|---|---|---|
| shipment_id | 关联运单ID | 文本/数字 | 是 | 关联 shipment_ledger.id；一对一 |
| quantity | 库存数量（万吨） | 数字 | 是 | 初始=运单数量；随出入库变动，下限 0 |
| safety_stock | 安全库存（万吨） | 数字 | 否 | 默认 0；低于 safety_stock×0.8 触发低库存预警 |
| expiry_date | 效期 | 日期 | 否 | 距效期 ≤30 天触发效期预警 |
| remark | 备注 | 文本 | 否 | |

### 表 inventory_txn（出入库流水）
| 字段 | 中文名 | 类型 | 必填 | 规则 |
|---|---|---|---|---|
| shipment_id | 关联运单ID | 文本/数字 | 是 | 关联 shipment_ledger.id |
| type | 类型 | 文本(枚举) | 是 | 入 / 出 |
| qty | 数量（万吨） | 数字 | 是 | 本次出入库数量 |
| operator | 操作人 | 文本 | 否 | |
| time | 时间 | 日期 | 否 | 写入时赋值 YYYY-MM-DD |
| remark | 备注 | 文本 | 否 | |

## 3. 核心业务规则
R1 入库存标准（sync_filter）：仅当运单 actual_arrival_date ≤ 今天 或 discharge_complete_date ≤ 今天，才同步进 inventory_simple（初始 quantity=运单 quantity，shipment_id=运单 id）。其余运单不进库存。
R2 出入库计算（apply_txn）：新库存 = 入库时 quantity+qty；出库时 quantity−qty；结果不小于 0（取 max(新值,0)）。每次出入库同步写 inventory_txn（type=入/出, qty, time）。
R3 安全库存与低库存预警阈值：qty < safety_stock × 0.8（低于安全库存 80%）触发低库存预警。safety_stock 默认 0（=不预警），由 set_param 设置。
R4 效期与效期预警阈值：距 expiry_date ≤ 30 天触发效期预警；已过期为 error 级，未过期为 warning 级。expiry_date 为空不预警。
R5 热值分类库存统计（stats_by_calorific）：按 calorific_value 经热值分类规则（≤4000 低卡 / 4000~5000 中卡 / >5000 高卡）聚合 quantity 与条数，输出 高卡/中卡/低卡 三类的 qty 与 count。

## 4. 库存管理操作路由（cola_inventory）
开始输入 text（如「同步库存」「XX船入库5万吨」「设置XX船安全库存5」「按热值统计」）。
大模型节点判定 action（仅输出 JSON），枚举：
- sync：同步库存（从已到港运单）
- in：入库（需 shipment_id + qty）
- out：出库（需 shipment_id + qty）
- set_param：设置安全库存/效期（需 shipment_id + safety_stock 或 expiry_date）
- stats：按热值分类统计库存
- list：列出当前库存
各 action 处理：
- sync：查 shipment_ledger → inventory.sync_filter 得 sync_ids → 批量新增 inventory_simple。
- in/out：查 inventory_simple 得 quantity → inventory.apply_txn 算 new_quantity → 更新库存 + 写 inventory_txn。
- set_param：更新 inventory_simple 的 safety_stock / expiry_date。
- stats：JOIN inventory_simple + shipment_ledger 取 calorific_value → inventory.stats_by_calorific → 卡片。
- list：查全部库存 → 卡片。

## 5. 与预警中心的接口
预警中心（cola_alert）读取 inventory_simple 的 safety_stock / expiry_date 与 quantity，依据 R3/R4 生成「低库存」「效期」预警；本模块的库存参数（R3/R4 阈值）即预警的触发条件，二者共享同一张表，无需重复定义。

## 6. 合并约定
- inventory_simple / inventory_txn 为公共数据层，字段名/类型/枚举不可私自变更。
- 工作流命名建议 cola_inventory；变量 snake_case；代码节点仅标准库，不直连库。
- 若成员模块也读库存，复用同一张表即可，本模块逻辑无需改。
