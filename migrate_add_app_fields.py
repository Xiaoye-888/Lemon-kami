"""
数据库迁移脚本：为 apps 表添加 created_by 和 created_at 字段
"""
import sys
sys.path.insert(0, '.')

from database import engine
from sqlalchemy import text

def migrate():
    """执行数据库迁移"""
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("SHOW COLUMNS FROM apps LIKE 'created_by'"))
        if not result.fetchone():
            print("添加 created_by 字段...")
            conn.execute(text("ALTER TABLE apps ADD COLUMN created_by VARCHAR(255) DEFAULT NULL COMMENT '创建人用户名'"))
        
        result = conn.execute(text("SHOW COLUMNS FROM apps LIKE 'created_at'"))
        if not result.fetchone():
            print("添加 created_at 字段...")
            conn.execute(text("ALTER TABLE apps ADD COLUMN created_at DATETIME DEFAULT NULL COMMENT '创建时间'"))
        
        conn.commit()
        print("数据库迁移完成！")

if __name__ == "__main__":
    migrate()
