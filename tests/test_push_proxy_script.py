from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "push_github_with_proxy.ps1"


def test_proxy_push_script_exists_and_updates_git_proxy_before_push():
    assert SCRIPT.exists(), "scripts/push_github_with_proxy.ps1 should exist"

    content = SCRIPT.read_text(encoding="utf-8")

    assert "Internet Settings" in content
    assert "ProxyServer" in content
    assert "Test-NetConnection" in content
    assert "git config --global http.proxy" in content
    assert "git config --global https.proxy" in content
    assert "git push --dry-run" in content
    assert "git push" in content
    assert "origin" in content
    assert "main" in content
