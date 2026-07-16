"""
重置 admin 密码并测试日志记录
"""
import hashlib
import os
import requests

def hash_password(password: str) -> str:
    """生成密码哈希"""
    salt = os.urandom(32).hex()
    password_hash = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    return f"{salt}${password_hash}"

# 生成新密码哈希
new_password = "admin123"
password_hash = hash_password(new_password)

print(f"新密码哈希: {password_hash[:50]}...")

# 更新数据库
import subprocess
cmd = f'docker exec lemon_kami_mysql mysql -u root -proot_password_123 lemon_kami -e "UPDATE admin_users SET password_hash=\'{password_hash}\' WHERE username=\'admin\';"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(f"数据库更新结果: {result.stdout}")
if result.stderr:
    print(f"错误: {result.stderr}")

# 测试登录
print("\n测试登录...")
r = requests.post('http://localhost:8000/api/v1/admin/login', params={
    'username': 'admin',
    'password': 'admin123'
})

print(f"状态码: {r.status_code}")
if r.status_code == 200:
    print("✅ 登录成功！")
    data = r.json()
    print(f"Token: {data['token'][:50]}...")
    
    # 检查日志
    print("\n检查日志记录...")
    token = data['token']
    r_logs = requests.get('http://localhost:8000/api/v1/admin/event-logs', 
                          params={'token': token, 'page': 1, 'page_size': 5})
    if r_logs.status_code == 200:
        logs_data = r_logs.json()
        print(f"找到 {logs_data['total']} 条日志")
        if logs_data['data']:
            for log in logs_data['data'][:3]:
                print(f"  - [{log['created_at']}] {log['event_type']}: {log['message']}")
        else:
            print("  （暂无日志）")
else:
    print(f"❌ 登录失败: {r.text}")
