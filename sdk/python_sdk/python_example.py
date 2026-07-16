"""
Lemon Kami Python SDK 使用示例
"""

from lemon_kami import LemonKamiSDK
import time


def main():
    # ==================== 配置信息 ====================
    # 请替换为您在后台创建的应用信息
    APP_ID = "your_app_id"  # 从后台管理获取
    APP_SECRET = "your_app_secret"  # 从后台管理获取
    SERVER_URL = "http://localhost:8000"  # 替换为您的服务地址
    
    # ==================== 初始化 SDK ====================
    print("=" * 60)
    print("Lemon Kami Python SDK 示例")
    print("=" * 60)
    
    sdk = LemonKamiSDK(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        server_url=SERVER_URL
    )
    
    print(f"设备指纹: {sdk.fingerprint[:32]}...")
    print()
    
    # ==================== 卡密验证 ====================
    print("【步骤1】验证卡密")
    KAMI_CODE = input("请输入卡密代码: ").strip()
    
    result = sdk.verify(KAMI_CODE)
    print(f"验证结果: {result}")
    
    if not result.get("success"):
        print(f"❌ 验证失败: {result.get('message')}")
        return
    
    print(f"✅ 验证成功！")
    print(f"   卡密类型: {result.get('kami_type')}")
    print(f"   到期时间: {result.get('expire_time')}")
    print()
    
    # ==================== 行为上报 ====================
    print("【步骤2】上报用户登录事件")
    report_result = sdk.report_event(
        kami_code=KAMI_CODE,
        event_type="login",
        extra_data={
            "username": "test_user",
            "login_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    )
    print(f"上报结果: {report_result}")
    print()
    
    # ==================== 心跳保持 ====================
    print("【步骤3】发送心跳（模拟每30秒一次）")
    for i in range(3):
        heartbeat_result = sdk.heartbeat(KAMI_CODE)
        print(f"  第 {i+1} 次心跳: {heartbeat_result}")
        if i < 2:  # 最后一次不等待
            time.sleep(2)  # 示例中缩短为2秒，实际应为30秒
    
    print()
    print("=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
