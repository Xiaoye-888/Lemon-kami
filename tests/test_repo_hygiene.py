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
