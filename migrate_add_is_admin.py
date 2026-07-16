"""
数据库迁移脚本：为 admin_users 表添加 is_admin 字段
"""
import sys
sys.path.insert(0, '.')

from database import engine
from sqlalchemy import text

def migrate():
    """执行数据库迁移"""
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("SHOW COLUMNS FROM admin_users LIKE 'is_admin'"))
        if not result.fetchone():
            print("添加 is_admin 字段到 admin_users 表...")
            conn.execute(text("""
                ALTER TABLE admin_users 
                ADD COLUMN is_admin BOOLEAN DEFAULT FALSE COMMENT '是否为超级管理员'
            """))
            conn.commit()
            
            # 将第一个用户设置为 admin（如果存在）
            result = conn.execute(text("SELECT id FROM admin_users ORDER BY id ASC LIMIT 1"))
            first_user = result.fetchone()
            if first_user:
                conn.execute(text("UPDATE admin_users SET is_admin = TRUE WHERE id = :user_id"), {"user_id": first_user[0]})
                conn.commit()
                print("已将第一个用户设置为管理员")
            
            print("字段添加成功！")
        else:
            print("字段已存在，跳过添加")

if __name__ == "__main__":
    migrate()
