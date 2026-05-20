"""
数据库连接管理（云开发版）
已迁移至 CloudBase 云数据库，不再依赖 MongoDB/Redis
"""

import logging

logger = logging.getLogger(__name__)

# 从 cloudbase_client 重新导出，保持向后兼容
from app.core.cloudbase_client import (
    CloudBaseClient,
    CloudBaseDatabase,
    CloudBaseCollection,
    cloudbase_client,
    init_db,
    close_db,
    get_mongo_db,
    get_mongo_client,
    get_database_health,
    set_task_progress,
    get_task_progress,
    check_and_increment_quota,
)

# 兼容性别名
init_database = init_db
close_database = close_db
get_redis_client = None  # Redis 已移除


def get_db():
    """获取数据库实例（简化别名）"""
    return get_mongo_db()
