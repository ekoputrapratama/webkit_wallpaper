import logging
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

logger = logging.getLogger(__name__)

FULLSCREEN_ATOM = "_NET_WM_STATE_FULLSCREEN"
ACTIVE_ATOM = "_NET_ACTIVE_WINDOW"
STATE_ATOM = "_NET_WM_STATE"

POLL_MS = 750


def _has_xprop():
    for path in (
            "/usr/bin/xprop",
            "/bin/xprop",
            "/usr/local/bin/xprop",
    ):
        if os.path.exists(path):
            return True
    try:
        subprocess.run(
            ["xprop", "-root", "-notype", ACTIVE_ATOM],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return True
    except Exception:
        return False


def _run(cmd, timeout=3):
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return proc.stdout.decode("utf-8", "replace")
    except Exception as e:
        logger.debug("fullscreen_monitor._run() %s failed: %s", cmd, e)
        return ""


def _active_window_id():
    out = _run(["xprop", "-root", "-notype", ACTIVE_ATOM])
    for line in out.splitlines():
        if ACTIVE_ATOM in line:
            parts = line.split()
            for part in parts:
                if part.startswith("0x") and part != "0x0":
                    return part
    return None


def _window_is_fullscreen(window_id):
    if not window_id:
        return False
    out = _run(["xprop", "-id", window_id, "-notype", STATE_ATOM])
    return FULLSCREEN_ATOM in out


def create_monitor(on_fullscreen=None, on_restore=None):
    """Return the best available fullscreen-detection monitor.

    Prefers the native Wayland monitor (COSMIC ``zcosmic_toplevel_info_v1``)
    which can see native Wayland windows that EWMH/``xprop`` cannot; falls
    back to the X11 EWMH monitor otherwise.
    """
    from webkit_wallpaper.wayland_toplevel_monitor import (
        WaylandToplevelMonitor,
    )
    monitor = WaylandToplevelMonitor(on_fullscreen, on_restore)
    if monitor.is_available:
        return monitor
    return FullscreenMonitor(on_fullscreen, on_restore)


class FullscreenMonitor:
    """Polls the window manager to detect when an app other than the
    wallpaper goes fullscreen, then calls the registered callbacks.

    Detection strategies (in order of availability):

    * X11 EWWM (works for X11 sessions and XWayland windows). If the
      active window carries ``_NET_WM_STATE_FULLSCREEN`` in its
      ``_NET_WM_STATE``, we consider an app fullscreen.
    * KDE Wayland native windows are only reachable through the KWin
      scripting bridge, which is not installed out of the box; when no
      X11 detection applies we gracefully disable and log a hint.
    """

    def __init__(self, on_fullscreen=None, on_restore=None):
        self._on_fullscreen = on_fullscreen
        self._on_restore = on_restore
        self._timer_id = None
        self._enabled = False
        self._fullscreen = False
        self._available = _has_xprop()
        if not self._available:
            logger.warning(
                "fullscreen_monitor: 'xprop' not found. Auto-pause on "
                "fullscreen disabled. Install x11-utils (Debian/Ubuntu) or "
                "xorg-xprop (Arch). KDE Wayland native-window detection "
                "requires a KWin scripting bridge and is not enabled."
            )

    def set_callback(self, on_fullscreen=None, on_restore=None):
        self._on_fullscreen = on_fullscreen
        self._on_restore = on_restore

    @property
    def is_available(self):
        return self._available

    @property
    def is_fullscreen(self):
        return self._fullscreen

    def start(self):
        if self._enabled or not self._available:
            return
        self._enabled = True
        self._timer_id = GLib.timeout_add(POLL_MS, self._tick)
        logger.debug("fullscreen_monitor: polling started (every %d ms)",
                     POLL_MS)

    def stop(self):
        if not self._enabled:
            return
        self._enabled = False
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._fullscreen = False
        logger.debug("fullscreen_monitor: polling stopped")

    def _tick(self):
        if not self._enabled:
            return False
        try:
            fullscreen_now = False
            win_id = _active_window_id()
            if win_id:
                fullscreen_now = _window_is_fullscreen(win_id)
            self._set_fullscreen(fullscreen_now)
        except Exception as e:
            logger.debug("fullscreen_monitor._tick() error: %s", e)
        return True

    def _set_fullscreen(self, value):
        if value == self._fullscreen:
            return
        self._fullscreen = value
        logger.info("fullscreen_monitor: fullscreen=%s", value)
        if value:
            if self._on_fullscreen:
                self._on_fullscreen()
        else:
            if self._on_restore:
                self._on_restore()
