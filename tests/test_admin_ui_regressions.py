from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_end_users_page_keeps_batch_delete_button_between_export_and_refresh():
    source = read_text("admin/src/views/EndUsers.vue")

    assert '@selection-change="handleSelectionChange"' in source
    assert 'type="selection"' in source
    assert "handleDeleteSelectedUsers" in source
    assert "永久删除" in source
    assert "无法恢复" in source

    export_index = source.index("handleExportUsers")
    delete_index = source.index("handleDeleteSelectedUsers")
    refresh_index = source.index("loadData")
    assert export_index < delete_index < refresh_index


def test_end_users_page_displays_last_login_from_api_payload():
    source = read_text("admin/src/views/EndUsers.vue")

    assert 'prop="last_login"' in source
    assert 'label="最近登录"' in source
    assert "formatOptionalTime(row.last_login)" in source


def test_points_api_exports_batch_delete_end_users_request():
    source = read_text("admin/src/api/points.js")

    assert "export function deleteEndUsers" in source
    assert "url: '/admin/end-users/delete'" in source
    assert "method: 'post'" in source
