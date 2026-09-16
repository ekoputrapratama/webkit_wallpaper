import zipfile

import webkit_wallpaper.themes as themes


def _make_theme_dir(root, name, thumb="thumb.png", entry="index.html"):
    theme_dir = root / name
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "index.html").write_text("<!doctype html><html></html>")
    (theme_dir / thumb).write_bytes(b"\x89PNG\r\n")
    (theme_dir / f"{name}.theme").write_text(
        "[Theme]\n"
        f"Name={name}\n"
        f"Description=Test\n"
        f"Author=tester\n"
        f"Version=1.0\n"
        f"Thumbnail={thumb}\n"
        f"Entry={entry}\n"
    )
    return theme_dir


def test_parse_theme_file_valid(tmp_path):
    theme_dir = _make_theme_dir(tmp_path, "sakura")
    meta = themes._parse_theme_file(theme_dir / "sakura.theme")
    assert meta is not None
    assert meta["name"] == "sakura"
    assert meta["thumbnail"] == "thumb.png"
    assert meta["entry"] == "index.html"


def test_parse_theme_file_missing_section(tmp_path):
    p = tmp_path / "bad.theme"
    p.write_text("[Other]\nName=x\n")
    assert themes._parse_theme_file(str(p)) is None


def test_parse_theme_file_defaults_entry(tmp_path):
    p = tmp_path / "theme.theme"
    p.write_text("[Theme]\nName=noentry\n")
    meta = themes._parse_theme_file(str(p))
    assert meta["entry"] == "index.html"
    assert meta["thumbnail"] == ""


def test_scan_themes_finds_valid_dirs(tmp_path, monkeypatch):
    system = tmp_path / "system"
    user = tmp_path / "user"
    system.mkdir(); user.mkdir()
    _make_theme_dir(system, "sakura")
    _make_theme_dir(user, "custom", thumb="preview.png")
    (user / "custom" / "custom.theme").write_text(
        "[Theme]\nName=custom\nThumbnail=preview.png\nEntry=index.html\n"
    )
    # a bad dir: theme file missing
    (user / "broken").mkdir()
    monkeypatch.setattr(themes, "SYSTEM_THEMES_DIR", str(system))
    monkeypatch.setattr(themes, "USER_THEMES_DIR", str(user))
    result = themes.scan_themes()
    ids = {t["id"] for t in result}
    assert ids == {"sakura", "custom"}
    custom = next(t for t in result if t["id"] == "custom")
    assert custom["user"] is True
    assert custom["thumbnail_path"] == str(user / "custom" / "preview.png")
    sakura = next(t for t in result if t["id"] == "sakura")
    assert sakura["user"] is False
    assert sakura["thumbnail_path"] == str(system / "sakura" / "thumb.png")


def test_scan_themes_ignores_non_dirs_and_broken(tmp_path, monkeypatch):
    system = tmp_path / "system"
    user = tmp_path / "user"
    system.mkdir(); user.mkdir()
    (system / "notadir.txt").write_text("x")
    (system / "nodir.theme").write_text("[Theme]\nName=x\n")
    (system / "sub").mkdir()
    monkeypatch.setattr(themes, "SYSTEM_THEMES_DIR", str(system))
    monkeypatch.setattr(themes, "USER_THEMES_DIR", str(user))
    assert themes.scan_themes() == []


def test_get_theme_entry_uri_constructs_file_uri():
    theme = {"entry_path": "/home/user/theme/index.html"}
    assert themes.get_theme_entry_uri(theme) == "file:///home/user/theme/index.html"


def test_get_theme_entry_uri_missing_entry_path():
    assert themes.get_theme_entry_uri({"entry_path": ""}) == ""


def test_install_theme_from_zip(tmp_path, monkeypatch):
    user = tmp_path / "user"
    user.mkdir()
    zip_path = tmp_path / "theme.zip"
    src = _make_theme_dir(tmp_path, "sakura")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in ("sakura/sakura.theme", "sakura/index.html", "sakura/thumb.png"):
            zf.write(src.parent / f, arcname=f)
    monkeypatch.setattr(themes, "USER_THEMES_DIR", str(user))
    meta, err = themes.install_theme(str(zip_path))
    assert err is None
    assert meta["id"] == "sakura"
    assert (user / "sakura" / "index.html").is_file()
    assert meta["entry_path"].endswith("index.html")


def test_install_theme_rejects_non_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(themes, "USER_THEMES_DIR", str(tmp_path / "user"))
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    meta, err = themes.install_theme(str(bad))
    assert meta is None
    assert err


def test_uninstall_theme_removes_dir(tmp_path, monkeypatch):
    user = tmp_path / "user"
    (user / "sakura").mkdir(parents=True)
    monkeypatch.setattr(themes, "USER_THEMES_DIR", str(user))
    assert themes.uninstall_theme("sakura") is True
    assert not (user / "sakura").exists()
    assert themes.uninstall_theme("sakura") is False
