# Copyright (c) 2026 webkit_wallpaper contributors.
# Licensed under the MIT License (see LICENSE).
"""Tests for webkit_wallpaper.dotenv (pure .env parsing).

These tests exercise only the pure file-parsing / env helpers and do not
require a display, GTK, or a running compositor.
"""

import webkit_wallpaper.dotenv as dotenv


def test_parse_value_strips_quotes_and_whitespace():
    assert dotenv._parse_value('"hello"') == "hello"
    assert dotenv._parse_value("'world'") == "world"
    assert dotenv._parse_value("  padded  ") == "padded"
    assert dotenv._parse_value('"unbalanced') == '"unbalanced'


def test_load_env_parses_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        '# comment\n\n'
        'FIREBASE_PROJECT_ID="project-abc"\n'
        "FIRESTORE_API_KEY='key-123'\n"
        "EMPTY=\n"
    )
    monkeypatch.setattr(dotenv, "_find_env_file", lambda: str(env))
    monkeypatch.setattr(dotenv, "_ENV", None)
    result = dotenv.load_env()
    assert result.get("FIREBASE_PROJECT_ID") == "project-abc"
    assert result.get("FIRESTORE_API_KEY") == "key-123"
    assert result.get("EMPTY") == ""


def test_load_env_ignores_malformed_and_commented_lines(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "GOOD=1\n"
        "# comment\n"
        "no equals here\n"
        "=orphan\n"
        "\n"
    )
    monkeypatch.setattr(dotenv, "_find_env_file", lambda: str(env))
    monkeypatch.setattr(dotenv, "_ENV", None)
    result = dotenv.load_env()
    assert result.get("GOOD") == "1"
    assert "comment" not in " ".join(result.values())
    assert "orphan" not in " ".join(result.values())


def test_load_env_no_file_returns_empty(monkeypatch):
    monkeypatch.setattr(dotenv, "_find_env_file", lambda: None)
    monkeypatch.setattr(dotenv, "_ENV", None)
    assert dotenv.load_env() == {}


def test_get_with_missing_key_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(dotenv, "_find_env_file", lambda: None)
    monkeypatch.setattr(dotenv, "_ENV", None)
    assert dotenv.get("WEBKIT_WALLPAPER_MISSING", "fallback") == "fallback"
    assert dotenv.get("WEBKIT_WALLPAPER_MISSING") == ""
