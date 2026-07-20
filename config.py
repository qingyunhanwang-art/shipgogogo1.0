"""
全局配置文件
"""
import os

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key-here")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "raw_material.db")

# 运单状态选项（管理=已下单 / 计划=计划）
SHIPMENT_STATUS_OPTIONS = ["已下单", "计划"]

# 预警阈值
LOW_STOCK_RATIO = 0.2          # 库存低于安全库存的20%时预警
EXPIRE_WARNING_DAYS = 30       # 距效期不足30天预警
