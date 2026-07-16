"""
数据库迁移脚本：创建 app_authorizations 表
"""
import sys
sys.path.insert(0, '.')

from database import engine
from sqlalchemy import text

def migrate():
    """执行数据库迁移"""
    with engine.connect() as conn:
        # 检查表是否已存在
        result = conn.execute(text("SHOW TABLES LIKE 'app_authorizations'"))
        if not result.fetchone():
            print("创建 app_authorizations 表...")
            conn.execute(text("""
                CREATE TABLE app_authorizations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64) NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    granted_by VARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_app_id (app_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用授权表'
            """))
            conn.commit()
            print("表创建成功！")
        else:
            print("表已存在，跳过创建")

if __name__ == "__main__":
    migrate()
