from pathlib import Path


def test_legacy_root_init_sql_is_not_kept_as_runtime_schema_source():
    assert not Path("init.sql").exists()


def test_end_user_routes_do_not_import_admin_router_module():
    source = Path("routes_user.py").read_text(encoding="utf-8")
    assert "from routes_admin import hash_password, verify_password" not in source


def test_public_docs_routes_do_not_import_admin_router_module():
    source = Path("routes_docs.py").read_text(encoding="utf-8")
    assert "from routes_admin import" not in source
