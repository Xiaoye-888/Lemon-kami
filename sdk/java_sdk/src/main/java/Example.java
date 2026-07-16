import com.lemon.kami.LemonKamiSDK;

import java.util.HashMap;
import java.util.Map;

/**
 * Lemon Kami Java SDK 使用示例
 */
public class Example {
    static String kami = "C4J7Z4WSWH0JA1JR";
    
    public static void main(String[] args) {
        // 初始化 SDK
        LemonKamiSDK sdk = new LemonKamiSDK(
            "your_app_id",           // 替换为你的 app_id
            "your_app_secret",       // 替换为你的 app_secret
            "http://localhost:8000"  // 服务器地址
        );
        
        System.out.println("=== Lemon Kami Java SDK 示例 ===\n");
        
        // 1. 验证卡密
        testVerify(sdk);
        
        // 2. 上报事件
        testReportEvent(sdk);
        
        // 3. 发送心跳
        testHeartbeat(sdk);
    }
    
    /**
     * 测试卡密验证
     */
    private static void testVerify(LemonKamiSDK sdk) {
        System.out.println("1. 验证卡密");
        System.out.println("-------------------");
        
        String kamiCode = kami; // 替换为实际的卡密
        
        Map<String, Object> result = sdk.verify(kamiCode);
        
        if ((Boolean) result.getOrDefault("success", false)) {
            System.out.println("✅ 验证成功！");
            System.out.println("卡密类型: " + result.get("kami_type"));
            System.out.println("到期时间: " + result.get("expire_time"));
            System.out.println("消息: " + result.get("message"));
        } else {
            System.out.println("❌ 验证失败: " + result.get("message"));
        }
        
        System.out.println();
    }
    
    /**
     * 测试事件上报
     */
    private static void testReportEvent(LemonKamiSDK sdk) {
        System.out.println("2. 上报事件");
        System.out.println("-------------------");
        
        String kamiCode = kami; // 替换为实际的卡密
        
        // 构建额外数据
        Map<String, Object> extraData = new HashMap<>();
        extraData.put("username", "test_user");
        extraData.put("level", 10);
        extraData.put("action", "login");
        
        Map<String, Object> result = sdk.reportEvent(kamiCode, "login", extraData);
        
        if ((Boolean) result.getOrDefault("success", false)) {
            System.out.println("✅ 事件上报成功！");
            System.out.println("消息: " + result.get("message"));
        } else {
            System.out.println("❌ 事件上报失败: " + result.get("message"));
        }
        
        System.out.println();
    }
    
    /**
     * 测试心跳
     */
    private static void testHeartbeat(LemonKamiSDK sdk) {
        System.out.println("3. 发送心跳");
        System.out.println("-------------------");
        
        String kamiCode = kami; // 替换为实际的卡密
        
        Map<String, Object> result = sdk.heartbeat(kamiCode);
        
        if ((Boolean) result.getOrDefault("success", false)) {
            System.out.println("✅ 心跳发送成功！");
            System.out.println("消息: " + result.get("message"));
        } else {
            System.out.println("❌ 心跳发送失败: " + result.get("message"));
        }
        
        System.out.println();
    }
}
