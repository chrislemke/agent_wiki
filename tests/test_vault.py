from pathlib import Path

from conftest import make_vault, run_script


def test_detect_from_vault_root_prints_root(vault: Path):
    r = run_script("vault.py", "detect", cwd=vault)
    assert r.code == 0, r
    assert r.out.strip() == str(vault)


def test_detect_from_subdirectory_walks_up(vault: Path):
    sub = vault / "wiki" / "entities"
    r = run_script("vault.py", "detect", "--json", cwd=sub)
    assert r.code == 0, r
    data = r.json()
    assert data["root"] == str(vault)
    assert data["schema_version"] == 1
    assert data["plugin_version"] == "0.1.0"


def test_detect_outside_vault_exits_one_silently_on_stdout(tmp_path: Path):
    r = run_script("vault.py", "detect", cwd=tmp_path)
    assert r.code == 1
    assert r.out == ""
    assert "no vault" in r.err.lower()


def test_detect_accepts_explicit_path(tmp_path: Path):
    v = make_vault(tmp_path / "elsewhere")
    r = run_script("vault.py", "detect", str(v / "raw"), cwd=tmp_path)
    assert r.code == 0
    assert r.out.strip() == str(v)
