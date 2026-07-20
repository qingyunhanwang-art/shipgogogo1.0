"""
数据库初始化脚本 — 建表
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化所有数据表"""
    conn = get_connection()
    cur = conn.cursor()

    # ============ 运单台账表 ============
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shipment_ledger (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            load_month      TEXT,                -- 装货月份
            supplier        TEXT,                -- 供货方
            vessel_name     TEXT,                -- 船名
            arrive_load_port_date DATE,          -- 到装港日期
            load_start_date DATE,                -- 装货日期
            load_end_date   DATE,                -- 完货日期
            planned_arrival_date DATE,           -- 计划到港日期
            adjusted_arrival_date DATE,          -- 调整到港日期
            actual_arrival_date DATE,            -- 实际到港日期
            customs_clearance_date DATE,         -- 通关完成日期
            discharge_complete_date DATE,        -- 卸完日期
            discharge_port  TEXT,                -- 卸货港
            coal_type       TEXT,                -- 煤种
            sulfur_content  REAL,                -- 硫份(%)
            calorific_value REAL,                -- 热值（大卡）
            quantity        REAL,                -- 数量（万吨）
            fob_price       REAL,                -- FOB价格
            freight_cost    REAL,                -- 海运费
            standard_unit_price REAL,            -- 标准单价
            status          TEXT DEFAULT '计划', -- 运单状态（已下单/计划）
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 字段迁移：为旧表补充卸完日期列
    cur.execute("PRAGMA table_info(shipment_ledger)")
    shipment_cols = [c["name"] for c in cur.fetchall()]
    if "discharge_complete_date" not in shipment_cols:
        cur.execute("ALTER TABLE shipment_ledger ADD COLUMN discharge_complete_date DATE")

    # ============ 库存表（与运单一对一） ============
    # 先检查旧表结构是否需要迁移
    cur.execute("PRAGMA table_info(inventory_simple)")
    columns = [c["name"] for c in cur.fetchall()]
    if "shipment_id" not in columns:
        # 旧表没有 shipment_id，需要重建
        cur.execute("DROP TABLE IF EXISTS inventory_simple")
        cur.execute("DROP TABLE IF EXISTS inventory_txn")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_simple (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id     INTEGER UNIQUE NOT NULL,   -- 对应调运单ID，一一对应
            quantity        REAL DEFAULT 0,             -- 当前库存(万吨)
            safety_stock    REAL DEFAULT 0,             -- 安全库存(万吨)
            expiry_date     DATE,                       -- 效期
            remark          TEXT DEFAULT '',             -- 备注
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (shipment_id) REFERENCES shipment_ledger(id) ON DELETE CASCADE
        )
    """)

    # ============ 库存出入库记录 ============
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_txn (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id     INTEGER,                    -- 关联运单ID
            type            TEXT NOT NULL,               -- 入/出
            qty             REAL NOT NULL,               -- 数量（万吨）
            operator        TEXT DEFAULT '',             -- 操作人
            time            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remark          TEXT DEFAULT '',
            FOREIGN KEY (shipment_id) REFERENCES shipment_ledger(id) ON DELETE SET NULL
        )
    """)

    # ============ 首次初始化：库存为空但有运单时，按到港/卸完日期自动同步 ============
    cur.execute("SELECT COUNT(*) as cnt FROM inventory_simple")
    if cur.fetchone()["cnt"] == 0:
        cur.execute("SELECT COUNT(*) as cnt FROM shipment_ledger")
        shipment_cnt = cur.fetchone()["cnt"]
        if shipment_cnt > 0:
            cur.execute("""
                INSERT INTO inventory_simple (shipment_id, quantity)
                SELECT id, COALESCE(quantity, 0) FROM shipment_ledger
                WHERE (actual_arrival_date IS NOT NULL AND actual_arrival_date <= date('now'))
                   OR (discharge_complete_date IS NOT NULL AND discharge_complete_date <= date('now'))
            """)
            synced = cur.execute("SELECT COUNT(*) as cnt FROM inventory_simple").fetchone()["cnt"]
            print(f"库存初始化完成：已到港/卸完的运单 {synced} 条已同步（共 {shipment_cnt} 条运单）。")

    conn.commit()
    conn.close()
    print("数据库初始化完成。")


if __name__ == "__main__":
    init_db()
