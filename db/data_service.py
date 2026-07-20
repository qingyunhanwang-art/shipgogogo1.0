"""
数据服务层 — 封装所有数据库操作，后续可替换为 ERP 接口
"""
from db.init_db import get_connection


# ==================== 运单台账 ====================

def get_all_shipments(status=None, keyword="", offset=0, limit=100):
    """查询运单列表（支持状态筛选和关键词搜索）"""
    conn = get_connection()
    conditions = []
    params = []

    if status and status != "全部":
        conditions.append("status = ?")
        params.append(status)
    if keyword:
        conditions.append("""
            (supplier LIKE ? OR vessel_name LIKE ? OR discharge_port LIKE ? OR coal_type LIKE ?)
        """)
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM shipment_ledger{where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shipment_count(status=None, keyword=""):
    """查询运单数量"""
    conn = get_connection()
    conditions = []
    params = []
    if status and status != "全部":
        conditions.append("status = ?")
        params.append(status)
    if keyword:
        conditions.append(
            "(supplier LIKE ? OR vessel_name LIKE ? OR discharge_port LIKE ? OR coal_type LIKE ?)"
        )
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM shipment_ledger{where}", params).fetchone()
    conn.close()
    return row["cnt"]


def get_shipment_by_id(shipment_id):
    """按ID获取单条运单"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM shipment_ledger WHERE id = ?", (shipment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_shipment(data: dict):
    """新增运单"""
    conn = get_connection()
    fields = [
        "load_month", "supplier", "vessel_name", "arrive_load_port_date",
        "load_start_date", "load_end_date", "planned_arrival_date",
        "adjusted_arrival_date", "actual_arrival_date", "customs_clearance_date",
        "discharge_complete_date",
        "discharge_port", "coal_type", "sulfur_content", "calorific_value",
        "quantity", "fob_price", "freight_cost", "standard_unit_price", "status"
    ]
    placeholders = ", ".join(["?"] * len(fields))
    cols = ", ".join(fields)
    vals = [data.get(f, None) for f in fields]
    conn.execute(f"INSERT INTO shipment_ledger ({cols}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()


def update_shipment(shipment_id, data: dict):
    """更新运单（部分更新）"""
    if not data:
        return
    conn = get_connection()
    sets = ", ".join([f"{k} = ?" for k in data.keys()])
    vals = list(data.values()) + [shipment_id]
    conn.execute(f"UPDATE shipment_ledger SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
    conn.commit()
    conn.close()


def update_shipment_status(shipment_id, new_status):
    """快捷更新运单状态"""
    conn = get_connection()
    conn.execute(
        "UPDATE shipment_ledger SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, shipment_id)
    )
    conn.commit()
    conn.close()


def delete_shipment(shipment_id):
    """删除运单"""
    conn = get_connection()
    conn.execute("DELETE FROM shipment_ledger WHERE id = ?", (shipment_id,))
    conn.commit()
    conn.close()


def bulk_delete_shipments(ids: list[int]):
    """批量删除运单，返回实际删除条数"""
    if not ids:
        return 0
    conn = get_connection()
    placeholders = ",".join(["?"] * len(ids))
    conn.execute(f"DELETE FROM shipment_ledger WHERE id IN ({placeholders})", ids)
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    return deleted


def bulk_import_shipments(rows: list[dict]):
    """批量导入运单"""
    conn = get_connection()
    fields = [
        "load_month", "supplier", "vessel_name", "arrive_load_port_date",
        "load_start_date", "load_end_date", "planned_arrival_date",
        "adjusted_arrival_date", "actual_arrival_date", "customs_clearance_date",
        "discharge_complete_date",
        "discharge_port", "coal_type", "sulfur_content", "calorific_value",
        "quantity", "fob_price", "freight_cost", "standard_unit_price", "status"
    ]
    placeholders = ", ".join(["?"] * len(fields))
    cols = ", ".join(fields)
    batch = []
    for r in rows:
        batch.append([r.get(f, None) for f in fields])
    conn.executemany(f"INSERT INTO shipment_ledger ({cols}) VALUES ({placeholders})", batch)
    conn.commit()
    conn.close()


# ==================== 库存（与运单一对一） ====================

def clear_and_sync_inventory():
    """清空库存后，从调运单导入已到港/已卸完的运单（一一对应）
    入库标准：实际到港日期 ≤ 今日  OR  卸完日期 ≤ 今日"""
    conn = get_connection()
    conn.execute("DELETE FROM inventory_simple")
    conn.execute("DELETE FROM inventory_txn")
    conn.execute("""
        INSERT INTO inventory_simple (shipment_id, quantity)
        SELECT id, COALESCE(quantity, 0) FROM shipment_ledger
        WHERE (actual_arrival_date IS NOT NULL AND actual_arrival_date <= date('now'))
           OR (discharge_complete_date IS NOT NULL AND discharge_complete_date <= date('now'))
    """)
    conn.commit()
    synced = conn.execute("SELECT COUNT(*) as cnt FROM inventory_simple").fetchone()["cnt"]
    not_synced = conn.execute("""
        SELECT COUNT(*) as cnt FROM shipment_ledger
        WHERE NOT (
            (actual_arrival_date IS NOT NULL AND actual_arrival_date <= date('now'))
            OR (discharge_complete_date IS NOT NULL AND discharge_complete_date <= date('now'))
        )
    """).fetchone()["cnt"]
    conn.close()
    return synced, not_synced


def get_all_inventory():
    """获取所有库存（JOIN 调运单完整信息）"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*,
               inv.id          AS inventory_id,
               inv.quantity    AS inventory_quantity,
               inv.safety_stock,
               inv.expiry_date AS inventory_expiry_date,
               inv.remark      AS inventory_remark,
               inv.updated_at  AS inventory_updated_at
        FROM inventory_simple inv
        JOIN shipment_ledger s ON inv.shipment_id = s.id
        ORDER BY s.planned_arrival_date DESC, s.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inventory_by_shipment(shipment_id):
    """根据运单ID获取对应库存"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM inventory_simple WHERE shipment_id = ?", (shipment_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_inventory_by_shipment(shipment_id, quantity=None, safety_stock=None,
                                  expiry_date=None, remark=None):
    """更新某条运单对应的库存（不存则自动创建）"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM inventory_simple WHERE shipment_id = ?", (shipment_id,)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO inventory_simple (shipment_id, quantity, safety_stock) VALUES (?, 0, 0)",
            (shipment_id,)
        )
        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        inv_id = row["id"]

    updates = {}
    if quantity is not None:
        updates["quantity"] = quantity
    if safety_stock is not None:
        updates["safety_stock"] = safety_stock
    if expiry_date is not None:
        updates["expiry_date"] = expiry_date
    if remark is not None:
        updates["remark"] = remark

    if updates:
        set_clause = ", ".join([f"{k}=?" for k in updates])
        values = list(updates.values()) + [inv_id]
        conn.execute(
            f"UPDATE inventory_simple SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            values
        )
        conn.commit()
    conn.close()


def clear_empty_inventory():
    """一键清除库存数量为 0 的空库存单"""
    conn = get_connection()
    # 先删关联的出入库记录
    conn.execute("""
        DELETE FROM inventory_txn
        WHERE shipment_id IN (
            SELECT shipment_id FROM inventory_simple
            WHERE quantity = 0 OR quantity IS NULL
        )
    """)
    # 再删空库存记录
    conn.execute("""
        DELETE FROM inventory_simple
        WHERE quantity = 0 OR quantity IS NULL
    """)
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return deleted


# ==================== 出入库记录 ====================

def add_inventory_txn(shipment_id, txn_type, qty, operator="", remark=""):
    """新增出入库记录，同时更新对应运单的库存"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO inventory_txn (shipment_id, type, qty, operator, remark) VALUES (?,?,?,?,?)",
        (shipment_id, txn_type, qty, operator, remark)
    )
    # 更新对应运单的库存
    row = conn.execute(
        "SELECT id, quantity FROM inventory_simple WHERE shipment_id = ?", (shipment_id,)
    ).fetchone()
    if row:
        new_qty = row["quantity"] + qty if txn_type == "入" else row["quantity"] - qty
        conn.execute(
            "UPDATE inventory_simple SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (max(new_qty, 0), row["id"])
        )
    else:
        # 还没有库存记录时先创建
        init_qty = max(qty, 0) if txn_type == "入" else 0
        conn.execute(
            "INSERT INTO inventory_simple (shipment_id, quantity, safety_stock) VALUES (?, ?, 0)",
            (shipment_id, init_qty)
        )
    conn.commit()
    conn.close()


def get_inventory_txns(shipment_id=None, limit=50):
    """获取出入库记录，可筛选运单"""
    conn = get_connection()
    if shipment_id:
        rows = conn.execute(
            "SELECT * FROM inventory_txn WHERE shipment_id = ? ORDER BY time DESC LIMIT ?",
            (shipment_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM inventory_txn ORDER BY time DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 统计 ====================

def get_status_summary():
    """各状态运单数量统计"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM shipment_ledger GROUP BY status"
    ).fetchall()
    conn.close()
    return {r["status"]: r["cnt"] for r in rows}


def get_total_inventory():
    """当前总库存(万吨)——汇总所有运单的 inventory_quantity"""
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) as total FROM inventory_simple"
    ).fetchone()
    conn.close()
    return row["total"] if row else 0


def find_duplicate_shipments(vessel_name: str, planned_arrival_date, quantity):
    """
    根据船名+计划到港日期+数量查找重复运单（三条件同时满足）
    返回匹配的已有运单列表，空列表表示无重复
    """
    if not vessel_name or planned_arrival_date is None or quantity is None:
        return []
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, vessel_name, supplier, coal_type, quantity, calorific_value,
                  planned_arrival_date, adjusted_arrival_date, status, discharge_port,
                  load_month, fob_price, freight_cost, standard_unit_price
           FROM shipment_ledger
           WHERE vessel_name = ? AND planned_arrival_date = ? AND quantity = ?""",
        (vessel_name, str(planned_arrival_date), quantity)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_arrived_quantity():
    """
    获取已下单运单的总数量（万吨）
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) as total FROM shipment_ledger WHERE status = '已下单'"
    ).fetchone()
    conn.close()
    return row["total"] if row else 0
