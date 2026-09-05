import logging
import os
import signal
import sys


logger = logging.getLogger(__name__)


def _is_wayland():
    result = os.environ.get("XDG_SESSION_TYPE") == "wayland"
    logger.debug("_is_wayland() -> %s", result)
    return result


def _desktop_env():
    result = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    logger.debug("_desktop_env() -> %r", result)
    return result


def _is_gnome_wayland():
    result = _is_wayland() and "gnome" in _desktop_env()
    logger.debug("_is_gnome_wayland() -> %s", result)
    return result


def _is_kde_wayland():
    result = _is_wayland() and "kde" in _desktop_env()
    logger.debug("_is_kde_wayland() -> %s", result)
    return result


def _has_nvidia():
    if os.path.exists("/proc/driver/nvidia"):
        logger.debug("_has_nvidia() -> True (found /proc/driver/nvidia)")
        return True
    try:
        with open("/proc/modules") as f:
            for line in f:
                if line.startswith("nvidia "):
                    logger.debug("_has_nvidia() -> True (found nvidia module)")
                    return True
    except OSError:
        pass
    logger.debug("_has_nvidia() -> False")
    return False


def _apply_platform_workarounds():
    logger.debug("_apply_platform_workarounds() called")
    if _has_nvidia():
        os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
        logger.debug("_apply_platform_workarounds() set WEBKIT_DISABLE_DMABUF_RENDERER=1")

    if not _is_gnome_wayland():
        logger.debug("_apply_platform_workarounds() not gnome wayland, returning")
        return
    if not os.environ.get("DISPLAY"):
        logger.debug("_apply_platform_workarounds() no DISPLAY set, returning")
        return
    os.environ.setdefault("GDK_BACKEND", "x11")
    logger.debug("_apply_platform_workarounds() set GDK_BACKEND=x11")


_apply_platform_workarounds()

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from webkit_wallpaper import config
from webkit_wallpaper.wallpaper_window import WallpaperWindow
from webkit_wallpaper.fullscreen_monitor import create_monitor
from webkit_wallpaper.tray_icon import TrayIcon
from webkit_wallpaper.settings_dialog import SettingsDialog
from webkit_wallpaper.store_window import StoreWindow
from webkit_wallpaper import autostart
from webkit_wallpaper.wallpaper_window import HAS_LAYER_SHELL


def _apply_system_theme():
    logger.debug("_apply_system_theme() called")
    settings = Gtk.Settings.get_default()
    if settings is None:
        logger.debug("_apply_system_theme() Gtk.Settings.get_default() returned None")
        return

    prefer_dark = _detect_dark_theme()
    settings.set_property("gtk-application-prefer-dark-theme", prefer_dark)
    logger.debug("_apply_system_theme() set prefer_dark=%s", prefer_dark)


def _detect_dark_theme():
    logger.debug("_detect_dark_theme() called")
    gtk_settings = Gtk.Settings.get_default()
    if gtk_settings is None:
        logger.debug("_detect_dark_theme() -> False (no Gtk.Settings)")
        return False
    theme_name = gtk_settings.get_property("gtk-theme-name") or ""
    theme_name = theme_name.lower()
    dark_hints = ["dark", "adwaita-dark", "oppo-dark", "breeze-dark"]
    if any(h in theme_name for h in dark_hints):
        logger.debug("_detect_dark_theme() -> True (theme_name=%r matched dark hint)", theme_name)
        return True
    try:
        schema = Gio.Settings.new("org.gnome.desktop.interface")
        color_scheme = schema.get_string("color-scheme") or ""
        if "dark" in color_scheme.lower():
            logger.debug("_detect_dark_theme() -> True (color_scheme=%r)", color_scheme)
            return True
        gtk_theme = schema.get_string("gtk-theme") or ""
        if "dark" in gtk_theme.lower():
            logger.debug("_detect_dark_theme() -> True (gtk_theme=%r)", gtk_theme)
            return True
    except Exception as e:
        logger.debug("_detect_dark_theme() exception: %s", e)
    logger.debug("_detect_dark_theme() -> False")
    return False


class Application:
    def __init__(self):
        logger.debug("Application.__init__() called")
        self.config = config.load()
        self.wallpaper = WallpaperWindow(self.config, on_url_change=self._on_url_change)
        self.settings_dialog = SettingsDialog(self)
        self.store_window = StoreWindow(self)
        self.tray = TrayIcon(self)
        self.monitor = create_monitor(
            on_fullscreen=self._on_fullscreen,
            on_restore=self._on_restore,
        )
        self._apply_auto_pause()
        logger.debug("Application.__init__() done")

    def _on_fullscreen(self):
        logger.debug("Application._on_fullscreen()")
        if self.config.get("auto_pause", True) and not self.wallpaper.is_paused():
            self.wallpaper.pause()

    def _on_restore(self):
        logger.debug("Application._on_restore()")
        if self.wallpaper.is_paused():
            self.wallpaper.resume()

    def set_auto_pause(self, enabled):
        logger.debug("Application.set_auto_pause(enabled=%s)", enabled)
        self.config["auto_pause"] = bool(enabled)
        config.save(self.config)
        if not enabled and self.wallpaper.is_paused():
            self.wallpaper.resume()
        self._apply_auto_pause()

    def _apply_auto_pause(self):
        logger.debug("Application._apply_auto_pause()")
        if self.config.get("auto_pause", True) and self.monitor.is_available:
            self.monitor.start()
        else:
            self.monitor.stop()

    def toggle_pause(self):
        logger.debug("Application.toggle_pause()")
        if self.wallpaper.is_paused():
            self.wallpaper.resume()
        else:
            self.wallpaper.pause()

    def _on_url_change(self, url):
        logger.debug("Application._on_url_change(url=%s)", url)
        config.save(self.config)

    def show_settings(self):
        logger.debug("Application.show_settings()")
        self.settings_dialog.present()

    def show_store(self):
        logger.debug("Application.show_store()")
        self.store_window.present()

    def toggle_autostart(self):
        logger.debug("Application.toggle_autostart()")
        autostart.toggle()
        self.config["autostart_enabled"] = autostart.is_enabled()
        config.save(self.config)

    def quit(self):
        logger.debug("Application.quit()")
        config.save(self.config)
        Gtk.main_quit()


def main():
    logger.debug("main() called")
    if _is_wayland() and not HAS_LAYER_SHELL:
        logger.warning(
            "GtkLayerShell bindings (gir1.2-gtklayershell-0.1) not installed. "
            "Falling back to X11 desktop hints. Install the GTK layer-shell "
            "package (NOT layer-shell-qt, which is Qt-only) for proper Wayland "
            "placement: sudo apt install gir1.2-gtklayershell-0.1"
        )
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    _apply_system_theme()
    app = Application()

    def _on_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down gracefully")
        try:
            app.quit()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _on_sigterm)

    app.wallpaper.show_all()
    logger.debug("main() entering Gtk.main()")
    Gtk.main()
    logger.debug("main() Gtk.main() returned")


if __name__ == "__main__":
    main()
