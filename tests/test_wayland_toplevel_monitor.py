import ctypes
# Copyright (c) 2026 webkit_wallpaper contributors.
# Licensed under the MIT License (see LICENSE).
"""Tests for webkit_wallpaper.wayland_toplevel_monitor.

We exercise the pure protocol/state-building helpers headlessly. The live
Wayland display connection is intentionally never attempted here, so these
tests run on any machine (CI, minimal containers, etc.).
"""

import ctypes

import webkit_wallpaper.wayland_toplevel_monitor as w


def test_protocol_build_returns_registry_interface():
    defs = w._build_protocol_definitions()
    assert "registry_interface" in defs
    assert defs["registry_interface"].name == b"wl_registry"
    assert defs["registry_interface"].version == 1


def test_protocol_has_cosmic_interfaces():
    defs = w._build_protocol_definitions()
    assert b"zcosmic_toplevel_handle_v1" in defs["handle_interface"].name
    assert b"zcosmic_toplevel_info_v1" in defs["info_interface"].name
    assert defs["info_interface"].version >= 1


def test_state_constants_exist():
    assert w.STATE_ACTIVATED is not None
    assert w.STATE_FULLSCREEN is not None
    assert w.STATE_ACTIVATED != w.STATE_FULLSCREEN


def test_info_events_include_toplevel_and_handle_has_state():
    defs = w._build_protocol_definitions()
    info_events = []
    for i in range(defs["info_interface"].event_count):
        ev_u = defs["info_interface"].events[i]
        info_events.append(ctypes.string_at(ev_u.name))
    assert b"toplevel" in info_events
    handle_events = []
    for i in range(defs["handle_interface"].event_count):
        ev_u = defs["handle_interface"].events[i]
        handle_events.append(ctypes.string_at(ev_u.name))
    assert b"state" in handle_events
