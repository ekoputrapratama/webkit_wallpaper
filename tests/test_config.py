import json

from webkit_wallpaper import config


def test_load_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    result = config.load()
    expected = set(config.DEFAULT_CONFIG.keys())
    assert set(result.keys()) == expected
    # defaults are fresh copies, not a shared mutable reference
    assert result is not config.DEFAULT_CONFIG
    assert result["mute_audio"] is True
    assert result["zoom"] == 1.0


def test_load_merges_saved_over_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    (tmp_path / "config.json").write_text(json.dumps({"mute_audio": False}))
    result = config.load()
    assert result["mute_audio"] is False
    assert result["zoom"] == 1.0  # default preserved


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    data = dict(config.DEFAULT_CONFIG)
    data["url"] = "https://example.com"
    data["fps_cap"] = 30
    config.save(data)
    reloaded = config.load()
    assert reloaded["url"] == "https://example.com"
    assert reloaded["fps_cap"] == 30


def test_update_persists_and_returns_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    result = config.update("zoom", 1.5)
    assert result["zoom"] == 1.5
    assert config.load()["zoom"] == 1.5


def test_ensure_config_dir_creates(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "dir"
    monkeypatch.setattr(config, "CONFIG_DIR", str(target))
    config.ensure_config_dir()
    assert target.is_dir()
