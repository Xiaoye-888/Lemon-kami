-- Lemon Kami 数据库初始化脚本

CREATE DATABASE IF NOT EXISTS lemon_kami CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE lemon_kami;

-- 管理员用户表
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    email VARCHAR(128) DEFAULT NULL,
    phone VARCHAR(32) DEFAULT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    role VARCHAR(32) DEFAULT 'operator',
    status INT DEFAULT 1 COMMENT '1启用，0禁用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME DEFAULT NULL,
    failed_attempts INT DEFAULT 0 COMMENT '连续失败次数',
    locked_until DATETIME DEFAULT NULL COMMENT '锁定到期时间',
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 应用表
CREATE TABLE IF NOT EXISTS apps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    app_secret VARCHAR(128) NOT NULL,
    rsa_public_key TEXT NOT NULL,
    rsa_private_key TEXT NOT NULL,
    status INT DEFAULT 1 COMMENT '1启用，0禁用',
    INDEX idx_app_id (app_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 卡密表
CREATE TABLE IF NOT EXISTS kamis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    kami_code VARCHAR(128) UNIQUE NOT NULL,
    kami_type ENUM('day', 'month', 'lifetime', 'points', 'times') NOT NULL,
    status ENUM('unused', 'active', 'frozen') DEFAULT 'unused',
    bind_uuid VARCHAR(128) DEFAULT NULL,
    activate_time DATETIME DEFAULT NULL COMMENT '激活时间',
    expire_time DATETIME DEFAULT NULL,
    points_amount INT DEFAULT NULL COMMENT '积分卡面额',
    batch_no VARCHAR(64) DEFAULT NULL COMMENT '卡批次号',
    points_valid_days INT DEFAULT NULL COMMENT '积分兑换后有效天数',
    redeemed_by_user_id INT DEFAULT NULL COMMENT '兑换用户ID',
    redeemed_at DATETIME DEFAULT NULL COMMENT '兑换时间',
    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
    INDEX idx_app_id (app_id),
    INDEX idx_kami_code (kami_code),
    INDEX idx_batch_no (batch_no),
    INDEX idx_redeemed_by_user_id (redeemed_by_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 普通用户表
CREATE TABLE IF NOT EXISTS end_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) DEFAULT NULL,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) DEFAULT NULL,
    phone VARCHAR(64) DEFAULT NULL,
    status INT DEFAULT 1 COMMENT '1启用，0禁用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME DEFAULT NULL,
    INDEX idx_app_id (app_id),
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户积分账户表
CREATE TABLE IF NOT EXISTS user_point_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    balance INT DEFAULT 0 COMMENT '当前积分余额',
    total_recharged INT DEFAULT 0 COMMENT '累计充值积分',
    total_consumed INT DEFAULT 0 COMMENT '累计消费积分',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 积分流水表
CREATE TABLE IF NOT EXISTS point_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(64) UNIQUE NOT NULL,
    user_id INT NOT NULL,
    app_id VARCHAR(64) DEFAULT NULL,
    kami_code VARCHAR(128) DEFAULT NULL,
    transaction_type ENUM('recharge', 'consume', 'adjust') NOT NULL,
    amount INT NOT NULL COMMENT '积分变动，充值为正，消费为负',
    balance_before INT NOT NULL,
    balance_after INT NOT NULL,
    biz_id VARCHAR(128) DEFAULT NULL COMMENT '业务幂等ID',
    remark TEXT DEFAULT NULL,
    metadata_json TEXT DEFAULT NULL,
    operator VARCHAR(255) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_user_id (user_id),
    INDEX idx_app_id (app_id),
    INDEX idx_kami_code (kami_code),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_biz_id (biz_id),
    INDEX idx_created_at (created_at),
    UNIQUE KEY uk_point_tx_user_app_type_biz (user_id, app_id, transaction_type, biz_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 积分批次表
CREATE TABLE IF NOT EXISTS user_point_lots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    source_transaction_id VARCHAR(64) UNIQUE NOT NULL,
    app_id VARCHAR(64) DEFAULT NULL,
    kami_code VARCHAR(128) DEFAULT NULL,
    points_total INT NOT NULL COMMENT '批次原始积分',
    points_remaining INT DEFAULT 0 COMMENT '批次剩余积分',
    expires_at DATETIME DEFAULT NULL COMMENT '批次到期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_source_transaction_id (source_transaction_id),
    INDEX idx_app_id (app_id),
    INDEX idx_kami_code (kami_code),
    INDEX idx_points_remaining (points_remaining),
    INDEX idx_expires_at (expires_at),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 授权账户表
CREATE TABLE IF NOT EXISTS authorization_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    owner_type VARCHAR(32) NOT NULL,
    owner_key VARCHAR(512) NOT NULL DEFAULT '',
    user_id INT DEFAULT NULL,
    username VARCHAR(64) DEFAULT NULL,
    device_uuid VARCHAR(255) DEFAULT NULL,
    fingerprint VARCHAR(255) DEFAULT NULL,
    time_expires_at DATETIME DEFAULT NULL,
    is_lifetime BOOLEAN DEFAULT FALSE,
    times_balance INT DEFAULT 0,
    points_balance INT DEFAULT 0,
    status INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_app_id (app_id),
    INDEX idx_owner_type (owner_type),
    INDEX idx_owner_key (owner_key),
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_device_uuid (device_uuid),
    INDEX idx_fingerprint (fingerprint),
    INDEX idx_time_expires_at (time_expires_at),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    UNIQUE KEY uk_authorization_account_owner (app_id, owner_type, owner_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 授权批次权益表
CREATE TABLE IF NOT EXISTS authorization_lots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    source_kami_code VARCHAR(255) DEFAULT NULL,
    benefit_type VARCHAR(32) NOT NULL,
    amount_total INT NOT NULL,
    amount_remaining INT DEFAULT 0,
    starts_at DATETIME DEFAULT NULL,
    expires_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES authorization_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_source_kami_code (source_kami_code),
    INDEX idx_benefit_type (benefit_type),
    INDEX idx_amount_remaining (amount_remaining),
    INDEX idx_expires_at (expires_at),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 授权流水表
CREATE TABLE IF NOT EXISTS authorization_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id VARCHAR(64) UNIQUE NOT NULL,
    account_id INT NOT NULL,
    source_kami_code VARCHAR(255) DEFAULT NULL,
    transaction_type VARCHAR(32) NOT NULL,
    benefit_type VARCHAR(32) NOT NULL,
    amount INT NOT NULL,
    balance_after INT NOT NULL,
    biz_id VARCHAR(128) DEFAULT NULL,
    operator VARCHAR(255) DEFAULT NULL,
    metadata_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES authorization_accounts(id) ON DELETE CASCADE,
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_account_id (account_id),
    INDEX idx_source_kami_code (source_kami_code),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_benefit_type (benefit_type),
    INDEX idx_biz_id (biz_id),
    INDEX idx_created_at (created_at),
    UNIQUE KEY uk_authorization_tx_account_type_biz (account_id, transaction_type, biz_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 次数卡核销事务表
CREATE TABLE IF NOT EXISTS kami_consume_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    consume_id VARCHAR(64) UNIQUE NOT NULL,
    app_id VARCHAR(64) NOT NULL,
    kami_code VARCHAR(128) NOT NULL,
    biz_id VARCHAR(128) NOT NULL COMMENT '业务幂等ID',
    amount INT NOT NULL COMMENT '本次核销次数',
    times_total INT DEFAULT NULL,
    times_remaining INT DEFAULT NULL,
    device_uuid VARCHAR(255) DEFAULT NULL,
    fingerprint VARCHAR(255) DEFAULT NULL,
    ip_address VARCHAR(255) DEFAULT NULL,
    payload_json TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
    FOREIGN KEY (kami_code) REFERENCES kamis(kami_code) ON DELETE CASCADE,
    INDEX idx_consume_id (consume_id),
    INDEX idx_app_id (app_id),
    INDEX idx_kami_code (kami_code),
    INDEX idx_biz_id (biz_id),
    INDEX idx_times_remaining (times_remaining),
    INDEX idx_device_uuid (device_uuid),
    INDEX idx_fingerprint (fingerprint),
    INDEX idx_created_at (created_at),
    UNIQUE KEY uk_kami_consume_app_kami_biz (app_id, kami_code, biz_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 设备风控表
CREATE TABLE IF NOT EXISTS devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    uuid VARCHAR(128) NOT NULL,
    fingerprint VARCHAR(256) NOT NULL,
    last_ip VARCHAR(64) DEFAULT NULL,
    risk_level INT DEFAULT 0 COMMENT '0正常，1警告，2黑名单',
    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
    INDEX idx_app_id (app_id),
    INDEX idx_uuid (uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数据上报表
CREATE TABLE IF NOT EXISTS event_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    kami_code VARCHAR(128) DEFAULT NULL,
    event_type VARCHAR(64) NOT NULL COMMENT 'login/activate/verify/heartbeat/admin_login',
    ip_address VARCHAR(64) DEFAULT NULL COMMENT 'IP地址',
    device_uuid VARCHAR(128) DEFAULT NULL COMMENT '设备UUID',
    user_agent TEXT DEFAULT NULL COMMENT 'User-Agent',
    payload TEXT DEFAULT NULL COMMENT 'JSON字符串',
    status INT DEFAULT 1 COMMENT '1成功，0失败',
    message TEXT DEFAULT NULL COMMENT '消息描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
    INDEX idx_app_id (app_id),
    INDEX idx_kami_code (kami_code),
    INDEX idx_event_type (event_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
