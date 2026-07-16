"""
快速重置管理员密码为 admin123
"""
import subprocess
import sys

def reset_admin_password():
    """重置 admin 用户密码为 admin123"""
    
    print("=" * 60)
    print("重置管理员密码")
    print("=" * 60)
    
    # 使用 Python 生成新的密码哈希
    import hashlib
    import os
    
    new_password = "admin123"
    salt = os.urandom(32).hex()
    password_hash = hashlib.sha256((new_password + salt).encode('utf-8')).hexdigest()
    full_hash = f"{salt}${password_hash}"
    
    print(f"\n新密码: {new_password}")
    print(f"正在更新数据库...")
    
    # 执行 SQL 更新命令
    cmd = [
        'docker', 'exec', 'lemon_kami_mysql',
        'mysql', '-u', 'root', '-proot_password_123',
        'lemon_kami',
        '-e', f"UPDATE admin_users SET password_hash='{full_hash}' WHERE username='admin';"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print("✅ 密码重置成功！")
            print("\n登录信息：")
            print(f"  用户名: admin")
            print(f"  密码: {new_password}")
            print(f"  地址: http://localhost:3001")
            print("\n请立即登录并修改密码！")
        else:
            print(f"❌ 更新失败: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 执行失败: {e}")
        print(f"错误信息: {e.stderr}")
        print("\n请确保 Docker 容器正在运行：")
        print("  docker compose ps")
    except FileNotFoundError:
        print("❌ 未找到 docker 命令，请确保已安装 Docker")
        sys.exit(1)

if __name__ == "__main__":
    reset_admin_password()
