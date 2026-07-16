package com.lemon.kami;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.apache.commons.codec.binary.Base64;
import org.apache.commons.codec.digest.HmacUtils;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;

/**
 * Lemon Kami Java SDK
 * 小柠檬网络验证 Java 客户端 SDK
 */
public class LemonKamiSDK {
    
    private String appId;
    private String appSecret;
    private String serverUrl;
    private String rsaPublicKey;
    private String fingerprint;
    private Gson gson;
    
    /**
     * 初始化 SDK
     *
     * @param appId       应用ID
     * @param appSecret   应用密钥
     * @param serverUrl   服务器地址
     * @param rsaPublicKey RSA公钥（可选，会自动从服务器获取）
     */
    public LemonKamiSDK(String appId, String appSecret, String serverUrl, String rsaPublicKey) {
        this.appId = appId;
        this.appSecret = appSecret;
        this.serverUrl = serverUrl.replaceAll("/$", "");
        this.rsaPublicKey = rsaPublicKey;
        this.fingerprint = generateDeviceFingerprint();
        this.gson = new Gson();
        
        // 如果未提供公钥，自动获取
        if (this.rsaPublicKey == null || this.rsaPublicKey.isEmpty()) {
            fetchPublicKey();
        }
    }
    
    /**
     * 初始化 SDK（不带公钥，自动获取）
     *
     * @param appId     应用ID
     * @param appSecret 应用密钥
     * @param serverUrl 服务器地址
     */
    public LemonKamiSDK(String appId, String appSecret, String serverUrl) {
        this(appId, appSecret, serverUrl, null);
    }
    
    /**
     * 生成设备指纹
     * 使用多种硬件信息组合生成唯一的设备标识符
     *
     * @return 设备指纹哈希
     */
    private String generateDeviceFingerprint() {
        try {
            Map<String, Object> info = new LinkedHashMap<>();
            
            // 操作系统信息
            info.put("os.name", System.getProperty("os.name"));
            info.put("os.version", System.getProperty("os.version"));
            info.put("os.arch", System.getProperty("os.arch"));
            
            // Java 虚拟机信息
            info.put("java.vm.name", System.getProperty("java.vm.name"));
            info.put("java.vm.version", System.getProperty("java.vm.version"));
            
            // 计算机名
            info.put("user.name", System.getProperty("user.name"));
            
            // MAC 地址
            info.put("mac_addresses", getMacAddresses());
            
            // 系统唯一标识
            info.put("system_info", getSystemUniqueId());
            
            // 生成 SHA256 哈希
            String fingerprintStr = gson.toJson(info);
            return sha256(fingerprintStr);
            
        } catch (Exception e) {
            // 如果获取失败，使用简单的标识
            return sha256(System.getProperty("os.name") + System.getProperty("user.name"));
        }
    }
    
    /**
     * 获取 MAC 地址列表
     *
     * @return MAC 地址列表
     */
    private List<String> getMacAddresses() {
        List<String> macs = new ArrayList<>();
        try {
            String os = System.getProperty("os.name").toLowerCase();
            Process process;
            
            if (os.contains("win")) {
                // Windows
                process = Runtime.getRuntime().exec("getmac");
            } else if (os.contains("mac") || os.contains("darwin")) {
                // macOS
                process = Runtime.getRuntime().exec("ifconfig");
            } else {
                // Linux
                process = Runtime.getRuntime().exec("ifconfig");
            }
            
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
            String line;
            while ((line = reader.readLine()) != null) {
                // 提取 MAC 地址格式: XX:XX:XX:XX:XX:XX 或 XX-XX-XX-XX-XX-XX
                if (line.matches(".*([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}.*")) {
                    String[] parts = line.split("[:\\-]");
                    if (parts.length >= 6) {
                        StringBuilder mac = new StringBuilder();
                        for (int i = 0; i < 6; i++) {
                            if (i > 0) mac.append(":");
                            mac.append(parts[i].replaceAll("[^0-9A-Fa-f]", ""));
                        }
                        if (!macs.contains(mac.toString())) {
                            macs.add(mac.toString());
                        }
                    }
                }
            }
            reader.close();
            process.waitFor();
        } catch (Exception e) {
            // 忽略错误
        }
        
        Collections.sort(macs);
        return macs;
    }
    
    /**
     * 获取系统唯一标识符
     *
     * @return 系统唯一标识
     */
    private String getSystemUniqueId() {
        try {
            String os = System.getProperty("os.name").toLowerCase();
            
            if (os.contains("win")) {
                // Windows: 尝试获取 MachineGuid
                Process process = Runtime.getRuntime().exec(
                    "reg query HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography /v MachineGuid"
                );
                BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.contains("MachineGuid")) {
                        String[] parts = line.trim().split("\\s+");
                        if (parts.length > 0) {
                            return parts[parts.length - 1];
                        }
                    }
                }
                reader.close();
                process.waitFor();
            } else if (os.contains("mac") || os.contains("darwin")) {
                // macOS: 获取硬件 UUID
                Process process = Runtime.getRuntime().exec("system_profiler SPHardwareDataType");
                BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.contains("Hardware UUID")) {
                        String[] parts = line.split(":");
                        if (parts.length > 1) {
                            return parts[1].trim();
                        }
                    }
                }
                reader.close();
                process.waitFor();
            } else {
                // Linux: 尝试获取 machine-id
                try {
                    Process process = Runtime.getRuntime().exec("cat /etc/machine-id");
                    BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()));
                    String machineId = reader.readLine();
                    reader.close();
                    process.waitFor();
                    if (machineId != null && !machineId.isEmpty()) {
                        return machineId;
                    }
                } catch (Exception e) {
                    // 忽略
                }
            }
        } catch (Exception e) {
            // 忽略错误
        }
        
        // 如果所有方法都失败，返回一个基于平台信息的标识符
        return System.getProperty("os.name") + "_" + System.getProperty("os.version") + "_" + System.getProperty("os.arch");
    }
    
    /**
     * SHA256 哈希
     *
     * @param input 输入字符串
     * @return SHA256 哈希值（十六进制）
     */
    private String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            throw new RuntimeException("SHA256 计算失败", e);
        }
    }
    
    /**
     * 从服务器获取 RSA 公钥
     */
    private void fetchPublicKey() {
        try {
            String url = serverUrl + "/api/v1/sdk/public-key?app_id=" + appId;
            HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();
                
                JsonObject json = gson.fromJson(response.toString(), JsonObject.class);
                this.rsaPublicKey = json.get("public_key").getAsString();
            } else {
                throw new RuntimeException("获取公钥失败: HTTP " + responseCode);
            }
            conn.disconnect();
        } catch (Exception e) {
            throw new RuntimeException("获取公钥失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 加密数据
     * 使用 RSA + AES 混合加密
     *
     * @param data 要加密的数据
     * @return 加密后的数据对象
     */
    private Map<String, Object> encryptData(Map<String, Object> data) {
        try {
            if (rsaPublicKey == null || rsaPublicKey.isEmpty()) {
                throw new RuntimeException("RSA 公钥未初始化，请检查服务器连接或手动指定公钥");
            }
            
            // 生成随机 AES 密钥和 IV (AES-128, 16字节)
            KeyGenerator keyGen = KeyGenerator.getInstance("AES");
            keyGen.init(128);
            SecretKey aesKey = keyGen.generateKey();
            byte[] aesIv = new byte[16];
            new Random().nextBytes(aesIv);
            
            // AES 加密业务数据
            String dataJson = gson.toJson(data);
            Cipher aesCipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            aesCipher.init(Cipher.ENCRYPT_MODE, aesKey, new IvParameterSpec(aesIv));
            byte[] encryptedData = aesCipher.doFinal(dataJson.getBytes(StandardCharsets.UTF_8));
            
            // RSA 加密 AES 密钥
            // 先将 AES 密钥转为 Base64 字符串，再 RSA 加密（与 Python/JS SDK 保持一致）
            String aesKeyBase64 = Base64.encodeBase64String(aesKey.getEncoded());
            PublicKey publicKey = loadPublicKey(rsaPublicKey);
            Cipher rsaCipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");
            rsaCipher.init(Cipher.ENCRYPT_MODE, publicKey);
            byte[] encryptedAesKey = rsaCipher.doFinal(aesKeyBase64.getBytes(StandardCharsets.UTF_8));
            
            // 生成时间戳和随机数
            long timestamp = System.currentTimeMillis() / 1000;
            String nonce = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
            
            // 生成 HMAC-SHA256 签名
            String encryptedDataBase64 = Base64.encodeBase64String(encryptedData);
            String signStr = timestamp + nonce + encryptedDataBase64;
            String signature = HmacUtils.hmacSha256Hex(appSecret, signStr);
            
            // 构建返回结果
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("app_id", appId);
            result.put("timestamp", timestamp);
            result.put("nonce", nonce);
            result.put("sign", signature);
            result.put("encrypted_key", Base64.encodeBase64String(encryptedAesKey));
            result.put("encrypted_data", encryptedDataBase64);
            result.put("iv", Base64.encodeBase64String(aesIv));
            
            return result;
            
        } catch (Exception e) {
            throw new RuntimeException("数据加密失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 加载 RSA 公钥
     *
     * @param publicKeyPEM PEM 格式的公钥
     * @return PublicKey 对象
     */
    private PublicKey loadPublicKey(String publicKeyPEM) throws Exception {
        // 移除 PEM 头尾和换行符
        String publicKeyContent = publicKeyPEM
            .replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replaceAll("\\s", "");
        
        byte[] decoded = Base64.decodeBase64(publicKeyContent);
        X509EncodedKeySpec spec = new X509EncodedKeySpec(decoded);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        return keyFactory.generatePublic(spec);
    }
    
    /**
     * 验证卡密
     *
     * @param kamiCode 卡密代码
     * @return 验证结果
     */
    public Map<String, Object> verify(String kamiCode) {
        try {
            // 构建请求数据
            Map<String, Object> requestData = new LinkedHashMap<>();
            requestData.put("kami", kamiCode);
            requestData.put("fingerprint", fingerprint);
            
            Map<String, Object> appInfo = new LinkedHashMap<>();
            appInfo.put("app_id", appId);
            requestData.put("_app_info", appInfo);
            
            // 加密数据
            Map<String, Object> encryptedPayload = encryptData(requestData);
            
            // 发送请求
            String url = serverUrl + "/api/v1/sdk/verify";
            HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            // 写入请求体
            String jsonPayload = gson.toJson(encryptedPayload);
            conn.getOutputStream().write(jsonPayload.getBytes(StandardCharsets.UTF_8));
            conn.getOutputStream().flush();
            
            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();
                
                @SuppressWarnings("unchecked")
                Map<String, Object> result = gson.fromJson(response.toString(), Map.class);
                
                // 检查是否是加密响应
                if (result.containsKey("encrypted") && (Boolean) result.get("encrypted")) {
                    return decryptResponse(result);
                }
                
                conn.disconnect();
                return result;
            } else {
                conn.disconnect();
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("success", false);
                error.put("message", "HTTP " + responseCode);
                return error;
            }
            
        } catch (Exception e) {
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("success", false);
            error.put("message", "网络错误: " + e.getMessage());
            return error;
        }
    }
    
    /**
     * 上报行为事件
     *
     * @param kamiCode  卡密代码
     * @param eventType 事件类型
     * @param extraData 额外数据
     * @return 上报结果
     */
    public Map<String, Object> reportEvent(String kamiCode, String eventType, Map<String, Object> extraData) {
        try {
            // 构建请求数据
            Map<String, Object> requestData = new LinkedHashMap<>();
            requestData.put("kami", kamiCode);
            requestData.put("event_type", eventType);
            requestData.put("extra_data", extraData != null ? extraData : new LinkedHashMap<>());
            
            Map<String, Object> appInfo = new LinkedHashMap<>();
            appInfo.put("app_id", appId);
            requestData.put("_app_info", appInfo);
            
            // 加密数据
            Map<String, Object> encryptedPayload = encryptData(requestData);
            
            // 发送请求
            String url = serverUrl + "/api/v1/sdk/report";
            HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            // 写入请求体
            String jsonPayload = gson.toJson(encryptedPayload);
            conn.getOutputStream().write(jsonPayload.getBytes(StandardCharsets.UTF_8));
            conn.getOutputStream().flush();
            
            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();
                
                @SuppressWarnings("unchecked")
                Map<String, Object> result = gson.fromJson(response.toString(), Map.class);
                
                // 检查是否是加密响应
                if (result.containsKey("encrypted") && (Boolean) result.get("encrypted")) {
                    return decryptResponse(result);
                }
                
                conn.disconnect();
                return result;
            } else {
                conn.disconnect();
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("success", false);
                error.put("message", "HTTP " + responseCode);
                return error;
            }
            
        } catch (Exception e) {
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("success", false);
            error.put("message", "网络错误: " + e.getMessage());
            return error;
        }
    }
    
    /**
     * 上报行为事件（无额外数据）
     *
     * @param kamiCode  卡密代码
     * @param eventType 事件类型
     * @return 上报结果
     */
    public Map<String, Object> reportEvent(String kamiCode, String eventType) {
        return reportEvent(kamiCode, eventType, null);
    }
    
    /**
     * 发送心跳
     *
     * @param kamiCode 卡密代码
     * @return 心跳结果
     */
    public Map<String, Object> heartbeat(String kamiCode) {
        return reportEvent(kamiCode, "heartbeat");
    }

    /**
     * 释放当前设备占用名额
     *
     * @param kamiCode 卡密代码
     * @return 释放结果
     */
    public Map<String, Object> releaseDevice(String kamiCode) {
        try {
            Map<String, Object> requestData = new LinkedHashMap<>();
            requestData.put("kami", kamiCode);
            requestData.put("fingerprint", fingerprint);

            Map<String, Object> appInfo = new LinkedHashMap<>();
            appInfo.put("app_id", appId);
            requestData.put("_app_info", appInfo);

            Map<String, Object> encryptedPayload = encryptData(requestData);

            String url = serverUrl + "/api/v1/sdk/release-device";
            HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);

            String jsonPayload = gson.toJson(encryptedPayload);
            conn.getOutputStream().write(jsonPayload.getBytes(StandardCharsets.UTF_8));
            conn.getOutputStream().flush();

            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();

                @SuppressWarnings("unchecked")
                Map<String, Object> result = gson.fromJson(response.toString(), Map.class);

                if (result.containsKey("encrypted") && (Boolean) result.get("encrypted")) {
                    return decryptResponse(result);
                }

                conn.disconnect();
                return result;
            } else {
                conn.disconnect();
                Map<String, Object> error = new LinkedHashMap<>();
                error.put("success", false);
                error.put("message", "HTTP " + responseCode);
                return error;
            }
        } catch (Exception e) {
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("success", false);
            error.put("message", "网络错误: " + e.getMessage());
            return error;
        }
    }
    
    /**
     * 解密响应数据
     *
     * @param encryptedResponse 加密的响应数据
     * @return 解密后的数据
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> decryptResponse(Map<String, Object> encryptedResponse) {
        try {
            // 提取加密字段
            long timestamp = ((Number) encryptedResponse.get("timestamp")).longValue();
            String nonce = (String) encryptedResponse.get("nonce");
            String sign = (String) encryptedResponse.get("sign");
            String encryptedKeyBase64 = (String) encryptedResponse.get("encrypted_key");
            String encryptedDataBase64 = (String) encryptedResponse.get("encrypted_data");
            String ivBase64 = (String) encryptedResponse.get("iv");
            
            if (timestamp == 0 || nonce == null || sign == null || 
                encryptedKeyBase64 == null || encryptedDataBase64 == null || ivBase64 == null) {
                throw new RuntimeException("响应数据格式错误");
            }
            
            // 验证签名
            String signStr = timestamp + nonce + encryptedDataBase64;
            String expectedSign = HmacUtils.hmacSha256Hex(appSecret, signStr);
            
            if (!expectedSign.equals(sign)) {
                throw new RuntimeException("响应签名验证失败");
            }
            
            // AES 密钥已经是明文（Base64编码）
            byte[] aesKeyBytes = Base64.decodeBase64(encryptedKeyBase64);
            byte[] aesIv = Base64.decodeBase64(ivBase64);
            byte[] encryptedData = Base64.decodeBase64(encryptedDataBase64);
            
            // AES 解密
            SecretKeySpec keySpec = new SecretKeySpec(aesKeyBytes, "AES");
            Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
            cipher.init(Cipher.DECRYPT_MODE, keySpec, new IvParameterSpec(aesIv));
            byte[] decryptedPadded = cipher.doFinal(encryptedData);
            
            // 解析 JSON
            String decryptedText = new String(decryptedPadded, StandardCharsets.UTF_8);
            return gson.fromJson(decryptedText, Map.class);
            
        } catch (Exception e) {
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("success", false);
            error.put("message", "响应解密失败: " + e.getMessage());
            return error;
        }
    }
}
