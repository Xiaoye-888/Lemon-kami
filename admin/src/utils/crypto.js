/**
 * 加密工具函数
 * 用于登录等敏感信息的 AES 加密
 */
import CryptoJS from 'crypto-js'

/**
 * 纯 AES 加密（用于登录）
 * @param {object} data - 要加密的业务数据
 * @param {string} keyBase64 - Base64 编码的 AES 密钥
 * @returns {object} - 包含 encrypted_data 和 iv 的对象
 */
export function aesEncryptForLogin(data, keyBase64) {
  // 解码 Base64 密钥
  const key = CryptoJS.enc.Base64.parse(keyBase64)
  
  // 将数据转为 JSON 字符串
  const dataStr = typeof data === 'string' ? data : JSON.stringify(data)
  
  // 生成随机 IV
  const iv = CryptoJS.lib.WordArray.random(16)
  
  // 使用 AES-CBC 模式加密
  const encrypted = CryptoJS.AES.encrypt(dataStr, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  })
  
  return {
    encrypted_data: encrypted.ciphertext.toString(CryptoJS.enc.Base64),
    iv: iv.toString(CryptoJS.enc.Base64)
  }
}
