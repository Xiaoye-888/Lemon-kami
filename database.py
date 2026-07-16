from sqlmodel import create_engine, Session
from config import settings
import time
import sys
import logging

# 配置日志
logger = logging.getLogger(__name__)

def debug_print(msg: str):
    """只在调试模式下打印信息"""
    if settings.DEBUG:
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
            sys.stdout.flush()
        sys.stdout.flush()

# 创建数据库引擎
echo_sql = settings.DEBUG  # 只在调试模式下显示 SQL
engine_kwargs = {"echo": echo_sql, "pool_pre_ping": True}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)


def _ensure_points_schema():
    """Create points-system tables and columns for existing databases."""
    from sqlalchemy import text

    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        existing_tables = [row[0] for row in result.fetchall()]

        def varchar_length(table_name: str, column_name: str, default: int) -> int:
            if table_name not in existing_tables:
                return default
            for row in conn.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall():
                if row[0] != column_name:
                    continue
                column_type = str(row[1]).lower()
                if column_type.startswith("varchar("):
                    return int(column_type.split("(", 1)[1].split(")", 1)[0])
            return default

        app_id_length = varchar_length("apps", "app_id", 64)
        kami_code_length = varchar_length("kamis", "kami_code", 255)

        if "end_users" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE end_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64),
                    username VARCHAR(64) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(255),
                    phone VARCHAR(64),
                    status INT DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    INDEX idx_app_id (app_id),
                    INDEX idx_username (username),
                    INDEX idx_email (email),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='End users'
            """))
            conn.commit()

        if "end_users" in existing_tables:
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM end_users")).fetchall()
            }
            if "app_id" not in columns:
                conn.execute(text("ALTER TABLE end_users ADD COLUMN app_id VARCHAR(64) DEFAULT NULL"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_end_users_app_id ON end_users (app_id)"))
                conn.commit()

        if "user_point_accounts" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE user_point_accounts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    balance INT DEFAULT 0,
                    total_recharged INT DEFAULT 0,
                    total_consumed INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User point accounts'
            """))
            conn.commit()

        if "point_transactions" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE point_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    transaction_id VARCHAR(64) NOT NULL UNIQUE,
                    user_id INT NOT NULL,
                    app_id VARCHAR(64),
                    kami_code VARCHAR(255),
                    transaction_type ENUM('recharge', 'consume', 'refund', 'adjust') NOT NULL,
                    amount INT NOT NULL,
                    balance_before INT NOT NULL,
                    balance_after INT NOT NULL,
                    biz_id VARCHAR(128),
                    remark TEXT,
                    metadata_json TEXT,
                    operator VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_transaction_id (transaction_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_app_id (app_id),
                    INDEX idx_kami_code (kami_code),
                    INDEX idx_transaction_type (transaction_type),
                    INDEX idx_biz_id (biz_id),
                    INDEX idx_created_at (created_at),
                    UNIQUE KEY uk_point_tx_user_type_biz (user_id, transaction_type, biz_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Point transactions'
            """))
            conn.commit()

        if "point_transactions" in existing_tables:
            columns = {
                row[0]: row[1]
                for row in conn.execute(text("SHOW COLUMNS FROM point_transactions")).fetchall()
            }
            if "transaction_type" in columns and "refund" not in columns["transaction_type"]:
                conn.execute(text("""
                    ALTER TABLE point_transactions
                    MODIFY COLUMN transaction_type ENUM('recharge', 'consume', 'refund', 'adjust') NOT NULL
                """))
                conn.commit()
            indexes = {
                row[2]
                for row in conn.execute(text("SHOW INDEX FROM point_transactions")).fetchall()
            }
            if "uk_point_tx_user_type_biz" not in indexes:
                conn.execute(text("""
                    ALTER TABLE point_transactions
                    ADD UNIQUE KEY uk_point_tx_user_type_biz (user_id, transaction_type, biz_id)
                """))
                conn.commit()

        if "user_point_lots" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE user_point_lots (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    source_transaction_id VARCHAR(64) NOT NULL UNIQUE,
                    app_id VARCHAR(64),
                    kami_code VARCHAR(255),
                    points_total INT NOT NULL,
                    points_remaining INT DEFAULT 0,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_source_transaction_id (source_transaction_id),
                    INDEX idx_app_id (app_id),
                    INDEX idx_kami_code (kami_code),
                    INDEX idx_points_remaining (points_remaining),
                    INDEX idx_expires_at (expires_at),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User point lots'
            """))
            conn.commit()

        if "kamis" in existing_tables:
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM kamis")).fetchall()
            }
            if "spec_id" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN spec_id INT DEFAULT NULL"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_kamis_spec_id ON kamis (spec_id)"))
                conn.commit()
            if "points_amount" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN points_amount INT DEFAULT NULL"))
                conn.commit()
            if "batch_no" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN batch_no VARCHAR(64) DEFAULT NULL"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_batch_no ON kamis (batch_no)"))
                conn.commit()
            if "points_valid_days" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN points_valid_days INT DEFAULT NULL"))
                conn.commit()
            if "redeemed_by_user_id" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN redeemed_by_user_id INT DEFAULT NULL"))
                conn.commit()
            if "redeemed_at" not in columns:
                conn.execute(text("ALTER TABLE kamis ADD COLUMN redeemed_at DATETIME DEFAULT NULL"))
                conn.commit()
            if "hour" not in next(
                (
                    row[1]
                    for row in conn.execute(text("SHOW COLUMNS FROM kamis")).fetchall()
                    if row[0] == "kami_type"
                ),
                "",
            ):
                conn.execute(text("""
                    ALTER TABLE kamis
                    MODIFY COLUMN kami_type ENUM('hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime', 'points', 'times') NOT NULL
                """))
                conn.commit()
            extra_columns = {
                "time_value": "ALTER TABLE kamis ADD COLUMN time_value INT DEFAULT NULL",
                "time_unit": "ALTER TABLE kamis ADD COLUMN time_unit VARCHAR(32) DEFAULT NULL",
                "times_total": "ALTER TABLE kamis ADD COLUMN times_total INT DEFAULT NULL",
                "times_remaining": "ALTER TABLE kamis ADD COLUMN times_remaining INT DEFAULT NULL",
                "code_prefix": "ALTER TABLE kamis ADD COLUMN code_prefix VARCHAR(32) DEFAULT NULL",
                "code_length": "ALTER TABLE kamis ADD COLUMN code_length INT DEFAULT NULL",
                "charset": "ALTER TABLE kamis ADD COLUMN charset VARCHAR(32) DEFAULT NULL",
                "code_valid_days": "ALTER TABLE kamis ADD COLUMN code_valid_days INT DEFAULT NULL",
                "code_expires_at": "ALTER TABLE kamis ADD COLUMN code_expires_at DATETIME DEFAULT NULL",
                "bind_ip": "ALTER TABLE kamis ADD COLUMN bind_ip VARCHAR(255) DEFAULT NULL",
                "unbind_count": "ALTER TABLE kamis ADD COLUMN unbind_count INT DEFAULT 0",
                "last_unbind_at": "ALTER TABLE kamis ADD COLUMN last_unbind_at DATETIME DEFAULT NULL",
                "last_verify_at": "ALTER TABLE kamis ADD COLUMN last_verify_at DATETIME DEFAULT NULL",
                "machine_bind_mode": "ALTER TABLE kamis ADD COLUMN machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device'",
                "max_bind_devices": "ALTER TABLE kamis ADD COLUMN max_bind_devices INT DEFAULT 1",
                "authorization_owner": "ALTER TABLE kamis ADD COLUMN authorization_owner VARCHAR(32) DEFAULT 'device'",
                "user_bind_mode": "ALTER TABLE kamis ADD COLUMN user_bind_mode VARCHAR(32) DEFAULT 'none'",
                "created_at": "ALTER TABLE kamis ADD COLUMN created_at DATETIME DEFAULT NULL",
            }
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM kamis")).fetchall()
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(ddl))
                    conn.commit()
            conn.execute(text("""
                UPDATE kamis
                SET max_bind_devices = CASE
                    WHEN machine_bind_mode = 'no_limit' THEN 0
                    WHEN machine_bind_mode = 'one_card_multi_device' THEN 3
                    ELSE 1
                END
                WHERE max_bind_devices IS NULL
                   OR (machine_bind_mode = 'one_card_multi_device' AND max_bind_devices < 2)
                   OR (machine_bind_mode = 'no_limit' AND max_bind_devices != 0)
                   OR (machine_bind_mode = 'one_card_one_device' AND max_bind_devices != 1)
            """))
            conn.commit()

        if "apps" in existing_tables:
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM apps")).fetchall()
            }
            extra_columns = {
                "notice_enabled": "ALTER TABLE apps ADD COLUMN notice_enabled BOOLEAN DEFAULT FALSE",
                "notice_title": "ALTER TABLE apps ADD COLUMN notice_title VARCHAR(128) DEFAULT NULL",
                "notice": "ALTER TABLE apps ADD COLUMN notice TEXT DEFAULT NULL",
                "notice_level": "ALTER TABLE apps ADD COLUMN notice_level VARCHAR(32) DEFAULT 'normal'",
                "notice_popup": "ALTER TABLE apps ADD COLUMN notice_popup BOOLEAN DEFAULT FALSE",
                "version": "ALTER TABLE apps ADD COLUMN version VARCHAR(64) DEFAULT NULL",
                "version_info": "ALTER TABLE apps ADD COLUMN version_info TEXT DEFAULT NULL",
                "force_update": "ALTER TABLE apps ADD COLUMN force_update BOOLEAN DEFAULT FALSE",
                "update_url": "ALTER TABLE apps ADD COLUMN update_url TEXT DEFAULT NULL",
                "update_url_type": "ALTER TABLE apps ADD COLUMN update_url_type VARCHAR(32) DEFAULT 'direct'",
                "download_url": "ALTER TABLE apps ADD COLUMN download_url TEXT DEFAULT NULL",
                "download_note": "ALTER TABLE apps ADD COLUMN download_note TEXT DEFAULT NULL",
                "download_button_text": "ALTER TABLE apps ADD COLUMN download_button_text VARCHAR(64) DEFAULT '立即下载'",
                "signature_required": "ALTER TABLE apps ADD COLUMN signature_required BOOLEAN DEFAULT TRUE",
                "nonce_required": "ALTER TABLE apps ADD COLUMN nonce_required BOOLEAN DEFAULT TRUE",
                "timestamp_tolerance_seconds": "ALTER TABLE apps ADD COLUMN timestamp_tolerance_seconds INT DEFAULT 300",
                "allow_unbind": "ALTER TABLE apps ADD COLUMN allow_unbind BOOLEAN DEFAULT FALSE",
                "max_unbind_count": "ALTER TABLE apps ADD COLUMN max_unbind_count INT DEFAULT 0",
                "unbind_cooldown_hours": "ALTER TABLE apps ADD COLUMN unbind_cooldown_hours INT DEFAULT 24",
                "unbind_deduct_hours": "ALTER TABLE apps ADD COLUMN unbind_deduct_hours INT DEFAULT 0",
                "unbind_deduct_times": "ALTER TABLE apps ADD COLUMN unbind_deduct_times INT DEFAULT 0",
                "ip_lock_enabled": "ALTER TABLE apps ADD COLUMN ip_lock_enabled BOOLEAN DEFAULT FALSE",
                "api_call_count": "ALTER TABLE apps ADD COLUMN api_call_count INT DEFAULT 0",
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(ddl))
                    conn.commit()

        if "api_interfaces" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE api_interfaces (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    interface_key VARCHAR(128) NOT NULL UNIQUE,
                    method VARCHAR(16) DEFAULT 'POST',
                    path VARCHAR(255) NOT NULL,
                    category VARCHAR(64) DEFAULT 'core',
                    description TEXT,
                    auth_mode VARCHAR(64) DEFAULT 'bearer',
                    content_type VARCHAR(128) DEFAULT 'application/json',
                    status INT DEFAULT 1,
                    request_headers_json TEXT,
                    request_params_json TEXT,
                    response_params_json TEXT,
                    success_example_json TEXT,
                    error_example_json TEXT,
                    response_example_json TEXT,
                    doc_markdown TEXT,
                    remark TEXT,
                    sort_order INT DEFAULT 0,
                    is_builtin BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_interface_key (interface_key),
                    INDEX idx_path (path),
                    INDEX idx_category (category),
                    INDEX idx_status (status),
                    INDEX idx_sort_order (sort_order),
                    INDEX idx_is_builtin (is_builtin)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API interface definitions'
            """))
            conn.commit()
        else:
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM api_interfaces")).fetchall()
            }
            extra_columns = {
                "description": "ALTER TABLE api_interfaces ADD COLUMN description TEXT DEFAULT NULL",
                "auth_mode": "ALTER TABLE api_interfaces ADD COLUMN auth_mode VARCHAR(64) DEFAULT 'bearer'",
                "content_type": "ALTER TABLE api_interfaces ADD COLUMN content_type VARCHAR(128) DEFAULT 'application/json'",
                "request_headers_json": "ALTER TABLE api_interfaces ADD COLUMN request_headers_json TEXT DEFAULT NULL",
                "response_params_json": "ALTER TABLE api_interfaces ADD COLUMN response_params_json TEXT DEFAULT NULL",
                "success_example_json": "ALTER TABLE api_interfaces ADD COLUMN success_example_json TEXT DEFAULT NULL",
                "error_example_json": "ALTER TABLE api_interfaces ADD COLUMN error_example_json TEXT DEFAULT NULL",
                "remark": "ALTER TABLE api_interfaces ADD COLUMN remark TEXT DEFAULT NULL",
                "sort_order": "ALTER TABLE api_interfaces ADD COLUMN sort_order INT DEFAULT 0",
                "is_builtin": "ALTER TABLE api_interfaces ADD COLUMN is_builtin BOOLEAN DEFAULT FALSE",
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(ddl))
                    conn.commit()

        if "app_interface_configs" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE app_interface_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64) NOT NULL,
                    interface_id INT NOT NULL,
                    enabled BOOLEAN DEFAULT FALSE,
                    quota_limit INT DEFAULT NULL,
                    expires_at DATETIME DEFAULT NULL,
                    config_json TEXT,
                    remark TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_app_id (app_id),
                    INDEX idx_interface_id (interface_id),
                    INDEX idx_enabled (enabled),
                    INDEX idx_expires_at (expires_at),
                    UNIQUE KEY uk_app_interface_config (app_id, interface_id),
                    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
                    FOREIGN KEY (interface_id) REFERENCES api_interfaces(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Per-app API interface configs'
            """))
            conn.commit()

        if "kami_specs" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE kami_specs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR(64) NOT NULL,
                    spec_key VARCHAR(255) NOT NULL,
                    spec_name VARCHAR(128) NOT NULL,
                    spec_group VARCHAR(32) DEFAULT 'custom',
                    kami_type ENUM('hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime', 'points', 'times') NOT NULL,
                    points_amount INT DEFAULT NULL,
                    points_valid_days INT DEFAULT NULL,
                    time_value INT DEFAULT NULL,
                    time_unit VARCHAR(32) DEFAULT NULL,
                    times_total INT DEFAULT NULL,
                    machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device',
                    max_bind_devices INT DEFAULT 1,
                    authorization_owner VARCHAR(32) DEFAULT 'device',
                    user_bind_mode VARCHAR(32) DEFAULT 'none',
                    status INT DEFAULT 1,
                    sort_order INT DEFAULT 0,
                    remark TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_app_id (app_id),
                    INDEX idx_spec_key (spec_key),
                    INDEX idx_spec_group (spec_group),
                    INDEX idx_kami_type (kami_type),
                    INDEX idx_status (status),
                    INDEX idx_sort_order (sort_order),
                    UNIQUE KEY uk_kami_spec_app_key (app_id, spec_key),
                    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kami specifications'
            """))
            conn.commit()

        if "kami_batches" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE kami_batches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    spec_id INT DEFAULT NULL,
                    app_id VARCHAR(64) NOT NULL,
                    batch_no VARCHAR(64) NOT NULL,
                    kami_type ENUM('hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime', 'points', 'times') NOT NULL,
                    points_amount INT DEFAULT NULL,
                    points_valid_days INT DEFAULT NULL,
                    time_value INT DEFAULT NULL,
                    time_unit VARCHAR(32) DEFAULT NULL,
                    times_total INT DEFAULT NULL,
                    code_prefix VARCHAR(32) DEFAULT NULL,
                    code_length INT DEFAULT 16,
                    charset VARCHAR(32) DEFAULT 'upper_numeric',
                    code_valid_days INT DEFAULT NULL,
                    machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device',
                    max_bind_devices INT DEFAULT 1,
                    authorization_owner VARCHAR(32) DEFAULT 'device',
                    user_bind_mode VARCHAR(32) DEFAULT 'none',
                    status INT DEFAULT 1,
                    remark TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_app_id (app_id),
                    INDEX idx_spec_id (spec_id),
                    INDEX idx_batch_no (batch_no),
                    INDEX idx_kami_type (kami_type),
                    INDEX idx_machine_bind_mode (machine_bind_mode),
                    INDEX idx_authorization_owner (authorization_owner),
                    INDEX idx_user_bind_mode (user_bind_mode),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at),
                    UNIQUE KEY uk_kami_batch_app_batch (app_id, batch_no),
                    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kami batch configs'
            """))
            conn.commit()
        else:
            columns = {
                row[0]
                for row in conn.execute(text("SHOW COLUMNS FROM kami_batches")).fetchall()
            }
            if "spec_id" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN spec_id INT DEFAULT NULL"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_kami_batches_spec_id ON kami_batches (spec_id)"))
                conn.commit()
            if "max_bind_devices" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN max_bind_devices INT DEFAULT 1"))
                conn.commit()
            if "authorization_owner" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN authorization_owner VARCHAR(32) DEFAULT 'device'"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_kami_batches_authorization_owner ON kami_batches (authorization_owner)"))
                conn.commit()
            if "user_bind_mode" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN user_bind_mode VARCHAR(32) DEFAULT 'none'"))
                conn.commit()
                conn.execute(text("CREATE INDEX idx_kami_batches_user_bind_mode ON kami_batches (user_bind_mode)"))
                conn.commit()
            if "code_valid_days" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN code_valid_days INT DEFAULT NULL"))
                conn.commit()
            conn.execute(text("""
                UPDATE kami_batches
                SET max_bind_devices = CASE
                    WHEN machine_bind_mode = 'no_limit' THEN 0
                    WHEN machine_bind_mode = 'one_card_multi_device' THEN 3
                    ELSE 1
                END
                WHERE max_bind_devices IS NULL
                   OR (machine_bind_mode = 'one_card_multi_device' AND max_bind_devices < 2)
                   OR (machine_bind_mode = 'no_limit' AND max_bind_devices != 0)
                   OR (machine_bind_mode = 'one_card_one_device' AND max_bind_devices != 1)
            """))
            conn.commit()

        if "kami_device_bindings" not in existing_tables:
            conn.execute(text(f"""
                CREATE TABLE kami_device_bindings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    app_id VARCHAR({app_id_length}) NOT NULL,
                    kami_code VARCHAR({kami_code_length}) NOT NULL,
                    device_uuid VARCHAR(255) NOT NULL,
                    fingerprint VARCHAR(255) NOT NULL,
                    bind_ip VARCHAR(255) DEFAULT NULL,
                    first_bind_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_verify_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_app_id (app_id),
                    INDEX idx_kami_code (kami_code),
                    INDEX idx_device_uuid (device_uuid),
                    INDEX idx_fingerprint (fingerprint),
                    UNIQUE KEY uk_kami_device_fingerprint (kami_code, fingerprint),
                    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
                    FOREIGN KEY (kami_code) REFERENCES kamis(kami_code) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kami multi-device bindings'
            """))
            conn.commit()


def _ensure_sqlite_schema():
    """Add lightweight local-dev columns that create_all cannot add to existing SQLite files."""
    from sqlalchemy import text

    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "end_users" in tables:
            columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(end_users)")).fetchall()
            }
            if "app_id" not in columns:
                conn.execute(text("ALTER TABLE end_users ADD COLUMN app_id VARCHAR(64) DEFAULT NULL"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_end_users_app_id ON end_users (app_id)"))
                conn.commit()
        if "apps" in tables:
            columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(apps)")).fetchall()
            }
            extra_columns = {
                "notice_enabled": "BOOLEAN DEFAULT 0",
                "notice_title": "VARCHAR(128) DEFAULT NULL",
                "notice": "TEXT DEFAULT NULL",
                "notice_level": "VARCHAR(32) DEFAULT 'normal'",
                "notice_popup": "BOOLEAN DEFAULT 0",
                "version": "VARCHAR(64) DEFAULT NULL",
                "version_info": "TEXT DEFAULT NULL",
                "force_update": "BOOLEAN DEFAULT 0",
                "update_url": "TEXT DEFAULT NULL",
                "update_url_type": "VARCHAR(32) DEFAULT 'direct'",
                "download_url": "TEXT DEFAULT NULL",
                "download_note": "TEXT DEFAULT NULL",
                "download_button_text": "VARCHAR(64) DEFAULT '立即下载'",
                "signature_required": "BOOLEAN DEFAULT 1",
                "nonce_required": "BOOLEAN DEFAULT 1",
                "timestamp_tolerance_seconds": "INTEGER DEFAULT 300",
                "allow_unbind": "BOOLEAN DEFAULT 0",
                "max_unbind_count": "INTEGER DEFAULT 0",
                "unbind_cooldown_hours": "INTEGER DEFAULT 24",
                "unbind_deduct_hours": "INTEGER DEFAULT 0",
                "unbind_deduct_times": "INTEGER DEFAULT 0",
                "ip_lock_enabled": "BOOLEAN DEFAULT 0",
                "api_call_count": "INTEGER DEFAULT 0",
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(f"ALTER TABLE apps ADD COLUMN {column} {ddl}"))
            conn.commit()
        if "api_interfaces" in tables:
            columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(api_interfaces)")).fetchall()
            }
            extra_columns = {
                "description": "TEXT DEFAULT NULL",
                "auth_mode": "VARCHAR(64) DEFAULT 'bearer'",
                "content_type": "VARCHAR(128) DEFAULT 'application/json'",
                "request_headers_json": "TEXT DEFAULT NULL",
                "response_params_json": "TEXT DEFAULT NULL",
                "success_example_json": "TEXT DEFAULT NULL",
                "error_example_json": "TEXT DEFAULT NULL",
                "remark": "TEXT DEFAULT NULL",
                "sort_order": "INTEGER DEFAULT 0",
                "is_builtin": "BOOLEAN DEFAULT 0",
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(f"ALTER TABLE api_interfaces ADD COLUMN {column} {ddl}"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_interfaces_sort_order ON api_interfaces (sort_order)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_interfaces_is_builtin ON api_interfaces (is_builtin)"))
            conn.commit()
        if "kamis" in tables:
            columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(kamis)")).fetchall()
            }
            extra_columns = {
                "spec_id": "INTEGER DEFAULT NULL",
                "time_value": "INTEGER DEFAULT NULL",
                "time_unit": "VARCHAR(32) DEFAULT NULL",
                "times_total": "INTEGER DEFAULT NULL",
                "times_remaining": "INTEGER DEFAULT NULL",
                "code_prefix": "VARCHAR(32) DEFAULT NULL",
                "code_length": "INTEGER DEFAULT NULL",
                "charset": "VARCHAR(32) DEFAULT NULL",
                "code_valid_days": "INTEGER DEFAULT NULL",
                "code_expires_at": "DATETIME DEFAULT NULL",
                "bind_ip": "VARCHAR(255) DEFAULT NULL",
                "unbind_count": "INTEGER DEFAULT 0",
                "last_unbind_at": "DATETIME DEFAULT NULL",
                "last_verify_at": "DATETIME DEFAULT NULL",
                "machine_bind_mode": "VARCHAR(32) DEFAULT 'one_card_one_device'",
                "max_bind_devices": "INTEGER DEFAULT 1",
                "authorization_owner": "VARCHAR(32) DEFAULT 'device'",
                "user_bind_mode": "VARCHAR(32) DEFAULT 'none'",
                "created_at": "DATETIME DEFAULT NULL",
            }
            for column, ddl in extra_columns.items():
                if column not in columns:
                    conn.execute(text(f"ALTER TABLE kamis ADD COLUMN {column} {ddl}"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_spec_id ON kamis (spec_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_times_remaining ON kamis (times_remaining)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_machine_bind_mode ON kamis (machine_bind_mode)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_authorization_owner ON kamis (authorization_owner)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_user_bind_mode ON kamis (user_bind_mode)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_created_at ON kamis (created_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kamis_code_expires_at ON kamis (code_expires_at)"))
            conn.execute(text("""
                UPDATE kamis
                SET max_bind_devices = CASE
                    WHEN machine_bind_mode = 'no_limit' THEN 0
                    WHEN machine_bind_mode = 'one_card_multi_device' THEN 3
                    ELSE 1
                END
                WHERE max_bind_devices IS NULL
                   OR (machine_bind_mode = 'one_card_multi_device' AND max_bind_devices < 2)
                   OR (machine_bind_mode = 'no_limit' AND max_bind_devices != 0)
                   OR (machine_bind_mode = 'one_card_one_device' AND max_bind_devices != 1)
            """))
            conn.commit()
        if "kami_batches" in tables:
            columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(kami_batches)")).fetchall()
            }
            if "spec_id" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN spec_id INTEGER DEFAULT NULL"))
            if "max_bind_devices" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN max_bind_devices INTEGER DEFAULT 1"))
            if "authorization_owner" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN authorization_owner VARCHAR(32) DEFAULT 'device'"))
            if "user_bind_mode" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN user_bind_mode VARCHAR(32) DEFAULT 'none'"))
            if "code_valid_days" not in columns:
                conn.execute(text("ALTER TABLE kami_batches ADD COLUMN code_valid_days INTEGER DEFAULT NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kami_batches_spec_id ON kami_batches (spec_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kami_batches_authorization_owner ON kami_batches (authorization_owner)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_kami_batches_user_bind_mode ON kami_batches (user_bind_mode)"))
            conn.execute(text("""
                UPDATE kami_batches
                SET max_bind_devices = CASE
                    WHEN machine_bind_mode = 'no_limit' THEN 0
                    WHEN machine_bind_mode = 'one_card_multi_device' THEN 3
                    ELSE 1
                END
                WHERE max_bind_devices IS NULL
                   OR (machine_bind_mode = 'one_card_multi_device' AND max_bind_devices < 2)
                   OR (machine_bind_mode = 'no_limit' AND max_bind_devices != 0)
                   OR (machine_bind_mode = 'one_card_one_device' AND max_bind_devices != 1)
            """))
            conn.commit()


def wait_for_db(max_retries=30, retry_interval=2):
    """
    等待数据库就绪
    
    Args:
        max_retries: 最大重试次数
        retry_interval: 重试间隔（秒）
    """
    import sys
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            msg = f"✅ Database connection successful (attempt {attempt})"
            debug_print(msg)
            return True
        except Exception as e:
            msg = f"⚠️  Database connection failed (attempt {attempt}/{max_retries}): {e}"
            debug_print(msg)
            if attempt < max_retries:
                time.sleep(retry_interval)
            else:
                msg = "❌ Failed to connect to database after maximum retries"
                print(msg, flush=True)  # 关键错误，始终打印
                sys.stdout.flush()
                raise


def init_db():
    """初始化数据库表"""
    import sys
    from models import SQLModel, AdminUser
    from passlib.context import CryptContext
    from sqlalchemy import text

    if engine.dialect.name == "sqlite":
        SQLModel.metadata.create_all(engine)
        _ensure_sqlite_schema()
        from kami_spec_service import backfill_specs_for_session
        with Session(engine) as session:
            backfill_specs_for_session(session)
        _init_default_admin()
        msg = "SQLite database initialized successfully"
        debug_print(msg)
        return
    
    # 等待数据库就绪
    wait_for_db()
    
    # 检查表是否已存在
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        existing_tables = [row[0] for row in result.fetchall()]
    
    # 如果表已存在，跳过创建（保留数据）
    required_tables = ['admin_users', 'apps', 'kamis', 'devices', 'event_logs', 'app_authorizations']
    tables_exist = all(table in existing_tables for table in required_tables)
    
    if tables_exist:
        msg = "ℹ️  Database tables already exist, skipping creation"
        debug_print(msg)
    else:
        # 只在表不存在时才创建
        msg = "🔨 Creating database tables..."
        print(msg, flush=True)  # 重要信息，始终打印
        sys.stdout.flush()
        
        with engine.connect() as conn:
            # 1. 创建 admin_users 表
            if 'admin_users' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE admin_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        phone VARCHAR(255),
                        is_admin BOOLEAN DEFAULT FALSE,
                        status INT DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_login DATETIME,
                        failed_attempts INT DEFAULT 0,
                        locked_until DATETIME,
                        INDEX idx_username (username)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员用户表'
                """))
                conn.commit()
                msg = "✅ Created admin_users table"
                debug_print(msg)
            
            # 2. 创建 apps 表（app_id 使用 VARCHAR(64)）
            if 'apps' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE apps (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64) NOT NULL UNIQUE,
                        name VARCHAR(255) NOT NULL,
                        app_secret VARCHAR(255) NOT NULL,
                        rsa_public_key TEXT NOT NULL,
                        rsa_private_key TEXT NOT NULL,
                        status INT DEFAULT 1,
                        created_by VARCHAR(255),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        notice TEXT,
                        version VARCHAR(64),
                        version_info TEXT,
                        force_update BOOLEAN DEFAULT FALSE,
                        update_url TEXT,
                        update_url_type VARCHAR(32) DEFAULT 'direct',
                        download_url TEXT,
                        download_note TEXT,
                        signature_required BOOLEAN DEFAULT TRUE,
                        nonce_required BOOLEAN DEFAULT TRUE,
                        timestamp_tolerance_seconds INT DEFAULT 300,
                        allow_unbind BOOLEAN DEFAULT FALSE,
                        max_unbind_count INT DEFAULT 0,
                        unbind_cooldown_hours INT DEFAULT 24,
                        unbind_deduct_hours INT DEFAULT 0,
                        unbind_deduct_times INT DEFAULT 0,
                        ip_lock_enabled BOOLEAN DEFAULT FALSE,
                        api_call_count INT DEFAULT 0,
                        INDEX idx_app_id (app_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用表'
                """))
                conn.commit()
                msg = "✅ Created apps table"
                debug_print(msg)
            
            # 3. 创建 kamis 表
            if 'kamis' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE kamis (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64) NOT NULL,
                        kami_code VARCHAR(255) NOT NULL UNIQUE,
                        kami_type ENUM('hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime', 'points', 'times') NOT NULL,
                        status ENUM('unused', 'active', 'frozen') DEFAULT 'unused',
                        bind_uuid VARCHAR(255),
                        activate_time DATETIME,
                        expire_time DATETIME,
                        time_value INT,
                        time_unit VARCHAR(32),
                        times_total INT,
                        times_remaining INT,
                        code_prefix VARCHAR(32),
                        code_length INT,
                        charset VARCHAR(32),
                        code_valid_days INT,
                        code_expires_at DATETIME,
                        bind_ip VARCHAR(255),
                        unbind_count INT DEFAULT 0,
                        last_unbind_at DATETIME,
                        last_verify_at DATETIME,
                        machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device',
                        max_bind_devices INT DEFAULT 1,
                        authorization_owner VARCHAR(32) DEFAULT 'device',
                        user_bind_mode VARCHAR(32) DEFAULT 'none',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        points_amount INT,
                        batch_no VARCHAR(64),
                        points_valid_days INT,
                        redeemed_by_user_id INT,
                        redeemed_at DATETIME,
                        INDEX idx_app_id (app_id),
                        INDEX idx_kami_code (kami_code),
                        INDEX idx_batch_no (batch_no),
                        INDEX idx_times_remaining (times_remaining),
                        INDEX idx_code_expires_at (code_expires_at),
                        INDEX idx_machine_bind_mode (machine_bind_mode),
                        INDEX idx_authorization_owner (authorization_owner),
                        INDEX idx_user_bind_mode (user_bind_mode),
                        INDEX idx_created_at (created_at),
                        FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡密表'
                """))
                conn.commit()
                msg = "✅ Created kamis table"
                debug_print(msg)
            
            # 4. 创建 devices 表
            if 'devices' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE devices (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64) NOT NULL,
                        uuid VARCHAR(255) NOT NULL,
                        fingerprint TEXT NOT NULL,
                        last_ip VARCHAR(255),
                        risk_level INT DEFAULT 0,
                        INDEX idx_app_id (app_id),
                        INDEX idx_uuid (uuid),
                        FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='设备表'
                """))
                conn.commit()
                msg = "✅ Created devices table"
                debug_print(msg)

            if 'kami_device_bindings' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE kami_device_bindings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64) NOT NULL,
                        kami_code VARCHAR(255) NOT NULL,
                        device_uuid VARCHAR(255) NOT NULL,
                        fingerprint VARCHAR(255) NOT NULL,
                        bind_ip VARCHAR(255),
                        first_bind_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_verify_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_app_id (app_id),
                        INDEX idx_kami_code (kami_code),
                        INDEX idx_device_uuid (device_uuid),
                        INDEX idx_fingerprint (fingerprint),
                        UNIQUE KEY uk_kami_device_fingerprint (kami_code, fingerprint),
                        FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE,
                        FOREIGN KEY (kami_code) REFERENCES kamis(kami_code) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='卡密多设备绑定表'
                """))
                conn.commit()
                msg = "✅ Created kami_device_bindings table"
                debug_print(msg)
            
            # 5. 创建 event_logs 表
            if 'event_logs' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE event_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64),
                        kami_code VARCHAR(255),
                        event_type VARCHAR(255) NOT NULL,
                        ip_address VARCHAR(255),
                        device_uuid VARCHAR(255),
                        user_agent TEXT,
                        payload TEXT,
                        status INT DEFAULT 1,
                        message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_app_id (app_id),
                        INDEX idx_kami_code (kami_code),
                        INDEX idx_event_type (event_type),
                        INDEX idx_created_at (created_at),
                        FOREIGN KEY (kami_code) REFERENCES kamis(kami_code) ON DELETE SET NULL
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件日志表'
                """))
                conn.commit()
                msg = "✅ Created event_logs table"
                debug_print(msg)
            
            # 6. 创建 app_authorizations 表（app_id 同样使用 VARCHAR(64)）
            if 'app_authorizations' not in existing_tables:
                conn.execute(text("""
                    CREATE TABLE app_authorizations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        app_id VARCHAR(64) NOT NULL,
                        username VARCHAR(255) NOT NULL,
                        granted_by VARCHAR(255) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_username (username),
                        INDEX idx_app_id (app_id),
                        FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='应用授权表'
                """))
                conn.commit()
                msg = "✅ Created app_authorizations table"
                debug_print(msg)
        
        msg = "✅ All database tables created successfully"
        debug_print(msg)

    _ensure_points_schema()

    # create_all is non-destructive and adds newer SQLModel tables that are not
    # covered by the legacy hand-written bootstrap path.
    SQLModel.metadata.create_all(engine)
    
    _ensure_points_schema()

    from kami_spec_service import backfill_specs_for_session
    with Session(engine) as session:
        backfill_specs_for_session(session)

    # 初始化默认 admin 用户
    _init_default_admin()


def get_session():
    """获取数据库会话"""
    with Session(engine) as session:
        yield session


def _init_default_admin():
    """初始化默认 admin 用户（如果不存在）"""
    from models import AdminUser
    from sqlmodel import select
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(password: str) -> str:
        """密码哈希（使用 SHA256 + salt）"""
        return pwd_context.hash(password)
    
    with Session(engine) as session:
        # 检查是否已有 admin 用户
        statement = select(AdminUser).where(AdminUser.username == "admin")
        existing_admin = session.exec(statement).first()
        
        if not existing_admin:
            if not settings.BOOTSTRAP_ADMIN_PASSWORD:
                msg = "BOOTSTRAP_ADMIN_PASSWORD is not set; skipping admin bootstrap"
                debug_print(msg)
                return

            # 创建默认 admin 用户
            default_admin = AdminUser(
                username="admin",
                password_hash="",
                is_admin=True,
                status=1
            )
            default_admin.password_hash = hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD)
            session.add(default_admin)
            session.commit()
            msg = "Bootstrap admin user created (username: admin)"
            debug_print(msg)
        else:
            msg = "ℹ️  Admin user already exists"
            debug_print(msg)
