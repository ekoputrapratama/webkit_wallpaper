import os
import signal
import sys


def _is_wayland():
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _desktop_env():
    return os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def _is_gnome_wayland():
    return _is_wayland() and "gnome" in _desktop_env()


def _is_kde_wayland():
    return _is_wayland() and "kde" in _desktop_env()


def _has_nvidia():
    if os.path.exists("/proc/driver/nvidia"):
        return True
    try:
        with open("/proc/modules") as f:
            for line in f:
                if line.startswith("nvidia "):
                    return True
    except OSError:
        pass
    return False


def _apply_platform_workarounds():
    # WebKitGTK's DMABUF renderer fails to allocate GBM buffers on the
    # proprietary NVIDIA driver ("Failed to create GBM buffer: Invalid
    # argument"), which stalls rendering entirely. Fall back to the legacy
    # renderer only when NVIDIA is detected; other GPUs keep full GPU
    # acceleration. Must run before WebKitGTK is loaded.
    if _has_nvidia():
        os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

    # On GNOME Wayland, layer-shell is not supported by mutter and the X11
    # fallback path (via XWayland) is needed for desktop window stacking
    # (DESKTOP type hint). Force GDK_BACKEND=x11 so GTK uses XWayland,
    # enabling X11 window manager hints that mutter respects.
    # KDE KWin supports wlr-layer-shell natively, so KDE Wayland uses the
    # native Wayland backend for better performance.
    # wlroots-based compositors (Sway, Hyprland, etc.) also use layer-shell
    # natively and must stay on the Wayland backend.
    if not _is_gnome_wayland():
        return
    if not os.environ.get("DISPLAY"):
        return
    os.environ.setdefault("GDK_BACKEND", "x11")


_apply_platform_workarounds()

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from webkit_wallpaper import config
from webkit_wallpaper.wallpaper_window import WallpaperWindow
from webkit_wallpaper.tray_icon import TrayIcon
from webkit_wallpaper.settings_dialog import SettingsDialog
from webkit_wallpaper.store_window import StoreWindow
from webkit_wallpaper import autostart


def _apply_system_theme():
    settings = Gtk.Settings.get_default()
    if settings is None:
        return

    prefer_dark = _detect_dark_theme()
    settings.set_property("gtk-application-prefer-dark-theme", prefer_dark)


def _detect_dark_theme():
    gtk_settings = Gtk.Settings.get_default()
    if gtk_settings is None:
        return False
    theme_name = gtk_settings.get_property("gtk-theme-name") or ""
    theme_name = theme_name.lower()
    dark_hints = ["dark", "adwaita-dark", "oppo-dark", "breeze-dark"]
    if any(h in theme_name for h in dark_hints):
        return True
    try:
        schema = Gio.Settings.new("org.gnome.desktop.interface")
        color_scheme = schema.get_string("color-scheme") or ""
        if "dark" in color_scheme.lower():
            return True
        gtk_theme = schema.get_string("gtk-theme") or ""
        if "dark" in gtk_theme.lower():
            return True
    except Exception:
        pass
    return False


class Application:
    def __init__(self):
        self.config = config.load()
        self.wallpaper = WallpaperWindow(self.config, on_url_change=self._on_url_change)
        self.settings_dialog = SettingsDialog(self)
        self.store_window = StoreWindow(self)
        self.tray = TrayIcon(self)

    def _on_url_change(self, url):
        config.save(self.config)

    def show_settings(self):
        self.settings_dialog.present()

    def show_store(self):
        self.store_window.present()

    def toggle_autostart(self):
        autostart.toggle()
        self.config["autostart_enabled"] = autostart.is_enabled()
        config.save(self.config)

    def quit(self):
        config.save(self.config)
        Gtk.main_quit()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    _apply_system_theme()
    app = Application()
    app.wallpaper.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
