/**
 * Lemon Kami JavaScript SDK
 * 卡密验证客户端 SDK (使用 crypto-js + JSEncrypt)
 */

class LemonKamiSDK {
  /**
   * 初始化 SDK
   * @param {Object} config - 配置对象
   * @param {string} config.appId - 应用ID
   * @param {string} config.appSecret - 应用密钥
   * @param {string} [config.serverUrl='http://localhost:8000'] - 服务器地址
   * @param {string} [config.rsaPublicKey] - RSA公钥（可选）
   * @param {boolean} [config.autoReleaseOnUnload=true] - 页面关闭时自动释放设备名额
   */
  constructor(config) {
    // 检查依赖库是否已加载
    if (typeof CryptoJS === 'undefined') {
      throw new Error('CryptoJS 未加载，请先引入 crypto-js 库');
    }
    if (typeof JSEncrypt === 'undefined') {
      throw new Error('JSEncrypt 未加载，请先引入 jsencrypt 库');
    }
    
    this.appId = config.appId;
    this.appSecret = config.appSecret;
    this.serverUrl = (config.serverUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.rsaPublicKey = config.rsaPublicKey || null;
    this.deviceUuid = this._getDeviceUuid();
    this.fingerprint = ''; // 初始化为空字符串
    this.currentKamiCode = null;
    this.autoReleaseOnUnload = config.autoReleaseOnUnload !== false;
    this._releaseOnUnloadHandler = () => {
      if (this.autoReleaseOnUnload && this.currentKamiCode) {
        this.releaseDevice(this.currentKamiCode, { keepalive: true });
      }
    };

    // 异步生成指纹
    this._fingerprintReady = this._initFingerprint();

    // 如果未提供公钥，自动获取
    if (!this.rsaPublicKey) {
      this._fetchPublicKey();
    }

    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('pagehide', this._releaseOnUnloadHandler);
      window.addEventListener('beforeunload', this._releaseOnUnloadHandler);
    }
  }

  /**
   * 异步初始化设备指纹
   * @private
   */
  async _initFingerprint() {
    this.fingerprint = await this._generateFingerprint();
  }

  /**
   * 获取设备UUID
   * @returns {string} 设备UUID
   * @private
   */
  _getDeviceUuid() {
    let uuid = localStorage.getItem('device_uuid');
    if (!uuid) {
      uuid = this._generateUuid();
      localStorage.setItem('device_uuid', uuid);
    }
    return uuid;
  }

  /**
   * 生成UUID
   * @returns {string} UUID
   * @private
   */
  _generateUuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * 生成设备指纹
   * @returns {string} 设备指纹哈希
   * @private
   */
  _generateFingerprint() {
    const info = {
      platform: navigator.platform,
      userAgent: navigator.userAgent,
      language: navigator.language,
      screenResolution: `${screen.width}x${screen.height}`,
      colorDepth: screen.colorDepth,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };

    const fingerprintStr = JSON.stringify(info);
    return this._sha256(fingerprintStr);
  }

  /**
   * SHA256 哈希
   * @param {string} str - 输入字符串
   * @returns {string} SHA256 哈希值
   * @private
   */
  _sha256(str) {
    return CryptoJS.SHA256(str).toString(CryptoJS.enc.Hex);
  }

  /**
   * HMAC-SHA256 签名
   * @param {string} str - 输入字符串
   * @param {string} secret - 密钥
   * @returns {string} HMAC-SHA256 签名
   * @private
   */
  _hmacSha256(str, secret) {
    return CryptoJS.HmacSHA256(str, secret).toString(CryptoJS.enc.Hex);
  }

  /**
   * 从服务器获取RSA公钥
   * @private
   */
  async _fetchPublicKey() {
    try {
      const response = await fetch(
        `${this.serverUrl}/api/v1/sdk/public-key?app_id=${this.appId}`
      );
      if (response.ok) {
        const data = await response.json();
        this.rsaPublicKey = data.public_key;
      }
    } catch (error) {
      // 静默失败，公钥将在需要时重新获取
    }
  }

  /**
   * 加密数据
   * @param {Object} data - 要加密的数据
   * @returns {Promise<Object>} 加密后的数据对象
   * @private
   */
  async _encryptData(data) {
    // 验证公钥是否存在
    if (!this.rsaPublicKey) {
      throw new Error("RSA 公钥未初始化，请检查服务器连接或手动指定公钥");
    }

    // 生成随机 AES 密钥和 IV (使用 AES-128, 16字节)
    const aesKey = CryptoJS.lib.WordArray.random(16);
    const aesIv = CryptoJS.lib.WordArray.random(16);

    // AES 加密业务数据
    const dataJson = JSON.stringify(data);
    const encryptedData = this._aesEncrypt(dataJson, aesKey, aesIv);

    // RSA 加密 AES 密钥
    // 将 WordArray 转换为原始字节数组，然后转为字符串（每个字节一个字符）
    const aesKeyBytes = new Uint8Array(aesKey.sigBytes);
    for (let i = 0; i < aesKey.sigBytes; i++) {
      aesKeyBytes[i] = (aesKey.words[i >>> 2] >>> (24 - (i % 4) * 8)) & 0xff;
    }
    
    // 将字节数组转为字符串（每个字节作为一个字符）
    let aesKeyStr = '';
    for (let i = 0; i < aesKeyBytes.length; i++) {
      aesKeyStr += String.fromCharCode(aesKeyBytes[i]);
    }
    
    const encryptedAesKey = this._rsaEncrypt(aesKeyStr);

    // 生成时间戳和随机数
    const timestamp = Math.floor(Date.now() / 1000);
    const nonce = Math.random().toString(36).substring(2, 18);

    // 生成 HMAC-SHA256 签名（与后端保持一致）
    const encryptedDataBase64 = encryptedData.toString(CryptoJS.enc.Base64);
    const signStr = `${timestamp}${nonce}${encryptedDataBase64}`;
    const signature = this._hmacSha256(signStr, this.appSecret);

    // 返回符合后端格式的字典
    const result = {
      app_id: this.appId,
      timestamp: timestamp,
      nonce: nonce,
      sign: signature,
      encrypted_key: encryptedAesKey,
      encrypted_data: encryptedDataBase64,
      iv: aesIv.toString(CryptoJS.enc.Base64)
    };

    return result;
  }

  /**
   * AES 加密
   * @param {string} data - 数据
   * @param {WordArray} key - 密钥
   * @param {WordArray} iv - 初始化向量
   * @returns {WordArray} 加密后的数据
   * @private
   */
  _aesEncrypt(data, key, iv) {
    const encrypted = CryptoJS.AES.encrypt(data, key, {
      iv: iv,
      mode: CryptoJS.mode.CBC,
      padding: CryptoJS.pad.Pkcs7
    });
    
    return encrypted.ciphertext;
  }

  /**
   * RSA 加密（使用 JSEncrypt）
   * @param {string} data - 原始字符串（必须是 Latin1 编码）
   * @returns {string} 加密后的数据（Base64）
   * @private
   */
  _rsaEncrypt(data) {
    // JSEncrypt 内部会将字符串转为 UTF-8，导致字节膨胀
    // 所以我们需要先将字符串转为字节数组，然后手动处理
    
    const encrypt = new JSEncrypt();
    encrypt.setPublicKey(this.rsaPublicKey);
    
    // 将字符串转为字节数组（每个字符一个字节）
    const bytes = new Uint8Array(data.length);
    for (let i = 0; i < data.length; i++) {
      bytes[i] = data.charCodeAt(i) & 0xFF;
    }
    
    // 将字节数组转为 Base64
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64Data = btoa(binary);
    
    // 加密 Base64 字符串
    const encrypted = encrypt.encrypt(base64Data);
    
    if (!encrypted) {
      throw new Error('RSA 加密失败');
    }
    
    return encrypted;
  }

  /**
   * 验证卡密
   * @param {string} kamiCode - 卡密代码
   * @returns {Promise<Object>} 验证结果
   */
  async verify(kamiCode) {
    await this._fingerprintReady;
    const requestData = {
      kami: kamiCode,
      uuid: this.deviceUuid,
      fingerprint: this.fingerprint,
      _app_info: {
        app_id: this.appId
      }
    };

    const encryptedData = await this._encryptData(requestData);

    try {
      const response = await fetch(`${this.serverUrl}/api/v1/sdk/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(encryptedData)
      });

      const result = await response.json();

      // 检查是否是加密响应
      const finalResult = result.encrypted ? await this._decryptResponse(result) : result;
      if (finalResult.success) {
        this.currentKamiCode = kamiCode;
      }
      return finalResult;
    } catch (error) {
      return {
        success: false,
        message: `网络错误: ${error.message}`
      };
    }
  }

  /**
   * 释放当前设备占用名额
   * @param {string} [kamiCode] - 卡密代码，默认使用最近验证成功的卡密
   * @param {Object} [options={}] - 请求选项
   * @param {boolean} [options.keepalive=false] - 页面关闭时使用 keepalive 请求
   * @returns {Promise<Object>} 释放结果
   */
  async releaseDevice(kamiCode = this.currentKamiCode, options = {}) {
    if (!kamiCode) {
      return {
        success: false,
        message: '暂无需要释放的卡密'
      };
    }

    await this._fingerprintReady;
    const requestData = {
      kami: kamiCode,
      uuid: this.deviceUuid,
      fingerprint: this.fingerprint,
      _app_info: {
        app_id: this.appId
      }
    };

    try {
      const encryptedData = await this._encryptData(requestData);
      const response = await fetch(`${this.serverUrl}/api/v1/sdk/release-device`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(encryptedData),
        keepalive: Boolean(options.keepalive)
      });

      const result = await response.json();
      const finalResult = result.encrypted ? await this._decryptResponse(result) : result;
      if (finalResult.success) {
        this.currentKamiCode = null;
      }
      return finalResult;
    } catch (error) {
      return {
        success: false,
        message: `释放设备失败: ${error.message}`
      };
    }
  }

  /**
   * 上报行为事件
   * @param {string} kamiCode - 卡密代码
   * @param {string} eventType - 事件类型
   * @param {Object} [extraData={}] - 额外数据
   * @returns {Promise<Object>} 上报结果
   */
  async reportEvent(kamiCode, eventType, extraData = {}) {
    const requestData = {
      kami: kamiCode,
      event_type: eventType,
      extra_data: extraData,
      _app_info: {
        app_id: this.appId
      }
    };

    const encryptedData = await this._encryptData(requestData);

    try {
      const response = await fetch(`${this.serverUrl}/api/v1/sdk/report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(encryptedData)
      });

      const result = await response.json();

      // 检查是否是加密响应
      if (result.encrypted) {
        return await this._decryptResponse(result);
      }

      return result;
    } catch (error) {
      return {
        success: false,
        message: `网络错误: ${error.message}`
      };
    }
  }

  /**
   * 发送心跳
   * @param {string} kamiCode - 卡密代码
   * @returns {Promise<Object>} 心跳结果
   */
  heartbeat(kamiCode) {
    return this.reportEvent(kamiCode, 'heartbeat');
  }

  /**
   * 销毁 SDK 实例，释放当前设备名额并移除自动释放监听
   * @returns {Promise<Object>} 释放结果
   */
  async destroy() {
    if (typeof window !== 'undefined' && window.removeEventListener) {
      window.removeEventListener('pagehide', this._releaseOnUnloadHandler);
      window.removeEventListener('beforeunload', this._releaseOnUnloadHandler);
    }
    return await this.releaseDevice(this.currentKamiCode);
  }

  /**
   * 解密响应数据
   * @param {Object} encryptedResponse - 加密的响应数据
   * @returns {Promise<Object>} 解密后的数据
   * @private
   */
  async _decryptResponse(encryptedResponse) {
    try {
      // 提取加密字段
      const { timestamp, nonce, sign, encrypted_key, encrypted_data, iv } = encryptedResponse;

      if (!timestamp || !nonce || !sign || !encrypted_key || !encrypted_data || !iv) {
        throw new Error("响应数据格式错误");
      }

      // 验证签名
      const signStr = `${timestamp}${nonce}${encrypted_data}`;
      const expectedSign = this._hmacSha256(signStr, this.appSecret);

      if (expectedSign !== sign) {
        throw new Error("响应签名验证失败");
      }

      // 后端返回的 encrypted_key 只是 Base64 编码，不是 RSA 加密
      // 直接 Base64 解码得到 AES 密钥
      const aesKey = CryptoJS.enc.Base64.parse(encrypted_key);
      const aesIv = CryptoJS.enc.Base64.parse(iv);
      const encryptedData = CryptoJS.enc.Base64.parse(encrypted_data);

      // AES 解密
      const decrypted = CryptoJS.AES.decrypt(
        { ciphertext: encryptedData },
        aesKey,
        {
          iv: aesIv,
          mode: CryptoJS.mode.CBC,
          padding: CryptoJS.pad.Pkcs7
        }
      );

      // 转换为字符串
      const decryptedText = decrypted.toString(CryptoJS.enc.Utf8);

      if (!decryptedText) {
        throw new Error("解密失败");
      }

      // 解析 JSON
      return JSON.parse(decryptedText);

    } catch (error) {
      return {
        success: false,
        message: `响应解密失败: ${error.message}`
      };
    }
  }
}

// Export for CommonJS and browser globals.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LemonKamiSDK;
  module.exports.LemonKamiSDK = LemonKamiSDK;
} else {
  window.LemonKamiSDK = LemonKamiSDK;
}
