from pathlib import Path


def test_legacy_root_init_sql_is_not_kept_as_runtime_schema_source():
    assert not Path("init.sql").exists()


def test_end_user_routes_do_not_import_admin_router_module():
    source = Path("routes_user.py").read_text(encoding="utf-8")
    assert "from routes_admin import hash_password, verify_password" not in source


def test_public_docs_routes_do_not_import_admin_router_module():
    source = Path("routes_docs.py").read_text(encoding="utf-8")
    assert "from routes_admin import" not in source


def test_app_model_and_database_bootstrap_do_not_keep_legacy_app_content_fields():
    model_source = Path("models.py").read_text(encoding="utf-8")
    database_source = Path("database.py").read_text(encoding="utf-8")
    legacy_fields = [
        "notice_enabled",
        "notice_title",
        "notice_level",
        "notice_popup",
        "version_info",
        "update_url_type",
        "download_button_text",
    ]

    for field in legacy_fields:
        assert field not in model_source
        assert field not in database_source


def test_legacy_app_field_migration_script_is_removed():
    assert not Path("migrate_add_app_fields.py").exists()


def test_reset_password_script_reads_secrets_from_env_or_prompt_only():
    source = Path("reset_password.py").read_text(encoding="utf-8")

    assert "getpass.getpass" in source
    assert "RESET_ADMIN_PASSWORD" in source
    assert "RESET_MYSQL_PASSWORD" in source
    assert "MYSQL_PWD" in source
    assert "-p{mysql_password}" not in source
    assert 'new_password = "' not in source
    assert 'mysql_password = "' not in source


def test_builtin_sdk_clients_send_device_info_device_id_without_legacy_request_fields():
    source_by_path = {
        "python": Path("sdk/python_sdk/lemon_kami.py").read_text(encoding="utf-8"),
        "js": Path("sdk/js_sdk/lemon-kami.js").read_text(encoding="utf-8"),
        "js_complete": Path("sdk/js_sdk/lemon-kami-complete.js").read_text(encoding="utf-8"),
        "admin_public_js": Path("admin/public/sdk/lemon-kami.js").read_text(encoding="utf-8"),
        "java": Path("sdk/java_sdk/src/main/java/com/lemon/kami/LemonKamiSDK.java").read_text(encoding="utf-8"),
    }

    assert '"fingerprint": self.fingerprint' not in source_by_path["python"]
    assert '"fingerprint": this.fingerprint' not in source_by_path["js"]
    assert '"fingerprint": this.fingerprint' not in source_by_path["js_complete"]
    assert '"fingerprint": this.fingerprint' not in source_by_path["admin_public_js"]
    assert '"uuid": this.deviceUuid' not in source_by_path["js"]
    assert '"uuid": this.deviceUuid' not in source_by_path["js_complete"]
    assert '"uuid": this.deviceUuid' not in source_by_path["admin_public_js"]
    assert 'requestData.put("fingerprint"' not in source_by_path["java"]
    assert 'requestData.put("uuid"' not in source_by_path["java"]

    assert '"device_info": self.device_info' in source_by_path["python"]
    assert "device_info: this.deviceInfo" in source_by_path["js"]
    assert "device_info: this.deviceInfo" in source_by_path["js_complete"]
    assert "device_info: this.deviceInfo" in source_by_path["admin_public_js"]
    assert 'requestData.put("device_info", deviceInfo)' in source_by_path["java"]
