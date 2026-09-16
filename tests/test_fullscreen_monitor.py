# Copyright (c) 2026 webkit_wallpaper contributors.
# Licensed under the MIT License (see LICENSE).
"""Tests for webkit_wallpaper.fullscreen_monitor (headless logic).

We exercise the pure decision helpers (atom parsing / active-window
detection) and the FullscreenMonitor state machine by monkeypatching the
subprocess/xprop plumbing — no display required.
"""

import webkit_wallpaper.fullscreen_monitor as fm
from webkit_wallpaper.fullscreen_monitor import FullscreenMonitor


def test_active_window_id_parses_xprop_output(monkeypatch):
    monkeypatch.setattr(
        fm,
        "_run",
        lambda *a, **k: "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x3800001",
    )
    assert fm._active_window_id() == "0x3800001"


def test_active_window_id_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(fm, "_run", lambda *a, **k: "")
    assert fm._active_window_id() is None


def test_window_is_fullscreen_checks_state(monkeypatch):
    monkeypatch.setattr(
        fm,
        "_run",
        lambda *a, **k: "_NET_WM_STATE: _NET_WM_STATE_FULLSCREEN, _NET_WM_STATE_MODAL",
    )
    assert fm._window_is_fullscreen("0x3800001") is True
    monkeypatch.setattr(fm, "_run", lambda *a, **k: "_NET_WM_STATE: (no state)")
    assert fm._window_is_fullscreen("0x3800001") is False


def test_window_is_fullscreen_false_for_empty_id():
    assert fm._window_is_fullscreen("") is False
    assert fm._window_is_fullscreen(None) is False


def test_fullscreen_monitor_transitions_and_callbacks():
    events = []
    mon = FullscreenMonitor(
        on_fullscreen=lambda: events.append("full"),
        on_restore=lambda: events.append("restore"),
    )
    mon.start()
    assert mon.is_fullscreen is False
    mon._set_fullscreen(True)
    assert mon.is_fullscreen is True
    assert events == ["full"]
    mon._set_fullscreen(False)
    assert mon.is_fullscreen is False
    assert events == ["full", "restore"]
    # Same state twice -> no duplicate callbacks
    mon._set_fullscreen(False)
    assert events == ["full", "restore"]
    mon.stop()


def test_tick_sets_fullscreen_when_active_window_fullscreen(monkeypatch):
    events = []
    mon = FullscreenMonitor(on_fullscreen=lambda: events.append("full"))
    mon._enabled = True
    monkeypatch.setattr(fm, "_active_window_id", lambda: "0x1")
    monkeypatch.setattr(fm, "_window_is_fullscreen", lambda wid: True)
    mon._tick()
    assert mon.is_fullscreen is True
    assert events == ["full"]
    mon.stop()
