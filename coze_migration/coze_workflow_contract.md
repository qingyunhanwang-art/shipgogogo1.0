# 煤船快跑 · 工作流接口契约与合并约定（coze_workflow_contract）

> 文档定位：本项目的交付单元是 **4 条独立工作流**，不是完整智能体包装。
> 每条工作流都有**明确的输入/输出变量契约**，便于将来与小组成员的工作流合并到同一个智能体/工作流编排里。
> 合并时，本文件即为「模块接口说明书」；数据库表为「公共数据层接口」。

---

## 0. 合并总体约定（先读这段）

1. **公共数据层 = 3 张扣子数据库表**（`shipment_ledger` / `inventory_simple` / `inventory_txn`）。
   这是跨工作流、跨成员共享的唯一真相源。合并时**表名、字段名、字段类型必须对齐**（见 `coze_db_schema.md`），字段变动需全员同步。
2. **工作流命名规范**：建议统一前缀或语义化英文名，避免与成员冲突，例如：
   `cola_qa`（问答）/`cola_transport`（录入）/`cola_inventory`（库存）/`cola_alert`（预警）。
3. **变量命名规范**：输入/输出变量统一 `snake_case`，语义自解释；大模型节点统一只输出 **JSON**，由选择器/代码节点解析。
4. **代码节点约束**：仅用 Python 标准库；入参全部来自上游变量，出参全部为变量；不直连数据库。
5. **职责边界**：本模块只管「燃料调运」域。合并时的总路由（用户一句话分流到谁的工作流）由总调度方负责——本模块暴露的工作流可被直接被「总调度工作流/智能体人设」以相同输入变量调用。

---

## 1. 工作流总览

| 工作流（建议名） | 英文名 | 触发意图 | 输入变量 | 核心输出 |
|---|---|---|---|---|
| 调运录入 | `cola_transport` | 录入/导入运单 | `text` | `inserted_count` / `card` |
| 库存管理 | `cola_inventory` | 同步/出入库/看库存 | `text` | `card` / `result` |
| 预警中心 | `cola_alert` | 查看预警 | （无/可选 `query`） | `card` |
| AI 问答 | `cola_qa` | 库存/在途/到港/逾期等查询 | `query` | `answer` / `card` |

---

## 2. 工作流接口契约（逐条）

### 2.1 调运录入 `cola_transport`

**输入**
- `text` (文本)：单条口语化描述，或「批量导入」时粘贴的 CSV 全文（需含表头）。

**内部节点链**
```
开始(text)
 ├─ [批量判定] 选择器：text 含换行或表头 → csv_io 分支；否则 → 单条分支
 │   ├─ csv_io 分支：代码 csv_io.main(csv_text) → {rows, errors}
 │   │      → 代码 classify.main(rows) → {rows}
 │   │      → 数据库「查询 shipment_ledger(全部)」→ existing
 │   │      → 代码 validate.main(rows, existing) → {valid_rows, errors, dup_rows}
 │   │      → 数据库「批量新增 shipment_ledger」(valid_rows) → inserted_count
 │   └─ 单条分支：大模型(字段抽取, 提示词四) → 代码 classify.main([row]) → 数据库新增
 └─ 卡片(模板B：导入结果/重复提示) → 结束
```

**依赖代码节点 / main 签名**
- `csv_io.py`：`main(csv_text)` → `{"rows":[...], "errors":[...]}`
- `classify.py`：`main(rows)` → `{"rows":[...]}`（含 `calorific_class`、`status` 自动归类）
- `validate.py`：`main(rows, existing=None)` → `{"valid_rows":[...], "errors":[...], "dup_rows":[...]}`

**输出**
- `inserted_count` (数字)
- `card` (卡片所需结构化数据：成功数、重复数、错误明细)

**合并注意**：批量导入依赖「数据库查询全部 existing」做去重；合并后若其他成员也写 `shipment_ledger`，去重逻辑天然覆盖，无需额外改动。

---

### 2.2 库存管理 `cola_inventory`

**输入**
- `text` (文本)：如「同步库存」「煤船1 入库 3 万吨」「设置煤船2 安全库存 5」「按热值统计」。

**内部节点链**
```
开始(text)
 → 大模型(操作路由, 提示词五) → {action}
 → 选择器(action): sync / in / out / set_param / stats / list
     sync:    数据库查 shipment_ledger → 代码 inventory.main(shipments, action="sync") → 写 inventory_simple
     in/out:  数据库查 + 代码 inventory.main(..., action="txn", txn_type, qty) → 写 inventory_simple + inventory_txn
     set_param: 代码 inventory.main(action="set_param") → 更新 inventory_simple
     stats:   数据库查 inventory_simple + shipment_ledger → 代码 inventory.main(action="stats") → 卡片
     list:    数据库查 inventory_simple → 卡片
 → 卡片(模板C) → 结束
```

**依赖代码节点 / main 签名**
- `inventory.py`：
  `main(shipments=None, inv_rows=None, quantity=None, qty=None, txn_type=None, action="stats")`
  返回随 `action` 不同：`sync`→`{"sync_ids":[...]}`；`txn`→`{"new_quantity":...}`；`stats`→`{"by_class":{...},"total":...}`。

**输出**
- `card`（统计卡 / 结果卡）
- `result`（可选：操作结果文本）

**合并注意**：库存动作全部围绕 `inventory_simple`/`inventory_txn`；若成员模块也读库存，共享同一张表即可。

---

### 2.3 预警中心 `cola_alert`

**输入**
- 无（或可选 `query` 文本，用于「只看逾期」等过滤，本期可留空）。

**内部节点链**
```
开始(无)
 → 数据库查 shipment_ledger → shipments
 → 数据库查 inventory_simple → inventory
 → 代码 alerts.main(shipments, inventory)
 → 卡片(模板D：三类预警 + 统计概览) → 结束
```

**依赖代码节点 / main 签名**
- `alerts.py`：`main(shipments, inventory)` →
  `{"delay":[...], "low_stock":[...], "expiry":[...], "total_count":N, "by_level":{...}}`

**输出**
- `card`（预警列表 + 等级统计）

**合并注意**：纯只读、无副作用，最适合被其他模块「嵌入调用」或定时触发。

---

### 2.4 AI 问答 `cola_qa`

**输入**
- `query` (文本)：用户自然语言问题。

**内部节点链**
```
开始(query)
 → 大模型(意图识别, 提示词二) → {intent, date_str, grade, need_detail}
 → 选择器(intent): 精确类(库存/到港/在途/逾期/热值/运单) / 通用
     精确类: 数据库查 shipment_ledger → 代码 qa.main(query) 取 date_str/grade
             → 代码 query.main(rows, query_date, grade) → 卡片(模板A) → 结束
     通用类: 数据库查 shipment_ledger + inventory_simple → 代码 qa.main(query) 拼 context
             → 大模型(通用问答, 提示词三) → answer → 结束
```

**依赖代码节点 / main 签名**
- `qa.py`：`main(question)` → `{"date_str":..., "grade":..., "context":...}`（精确/通用共用，按分支取所需字段）
- `query.py`：`main(rows, query_date, grade="全部")` →
  `{"effective_inventory":..., "arrived":..., "in_transit":..., "delay_count":..., "by_class":{...}}`

**输出**
- 精确类：`card`（含 `effective_inventory` 等结构化字段）
- 通用类：`answer` (文本)

**合并注意**：问答是「只读 + 大模型生成」模块，最安全；若成员有其它域知识，问答路由可在总调度处扩展 `intent` 枚举后分流。

---

## 3. 公共数据层接口（合并关键）

合并时，3 张表的 schema 即团队契约，定义在 `coze_db_schema.md`：

- `shipment_ledger`：运单台账（21 字段，含派生 `status`/`calorific_class`）
- `inventory_simple`：库存（5 字段，`shipment_id` 一对一关联）
- `inventory_txn`：出入库流水（6 字段）

字段英文名、类型、枚举值**不可私自变更**；新增字段需通知合并方并同步到所有读写该表的工作流。

---

## 4. 代码节点复用表（合并时直接整文件粘贴）

| 文件 | 入口 | 用途 | 被哪些工作流调用 |
|---|---|---|---|
| `csv_io.py` | `main(csv_text)` | CSV 解析 | 调运录入 |
| `classify.py` | `main(rows)` | 热值分类+状态归类 | 调运录入 |
| `validate.py` | `main(rows, existing)` | 日期校验+去重 | 调运录入 |
| `inventory.py` | `main(..., action)` | 同步/出入库/统计 | 库存管理 |
| `alerts.py` | `main(shipments, inventory)` | 三类预警 | 预警中心 |
| `query.py` | `main(rows, query_date, grade)` | 精确聚合 | AI 问答 |
| `qa.py` | `main(question)` | 日期解析/上下文拼装 | AI 问答 |

所有脚本仅标准库，`py_compile` 与逻辑冒烟测试已通过。

---

## 5. 合并落地建议

1. **各自先把 4 条工作流建好、自测通过**（按 `扣子_煤船快跑_搭建方案.md`）。
2. 合并时**先对齐数据库表**：把 3 张表在团队空间建好，所有人引用同一份 schema。
3. 工作流命名加前缀（如 `cola_*`），避免与成员重名。
4. 由总调度方（人或单独「总路由工作流」）按意图把用户输入分发到各模块工作流——本模块 4 条工作流输入变量固定（`text` / `query`），可直接被调用。
5. 若成员的模块也读写「库存/运单」，复用同一张表即可，无需改本模块逻辑。
