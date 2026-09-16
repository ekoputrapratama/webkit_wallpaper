# Copyright (c) 2026 webkit_wallpaper contributors.
# Licensed under the MIT License (see LICENSE).
"""Tests for webkit_wallpaper.autostart.

These cover the pure autostart .desktop file logic using tmp dirs (no
real $HOME, no display, no external executables).
"""

import os

import webkit_wallpaper.autostart as autostart


def test_is_enabled_false_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    assert autostart.is_enabled() is False


def test_enable_writes_desktop_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    autostart.enable()
    assert autostart.is_enabled() is True
    content = (tmp_path / "webkit_wallpaper.desktop").read_text()
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "webkit_wallpaper" in content


def test_disable_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    autostart.enable()
    autostart.disable()
    assert autostart.is_enabled() is False
    assert not (tmp_path / "webkit_wallpaper.desktop").exists()


def test_disable_is_idempotent_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    autostart.disable()  # no file present
    assert autostart.is_enabled() is False


def test_toggle_flips_state(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    assert autostart.toggle() is True
    assert autostart.is_enabled() is True
    assert autostart.toggle() is False
    assert autostart.is_enabled() is False


def test_desktop_content_is_formatted_with_exec(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "AUTOSTART_DIR", str(tmp_path))
    monkeypatch.setattr(
        autostart, "DESKTOP_FILE", str(tmp_path / "webkit_wallpaper.desktop")
    )
    autostart.enable()
    content = (tmp_path / "webkit_wallpaper.desktop").read_text()
    assert "Exec=" in content
    assert content.index("Exec=") > content.index("[Desktop Entry]")
